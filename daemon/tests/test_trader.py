import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from daemon.trader import filter_high_confidence, should_sell


def test_filter_high_confidence():
    signals = [
        {"code": "005930", "name": "삼성전자", "vision_signal": "매수", "api_signal": "매수", "theme": "반도체", "theme_rank": 1},
        {"code": "000660", "name": "SK하이닉스", "vision_signal": "매수", "api_signal": "중립", "theme": "반도체", "theme_rank": 2},
        {"code": "047040", "name": "대우건설", "vision_signal": "적극매수", "api_signal": "매수", "theme": "건설", "theme_rank": 1},
    ]
    result = filter_high_confidence(signals)
    codes = [r["code"] for r in result]
    assert "005930" in codes
    assert "000660" not in codes
    assert "047040" in codes


def test_filter_high_confidence_or_mode():
    signals = [
        {"code": "005930", "vision_signal": "매수", "api_signal": "매수"},
        {"code": "000660", "vision_signal": "매수", "api_signal": "중립"},
        {"code": "047040", "vision_signal": "중립", "api_signal": "적극매수"},
        {"code": "999999", "vision_signal": "중립", "api_signal": "중립"},
    ]
    result = filter_high_confidence(signals, mode="or")
    codes = [r["code"] for r in result]
    assert "005930" in codes  # 둘 다 매수 → 통과
    assert "000660" in codes  # vision만 매수 → OR이므로 통과
    assert "047040" in codes  # api만 적극매수 → OR이므로 통과
    assert "999999" not in codes  # 둘 다 중립 → 탈락


def test_filter_high_confidence_leader_mode():
    signals = [
        {"code": "005930", "vision_signal": "매수", "api_signal": "매수", "theme": "반도체"},
        {"code": "000660", "vision_signal": "중립", "api_signal": "중립", "theme": "반도체"},
        {"code": "999999", "vision_signal": "매수", "api_signal": "매수"},  # 대장주 아님 (theme 없음)
    ]
    result = filter_high_confidence(signals, mode="leader")
    assert len(result) == 2  # 대장주(theme 있는)만 통과, 시그널 무관
    assert all(s.get("theme") for s in result)


def test_filter_high_confidence_empty():
    assert filter_high_confidence([]) == []
    assert filter_high_confidence(None) == []


def test_should_sell_take_profit():
    reason = should_sell(buy_price=68500, current_price=70555, take_profit=3.0, stop_loss=-3.0)
    assert reason == "take_profit"  # +3.0%


def test_should_sell_stop_loss():
    reason = should_sell(buy_price=68500, current_price=66445, take_profit=3.0, stop_loss=-3.0)
    assert reason == "stop_loss"


def test_should_sell_hold():
    reason = should_sell(buy_price=68500, current_price=69870, take_profit=3.0, stop_loss=-3.0)
    assert reason is None  # +2.0% → 아직 +3% 미달, 홀드


# ─── sell_all_positions_force: KIS 잔고 verify 로직 테스트 ───────────────────

def _make_pos(code="005930", name="삼성전자", qty=137, status="filled"):
    return {
        "id": "pos-001",
        "code": code,
        "name": name,
        "quantity": qty,
        "status": status,
        "filled_price": 10000,
        "order_price": 10000,
    }


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _force_mocks(bal, qty, order_result=None, verify_result=None):
    """sell_all_positions_force 테스트용 공통 mock context 반환."""
    from contextlib import ExitStack
    stack = ExitStack()
    m = {}
    m["cancel"]   = stack.enter_context(patch("daemon.trader.cancel_all_pending_orders", new_callable=AsyncMock))
    m["positions"]= stack.enter_context(patch("daemon.trader.get_active_positions", new_callable=AsyncMock))
    m["bal"]      = stack.enter_context(patch("daemon.trader._check_balance_qty", new_callable=AsyncMock))
    m["price"]    = stack.enter_context(patch("daemon.trader._get_current_price", new_callable=AsyncMock))
    m["order"]    = stack.enter_context(patch("daemon.trader._kis_order_market", new_callable=AsyncMock))
    m["verify"]   = stack.enter_context(patch("daemon.trader._verify_sell_fill", new_callable=AsyncMock))
    m["actual"]   = stack.enter_context(patch("daemon.trader._get_actual_fill_price", new_callable=AsyncMock))
    m["upd_sold"] = stack.enter_context(patch("daemon.trader.update_position_sold", new_callable=AsyncMock))
    m["telegram"] = stack.enter_context(patch("daemon.trader.send_telegram", new_callable=AsyncMock))
    m["is_sell"]  = stack.enter_context(patch("daemon.trader.is_selling", return_value=False))
    m["mark"]     = stack.enter_context(patch("daemon.trader.mark_selling"))
    m["unmark"]   = stack.enter_context(patch("daemon.trader.unmark_selling"))
    stack.enter_context(patch("daemon.position_db.invalidate_cache"))

    pos = _make_pos(qty=qty)
    m["positions"].return_value = [pos]
    m["bal"].return_value = bal
    m["price"].return_value = 11000
    m["order"].return_value = order_result or {"rt_cd": "0"}
    m["verify"].return_value = verify_result if verify_result is not None else bal
    m["actual"].return_value = 11000
    return stack, m


def test_sell_force_kis_qty_used_when_mismatch():
    """DB qty=137, KIS bal=68 불일치 → 68주로 주문해야 함."""
    from daemon.trader import sell_all_positions_force
    stack, m = _force_mocks(bal=68, qty=137)
    with stack:
        _run(sell_all_positions_force())
        called_qty = m["order"].call_args[0][2]
        assert called_qty == 68, f"주문 수량이 68이어야 하는데 {called_qty}임"


def test_sell_force_db_qty_used_when_match():
    """DB qty=100, KIS bal=100 일치 → 100주로 주문해야 함."""
    from daemon.trader import sell_all_positions_force
    stack, m = _force_mocks(bal=100, qty=100)
    with stack:
        _run(sell_all_positions_force())
        called_qty = m["order"].call_args[0][2]
        assert called_qty == 100


def test_sell_force_skip_when_bal_zero():
    """KIS bal=0 → 주문 없이 already-sold 처리해야 함."""
    from daemon.trader import sell_all_positions_force
    stack, m = _force_mocks(bal=0, qty=137)
    with stack:
        _run(sell_all_positions_force())
        m["order"].assert_not_called()
        m["upd_sold"].assert_called_once()
