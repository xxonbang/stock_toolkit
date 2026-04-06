"""KIS 모의투자 토큰 + 주문 디버그"""
import asyncio
import base64
import json
import sys
sys.path.insert(0, ".")
from daemon.trader import _ensure_mock_token, _order_headers
from daemon.config import KIS_MOCK_BASE_URL, KIS_MOCK_ACCOUNT_NO
from daemon.http_session import get_session, close_session


async def main():
    token = await _ensure_mock_token()
    print(f"토큰 발급: {'OK' if token else 'FAIL'}")

    # JWT payload 디코딩
    if token:
        parts = token.split(".")
        if len(parts) >= 2:
            payload_b64 = parts[1]
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            decoded = json.loads(base64.urlsafe_b64decode(payload_b64))
            print(f"JWT sub: {decoded.get('sub')}")
            print(f"JWT aud: {decoded.get('aud')}")
            print(f"JWT prdt_cd: {decoded.get('prdt_cd')}")
            print(f"JWT iss: {decoded.get('iss')}")

    print(f"\n설정 계좌: {KIS_MOCK_ACCOUNT_NO}")
    cano = KIS_MOCK_ACCOUNT_NO.split("-")[0] if "-" in KIS_MOCK_ACCOUNT_NO else KIS_MOCK_ACCOUNT_NO[:8]
    acnt = KIS_MOCK_ACCOUNT_NO.split("-")[1] if "-" in KIS_MOCK_ACCOUNT_NO else KIS_MOCK_ACCOUNT_NO[8:]
    print(f"CANO: {cano}, ACNT_PRDT_CD: {acnt}")

    # 주문 테스트 (삼성전자 1주)
    print("\n--- 매수 주문 테스트 ---")
    session = await get_session()
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/order-cash"
    body = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt,
        "PDNO": "005930",
        "ORD_DVSN": "00",
        "ORD_QTY": "1",
        "ORD_UNPR": "55000",
    }
    resp = await session.post(url, json=body, headers=_order_headers(token, "VTTC0802U"))
    result = await resp.json()
    print(f"rt_cd: {result.get('rt_cd')}")
    print(f"msg: {result.get('msg1', '')}")
    if result.get("rt_cd") == "0":
        print("주문 성공!")
        print(json.dumps(result.get("output", {}), indent=2, ensure_ascii=False))

    await close_session()

asyncio.run(main())
