import json
from pathlib import Path


class DataLoader:
    def __init__(self, theme_path: str, signal_path: str):
        self.theme_path = Path(theme_path)
        self.signal_path = Path(signal_path)
        self._cache = {}

    def _load_json(self, path: Path) -> dict | list:
        key = str(path)
        if key not in self._cache:
            if not path.exists():
                return {}
            with open(path, "r", encoding="utf-8") as f:
                self._cache[key] = json.load(f)
        return self._cache[key]

    def clear_cache(self):
        self._cache.clear()
        self._stock_index = None

    # --- Theme Analysis ---
    def get_latest(self) -> dict:
        return self._load_json(self.theme_path / "latest.json")

    def get_themes(self) -> list:
        data = self.get_latest()
        # 구조: theme_analysis.themes 또는 직접 themes
        ta = data.get("theme_analysis", {})
        if isinstance(ta, dict) and "themes" in ta:
            return ta["themes"]
        return data.get("themes", [])

    def get_stock_history(self) -> dict:
        """종목 일봉 히스토리: stock-history.json 우선, 없으면 latest.json history 폴백"""
        separated = self.theme_path / "stock-history.json"
        if separated.exists():
            return self._load_json(separated)
        return self.get_latest().get("history", {})

    def get_theme_forecast(self) -> dict:
        return self._load_json(self.theme_path / "theme-forecast.json")

    def get_macro_indicators(self) -> dict:
        return self._load_json(self.theme_path / "macro-indicators.json")

    def get_intraday_history(self) -> dict:
        return self._load_json(self.theme_path / "intraday-history.json")

    def get_volume_profile(self) -> dict:
        return self._load_json(self.theme_path / "volume-profile.json")

    def get_theme_history(self) -> list:
        history_dir = self.theme_path / "history"
        if not history_dir.exists():
            return []
        files = sorted(history_dir.glob("*.json"))
        return [{"date": f.stem, "data": self._load_json(f)} for f in files]

    # --- Signal Analysis ---
    def get_vision_signals(self) -> list:
        data = self._load_json(self.signal_path / "vision" / "vision_analysis.json")
        return data.get("stocks", [])

    def get_kis_signals(self) -> list:
        data = self._load_json(self.signal_path / "kis" / "kis_analysis.json")
        return data.get("stocks", [])

    def get_combined_signals(self) -> list:
        data = self._load_json(self.signal_path / "combined" / "combined_analysis.json")
        return data.get("stocks", [])

    def get_fear_greed(self) -> dict:
        return self._load_json(self.signal_path / "kis" / "fear_greed.json")

    def get_vix(self) -> dict:
        return self._load_json(self.signal_path / "kis" / "vix.json")

    def get_market_status(self) -> dict:
        return self._load_json(self.signal_path / "kis" / "market_status.json")

    def get_signal_history(self, source: str = "vision") -> list:
        history_dir = self.signal_path / source / "history"
        if not history_dir.exists():
            return []
        files = sorted(history_dir.glob("*.json"))
        return [{"date": f.stem, "data": self._load_json(f)} for f in files]

    def get_simulation(self, category: str = "combined_strong_buy") -> dict:
        return self._load_json(self.signal_path / "simulation" / f"{category}.json")

    # --- KIS Gemini ---
    def get_kis_gemini(self) -> dict:
        return self._load_json(self.signal_path / "kis" / "kis_gemini.json")

    def get_kis_analysis(self) -> list:
        data = self._load_json(self.signal_path / "kis" / "kis_analysis.json")
        return data.get("results", [])

    # --- Theme 추가 데이터 ---
    def get_investor_intraday(self) -> dict:
        return self._load_json(self.theme_path / "investor-intraday.json")

    def get_indicator_history(self) -> dict:
        return self._load_json(self.theme_path / "indicator-history.json")

    def get_paper_trading_latest(self) -> dict:
        pt_dir = self.theme_path / "paper-trading"
        if not pt_dir.exists():
            return {}
        files = sorted(pt_dir.glob("*.json"))
        return self._load_json(files[-1]) if files else {}

    def get_forecast_history(self, count: int = 3) -> list:
        fh_dir = self.theme_path / "forecast-history"
        if not fh_dir.exists():
            return []
        files = sorted(fh_dir.glob("*.json"))
        return [self._load_json(f) for f in files[-count:]]

    # --- 통합 조회 ---
    def get_macro(self) -> dict:
        return {
            "fear_greed": self.get_fear_greed(),
            "vix": self.get_vix(),
            "market_status": self.get_market_status(),
            "indicators": self.get_macro_indicators(),
        }

    _stock_index: dict[str, dict] | None = None

    def _build_stock_index(self) -> dict[str, dict]:
        """코드 → 종목 데이터 인덱스 구축 (O(1) 조회용)"""
        index: dict[str, dict] = {}
        latest = self.get_latest()
        for key in ["rising_stocks", "falling_stocks", "volume_top", "trading_value_top"]:
            for stock in latest.get(key, []):
                code = stock.get("code")
                if code:
                    if code not in index:
                        index[code] = {"code": code}
                    index[code].update(stock)
        for theme in self.get_themes():
            for leader in theme.get("leaders", []):
                code = leader.get("code")
                if code:
                    if code not in index:
                        index[code] = {"code": code}
                    index[code].update(leader)
                    index[code]["theme"] = theme.get("name")
                    index[code]["theme_rank"] = theme.get("rank")
                    index[code]["is_leader"] = True
        for signal in self.get_combined_signals():
            code = signal.get("code")
            if code:
                if code not in index:
                    index[code] = {"code": code}
                index[code]["signal"] = signal
        return index

    def get_stock(self, code: str) -> dict | None:
        """종목 코드로 데이터 조회 (인덱스 기반 O(1))"""
        if self._stock_index is None:
            self._stock_index = self._build_stock_index()
        return self._stock_index.get(code)
