def detect_gaps(stocks: list, threshold: float = 3.0) -> list:
    gaps = []
    for s in stocks:
        open_p = s.get("open_price", 0)
        prev_close = s.get("prev_close", 0)
        if prev_close <= 0 or open_p <= 0:
            continue
        gap_pct = round((open_p - prev_close) / prev_close * 100, 2)
        if abs(gap_pct) >= threshold:
            direction = "gap_up" if gap_pct > 0 else "gap_down"
            gaps.append({
                "code": s.get("code"),
                "name": s.get("name", ""),
                "gap_pct": gap_pct,
                "direction": direction,
                "open_price": open_p,
                "prev_close": prev_close,
            })
    return sorted(gaps, key=lambda x: abs(x["gap_pct"]), reverse=True)


def calculate_gap_fill_probability(stock: dict, history: list) -> float:
    gap_pct = stock.get("gap_pct", 0)
    if not history or gap_pct == 0:
        return 0.0
    direction = "up" if gap_pct > 0 else "down"
    filled = 0
    total = 0
    for day in history:
        prev = day.get("prev_close", 0)
        high = day.get("high", 0)
        low = day.get("low", 0)
        op = day.get("open_price", 0)
        if prev <= 0 or op <= 0:
            continue
        day_gap = (op - prev) / prev * 100
        if direction == "up" and day_gap >= 3.0:
            total += 1
            if low <= prev:
                filled += 1
        elif direction == "down" and day_gap <= -3.0:
            total += 1
            if high >= prev:
                filled += 1
    if total == 0:
        return 0.5
    return round(filled / total, 2)


def format_gap_alert(gaps: list) -> str:
    if not gaps:
        return "<b>[갭 분석] 유의미한 갭 없음</b>"
    lines = ["<b>[갭 분석] 갭 발생 종목</b>", "━" * 20]
    for g in gaps[:5]:
        label = "갭업 ▲" if g["direction"] == "gap_up" else "갭다운 ▼"
        lines.append(
            f"\n{label} <b>{g['name']} ({g['code']})</b>\n"
            f"  갭: {g['gap_pct']:+.1f}% | 시가: {g['open_price']:,} / 전종가: {g['prev_close']:,}"
        )
    lines.append("━" * 20)
    return "\n".join(lines)
