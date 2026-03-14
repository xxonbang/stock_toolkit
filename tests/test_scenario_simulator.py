import pytest
from modules.scenario_simulator import parse_strategy, simulate_strategy, compare_strategies

SAMPLE_HISTORY = [
    {"date": "2026-03-10", "stocks": [
        {"code": "006400", "signal": "적극매수", "score": 85,
         "foreign_consecutive_buy": 3, "ma_aligned": True,
         "price_d0": 400000, "price_d1": 408000, "price_d3": 415000, "price_d5": 420000},
        {"code": "005930", "signal": "매수", "score": 70,
         "foreign_consecutive_buy": 1, "ma_aligned": False,
         "price_d0": 70000, "price_d1": 69500, "price_d3": 71000, "price_d5": 72000},
    ]},
]


def test_parse_strategy():
    s = parse_strategy("signal=적극매수 hold=5 stop=-5")
    assert s["filters"] == "signal=적극매수"
    assert s["hold_days"] == 5
    assert s["stop_loss"] == -5.0


def test_simulate_strategy():
    s = parse_strategy("signal=적극매수 hold=5")
    result = simulate_strategy(SAMPLE_HISTORY, s)
    assert result["total_trades"] == 1
    assert result["win_rate"] > 0


def test_compare_strategies():
    s1 = parse_strategy("signal=적극매수 hold=5")
    s2 = parse_strategy("signal=매수 hold=5")
    comparison = compare_strategies(SAMPLE_HISTORY, [s1, s2])
    assert len(comparison) == 2
