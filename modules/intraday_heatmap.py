def build_hourly_returns(intraday_data: list) -> dict:
    """
    intraday_data: [{"hour": int, "return_pct": float}, ...]
    Aggregates returns by hour across multiple days.
    """
    hour_buckets: dict = {}
    for row in intraday_data:
        hour = row.get("hour")
        ret = row.get("return_pct", 0)
        if hour is None:
            continue
        if hour not in hour_buckets:
            hour_buckets[hour] = []
        hour_buckets[hour].append(ret)
    hourly_returns = {}
    for hour, returns in hour_buckets.items():
        n = len(returns)
        avg = round(sum(returns) / n, 3)
        positive = sum(1 for r in returns if r > 0)
        hourly_returns[hour] = {
            "avg_return": avg,
            "win_rate": round(positive / n, 2) if n > 0 else 0.0,
            "sample_count": n,
        }
    return hourly_returns


def find_best_hours(hourly_returns: dict, min_samples: int = 5) -> dict:
    qualified = {
        h: v for h, v in hourly_returns.items()
        if v.get("sample_count", 0) >= min_samples
    }
    if not qualified:
        return {"best_hours": [], "worst_hours": []}
    sorted_hours = sorted(qualified.items(), key=lambda x: x[1]["avg_return"], reverse=True)
    best = [
        {"hour": h, **v} for h, v in sorted_hours if v["avg_return"] > 0
    ][:3]
    worst = [
        {"hour": h, **v} for h, v in reversed(sorted_hours) if v["avg_return"] < 0
    ][:3]
    return {"best_hours": best, "worst_hours": worst}


def format_heatmap_alert(results: dict) -> str:
    lines = ["<b>[시간대별 수익률 히트맵]</b>", "━" * 20]
    best = results.get("best_hours", [])
    worst = results.get("worst_hours", [])
    if best:
        lines.append("<b>강세 시간대</b>")
        for h in best:
            lines.append(
                f"  {h['hour']:02d}시: {h['avg_return']:+.2f}% (승률 {h['win_rate']*100:.0f}%)"
            )
    if worst:
        lines.append("<b>약세 시간대</b>")
        for h in worst:
            lines.append(
                f"  {h['hour']:02d}시: {h['avg_return']:+.2f}% (승률 {h['win_rate']*100:.0f}%)"
            )
    if not best and not worst:
        lines.append("유의미한 시간대 없음")
    lines.append("━" * 20)
    return "\n".join(lines)
