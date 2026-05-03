from datetime import datetime, timezone, timedelta
from daemon.market_calendar import is_kr_market_open

_KST = timezone(timedelta(hours=9))


def _kst(year: int, month: int, day: int, hour: int = 9) -> datetime:
    return datetime(year, month, day, hour, 0, 0, tzinfo=_KST)


def test_weekday_open():
    """2026-05-04 월요일 09:00 KST — 평일, 공휴일 아님 → 개장"""
    assert is_kr_market_open(_kst(2026, 5, 4)) is True


def test_saturday_closed():
    """2026-05-02 토요일 → 휴장"""
    assert is_kr_market_open(_kst(2026, 5, 2)) is False


def test_sunday_closed():
    """2026-05-03 일요일 → 휴장"""
    assert is_kr_market_open(_kst(2026, 5, 3)) is False


def test_labor_day_closed():
    """2026-05-01 근로자의 날 (holidays.KR 미수록 — 수동 추가) → 휴장"""
    assert is_kr_market_open(_kst(2026, 5, 1)) is False


def test_childrens_day_closed():
    """2026-05-05 어린이날 (holidays.KR 수록) → 휴장"""
    assert is_kr_market_open(_kst(2026, 5, 5)) is False


def test_none_uses_current_time():
    """dt=None 호출 시 예외 없이 bool 반환"""
    result = is_kr_market_open(None)
    assert isinstance(result, bool)


def test_naive_datetime():
    """timezone-naive datetime 전달 시 KST로 해석"""
    # 2026-05-04 (월) naive
    dt = datetime(2026, 5, 4, 9, 0, 0)
    assert is_kr_market_open(dt) is True
