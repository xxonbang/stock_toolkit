def calculate_lag_pattern(history: dict) -> dict:
    """
    history: {"leader": [{"date": str, "change_pct": float}], "follower_name": [...], ...}
    Returns average lag in trading days for each follower.
    """
    leader_data = history.get("leader", [])
    lag_results = {}
    leader_up_dates = {
        d["date"] for d in leader_data if d.get("change_pct", 0) >= 3.0
    }
    for key, follower_data in history.items():
        if key == "leader":
            continue
        lags = []
        for i, day in enumerate(follower_data):
            if day.get("change_pct", 0) >= 3.0:
                for lag in range(1, 6):
                    if i >= lag:
                        candidate = follower_data[i - lag].get("date", "")
                        if candidate in leader_up_dates:
                            lags.append(lag)
                            break
        lag_results[key] = round(sum(lags) / len(lags), 1) if lags else None
    return lag_results


def predict_propagation(leader_stock: dict, theme_stocks: list, history: dict) -> list:
    """
    leader_stock: {"name": str, "change_pct": float}
    theme_stocks: [{"name": str, "code": str, "correlation": float}]
    Returns predictions sorted by propagation likelihood.
    """
    lag_map = calculate_lag_pattern(history)
    leader_move = leader_stock.get("change_pct", 0)
    predictions = []
    for stock in theme_stocks:
        name = stock.get("name", "")
        corr = stock.get("correlation", 0.5)
        lag = lag_map.get(name)
        if lag is None:
            lag = 2.0
        expected_move = round(leader_move * corr * 0.7, 2)
        probability = round(min(corr * 0.8 + (1 / (lag + 1)) * 0.2, 1.0), 2)
        predictions.append({
            "name": name,
            "code": stock.get("code", ""),
            "expected_move_pct": expected_move,
            "lag_days": lag,
            "probability": probability,
        })
    return sorted(predictions, key=lambda x: x["probability"], reverse=True)


def format_propagation_alert(predictions: list) -> str:
    if not predictions:
        return "<b>[테마 전이] 예측 데이터 없음</b>"
    lines = ["<b>[테마 전이 예측]</b>", "━" * 20]
    for p in predictions[:5]:
        lines.append(
            f"\n<b>{p['name']} ({p['code']})</b>\n"
            f"  예상 등락: {p['expected_move_pct']:+.1f}% | "
            f"지연: {p['lag_days']}일 | 확률: {p['probability']*100:.0f}%"
        )
    lines.append("━" * 20)
    return "\n".join(lines)
