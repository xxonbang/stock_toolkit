"""KIS 모의투자 자동매매 — 매수/매도 주문 + 수익률 감시"""
import logging
import aiohttp
from daemon.config import (
    KIS_APP_KEY, KIS_APP_SECRET, KIS_MOCK_ACCOUNT_NO, KIS_MOCK_BASE_URL,
    TRADE_AMOUNT_PER_STOCK, TRADE_TAKE_PROFIT_PCT, TRADE_STOP_LOSS_PCT,
    DATA_BASE_URL,
)
from daemon.position_db import (
    is_already_held_or_ordered, insert_buy_order, update_position_filled,
    update_position_sold, get_active_positions, calc_quantity, calc_pnl_pct,
)
from daemon.notifier import send_telegram
from daemon.stock_manager import fetch_json

logger = logging.getLogger("daemon.trader")

BUY_SIGNALS = {"적극매수", "매수"}

_access_token = ""


async def _ensure_mock_token() -> str | None:
    global _access_token
    if _access_token:
        return _access_token
    url = f"{KIS_MOCK_BASE_URL}/oauth2/tokenP"
    body = {
        "grant_type": "client_credentials",
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_APP_SECRET,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    _access_token = data.get("access_token", "")
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
    """매도 판정: 'take_profit', 'stop_loss', 또는 None(홀드)"""
    pnl = calc_pnl_pct(buy_price, current_price)
    if pnl >= take_profit:
        return "take_profit"
    if pnl <= stop_loss:
        return "stop_loss"
    return None


async def place_buy_order(code: str, name: str, price: int) -> bool:
    """KIS 모의투자 지정가 매수 주문"""
    token = await _ensure_mock_token()
    if not token:
        return False

    quantity = calc_quantity(TRADE_AMOUNT_PER_STOCK, price)
    if quantity <= 0:
        logger.warning(f"매수 수량 0 — {name}({code}) 가격 {price}원")
        return False

    position = await insert_buy_order(code, name, price, quantity)
    if not position:
        return False

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
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=_order_headers(token, "VTTC0802U"), timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("rt_cd") == "0":
                    await update_position_filled(position["id"], price)
                    logger.info(f"매수 체결: {name}({code}) {price:,}원 × {quantity}주")
                    await send_telegram(
                        f"<b>📥 자동 매수 체결</b>\n"
                        f"<b>{name} ({code})</b>\n"
                        f"가격: {price:,}원 × {quantity}주\n"
                        f"금액: {price * quantity:,}원"
                    )
                    return True
                else:
                    msg = data.get("msg1", "")
                    logger.error(f"매수 주문 실패: {name}({code}) — {msg}")
    except Exception as e:
        logger.error(f"매수 주문 오류: {e}")
    return False


async def place_sell_order(code: str, name: str, price: int, quantity: int, position_id: str, reason: str, buy_price: int) -> bool:
    """KIS 모의투자 지정가 매도 주문"""
    token = await _ensure_mock_token()
    if not token:
        return False

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
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=_order_headers(token, "VTTC0801U"), timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("rt_cd") == "0":
                    pnl = calc_pnl_pct(buy_price, price)
                    await update_position_sold(position_id, price, pnl, reason)
                    reason_label = "익절 +2%" if reason == "take_profit" else "손절 -3%"
                    emoji = "💰" if reason == "take_profit" else "🛑"
                    logger.info(f"매도 체결: {name}({code}) {reason_label} ({pnl:+.1f}%)")
                    await send_telegram(
                        f"<b>{emoji} 자동 매도 ({reason_label})</b>\n"
                        f"<b>{name} ({code})</b>\n"
                        f"매수가: {buy_price:,}원 → 매도가: {price:,}원\n"
                        f"수익률: {pnl:+.2f}% ({quantity}주)"
                    )
                    return True
                else:
                    msg = data.get("msg1", "")
                    logger.error(f"매도 주문 실패: {name}({code}) — {msg}")
    except Exception as e:
        logger.error(f"매도 주문 오류: {e}")
    return False


async def run_buy_process():
    """매수 프로세스: cross_signal에서 고확신 종목 추출 → 중복 체크 → 매수"""
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
    """보유 포지션 수익률 체크 → 익절/손절"""
    code = current_price_data["code"]
    current_price = current_price_data["price"]

    positions = await get_active_positions()
    for pos in positions:
        if pos["code"] != code or pos["status"] != "filled":
            continue

        buy_price = pos.get("filled_price") or pos.get("order_price", 0)
        if buy_price <= 0:
            continue

        reason = should_sell(buy_price, current_price)
        if reason:
            await place_sell_order(
                code=code,
                name=pos["name"],
                price=current_price,
                quantity=pos["quantity"],
                position_id=pos["id"],
                reason=reason,
                buy_price=buy_price,
            )
