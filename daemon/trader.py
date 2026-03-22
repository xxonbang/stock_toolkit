"""KIS 모의투자 자동매매 — 매수/매도 주문 + 수익률 감시"""
import logging
import time
from daemon.config import (
    KIS_APP_KEY, KIS_APP_SECRET, KIS_MOCK_ACCOUNT_NO, KIS_MOCK_BASE_URL,
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
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_APP_SECRET,
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
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_APP_SECRET,
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
                import asyncio
                await asyncio.sleep(1)
                return await _kis_order(tr_id, code, quantity, price, retry=False)
            logger.error(f"KIS 주문 실패 ({tr_id}): {msg}")
    except Exception as e:
        logger.error(f"KIS 주문 오류 ({tr_id}): {e}")
    return None


async def place_buy_order(code: str, name: str, price: int) -> bool:
    quantity = calc_quantity(TRADE_AMOUNT_PER_STOCK, price)
    if quantity <= 0:
        logger.warning(f"매수 수량 0 — {name}({code}) 가격 {price}원")
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
        reason_label = "익절 +3%" if reason == "take_profit" else "손절 -3%"
        emoji = "💰" if reason == "take_profit" else "🛑"
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


async def run_buy_process():
    cross_data = await fetch_json(f"{DATA_BASE_URL}/cross_signal.json")
    if not isinstance(cross_data, list):
        logger.warning("cross_signal.json 로드 실패")
        return

    targets = filter_high_confidence(cross_data)
    if not targets:
        logger.info("고확신 매수 대상 없음")
        return

    logger.info(f"고확신 종목 {len(targets)}개 발견")
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

        await place_buy_order(code, name, price)


async def check_positions_for_sell(current_price_data: dict):
    """보유 포지션 수익률 체크 → 익절/손절 (캐시 + 중복 매도 방지)"""
    code = current_price_data["code"]
    current_price = current_price_data["price"]

    positions = await get_active_positions()  # 5초 캐시 사용
    for pos in positions:
        if pos["code"] != code or pos["status"] != "filled":
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
