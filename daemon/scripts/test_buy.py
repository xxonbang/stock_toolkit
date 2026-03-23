"""대장주 전종목 수동 매수 테스트 — daemon의 매수 함수 직접 사용 (알림 포함)"""
import asyncio
import aiohttp
import sys
sys.path.insert(0, ".")

from daemon.config import KIS_MOCK_APP_KEY, KIS_MOCK_APP_SECRET, KIS_MOCK_BASE_URL
from daemon.trader import place_buy_order_with_qty, _ensure_mock_token
from daemon.position_db import calc_quantity
from daemon.notifier import telegram_worker
from daemon.http_session import get_session, close_session


async def get_price(code):
    token = await _ensure_mock_token()
    if not token:
        return 0
    session = await get_session()
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": KIS_MOCK_APP_KEY,
        "appsecret": KIS_MOCK_APP_SECRET,
        "tr_id": "FHKST01010100",
        "custtype": "P",
    }
    async with session.get(url, params=params, headers=headers) as resp:
        data = await resp.json()
        if data.get("rt_cd") == "0":
            return int(data.get("output", {}).get("stck_prpr", "0"))
    return 0


async def main():
    targets = [
        ("003280", "흥아해운"),
        ("100090", "SK오션플랜트"),
        ("322000", "HD현대에너지솔루션"),
        ("117580", "대성에너지"),
        ("092220", "KEC"),
        ("069540", "빛과전자"),
        ("038110", "에코플라스틱"),
        ("375500", "DL이앤씨"),
    ]

    # telegram_worker를 백그라운드로 실행 (알림 전송용)
    tg_task = asyncio.create_task(telegram_worker())

    token = await _ensure_mock_token()
    if not token:
        print("토큰 발급 실패")
        tg_task.cancel()
        await close_session()
        return
    print(f"토큰: {token[:20]}...")

    # 현재가 조회
    priced = []
    for code, name in targets:
        price = await get_price(code)
        print(f"  {name:16s} {code}  현재가: {price:>8,}원")
        if price > 0:
            priced.append((code, name, price))
        await asyncio.sleep(0.3)

    if not priced:
        print("현재가 조회 실패")
        tg_task.cancel()
        await close_session()
        return

    total_budget = 7_000_000
    amount_per = total_budget // len(priced)
    print(f"\n예산: {total_budget:,}원 / {len(priced)}종목 = 종목당 {amount_per:,}원")

    for code, name, price in priced:
        qty = calc_quantity(amount_per, price)
        if qty <= 0:
            print(f"  {name}: 수량 0 스킵")
            continue
        print(f"  매수: {name} {price:,}원 x {qty}주 = {price * qty:,}원")
        ok = await place_buy_order_with_qty(code, name, price, qty)
        print(f"    -> {'성공' if ok else '실패(상한가 또는 주문오류)'}")
        await asyncio.sleep(0.5)

    # 알림 전송 대기
    print("\n알림 전송 대기 중...")
    await asyncio.sleep(3)
    tg_task.cancel()
    await close_session()
    print("완료")


asyncio.run(main())
