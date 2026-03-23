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
from daemon.stock_manager import fetch_subscription_codes, get_stock_name
from daemon.trader import check_positions_for_sell, run_buy_process, sell_all_positions_market
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
    """체결 데이터 수신 콜백 — 알림 규칙 검사 + 보유 포지션 수익률 체크"""
    if not is_market_hours():
        return  # 장 외 시간 무시
    alerts = alert_engine.check(data, tick_volume=data.get("tick_volume"))
    for alert in alerts:
        name = get_stock_name(alert["code"])
        msg = format_alert(alert, stock_name=name)
        logger.info(f"알림 발송: {alert['type']} {alert['code']}")
        await send_telegram(msg)
    # 보유 포지션 익절/손절 체크
    await check_positions_for_sell(data)


async def on_asking_price(data: dict):
    """호가 데이터 수신 콜백 — 호가 벽 + 수급 반전 검사"""
    alerts = alert_engine.check_asking_price(data)
    for alert in alerts:
        name = get_stock_name(alert["code"])
        msg = format_alert(alert, stock_name=name)
        logger.info(f"알림 발송: {alert['type']} {alert['code']}")
        await send_telegram(msg)


async def refresh_subscriptions():
    """구독 종목 갱신 (GitHub Pages 폴링)"""
    if not ws_client:
        return
    codes = await fetch_subscription_codes()
    if codes:
        await ws_client.update_subscriptions(codes)
        logger.info(f"구독 갱신 완료: {len(codes)}종목")


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
    global ws_client

    logger.info("WebSocket 알림 데몬 시작")

    codes = await fetch_subscription_codes()
    logger.info(f"초기 구독 종목: {len(codes)}개")

    ws_client = KISWebSocketClient(on_execution=on_execution, on_asking_price=on_asking_price)
    for code in codes:
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
