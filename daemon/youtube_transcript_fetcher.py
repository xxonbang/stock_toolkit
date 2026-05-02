"""GCP ws-daemon 전용 — YouTube 자막 수집 후 Supabase에 저장.

GitHub Actions IP는 YouTube 봇 차단을 받아 자막 추출 불가.
GCP 정적 IP는 차단되지 않으므로 데몬에서 자막을 미리 수집해 youtube_transcripts
테이블에 저장하고, GitHub Actions에서 SELECT만 수행.

스케줄: KST 07:25, 19:55 (news-top3.yml cron 5분 전 실행).
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import aiohttp

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

# 동일 5채널 (modules/news/collectors/youtube.py와 일치)
KR_STOCK_CHANNELS = [
    ("UChlv4GSd7OQl3js-jkLOnFA", "삼프로TV"),
    ("UCsJ6RuBiTVWRX156FVbeaGg", "슈카월드"),
    ("UCvil4OAt-zShzkKHsg9EQAw", "김작가 TV"),
    ("UCC3yfxS5qC6PCwDzetUuEWg", "소수몽키"),
    ("UC84OTRAO0FMDgMY1u9pbOBg", "올랜도 킴 미국주식"),
]

RETENTION_DAYS = 30
MAX_VIDEOS_PER_CHANNEL = 3


def _list_recent_videos(youtube_client, channel_id: str, since: datetime, max_results: int = 3) -> list:
    try:
        published_after = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        req = youtube_client.search().list(
            channelId=channel_id,
            part="id,snippet",
            order="date",
            type="video",
            publishedAfter=published_after,
            maxResults=max_results,
        )
        resp = req.execute()
        return resp.get("items", [])
    except Exception as e:
        logger.warning(f"YouTube 채널 검색 실패 ({channel_id[:8]}): {e}")
        return []


def _fetch_via_api(video_id: str) -> tuple[str, str]:
    """youtube-transcript-api. 성공 시 (text, language) 반환."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
        api = YouTubeTranscriptApi()
        try:
            fetched = api.fetch(video_id, languages=["ko"])
            lang = "ko"
        except NoTranscriptFound:
            fetched = api.fetch(video_id, languages=["en"])
            lang = "en"
        parts = []
        for seg in fetched:
            t = getattr(seg, "text", None) or (seg.get("text") if isinstance(seg, dict) else None)
            if t:
                parts.append(t)
        text = " ".join(parts)[:5000]
        return text, lang
    except (TranscriptsDisabled, NoTranscriptFound):
        return "", ""
    except Exception as e:
        logger.debug(f"transcript-api 실패 ({video_id}): {e}")
        return "", ""


