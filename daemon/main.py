"""WebSocket 알림 데몬 — 엔트리포인트"""
import asyncio
import logging
import signal
from datetime import datetime, timezone, timedelta
from daemon.config import (
    ALERT_SURGE_LEVELS, ALERT_DROP_LEVELS,
    ALERT_VOLUME_RATIO, ALERT_COOLDOWN_SEC,
    ALERT_WALL_RATIO, ALERT_SUPPLY_REVERSAL_THRESHOLD,
)
from daemon.ws_client import KISWebSocketClient
from daemon.alert_rules import AlertEngine
from daemon.notifier import format_alert, send_telegram, telegram_worker
from daemon.stock_manager import fetch_subscription_codes, fetch_trade_codes, get_stock_name
from daemon.trader import check_positions_for_sell, run_buy_process, sell_all_positions_market, schedule_sell_check, cancel_all_pending_orders
from daemon.github_monitor import check_workflow_completion
from daemon.http_session import close_session

_DB_REFRESH_INTERVAL = 600  # seconds (10분)
_GITHUB_CHECK_INTERVAL = 300  # seconds (5분)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("daemon.main")

alert_engine = AlertEngine(
    surge_levels=ALERT_SURGE_LEVELS,
    drop_levels=ALERT_DROP_LEVELS,
    volume_ratio=ALERT_VOLUME_RATIO,
    cooldown_sec=ALERT_COOLDOWN_SEC,
    wall_ratio=ALERT_WALL_RATIO,
    supply_reversal_threshold=ALERT_SUPPLY_REVERSAL_THRESHOLD,
)
ws_client: KISWebSocketClient | None = None
_shutdown = False  # 종료 신호
_buy_running = False  # run_buy_process 중복 실행 방지

# 구독 종목 용도별 분리
_alert_codes: set[str] = set()  # 알림용 (cross_signal + portfolio)
_trade_codes: set[str] = set()  # 모의투자용 (auto_trades filled)

KST = timezone(timedelta(hours=9))

# 한국 공휴일 (고정 공휴일 + 연도별 음력 공휴일)
_KR_FIXED_HOLIDAYS = {"01-01", "03-01", "05-05", "06-06", "08-15", "10-03", "10-09", "12-25"}
_KR_LUNAR_HOLIDAYS = {
    2026: {"01-28", "01-29", "01-30", "05-24", "09-24", "09-25", "09-26"},  # 설날, 부처님오신날, 추석
    2027: {"02-16", "02-17", "02-18", "05-13", "10-13", "10-14", "10-15"},
}

def _get_holidays(year: int) -> set[str]:
    return _KR_FIXED_HOLIDAYS | _KR_LUNAR_HOLIDAYS.get(year, set())


def is_market_day() -> bool:
    """오늘이 장 운영일인지 (주말/공휴일 제외)"""
    now = datetime.now(KST)
    if now.weekday() >= 5:  # 토(5), 일(6)
        return False
    if now.strftime("%m-%d") in _get_holidays(now.year):
        return False
    return True


def is_market_hours() -> bool:
    """현재 장중 시간인지 (09:00 ~ 15:30 KST)"""
    now = datetime.now(KST)
    h, m = now.hour, now.minute
    if h < 9:
        return False
    if h > 15 or (h == 15 and m > 30):
        return False
    return True


async def on_execution(data: dict):
    """체결 데이터 수신 콜백 — 용도별 분기 처리"""
    if not is_market_hours():
        return
    code = data.get("code", "")

    # 알림용 종목 → 급등/급락/거래량 알림
    if code in _alert_codes:
        alerts = alert_engine.check(data, tick_volume=data.get("tick_volume"))
        for alert in alerts:
            name = get_stock_name(alert["code"])
            msg = format_alert(alert, stock_name=name)
            logger.info(f"알림 발송: {alert['type']} {alert['code']}")
            await send_telegram(msg)

    # 모의투자 보유 종목 → 익절/손절/trailing stop 체크
    if code in _trade_codes:
        await check_positions_for_sell(data)


