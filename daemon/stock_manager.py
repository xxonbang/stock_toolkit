"""구독 종목 관리 — GitHub Pages JSON 폴링 + Supabase 알림 설정"""
import logging
from daemon.config import DATA_BASE_URL, SUPABASE_URL, SUPABASE_SECRET_KEY, TRADE_TAKE_PROFIT_PCT, TRADE_STOP_LOSS_PCT, TRADE_TRAILING_STOP_PCT, TRADE_FLASH_SPIKE_PCT
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


_config_cache: dict | None = None  # 마지막 성공 조회값 캐시

async def fetch_alert_config() -> dict:
    """Supabase alert_config에서 전체 설정 조회. 실패 시 캐시 → 안전 defaults."""
    global _config_cache
    safe_defaults = {"alert_mode": "off", "take_profit_pct": TRADE_TAKE_PROFIT_PCT, "stop_loss_pct": TRADE_STOP_LOSS_PCT, "trailing_stop_pct": TRADE_TRAILING_STOP_PCT, "buy_signal_mode": "research_optimal", "strategy_type": "gapup", "flash_spike_pct": 15.0, "criteria_filter": False}
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return _config_cache or safe_defaults
    try:
        session = await get_session()
        url = f"{SUPABASE_URL}/rest/v1/alert_config?select=user_id,alert_mode,take_profit_pct,stop_loss_pct,trailing_stop_pct,buy_signal_mode,strategy_type,criteria_filter,emergency_sl&limit=1"
        headers = {
            "apikey": SUPABASE_SECRET_KEY,
            "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        }
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                rows = await resp.json()
                if rows and isinstance(rows, list):
                    row = rows[0]
                    result = {
                        "alert_mode": row.get("alert_mode") or "all",
                        "take_profit_pct": float(row.get("take_profit_pct") or TRADE_TAKE_PROFIT_PCT),
                        "stop_loss_pct": float(row.get("stop_loss_pct") or TRADE_STOP_LOSS_PCT),
                        "trailing_stop_pct": float(row.get("trailing_stop_pct") or TRADE_TRAILING_STOP_PCT),
                        "buy_signal_mode": row.get("buy_signal_mode") or "and",
                        "strategy_type": row.get("strategy_type") or "fixed",
                        "flash_spike_pct": TRADE_FLASH_SPIKE_PCT,
                        "criteria_filter": bool(row.get("criteria_filter", False)),
                        "emergency_sl": str(row.get("emergency_sl", "-5")),
                        "stepped_preset": "default",
                        "user_id": row.get("user_id") or "",
                    }
                    # stepped_preset 별도 조회 (컬럼 미존재 시 안전)
                    try:
                        sp_url = f"{SUPABASE_URL}/rest/v1/alert_config?select=stepped_preset&limit=1"
                        async with session.get(sp_url, headers=headers) as sp_resp:
                            if sp_resp.status == 200:
                                sp_rows = await sp_resp.json()
                                if sp_rows and sp_rows[0].get("stepped_preset"):
                                    result["stepped_preset"] = sp_rows[0]["stepped_preset"]
                    except Exception:
                        pass
                    _config_cache = result  # 성공 시 캐시 갱신
                    return result
    except Exception as e:
        logger.warning(f"설정 조회 실패: {e}")
    if _config_cache:
        logger.info("설정 조회 실패 → 캐시 사용 (마지막 성공값)")
        return _config_cache
    return safe_defaults


async def fetch_alert_mode() -> str:
    config = await fetch_alert_config()
    return config["alert_mode"]


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


async def fetch_trade_codes() -> set[str]:
    """모의투자 보유 종목 코드 조회 (auto_trades에서 filled 상태)"""
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return set()
    try:
        session = await get_session()
        url = f"{SUPABASE_URL}/rest/v1/auto_trades?status=eq.filled&select=code,name"
        headers = {
            "apikey": SUPABASE_SECRET_KEY,
            "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        }
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                rows = await resp.json()
                codes = set()
                for row in (rows or []):
                    code = row.get("code")
                    if code:
                        codes.add(code)
                        name = row.get("name", "")
                        if name:
                            stock_names[code] = name
                return codes
    except Exception as e:
        logger.warning(f"모의투자 종목 조회 실패: {e}")
    return set()


def get_stock_name(code: str) -> str:
    return stock_names.get(code, "")
