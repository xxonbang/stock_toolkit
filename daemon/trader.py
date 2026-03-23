"""KIS 모의투자 자동매매 — 매수/매도 주문 + 수익률 감시"""
import asyncio
import logging
import time
from daemon.config import (
    KIS_MOCK_APP_KEY, KIS_MOCK_APP_SECRET, KIS_MOCK_ACCOUNT_NO, KIS_MOCK_BASE_URL,
    TRADE_AMOUNT_PER_STOCK, TRADE_TAKE_PROFIT_PCT, TRADE_STOP_LOSS_PCT,
    DATA_BASE_URL,
)
from daemon.position_db import (
    is_already_held_or_ordered, insert_buy_order, update_position_filled,
    update_position_sold, get_active_positions, calc_quantity, calc_pnl_pct,
    is_selling, mark_selling, unmark_selling,
)
from daemon.notifier import send_telegram
from daemon.stock_manager import fetch_json
from daemon.http_session import get_session

logger = logging.getLogger("daemon.trader")

BUY_SIGNALS = {"적극매수", "매수"}

_access_token = ""
_token_issued_at: float = 0
_TOKEN_TTL = 3500  # KIS 토큰 유효기간 ~1시간, 여유 두고 58분


async def _ensure_mock_token() -> str | None:
    """모의투자 토큰 발급 — 만료 시 자동 재발급"""
    global _access_token, _token_issued_at
    now = time.time()
    if _access_token and (now - _token_issued_at) < _TOKEN_TTL:
        return _access_token
    # 재발급
    _access_token = ""
    url = f"{KIS_MOCK_BASE_URL}/oauth2/tokenP"
    body = {
        "grant_type": "client_credentials",
        "appkey": KIS_MOCK_APP_KEY,
        "appsecret": KIS_MOCK_APP_SECRET,
    }
    try:
        session = await get_session()
        async with session.post(url, json=body) as resp:
            if resp.status == 200:
                data = await resp.json()
                _access_token = data.get("access_token", "")
                _token_issued_at = now
                logger.info("모의투자 토큰 발급 완료")
                return _access_token
    except Exception as e:
        logger.error(f"모의투자 토큰 발급 실패: {e}")
    return None


def _order_headers(token: str, tr_id: str) -> dict:
    return {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": KIS_MOCK_APP_KEY,
        "appsecret": KIS_MOCK_APP_SECRET,
        "tr_id": tr_id,
        "custtype": "P",
    }


def filter_high_confidence(signals: list | None) -> list[dict]:
    """고확신 종목 필터: 대장주 AND vision 매수 AND api 매수"""
    if not signals:
        return []
    return [
        s for s in signals
        if s.get("vision_signal") in BUY_SIGNALS
        and s.get("api_signal") in BUY_SIGNALS
    ]


def should_sell(buy_price: int, current_price: int, take_profit: float = TRADE_TAKE_PROFIT_PCT, stop_loss: float = TRADE_STOP_LOSS_PCT) -> str | None:
    pnl = calc_pnl_pct(buy_price, current_price)
    if pnl >= take_profit:
        return "take_profit"
    if pnl <= stop_loss:
        return "stop_loss"
    return None


async def _kis_order(tr_id: str, code: str, quantity: int, price: int, retry: bool = True) -> dict | None:
    """KIS 모의투자 주문 공통 — 토큰 만료 시 1회 재시도"""
    token = await _ensure_mock_token()
    if not token:
        return None
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/order-cash"
    account_parts = KIS_MOCK_ACCOUNT_NO.split("-") if "-" in KIS_MOCK_ACCOUNT_NO else [KIS_MOCK_ACCOUNT_NO[:8], KIS_MOCK_ACCOUNT_NO[8:]]
    body = {
        "CANO": account_parts[0],
        "ACNT_PRDT_CD": account_parts[1] if len(account_parts) > 1 else "01",
        "PDNO": code,
        "ORD_DVSN": "00",
        "ORD_QTY": str(quantity),
        "ORD_UNPR": str(price),
    }
    try:
        session = await get_session()
        async with session.post(url, json=body, headers=_order_headers(token, tr_id)) as resp:
            data = await resp.json()
            if data.get("rt_cd") == "0":
                return data
            msg = data.get("msg1", "")
            if retry and ("만료" in msg or "token" in msg.lower()):
                logger.warning(f"KIS 토큰 만료 — 재발급 후 재시도")
                _reset_token()
                await asyncio.sleep(1)
                return await _kis_order(tr_id, code, quantity, price, retry=False)
            logger.error(f"KIS 주문 실패 ({tr_id}): {msg}")
    except Exception as e:
        logger.error(f"KIS 주문 오류 ({tr_id}): {e}")
    return None


