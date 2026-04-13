"""daily_ohlcv_all.json 증분 갱신 — volume-rank TOP 200 대상, 최근 5거래일 append.

GCP 서버에서 주 1회 실행. theme_analysis 의존성 없이 daemon 도구만 사용.

전략: 전체 2,618종목 갱신은 느리므로, volume-rank fallback에 필요한
상위 종목(전일 거래대금 기준 TOP 200 + 기존 파일에 있는 종목 중 최근 누락)만 갱신.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))
OHLCV_PATH = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"


async def update_daily_ohlcv():
    """volume-rank TOP + 보유 종목의 최근 20거래일 데이터를 기존 파일에 append."""
    from daemon.trader import _ensure_mock_token, get_session, _order_headers
    from daemon.config import KIS_MOCK_BASE_URL

    if not OHLCV_PATH.exists():
        logger.warning(f"daily_ohlcv_all.json 없음 → 갱신 불가 ({OHLCV_PATH})")
        return

    logger.info(f"daily_ohlcv 증분 갱신 시작 ({OHLCV_PATH.stat().st_size/1e6:.0f}MB)")

    # 1. 기존 파일 로드
    with open(OHLCV_PATH, encoding="utf-8") as f:
        ohlcv = json.load(f)

    # 2. 업데이트 대상 결정 — 전일 거래대금 TOP 500 (넉넉히)
    candidates = []
    for code, info in ohlcv.items():
        if len(code) != 6 or not code.isdigit():
            continue
        bars = info.get("bars", [])
        if not bars:
            continue
        last_bar = bars[-1]
        tv = int(last_bar.get("acml_tr_pbmn", 0))
        last_date = last_bar.get("stck_bsop_date", "")
        if tv > 0:
            candidates.append({"code": code, "tv": tv, "last_date": last_date})
    candidates.sort(key=lambda x: -x["tv"])
    targets = candidates[:500]
    logger.info(f"갱신 대상: 전일TV 기준 TOP {len(targets)}종목")

    # 3. 최신 데이터 조회 + append
    token = await _ensure_mock_token()
    if not token:
        logger.warning("모의투자 토큰 없음 → 갱신 중단")
        return

    session = await get_session()
    updated = 0
    errors = 0
    today_yyyymmdd = datetime.now(_KST).strftime("%Y%m%d")

    for i, t in enumerate(targets):
        code = t["code"]
        last_date = t["last_date"]
        # 마지막 날짜가 오늘이면 skip
        if last_date >= today_yyyymmdd:
            continue
        try:
            url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-price"
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": code,
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "0",
            }
            async with session.get(url, params=params, headers=_order_headers(token, "FHKST01010400")) as resp:
                data = await resp.json()
                if data.get("rt_cd") != "0":
                    errors += 1
                    continue
                new_bars = data.get("output", [])

            # 기존 bars에 없는 날짜만 append
            existing_dates = {b["stck_bsop_date"] for b in ohlcv[code]["bars"]}
            added = 0
            for b in new_bars:
                d = b.get("stck_bsop_date", "")
                if d and d not in existing_dates:
                    ohlcv[code]["bars"].append(b)
                    existing_dates.add(d)
                    added += 1
            if added > 0:
                # 날짜순 정렬
                ohlcv[code]["bars"].sort(key=lambda x: x.get("stck_bsop_date", ""))
                updated += 1

            # rate limit: 초당 20건
            await asyncio.sleep(0.06)

            if (i + 1) % 50 == 0:
                logger.info(f"  진행: {i+1}/{len(targets)} (갱신 {updated}, 에러 {errors})")
        except Exception as e:
            errors += 1
            logger.warning(f"  {code} 오류: {e}")

    # 4. 저장
    if updated > 0:
        with open(OHLCV_PATH, "w", encoding="utf-8") as f:
            json.dump(ohlcv, f, ensure_ascii=False)
        logger.info(f"daily_ohlcv 증분 갱신 완료: {updated}종목 갱신, {errors}에러, 파일 크기 {OHLCV_PATH.stat().st_size/1e6:.0f}MB")
    else:
        logger.info(f"daily_ohlcv 갱신 불필요 (모두 최신, 에러 {errors})")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    asyncio.run(update_daily_ohlcv())
