import pytest
from daemon.ws_client import parse_stock_execution

SAMPLE_DATA = "005930^0^153000^68500^2^500^0^68800^0.74^68200^0^250^12345678^890000000^68000^69000^68500^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0"


def test_parse_stock_execution_basic():
    result = parse_stock_execution(SAMPLE_DATA)
    assert result["code"] == "005930"
    assert result["price"] == 68500
    assert result["change_rate"] == 0.74
    assert result["tick_volume"] == 250
    assert result["volume"] == 12345678


def test_parse_stock_execution_invalid():
    result = parse_stock_execution("invalid^data")
    assert result is None


def test_parse_stock_execution_empty():
    result = parse_stock_execution("")
    assert result is None
