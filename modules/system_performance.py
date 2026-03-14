from statistics import mean, stdev


def calculate_hit_rate(signals: list, target_signal: str = "적극매수") -> dict:
    filtered = [s for s in signals if s.get("signal") == target_signal]
    if not filtered:
        return {"total": 0, "wins": 0, "rate": 0.0}
    wins = sum(1 for s in filtered if s.get("return_d5", 0) > 0)
    return {
        "total": len(filtered),
        "wins": wins,
        "rate": round(wins / len(filtered) * 100, 1),
    }


def calculate_avg_return(returns: list) -> dict:
    if not returns:
        return {"mean": 0, "max": 0, "min": 0, "stdev": 0}
    return {
        "mean": round(mean(returns), 2),
        "max": round(max(returns), 2),
        "min": round(min(returns), 2),
        "stdev": round(stdev(returns), 2) if len(returns) > 1 else 0,
    }


def classify_market_regime(fear_greed: float, above_ma20: bool) -> str:
    if above_ma20 and fear_greed > 50:
        return "상승장"
    elif not above_ma20 and fear_greed < 40:
        return "하락장"
    return "횡보장"


def analyze_performance_by_source(history: list) -> dict:
    sources = {}
    for item in history:
        src = item.get("source", "unknown")
        if src not in sources:
            sources[src] = []
        sources[src].append(item)
    result = {}
    for src, items in sources.items():
        returns = [i.get("return_d5", 0) for i in items]
        result[src] = {
            "total": len(items),
            "hit_rate": calculate_hit_rate(items),
            "returns": calculate_avg_return(returns),
        }
    return result


def build_performance_report(data_loader) -> dict:
    report = {"by_source": {}, "current_regime": ""}
    for category in ["vision_strong_buy", "kis_strong_buy", "combined_strong_buy"]:
        sim = data_loader.get_simulation(category)
        if sim:
            source = category.split("_")[0]
            returns = []
            for date_data in sim.get("dates", sim.get("results", [])):
                for stock in date_data.get("stocks", []):
                    ret = stock.get("return_pct", stock.get("return", 0))
                    returns.append(ret)
            if returns:
                report["by_source"][source] = calculate_avg_return(returns)
    macro = data_loader.get_macro()
    fg = macro.get("fear_greed", {}).get("score", 50)
    ms = macro.get("market_status", {})
    above_ma20 = ms.get("kospi_above_ma20", True)
    report["current_regime"] = classify_market_regime(fg, above_ma20)
    return report
