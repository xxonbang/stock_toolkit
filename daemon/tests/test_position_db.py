import pytest
from daemon.position_db import calc_quantity, calc_pnl_pct


def test_calc_quantity():
    assert calc_quantity(10_000_000, 68500) == 145


def test_calc_quantity_zero_price():
    assert calc_quantity(10_000_000, 0) == 0


def test_calc_pnl_pct():
    result = calc_pnl_pct(68500, 70000)
    assert round(result, 2) == 2.19


def test_calc_pnl_pct_loss():
    result = calc_pnl_pct(68500, 66000)
    assert result < 0


def test_calc_pnl_pct_zero():
    assert calc_pnl_pct(0, 70000) == 0.0
