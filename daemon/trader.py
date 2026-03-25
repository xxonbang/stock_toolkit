"""KIS 모의투자 자동매매 — 매수/매도 주문 + 수익률 감시"""
import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from daemon.config import (
    KIS_MOCK_APP_KEY, KIS_MOCK_APP_SECRET, KIS_MOCK_ACCOUNT_NO, KIS_MOCK_BASE_URL,
    TRADE_AMOUNT_PER_STOCK, TRADE_TAKE_PROFIT_PCT, TRADE_STOP_LOSS_PCT, TRADE_TRAILING_STOP_PCT,
    DATA_BASE_URL,
)
from daemon.position_db import (
    is_already_held_or_ordered, insert_buy_order, update_position_filled,
    update_position_sold, update_position_quantity, get_active_positions,
    calc_quantity, calc_pnl_pct,
    is_selling, mark_selling, unmark_selling,
)
from daemon.notifier import send_telegram
from daemon.stock_manager import fetch_json, fetch_alert_config
from daemon.http_session import get_session

logger = logging.getLogger("daemon.trader")

BUY_SIGNALS = {"적극매수", "매수"}

# 종목별 고점 추적 (trailing stop용)
_peak_prices: dict[str, int] = {}

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


def filter_high_confidence(signals: list | None, mode: str = "and") -> list[dict]:
    """고확신 종목 필터. mode: 콤마 구분 토글 ('chart,indicator') 또는 레거시 ('and','or','leader')."""
    if not signals:
        return []
    # 레거시 모드 → 토글 플래그 변환
    if mode == "and":
        flags = {"chart", "indicator"}
    elif mode == "or":
        return [s for s in signals if s.get("vision_signal") in BUY_SIGNALS or s.get("api_signal") in BUY_SIGNALS]
    elif mode == "leader":
        flags = {"leader"}
    else:
        flags = set(mode.split(","))
    # 각 ON 토글은 AND 조건 — leader는 cross_signal 포함 자체가 조건(항상 충족)이므로 추가 필터 없음
    need_chart = "chart" in flags
    need_indicator = "indicator" in flags
    return [
        s for s in signals
        if (not need_chart or s.get("vision_signal") in BUY_SIGNALS)
        and (not need_indicator or s.get("api_signal") in BUY_SIGNALS)
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


_MAX_FILL_RETRIES = 3


async def _cancel_unfilled(code: str) -> int | None:
    """KIS 미체결 조회 → 해당 종목 미체결분 취소, 미체결 수량 반환. 조회 실패 시 None."""
    token = await _ensure_mock_token()
    if not token:
        return None
    account_parts = KIS_MOCK_ACCOUNT_NO.split("-") if "-" in KIS_MOCK_ACCOUNT_NO else [KIS_MOCK_ACCOUNT_NO[:8], KIS_MOCK_ACCOUNT_NO[8:]]
    cano, acnt_cd = account_parts[0], account_parts[1] if len(account_parts) > 1 else "01"
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-nccs"
    params = {
        "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
        "INQR_STRT_DT": "", "INQR_END_DT": "",
        "SLL_BUY_DVSN_CD": "02", "INQR_DVSN": "00",
        "PDNO": "", "CCLD_DVSN": "01",
        "ORD_GNO_BRNO": "", "ODNO": "",
        "INQR_DVSN_3": "00", "INQR_DVSN_1": "",
        "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
    }
    unfilled_qty = 0
    try:
        session = await get_session()
        async with session.get(url, params=params, headers=_order_headers(token, "VTTC8001R")) as resp:
            data = await resp.json()
            if data.get("rt_cd") != "0":
                return None
            for order in data.get("output", []):
                if order.get("pdno") != code:
                    continue
                rmn = int(order.get("rmn_qty", "0") or "0")
                if rmn <= 0:
                    continue
                unfilled_qty += rmn
                odno = order.get("odno", "")
                if odno:
                    cancel_url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/order-rvsecncl"
                    cancel_body = {
                        "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
                        "KRX_FWDG_ORD_ORGNO": "", "ORGN_ODNO": odno,
                        "ORD_DVSN": "00", "RVSE_CNCL_DVSN_CD": "02",
                        "ORD_QTY": str(rmn), "ORD_UNPR": "0", "QTY_ALL_ORD_YN": "Y",
                    }
                    async with session.post(cancel_url, json=cancel_body, headers=_order_headers(token, "VTTC0803U")) as cresp:
                        cdata = await cresp.json()
                        if cdata.get("rt_cd") == "0":
                            logger.info(f"미체결 취소: {code} 잔여 {rmn}주")
                        else:
                            logger.warning(f"미체결 취소 실패: {code} {cdata.get('msg1', '')}")
                    await asyncio.sleep(0.3)
    except Exception as e:
        logger.error(f"미체결 조회/취소 오류: {e}")
        return None
    return unfilled_qty


async def _verify_fill_with_retry(code: str, ordered_qty: int) -> int:
    """주문 후 체결 확인 → 미체결분 취소 후 재주문, 최대 3회 retry"""
    total_filled = 0
    remaining = ordered_qty
    for attempt in range(1, _MAX_FILL_RETRIES + 1):
        await asyncio.sleep(1)
        unfilled = await _cancel_unfilled(code)
        if unfilled is None:
            logger.warning(f"미체결 조회 실패: {code} — 체결 확인 불가, 주문수량 그대로 반영")
            return ordered_qty
        filled_this_round = remaining - unfilled
        total_filled += filled_this_round
        if unfilled == 0:
            break  # 전량 체결
        remaining = unfilled
        if attempt < _MAX_FILL_RETRIES:
            logger.info(f"미체결 재주문 ({attempt}/{_MAX_FILL_RETRIES}): {code} {remaining}주")
            result = await _kis_order_market("VTTC0802U", code, remaining)
            if not result:
                logger.warning(f"재주문 실패: {code} {remaining}주")
                break
        else:
            logger.info(f"최대 재시도 도달: {code} 최종 체결 {total_filled}주 / 주문 {ordered_qty}주")
    if total_filled != ordered_qty:
        logger.info(f"체결 결과: {code} 주문 {ordered_qty}주 → 체결 {total_filled}주")
    return total_filled


async def place_buy_order_with_qty(code: str, name: str, price: int, quantity: int) -> bool:
    """수량을 직접 지정하여 시장가 매수 (미체결 방지)"""
    if await is_upper_limit(code, price):
        logger.info(f"상한가 종목 스킵 — {name}({code}) {price:,}원")
        return False
    position = await insert_buy_order(code, name, price, quantity)
    if not position:
        return False

    # 시장가 매수 (지정가 미체결 방지)
    result = await _kis_order_market("VTTC0802U", code, quantity)
    if result:
        filled_qty = await _verify_fill_with_retry(code, quantity)
        if filled_qty <= 0:
            # 체결 0주 → DB 정리
            from daemon.position_db import delete_position
            await delete_position(position["id"])
            logger.warning(f"체결 0주 → pending 삭제: {name}({code})")
            return False
        await update_position_filled(position["id"], price)
        if filled_qty != quantity:
            await update_position_quantity(position["id"], filled_qty)
        logger.info(f"매수 체결: {name}({code}) {price:,}원 × {filled_qty}주 (시장가)")
        await send_telegram(
            f"<b>📥 자동 매수 체결</b>\n"
            f"<b>{name} ({code})</b>\n"
            f"가격: {price:,}원 × {filled_qty}주\n"
            f"금액: {price * filled_qty:,}원"
            + (f"\n⚠️ 부분체결 ({quantity}주 중 {filled_qty}주)" if filled_qty != quantity else "")
        )
        # 매수 후 구독 갱신 (모의투자 종목 WebSocket 수신 시작)
        try:
            from daemon.main import trigger_subscription_refresh
            asyncio.ensure_future(trigger_subscription_refresh())
        except Exception:
            pass
        return True
    # KIS 주문 실패 → DB pending 정리
    from daemon.position_db import delete_position
    await delete_position(position["id"])
    logger.warning(f"매수 실패 → pending 삭제: {name}({code})")
    return False


async def place_sell_order(code: str, name: str, price: int, quantity: int, position_id: str, reason: str, buy_price: int) -> bool:
    # 시장가 매도 (지정가 미체결 방지)
    result = await _kis_order_market("VTTC0801U", code, quantity)
    if result:
        pnl = calc_pnl_pct(buy_price, price)
        await update_position_sold(position_id, price, pnl, reason)
        reason_labels = {"take_profit": "익절", "stop_loss": "손절", "trailing_stop": "급락 손절", "manual_sell": "수동 매도", "eod_close": "장 마감 청산"}
        reason_label = reason_labels.get(reason, reason)
        emoji = {"take_profit": "💰", "stop_loss": "🛑", "trailing_stop": "📉", "manual_sell": "✋", "eod_close": "🔔"}.get(reason, "📊")
        # 고점 추적 정리
        _peak_prices.pop(position_id, None)
        logger.info(f"매도 체결: {name}({code}) {reason_label} ({pnl:+.1f}%)")
        await send_telegram(
            f"<b>{emoji} 자동 매도 ({reason_label})</b>\n"
            f"<b>{name} ({code})</b>\n"
            f"매수가: {buy_price:,}원 → 매도가: {price:,}원\n"
            f"수익률: {pnl:+.2f}% ({quantity}주)"
        )
        # 매도 후 구독 갱신 (보유 종목 변경 반영)
        try:
            from daemon.main import trigger_subscription_refresh
            asyncio.ensure_future(trigger_subscription_refresh())
        except Exception:
            pass
        return True
    unmark_selling(position_id)
    logger.error(f"매도 실패: {name}({code}) {reason}")
    await send_telegram(f"<b>⚠️ 매도 실패</b>\n{name} ({code})\n사유: {reason}\n수동 확인 필요")
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

    config = await fetch_alert_config()
    buy_mode = config.get("buy_signal_mode", "and")
    targets = filter_high_confidence(cross_data, mode=buy_mode)
    if not targets:
        logger.info(f"고확신 매수 대상 없음 (모드: {buy_mode})")
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

    MIN_AMOUNT_PER_STOCK = 1_000_000  # 종목당 최소 100만원
    if balance <= MIN_AMOUNT_PER_STOCK:
        # 100만원 이하: 1종목만 매수
        actual_candidates = buy_candidates[:1]
    else:
        # 100만원 초과: 종목당 100만원 기준으로 매수 가능 종목 수 결정
        max_stocks = balance // MIN_AMOUNT_PER_STOCK
        actual_candidates = buy_candidates[:max_stocks]
    amount_per_stock = balance // len(actual_candidates)
    logger.info(f"고확신 {len(buy_candidates)}종목 중 {len(actual_candidates)}종목 매수, 잔고 {balance:,}원, 종목당 {amount_per_stock:,}원")

    for c in actual_candidates:
        quantity = calc_quantity(amount_per_stock, c["price"])
        if quantity <= 0:
            continue
        await place_buy_order_with_qty(c["code"], c["name"], c["price"], quantity)


_trade_config_cache: dict | None = None
_trade_config_time: float = 0

async def _get_trade_config() -> dict:
    """익절/손절 설정 조회 (60초 캐시)"""
    global _trade_config_cache, _trade_config_time
    now = time.time()
    if _trade_config_cache and (now - _trade_config_time) < 60:
        return _trade_config_cache
    _trade_config_cache = await fetch_alert_config()
    _trade_config_time = now
    return _trade_config_cache


async def check_positions_for_sell(current_price_data: dict):
    """보유 포지션 수익률 체크 → 익절/손절/수동매도 (캐시 + 중복 매도 방지)"""
    code = current_price_data["code"]
    current_price = current_price_data["price"]

    config = await _get_trade_config()
    tp = config.get("take_profit_pct", TRADE_TAKE_PROFIT_PCT)
    sl = config.get("stop_loss_pct", TRADE_STOP_LOSS_PCT)

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

        # 고점 추적 (trailing stop용)
        peak_key = position_id
        if current_price > _peak_prices.get(peak_key, 0):
            _peak_prices[peak_key] = current_price

        # 익일 보유 종목은 익절 기준 10%로 상향
        _KST = timezone(timedelta(hours=9))
        created = pos.get("created_at", "")
        is_carry_over = False
        if created:
            try:
                created_date = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(_KST).date()
                today = datetime.now(_KST).date()
                is_carry_over = created_date < today
            except Exception:
                pass
        effective_tp = 10.0 if is_carry_over else tp

        reason = should_sell(buy_price, current_price, take_profit=effective_tp, stop_loss=sl)

        # trailing stop: 수익 중(pnl > 0)이고 고점 대비 c% 하락
        if not reason:
            pnl = calc_pnl_pct(buy_price, current_price)
            peak = _peak_prices.get(peak_key, current_price)
            if pnl > 0 and peak > 0:
                drop = (current_price - peak) / peak * 100
                ts_pct = config.get("trailing_stop_pct", TRADE_TRAILING_STOP_PCT)
                if drop <= ts_pct:
                    reason = "trailing_stop"

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


CARRY_OVER_THRESHOLD = 3.0  # 익일 보유 허용 기준 (당일 수익률 %)
MAX_HOLD_DAYS = 3           # 최대 보유일 (초과 시 강제 청산)

async def sell_all_positions_market():
    """장 마감 청산 — 수익 +3% 이상은 익일 보유, 나머지 시장가 매도"""
    from daemon.position_db import invalidate_cache

    # 1) 미체결 주문 취소
    await cancel_all_pending_orders()

    # 2) 보유 포지션 분류
    positions = await get_active_positions(force_refresh=True)
    filled = [p for p in positions if p["status"] == "filled"]
    if not filled:
        logger.info("장 마감 청산: 보유 포지션 없음")
        return

    to_sell = []
    to_carry = []

    _KST = timezone(timedelta(hours=9))
    today = datetime.now(_KST).date()

    for pos in filled:
        buy_price = pos.get("filled_price") or pos.get("order_price", 0)
        if buy_price <= 0:
            to_sell.append(pos)
            continue

        # 보유일 계산
        hold_days = 0
        created = pos.get("created_at", "")
        if created:
            try:
                created_date = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(_KST).date()
                hold_days = (today - created_date).days
            except Exception:
                pass

        current_price = await _get_current_price(pos["code"])
        pnl = calc_pnl_pct(buy_price, current_price) if current_price > 0 else 0
        pos["_current_price"] = current_price
        pos["_pnl"] = pnl

        # 최대 보유일 초과 → 강제 매도
        if hold_days >= MAX_HOLD_DAYS:
            to_sell.append(pos)
            logger.info(f"최대 보유일 초과({hold_days}일): {pos['name']}({pos['code']})")
        elif pnl >= CARRY_OVER_THRESHOLD:
            to_carry.append(pos)
        else:
            to_sell.append(pos)
        await asyncio.sleep(0.2)

    # 익일 보유 종목: 고점 추적 초기화 (익일 시가부터 새로 추적)
    for pos in to_carry:
        _peak_prices.pop(pos.get("id", ""), None)

    # 익일 보유 종목 알림
    if to_carry:
        carry_lines = []
        for pos in to_carry:
            carry_lines.append(f"  {pos['name']}({pos['code']}) {pos['_pnl']:+.2f}%")
        logger.info(f"익일 보유: {len(to_carry)}종목 (수익 +{CARRY_OVER_THRESHOLD}% 이상)")
        await send_telegram(
            f"<b>📌 익일 보유 ({len(to_carry)}종목)</b>\n"
            f"수익 +{CARRY_OVER_THRESHOLD}% 이상 → 보유 유지\n"
            f"익절 목표: +10%, trailing stop: -3%\n\n"
            + "\n".join(carry_lines)
        )

    # 매도 대상
    if not to_sell:
        logger.info("장 마감 청산: 매도 대상 없음 (전종목 익일 보유)")
        invalidate_cache()
        return

    logger.info(f"장 마감 청산: {len(to_sell)}종목 매도, {len(to_carry)}종목 익일 보유")
    for pos in to_sell:
        position_id = pos["id"]
        if is_selling(position_id):
            continue
        mark_selling(position_id)
        buy_price = pos.get("filled_price") or pos.get("order_price", 0)
        current_price = pos.get("_current_price") or await _get_current_price(pos["code"])
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
