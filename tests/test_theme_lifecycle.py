import pytest
from modules.theme_lifecycle import classify_lifecycle_stage, track_theme_lifecycle

def test_classify_birth():
    assert classify_lifecycle_stage(appeared_days=2, rank_trend="rising", volume_trend="rising", leader_change=5.0, spread_count=3) == "탄생"

def test_classify_growth():
    assert classify_lifecycle_stage(appeared_days=10, rank_trend="stable_high", volume_trend="rising", leader_change=3.0, spread_count=8) == "성장"

def test_classify_overheated():
    assert classify_lifecycle_stage(appeared_days=20, rank_trend="stable_high", volume_trend="peak", leader_change=8.0, spread_count=15) == "과열"

def test_classify_decline():
    assert classify_lifecycle_stage(appeared_days=25, rank_trend="falling", volume_trend="falling", leader_change=-3.0, spread_count=5) == "쇠퇴"

def test_track_theme_lifecycle():
    history = [{"date": f"2026-03-{10+i:02d}", "themes": [{"name": "2차전지", "rank": max(1, 3-i), "leader_change": 2.0+i, "stock_count": 3+i}]} for i in range(5)]
    result = track_theme_lifecycle("2차전지", history)
    assert result["theme"] == "2차전지"
    assert result["stage"] in ["탄생", "성장", "과열", "쇠퇴"]
    assert result["appeared_days"] == 5
