from collections import defaultdict


def detect_volume_spike(stock: dict, threshold: float = 5.0) -> dict | None:
    current = stock.get("current_volume", 0)
    avg = stock.get("avg_volume_20d", 0)
    if avg <= 0 or current <= 0:
        return None
    ratio = round(current / avg, 1)
    if ratio >= threshold:
        return {"type": "volume_spike", "code": stock["code"], "name": stock.get("name", ""), "ratio": ratio, "current_volume": current, "avg_volume": avg}
    return None


def detect_simultaneous_surge(stocks: list, min_count: int = 3, min_change: float = 2.0) -> list:
    theme_stocks = defaultdict(list)
    for s in stocks:
        theme = s.get("theme")
        if theme and s.get("change_rate", 0) >= min_change:
            theme_stocks[theme].append(s)
    results = []
    for theme, group in theme_stocks.items():
        if len(group) >= min_count:
            results.append({"type": "simultaneous_surge", "theme": theme, "count": len(group), "stocks": group, "avg_change": round(sum(s["change_rate"] for s in group) / len(group), 1)})
    return results


def detect_gap(stock: dict, threshold: float = 5.0) -> dict | None:
    open_p = stock.get("open_price", 0)
    prev_close = stock.get("prev_close", 0)
    if prev_close <= 0 or open_p <= 0:
        return None
    gap_pct = round((open_p - prev_close) / prev_close * 100, 1)
    if abs(gap_pct) >= threshold:
        return {"type": "gap", "code": stock["code"], "name": stock.get("name", ""), "gap_pct": gap_pct}
    return None


def detect_price_spike(stock: dict, threshold: float = 3.0) -> dict | None:
    change = stock.get("change_rate_5min", 0)
    if abs(change) >= threshold:
        return {"type": "price_spike", "code": stock["code"], "name": stock.get("name", ""), "change_rate": change}
    return None


def run_anomaly_scan(stocks: list) -> list:
    anomalies = []
    for s in stocks:
        for detector in [detect_volume_spike, detect_gap, detect_price_spike]:
            result = detector(s)
            if result:
                anomalies.append(result)
    surges = detect_simultaneous_surge(stocks)
    anomalies.extend(surges)
    return anomalies


def format_anomaly_alert(anomaly: dict) -> str:
    t = anomaly["type"]
    if t == "volume_spike":
        return f"<b>[이상 거래] 거래량 폭발</b>\n{anomaly['name']} ({anomaly['code']})\n거래량: 20일 평균의 {anomaly['ratio']}배"
    elif t == "simultaneous_surge":
        names = ", ".join(s["name"] for s in anomaly["stocks"][:5])
        return f"<b>[이상 거래] 동시 급등 — {anomaly['theme']}</b>\n{anomaly['count']}종목 평균 +{anomaly['avg_change']}%\n종목: {names}"
    elif t == "gap":
        direction = "갭업" if anomaly["gap_pct"] > 0 else "갭다운"
        return f"<b>[이상 거래] {direction}</b>\n{anomaly['name']} ({anomaly['code']})\n갭: {anomaly['gap_pct']:+.1f}%"
    elif t == "price_spike":
        return f"<b>[이상 거래] 가격 급변</b>\n{anomaly['name']} ({anomaly['code']})\n5분 변동: {anomaly['change_rate']:+.1f}%"
    return str(anomaly)
