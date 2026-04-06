"""미체결 종목 현재가 + 상하한가 확인"""
import asyncio
import sys
sys.path.insert(0, ".")
from daemon.trader import _ensure_mock_token, _order_headers
from daemon.config import KIS_MOCK_BASE_URL
from daemon.http_session import get_session, close_session


async def main():
    token = await _ensure_mock_token()
    if not token:
        print("토큰 발급 실패")
        return
    session = await get_session()

    for code, name, order_price in [("038110", "에코플라스틱", 3910), ("069540", "빛과전자", 2845)]:
        url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
        params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
        async with session.get(url, params=params, headers=_order_headers(token, "FHKST01010100")) as resp:
            data = await resp.json()
            out = data.get("output", {})
            cur = out.get("stck_prpr", "?")
            hi = out.get("stck_mxpr", "?")
            lo = out.get("stck_llam", "?")
            print(f"{name} ({code}): 현재가={cur}, 상한가={hi}, 하한가={lo}, 주문가={order_price}")
            if cur != "?":
                diff = int(cur) - order_price
                print(f"  주문가와 차이: {diff:+,}원 ({'체결가능' if diff <= 0 else '현재가>주문가 → 미체결'})")

    await close_session()

asyncio.run(main())
