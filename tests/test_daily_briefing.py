import pytest
from modules.daily_briefing import build_morning_context, build_evening_context


def test_build_morning_context():
    macro = {"fear_greed": {"score": 62}, "vix": {"current": 18.5}, "indicators": {"krw_usd": 1320}}
    forecast = {"today": [{"theme": "2차전지", "confidence": 0.85}]}
    cross_signals = [{"name": "삼성SDI", "signal": "적극매수", "theme": "2차전지"}]
    ctx = build_morning_context(macro, forecast, cross_signals)
    assert "fear_greed" in ctx
    assert "themes" in ctx
    assert "cross_signals" in ctx
    assert ctx["type"] == "morning"


def test_build_evening_context():
    macro = {"fear_greed": {"score": 62}, "vix": {"current": 18.5}, "indicators": {"kospi": 2650}}
    performance = {"by_source": {"combined": {"mean": 3.1}}}
    ctx = build_evening_context(macro, performance)
    assert "market" in ctx
    assert "performance" in ctx
    assert ctx["type"] == "evening"
