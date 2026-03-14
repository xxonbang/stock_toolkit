import pytest
from modules.system_performance import (
    calculate_hit_rate, calculate_avg_return, classify_market_regime,
    analyze_performance_by_source,
)


def test_calculate_hit_rate():
    signals = [
        {"signal": "적극매수", "return_d5": 3.2},
        {"signal": "적극매수", "return_d5": -1.5},
        {"signal": "적극매수", "return_d5": 2.1},
    ]
    result = calculate_hit_rate(signals, "적극매수")
    assert result["total"] == 3
    assert result["wins"] == 2
    assert abs(result["rate"] - 66.7) < 0.1


def test_calculate_avg_return():
    returns = [3.2, -1.5, 2.1, 4.0]
    result = calculate_avg_return(returns)
    assert abs(result["mean"] - 1.95) < 0.01
    assert result["max"] == 4.0
    assert result["min"] == -1.5


def test_classify_market_regime():
    assert classify_market_regime(fear_greed=65, above_ma20=True) == "상승장"
    assert classify_market_regime(fear_greed=30, above_ma20=False) == "하락장"
    assert classify_market_regime(fear_greed=45, above_ma20=True) == "횡보장"


def test_analyze_performance_by_source():
    history = [
        {"source": "vision", "signal": "적극매수", "return_d5": 3.0, "regime": "상승장"},
        {"source": "vision", "signal": "적극매수", "return_d5": -2.0, "regime": "하락장"},
        {"source": "combined", "signal": "적극매수", "return_d5": 4.0, "regime": "상승장"},
    ]
    result = analyze_performance_by_source(history)
    assert "vision" in result
    assert "combined" in result
    assert result["vision"]["total"] == 2
