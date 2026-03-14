import pytest
from modules.trading_journal import match_trade_context, detect_trading_bias, calculate_trade_stats

def test_match_trade_context():
    trade = {"code": "006400", "date": "2026-03-14", "action": "buy", "price": 425000}
    signal_history = {"2026-03-14": [{"code": "006400", "signal": "적극매수", "score": 85}]}
    theme_history = {"2026-03-14": [{"name": "2차전지", "leaders": [{"code": "006400"}]}]}
    ctx = match_trade_context(trade, signal_history, theme_history)
    assert ctx["signal"] == "적극매수"
    assert ctx["theme"] == "2차전지"

def test_detect_chasing():
    trades = [{"action": "buy", "change_at_buy": 4.5}, {"action": "buy", "change_at_buy": 5.2}, {"action": "buy", "change_at_buy": 0.5}]
    biases = detect_trading_bias(trades)
    assert any(b["type"] == "추격 매수" for b in biases)

def test_detect_sector_concentration():
    trades = [{"action": "buy", "theme": "2차전지"}, {"action": "buy", "theme": "2차전지"}, {"action": "buy", "theme": "2차전지"}, {"action": "buy", "theme": "AI반도체"}]
    biases = detect_trading_bias(trades)
    assert any(b["type"] == "섹터 편중" for b in biases)

def test_calculate_trade_stats():
    trades = [{"return_pct": 5.0}, {"return_pct": -2.0}, {"return_pct": 3.0}]
    stats = calculate_trade_stats(trades)
    assert stats["total"] == 3
    assert stats["win_rate"] == round(2/3*100, 1)