def _fetch_via_ytdlp(video_id: str) -> tuple[str, str]:
    """yt-dlp fallback (vtt 포맷)."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            url = f"https://www.youtube.com/watch?v={video_id}"
            cmd = [
                "yt-dlp", url,
                "--skip-download",
                "--write-auto-subs", "--write-subs",
                "--sub-langs", "ko,en",
                "--sub-format", "vtt/best",
                "-o", os.path.join(tmpdir, "%(id)s"),
                "--no-warnings",
            ]
            res = subprocess.run(cmd, capture_output=True, timeout=60, check=False, text=True)
            if res.returncode != 0:
                logger.debug(f"yt-dlp rc={res.returncode} ({video_id}): {(res.stderr or '')[:200]}")
                return "", ""
            for lang in ("ko", "en"):
                files = list(Path(tmpdir).glob(f"{video_id}.{lang}.vtt"))
                if not files:
                    continue
                raw = files[0].read_text(encoding="utf-8")
                lines = []
                for line in raw.split("\n"):
                    line = line.strip()
                    if not line or line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
                        continue
                    if "-->" in line or line.isdigit():
                        continue
                    cleaned = re.sub(r"<[^>]+>", "", line).strip()
                    if cleaned:
                        lines.append(cleaned)
                text = " ".join(lines)
                if text.strip():
                    return text[:5000], lang
            return "", ""
    except subprocess.TimeoutExpired:
        logger.warning(f"yt-dlp 타임아웃 ({video_id})")
        return "", ""
    except FileNotFoundError:
        logger.warning("yt-dlp 미설치 — pip install yt-dlp 필요")
        return "", ""
    except Exception as e:
        logger.debug(f"yt-dlp 예외 ({video_id}): {e}")
        return "", ""


async def _supabase_request(method: str, url: str, *, json_body=None, headers=None) -> tuple[int, str]:
    """간이 Supabase REST 호출."""
    from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
    from daemon.http_session import get_session
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return 0, "config 누락"
    session = await get_session()
    h = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
         "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"}
    if headers:
        h.update(headers)
    try:
        async with session.request(method, url, headers=h, json=json_body, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            text = await resp.text() if resp.status >= 400 else ""
            return resp.status, text
    except Exception as e:
        return 0, str(e)


async def _upsert_transcript(row: dict) -> bool:
    from daemon.config import SUPABASE_URL
    url = f"{SUPABASE_URL}/rest/v1/youtube_transcripts"
    status, err = await _supabase_request("POST", url, json_body=row)
    if status in (200, 201, 204):
        return True
    logger.warning(f"upsert 실패 video_id={row.get('video_id')}: {status} {err[:150]}")
    return False


async def _cleanup_old() -> int:
    """30일 이전 자막 삭제."""
    from daemon.config import SUPABASE_URL
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"{SUPABASE_URL}/rest/v1/youtube_transcripts?fetched_at=lt.{cutoff}"
    status, err = await _supabase_request("DELETE", url)
    if status in (200, 204):
        logger.info(f"오래된 자막 정리 완료 (>{RETENTION_DAYS}일)")
        return 0
    logger.warning(f"자막 정리 실패: {status} {err[:100]}")
    return 1


def _build_youtube_client():
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY 환경변수 미설정")
    from googleapiclient.discovery import build
    return build("youtube", "v3", developerKey=api_key, cache_discovery=False)


async def fetch_and_store_transcripts() -> dict:
    """5채널 × 최근 7일 영상 자막 fetch → Supabase upsert.
    이미 저장된 video_id는 스킵 (중복 fetch 방지)."""
    logger.info("=" * 60)
    logger.info("YouTube 자막 수집 시작 — 5채널 × 최근 7일")
    try:
        yt = _build_youtube_client()
    except Exception as e:
        logger.error(f"YouTube client 초기화 실패: {e}")
        return {"error": str(e)}

    since = datetime.now(timezone.utc) - timedelta(days=7)
    seen: set[str] = set()
    candidates: list[dict] = []
    for channel_id, channel_name in KR_STOCK_CHANNELS:
        items = _list_recent_videos(yt, channel_id, since, max_results=MAX_VIDEOS_PER_CHANNEL)
        for it in items:
            vid = (it.get("id") or {}).get("videoId")
            if not vid or vid in seen:
                continue
            seen.add(vid)
            sn = it.get("snippet") or {}
            candidates.append({
                "video_id": vid,
                "channel_id": channel_id,
                "channel_name": channel_name,
                "title": sn.get("title", "")[:500],
                "published_at": sn.get("publishedAt"),
            })
    logger.info(f"채널 검색 완료: 후보 {len(candidates)}개")

    # 이미 저장된 video_id 조회 (중복 fetch 회피)
    from daemon.config import SUPABASE_URL
    existing = set()
    if candidates:
        ids_filter = ",".join(f'"{c["video_id"]}"' for c in candidates)
        url = f"{SUPABASE_URL}/rest/v1/youtube_transcripts?video_id=in.({ids_filter})&select=video_id"
        from daemon.config import SUPABASE_SECRET_KEY
        from daemon.http_session import get_session
        session = await get_session()
        try:
            async with session.get(url, headers={"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    for row in (await resp.json()) or []:
                        existing.add(row["video_id"])
        except Exception as e:
            logger.warning(f"기존 자막 조회 실패: {e}")

    new_videos = [c for c in candidates if c["video_id"] not in existing]
    logger.info(f"신규 fetch 대상: {len(new_videos)}개 (이미 저장: {len(existing)}개)")

    fetched = 0
    failed = 0
    for c in new_videos:
        text, lang = await asyncio.to_thread(_fetch_via_api, c["video_id"])
        source = "transcript-api"
        if not text:
            text, lang = await asyncio.to_thread(_fetch_via_ytdlp, c["video_id"])
            source = "yt-dlp"
        if not text:
            failed += 1
            logger.debug(f"  자막 추출 실패: {c['video_id']} [{c['channel_name']}]")
            continue
        row = {**c, "transcript": text, "language": lang, "source": source}
        ok = await _upsert_transcript(row)
        if ok:
            fetched += 1
            logger.info(f"  [{c['channel_name']}] {c['title'][:40]} ({source}, {lang}, {len(text)}자)")
        else:
            failed += 1

    await _cleanup_old()
    logger.info(f"YouTube 자막 수집 완료: 신규 {fetched}건, 실패 {failed}건, 스킵 {len(existing)}건")
    logger.info("=" * 60)
    return {"new": fetched, "failed": failed, "skipped": len(existing)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
    load_dotenv(Path(__file__).parent / ".env")
    asyncio.run(fetch_and_store_transcripts())
