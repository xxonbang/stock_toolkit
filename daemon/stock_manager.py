"""구독 종목 관리 — GitHub Pages JSON 폴링 + Supabase 알림 설정"""
import logging
from daemon.config import DATA_BASE_URL, SUPABASE_URL, SUPABASE_SECRET_KEY
from daemon.http_session import get_session

logger = logging.getLogger("daemon.stocks")

stock_names: dict[str, str] = {}


def parse_cross_signal_codes(data: list | None, limit: int = 20) -> set[str]:
    if not data:
        return set()
    codes = set()
    for item in data[:limit]:
        code = item.get("code")
        if code:
            codes.add(code)
            name = item.get("name", "")
            if name:
                stock_names[code] = name
    return codes


def parse_portfolio_codes(data: list | None) -> set[str]:
    if not data:
        return set()
    codes = set()
    for item in data:
        code = item.get("code")
        if code:
            codes.add(code)
            name = item.get("name", "")
            if name:
                stock_names[code] = name
    return codes


async def fetch_json(url: str) -> list | dict | None:
    try:
        session = await get_session()
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.json(content_type=None)
    except Exception as e:
        logger.warning(f"JSON fetch 실패 ({url}): {e}")
    return None


async def fetch_alert_config() -> dict:
    """Supabase alert_config에서 전체 설정 조회"""
    defaults = {"alert_mode": "all", "take_profit_pct": 3.0, "stop_loss_pct": -3.0}
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return defaults
    try:
        session = await get_session()
        url = f"{SUPABASE_URL}/rest/v1/alert_config?select=alert_mode,take_profit_pct,stop_loss_pct&limit=1"
        headers = {
            "apikey": SUPABASE_SECRET_KEY,
            "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        }
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                rows = await resp.json()
                if rows and isinstance(rows, list):
                    row = rows[0]
                    return {
                        "alert_mode": row.get("alert_mode") or "all",
                        "take_profit_pct": float(row.get("take_profit_pct") or 3.0),
                        "stop_loss_pct": float(row.get("stop_loss_pct") or -3.0),
                    }
    except Exception as e:
        logger.warning(f"설정 조회 실패: {e}")
    return defaults


async def fetch_alert_mode() -> str:
    config = await fetch_alert_config()
    return config["alert_mode"]
    return "all"


async def fetch_subscription_codes(manual_codes: set[str] | None = None) -> set[str]:
    codes: set[str] = set()

    alert_mode = await fetch_alert_mode()

    # 전체 OFF → 구독 없음
    if alert_mode == "off":
        logger.info("알림 전체 OFF — 구독 종목 없음")
        return codes

    # 교차 신호 종목 (alert_mode가 'all'일 때만)
    if alert_mode == "all":
        cross_data = await fetch_json(f"{DATA_BASE_URL}/cross_signal.json")
        if isinstance(cross_data, list):
            codes |= parse_cross_signal_codes(cross_data, limit=20)

    # 포트폴리오 종목 (all, portfolio_only 모두 포함)
    portfolio_data = await fetch_json(f"{DATA_BASE_URL}/portfolio.json")
    if isinstance(portfolio_data, dict):
        holdings = portfolio_data.get("holdings", [])
        codes |= parse_portfolio_codes(holdings)

    if manual_codes:
        codes |= manual_codes

    if len(codes) > 20:
        codes = set(list(codes)[:20])
        logger.warning(f"구독 한도 20종목 초과 — {len(codes)}종목으로 제한 (체결가+호가 = {len(codes)*2}슬롯)")

    return codes


def get_stock_name(code: str) -> str:
    return stock_names.get(code, "")
