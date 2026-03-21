import pytest
from daemon.alert_rules import AlertEngine


@pytest.fixture
def engine():
    return AlertEngine(
        surge_levels=[5.0, 10.0, 15.0],
        drop_levels=[-3.0, -5.0],
        volume_ratio=3.0,
        cooldown_sec=300,
    )


def test_surge_5pct(engine):
    alerts = engine.check({"code": "005930", "price": 105000, "change_rate": 5.5, "volume": 1000})
    types = [a["type"] for a in alerts]
    assert "surge_5" in types


def test_surge_15pct(engine):
    alerts = engine.check({"code": "005930", "price": 115000, "change_rate": 15.5, "volume": 1000})
    types = [a["type"] for a in alerts]
    assert "surge_5" in types
    assert "surge_10" in types
    assert "surge_15" in types


def test_no_surge_below_threshold(engine):
    alerts = engine.check({"code": "005930", "price": 100000, "change_rate": 3.0, "volume": 1000})
    surge_alerts = [a for a in alerts if a["type"].startswith("surge")]
    assert len(surge_alerts) == 0


def test_drop_3pct(engine):
    alerts = engine.check({"code": "005930", "price": 97000, "change_rate": -3.5, "volume": 1000})
    types = [a["type"] for a in alerts]
    assert "drop_3" in types


def test_drop_5pct(engine):
    alerts = engine.check({"code": "005930", "price": 95000, "change_rate": -5.5, "volume": 1000})
    types = [a["type"] for a in alerts]
    assert "drop_3" in types
    assert "drop_5" in types


def test_volume_surge(engine):
    for _ in range(10):
        engine.record_volume("005930", 100)
    alerts = engine.check({"code": "005930", "price": 100000, "change_rate": 0.5, "volume": 1000}, tick_volume=400)
    types = [a["type"] for a in alerts]
    assert "volume_surge" in types


def test_no_volume_surge_below_ratio(engine):
    for _ in range(10):
        engine.record_volume("005930", 100)
    alerts = engine.check({"code": "005930", "price": 100000, "change_rate": 0.5, "volume": 1000}, tick_volume=200)
    volume_alerts = [a for a in alerts if a["type"] == "volume_surge"]
    assert len(volume_alerts) == 0


def test_cooldown_prevents_duplicate(engine):
    alerts1 = engine.check({"code": "005930", "price": 105000, "change_rate": 5.5, "volume": 1000})
    assert len(alerts1) > 0
    alerts2 = engine.check({"code": "005930", "price": 106000, "change_rate": 6.0, "volume": 1000})
    surge5 = [a for a in alerts2 if a["type"] == "surge_5"]
    assert len(surge5) == 0


def test_target_price_reached(engine):
    engine.set_target("005930", 70000)
    alerts = engine.check({"code": "005930", "price": 70500, "change_rate": 2.0, "volume": 1000})
    types = [a["type"] for a in alerts]
    assert "target_reached" in types


def test_target_price_not_reached(engine):
    engine.set_target("005930", 70000)
    alerts = engine.check({"code": "005930", "price": 69000, "change_rate": 1.0, "volume": 1000})
    target_alerts = [a for a in alerts if a["type"] == "target_reached"]
    assert len(target_alerts) == 0
