import pytest
from modules.news_impact import classify_news_type, calculate_impact_stats


def test_classify_news_type():
    assert classify_news_type("삼성바이오 신약 FDA 승인") == "FDA 승인"
    assert classify_news_type("대규모 수주 계약 체결") == "대규모 수주"
    assert classify_news_type("3분기 실적 서프라이즈") == "실적 서프라이즈"
    assert classify_news_type("유상증자 결정") == "유상증자"


def test_calculate_impact_stats():
    impacts = [
        {"return_d1": 4.2, "return_d3": 7.8, "return_d5": 9.1},
        {"return_d1": 2.1, "return_d3": 5.3, "return_d5": 6.2},
        {"return_d1": -1.5, "return_d3": 3.2, "return_d5": 4.0},
    ]
    stats = calculate_impact_stats(impacts)
    assert stats["count"] == 3
    assert abs(stats["avg_d1"] - 1.6) < 0.1
    assert stats["positive_rate_d5"] == 100.0
