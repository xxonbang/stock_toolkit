"""한국 주식시장 휴장일 판단 헬퍼

holidays.KR()이 근로자의 날(5/1)을 미지원하므로 수동 추가.
"""
from datetime import datetime, date, timezone, timedelta
from typing import Optional

import holidays

_KST = timezone(timedelta(hours=9))

# holidays.KR()이 포함하지 않는 추가 공휴일 (월/일 고정)
# 근로자의 날 (5/1)은 법정 공휴일이나 holidays 라이브러리 미수록
_EXTRA_HOLIDAYS: list[tuple[int, int]] = [
    (5, 1),  # 근로자의 날
]


def is_kr_market_open(dt: Optional[datetime] = None) -> bool:
    """한국 주식시장 개장 여부 반환.

    Args:
        dt: 판단 기준 datetime (timezone-aware 권장). None이면 현재 KST 사용.

    Returns:
        True = 개장일 (매수/시뮬 허용)
        False = 휴장일 (토/일/공휴일/근로자의 날)
    """
    if dt is None:
        dt = datetime.now(_KST)

    # timezone-naive라면 KST로 간주
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_KST)

    d: date = dt.astimezone(_KST).date()

    # 주말 체크
    if d.weekday() >= 5:  # 5=토, 6=일
        return False

    # holidays.KR() 공휴일 체크
    kr_holidays = holidays.KR(years=d.year)
    if d in kr_holidays:
        return False

    # 추가 공휴일 체크 (근로자의 날 등 라이브러리 미수록)
    if (d.month, d.day) in _EXTRA_HOLIDAYS:
        return False

    return True