async def on_asking_price(data: dict):
    """호가 데이터 수신 콜백 — 알림용 종목만 호가 벽/수급 반전 검사"""
    code = data.get("code", "")
    if code not in _alert_codes:
        return
    alerts = alert_engine.check_asking_price(data)
    for alert in alerts:
        name = get_stock_name(alert["code"])
        msg = format_alert(alert, stock_name=name)
        logger.info(f"알림 발송: {alert['type']} {alert['code']}")
        await send_telegram(msg)


async def refresh_subscriptions():
    """구독 종목 갱신 — 알림용 + 모의투자용 분리 관리"""
    global _alert_codes, _trade_codes
    if not ws_client:
        return

    new_alert = await fetch_subscription_codes()
    new_trade = await fetch_trade_codes()

    _alert_codes = new_alert
    _trade_codes = new_trade

    # 모의투자 보유 종목 우선 확보, 나머지 슬롯을 알림용으로 배분
    combined = set(new_trade)  # 보유 종목 우선
    remaining_slots = 20 - len(combined)
    if remaining_slots > 0:
        for code in new_alert:
            if code not in combined:
                combined.add(code)
                if len(combined) >= 20:
                    break

    if combined:
        await ws_client.update_subscriptions(combined)
    logger.info(f"구독 갱신: 알림 {len(new_alert)}종목, 모의투자 {len(new_trade)}종목, 실구독 {len(combined)}종목")


async def schedule_refresh():
    """10분마다 구독 종목 갱신 (장 운영일만)"""
    while not _shutdown:
        await asyncio.sleep(_DB_REFRESH_INTERVAL)
        if _shutdown or not is_market_day():
            continue
        try:
            await refresh_subscriptions()
            # heartbeat: 보유종목 요약
            from daemon.position_db import get_active_positions, calc_pnl_pct
            positions = await get_active_positions(force_refresh=True)
            held = [p for p in positions if p["status"] in ("filled", "sell_requested")]
            if held:
                summary = ", ".join(f"{p.get('name','')}({p.get('code','')})" for p in held[:5])
                logger.info(f"[heartbeat] 보유 {len(held)}종목: {summary}")
            elif is_market_hours():
                logger.info("[heartbeat] 보유종목 없음")
        except Exception as e:
            logger.error(f"구독 갱신 실패: {e}")


_last_workflow_time: str | None = None
_first_trade_check_done: bool = False  # 데몬 시작 후 첫 체크 시 현재 워크플로우 시각만 기록


async def trigger_subscription_refresh():
    """매수/매도 후 구독 즉시 갱신 (외부에서 호출 가능)"""
    try:
        await refresh_subscriptions()
    except Exception as e:
        logger.error(f"구독 즉시 갱신 실패: {e}")


async def schedule_auto_trade():
    """5분마다 theme-analysis 워크플로우 완료 확인 → 매수 프로세스 (장중만)"""
    global _last_workflow_time, _buy_running, _first_trade_check_done
    while not _shutdown:
        await asyncio.sleep(_GITHUB_CHECK_INTERVAL)
        if _shutdown or not is_market_day() or not is_market_hours():
            continue
        # 09:05 이전 매수 차단 — 개장 직후 고변동성 시간대 회피
        now_hm = datetime.now(KST)
        if now_hm.hour == 9 and now_hm.minute < 5:
            continue
        if _buy_running:
            continue
        try:
            completed, new_time = await check_workflow_completion(_last_workflow_time)
            if completed:
                _last_workflow_time = new_time
                # 데몬 시작 후 첫 체크: 현재 시각만 기록하고 매수 실행 안 함 (오래된 워크플로우 방지)
                if not _first_trade_check_done:
                    _first_trade_check_done = True
                    logger.info(f"데몬 시작 후 첫 체크 — 워크플로우 시각 기록: {new_time}")
                    continue
                _buy_running = True
                logger.info("theme-analysis 완료 감지 — 매수 프로세스 시작")
                try:
                    await run_buy_process()
                finally:
                    _buy_running = False
        except Exception as e:
            logger.error(f"자동매매 루프 오류: {e}")


