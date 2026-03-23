"""대장주 전종목 수동 매수 테스트 — 독립 실행"""
import asyncio
import aiohttp
import json
import sys
sys.path.insert(0, ".")

from daemon.config import KIS_MOCK_APP_KEY, KIS_MOCK_APP_SECRET, KIS_MOCK_BASE_URL, KIS_MOCK_ACCOUNT_NO
from daemon.position_db import calc_quantity, insert_buy_order, update_position_filled

CANO = KIS_MOCK_ACCOUNT_NO.split("-")[0]
ACNT_CD = KIS_MOCK_ACCOUNT_NO.split("-")[1] if "-" in KIS_MOCK_ACCOUNT_NO else "01"


async def get_token(session):
    url = f"{KIS_MOCK_BASE_URL}/oauth2/tokenP"
    body = {"grant_type": "client_credentials", "appkey": KIS_APP_KEY, "appsecret": KIS_APP_SECRET}
    async with session.post(url, json=body) as resp:
        data = await resp.json()
        return data.get("access_token")


def headers(token, tr_id):
    return {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": KIS_MOCK_APP_KEY,
        "appsecret": KIS_MOCK_APP_SECRET,
        "tr_id": tr_id,
        "custtype": "P",
    }


async def get_price(session, token, code):
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    async with session.get(url, params=params, headers=headers(token, "FHKST01010100")) as resp:
        data = await resp.json()
        if data.get("rt_cd") == "0":
            return int(data.get("output", {}).get("stck_prpr", "0"))
    return 0


async def buy_order(session, token, code, qty, price):
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/order-cash"
    body = {
        "CANO": CANO, "ACNT_PRDT_CD": ACNT_CD,
        "PDNO": code, "ORD_DVSN": "00",
        "ORD_QTY": str(qty), "ORD_UNPR": str(price),
    }
    async with session.post(url, json=body, headers=headers(token, "VTTC0802U")) as resp:
        data = await resp.json()
        if data.get("rt_cd") == "0":
            return True
        print(f"    KIS 오류: {data.get('msg1', '')}")
    return False


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

    async with aiohttp.ClientSession() as session:
        token = await get_token(session)
        if not token:
            print("토큰 발급 실패")
            return
        print(f"토큰: {token[:20]}...")

        # 현재가 조회
        priced = []
        for code, name in targets:
            price = await get_price(session, token, code)
            print(f"  {name:16s} {code}  현재가: {price:>8,}원")
            if price > 0:
                priced.append((code, name, price))
            await asyncio.sleep(0.3)

        if not priced:
            print("현재가 조회 실패")
            return

        # 700만원 기준 균등 분배
        total_budget = 7_000_000
        amount_per = total_budget // len(priced)
        print(f"\n예산: {total_budget:,}원 / {len(priced)}종목 = 종목당 {amount_per:,}원")

        for code, name, price in priced:
            qty = calc_quantity(amount_per, price)
            if qty <= 0:
                print(f"  {name}: 수량 0 스킵")
                continue
            print(f"  매수: {name} {price:,}원 x {qty}주 = {price * qty:,}원")

            # DB 기록
            position = await insert_buy_order(code, name, price, qty)
            if not position:
                print(f"    DB 기록 실패")
                continue

            # KIS 주문
            ok = await buy_order(session, token, code, qty, price)
            if ok:
                await update_position_filled(position["id"], price)
                print(f"    -> 성공")
            else:
                print(f"    -> KIS 주문 실패")
            await asyncio.sleep(0.5)


asyncio.run(main())
