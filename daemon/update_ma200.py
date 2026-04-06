"""MA200 캐시 자동 갱신 스크립트

GCP 서버에서 주 1회(월요일 08:50 KST) 실행.
KIS API로 상위 종목의 최근 종가를 조회하여 MA200을 재계산한다.

방법: stock-master.json의 전종목에 대해 일봉 200일을 조회하면 정확하지만,
API 호출이 2,600 × 2 = 5,200건으로 ~4분 소요.
대신, 기존 MA200 캐시의 값을 전일 종가로 업데이트하는 근사 방식 사용:
  새 MA200 = (기존 MA200 × 200 - 200일 전 종가 + 전일 종가) / 200
  → 200일 전 종가를 모르므로, 더 간단하게:
  새 MA200 = 기존 MA200 × (199/200) + 전일 종가 × (1/200)
  이건 지수이동평균(EMA) 근사이고, 실제 SMA와 약간 차이나지만
  MA200 필터 용도로는 충분함.

실제 구현: KIS API inquire-price로 전일 종가(stck_sdpr)를 조회하여 갱신.
"""
import json
import sys
import asyncio
import time
from pathlib import Path

# daemon 패키지 import를 위한 경로 설정
sys.path.insert(0, str(Path(__file__).parent.parent))

CACHE_PATH = Path(__file__).parent / "ma200_cache.json"
MASTER_PATH = Path(__file__).parent.parent / "results" / "stock-master.json"


async def update_ma200():
    from daemon.trader import _ensure_mock_token, _order_headers
    from daemon.config import KIS_MOCK_BASE_URL
    from daemon.http_session import get_session, close_session

    # 기존 캐시 로드
    if not CACHE_PATH.exists():
        print("MA200 캐시 없음 — 종료")
        return
    cache = json.loads(CACHE_PATH.read_text())
    print(f"기존 캐시: {len(cache)}종목")

    # 토큰 확보
    token = await _ensure_mock_token()
    if not token:
        print("토큰 발급 실패")
        return

    # 전종목 전일 종가 조회 (5건씩 배치 — KIS rate limit 방어)
    codes = list(cache.keys())
    session = await get_session()
    updated = 0
    failed = 0
    prev_closes = {}  # code → 전일 종가 (MA20 갱신용)
    fail_reasons = {}  # 실패 사유 집계

    BATCH_SIZE = 5  # KIS 모의투자 rate limit: 초당 ~5건
    for i in range(0, len(codes), BATCH_SIZE):
        batch = codes[i:i+BATCH_SIZE]
        tasks = []
        for code in batch:
            url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
            params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
            tasks.append(session.get(url, params=params, headers=_order_headers(token, "FHKST01010100")))

        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for code, resp in zip(batch, responses):
            if isinstance(resp, Exception):
                failed += 1
                reason = type(resp).__name__
                fail_reasons[reason] = fail_reasons.get(reason, 0) + 1
                continue
            try:
                data = await resp.json()
                if data.get("rt_cd") != "0":
                    failed += 1
                    reason = data.get("msg1", "unknown")[:30]
                    fail_reasons[reason] = fail_reasons.get(reason, 0) + 1
                    continue
                prev_close = int(data.get("output", {}).get("stck_sdpr", "0"))
                if prev_close <= 0:
                    continue
                prev_closes[code] = prev_close  # MA20 갱신용 저장
                # MA200 근사 갱신: 새 MA200 ≈ 기존 × (199/200) + 전일종가 × (1/200)
                old_ma = cache.get(code, 0)
                if old_ma > 0:
                    cache[code] = round(old_ma * (199/200) + prev_close * (1/200), 2)
                    updated += 1
            except Exception as e:
                failed += 1
                reason = type(e).__name__
                fail_reasons[reason] = fail_reasons.get(reason, 0) + 1

        if i % 500 == 0 and i > 0:
            print(f"  진행: {i}/{len(codes)} (갱신={updated}, 실패={failed})")
        await asyncio.sleep(0.5)

    if fail_reasons:
        print(f"  실패 사유: {fail_reasons}")

    # 저장
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False))
    print(f"\nMA200 캐시 갱신 완료: {updated}종목 갱신, {failed}건 실패")
    print(f"저장: {CACHE_PATH}")

    # MA20 캐시 갱신 (19/20 근사 — MA20은 변동이 크지만 필터 용도로 충분)
    MA20_PATH = Path(__file__).parent / "ma20_cache.json"
    if MA20_PATH.exists():
        ma20_cache = json.loads(MA20_PATH.read_text())
        ma20_updated = 0
        for code, prev_close in prev_closes.items():
            if code in ma20_cache and prev_close > 0:
                old_ma20 = ma20_cache[code]
                ma20_cache[code] = round(old_ma20 * (19/20) + prev_close * (1/20), 2)
                ma20_updated += 1
        MA20_PATH.write_text(json.dumps(ma20_cache, ensure_ascii=False))
        print(f"MA20 캐시 갱신: {ma20_updated}종목")

    await close_session()


async def cleanup_old_sim_only():
    """현재는 삭제 없음 — sim_only는 시뮬 trade_id 참조에 필요하므로 유지.
    연 ~1,000건 (0.5MB) 수준으로 Supabase 용량 문제 없음."""
    pass


async def update_stock_master():
    """stock-master.json을 GitHub Pages에서 다운로드 (주 1회)"""
    import aiohttp
    from datetime import datetime, timezone, timedelta
    KST = timezone(timedelta(hours=9))

    url = "https://xxonbang.github.io/stock_toolkit/data/stock-master.json"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    stocks = data.get("stocks", [])
                    if stocks:
                        MASTER_PATH.parent.mkdir(parents=True, exist_ok=True)
                        MASTER_PATH.write_text(json.dumps(data, ensure_ascii=False))
                        print(f"stock-master.json 갱신: {len(stocks)}종목")
                    else:
                        print("stock-master.json 갱신 실패: 종목 0건")
                else:
                    print(f"stock-master.json 다운로드 실패: HTTP {resp.status}")
    except Exception as e:
        print(f"stock-master.json 갱신 오류: {e}")


if __name__ == "__main__":
    asyncio.run(update_ma200())
