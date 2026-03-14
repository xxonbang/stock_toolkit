import pytest
from modules.risk_monitor import evaluate_risk, detect_concentration

def test_evaluate_risk_high():
    stock = {"code": "247540", "name": "에코프로비엠", "signal_prev": "매수", "signal_now": "매도", "foreign_consecutive_sell": 4, "below_ma20": True, "short_ratio": 6.2}
    result = evaluate_risk(stock)
    assert result["level"] == "높음"
    assert len(result["warnings"]) >= 2

def test_evaluate_risk_low():
    stock = {"code": "006400", "name": "삼성SDI", "signal_prev": "적극매수", "signal_now": "적극매수", "foreign_consecutive_sell": 0, "below_ma20": False, "short_ratio": 1.2}
    result = evaluate_risk(stock)
    assert result["level"] == "낮음"
    assert len(result["warnings"]) == 0

def test_detect_concentration():
    portfolio = [
        {"code": "006400", "theme": "2차전지", "weight": 0.3},
        {"code": "373220", "theme": "2차전지", "weight": 0.25},
        {"code": "247540", "theme": "2차전지", "weight": 0.2},
        {"code": "005930", "theme": "AI반도체", "weight": 0.25},
    ]
    warnings = detect_concentration(portfolio, threshold=0.5)
    assert len(warnings) == 1
    assert warnings[0]["theme"] == "2차전지"
    assert warnings[0]["total_weight"] == 0.75
