"""Telegram 알림 발송 — 포맷팅 + 비동기 전송"""
import logging
import aiohttp
from daemon.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger("daemon.notify")

ALERT_LABELS = {
    "surge_5": ("📈 급등 +5%", "warning"),
    "surge_10": ("🔥 급등 +10%", "danger"),
    "surge_15": ("🚀 급등 +15%", "critical"),
    "drop_3": ("📉 급락 -3%", "warning"),
    "drop_5": ("💥 급락 -5%", "danger"),
    "volume_surge": ("📊 거래량 폭증", "info"),
    "target_reached": ("🎯 목표가 도달", "success"),
    "bid_wall": ("🧱 매수벽 감지", "info"),
    "ask_wall": ("🧱 매도벽 감지", "warning"),
    "supply_reversal_buy": ("🔄 수급 매수 전환", "success"),
    "supply_reversal_sell": ("🔄 수급 매도 전환", "danger"),
}


def format_alert(alert: dict, stock_name: str = "") -> str:
    alert_type = alert["type"]
    label, _ = ALERT_LABELS.get(alert_type, (alert_type, "info"))
    code = alert["code"]
    price = alert["price"]
    name_str = f"{stock_name} " if stock_name else ""

    lines = [f"<b>[ST] {label}</b>"]
    lines.append(f"<b>{name_str}({code})</b>")
    lines.append(f"현재가: {price:,}원")

    if alert_type.startswith("surge_") or alert_type.startswith("drop_"):
        rate = alert["change_rate"]
        lines.append(f"등락률: {rate:+.1f}%")
    elif alert_type == "volume_surge":
        lines.append(f"체결량: 평균 대비 {alert['ratio']}배")
    elif alert_type == "target_reached":
        lines.append(f"목표가: {alert['target']:,.0f}원")
    elif alert_type in ("bid_wall", "ask_wall"):
        wall_type = "매수" if alert_type == "bid_wall" else "매도"
        lines.append(f"{wall_type}벽: {alert['price']:,}원 ({alert['qty']:,}주, 평균의 {alert['ratio']}배)")
    elif alert_type in ("supply_reversal_buy", "supply_reversal_sell"):
        direction = "매수 전환" if "buy" in alert_type else "매도 전환"
        lines.append(f"{direction}: 매수비율 {alert['prev_ratio']}% → {alert['bid_ratio']}% ({alert['delta']:+.1f}%p)")

    return "\n".join(lines)


async def send_telegram(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram 설정 누락 — 알림 미발송")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error(f"Telegram 발송 실패 ({resp.status}): {body}")
    except Exception as e:
        logger.error(f"Telegram 발송 오류: {e}")
