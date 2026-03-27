"""KIS 모의투자 자동매매 — 매수/매도 주문 + 수익률 감시"""
import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from daemon.config import (
    KIS_MOCK_APP_KEY, KIS_MOCK_APP_SECRET, KIS_MOCK_ACCOUNT_NO, KIS_MOCK_BASE_URL,
    TRADE_TAKE_PROFIT_PCT, TRADE_STOP_LOSS_PCT, TRADE_TRAILING_STOP_PCT, TRADE_MIN_AMOUNT_PER_STOCK,
    DATA_BASE_URL,
)
from daemon.position_db import (
    is_already_held_or_ordered, insert_buy_order, update_position_filled,
    update_position_sold, update_position_quantity, get_active_positions,
    calc_quantity, calc_pnl_pct,
    is_selling, mark_selling, unmark_selling, try_mark_selling,
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


_KST = timezone(timedelta(hours=9))


def _calc_hold_days(pos: dict) -> int:
    """포지션의 보유일수 계산 (KST 기준)"""
    created = pos.get("filled_at") or pos.get("created_at", "")
    if not created:
        return 0
    try:
        created_date = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(_KST).date()
        return (datetime.now(_KST).date() - created_date).days
    except Exception:
        return 0


def _parse_account() -> tuple[str, str]:
    """KIS_MOCK_ACCOUNT_NO를 (CANO, ACNT_PRDT_CD) 튜플로 파싱"""
    parts = KIS_MOCK_ACCOUNT_NO.split("-") if "-" in KIS_MOCK_ACCOUNT_NO else [KIS_MOCK_ACCOUNT_NO[:8], KIS_MOCK_ACCOUNT_NO[8:]]
    return parts[0], parts[1] if len(parts) > 1 else "01"


def filter_high_confidence(signals: list | None, mode: str = "and") -> list[dict]:
    """고확신 종목 필터. mode: 콤마 구분 토글 ('chart,indicator,top_leader') 또는 레거시."""
    if not signals or mode == "none":
        return []
    # 레거시 모드 → 토글 플래그 변환
    if mode == "and":
        flags = {"chart", "indicator"}
    elif mode == "or":
        return [s for s in signals if s.get("vision_signal") in BUY_SIGNALS or s.get("api_signal") in BUY_SIGNALS]
    elif mode == "leader":
        flags = {"all_leaders"}
    else:
        flags = set(mode.split(","))
    # top_leader: 대장주(theme 보유) 중 테마별 거래대금 1위 코드 집합 산출
    top_codes: set[str] | None = None
    if "top_leader" in flags:
        theme_best: dict[str, tuple[str, int]] = {}  # theme → (code, volume)
        for s in signals:
            theme = s.get("theme")
            if not theme:
                continue  # 대장주가 아닌 종목은 top_leader 대상 아님
            vol = (s.get("api_data") or {}).get("ranking", {}).get("volume", 0)
            if theme not in theme_best or vol > theme_best[theme][1]:
                theme_best[theme] = (s.get("code", ""), vol)
        top_codes = {code for code, _ in theme_best.values()}
    # all_leaders: theme 필드가 있는 종목만 (대장주)
    need_all_leaders = "all_leaders" in flags
    # 시그널 + 대장주 조건 AND 필터
    need_chart = "chart" in flags
    need_indicator = "indicator" in flags
    return [
        s for s in signals
        if (not need_chart or s.get("vision_signal") in BUY_SIGNALS)
        and (not need_indicator or s.get("api_signal") in BUY_SIGNALS)
        and (top_codes is None or s.get("code", "") in top_codes)
        and (not need_all_leaders or s.get("theme"))
    ]


def should_sell(buy_price: int, current_price: int, take_profit: float = TRADE_TAKE_PROFIT_PCT, stop_loss: float = TRADE_STOP_LOSS_PCT) -> str | None:
    pnl = calc_pnl_pct(buy_price, current_price)
    if pnl >= take_profit:
        return "take_profit"
    if pnl <= stop_loss:
        return "stop_loss"
    return None


# Stepped Trailing 파라미터 (고정값)
_STEPPED_LEVELS = [
    (25.0, None),   # +25%+ → peak - trailing_pct (동적)
    (20.0, 15.0),   # +20% 도달 → stop +15%
    (15.0, 10.0),   # +15% 도달 → stop +10%
    (10.0, 5.0),    # +10% 도달 → stop +5%
    (5.0, 0.0),     # +5% 도달 → stop 0% (본전)
]


def calc_stepped_stop_pct(peak_pnl_pct: float, trailing_pct: float) -> float:
    """Stepped Trailing: 고점 수익률 기반 stop 위치 계산.
    peak_pnl_pct: 매수가 대비 고점 수익률 (%)
    trailing_pct: trailing stop % (음수, 기본 -3.0)
    Returns: stop 수익률 (%, 이 아래로 내려가면 매도)
    """
    for level, stop in _STEPPED_LEVELS:
        if peak_pnl_pct >= level:
            if stop is None:
                # +25% 이상: 고점 기준 trailing
                return peak_pnl_pct + trailing_pct  # e.g., 27% + (-3%) = 24%
            return stop
    return -999.0  # step 미도달 → stepped stop 미작동, 기본 SL만 적용


async def _kis_order(tr_id: str, code: str, quantity: int, price: int, retry: bool = True) -> dict | None:
    """KIS 모의투자 주문 공통 — 토큰 만료 시 1회 재시도"""
    token = await _ensure_mock_token()
    if not token:
        return None
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/order-cash"
    cano, acnt_cd = _parse_account()
    body = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_cd,
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


_MAX_FILL_RETRIES = 3


async def _cancel_unfilled(code: str, is_sell: bool = False) -> int | None:
    """KIS 미체결 조회 → 해당 종목 미체결분 취소, 미체결 수량 반환. 조회 실패 시 None."""
    sll_buy = "01" if is_sell else "02"
    label = "매도 " if is_sell else ""
    token = await _ensure_mock_token()
    if not token:
        return None
    cano, acnt_cd = _parse_account()
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-nccs"
    params = {
        "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
        "INQR_STRT_DT": "", "INQR_END_DT": "",
        "SLL_BUY_DVSN_CD": sll_buy, "INQR_DVSN": "00",
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
                            logger.info(f"{label}미체결 취소: {code} 잔여 {rmn}주")
                        else:
                            logger.warning(f"{label}미체결 취소 실패: {code} {cdata.get('msg1', '')}")
                    await asyncio.sleep(0.3)
    except Exception as e:
        logger.error(f"{label}미체결 조회/취소 오류: {e}")
        return None
    return unfilled_qty


async def _verify_sell_fill(code: str, ordered_qty: int) -> int:
    """매도 주문 후 체결 확인 → 미체결분 취소 후 재주문, 최대 3회 retry"""
    total_filled = 0
    remaining = ordered_qty
    for attempt in range(1, _MAX_FILL_RETRIES + 1):
        await asyncio.sleep(1)
        unfilled = await _cancel_unfilled(code, is_sell=True)
        if unfilled is None:
            logger.warning(f"매도 미체결 조회 실패: {code} — 모의투자 시장가 즉시체결 간주")
            return ordered_qty
        filled_this_round = remaining - unfilled
        total_filled += filled_this_round
        if unfilled == 0:
            break  # 전량 체결
        remaining = unfilled
        if attempt < _MAX_FILL_RETRIES:
            logger.info(f"매도 미체결 재주문 ({attempt}/{_MAX_FILL_RETRIES}): {code} {remaining}주")
            result = await _kis_order_market("VTTC0801U", code, remaining)
            if not result:
                logger.warning(f"매도 재주문 실패: {code} {remaining}주")
                break
        else:
            logger.info(f"매도 최대 재시도 도달: {code} 최종 체결 {total_filled}주 / 주문 {ordered_qty}주")
    if total_filled != ordered_qty:
        logger.warning(f"매도 부분체결: {code} 주문 {ordered_qty}주 → 체결 {total_filled}주")
    return total_filled


async def _verify_fill_with_retry(code: str, ordered_qty: int) -> int:
    """주문 후 체결 확인 → 미체결분 취소 후 재주문, 최대 3회 retry"""
    total_filled = 0
    remaining = ordered_qty
    for attempt in range(1, _MAX_FILL_RETRIES + 1):
        await asyncio.sleep(1)
        unfilled = await _cancel_unfilled(code)
        if unfilled is None:
            logger.warning(f"미체결 조회 실패: {code} — 모의투자 시장가 즉시체결 간주")
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
            task = asyncio.ensure_future(trigger_subscription_refresh())
            task.add_done_callback(lambda t: logger.warning(f"구독 갱신 실패: {t.exception()}") if not t.cancelled() and t.exception() else None)
        except Exception:
            pass
        # 비선택 전략 가상 시뮬레이션 생성
        try:
            config = await _get_trade_config()
            active_strategy = config.get("strategy_type", "fixed")
            sim_strategy = "stepped" if active_strategy == "fixed" else "fixed"
            trade_id = position["id"]
            user_id = position.get("user_id", "")
            asyncio.ensure_future(_create_simulation(
                trade_id=trade_id,
                strategy_type=sim_strategy,
                entry_price=price,
                user_id=user_id,
            ))
        except Exception as e:
            logger.warning(f"가상 시뮬레이션 생성 호출 오류: {e}")
        return True
    # KIS 주문 실패 → DB pending 정리
    from daemon.position_db import delete_position
    await delete_position(position["id"])
    logger.warning(f"매수 실패 → pending 삭제: {name}({code})")
    return False


async def place_sell_order(code: str, name: str, price: int, quantity: int, position_id: str, reason: str, buy_price: int) -> bool:
    try:
        result = await _kis_order_market("VTTC0801U", code, quantity)
        if result:
            filled_qty = await _verify_sell_fill(code, quantity)
            if filled_qty <= 0:
                unmark_selling(position_id)
                _peak_prices.pop(position_id, None)
                logger.warning(f"매도 체결 0주: {name}({code}) — 매도 실패 처리")
                await send_telegram(f"<b>⚠️ 매도 미체결</b>\n{name} ({code})\n사유: {reason}\n체결 0주, 수동 확인 필요")
                return False
            pnl = calc_pnl_pct(buy_price, price)
            reason_labels = {"take_profit": "익절", "stop_loss": "손절", "trailing_stop": "급락 손절", "manual_sell": "수동 매도", "eod_close": "장 마감 청산"}
            reason_label = reason_labels.get(reason, reason)
            emoji = {"take_profit": "💰", "stop_loss": "🛑", "trailing_stop": "📉", "manual_sell": "✋", "eod_close": "🔔"}.get(reason, "📊")
            _peak_prices.pop(position_id, None)
            if filled_qty < quantity:
                # NOTE: update_position_quantity()가 unmark_selling() 전에 실행되므로
                # 재매도 시 줄어든 잔여 수량으로만 주문됨 (이중 매도 아님)
                await update_position_quantity(position_id, quantity - filled_qty)
                unmark_selling(position_id)
                logger.warning(f"매도 부분체결: {name}({code}) {filled_qty}/{quantity}주, 잔여 {quantity - filled_qty}주")
            else:
                await update_position_sold(position_id, price, pnl, reason)
            logger.info(f"매도 체결: {name}({code}) {reason_label} ({pnl:+.1f}%) {filled_qty}주")
            await send_telegram(
                f"<b>{emoji} 자동 매도 ({reason_label})</b>\n"
                f"<b>{name} ({code})</b>\n"
                f"매수가: {buy_price:,}원 → 매도가: {price:,}원\n"
                f"수익률: {pnl:+.2f}% ({filled_qty}주)"
                + (f"\n⚠️ 부분체결 ({quantity}주 중 {filled_qty}주)" if filled_qty != quantity else "")
            )
            try:
                from daemon.main import trigger_subscription_refresh
                task = asyncio.ensure_future(trigger_subscription_refresh())
                task.add_done_callback(lambda t: logger.warning(f"구독 갱신 실패: {t.exception()}") if not t.cancelled() and t.exception() else None)
            except Exception:
                pass
            return True
        unmark_selling(position_id)
        _peak_prices.pop(position_id, None)
        logger.error(f"매도 실패: {name}({code}) {reason}")
        await send_telegram(f"<b>⚠️ 매도 실패</b>\n{name} ({code})\n사유: {reason}\n수동 확인 필요")
        return False
    except Exception as e:
        unmark_selling(position_id)
        _peak_prices.pop(position_id, None)
        logger.error(f"매도 처리 오류: {name}({code}) {e}")
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
    cano, acnt_cd = _parse_account()
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-psbl-order"
    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_cd,
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


MAX_DAILY_LOSS_PCT = -10.0  # 당일 누적 손실 한도 (%)

async def run_buy_process():
    # 당일 누적 손실 체크 — 한도 초과 시 매수 중단
    sold_today_rows = await _get_sold_today_trades()
    if sold_today_rows:
        total_loss = sum(t.get("pnl_pct", 0) for t in sold_today_rows)
        if total_loss <= MAX_DAILY_LOSS_PCT:
            logger.warning(f"당일 누적 손실 {total_loss:.1f}% — 매수 중단 (한도 {MAX_DAILY_LOSS_PCT}%)")
            return
    sold_today_codes = {r["code"] for r in sold_today_rows if r.get("code")}

    cross_data = await fetch_json(f"{DATA_BASE_URL}/cross_signal.json")
    if not isinstance(cross_data, list):
        logger.warning("cross_signal.json 로드 실패")
        return

    config = await fetch_alert_config()
    buy_mode = config.get("buy_signal_mode", "and")
    # fallback_top_leader는 별도 처리 — 원래 조건에서 제외
    has_fallback = "fallback_top_leader" in buy_mode
    primary_mode = buy_mode.replace(",fallback_top_leader", "").replace("fallback_top_leader,", "").replace("fallback_top_leader", "") or "none"
    targets = filter_high_confidence(cross_data, mode=primary_mode)
    # fallback: 원래 조건 매칭 0건 시 대장주 1위로 대체
    if not targets and has_fallback:
        logger.info(f"1차 조건({primary_mode}) 매칭 0건 — fallback 대장주 1위로 전환")
        targets = filter_high_confidence(cross_data, mode="top_leader")
    if not targets:
        logger.info(f"고확신 매수 대상 없음 (모드: {buy_mode})")
        return

    # Pass 1: 보유/주문/당일매도 필터링 (현재가 API 호출 없음)
    need_price = []
    for t in targets:
        code = t["code"]
        name = t.get("name", "")
        if await is_already_held_or_ordered(code):
            logger.info(f"이미 보유/주문중 — {name}({code}) 스킵")
            continue
        if code in sold_today_codes:
            logger.info(f"당일 매도 종목 — {name}({code}) 재매수 방지 스킵")
            continue
        price = 0
        api_data = t.get("api_data", {})
        if api_data:
            price = api_data.get("price", {}).get("current", 0)
        need_price.append({"code": code, "name": name, "price": price, "_need_fetch": price <= 0})

    if not need_price:
        logger.info("매수 가능 종목 없음")
        return

    # Pass 2: 현재가 병렬 조회
    fetch_targets = [c for c in need_price if c["_need_fetch"]]
    if fetch_targets:
        prices = await asyncio.gather(*[_get_current_price(c["code"]) for c in fetch_targets])
        for c, p in zip(fetch_targets, prices):
            c["price"] = p

    # Pass 3: 가격 없는 종목 제거 + 상한가 체크
    buy_candidates = []
    for c in need_price:
        if c["price"] <= 0:
            logger.warning(f"현재가 없음 — {c['name']}({c['code']}) 스킵")
            continue
        # 상한가 사전 체크 (분배 전에 걸러냄)
        if await is_upper_limit(c["code"], c["price"]):
            logger.info(f"상한가 종목 스킵 — {c['name']}({c['code']}) {c['price']:,}원")
            continue
        buy_candidates.append({"code": c["code"], "name": c["name"], "price": c["price"]})

    if not buy_candidates:
        logger.info("매수 가능 종목 없음")
        return

    # 가용 잔고 조회 → 균등 분배
    balance = await fetch_available_balance()
    if balance <= 0:
        logger.warning("가용 잔고 없음 — 매수 중단")
        return

    if balance <= TRADE_MIN_AMOUNT_PER_STOCK:
        actual_candidates = buy_candidates[:1]
    else:
        max_stocks = balance // TRADE_MIN_AMOUNT_PER_STOCK
        actual_candidates = buy_candidates[:max_stocks]
    amount_per_stock = balance // len(actual_candidates)
    logger.info(f"매수 대상 {len(buy_candidates)}종목 중 {len(actual_candidates)}종목 매수, 잔고 {balance:,}원, 종목당 {amount_per_stock:,}원")

    for c in actual_candidates:
        quantity = calc_quantity(amount_per_stock, c["price"])
        if quantity <= 0:
            continue
        await place_buy_order_with_qty(c["code"], c["name"], c["price"], quantity)


def _today_utc_start() -> str:
    """KST 0시를 UTC로 변환한 타임스탬프"""
    return (datetime.now(_KST).replace(hour=0, minute=0, second=0) - timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:%S")


async def _get_sold_today_trades() -> list[dict]:
    """당일 매도된 종목 전체 조회 (pnl_pct 포함)"""
    from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return []
    try:
        session = await get_session()
        today_utc = _today_utc_start()
        url = f"{SUPABASE_URL}/rest/v1/auto_trades?status=eq.sold&sold_at=gte.{today_utc}&select=code,pnl_pct"
        headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
    except Exception as e:
        logger.warning(f"당일 매도 종목 조회 실패: {e}")
    return []



_trade_config_cache: dict | None = None
_trade_config_time: float = 0
_TRADE_CONFIG_TTL = 30  # seconds

async def _get_trade_config() -> dict:
    """익절/손절 설정 조회 (30초 캐시)"""
    global _trade_config_cache, _trade_config_time
    now = time.time()
    if _trade_config_cache and (now - _trade_config_time) < _TRADE_CONFIG_TTL:
        return _trade_config_cache
    _trade_config_cache = await fetch_alert_config()
    _trade_config_time = now
    return _trade_config_cache


async def check_positions_for_sell(current_price_data: dict):
    """보유 포지션 수익률 체크 → 익절/손절/수동매도 (캐시 + 중복 매도 방지)"""
    code = current_price_data.get("code", "")
    current_price = current_price_data.get("price", 0)
    if not code or current_price <= 0:
        return

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

        # 고점 추적 (trailing stop용, flash spike 방지: 이전 peak 대비 +5% 초과 점프 무시)
        peak_key = position_id
        prev_peak = _peak_prices.get(peak_key, 0)
        if current_price > prev_peak:
            if prev_peak > 0 and (current_price - prev_peak) / prev_peak > 0.05:
                pass  # flash spike — peak 갱신 안 함
            else:
                _peak_prices[peak_key] = current_price

        # 보유일수 계산 → 익절 기준 연동
        hold_days = _calc_hold_days(pos)
        effective_tp = get_tiered_tp(tp, hold_days)

        strategy_type = config.get("strategy_type", "fixed")
        reason = None

        if strategy_type == "stepped":
            # Stepped Trailing: 고정 TP 없음, stepped stop만 적용
            pnl = calc_pnl_pct(buy_price, current_price)

            # 기본 손절 체크
            if pnl <= sl:
                reason = "stop_loss"
            else:
                # 고점 수익률 기준 stepped stop 계산
                peak = _peak_prices.get(peak_key, current_price)
                peak_pnl = calc_pnl_pct(buy_price, peak)
                ts_pct = config.get("trailing_stop_pct", TRADE_TRAILING_STOP_PCT)
                stepped_stop = calc_stepped_stop_pct(peak_pnl, ts_pct)
                if stepped_stop > -999.0 and pnl <= stepped_stop:
                    reason = "stepped_trailing"
        else:
            # Fixed: 현행 로직 그대로
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
            if not try_mark_selling(position_id):
                continue  # 다른 태스크가 먼저 mark함
            await place_sell_order(
                code=code,
                name=pos["name"],
                price=current_price,
                quantity=pos["quantity"],
                position_id=position_id,
                reason=reason,
                buy_price=buy_price,
            )

    # 가상 시뮬레이션 체크
    await _check_simulations(current_price_data)


async def cancel_all_pending_orders():
    """KIS 미체결 주문 전체 취소 + DB pending 정리"""
    from daemon.position_db import invalidate_cache, delete_position
    token = await _ensure_mock_token()
    if not token:
        return
    cano, acnt_cd = _parse_account()

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


# 보유일별 익절 기준 / 장 마감 보유 기준 (매수가 대비 %, 누적)
# base_tp는 사용자 설정값 (기본 7%), 나머지는 base_tp 기준 오프셋
_TP_OFFSETS = [0, 3, 8, 13, 18]      # D+0: +0, D+1: +3, D+2: +8, D+3: +13, D+4+: +18
_CARRY_THRESHOLDS = [3, 5, 8, 12, 15]  # D+0: 3%, D+1: 5%, D+2: 8%, D+3: 12%, D+4+: 15%


def get_tiered_tp(base_tp: float, hold_days: int) -> float:
    """보유일수 연동 익절 기준 반환"""
    idx = min(max(hold_days, 0), len(_TP_OFFSETS) - 1)
    return base_tp + _TP_OFFSETS[idx]


def get_carry_threshold(hold_days: int) -> float:
    """보유일수 연동 장 마감 보유 기준 반환"""
    idx = min(max(hold_days, 0), len(_CARRY_THRESHOLDS) - 1)
    return _CARRY_THRESHOLDS[idx]

async def sell_all_positions_market():
    """장 마감 청산 — 수익 +3% 이상은 익일 보유, 나머지 시장가 매도"""
    from daemon.position_db import invalidate_cache

    # 1) 미체결 주문 취소
    await cancel_all_pending_orders()

    # 2) 보유 포지션 분류
    positions = await get_active_positions(force_refresh=True)
    filled = [p for p in positions if p["status"] in ("filled", "sell_requested")]
    if not filled:
        logger.info("장 마감 청산: 보유 포지션 없음")
        return

    to_sell = []
    to_carry = []

    today = datetime.now(_KST).date()

    for pos in filled:
        buy_price = pos.get("filled_price") or pos.get("order_price", 0)
        if buy_price <= 0:
            to_sell.append(pos)
            continue

        # 보유일 계산
        hold_days = _calc_hold_days(pos)

        current_price = await _get_current_price(pos["code"])
        pnl = calc_pnl_pct(buy_price, current_price) if current_price > 0 else 0
        pos["_current_price"] = current_price
        pos["_pnl"] = pnl

        # 보유일수 연동 장 마감 보유 기준 (금요일/연휴 전날은 기준 상향)
        carry_threshold = get_carry_threshold(hold_days)
        # 금요일 또는 다음 영업일까지 2일 이상 → carry 기준 1.5배
        if today.weekday() == 4:  # 금요일
            carry_threshold = carry_threshold * 1.5
        if pnl >= carry_threshold:
            to_carry.append(pos)
            pos["_hold_days"] = hold_days
            pos["_carry_threshold"] = carry_threshold
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
            d = pos.get("_hold_days", 0)
            thr = pos.get("_carry_threshold", 3)
            carry_lines.append(f"  {pos['name']}({pos['code']}) {pos['_pnl']:+.2f}% (D+{d}, 기준 +{thr}%)")
        logger.info(f"익일 보유: {len(to_carry)}종목")
        await send_telegram(
            f"<b>📌 익일 보유 ({len(to_carry)}종목)</b>\n"
            f"보유일별 기준 충족 → 보유 유지\n\n"
            + "\n".join(carry_lines)
        )

    # 매도 대상
    if not to_sell:
        logger.info("장 마감 청산: 매도 대상 없음 (전종목 익일 보유)")
        invalidate_cache()
        return

    logger.info(f"장 마감 청산: {len(to_sell)}종목 매도, {len(to_carry)}종목 익일 보유")
    failed_positions = []
    for pos in to_sell:
        position_id = pos["id"]
        if is_selling(position_id):
            continue
        mark_selling(position_id)
        buy_price = pos.get("filled_price") or pos.get("order_price", 0)
        current_price = pos.get("_current_price") or await _get_current_price(pos["code"])
        try:
            result = await _kis_order_market("VTTC0801U", pos["code"], pos["quantity"])
            if result:
                filled_qty = await _verify_sell_fill(pos["code"], pos["quantity"])
                if current_price <= 0:
                    current_price = await _get_current_price(pos["code"])
                sell_price = current_price if current_price > 0 else buy_price
                pnl = calc_pnl_pct(buy_price, sell_price)
                _peak_prices.pop(position_id, None)
                if filled_qty >= pos["quantity"]:
                    await update_position_sold(position_id, sell_price, pnl, "eod_close")
                    logger.info(f"장 마감 매도: {pos['name']}({pos['code']}) {pnl:+.2f}%")
                elif filled_qty > 0:
                    await update_position_quantity(position_id, pos["quantity"] - filled_qty)
                    unmark_selling(position_id)
                    failed_positions.append(pos)
                    logger.warning(f"장 마감 부분체결: {pos['name']}({pos['code']}) {filled_qty}/{pos['quantity']}주")
                else:
                    unmark_selling(position_id)
                    failed_positions.append(pos)
                    logger.warning(f"장 마감 미체결: {pos['name']}({pos['code']})")
                await send_telegram(
                    f"<b>🔔 장 마감 청산</b>\n"
                    f"<b>{pos['name']} ({pos['code']})</b>\n"
                    f"매수가: {buy_price:,}원 → 매도가: {sell_price:,}원\n"
                    f"수익률: {pnl:+.2f}% ({filled_qty}주)"
                    + (f"\n⚠️ 부분체결 ({pos['quantity']}주 중 {filled_qty}주)" if filled_qty < pos["quantity"] else "")
                )
            else:
                unmark_selling(position_id)
                failed_positions.append(pos)
        except Exception as e:
            unmark_selling(position_id)
            _peak_prices.pop(position_id, None)
            failed_positions.append(pos)
            logger.error(f"장 마감 매도 오류: {pos['name']}({pos['code']}) {e}")
        await asyncio.sleep(0.3)
    # 실패 종목 1회 재시도
    if failed_positions:
        logger.info(f"장 마감 미체결 {len(failed_positions)}종목 재시도")
        await asyncio.sleep(3)
        for pos in failed_positions:
            position_id = pos["id"]
            if is_selling(position_id):
                continue
            try:
                remaining = (await get_active_positions(force_refresh=True))
                pos_now = next((p for p in remaining if p["id"] == position_id and p["status"] == "filled"), None)
                if not pos_now:
                    continue
                mark_selling(position_id)
                result = await _kis_order_market("VTTC0801U", pos_now["code"], pos_now["quantity"])
                if result:
                    filled_qty = await _verify_sell_fill(pos_now["code"], pos_now["quantity"])
                    retry_buy_price = pos_now.get("filled_price") or pos_now.get("order_price", 0)
                    cp = await _get_current_price(pos_now["code"])
                    sp = cp if cp > 0 else retry_buy_price
                    pnl = calc_pnl_pct(retry_buy_price, sp)
                    if filled_qty >= pos_now["quantity"]:
                        await update_position_sold(position_id, sp, pnl, "eod_close")
                        logger.info(f"장 마감 재시도 성공: {pos_now['name']}({pos_now['code']})")
                    else:
                        unmark_selling(position_id)
                        logger.warning(f"장 마감 재시도 실패: {pos_now['name']}({pos_now['code']}) 체결 {filled_qty}주")
                else:
                    unmark_selling(position_id)
            except Exception as e:
                unmark_selling(position_id)
                logger.error(f"장 마감 재시도 오류: {pos.get('name')} {e}")
    invalidate_cache()


async def schedule_sell_check():
    """30초마다 보유종목 현재가 REST API 조회 → 익절/손절/수동매도 체크 (WebSocket 백업)"""
    from daemon import main as _main
    from daemon.main import is_market_hours, is_market_day
    while not _main._shutdown:
        # 30초 대기 (shutdown 시 즉시 탈출)
        for _ in range(30):
            if _main._shutdown:
                return
            await asyncio.sleep(1)
        if not is_market_day() or not is_market_hours():
            continue
        try:
            positions = await get_active_positions(force_refresh=True)
            targets = [p for p in positions if p["status"] in ("filled", "sell_requested")]
            if not targets:
                continue
            for pos in targets:
                code = pos["code"]
                price = await _get_current_price(code)
                if price <= 0:
                    continue
                await check_positions_for_sell({"code": code, "price": price})
                await asyncio.sleep(0.3)  # API 호출 간격
        except Exception as e:
            logger.error(f"매도 폴링 체크 오류: {e}")


async def _create_simulation(trade_id: str, strategy_type: str, entry_price: int, user_id: str):
    """비선택 전략의 가상 포지션 생성"""
    from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return
    try:
        session = await get_session()
        url = f"{SUPABASE_URL}/rest/v1/strategy_simulations"
        headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}", "Content-Type": "application/json", "Prefer": "return=minimal"}
        body = {
            "trade_id": trade_id,
            "strategy_type": strategy_type,
            "entry_price": entry_price,
            "status": "open",
            "peak_price": entry_price,
            "stepped_stop_pct": -2.0,
            "user_id": user_id,
        }
        async with session.post(url, json=body, headers=headers) as resp:
            if resp.status in (200, 201):
                logger.info(f"가상 시뮬레이션 생성: {strategy_type} entry={entry_price}")
            else:
                logger.warning(f"가상 시뮬레이션 생성 실패: {resp.status}")
    except Exception as e:
        logger.warning(f"가상 시뮬레이션 생성 오류: {e}")


async def _check_simulations(current_price_data: dict):
    """open 상태의 가상 포지션 체크 → 가상 매도 조건 충족 시 업데이트"""
    from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return
    code = current_price_data.get("code", "")
    current_price = current_price_data.get("price", 0)
    if not code or current_price <= 0:
        return

    try:
        session = await get_session()
        # open 상태의 가상 포지션 중 해당 종목 조회 (trade_id로 auto_trades.code와 조인)
        url = f"{SUPABASE_URL}/rest/v1/strategy_simulations?status=eq.open&select=id,strategy_type,entry_price,peak_price,stepped_stop_pct,trade_id"
        headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return
            sims = await resp.json()

        config = await _get_trade_config()
        tp = config.get("take_profit_pct", TRADE_TAKE_PROFIT_PCT)
        sl = config.get("stop_loss_pct", TRADE_STOP_LOSS_PCT)
        ts_pct = config.get("trailing_stop_pct", TRADE_TRAILING_STOP_PCT)

        for sim in sims:
            entry_price = sim["entry_price"]
            peak_price = sim.get("peak_price", entry_price)
            sim_id = sim["id"]
            strategy = sim["strategy_type"]
            pnl = calc_pnl_pct(entry_price, current_price)

            # Update peak
            new_peak = max(peak_price, current_price)

            exit_reason = None
            exit_price = None

            if strategy == "fixed":
                # 고정 TP 전략 시뮬레이션
                hold_days = 0  # 가상은 당일 기준
                effective_tp = get_tiered_tp(tp, hold_days)
                result = should_sell(entry_price, current_price, take_profit=effective_tp, stop_loss=sl)
                if result:
                    exit_reason = result
                    exit_price = current_price
                elif pnl > 0 and new_peak > 0:
                    drop = (current_price - new_peak) / new_peak * 100
                    if drop <= ts_pct:
                        exit_reason = "trailing_stop"
                        exit_price = current_price

            elif strategy == "stepped":
                # Stepped Trailing 시뮬레이션
                if pnl <= sl:
                    exit_reason = "stop_loss"
                    exit_price = current_price
                else:
                    peak_pnl = calc_pnl_pct(entry_price, new_peak)
                    stepped_stop = calc_stepped_stop_pct(peak_pnl, ts_pct)
                    if stepped_stop > -999.0 and pnl <= stepped_stop:
                        exit_reason = "stepped_trailing"
                        exit_price = current_price

            # Update simulation record
            update_body = {"peak_price": new_peak}
            if exit_reason:
                update_body.update({
                    "status": "closed",
                    "exit_price": exit_price,
                    "exit_reason": exit_reason,
                    "pnl_pct": round(pnl, 2),
                    "exited_at": datetime.now(_KST).isoformat(),
                })

            patch_url = f"{SUPABASE_URL}/rest/v1/strategy_simulations?id=eq.{sim_id}"
            patch_headers = {**headers, "Content-Type": "application/json", "Prefer": "return=minimal"}
            async with session.patch(patch_url, json=update_body, headers=patch_headers) as resp:
                pass  # best-effort update

    except Exception as e:
        logger.warning(f"가상 시뮬레이션 체크 오류: {e}")


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


async def _kis_order_market(tr_id: str, code: str, quantity: int, retry: bool = True) -> dict | None:
    """KIS 모의투자 시장가 주문 (토큰 만료 시 1회 재시도)"""
    token = await _ensure_mock_token()
    if not token:
        return None
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/order-cash"
    cano, acnt_cd = _parse_account()
    body = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_cd,
        "PDNO": code,
        "ORD_DVSN": "01",  # 시장가
        "ORD_QTY": str(quantity),
        "ORD_UNPR": "0",
    }
    try:
        session = await get_session()
        async with session.post(url, json=body, headers=_order_headers(token, tr_id)) as resp:
            if resp.status != 200:
                logger.error(f"시장가 주문 HTTP {resp.status}: {code} {tr_id}")
                return None
            data = await resp.json()
            if data.get("rt_cd") == "0":
                return data
            msg = data.get("msg1", "")
            if retry and ("만료" in msg or "token" in msg.lower()):
                logger.warning("시장가 주문 토큰 만료 — 재발급 후 재시도")
                _reset_token()
                await asyncio.sleep(1)
                return await _kis_order_market(tr_id, code, quantity, retry=False)
            logger.error(f"시장가 주문 실패 ({code}): {msg}")
    except Exception as e:
        logger.error(f"시장가 주문 오류: {e}")
    return None
