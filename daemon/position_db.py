"""포지션 DB — Supabase CRUD + 캐시 + retry"""
import logging
import time
import asyncio
from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
from daemon.http_session import get_session

logger = logging.getLogger("daemon.position")

# 포지션 캐시 (초당 수백 회 조회 방지)
_positions_cache: list[dict] = []
_cache_time: float = 0
_CACHE_TTL = 5  # 5초 캐시

# 매도 진행 중 종목 락 (중복 매도 방지)
_selling_locks: set[str] = set()


def calc_quantity(amount: int, price: int) -> int:
    if price <= 0:
        return 0
    return amount // price


def calc_pnl_pct(buy_price: int, current_price: int) -> float:
    if buy_price <= 0:
        return 0.0
    return (current_price - buy_price) / buy_price * 100


def _headers() -> dict:
    return {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


async def _supabase_request(method: str, url: str, retries: int = 2, **kwargs) -> dict | list | None:
    """Supabase 요청 + retry"""
    session = await get_session()
    for attempt in range(retries + 1):
        try:
            async with session.request(method, url, headers=_headers(), **kwargs) as resp:
                if resp.status in (200, 201):
                    return await resp.json()
                else:
                    text = await resp.text()
                    logger.warning(f"Supabase {method} {resp.status}: {text}")
                    if resp.status >= 500 and attempt < retries:
                        await asyncio.sleep(1)
                        continue
                    return None
        except Exception as e:
            logger.error(f"Supabase {method} 오류 (attempt {attempt+1}): {e}")
            if attempt < retries:
                await asyncio.sleep(1)
    return None


async def get_active_positions(force_refresh: bool = False) -> list[dict]:
    """보유중(filled) + 주문중(pending) 포지션 조회 — 5초 캐시"""
    global _positions_cache, _cache_time
    now = time.time()
    if not force_refresh and _positions_cache and (now - _cache_time) < _CACHE_TTL:
        return _positions_cache
    url = f"{SUPABASE_URL}/rest/v1/auto_trades?status=in.(pending,filled,sell_requested)&select=*"
    result = await _supabase_request("GET", url)
    if result is not None:
        _positions_cache = result
        _cache_time = now
    return _positions_cache


def invalidate_cache():
    """캐시 무효화 (매수/매도 후 즉시 갱신 필요 시)"""
    global _cache_time
    _cache_time = 0


async def is_already_held_or_ordered(code: str) -> bool:
    positions = await get_active_positions()
    return any(p["code"] == code for p in positions)


def is_selling(position_id: str) -> bool:
    """매도 진행 중 여부 (중복 매도 방지)"""
    return position_id in _selling_locks


def mark_selling(position_id: str):
    _selling_locks.add(position_id)


def unmark_selling(position_id: str):
    _selling_locks.discard(position_id)


async def insert_buy_order(code: str, name: str, price: int, quantity: int) -> dict | None:
    url = f"{SUPABASE_URL}/rest/v1/auto_trades"
    body = {"code": code, "name": name, "side": "buy", "order_price": price, "quantity": quantity, "status": "pending"}
    result = await _supabase_request("POST", url, retries=0, json=body)  # POST는 retry 안 함 (멱등성 없음)
    if result:
        invalidate_cache()
        return result[0] if isinstance(result, list) and result else result
    return None


async def update_position_filled(position_id: str, filled_price: int):
    url = f"{SUPABASE_URL}/rest/v1/auto_trades?id=eq.{position_id}"
    body = {"status": "filled", "filled_price": filled_price, "filled_at": "now()"}
    await _supabase_request("PATCH", url, json=body)
    invalidate_cache()


async def update_position_quantity(position_id: str, quantity: int):
    url = f"{SUPABASE_URL}/rest/v1/auto_trades?id=eq.{position_id}"
    await _supabase_request("PATCH", url, json={"quantity": quantity})
    invalidate_cache()


async def update_position_sold(position_id: str, sell_price: int, pnl_pct: float, reason: str):
    url = f"{SUPABASE_URL}/rest/v1/auto_trades?id=eq.{position_id}"
    body = {"status": "sold", "pnl_pct": round(pnl_pct, 2), "sell_reason": reason, "sold_at": "now()"}
    if sell_price and sell_price > 0:
        body["sell_price"] = sell_price
    result = await _supabase_request("PATCH", url, json=body)
    # sell_price 컬럼 미존재 시 재시도 (DB migration 전 호환)
    if result is None and "sell_price" in body:
        del body["sell_price"]
        await _supabase_request("PATCH", url, json=body)
    invalidate_cache()
    unmark_selling(position_id)


async def delete_position(position_id: str):
    url = f"{SUPABASE_URL}/rest/v1/auto_trades?id=eq.{position_id}"
    await _supabase_request("DELETE", url)
    invalidate_cache()
