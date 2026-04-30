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


class StepTimer:
    """with-블록 단계별 경과 시간 측정 + 시작/종료 명시 로그."""
    def __init__(self, label: str):
        self.label = label
        self.t0 = 0.0

    def __enter__(self):
        self.t0 = time.time()
        logger.info(f"━━━ ▶ {self.label} 시작 ━━━")
        return self

    def __exit__(self, exc_type, exc, tb):
        elapsed = time.time() - self.t0
        if exc_type is None:
            logger.info(f"━━━ ✓ {self.label} 완료 ({elapsed:.2f}s) ━━━")
        else:
            logger.error(f"━━━ ✗ {self.label} 실패 ({elapsed:.2f}s): {exc_type.__name__}: {exc} ━━━")
        return False  # 예외는 재전파


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
    result = {}
    with StepTimer("us_news 수집"):
        result["us_news"] = us_news.collect(now=now)
    with StepTimer("kr_news 수집"):
        result["kr_news"] = kr_news.collect(now=now)
    with StepTimer("youtube 수집"):
        result["youtube"] = youtube.collect(now=now)
    # 수집 통계 요약
    total_titles = sum(len(it.title) for b in ("us_news", "kr_news") for it in result[b])
    total_bodies = sum(len(it.body) for b in ("us_news", "kr_news") for it in result[b])
    total_transcripts = sum(len(v.transcript) for v in result["youtube"])
    logger.info(
        f"📊 수집 통계: us_news={len(result['us_news'])}건, kr_news={len(result['kr_news'])}건, "
        f"youtube={len(result['youtube'])}건 / "
        f"총 제목 {total_titles:,}자, 본문 {total_bodies:,}자, 자막 {total_transcripts:,}자"
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
    """AI 분석 결과 통합 — 프론트엔드가 읽을 최종 스키마.

    outlook은 merge_outlook_into_top3에 의해 top3 entry의 outlook 필드로 머지된 상태.
    region.outlook 필드는 호환성용으로 raw 응답을 그대로 보존.
    """
    return {
        "generated_at": now_kst.strftime("%Y-%m-%d %H:%M KST"),
        "phase": 2,
        "us": {
            "top3_sectors": top3.get("us_top3_sectors", []),
            "top3_stocks": top3.get("us_top3_stocks", []),
            "outlook": {
                "sectors": outlook.get("us_sector_outlook", []),
                "stocks": outlook.get("us_stock_outlook", []),
            },
            "collected": {"news": len(collected["us_news"])},
        },
        "kr": {
            "top3_sectors": top3.get("kr_top3_sectors", []),
            "top3_stocks": top3.get("kr_top3_stocks", []),
            "outlook": {
                "sectors": outlook.get("kr_sector_outlook", []),
                "stocks": outlook.get("kr_stock_outlook", []),
            },
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
        with StepTimer("LLM #1: extract_per_batch"):
            extraction = extractor.extract_per_batch(batches, client)
        # 추출 결과 요약
        for b in ("us_news", "kr_news"):
            stk = len(extraction.get(b, {}).get("stocks", []))
            sec = len(extraction.get(b, {}).get("sectors", []))
            logger.info(f"  📌 {b}: stocks={stk}개, sectors={sec}개")
    except Exception as e:
        logger.error(f"extract 실패 — Phase 1 폴백: {e}", exc_info=True)
        return build_payload_phase1(collected, now_kst)

    try:
        with StepTimer("LLM #2: select_top3"):
            top3 = extractor.select_top3(extraction, client)
        for k in ("us_top3_sectors", "us_top3_stocks", "kr_top3_sectors", "kr_top3_stocks"):
            entries = top3.get(k, [])
            logger.info(f"  📌 {k}: {len(entries)}건 → {[e.get('name','?') for e in entries]}")
        # raw 뉴스 매핑 — entry.related_news 채움 (프론트 "근거 뉴스 보기" 펼치기용)
        extractor.merge_related_news_into_top3(top3, batches)
    except Exception as e:
        logger.error(f"top3 실패: {e}", exc_info=True)
        top3 = {"us_top3_sectors": [], "us_top3_stocks": [], "kr_top3_sectors": [], "kr_top3_stocks": []}

    outlook: dict = {}
    try:
        with StepTimer("LLM #3: generate_outlook (Search grounding)"):
            outlook = extractor.generate_outlook(top3, client)
        logger.info(f"  📌 outlook keys: {list(outlook.keys()) if outlook else '비어있음'}")
        # outlook 응답을 top3 entry의 outlook 필드로 머지 (프론트가 entry.outlook 직접 표시)
        if outlook:
            extractor.merge_outlook_into_top3(top3, outlook)
    except Exception as e:
        logger.warning(f"outlook 실패: {e}", exc_info=True)
        outlook = {}

    yt_top3 = {"top3_sectors": [], "top3_stocks": []}
    try:
        with StepTimer("LLM #4: analyze_youtube"):
            yt_top3 = extractor.analyze_youtube(collected["youtube"], client)
        for k in ("top3_sectors", "top3_stocks"):
            entries = yt_top3.get(k, [])
            logger.info(f"  📌 youtube.{k}: {len(entries)}건 → {[e.get('name','?') for e in entries]}")
    except Exception as e:
        logger.warning(f"youtube 분석 실패: {e}", exc_info=True)

    return build_payload_full(collected, top3, outlook, yt_top3, now_kst)


def _diagnose_env() -> None:
    """환경 진단 — 키 set/missing 여부, runner 정보 출력 (값 노출 없음)."""
    keys = ["YOUTUBE_API_KEY"] + [f"GOOGLE_API_KEY_{i:02d}" for i in range(1, 6)]
    status = {k: ("set" if os.getenv(k) else "MISSING") for k in keys}
    logger.info("🔧 환경 진단:")
    for k, v in status.items():
        emoji = "✓" if v == "set" else "✗"
        logger.info(f"  {emoji} {k}: {v}")
    runner = os.getenv("GITHUB_ACTIONS")
    run_id = os.getenv("GITHUB_RUN_ID")
    if runner:
        logger.info(f"  🚀 GitHub Actions runner — run_id={run_id}")
    else:
        logger.info(f"  💻 로컬 실행 — Python {sys.version.split()[0]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Stock Insight 수집/분석 (수집 + 3단계 LLM 분석)")
    parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 콘솔 요약만")
    parser.add_argument("--skip-ai", action="store_true", help="AI 분석 생략, Phase 1 페이로드만")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    # 로그 timestamp를 KST로 표시 (GitHub Actions runner는 기본 UTC).
    logging.Formatter.converter = lambda *a: datetime.now(KST).timetuple()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s KST %(levelname)s [%(name)s] %(message)s",
    )

    # 로컬 .env 로드 (GitHub Actions에서는 secrets로 주입).
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        load_dotenv(ROOT / "daemon" / ".env")
    except ImportError:
        pass

    pipeline_t0 = time.time()
    now_utc = datetime.now(timezone.utc)
    now_kst = now_utc.astimezone(KST)

    logger.info("═══════════════════════════════════════════════════════")
    logger.info(f"🚀 Stock Insight 파이프라인 시작 — {now_kst.strftime('%Y-%m-%d %H:%M:%S KST')}")
    logger.info(f"   모드: {'--skip-ai (수집만)' if args.skip_ai else '전체 분석'}{' (--dry-run)' if args.dry_run else ''}")
    logger.info("═══════════════════════════════════════════════════════")
    _diagnose_env()

    with StepTimer("Phase A: 데이터 수집"):
        collected = collect_all(now_utc)

    # 미국 뉴스 제목 한국어 번역 (LLM 1회). 키 없으면 skip.
    client = None
    try:
        from modules.news import ai_client, translator
        with StepTimer("Phase B: Gemini 클라이언트 초기화"):
            client = ai_client.create_client()
        with StepTimer("Phase C: 미국 뉴스 제목 번역"):
            translated = translator.translate_us_titles(collected["us_news"], client)
            logger.info(f"  📝 번역 결과: {translated}/{len(collected['us_news'])}건 성공")
    except Exception as e:
        logger.warning(f"번역 단계 skip — 사유: {e}")

    if args.skip_ai:
        payload = build_payload_phase1(collected, now_kst)
        logger.info("⏭  Phase D (AI 분석) 스킵 — Phase 1 페이로드만 생성")
    else:
        with StepTimer("Phase D: AI 분석 (LLM #1~#4)"):
            payload = run_ai_pipeline(collected, now_kst, client=client)

    # LLM 호출 통계 요약
    if client is not None and hasattr(client, "summary"):
        client.summary()

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
        logger.info(f"⏱  파이프라인 총 소요: {time.time()-pipeline_t0:.2f}s")
        return 0

    with StepTimer("Phase E: 결과 저장 + 히스토리 정리"):
        save_outputs(payload, now_kst)
        cleanup_history()
        write_history_index()

    logger.info("═══════════════════════════════════════════════════════")
    logger.info(f"✅ 파이프라인 완료 — 총 소요 {time.time()-pipeline_t0:.2f}s, phase={payload.get('phase')}")
    logger.info("═══════════════════════════════════════════════════════")
    return 0


if __name__ == "__main__":
    sys.exit(main())
