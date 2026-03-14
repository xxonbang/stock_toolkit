import pytest
from modules.anomaly_detector import detect_volume_spike, detect_simultaneous_surge, detect_gap


def test_detect_volume_spike():
    stock = {"code": "006400", "name": "삼성SDI", "current_volume": 1500000, "avg_volume_20d": 300000}
    result = detect_volume_spike(stock, threshold=5.0)
    assert result is not None
    assert result["type"] == "volume_spike"
    assert result["ratio"] == 5.0


def test_no_volume_spike():
    stock = {"code": "006400", "name": "삼성SDI", "current_volume": 400000, "avg_volume_20d": 300000}
    result = detect_volume_spike(stock, threshold=5.0)
    assert result is None


def test_detect_simultaneous_surge():
    stocks = [
        {"code": "006400", "name": "삼성SDI", "theme": "2차전지", "change_rate": 3.2},
        {"code": "373220", "name": "LG에너지", "theme": "2차전지", "change_rate": 2.8},
        {"code": "247540", "name": "에코프로비엠", "theme": "2차전지", "change_rate": 2.5},
        {"code": "005930", "name": "삼성전자", "theme": "AI반도체", "change_rate": 0.5},
    ]
    result = detect_simultaneous_surge(stocks, min_count=3, min_change=2.0)
    assert len(result) == 1
    assert result[0]["theme"] == "2차전지"
    assert result[0]["count"] == 3


def test_detect_gap():
    stock = {"code": "006400", "name": "삼성SDI", "open_price": 440000, "prev_close": 400000}
    result = detect_gap(stock, threshold=5.0)
    assert result is not None
    assert result["gap_pct"] == 10.0