async def is_upper_limit(code: str, price: int) -> bool:
    """현재가가 상한가인지 확인"""
    token = await _ensure_mock_token()
    if not token:
        return False
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    try:
        session = await get_session()
        async with session.get(url, params=params, headers=_order_headers(token, "FHKST01010100")) as resp:
            data = await resp.json()
            if data.get("rt_cd") == "0":
                upper = int(data.get("output", {}).get("stck_mxpr", "0"))
                if upper > 0 and price >= upper:
                    return True
    except Exception as e:
        logger.warning(f"상한가 조회 오류 ({code}): {e}")
    return False


async def place_buy_order(code: str, name: str, price: int) -> bool:
    quantity = calc_quantity(TRADE_AMOUNT_PER_STOCK, price)
    if quantity <= 0:
        logger.warning(f"매수 수량 0 — {name}({code}) 가격 {price}원")
        return False
    return await place_buy_order_with_qty(code, name, price, quantity)


async def place_buy_order_with_qty(code: str, name: str, price: int, quantity: int) -> bool:
    """수량을 직접 지정하여 매수"""
    if await is_upper_limit(code, price):
        logger.info(f"상한가 종목 스킵 — {name}({code}) {price:,}원")
        return False
    position = await insert_buy_order(code, name, price, quantity)
    if not position:
        return False

    result = await _kis_order("VTTC0802U", code, quantity, price)
    if result:
        await update_position_filled(position["id"], price)
        logger.info(f"매수 체결: {name}({code}) {price:,}원 × {quantity}주")
        await send_telegram(
            f"<b>📥 자동 매수 체결</b>\n"
            f"<b>{name} ({code})</b>\n"
            f"가격: {price:,}원 × {quantity}주\n"
            f"금액: {price * quantity:,}원"
        )
        return True
    return False


async def place_sell_order(code: str, name: str, price: int, quantity: int, position_id: str, reason: str, buy_price: int) -> bool:
    result = await _kis_order("VTTC0801U", code, quantity, price)
    if result:
        pnl = calc_pnl_pct(buy_price, price)
        await update_position_sold(position_id, price, pnl, reason)
        reason_label = "익절 +3%" if reason == "take_profit" else "손절 -3%" if reason == "stop_loss" else "수동 매도"
        emoji = "💰" if reason == "take_profit" else "🛑" if reason == "stop_loss" else "✋"
        logger.info(f"매도 체결: {name}({code}) {reason_label} ({pnl:+.1f}%)")
        await send_telegram(
            f"<b>{emoji} 자동 매도 ({reason_label})</b>\n"
            f"<b>{name} ({code})</b>\n"
            f"매수가: {buy_price:,}원 → 매도가: {price:,}원\n"
            f"수익률: {pnl:+.2f}% ({quantity}주)"
        )
        return True
    unmark_selling(position_id)
    return False


def _reset_token():
    global _access_token, _token_issued_at
    _access_token = ""
    _token_issued_at = 0


async def fetch_available_balance() -> int:
    """KIS 모의투자 계좌 예수금 조회"""
    token = await _ensure_mock_token()
    if not token:
        return 0
    account_parts = KIS_MOCK_ACCOUNT_NO.split("-") if "-" in KIS_MOCK_ACCOUNT_NO else [KIS_MOCK_ACCOUNT_NO[:8], KIS_MOCK_ACCOUNT_NO[8:]]
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-psbl-order"
    params = {
        "CANO": account_parts[0],
        "ACNT_PRDT_CD": account_parts[1] if len(account_parts) > 1 else "01",
        "PDNO": "005930",
        "ORD_UNPR": "0",
        "ORD_DVSN": "00",
        "CMA_EVLU_AMT_ICLD_YN": "Y",
        "OVRS_ICLD_YN": "N",
    }
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": KIS_MOCK_APP_KEY,
        "appsecret": KIS_MOCK_APP_SECRET,
        "tr_id": "VTTC8908R",
        "custtype": "P",
    }
    try:
        session = await get_session()
        async with session.get(url, params=params, headers=headers) as resp:
            data = await resp.json()
            if data.get("rt_cd") == "0":
                output = data.get("output", {})
                balance = int(output.get("ord_psbl_cash", "0"))
                logger.info(f"가용 잔고: {balance:,}원")
                return balance
            logger.warning(f"잔고 조회 실패: {data.get('msg1', '')}")
    except Exception as e:
        logger.error(f"잔고 조회 오류: {e}")
    return 0


