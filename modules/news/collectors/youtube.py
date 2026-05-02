"""유튜브 영상 수집 — YouTube Data API v3 + youtube-transcript-api

최근 7일 내 업로드된 한국 주식 관련 유명 채널의 영상 10개 수집.
영상 메타데이터(제목, 설명, 채널)와 자막을 묶어 분석에 활용.

채널 선정 기준 (2026-04-29 검증):
- 매일/주기적 시황 콘텐츠 또는 권위 있는 거시 분석 채널만 채택
- 신사임당(2022년 채널 양도로 정체성 약화), 김작가TV(자기계발 중심),
  박곰희TV(자산관리 중심) 제외
- playboard.co 인기순위 + 콘텐츠 적합성으로 4개 채널 보강
"""
import html
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# 한국 주식 유튜브 채널 5개 (사용자 명시, 2026-04-29)
# 종합 시황/경제: 삼프로TV, 슈카월드, 김작가TV
# 미국 주식/ETF: 소수몽키, 올랜도 킴 미국주식
KR_STOCK_CHANNELS = [
    ("UChlv4GSd7OQl3js-jkLOnFA", "삼프로TV"),
    ("UCsJ6RuBiTVWRX156FVbeaGg", "슈카월드"),
    ("UCvil4OAt-zShzkKHsg9EQAw", "김작가 TV"),
    ("UCC3yfxS5qC6PCwDzetUuEWg", "소수몽키"),
    ("UC84OTRAO0FMDgMY1u9pbOBg", "올랜도 킴 미국주식"),
]

# 영상 수가 부족할 때 조사 기간을 점진 확장 (주 단위). 키워드 검색은 데이터 폭을
# 제한해 오히려 품질을 저하시키므로 사용하지 않음.
EXPAND_WEEKS = (1, 2, 3, 4)


@dataclass
class YoutubeVideo:
    """수집된 유튜브 영상 1건"""
    video_id: str
    title: str
    description: str
    channel_name: str
    published_at: datetime  # tz-aware (UTC 또는 KST)
    transcript: str = ""  # 자막 텍스트 (있으면)
    url: str = field(default="")

    def __post_init__(self):
        if not self.url:
            self.url = f"https://www.youtube.com/watch?v={self.video_id}"


def _get_client():
    """YouTube Data API client. 환경변수에서 API key 로드."""
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY 환경변수 미설정")
    return build("youtube", "v3", developerKey=api_key, cache_discovery=False)


def _list_recent_videos_from_channel(youtube, channel_id: str, since: datetime, max_results: int = 5) -> List[dict]:
    """채널의 최근 영상 목록 (since 이후)"""
    try:
        # search.list로 채널의 최근 영상 가져오기 (publishedAfter 필터)
        published_after = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        request = youtube.search().list(
            channelId=channel_id,
            part="id,snippet",
            order="date",
            type="video",
            publishedAfter=published_after,
            maxResults=max_results,
        )
        response = request.execute()
        return response.get("items", [])
    except Exception as e:
        logger.warning(f"YouTube 채널 검색 실패 ({channel_id[:8]}...): {e}")
        return []


def _fetch_transcript_via_api(video_id: str) -> str:
    """기존 youtube-transcript-api 경로 — 로컬에서는 작동, GitHub Actions runner IP는 차단됨."""
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=["ko", "en"])
        text_parts = []
        for seg in fetched:
            t = getattr(seg, "text", None) or (seg.get("text") if isinstance(seg, dict) else None)
            if t:
                text_parts.append(t)
        return " ".join(text_parts)[:5000]
    except (TranscriptsDisabled, NoTranscriptFound):
        return ""
    except Exception as e:
        logger.debug(f"transcript-api fetch 실패 ({video_id}): {e}")
        return ""


_YTDLP_DIAG_DONE = False  # 첫 호출만 stderr 풀 출력 (이후엔 요약)


