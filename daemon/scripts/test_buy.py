"""대장주 전종목 수동 매수 테스트"""
import asyncio
import sys
sys.path.insert(0, ".")

from daemon.trader import _ensure_mock_token, place_buy_order_with_qty, _order_headers
from daemon.position_db import calc_quantity
from daemon.http_session import get_session, close_session
from daemon.config import KIS_APP_KEY, KIS_APP_SECRET, KIS_MOCK_BASE_URL, KIS_MOCK_ACCOUNT_NO


async def get_balance(token):
    session = await get_session()
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance"
    params = {
        "CANO": KIS_MOCK_ACCOUNT_NO.split("-")[0],
        "ACNT_PRDT_CD": KIS_MOCK_ACCOUNT_NO.split("-")[1] if "-" in KIS_MOCK_ACCOUNT_NO else "01",
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "02",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "00",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_APP_SECRET,
        "tr_id": "VTTC8434R",
        "custtype": "P",
    }
    async with session.get(url, params=params, headers=headers) as resp:
        data = await resp.json()
        if data.get("rt_cd") == "0":
            out2 = data.get("output2", [{}])
            o = out2[0] if isinstance(out2, list) and out2 else out2
            balance = int(o.get("dnca_tot_amt", "0"))
            avail = int(o.get("prvs_rcdl_excc_amt", "0"))
            total = int(o.get("tot_evlu_amt", "0"))
            return {"balance": balance, "available": avail, "total": total}
        print(f"잔고 조회 실패: {data.get('msg1', '')}")
    return None


async def get_price(token, code):
    session = await get_session()
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_APP_SECRET,
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

    token = await _ensure_mock_token()
    if not token:
        print("토큰 발급 실패")
        await close_session()
        return

    print(f"토큰: {token[:20]}...")

    # 잔고 조회
    bal = await get_balance(token)
    if bal:
        print(f"예수금: {bal['balance']:,}원  가용: {bal['available']:,}원  총평가: {bal['total']:,}원")
        available = bal["available"]
    else:
        print("잔고 조회 실패 — 기본 700만원으로 진행")
        available = 7_000_000

    # 현재가 조회
    priced = []
    for code, name in targets:
        price = await get_price(token, code)
        print(f"  {name:16s} {code}  현재가: {price:>8,}원")
        if price > 0:
            priced.append((code, name, price))
        await asyncio.sleep(0.3)

    if not priced:
        print("현재가 조회 실패")
        await close_session()
        return

    amount_per = available // len(priced)
    print(f"\n종목당 투자금: {amount_per:,}원 ({len(priced)}종목)")

    for code, name, price in priced:
        qty = calc_quantity(amount_per, price)
        if qty <= 0:
            print(f"  {name}: 수량 0 스킵")
            continue
        print(f"  매수: {name} {price:,}원 x {qty}주 = {price * qty:,}원")
        ok = await place_buy_order_with_qty(code, name, price, qty)
        print(f"    -> {'성공' if ok else '실패'}")
        await asyncio.sleep(0.5)

    await close_session()


asyncio.run(main())
