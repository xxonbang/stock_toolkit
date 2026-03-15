def calculate_optimal_exit(price_history: list, volatility: float) -> dict:
    """
    price_history: [{"close": float}, ...]
    volatility: annualized volatility in percent (e.g. 30.0)
    """
    if not price_history:
        return {"stop_loss_pct": -5.0, "take_profit_pct": 10.0, "risk_reward": 2.0}
    closes = [d.get("close", 0) for d in price_history if d.get("close", 0) > 0]
    if not closes:
        return {"stop_loss_pct": -5.0, "take_profit_pct": 10.0, "risk_reward": 2.0}
    # daily volatility estimate from annualized vol
    daily_vol = volatility / (252 ** 0.5)
    stop_loss_pct = round(-max(daily_vol * 2, 2.0), 2)
    take_profit_pct = round(abs(stop_loss_pct) * 2.5, 2)
    risk_reward = round(take_profit_pct / abs(stop_loss_pct), 2)
    return {
        "entry_price": closes[-1],
        "stop_loss_pct": stop_loss_pct,
        "take_profit_pct": take_profit_pct,
        "stop_loss_price": round(closes[-1] * (1 + stop_loss_pct / 100), 0),
        "take_profit_price": round(closes[-1] * (1 + take_profit_pct / 100), 0),
        "risk_reward": risk_reward,
    }


def suggest_trailing_stop(stock: dict, atr: float) -> dict:
    """
    stock: {"current_price": float, "entry_price": float}
    atr: Average True Range value
    """
    current = stock.get("current_price", 0)
    entry = stock.get("entry_price", current)
    if current <= 0 or atr <= 0:
        return {"trailing_stop": 0, "atr_multiple": 2.0}
    atr_multiple = 2.0
    trailing_stop = round(current - atr * atr_multiple, 0)
    gain_pct = round((current - entry) / entry * 100, 2) if entry > 0 else 0.0
    if gain_pct >= 10:
        atr_multiple = 1.5
        trailing_stop = round(current - atr * atr_multiple, 0)
    return {
        "current_price": current,
        "trailing_stop": trailing_stop,
        "atr_multiple": atr_multiple,
        "gain_pct": gain_pct,
    }


def format_exit_alert(suggestions: dict) -> str:
    lines = [
        "<b>[손절/익절 최적화]</b>",
        "━" * 20,
        f"진입가: {suggestions.get('entry_price', 0):,.0f}원",
        f"손절가: <b>{suggestions.get('stop_loss_price', 0):,.0f}원</b> ({suggestions.get('stop_loss_pct', 0):.1f}%)",
        f"익절가: <b>{suggestions.get('take_profit_price', 0):,.0f}원</b> ({suggestions.get('take_profit_pct', 0):+.1f}%)",
        f"손익비: {suggestions.get('risk_reward', 0):.1f}",
        "━" * 20,
    ]
    return "\n".join(lines)
