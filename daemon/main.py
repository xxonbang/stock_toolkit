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
from daemon.trader import check_positions_for_sell, run_buy_process, sell_all_positions_market, schedule_sell_check
from daemon.github_monitor import check_workflow_completion
from daemon.http_session import close_session

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

# 한국 공휴일 (2026년 기준, 매년 초 업데이트 필요)
KR_HOLIDAYS_2026 = {
    "01-01", "01-28", "01-29", "01-30",  # 신정, 설날 연휴
    "03-01",                              # 삼일절
    "05-05", "05-24",                     # 어린이날, 부처님오신날
    "06-06",                              # 현충일
    "08-15",                              # 광복절
    "09-24", "09-25", "09-26",            # 추석 연휴
    "10-03", "10-09",                     # 개천절, 한글날
    "12-25",                              # 크리스마스
}


def is_market_day() -> bool:
    """오늘이 장 운영일인지 (주말/공휴일 제외)"""
    now = datetime.now(KST)
    if now.weekday() >= 5:  # 토(5), 일(6)
        return False
    if now.strftime("%m-%d") in KR_HOLIDAYS_2026:
        return False
    return True


def is_market_hours() -> bool:
    """현재 장중 시간인지 (08:30 ~ 16:00 KST, 장 마감 후 동시호가까지 포함)"""
    now = datetime.now(KST)
    h, m = now.hour, now.minute
    if h < 8 or (h == 8 and m < 30):
        return False
    if h >= 16:
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
        await asyncio.sleep(600)
        if _shutdown or not is_market_day():
            continue
        try:
            await refresh_subscriptions()
        except Exception as e:
            logger.error(f"구독 갱신 실패: {e}")


_last_workflow_time: str | None = None


async def trigger_subscription_refresh():
    """매수/매도 후 구독 즉시 갱신 (외부에서 호출 가능)"""
    try:
        await refresh_subscriptions()
    except Exception as e:
        logger.error(f"구독 즉시 갱신 실패: {e}")


async def schedule_auto_trade():
    """5분마다 theme-analysis 워크플로우 완료 확인 → 매수 프로세스 (장중만)"""
    global _last_workflow_time, _buy_running
    while not _shutdown:
        await asyncio.sleep(300)
        if _shutdown or not is_market_day() or not is_market_hours():
            continue
        if _buy_running:
            continue  # 이전 매수 프로세스 아직 실행 중
        try:
            completed, new_time = await check_workflow_completion(_last_workflow_time)
            if completed:
                _last_workflow_time = new_time
                _buy_running = True
                logger.info("theme-analysis 완료 감지 — 매수 프로세스 시작")
                try:
                    await run_buy_process()
                finally:
                    _buy_running = False
        except Exception as e:
            logger.error(f"자동매매 루프 오류: {e}")


async def schedule_eod_close():
    """15:15에 보유 전 포지션 시장가 매도 (당일 청산)"""
    while not _shutdown:
        await asyncio.sleep(30)
        if _shutdown or not is_market_day():
            continue
        now = datetime.now(KST)
        if now.hour == 15 and now.minute == 15:
            logger.info("15:15 장 마감 청산 시작")
            try:
                await sell_all_positions_market()
            except Exception as e:
                logger.error(f"장 마감 청산 오류: {e}")
            # 다음 체크까지 10분 대기 (중복 실행 방지)
            await asyncio.sleep(600)


async def main():
    global ws_client, _alert_codes, _trade_codes

    logger.info("WebSocket 알림 데몬 시작")

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