async def schedule_eod_close():
    """15:15~15:20 사이에 보유 전 포지션 시장가 매도 (당일 청산)"""
    _eod_done_date: str = ""  # 당일 실행 완료 여부
    while not _shutdown:
        await asyncio.sleep(30)
        if _shutdown or not is_market_day():
            continue
        now = datetime.now(KST)
        today = now.strftime("%Y-%m-%d")
        if _eod_done_date == today:
            continue  # 오늘 이미 실행됨
        # 15:15~15:20 윈도우 (5분 폭, 30초 폴링으로 놓칠 확률 거의 0)
        if now.hour == 15 and 15 <= now.minute <= 20:
            logger.info("15:15 장 마감 청산 시작")
            try:
                await sell_all_positions_market()
            except Exception as e:
                logger.error(f"장 마감 청산 오류: {e}")
            _eod_done_date = today


async def main():
    global ws_client, _alert_codes, _trade_codes

    from daemon.config import validate_required_env
    validate_required_env()

    logger.info("WebSocket 알림 데몬 시작")

    # startup cleanup: stale pending 정리 + peak 초기화
    try:
        await cancel_all_pending_orders()
        logger.info("시작 시 pending 주문 정리 완료")
    except Exception as e:
        logger.warning(f"시작 시 pending 정리 실패: {e}")
    try:
        from daemon.trader import _peak_prices, _get_current_price
        from daemon.position_db import get_active_positions as _get_positions
        positions = await _get_positions(force_refresh=True)
        for pos in positions:
            if pos["status"] == "filled":
                price = await _get_current_price(pos["code"])
                if price > 0:
                    _peak_prices[pos["id"]] = price
        if _peak_prices:
            logger.info(f"시작 시 peak 초기화: {len(_peak_prices)}종목")
    except Exception as e:
        logger.warning(f"시작 시 peak 초기화 실패: {e}")

    # sell_requested 종목을 filled로 복구 (이전 세션 미처리 수동 매도 → schedule_sell_check가 재처리)
    try:
        from daemon.position_db import get_active_positions as _get_pos2, _supabase_request
        from daemon.config import SUPABASE_URL as _SU
        sr_positions = [p for p in await _get_pos2(force_refresh=True) if p["status"] == "sell_requested"]
        for p in sr_positions:
            url = f"{_SU}/rest/v1/auto_trades?id=eq.{p['id']}"
            await _supabase_request("PATCH", url, json={"status": "filled"})
            logger.info(f"sell_requested → filled 복구: {p.get('name')}({p.get('code')})")
    except Exception as e:
        logger.warning(f"sell_requested 복구 실패: {e}")

    _alert_codes = await fetch_subscription_codes()
    _trade_codes = await fetch_trade_codes()

    # 모의투자 보유 종목 우선, 나머지 슬롯을 알림용으로
    initial_codes = set(_trade_codes)
    remaining = 20 - len(initial_codes)
    if remaining > 0:
        for code in _alert_codes:
            if code not in initial_codes:
                initial_codes.add(code)
                if len(initial_codes) >= 20:
                    break

    logger.info(f"초기 구독: 알림 {len(_alert_codes)}종목, 모의투자 {len(_trade_codes)}종목, 실구독 {len(initial_codes)}종목")

    ws_client = KISWebSocketClient(on_execution=on_execution, on_asking_price=on_asking_price)
    for code in initial_codes:
        ws_client._subscribed_codes.add(code)

    def shutdown():
        global _shutdown
        _shutdown = True
        ws_client.stop()
        tasks.cancel()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)

    tasks = asyncio.gather(
        ws_client.connect(),
        schedule_refresh(),
        schedule_auto_trade(),
        schedule_eod_close(),
        schedule_sell_check(),
        telegram_worker(),
    )
    try:
        await tasks
    except asyncio.CancelledError:
        logger.info("종료 신호 수신 — 정리 중")

    await close_session()
    logger.info("WebSocket 알림 데몬 종료")


if __name__ == "__main__":
    asyncio.run(main())
