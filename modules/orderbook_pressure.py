def analyze_orderbook_pressure(stock: dict) -> dict:
    bids = stock.get("bids", [])  # list of {"price": int, "qty": int}
    asks = stock.get("asks", [])
    current_price = stock.get("current_price", 0)
    if not bids or not asks:
        return {"bid_total": 0, "ask_total": 0, "ratio": 0.0, "signal": "데이터 없음"}
    bid_total = sum(b.get("qty", 0) for b in bids)
    ask_total = sum(a.get("qty", 0) for a in asks)
    if ask_total == 0:
        ratio = 999.0
    else:
        ratio = round(bid_total / ask_total, 2)
    if ratio >= 2.0:
        signal = "강한 매수벽"
    elif ratio >= 1.3:
        signal = "매수 우위"
    elif ratio <= 0.5:
        signal = "강한 매도벽"
    elif ratio <= 0.77:
        signal = "매도 우위"
    else:
        signal = "균형"
    wall_bid = max(bids, key=lambda x: x.get("qty", 0), default={})
    wall_ask = max(asks, key=lambda x: x.get("qty", 0), default={})
    return {
        "bid_total": bid_total,
        "ask_total": ask_total,
        "ratio": ratio,
        "signal": signal,
        "largest_bid_wall": wall_bid,
        "largest_ask_wall": wall_ask,
    }


def detect_spoofing(stock: dict) -> dict:
    result = analyze_orderbook_pressure(stock)
    bids = stock.get("bids", [])
    asks = stock.get("asks", [])
    alerts = []
    for side, orders in [("매수", bids), ("매도", asks)]:
        if not orders:
            continue
        total = sum(o.get("qty", 0) for o in orders)
        if total == 0:
            continue
        for o in orders:
            share = o.get("qty", 0) / total
            if share >= 0.5:
                alerts.append(f"{side} {o.get('price', 0):,}원 집중 ({share*100:.0f}%)")
    return {"spoofing_alerts": alerts, "orderbook": result}


def format_pressure_alert(results: dict) -> str:
    ob = results.get("orderbook", results)
    lines = [
        "<b>[호가창 압력 분석]</b>",
        "━" * 20,
        f"매수잔량: {ob.get('bid_total', 0):,} | 매도잔량: {ob.get('ask_total', 0):,}",
        f"압력비율: <b>{ob.get('ratio', 0):.2f}</b> — {ob.get('signal', '')}",
    ]
    alerts = results.get("spoofing_alerts", [])
    if alerts:
        lines.append("\n<b>⚠ 집중 주문 감지</b>")
        for a in alerts:
            lines.append(f"  • {a}")
    lines.append("━" * 20)
    return "\n".join(lines)
