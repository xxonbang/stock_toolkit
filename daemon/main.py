"""WebSocket 알림 데몬 — 엔트리포인트"""
import asyncio
import logging
import signal
from daemon.config import (
    ALERT_SURGE_LEVELS, ALERT_DROP_LEVELS,
    ALERT_VOLUME_RATIO, ALERT_COOLDOWN_SEC,
    ALERT_WALL_RATIO, ALERT_SUPPLY_REVERSAL_THRESHOLD,
)
from daemon.ws_client import KISWebSocketClient
from daemon.alert_rules import AlertEngine
from daemon.notifier import format_alert, send_telegram
from daemon.stock_manager import fetch_subscription_codes, get_stock_name
from daemon.trader import check_positions_for_sell, run_buy_process
from daemon.github_monitor import check_workflow_completion

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


async def on_execution(data: dict):
    """체결 데이터 수신 콜백 — 알림 규칙 검사 + 보유 포지션 수익률 체크"""
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
    """10분마다 구독 종목 갱신"""
    while True:
        await asyncio.sleep(600)
        try:
            await refresh_subscriptions()
        except Exception as e:
            logger.error(f"구독 갱신 실패: {e}")


_last_workflow_time: str | None = None


async def schedule_auto_trade():
    """5분마다 theme-analysis 워크플로우 완료 확인 → 매수 프로세스"""
    global _last_workflow_time
    while True:
        await asyncio.sleep(300)
        try:
            completed, new_time = await check_workflow_completion(_last_workflow_time)
            if completed:
                _last_workflow_time = new_time
                logger.info("theme-analysis 완료 감지 — 매수 프로세스 시작")
                await run_buy_process()
        except Exception as e:
            logger.error(f"자동매매 루프 오류: {e}")


async def main():
    global ws_client

    logger.info("WebSocket 알림 데몬 시작")

    codes = await fetch_subscription_codes()
    logger.info(f"초기 구독 종목: {len(codes)}개")

    ws_client = KISWebSocketClient(on_execution=on_execution, on_asking_price=on_asking_price)
    for code in codes:
        ws_client._subscribed_codes.add(code)

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, ws_client.stop)

    await asyncio.gather(
        ws_client.connect(),
        schedule_refresh(),
        schedule_auto_trade(),
    )

    logger.info("WebSocket 알림 데몬 종료")


if __name__ == "__main__":
    asyncio.run(main())