async def run_buy_process():
    cross_data = await fetch_json(f"{DATA_BASE_URL}/cross_signal.json")
    if not isinstance(cross_data, list):
        logger.warning("cross_signal.json 로드 실패")
        return

    targets = filter_high_confidence(cross_data)
    if not targets:
        logger.info("고확신 매수 대상 없음")
        return

    # 이미 보유/주문 중인 종목 제외
    buy_candidates = []
    for t in targets:
        code = t["code"]
        name = t.get("name", "")
        if await is_already_held_or_ordered(code):
            logger.info(f"이미 보유/주문중 — {name}({code}) 스킵")
            continue
        price = 0
        api_data = t.get("api_data", {})
        if api_data:
            price = api_data.get("price", {}).get("current", 0)
        if price <= 0:
            logger.warning(f"현재가 없음 — {name}({code}) 스킵")
            continue
        buy_candidates.append({"code": code, "name": name, "price": price})

    if not buy_candidates:
        logger.info("매수 가능 종목 없음")
        return

    # 가용 잔고 조회 → 균등 분배
    balance = await fetch_available_balance()
    if balance <= 0:
        logger.warning("가용 잔고 없음 — 매수 중단")
        return

    amount_per_stock = balance // len(buy_candidates)
    logger.info(f"고확신 {len(buy_candidates)}종목, 잔고 {balance:,}원, 종목당 {amount_per_stock:,}원")

    if amount_per_stock < 100_000:
        logger.warning(f"종목당 투자금 {amount_per_stock:,}원 — 최소 10만원 미만, 매수 중단")
        return

    for c in buy_candidates:
        quantity = calc_quantity(amount_per_stock, c["price"])
        if quantity <= 0:
            continue
        await place_buy_order_with_qty(c["code"], c["name"], c["price"], quantity)


async def check_positions_for_sell(current_price_data: dict):
    """보유 포지션 수익률 체크 → 익절/손절/수동매도 (캐시 + 중복 매도 방지)"""
    code = current_price_data["code"]
    current_price = current_price_data["price"]

    positions = await get_active_positions()  # 5초 캐시 사용
    for pos in positions:
        if pos["code"] != code:
            continue
        # 수동 매도 요청 처리 (프론트엔드에서 status='sell_requested'로 변경)
        if pos["status"] == "sell_requested":
            position_id = pos["id"]
            if is_selling(position_id):
                continue
            mark_selling(position_id)
            buy_price = pos.get("filled_price") or pos.get("order_price", 0)
            await place_sell_order(
                code=code, name=pos["name"], price=current_price,
                quantity=pos["quantity"], position_id=position_id,
                reason="manual_sell", buy_price=buy_price,
            )
            continue
        if pos["status"] != "filled":
            continue

        position_id = pos["id"]
        # 중복 매도 방지: 이미 매도 진행 중이면 스킵
        if is_selling(position_id):
            continue

        buy_price = pos.get("filled_price") or pos.get("order_price", 0)
        if buy_price <= 0:
            continue

        reason = should_sell(buy_price, current_price)
        if reason:
            mark_selling(position_id)  # 락 설정
            await place_sell_order(
                code=code,
                name=pos["name"],
                price=current_price,
                quantity=pos["quantity"],
                position_id=position_id,
                reason=reason,
                buy_price=buy_price,
            )


async def cancel_all_pending_orders():
    """KIS 미체결 주문 전체 취소 + DB pending 정리"""
    from daemon.position_db import invalidate_cache, delete_position
    token = await _ensure_mock_token()
    if not token:
        return
    account_parts = KIS_MOCK_ACCOUNT_NO.split("-") if "-" in KIS_MOCK_ACCOUNT_NO else [KIS_MOCK_ACCOUNT_NO[:8], KIS_MOCK_ACCOUNT_NO[8:]]
    cano = account_parts[0]
    acnt_cd = account_parts[1] if len(account_parts) > 1 else "01"

    # KIS 모의투자 미체결 조회
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-nccs"
    params = {
        "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
        "INQR_STRT_DT": "", "INQR_END_DT": "",
        "SLL_BUY_DVSN_CD": "00", "INQR_DVSN": "00",
        "PDNO": "", "CCLD_DVSN": "01",
        "ORD_GNO_BRNO": "", "ODNO": "",
        "INQR_DVSN_3": "00", "INQR_DVSN_1": "",
        "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
    }
    session = await get_session()
    try:
        async with session.get(url, params=params, headers=_order_headers(token, "VTTC8001R")) as resp:
            data = await resp.json()
            if data.get("rt_cd") != "0":
                logger.warning(f"미체결 조회 실패: {data.get('msg1', '')}")
                return
            orders = data.get("output", [])
            if not orders:
                logger.info("미체결 주문 없음")
                return
            logger.info(f"미체결 {len(orders)}건 취소 시작")
            for order in orders:
                odno = order.get("odno", "")
                code = order.get("pdno", "")
                qty = order.get("psbl_qty", order.get("ord_qty", "0"))
                # 주문 취소
                cancel_url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/order-rvsecncl"
                cancel_body = {
                    "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
                    "KRX_FWDG_ORD_ORGNO": "",
                    "ORGN_ODNO": odno,
                    "ORD_DVSN": "00",
                    "RVSE_CNCL_DVSN_CD": "02",  # 취소
                    "ORD_QTY": str(qty),
                    "ORD_UNPR": "0",
                    "QTY_ALL_ORD_YN": "Y",
                }
                async with session.post(cancel_url, json=cancel_body, headers=_order_headers(token, "VTTC0803U")) as cresp:
                    cdata = await cresp.json()
                    if cdata.get("rt_cd") == "0":
                        logger.info(f"미체결 취소: {code} 주문번호={odno}")
                    else:
                        logger.warning(f"미체결 취소 실패: {code} {cdata.get('msg1', '')}")
                await asyncio.sleep(0.3)
    except Exception as e:
        logger.error(f"미체결 취소 오류: {e}")

    # DB pending 정리
    positions = await get_active_positions(force_refresh=True)
    pending = [p for p in positions if p["status"] == "pending"]
    for p in pending:
        await delete_position(p["id"])
        logger.info(f"DB pending 삭제: {p.get('name', '')}({p.get('code', '')})")
    invalidate_cache()


