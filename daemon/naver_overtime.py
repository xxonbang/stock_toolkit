"""네이버 polling API 시간외 단일가 시세 fetcher."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, TypedDict

import aiohttp

from daemon.market_calendar import is_kr_market_open

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))

_NAVER_URL = "https://polling.finance.naver.com/api/realtime/domestic/stock/{code}"
_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
_CACHE_TTL_SEC = 7  # 네이버 pollingInterval 권장값

# module-level cache: {code: (timestamp_sec, OvertimeQuote)}
_cache: dict[str, tuple[float, "OvertimeQuote"]] = {}


class OvertimeQuote(TypedDict):
    code: str
    price: int          # 시간외 단일가
    status: str         # "OPEN" / "CLOSE"
    traded_at: str      # ISO8601 KST
    prev_close: int     # 정규장 종가
    change: int         # 전일대비
    change_pct: float   # 등락률


def is_afterhours_kr(dt: Optional[datetime] = None) -> bool:
    """평일 KST 15:30~18:00 이면 True (시간외 단일가 시간대).

    주말/공휴일은 False.
    """
    if dt is None:
        dt = datetime.now(KST)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)

    dt_kst = dt.astimezone(KST)

    # 주말·공휴일 체크 (is_kr_market_open은 시간 무관 — 날짜만 봄)
    # 15:30 기준 datetime을 넘겨 날짜만 판단
    if not is_kr_market_open(dt_kst.replace(hour=10, minute=0, second=0, microsecond=0)):
        return False

    hhmm = dt_kst.hour * 60 + dt_kst.minute
    return 15 * 60 + 30 <= hhmm < 18 * 60


def _safe_int(val: object) -> int:
    """콤마 포함 문자열 또는 숫자를 int로 안전 변환. 실패 시 0."""
    try:
        return int(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return 0


def _safe_float(val: object) -> float:
    """문자열 또는 숫자를 float로 안전 변환. 실패 시 0.0."""
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


async def fetch_overtime_price(code: str, session=None) -> Optional[OvertimeQuote]:
    """네이버 polling으로 시간외 단일가 조회.

    - 시간외 OPEN + overPrice 유효일 때만 OvertimeQuote 반환.
    - 그 외(CLOSE, 파싱 실패, 네트워크 오류) → None.
    - 7초 미만 재호출은 in-memory cache 반환.
    - session: 외부 aiohttp.ClientSession 주입 가능 (None이면 내부 생성).
    """
    import time as _time

    now_ts = _time.monotonic()
    cached = _cache.get(code)
    if cached is not None:
        ts, quote = cached
        if now_ts - ts < _CACHE_TTL_SEC:
            return quote

    url = _NAVER_URL.format(code=code)
    headers = {"User-Agent": _USER_AGENT}

    _own_session = False
    try:
        if session is None:
            session = aiohttp.ClientSession()
            _own_session = True

        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            data = await resp.json(content_type=None)
    except Exception as e:
        logger.warning(f"네이버 시간외 조회 실패 ({code}): {e}")
        return None
    finally:
        if _own_session:
            await session.close()

    try:
        item = data["datas"][0]
        info = item.get("overMarketPriceInfo") or {}
        status = info.get("overMarketStatus", "CLOSE")
        over_price = _safe_int(info.get("overPrice", 0))

        if status != "OPEN" or over_price <= 0:
            _cache[code] = (now_ts, None)  # type: ignore[assignment]
            return None

        prev_close = _safe_int(item.get("closePrice", 0))
        change = over_price - prev_close
        change_pct = round(change / prev_close * 100, 2) if prev_close else 0.0

        quote: OvertimeQuote = {
            "code": code,
            "price": over_price,
            "status": status,
            "traded_at": datetime.now(KST).isoformat(),
            "prev_close": prev_close,
            "change": change,
            "change_pct": change_pct,
        }
        _cache[code] = (now_ts, quote)
        return quote

    except (KeyError, IndexError, TypeError) as e:
        logger.warning(f"네이버 시간외 응답 파싱 실패 ({code}): {e}")
        return None
