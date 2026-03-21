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
    """체결 데이터 수신 콜백 — 알림 규칙 검사 + 발송"""
    alerts = alert_engine.check(data, tick_volume=data.get("tick_volume"))
    for alert in alerts:
        name = get_stock_name(alert["code"])
        msg = format_alert(alert, stock_name=name)
        logger.info(f"알림 발송: {alert['type']} {alert['code']}")
        await send_telegram(msg)


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
    )

    logger.info("WebSocket 알림 데몬 종료")


if __name__ == "__main__":
    asyncio.run(main())