async def sell_all_positions_market():
    """보유 중인 전 포지션 시장가 매도 + 미체결 취소 (장 마감 전 청산)"""
    from daemon.position_db import invalidate_cache

    # 1) 미체결 주문 취소
    await cancel_all_pending_orders()

    # 2) 보유 포지션 시장가 매도
    positions = await get_active_positions(force_refresh=True)
    filled = [p for p in positions if p["status"] == "filled"]
    if not filled:
        logger.info("장 마감 청산: 보유 포지션 없음")
        return

    logger.info(f"장 마감 청산: {len(filled)}종목 시장가 매도 시작")
    for pos in filled:
        position_id = pos["id"]
        if is_selling(position_id):
            continue
        mark_selling(position_id)
        buy_price = pos.get("filled_price") or pos.get("order_price", 0)
        # 현재가 조회하여 수익률 계산
        current_price = await _get_current_price(pos["code"])
        result = await _kis_order_market("VTTC0801U", pos["code"], pos["quantity"])
        if result:
            sell_price = current_price if current_price > 0 else buy_price
            pnl = calc_pnl_pct(buy_price, sell_price)
            pnl_amount = (sell_price - buy_price) * pos["quantity"]
            await update_position_sold(position_id, sell_price, pnl, "eod_close")
            logger.info(f"장 마감 매도: {pos['name']}({pos['code']}) {pnl:+.2f}%")
            await send_telegram(
                f"<b>🔔 장 마감 청산</b>\n"
                f"<b>{pos['name']} ({pos['code']})</b>\n"
                f"매수가: {buy_price:,}원 → 현재가: {sell_price:,}원\n"
                f"수익률: {pnl:+.2f}% ({pnl_amount:+,}원)\n"
                f"{pos['quantity']}주 시장가 매도"
            )
        else:
            unmark_selling(position_id)
    invalidate_cache()


async def _get_current_price(code: str) -> int:
    """KIS API로 현재가 조회"""
    token = await _ensure_mock_token()
    if not token:
        return 0
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    try:
        session = await get_session()
        async with session.get(url, params=params, headers=_order_headers(token, "FHKST01010100")) as resp:
            data = await resp.json()
            if data.get("rt_cd") == "0":
                return int(data.get("output", {}).get("stck_prpr", "0"))
    except Exception as e:
        logger.warning(f"현재가 조회 실패 ({code}): {e}")
    return 0


async def _kis_order_market(tr_id: str, code: str, quantity: int) -> dict | None:
    """KIS 모의투자 시장가 주문"""
    token = await _ensure_mock_token()
    if not token:
        return None
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/order-cash"
    account_parts = KIS_MOCK_ACCOUNT_NO.split("-") if "-" in KIS_MOCK_ACCOUNT_NO else [KIS_MOCK_ACCOUNT_NO[:8], KIS_MOCK_ACCOUNT_NO[8:]]
    body = {
        "CANO": account_parts[0],
        "ACNT_PRDT_CD": account_parts[1] if len(account_parts) > 1 else "01",
        "PDNO": code,
        "ORD_DVSN": "01",  # 시장가
        "ORD_QTY": str(quantity),
        "ORD_UNPR": "0",
    }
    try:
        session = await get_session()
        async with session.post(url, json=body, headers=_order_headers(token, tr_id)) as resp:
            data = await resp.json()
            if data.get("rt_cd") == "0":
                return data
            logger.error(f"시장가 주문 실패: {data.get('msg1', '')}")
    except Exception as e:
        logger.error(f"시장가 주문 오류: {e}")
    return None
