import pytest
from modules.smart_money import calculate_smart_money_score, detect_accumulation_pattern, classify_flow_pattern


def test_calculate_smart_money_score():
    stock = {"foreign_consecutive_buy": 5, "institution_consecutive_buy": 3, "net_buy_ratio": 0.02, "accumulation_match": 0.8, "program_ratio": 0.1}
    score = calculate_smart_money_score(stock)
    assert 0 <= score <= 100


def test_detect_accumulation_pattern():
    history = [
        {"date": "2026-03-10", "foreign_net": 120, "price_change": 0.3},
        {"date": "2026-03-11", "foreign_net": 180, "price_change": 0.5},
        {"date": "2026-03-12", "foreign_net": 250, "price_change": 0.2},
        {"date": "2026-03-13", "foreign_net": 150, "price_change": 0.4},
        {"date": "2026-03-14", "foreign_net": 150, "price_change": 0.3},
    ]
    result = detect_accumulation_pattern(history, min_days=5)
    assert result["pattern"] == "조용한 매집"
    assert result["consecutive_days"] == 5


def test_classify_flow_pattern_rapid():
    history = [
        {"date": "2026-03-13", "foreign_net": 50, "price_change": 0.5},
        {"date": "2026-03-14", "foreign_net": 800, "price_change": 5.2},
    ]
    result = classify_flow_pattern(history)
    assert result == "급속 유입"


def test_classify_flow_pattern_dual_exit():
    history = [{"date": "2026-03-14", "foreign_net": -200, "institution_net": -150, "price_change": -2.1}]
    result = classify_flow_pattern(history)
    assert result == "쌍방 이탈"
