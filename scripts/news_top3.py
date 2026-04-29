"""뉴스/커뮤니티/유튜브 TOP3 리포트 생성 (Stock Insight)

매일 KST 07:30, 20:00 GitHub Actions에서 실행.
출력: results/news_top3_latest.json + results/news_top3_history/{YYYY-MM-DD-HHMM}.json

Phase 1: 수집기 골격 (4개 텍스트 배치 + 유튜브 영상)만 동작. AI 분석은 Phase 2에서 추가.
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
    """CollectedItem 또는 YoutubeVideo → dict (JSON 직렬화 가능)"""
    if is_dataclass(it):
        d = asdict(it)
        # datetime → ISO 문자열
        for k, v in d.items():
            if isinstance(v, datetime):
                d[k] = v.isoformat()
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
    """Phase 1: 수집 결과만 직렬화 (AI 분석 없음). Phase 2에서 top3/outlook 추가 예정."""
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Stock Insight 수집/분석 (Phase 1: 수집만)")
    parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 콘솔 요약만")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    # 로컬 .env 로드 (GitHub Actions에서는 secrets로 주입)
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / "daemon" / ".env")  # YOUTUBE_API_KEY 위치
    except ImportError:
        pass

    now_utc = datetime.now(timezone.utc)
    now_kst = now_utc.astimezone(KST)

    collected = collect_all(now_utc)
    payload = build_payload_phase1(collected, now_kst)

    if args.dry_run:
        print(f"[DRY-RUN] generated_at={payload['generated_at']}")
        print(f"  us.news={len(payload['us']['news'])}, us.community={len(payload['us']['community'])}")
        print(f"  kr.news={len(payload['kr']['news'])}, kr.community={len(payload['kr']['community'])}")
        print(f"  youtube.videos={len(payload['youtube']['videos'])}")
        return 0

    save_outputs(payload, now_kst)
    cleanup_history()
    return 0


if __name__ == "__main__":
    sys.exit(main())