def _fetch_transcript_via_ytdlp(video_id: str) -> str:
    """yt-dlp로 자동/수동 자막 다운로드. GitHub Actions IP 차단 시 같이 차단될 수 있음."""
    global _YTDLP_DIAG_DONE
    import subprocess, tempfile, json as _json, glob, os as _os
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            url = f"https://www.youtube.com/watch?v={video_id}"
            # yt-dlp 2026 호환: --sub-format은 best/srt/vtt만, json3는 invalid
            # 전략: vtt로 다운로드 → 정규식으로 텍스트만 추출
            cmd = [
                "yt-dlp", url,
                "--skip-download",
                "--write-auto-subs", "--write-subs",
                "--sub-langs", "ko,en",
                "--sub-format", "vtt/best",
                "-o", _os.path.join(tmpdir, "%(id)s"),
                "--no-warnings",
                "--extractor-args", "youtube:player_client=web,ios",
            ]
            res = subprocess.run(cmd, capture_output=True, timeout=60, check=False, text=True)
            # 첫 호출은 stderr 풀 출력 (디버깅), 이후엔 단축
            if not _YTDLP_DIAG_DONE:
                _YTDLP_DIAG_DONE = True
                logger.info(f"[yt-dlp 진단] returncode={res.returncode}")
                if res.stderr:
                    logger.info(f"[yt-dlp stderr 앞 1000자]: {res.stderr[:1000]}")
                if res.stdout:
                    logger.info(f"[yt-dlp stdout 앞 500자]: {res.stdout[:500]}")
            # 자막 파일 검색 (vtt) + 정규식 텍스트 추출
            import re
            for lang in ("ko", "en"):
                pattern = _os.path.join(tmpdir, f"{video_id}.{lang}.vtt")
                files = glob.glob(pattern)
                if not files:
                    continue
                try:
                    with open(files[0], encoding="utf-8") as f:
                        raw = f.read()
                except Exception as e:
                    logger.debug(f"yt-dlp vtt 읽기 실패 ({video_id}, {lang}): {e}")
                    continue
                # vtt 포맷: timestamp 라인 + 텍스트 라인 — 텍스트 라인만 추출
                lines = []
                for line in raw.split("\n"):
                    line = line.strip()
                    if not line: continue
                    if line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
                        continue
                    if "-->" in line:  # timestamp 라인 (00:00:01.000 --> 00:00:03.000)
                        continue
                    if line.isdigit():  # cue 번호
                        continue
                    # vtt 인라인 태그 제거 (<c>, <00:00:01.000>)
                    cleaned = re.sub(r"<[^>]+>", "", line).strip()
                    if cleaned:
                        lines.append(cleaned)
                text = " ".join(lines)
                if text.strip():
                    if not _YTDLP_DIAG_DONE or len(text) < 100:
                        logger.info(f"[yt-dlp] {video_id} {lang} 자막 {len(text)}자 추출")
                    return text[:5000]
            # 자막 파일 0개 — stderr 단축 출력
            if res.returncode != 0 and _YTDLP_DIAG_DONE:
                stderr_short = (res.stderr or "").split("\n")[0][:200] if res.stderr else "(empty)"
                logger.debug(f"yt-dlp 자막 0개 ({video_id}, rc={res.returncode}): {stderr_short}")
            return ""
    except subprocess.TimeoutExpired:
        logger.warning(f"yt-dlp 타임아웃 ({video_id}) — 60s 초과")
        return ""
    except FileNotFoundError:
        logger.error("yt-dlp 미설치 — requirements.txt 확인 필요")
        return ""
    except Exception as e:
        logger.warning(f"yt-dlp 예외 ({video_id}): {type(e).__name__}: {e}")
        return ""


