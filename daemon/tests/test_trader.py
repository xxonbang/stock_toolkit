import pytest
from daemon.trader import filter_high_confidence, should_sell


def test_filter_high_confidence():
    signals = [
        {"code": "005930", "name": "삼성전자", "vision_signal": "매수", "api_signal": "매수", "theme": "반도체", "theme_rank": 1},
        {"code": "000660", "name": "SK하이닉스", "vision_signal": "매수", "api_signal": "중립", "theme": "반도체", "theme_rank": 2},
        {"code": "047040", "name": "대우건설", "vision_signal": "적극매수", "api_signal": "매수", "theme": "건설", "theme_rank": 1},
    ]
    result = filter_high_confidence(signals)
    codes = [r["code"] for r in result]
    assert "005930" in codes
    assert "000660" not in codes
    assert "047040" in codes


def test_filter_high_confidence_or_mode():
    signals = [
        {"code": "005930", "vision_signal": "매수", "api_signal": "매수"},
        {"code": "000660", "vision_signal": "매수", "api_signal": "중립"},
        {"code": "047040", "vision_signal": "중립", "api_signal": "적극매수"},
        {"code": "999999", "vision_signal": "중립", "api_signal": "중립"},
    ]
    result = filter_high_confidence(signals, mode="or")
    codes = [r["code"] for r in result]
    assert "005930" in codes  # 둘 다 매수 → 통과
    assert "000660" in codes  # vision만 매수 → OR이므로 통과
    assert "047040" in codes  # api만 적극매수 → OR이므로 통과
    assert "999999" not in codes  # 둘 다 중립 → 탈락


def test_filter_high_confidence_leader_mode():
    signals = [
        {"code": "005930", "vision_signal": "매수", "api_signal": "매수"},
        {"code": "000660", "vision_signal": "중립", "api_signal": "중립"},
    ]
    result = filter_high_confidence(signals, mode="leader")
    assert len(result) == 2  # 대장주 전체 통과, 시그널 무관


def test_filter_high_confidence_empty():
    assert filter_high_confidence([]) == []
    assert filter_high_confidence(None) == []


def test_should_sell_take_profit():
    reason = should_sell(buy_price=68500, current_price=70555, take_profit=3.0, stop_loss=-3.0)
    assert reason == "take_profit"  # +3.0%


def test_should_sell_stop_loss():
    reason = should_sell(buy_price=68500, current_price=66445, take_profit=3.0, stop_loss=-3.0)
    assert reason == "stop_loss"


def test_should_sell_hold():
    reason = should_sell(buy_price=68500, current_price=69870, take_profit=3.0, stop_loss=-3.0)
    assert reason is None  # +2.0% → 아직 +3% 미달, 홀드
