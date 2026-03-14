import json
import pytest
from core.data_loader import DataLoader


@pytest.fixture
def loader(tmp_path):
    theme_dir = tmp_path / "theme"
    signal_dir = tmp_path / "signal"
    theme_dir.mkdir()
    signal_dir.mkdir()
    (theme_dir / "history").mkdir()
    (signal_dir / "vision").mkdir()
    (signal_dir / "kis").mkdir()
    (signal_dir / "combined").mkdir()

    (theme_dir / "latest.json").write_text(json.dumps({
        "themes": [{"name": "2차전지", "rank": 1, "leaders": [{"code": "006400", "name": "삼성SDI"}]}],
        "rising_stocks": [{"code": "006400", "name": "삼성SDI", "change_rate": 3.2}]
    }))
    (theme_dir / "theme-forecast.json").write_text(json.dumps({
        "today": [{"theme": "2차전지", "confidence": 0.85}]
    }))
    (theme_dir / "macro-indicators.json").write_text(json.dumps({"krw_usd": 1320, "kospi": 2650}))
    (signal_dir / "vision" / "vision_analysis.json").write_text(json.dumps({
        "stocks": [{"code": "006400", "name": "삼성SDI", "signal": "적극매수", "score": 85}]
    }))
    (signal_dir / "kis" / "kis_analysis.json").write_text(json.dumps({
        "stocks": [{"code": "006400", "name": "삼성SDI", "signal": "매수", "score": 78}]
    }))
    (signal_dir / "combined" / "combined_analysis.json").write_text(json.dumps({
        "stocks": [{"code": "006400", "name": "삼성SDI", "signal": "적극매수", "score": 82}]
    }))
    (signal_dir / "kis" / "fear_greed.json").write_text(json.dumps({"score": 62, "label": "탐욕"}))
    (signal_dir / "kis" / "vix.json").write_text(json.dumps({"current": 18.5}))

    return DataLoader(str(theme_dir), str(signal_dir))


def test_load_theme_data(loader):
    data = loader.get_themes()
    assert len(data) > 0
    assert data[0]["name"] == "2차전지"


def test_load_signal_data(loader):
    vision = loader.get_vision_signals()
    assert vision[0]["signal"] == "적극매수"


def test_load_combined_signals(loader):
    combined = loader.get_combined_signals()
    assert combined[0]["code"] == "006400"


def test_load_macro(loader):
    macro = loader.get_macro()
    assert macro["fear_greed"]["score"] == 62
    assert macro["vix"]["current"] == 18.5


def test_get_stock_by_code(loader):
    stock = loader.get_stock("006400")
    assert stock is not None
    assert stock["name"] == "삼성SDI"
    assert "theme" in stock
    assert "signal" in stock
