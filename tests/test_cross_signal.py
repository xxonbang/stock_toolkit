import pytest
from modules.cross_signal import find_cross_signals, format_cross_signal_alert


def test_find_cross_signals():
    themes = [{"name": "2차전지", "rank": 1, "leaders": [{"code": "006400", "name": "삼성SDI"}]}]
    signals = [
        {"code": "006400", "name": "삼성SDI", "signal": "적극매수", "score": 85},
        {"code": "005930", "name": "삼성전자", "signal": "매수", "score": 70},
    ]
    result = find_cross_signals(themes, signals)
    assert len(result) == 1
    assert result[0]["code"] == "006400"
    assert result[0]["theme"] == "2차전지"
    assert result[0]["signal"] == "적극매수"


def test_find_cross_signals_no_match():
    themes = [{"name": "바이오", "rank": 1, "leaders": [{"code": "111111", "name": "테스트"}]}]
    signals = [{"code": "222222", "name": "다른종목", "signal": "적극매수", "score": 80}]
    result = find_cross_signals(themes, signals)
    assert len(result) == 0


def test_format_cross_signal_alert():
    match = {"code": "006400", "name": "삼성SDI", "theme": "2차전지", "theme_rank": 1, "signal": "적극매수", "score": 85}
    text = format_cross_signal_alert([match])
    assert "삼성SDI" in text
    assert "2차전지" in text
    assert "적극매수" in text
