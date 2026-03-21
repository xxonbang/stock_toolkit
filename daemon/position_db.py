"""포지션 DB — Supabase CRUD"""
import logging
import aiohttp
from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY

logger = logging.getLogger("daemon.position")


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


async def get_active_positions() -> list[dict]:
    """보유중(filled) + 주문중(pending) 포지션 조회"""
    url = f"{SUPABASE_URL}/rest/v1/auto_trades"
    params = "status=in.(pending,filled)&select=*"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{url}?{params}", headers=_headers(), timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        logger.error(f"포지션 조회 실패: {e}")
    return []


async def is_already_held_or_ordered(code: str) -> bool:
    """해당 종목이 보유중/주문중인지 확인"""
    positions = await get_active_positions()
    return any(p["code"] == code for p in positions)


async def insert_buy_order(code: str, name: str, price: int, quantity: int) -> dict | None:
    """매수 주문 기록"""
    url = f"{SUPABASE_URL}/rest/v1/auto_trades"
    body = {
        "code": code,
        "name": name,
        "side": "buy",
        "order_price": price,
        "quantity": quantity,
        "status": "pending",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=_headers(), timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 201:
                    data = await resp.json()
                    return data[0] if data else None
                else:
                    text = await resp.text()
                    logger.error(f"매수 주문 기록 실패 ({resp.status}): {text}")
    except Exception as e:
        logger.error(f"매수 주문 기록 오류: {e}")
    return None


async def update_position_filled(position_id: str, filled_price: int):
    """체결 완료 업데이트"""
    url = f"{SUPABASE_URL}/rest/v1/auto_trades?id=eq.{position_id}"
    body = {
        "status": "filled",
        "filled_price": filled_price,
        "filled_at": "now()",
    }
    try:
        async with aiohttp.ClientSession() as session:
            await session.patch(url, json=body, headers=_headers(), timeout=aiohttp.ClientTimeout(total=10))
    except Exception as e:
        logger.error(f"체결 업데이트 실패: {e}")


async def update_position_sold(position_id: str, sell_price: int, pnl_pct: float, reason: str):
    """매도 완료 업데이트"""
    url = f"{SUPABASE_URL}/rest/v1/auto_trades?id=eq.{position_id}"
    body = {
        "status": "sold",
        "pnl_pct": round(pnl_pct, 2),
        "sell_reason": reason,
        "sold_at": "now()",
    }
    try:
        async with aiohttp.ClientSession() as session:
            await session.patch(url, json=body, headers=_headers(), timeout=aiohttp.ClientTimeout(total=10))
    except Exception as e:
        logger.error(f"매도 업데이트 실패: {e}")
