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
    base,  # noqa: F401
    us_news,
    kr_news,
    youtube,
)
# us_community / kr_community 비활성화 (2026-04-29) — 잡담·작전성 비율 높아 실효성 낮음.
# collector 파일은 보존 (향후 재활성화 시 import만 추가).

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
    """2개 뉴스 배치(미/한) + 유튜브 영상 수집"""
    logger.info("=== 수집 시작 ===")
    result = {
        "us_news": us_news.collect(now=now),
        "kr_news": kr_news.collect(now=now),
        "youtube": youtube.collect(now=now),
    }
    logger.info(
        f"수집 완료: us_news={len(result['us_news'])}, kr_news={len(result['kr_news'])}, "
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


def write_history_index() -> None:
    """results/news_top3_index.json 갱신 — 프론트가 히스토리 드롭다운용으로 사용.

    GitHub Pages는 디렉토리 listing 미지원이라 인덱스 파일 별도 필요.
    """
    if not HISTORY_DIR.exists():
        return
    files = sorted(
        (f for f in HISTORY_DIR.iterdir() if f.is_file() and f.suffix == ".json"),
        key=lambda p: p.stem,
        reverse=True,
    )
    entries = []
    for f in files:
        # 파일명: YYYY-MM-DD-HHMM (예: 2026-04-30-0730)
        stem = f.stem
        if len(stem) == 15 and stem[10] == "-":
            kst_label = f"{stem[:10]} {stem[11:13]}:{stem[13:15]} KST"
        else:
            kst_label = stem
        entries.append({"filename": f.name, "kst": kst_label})
    index = {
        "generated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"),
        "count": len(entries),
        "history": entries,
    }
    out = RESULTS_DIR / "news_top3_index.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    logger.info(f"history index 저장: {len(entries)}건 → {out.name}")


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
        "us": {"news": [_serialize_item(it) for it in collected["us_news"]]},
        "kr": {"news": [_serialize_item(it) for it in collected["kr_news"]]},
        "youtube": {"videos": [_serialize_item(v) for v in collected["youtube"]]},
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
            "collected": {"news": len(collected["us_news"])},
        },
        "kr": {
            "top3_sectors": top3.get("kr_top3_sectors", []),
            "top3_stocks": top3.get("kr_top3_stocks", []),
            "outlook": outlook.get("kr", {}),
            "collected": {"news": len(collected["kr_news"])},
        },
        "youtube": {
            "top3_sectors": yt_top3.get("top3_sectors", []),
            "top3_stocks": yt_top3.get("top3_stocks", []),
            "videos_collected": len(collected["youtube"]),
        },
    }


def run_ai_pipeline(collected: dict, now_kst: datetime, client=None) -> dict:
    """3단계 LLM 분석. 어느 단계든 실패 시 Phase 1 페이로드로 폴백."""
    from modules.news import ai_client, extractor

    if client is None:
        client = ai_client.create_client()
    batches = {
        "us_news": collected["us_news"],
        "kr_news": collected["kr_news"],
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

    # 미국 뉴스 제목 한국어 번역 (LLM 1회). 키 없으면 skip.
    client = None
    try:
        from modules.news import ai_client, translator
        client = ai_client.create_client()
        translator.translate_us_titles(collected["us_news"], client)
    except Exception as e:
        logger.warning(f"번역 단계 skip: {e}")

    if args.skip_ai:
        payload = build_payload_phase1(collected, now_kst)
    else:
        payload = run_ai_pipeline(collected, now_kst, client=client)

    if args.dry_run:
        phase = payload.get("phase", "?")
        print(f"[DRY-RUN] phase={phase} generated_at={payload['generated_at']}")
        if phase == 2:
            print(f"  us.top3_sectors={len(payload['us']['top3_sectors'])}, us.top3_stocks={len(payload['us']['top3_stocks'])}")
            print(f"  kr.top3_sectors={len(payload['kr']['top3_sectors'])}, kr.top3_stocks={len(payload['kr']['top3_stocks'])}")
            print(f"  youtube.top3_sectors={len(payload['youtube']['top3_sectors'])}, youtube.top3_stocks={len(payload['youtube']['top3_stocks'])}")
        else:
            print(f"  us.news={len(payload['us']['news'])}")
            print(f"  kr.news={len(payload['kr']['news'])}")
            print(f"  youtube.videos={len(payload['youtube']['videos'])}")
        return 0

    save_outputs(payload, now_kst)
    cleanup_history()
    write_history_index()
    return 0


if __name__ == "__main__":
    sys.exit(main())
