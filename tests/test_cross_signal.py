import pytest
from modules.cross_signal import find_cross_signals, format_cross_signal_alert


def test_find_cross_signals():
    themes = [{"name": "2차전지", "rank": 1, "leaders": [{"code": "006400", "name": "삼성SDI"}]}]
    signals = [
        {"code": "006400", "name": "삼성SDI", "signal": "적극매수", "score": 85},
        {"code": "005930", "name": "삼성전자", "signal": "매수", "score": 70},
    ]
    result = find_cross_signals(themes, signals)
    # UNION: 매수 시그널 2종목 + 대장주(006400 중복) = 2건
    assert len(result) == 2
    by_code = {r["code"]: r for r in result}
    assert "006400" in by_code
    assert by_code["006400"]["theme"] == "2차전지"
    assert by_code["006400"]["dual_signal"] == "Vision매수"
    assert "005930" in by_code
    assert by_code["005930"]["dual_signal"] == "Vision매수"


def test_find_cross_signals_no_match():
    themes = [{"name": "바이오", "rank": 1, "leaders": [{"code": "111111", "name": "테스트"}]}]
    signals = [{"code": "222222", "name": "다른종목", "signal": "적극매수", "score": 80}]
    result = find_cross_signals(themes, signals)
    # UNION: 매수 시그널 1건(222222) + 대장주 1건(111111) = 2건
    assert len(result) == 2
    by_code = {r["code"]: r for r in result}
    assert by_code["222222"]["dual_signal"] == "Vision매수"
    assert by_code["111111"]["dual_signal"] == "대장주"


def test_format_cross_signal_alert():
    match = {"code": "006400", "name": "삼성SDI", "theme": "2차전지", "theme_rank": 1, "signal": "적극매수", "score": 85}
    text = format_cross_signal_alert([match])
    assert "삼성SDI" in text
    assert "2차전지" in text
    assert "적극매수" in text
