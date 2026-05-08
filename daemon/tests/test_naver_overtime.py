"""daemon/naver_overtime.py 단위 테스트."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from daemon.naver_overtime import is_afterhours_kr, fetch_overtime_price, _cache


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

KST = timezone(timedelta(hours=9))


def _kst(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, 0, tzinfo=KST)


# ---------------------------------------------------------------------------
# is_afterhours_kr
# ---------------------------------------------------------------------------

class TestIsAfterhoursKr:
    def test_weekday_16h_true(self):
        """2026-05-04 (월) 16:00 KST → 시간외 시간대"""
        assert is_afterhours_kr(_kst(2026, 5, 4, 16, 0)) is True

    def test_weekday_1530_boundary_true(self):
        """15:30 정각은 시간외 시작 → True"""
        assert is_afterhours_kr(_kst(2026, 5, 4, 15, 30)) is True

    def test_weekday_1759_true(self):
        """17:59 KST → True"""
        assert is_afterhours_kr(_kst(2026, 5, 4, 17, 59)) is True

    def test_weekday_1800_false(self):
        """18:00 KST — 범위 밖 → False"""
        assert is_afterhours_kr(_kst(2026, 5, 4, 18, 0)) is False

    def test_weekday_0900_false(self):
        """2026-05-04 (월) 09:00 KST → 정규장 시간 → False"""
        assert is_afterhours_kr(_kst(2026, 5, 4, 9, 0)) is False

    def test_weekday_1529_false(self):
        """15:29 KST — 아직 정규장 → False"""
        assert is_afterhours_kr(_kst(2026, 5, 4, 15, 29)) is False

    def test_saturday_false(self):
        """2026-05-02 (토) 16:00 KST → 주말 → False"""
        assert is_afterhours_kr(_kst(2026, 5, 2, 16, 0)) is False

    def test_sunday_false(self):
        """2026-05-03 (일) 16:00 KST → 주말 → False"""
        assert is_afterhours_kr(_kst(2026, 5, 3, 16, 0)) is False

    def test_holiday_false(self):
        """2026-05-01 (금) 근로자의 날 16:00 KST → 공휴일 → False"""
        assert is_afterhours_kr(_kst(2026, 5, 1, 16, 0)) is False


# ---------------------------------------------------------------------------
# fetch_overtime_price — network mock 기반
# ---------------------------------------------------------------------------

_SAMPLE_RESPONSE = {
    "datas": [
        {
            "closePrice": "75000",
            "overMarketPriceInfo": {
                "overMarketStatus": "OPEN",
                "overPrice": "75500",
            },
        }
    ]
}

_SAMPLE_RESPONSE_CLOSE = {
    "datas": [
        {
            "closePrice": "75000",
            "overMarketPriceInfo": {
                "overMarketStatus": "CLOSE",
                "overPrice": "75500",
            },
        }
    ]
}


def _make_mock_session(json_data: dict):
    """aiohttp.ClientSession mock — async context manager 지원."""
    mock_resp = AsyncMock()
    mock_resp.json = AsyncMock(return_value=json_data)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_resp)
    return mock_session


def test_fetch_overtime_open():
    """overMarketStatus=OPEN, overPrice 유효 → OvertimeQuote 반환"""
    _cache.clear()
    session = _make_mock_session(_SAMPLE_RESPONSE)
    result = _run(fetch_overtime_price("005930", session=session))
    assert result is not None
    assert result["price"] == 75500
    assert result["status"] == "OPEN"
    assert result["prev_close"] == 75000
    assert result["change"] == 500
    assert result["code"] == "005930"


def test_fetch_overtime_close_returns_none():
    """overMarketStatus=CLOSE → None 반환"""
    _cache.clear()
    session = _make_mock_session(_SAMPLE_RESPONSE_CLOSE)
    result = _run(fetch_overtime_price("005930", session=session))
    assert result is None


def test_fetch_overtime_cache_hit():
    """7초 이내 동일 code 재호출 → 네트워크 없이 cache 반환"""
    _cache.clear()
    session = _make_mock_session(_SAMPLE_RESPONSE)

    first = _run(fetch_overtime_price("000660", session=session))
    assert first is not None
    call_count_after_first = session.get.call_count

    # 두 번째 호출 — cache hit이므로 session.get 추가 호출 없어야 함
    second = _run(fetch_overtime_price("000660", session=session))
    assert second == first
    assert session.get.call_count == call_count_after_first


def test_fetch_overtime_network_error_returns_none():
    """네트워크 예외 → None 반환 (crash 없음)"""
    _cache.clear()
    mock_resp = AsyncMock()
    mock_resp.__aenter__ = AsyncMock(side_effect=Exception("connection refused"))
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_resp)

    result = _run(fetch_overtime_price("999999", session=mock_session))
    assert result is None
