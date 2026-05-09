"""daemon/celltrion_band_monitor.py 단위 테스트."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

KST = timezone(timedelta(hours=9))


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _kst(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, 0, tzinfo=KST)


# ---------------------------------------------------------------------------
# _is_market_hours_now
# ---------------------------------------------------------------------------

class TestIsMarketHoursNow:
    """정규장 가드 — 날짜(개장일) + 시간(09:00~15:30) 복합 체크"""

    def test_weekday_1000_true(self):
        """평일(월) 10:00, is_kr_market_open=True → True"""
        from daemon.celltrion_band_monitor import _is_market_hours_now
        dt = _kst(2026, 5, 11, 10, 0)  # 2026-05-11 월요일
        with patch("daemon.celltrion_band_monitor.datetime") as mock_dt, \
             patch("daemon.market_calendar.is_kr_market_open", return_value=True):
            mock_dt.now.return_value = dt
            result = _is_market_hours_now()
        assert result is True

    def test_weekday_0859_false(self):
        """개장일이어도 08:59 → False"""
        from daemon.celltrion_band_monitor import _is_market_hours_now
        dt = _kst(2026, 5, 11, 8, 59)
        with patch("daemon.celltrion_band_monitor.datetime") as mock_dt, \
             patch("daemon.market_calendar.is_kr_market_open", return_value=True):
            mock_dt.now.return_value = dt
            result = _is_market_hours_now()
        assert result is False

    def test_weekday_1531_false(self):
        """개장일이어도 15:31 → False"""
        from daemon.celltrion_band_monitor import _is_market_hours_now
        dt = _kst(2026, 5, 11, 15, 31)
        with patch("daemon.celltrion_band_monitor.datetime") as mock_dt, \
             patch("daemon.market_calendar.is_kr_market_open", return_value=True):
            mock_dt.now.return_value = dt
            result = _is_market_hours_now()
        assert result is False

    def test_holiday_false(self):
        """공휴일(is_kr_market_open=False) 10:00 → False"""
        from daemon.celltrion_band_monitor import _is_market_hours_now
        dt = _kst(2026, 5, 5, 10, 0)  # 2026-05-05 어린이날
        with patch("daemon.celltrion_band_monitor.datetime") as mock_dt, \
             patch("daemon.market_calendar.is_kr_market_open", return_value=False):
            mock_dt.now.return_value = dt
            result = _is_market_hours_now()
        assert result is False


# ---------------------------------------------------------------------------
# _calc_current_cap
# ---------------------------------------------------------------------------

class TestCalcCurrentCap:
    """closed 사이클 누적 손익 → 현재 운용 자본 계산"""

    def test_no_closed_returns_start_capital(self):
        """closed 없음 → 1,000만원 그대로"""
        from daemon.celltrion_band_monitor import _calc_current_cap, SIM_START_CAPITAL
        with patch("daemon.celltrion_band_monitor._supabase_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []
            result = _run(_calc_current_cap())
        assert result == SIM_START_CAPITAL

    def test_single_closed_cycle(self):
        """closed 1건 (50주, 199k→205k = 6,000×50=300,000 이익) → 10,300,000"""
        from daemon.celltrion_band_monitor import _calc_current_cap, SIM_START_CAPITAL
        closed_sims = [
            {"id": "sim-1", "trade_id": "trade-1", "entry_price": 199_000, "exit_price": 205_000}
        ]
        trades = [{"quantity": 50}]

        async def fake_get(path: str):
            if "strategy_simulations" in path:
                return closed_sims
            if "auto_trades" in path:
                return trades
            return []

        with patch("daemon.celltrion_band_monitor._supabase_get", side_effect=fake_get):
            result = _run(_calc_current_cap())

        expected = SIM_START_CAPITAL + 50 * (205_000 - 199_000)  # 10_300_000
        assert result == expected

    def test_two_closed_cycles_accumulates(self):
        """closed 2건 누적 — cap이 계속 증가하는지 검증"""
        from daemon.celltrion_band_monitor import _calc_current_cap, SIM_START_CAPITAL
        closed_sims = [
            {"id": "sim-1", "trade_id": "trade-1", "entry_price": 199_000, "exit_price": 205_000},
            {"id": "sim-2", "trade_id": "trade-2", "entry_price": 199_000, "exit_price": 205_000},
        ]
        # qty는 각각 50, 51
        call_count = [0]

        async def fake_get(path: str):
            if "strategy_simulations" in path:
                return closed_sims
            if "auto_trades" in path:
                call_count[0] += 1
                return [{"quantity": 49 + call_count[0]}]  # 50, 51
            return []

        with patch("daemon.celltrion_band_monitor._supabase_get", side_effect=fake_get):
            result = _run(_calc_current_cap())

        profit1 = 50 * 6_000   # 300_000
        profit2 = 51 * 6_000   # 306_000
        expected = SIM_START_CAPITAL + profit1 + profit2
        assert result == expected

    def test_trade_id_none_skipped(self):
        """trade_id가 None인 sim은 손익 계산 스킵"""
        from daemon.celltrion_band_monitor import _calc_current_cap, SIM_START_CAPITAL
        closed_sims = [
            {"id": "sim-1", "trade_id": None, "entry_price": 199_000, "exit_price": 205_000}
        ]

        async def fake_get(path: str):
            if "strategy_simulations" in path:
                return closed_sims
            return []

        with patch("daemon.celltrion_band_monitor._supabase_get", side_effect=fake_get):
            result = _run(_calc_current_cap())

        assert result == SIM_START_CAPITAL  # 스킵 → 초기값 그대로


# ---------------------------------------------------------------------------
# check_celltrion_signal — 정규장 외 시간 차단
# ---------------------------------------------------------------------------

class TestCheckCelltrionSignalMarketGuard:
    """정규장 외 시간에는 매수/매도 trigger 없음"""

    def test_outside_market_hours_no_action(self):
        """정규장 외 → DB 접근 없음"""
        from daemon.celltrion_band_monitor import check_celltrion_signal
        with patch("daemon.celltrion_band_monitor._is_market_hours_now", return_value=False), \
             patch("daemon.celltrion_band_monitor._get_open_sim", new_callable=AsyncMock) as mock_sim:
            _run(check_celltrion_signal(195_000))
            mock_sim.assert_not_called()


# ---------------------------------------------------------------------------
# check_celltrion_signal — 미보유 + 가격<=199,000 → 매수
# ---------------------------------------------------------------------------

class TestCheckCelltrionSignalBuy:
    """미보유 상태에서 BUY_PRICE 이하 → 매수 trigger"""

    def test_no_holding_price_at_buy_threshold_triggers_buy(self):
        """미보유 + 가격=199,000 → _do_buy 호출"""
        from daemon.celltrion_band_monitor import check_celltrion_signal
        with patch("daemon.celltrion_band_monitor._is_market_hours_now", return_value=True), \
             patch("daemon.celltrion_band_monitor._get_open_sim", new_callable=AsyncMock, return_value=None), \
             patch("daemon.celltrion_band_monitor._do_buy", new_callable=AsyncMock) as mock_buy, \
             patch("daemon.celltrion_band_monitor._do_sell", new_callable=AsyncMock) as mock_sell:
            _run(check_celltrion_signal(199_000))
            mock_buy.assert_called_once_with(199_000)
            mock_sell.assert_not_called()

    def test_no_holding_price_below_buy_threshold_triggers_buy(self):
        """미보유 + 가격<199,000 → _do_buy 호출"""
        from daemon.celltrion_band_monitor import check_celltrion_signal
        with patch("daemon.celltrion_band_monitor._is_market_hours_now", return_value=True), \
             patch("daemon.celltrion_band_monitor._get_open_sim", new_callable=AsyncMock, return_value=None), \
             patch("daemon.celltrion_band_monitor._do_buy", new_callable=AsyncMock) as mock_buy:
            _run(check_celltrion_signal(198_000))
            mock_buy.assert_called_once_with(198_000)

    def test_no_holding_price_above_buy_threshold_no_action(self):
        """미보유 + 가격>199,000 → 아무 행동 없음"""
        from daemon.celltrion_band_monitor import check_celltrion_signal
        with patch("daemon.celltrion_band_monitor._is_market_hours_now", return_value=True), \
             patch("daemon.celltrion_band_monitor._get_open_sim", new_callable=AsyncMock, return_value=None), \
             patch("daemon.celltrion_band_monitor._do_buy", new_callable=AsyncMock) as mock_buy, \
             patch("daemon.celltrion_band_monitor._do_sell", new_callable=AsyncMock) as mock_sell:
            _run(check_celltrion_signal(200_000))
            mock_buy.assert_not_called()
            mock_sell.assert_not_called()


# ---------------------------------------------------------------------------
# check_celltrion_signal — 보유 + 가격>=205,000 → 매도
# ---------------------------------------------------------------------------

class TestCheckCelltrionSignalSell:
    """보유 상태에서 SELL_PRICE 이상 → 매도 trigger"""

    _FAKE_SIM = {"id": "sim-1", "trade_id": "trade-1", "entry_price": 199_000}

    def test_holding_price_at_sell_threshold_triggers_sell(self):
        """보유 + 가격=205,000 → _do_sell 호출"""
        from daemon.celltrion_band_monitor import check_celltrion_signal
        with patch("daemon.celltrion_band_monitor._is_market_hours_now", return_value=True), \
             patch("daemon.celltrion_band_monitor._get_open_sim", new_callable=AsyncMock, return_value=self._FAKE_SIM), \
             patch("daemon.celltrion_band_monitor._do_buy", new_callable=AsyncMock) as mock_buy, \
             patch("daemon.celltrion_band_monitor._do_sell", new_callable=AsyncMock) as mock_sell:
            _run(check_celltrion_signal(205_000))
            mock_sell.assert_called_once_with(self._FAKE_SIM, 205_000)
            mock_buy.assert_not_called()

    def test_holding_price_above_sell_threshold_triggers_sell(self):
        """보유 + 가격>205,000 → _do_sell 호출"""
        from daemon.celltrion_band_monitor import check_celltrion_signal
        with patch("daemon.celltrion_band_monitor._is_market_hours_now", return_value=True), \
             patch("daemon.celltrion_band_monitor._get_open_sim", new_callable=AsyncMock, return_value=self._FAKE_SIM), \
             patch("daemon.celltrion_band_monitor._do_sell", new_callable=AsyncMock) as mock_sell:
            _run(check_celltrion_signal(210_000))
            mock_sell.assert_called_once_with(self._FAKE_SIM, 210_000)

    def test_holding_price_below_sell_threshold_no_action(self):
        """보유 + 가격<205,000 → 아무 행동 없음"""
        from daemon.celltrion_band_monitor import check_celltrion_signal
        with patch("daemon.celltrion_band_monitor._is_market_hours_now", return_value=True), \
             patch("daemon.celltrion_band_monitor._get_open_sim", new_callable=AsyncMock, return_value=self._FAKE_SIM), \
             patch("daemon.celltrion_band_monitor._do_buy", new_callable=AsyncMock) as mock_buy, \
             patch("daemon.celltrion_band_monitor._do_sell", new_callable=AsyncMock) as mock_sell:
            _run(check_celltrion_signal(204_000))
            mock_buy.assert_not_called()
            mock_sell.assert_not_called()
