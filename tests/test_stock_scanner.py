import pytest
from modules.stock_scanner import parse_condition, scan_stocks

SAMPLE_STOCKS = [
    {"code": "006400", "name": "삼성SDI", "signal": "적극매수", "score": 85,
     "foreign_consecutive_buy": 4, "ma_aligned": True, "short_ratio": 2.1,
     "theme": "2차전지", "theme_rank": 1},
    {"code": "005930", "name": "삼성전자", "signal": "매수", "score": 70,
     "foreign_consecutive_buy": 1, "ma_aligned": False, "short_ratio": 1.5,
     "theme": "AI반도체", "theme_rank": 2},
    {"code": "247540", "name": "에코프로비엠", "signal": "매도", "score": 45,
     "foreign_consecutive_buy": 0, "ma_aligned": False, "short_ratio": 6.2,
     "theme": "2차전지", "theme_rank": 1},
]


def test_parse_single_condition():
    cond = parse_condition("signal=적극매수")
    assert cond is not None


def test_scan_by_signal():
    result = scan_stocks(SAMPLE_STOCKS, "signal=적극매수")
    assert len(result) == 1
    assert result[0]["code"] == "006400"


def test_scan_by_multiple_conditions():
    result = scan_stocks(SAMPLE_STOCKS, "signal=적극매수 AND foreign_consecutive_buy>=3")
    assert len(result) == 1


def test_scan_by_threshold():
    result = scan_stocks(SAMPLE_STOCKS, "short_ratio<3")
    assert len(result) == 2


def test_scan_no_match():
    result = scan_stocks(SAMPLE_STOCKS, "signal=적극매수 AND short_ratio>5")
    assert len(result) == 0


def test_scan_by_boolean():
    result = scan_stocks(SAMPLE_STOCKS, "ma_aligned=true")
    assert len(result) == 1