def _fetch_transcript_via_supabase(video_id: str) -> str:
    """Supabase youtube_transcripts에서 자막 SELECT (GCP 데몬이 미리 저장).
    GitHub Actions IP는 YouTube 봇 차단으로 자막 직접 fetch 불가 → 데몬이 사전 수집.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_PUBLISHABLE_KEY")
    if not url or not key:
        return ""
    try:
        import urllib.request, json
        req = urllib.request.Request(
            f"{url}/rest/v1/youtube_transcripts?video_id=eq.{video_id}&select=transcript",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            rows = json.loads(r.read())
        if rows and rows[0].get("transcript"):
            return rows[0]["transcript"][:5000]
    except Exception as e:
        logger.debug(f"supabase 자막 조회 실패 ({video_id}): {e}")
    return ""


def _fetch_transcript(video_id: str) -> str:
    """자막 추출 (3-tier fallback).
    1순위: Supabase (GCP 데몬이 미리 수집한 자막) — GitHub Actions에서 가장 안정
    2순위: youtube-transcript-api — 로컬에서 정상, GitHub IP 차단
    3순위: yt-dlp — 동일하게 GitHub IP 차단 대상이나 백업
    """
    text = _fetch_transcript_via_supabase(video_id)
    if text:
        return text
    text = _fetch_transcript_via_api(video_id)
    if text:
        return text
    return _fetch_transcript_via_ytdlp(video_id)


def _item_to_video(item: dict, channel_name_override: Optional[str] = None) -> Optional[YoutubeVideo]:
    """YouTube API 응답 항목 → YoutubeVideo. HTML entity 디코드(&#39; 등)."""
    snippet = item.get("snippet") or {}
    video_id = (item.get("id") or {}).get("videoId") if isinstance(item.get("id"), dict) else item.get("id")
    if not video_id:
        return None
    title = html.unescape((snippet.get("title") or "").strip())
    description = html.unescape((snippet.get("description") or "").strip())
    channel_name = channel_name_override or html.unescape(snippet.get("channelTitle", ""))
    published_str = snippet.get("publishedAt", "")
    try:
        published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return YoutubeVideo(
        video_id=video_id,
        title=title,
        description=description,
        channel_name=channel_name,
        published_at=published,
    )


def collect(now: Optional[datetime] = None, limit: int = 10) -> List[YoutubeVideo]:
    """5채널의 한국 주식 영상 수집. limit 미달 시 조사 기간을 1주씩 확장 (최대 4주).
    키워드 검색은 데이터 폭을 제한하므로 사용 안 함.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    try:
        youtube = _get_client()
    except Exception as e:
        logger.error(f"YouTube client 초기화 실패: {e}")
        return []

    seen_video_ids = set()
    videos: List[YoutubeVideo] = []

    # 7일 → 14일 → 21일 → 28일 점진 확장 (limit 채우면 조기 종료)
    for weeks in EXPAND_WEEKS:
        if len(videos) >= limit:
            break
        since = now - timedelta(days=7 * weeks)
        max_per_channel = 3 * weeks  # 회차마다 더 많은 과거 영상 fetch
        before = len(videos)
        per_channel_added = {}
        for channel_id, channel_name in KR_STOCK_CHANNELS:
            items = _list_recent_videos_from_channel(youtube, channel_id, since, max_results=max_per_channel)
            ch_before = len(videos)
            for item in items:
                v = _item_to_video(item, channel_name_override=channel_name)
                if not v or v.video_id in seen_video_ids:
                    continue
                seen_video_ids.add(v.video_id)
                videos.append(v)
            per_channel_added[channel_name] = len(videos) - ch_before
        added = len(videos) - before
        logger.info(f"  YouTube {weeks}주 확장: +{added}개 (누적 {len(videos)}/{limit}) — 채널별: {per_channel_added}")

    # 발행 시간 내림차순 + limit 적용
    videos.sort(key=lambda x: x.published_at, reverse=True)
    videos = videos[:limit]

    # 자막 추출 (limit 영상에 한해)
    transcript_failures = []
    for v in videos:
        v.transcript = _fetch_transcript(v.video_id)
        if not v.transcript:
            transcript_failures.append(v.video_id[:8] + "..")
    if transcript_failures:
        logger.info(f"  자막 추출 실패: {len(transcript_failures)}/{len(videos)}건 → {transcript_failures}")

    logger.info(
        f"youtube 수집 완료: {len(videos)}개 (자막 있음 "
        f"{sum(1 for v in videos if v.transcript)}개)"
    )
    return videos


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # 로컬 실행 시 .env 로드 (GitHub Actions에서는 환경변수로 주입됨)
    try:
        from dotenv import load_dotenv
        from pathlib import Path
        load_dotenv(Path(__file__).parent.parent.parent / ".env")
    except ImportError:
        pass
    for v in collect():
        ts = v.published_at.astimezone(KST).strftime("%Y-%m-%d %H:%M")
        print(f"[{ts}] [{v.channel_name}] {v.title}")
        print(f"  자막: {len(v.transcript)}자")
