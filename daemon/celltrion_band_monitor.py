"""셀트리온 횡보 매매 가상 시뮬레이션 — 실시간 모니터링

실거래 X. strategy_simulations(celltrion_band) + auto_trades(sim_only) DB row만 생성.
정규장(09:00~15:30 KST, 개장일)에만 동작.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
from daemon.http_session import get_session

logger = logging.getLogger("daemon.celltrion")

STOCK_CODE = "068270"
STOCK_NAME = "셀트리온"
BUY_PRICE = 199_000
SELL_PRICE = 205_000
SIM_START_CAPITAL = 10_000_000
STRATEGY_TYPE = "celltrion_band"

KST = timezone(timedelta(hours=9))


def _headers() -> dict:
    return {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


async def _supabase_get(path: str) -> list | None:
    """Supabase GET 요청"""
    session = await get_session()
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    try:
        async with session.get(url, headers=_headers()) as resp:
            if resp.status == 200:
                return await resp.json()
            text = await resp.text()
            logger.warning(f"Supabase GET {path} {resp.status}: {text}")
            return None
    except Exception as e:
        logger.error(f"Supabase GET {path} 오류: {e}")
        return None


async def _supabase_post(path: str, body: dict) -> dict | None:
    """Supabase POST 요청 (insert)"""
    session = await get_session()
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    try:
        async with session.post(url, headers=_headers(), json=body) as resp:
            if resp.status in (200, 201):
                result = await resp.json()
                if isinstance(result, list) and result:
                    return result[0]
                return result
            text = await resp.text()
            logger.warning(f"Supabase POST {path} {resp.status}: {text}")
            return None
    except Exception as e:
        logger.error(f"Supabase POST {path} 오류: {e}")
        return None


async def _supabase_patch(path: str, body: dict) -> None:
    """Supabase PATCH 요청 (update)"""
    session = await get_session()
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    try:
        async with session.patch(url, headers=_headers(), json=body) as resp:
            if resp.status not in (200, 204):
                text = await resp.text()
                logger.warning(f"Supabase PATCH {path} {resp.status}: {text}")
    except Exception as e:
        logger.error(f"Supabase PATCH {path} 오류: {e}")


def _is_market_hours_now() -> bool:
    """현재 정규장 시간인지 (09:00~15:30 KST, 개장일)"""
    from daemon.market_calendar import is_kr_market_open
    now = datetime.now(KST)
    if not is_kr_market_open(now):
        return False
    h, m = now.hour, now.minute
    if h < 9:
        return False
    if h > 15 or (h == 15 and m > 30):
        return False
    return True


async def _calc_current_cap() -> int:
    """closed 사이클 손익 누적 → 현재 운용 자본 계산.

    각 closed sim의 (exit_price - entry_price) * qty 를 누적.
    qty는 auto_trades.quantity에서 조회.
    """
    closed_sims = await _supabase_get(
        f"strategy_simulations?strategy_type=eq.{STRATEGY_TYPE}&status=eq.closed"
        f"&select=id,trade_id,entry_price,exit_price&order=created_at.asc"
    )
    if not closed_sims:
        return SIM_START_CAPITAL

    cap = SIM_START_CAPITAL
    for sim in closed_sims:
        trade_id = sim.get("trade_id")
        entry_price = sim.get("entry_price") or 0
        exit_price = sim.get("exit_price") or 0
        if not trade_id:
            continue
        trades = await _supabase_get(
            f"auto_trades?id=eq.{trade_id}&select=quantity"
        )
        if not trades:
            continue
        qty = trades[0].get("quantity") or 0
        profit = qty * (exit_price - entry_price)
        cap += profit

    return cap


async def _get_open_sim() -> dict | None:
    """현재 보유 중인 open sim 조회 (celltrion_band)"""
    sims = await _supabase_get(
        f"strategy_simulations?strategy_type=eq.{STRATEGY_TYPE}&status=eq.open"
        f"&select=id,trade_id,entry_price&order=created_at.desc&limit=1"
    )
    if sims:
        return sims[0]
    return None


async def _do_buy(current_price: int) -> None:
    """매수 처리: auto_trades(sim_only) + strategy_simulations(open) insert"""
    cap = await _calc_current_cap()
    new_qty = cap // BUY_PRICE
    if new_qty <= 0:
        logger.warning(f"셀트리온 매수 스킵 — cap={cap:,} qty=0")
        return

    now_iso = datetime.now(KST).isoformat()
    trade = await _supabase_post("auto_trades", {
        "code": STOCK_CODE,
        "name": STOCK_NAME,
        "side": "buy",
        "order_price": BUY_PRICE,
        "filled_price": BUY_PRICE,
        "quantity": new_qty,
        "status": "sim_only",
        "sell_reason": STRATEGY_TYPE,
        "created_at": now_iso,
        "filled_at": now_iso,
    })
    if not trade:
        logger.error("셀트리온 auto_trades insert 실패")
        return

    trade_id = trade.get("id")
    sim = await _supabase_post("strategy_simulations", {
        "trade_id": trade_id,
        "strategy_type": STRATEGY_TYPE,
        "status": "open",
        "entry_price": BUY_PRICE,
        "created_at": now_iso,
    })
    if not sim:
        logger.error(f"셀트리온 strategy_simulations insert 실패 (trade_id={trade_id})")
        return

    logger.info(
        f"[셀트리온 시뮬] 매수 — 가격={current_price:,} qty={new_qty} cap={cap:,}"
    )
    try:
        from daemon.notifier import send_telegram
        await send_telegram(
            f"[셀트리온 시뮬] 가상 매수\n"
            f"가격: {BUY_PRICE:,}원 / {new_qty}주 / 운용자본: {cap:,}원"
        )
    except Exception as e:
        logger.warning(f"셀트리온 매수 알림 실패: {e}")


async def _do_sell(sim: dict, current_price: int) -> None:
    """매도 처리: auto_trades(sell_price/sold_at) + strategy_simulations(closed) update.

    auto_trades.status는 sim_only 유지 (격리 룰).
    """
    sim_id = sim["id"]
    trade_id = sim["trade_id"]
    entry_price = sim.get("entry_price") or BUY_PRICE
    pnl_pct = round((SELL_PRICE - entry_price) / entry_price * 100, 2)
    now_iso = datetime.now(KST).isoformat()

    await _supabase_patch(f"auto_trades?id=eq.{trade_id}", {
        "sell_price": SELL_PRICE,
        "sold_at": now_iso,
        # status는 sim_only 유지
    })
    await _supabase_patch(f"strategy_simulations?id=eq.{sim_id}", {
        "status": "closed",
        "exit_price": SELL_PRICE,
        "exited_at": now_iso,
        "pnl_pct": pnl_pct,
    })

    logger.info(
        f"[셀트리온 시뮬] 매도 — 가격={current_price:,} pnl={pnl_pct}%"
    )
    try:
        from daemon.notifier import send_telegram
        await send_telegram(
            f"[셀트리온 시뮬] 가상 매도\n"
            f"가격: {SELL_PRICE:,}원 / pnl: +{pnl_pct}%"
        )
    except Exception as e:
        logger.warning(f"셀트리온 매도 알림 실패: {e}")


async def check_celltrion_signal(current_price: int) -> None:
    """실시간 셀트리온 시세가 들어올 때마다 호출.

    1) 정규장 가드 (is_kr_market_open + 09:00~15:30 KST)
    2) 보유 상태 조회 (strategy_simulations status=open AND strategy_type=celltrion_band)
    3) 미보유 + 가격<=199,000 → 매수 row insert
    4) 보유 + 가격>=205,000 → 매도 처리
    """
    if not _is_market_hours_now():
        return

    open_sim = await _get_open_sim()
    is_held = open_sim is not None

    if not is_held and current_price <= BUY_PRICE:
        await _do_buy(current_price)
    elif is_held and current_price >= SELL_PRICE:
        await _do_sell(open_sim, current_price)
