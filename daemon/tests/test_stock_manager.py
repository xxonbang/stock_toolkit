import pytest
from daemon.stock_manager import parse_cross_signal_codes, parse_portfolio_codes


def test_parse_cross_signal_codes():
    data = [
        {"code": "005930", "name": "삼성전자", "confidence": 0.8},
        {"code": "000660", "name": "SK하이닉스", "confidence": 0.6},
    ]
    codes = parse_cross_signal_codes(data, limit=20)
    assert codes == {"005930", "000660"}


def test_parse_cross_signal_empty():
    assert parse_cross_signal_codes([], limit=20) == set()
    assert parse_cross_signal_codes(None, limit=20) == set()


def test_parse_cross_signal_limit():
    data = [{"code": f"{i:06d}", "confidence": 0.5} for i in range(30)]
    codes = parse_cross_signal_codes(data, limit=10)
    assert len(codes) == 10


def test_parse_portfolio_codes():
    data = [
        {"code": "005930", "name": "삼성전자", "avg_price": 60000, "quantity": 10},
        {"code": "000660", "name": "SK하이닉스", "avg_price": 120000, "quantity": 5},
    ]
    codes = parse_portfolio_codes(data)
    assert codes == {"005930", "000660"}
