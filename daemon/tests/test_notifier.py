import pytest
from daemon.notifier import format_alert


def test_format_surge():
    alert = {"type": "surge_5", "code": "005930", "price": 70000, "change_rate": 5.5, "level": 5.0}
    msg = format_alert(alert, stock_name="삼성전자")
    assert "삼성전자" in msg
    assert "005930" in msg
    assert "+5.5%" in msg
    assert "급등" in msg


def test_format_drop():
    alert = {"type": "drop_3", "code": "005930", "price": 65000, "change_rate": -3.2, "level": -3.0}
    msg = format_alert(alert, stock_name="삼성전자")
    assert "급락" in msg
    assert "-3.2%" in msg


def test_format_volume_surge():
    alert = {"type": "volume_surge", "code": "005930", "price": 68000, "tick_volume": 500, "avg_volume": 100.0, "ratio": 5.0}
    msg = format_alert(alert, stock_name="삼성전자")
    assert "거래량" in msg
    assert "5.0배" in msg


def test_format_target_reached():
    alert = {"type": "target_reached", "code": "005930", "price": 71000, "target": 70000}
    msg = format_alert(alert, stock_name="삼성전자")
    assert "목표가" in msg
    assert "70,000" in msg
