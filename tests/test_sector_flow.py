import pytest
from modules.sector_flow import aggregate_by_sector, detect_rotation


def test_aggregate_by_sector():
    stocks = [
        {"code": "006400", "theme": "2차전지", "foreign_net": 120, "change_rate": 3.2, "trading_value": 5000},
        {"code": "373220", "theme": "2차전지", "foreign_net": 80, "change_rate": 2.1, "trading_value": 3000},
        {"code": "005930", "theme": "AI반도체", "foreign_net": -50, "change_rate": -0.5, "trading_value": 8000},
    ]
    result = aggregate_by_sector(stocks)
    assert "2차전지" in result
    assert result["2차전지"]["total_foreign_net"] == 200
    assert result["2차전지"]["stock_count"] == 2
    assert "AI반도체" in result


def test_detect_rotation():
    today = {"2차전지": {"total_foreign_net": 300}, "바이오": {"total_foreign_net": -200}}
    yesterday = {"2차전지": {"total_foreign_net": 100}, "바이오": {"total_foreign_net": 150}}
    rotations = detect_rotation(today, yesterday)
    assert len(rotations) > 0
    bio_rotation = [r for r in rotations if r["sector"] == "바이오"]
    assert len(bio_rotation) == 1
    assert bio_rotation[0]["direction"] == "유출 전환"
