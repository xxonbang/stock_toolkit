"""뉴스/커뮤니티/유튜브 TOP3 리포트 생성 (Stock Insight)

매일 KST 07:30, 20:00 GitHub Actions에서 실행.
출력: results/news_top3_latest.json + results/news_top3_history/{YYYY-MM-DD-HHMM}.json

흐름:
  collect → extract (LLM #1) → top3 (LLM #2) → outlook (LLM #3, Google Search grounding)
  + 유튜브 별도 분석 (LLM)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (modules.* import용)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.news.collectors import (  # noqa: E402
    base,
    us_news,
    us_community,
    kr_news,
    kr_community,
    youtube,
)

KST = timezone(timedelta(hours=9))
logger = logging.getLogger("news_top3")

HISTORY_RETENTION_DAYS = 31
RESULTS_DIR = ROOT / "results"
HISTORY_DIR = RESULTS_DIR / "news_top3_history"


def _serialize_item(it) -> dict:
    """CollectedItem 또는 YoutubeVideo → dict (JSON 직렬화 가능, 모든 시간은 KST)"""
    if is_dataclass(it):
        d = asdict(it)
        for k, v in d.items():
            if isinstance(v, datetime):
                # 모든 timestamp를 KST로 변환하여 직렬화
                kst = v.astimezone(KST) if v.tzinfo else v.replace(tzinfo=KST)
                d[k] = kst.strftime("%Y-%m-%d %H:%M:%S KST")
        return d
    return dict(it)


def collect_all(now: datetime) -> dict:
    """4개 텍스트 배치 + 유튜브 영상 수집"""
    logger.info("=== 수집 시작 ===")
    result = {
        "us_news": us_news.collect(now=now),
        "us_community": us_community.collect(now=now),
        "kr_news": kr_news.collect(now=now),
        "kr_community": kr_community.collect(now=now.astimezone(KST)),
        "youtube": youtube.collect(now=now),
    }
    logger.info(
        f"수집 완료: us_news={len(result['us_news'])}, us_community={len(result['us_community'])}, "
        f"kr_news={len(result['kr_news'])}, kr_community={len(result['kr_community'])}, "
        f"youtube={len(result['youtube'])}"
    )
    return result


def cleanup_history(retention_days: int = HISTORY_RETENTION_DAYS) -> int:
    """retention_days 이전의 history 파일 삭제. 삭제된 개수 반환."""
    if not HISTORY_DIR.exists():
        return 0
    cutoff = time.time() - retention_days * 86400
    removed = 0
    for f in HISTORY_DIR.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            f.unlink()
            removed += 1
    if removed:
        logger.info(f"history 정리: {removed}개 삭제 (>{retention_days}일)")
    return removed


def save_outputs(payload: dict, now_kst: datetime) -> None:
    """latest + history 동시 기록"""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    latest_path = RESULTS_DIR / "news_top3_latest.json"
    history_path = HISTORY_DIR / f"{now_kst.strftime('%Y-%m-%d-%H%M')}.json"
    with latest_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    with history_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"저장: {latest_path}")
    logger.info(f"저장: {history_path}")


def build_payload_phase1(collected: dict, now_kst: datetime) -> dict:
    """수집 결과만 직렬화 (AI 분석 실패 폴백 또는 --skip-ai 옵션 시)."""
    return {
        "generated_at": now_kst.strftime("%Y-%m-%d %H:%M KST"),
        "phase": 1,
        "us": {
            "news": [_serialize_item(it) for it in collected["us_news"]],
            "community": [_serialize_item(it) for it in collected["us_community"]],
        },
        "kr": {
            "news": [_serialize_item(it) for it in collected["kr_news"]],
            "community": [_serialize_item(it) for it in collected["kr_community"]],
        },
        "youtube": {
            "videos": [_serialize_item(v) for v in collected["youtube"]],
        },
    }


def build_payload_full(collected: dict, top3: dict, outlook: dict, yt_top3: dict, now_kst: datetime) -> dict:
    """AI 분석 결과 통합 — 프론트엔드가 읽을 최종 스키마."""
    return {
        "generated_at": now_kst.strftime("%Y-%m-%d %H:%M KST"),
        "phase": 2,
        "us": {
            "top3_sectors": top3.get("us_top3_sectors", []),
            "top3_stocks": top3.get("us_top3_stocks", []),
            "outlook": outlook.get("us", {}),
            "collected": {
                "news": len(collected["us_news"]),
                "community": len(collected["us_community"]),
            },
        },
        "kr": {
            "top3_sectors": top3.get("kr_top3_sectors", []),
            "top3_stocks": top3.get("kr_top3_stocks", []),
            "outlook": outlook.get("kr", {}),
            "collected": {
                "news": len(collected["kr_news"]),
                "community": len(collected["kr_community"]),
            },
        },
        "youtube": {
            "top3_sectors": yt_top3.get("top3_sectors", []),
            "top3_stocks": yt_top3.get("top3_stocks", []),
            "videos_collected": len(collected["youtube"]),
        },
    }


def run_ai_pipeline(collected: dict, now_kst: datetime) -> dict:
    """3단계 LLM 분석. 어느 단계든 실패 시 Phase 1 페이로드로 폴백."""
    from modules.news import ai_client, extractor

    client = ai_client.create_client()
    batches = {
        "us_news": collected["us_news"],
        "us_community": collected["us_community"],
        "kr_news": collected["kr_news"],
        "kr_community": collected["kr_community"],
    }

    try:
        logger.info("=== AI 추출 (LLM #1) ===")
        extraction = extractor.extract_per_batch(batches, client)
    except Exception as e:
        logger.error(f"extract 실패: {e} — Phase 1 폴백")
        return build_payload_phase1(collected, now_kst)

    try:
        logger.info("=== TOP3 선정 (LLM #2) ===")
        top3 = extractor.select_top3(extraction, client)
    except Exception as e:
        logger.error(f"top3 실패: {e}")
        top3 = {"us_top3_sectors": [], "us_top3_stocks": [], "kr_top3_sectors": [], "kr_top3_stocks": []}

    outlook: dict = {}
    try:
        logger.info("=== 1주일 전망 (LLM #3, Google Search grounding) ===")
        outlook = extractor.generate_outlook(top3, client)
    except Exception as e:
        logger.warning(f"outlook 실패: {e}")
        outlook = {}

    yt_top3 = {"top3_sectors": [], "top3_stocks": []}
    try:
        logger.info("=== YouTube TOP3 분석 ===")
        yt_top3 = extractor.analyze_youtube(collected["youtube"], client)
    except Exception as e:
        logger.warning(f"youtube 분석 실패: {e}")

    return build_payload_full(collected, top3, outlook, yt_top3, now_kst)


def main() -> int:
    parser = argparse.ArgumentParser(description="Stock Insight 수집/분석 (수집 + 3단계 LLM 분석)")
    parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 콘솔 요약만")
    parser.add_argument("--skip-ai", action="store_true", help="AI 분석 생략, Phase 1 페이로드만")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    # 로그 timestamp를 KST로 표시 (GitHub Actions runner는 기본 UTC).
    logging.Formatter.converter = lambda *args: datetime.now(KST).timetuple()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s KST %(levelname)s %(name)s %(message)s",
    )

    # 로컬 .env 로드 (GitHub Actions에서는 secrets로 주입).
    # 루트 .env 우선, daemon/.env 보조 (둘 다 존재할 경우 루트가 이미 set한 키는 유지).
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        load_dotenv(ROOT / "daemon" / ".env")
    except ImportError:
        pass

    now_utc = datetime.now(timezone.utc)
    now_kst = now_utc.astimezone(KST)

    collected = collect_all(now_utc)

    if args.skip_ai:
        payload = build_payload_phase1(collected, now_kst)
    else:
        payload = run_ai_pipeline(collected, now_kst)

    if args.dry_run:
        phase = payload.get("phase", "?")
        print(f"[DRY-RUN] phase={phase} generated_at={payload['generated_at']}")
        if phase == 2:
            print(f"  us.top3_sectors={len(payload['us']['top3_sectors'])}, us.top3_stocks={len(payload['us']['top3_stocks'])}")
            print(f"  kr.top3_sectors={len(payload['kr']['top3_sectors'])}, kr.top3_stocks={len(payload['kr']['top3_stocks'])}")
            print(f"  youtube.top3_sectors={len(payload['youtube']['top3_sectors'])}, youtube.top3_stocks={len(payload['youtube']['top3_stocks'])}")
        else:
            print(f"  us.news={len(payload['us']['news'])}, us.community={len(payload['us']['community'])}")
            print(f"  kr.news={len(payload['kr']['news'])}, kr.community={len(payload['kr']['community'])}")
        return 0

    save_outputs(payload, now_kst)
    cleanup_history()
    return 0


if __name__ == "__main__":
    sys.exit(main())
