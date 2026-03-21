import pytest
from daemon.ws_client import parse_stock_execution, parse_asking_price

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


# H0STASP0 호가 파싱 테스트
# 필드: 0=종목코드, 1~2=기타, 3~7=매도호가1~5, 8~12=기타, 13~17=매수호가1~5,
# 18~22=기타, 23~27=매도잔량1~5, 28~32=기타, 33~37=매수잔량1~5, ..., 43=총매도, 44=총매수
SAMPLE_ASK = "^".join(
    ["005930", "0", "0"]                        # 0~2
    + ["69000", "69100", "69200", "69300", "69400"]  # 3~7 매도호가
    + ["0"] * 5                                  # 8~12
    + ["68900", "68800", "68700", "68600", "68500"]  # 13~17 매수호가
    + ["0"] * 5                                  # 18~22
    + ["1000", "500", "300", "200", "100"]       # 23~27 매도잔량
    + ["0"] * 5                                  # 28~32
    + ["800", "15000", "400", "200", "100"]      # 33~37 매수잔량 (15000=매수벽)
    + ["0"] * 5                                  # 38~42
    + ["2100", "16500"]                          # 43=총매도, 44=총매수
)


def test_parse_asking_price_basic():
    result = parse_asking_price(SAMPLE_ASK)
    assert result["code"] == "005930"
    assert result["ask_prices"] == [69000, 69100, 69200, 69300, 69400]
    assert result["bid_prices"] == [68900, 68800, 68700, 68600, 68500]
    assert result["total_ask"] == 2100
    assert result["total_bid"] == 16500


def test_parse_asking_price_empty():
    assert parse_asking_price("") is None
    assert parse_asking_price("too^few^fields") is None
