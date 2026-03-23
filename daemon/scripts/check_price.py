"""미체결 종목 현재가 + 상하한가 확인"""
import asyncio
import aiohttp
import sys
sys.path.insert(0, ".")
from daemon.config import KIS_MOCK_APP_KEY, KIS_MOCK_APP_SECRET, KIS_MOCK_BASE_URL


async def main():
    async with aiohttp.ClientSession() as s:
        r = await s.post(
            f"{KIS_MOCK_BASE_URL}/oauth2/tokenP",
            json={"grant_type": "client_credentials", "appkey": KIS_MOCK_APP_KEY, "appsecret": KIS_MOCK_APP_SECRET},
        )
        token = (await r.json()).get("access_token")

        for code, name, order_price in [("038110", "에코플라스틱", 3910), ("069540", "빛과전자", 2845)]:
            url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
            params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
            hdrs = {
                "Content-Type": "application/json; charset=utf-8",
                "authorization": f"Bearer {token}",
                "appkey": KIS_MOCK_APP_KEY,
                "appsecret": KIS_MOCK_APP_SECRET,
                "tr_id": "FHKST01010100",
                "custtype": "P",
            }
            async with s.get(url, params=params, headers=hdrs) as resp:
                data = await resp.json()
                out = data.get("output", {})
                cur = out.get("stck_prpr", "?")
                hi = out.get("stck_mxpr", "?")
                lo = out.get("stck_llam", "?")
                print(f"{name} ({code}): 현재가={cur}, 상한가={hi}, 하한가={lo}, 주문가={order_price}")
                if cur != "?":
                    diff = int(cur) - order_price
                    print(f"  주문가와 차이: {diff:+,}원 ({'체결가능' if diff <= 0 else '현재가>주문가 → 미체결'})")

asyncio.run(main())
