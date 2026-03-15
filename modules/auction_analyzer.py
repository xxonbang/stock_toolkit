def analyze_auction(stock: dict) -> dict:
    """
    stock: {"name": str, "code": str, "open_auction": {...}, "close_auction": {...}}
    open/close_auction: {"indicative_price": int, "buy_qty": int, "sell_qty": int,
                         "prev_close": int, "last_close": int}
    """
    results = {}
    for phase in ("open_auction", "close_auction"):
        auction = stock.get(phase, {})
        if not auction:
            results[phase] = None
            continue
        buy_qty = auction.get("buy_qty", 0)
        sell_qty = auction.get("sell_qty", 0)
        indicative = auction.get("indicative_price", 0)
        ref = auction.get("prev_close", 0) if phase == "open_auction" else auction.get("last_close", 0)
        ratio = round(buy_qty / sell_qty, 2) if sell_qty > 0 else 999.0
        dev_pct = round((indicative - ref) / ref * 100, 2) if ref > 0 else 0.0
        results[phase] = {
            "buy_qty": buy_qty,
            "sell_qty": sell_qty,
            "ratio": ratio,
            "indicative_price": indicative,
            "deviation_pct": dev_pct,
        }
    return results


def detect_auction_anomaly(auction_data: dict) -> list:
    anomalies = []
    for phase, data in auction_data.items():
        if not data:
            continue
        ratio = data.get("ratio", 1.0)
        dev = abs(data.get("deviation_pct", 0))
        label = "시가" if phase == "open_auction" else "종가"
        if ratio >= 3.0:
            anomalies.append(f"{label} 동시호가 매수 집중 (비율 {ratio:.1f}x)")
        elif ratio <= 0.33:
            anomalies.append(f"{label} 동시호가 매도 집중 (비율 {ratio:.1f}x)")
        if dev >= 3.0:
            anomalies.append(f"{label} 예상 체결가 이상 괴리 ({data.get('deviation_pct', 0):+.1f}%)")
    return anomalies


def format_auction_alert(anomalies: list) -> str:
    if not anomalies:
        return "<b>[동시호가 분석] 이상 없음</b>"
    lines = ["<b>[동시호가 이상 감지]</b>", "━" * 20]
    for a in anomalies:
        lines.append(f"  • {a}")
    lines.append("━" * 20)
    return "\n".join(lines)
