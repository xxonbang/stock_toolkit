def detect_short_squeeze_candidates(stocks: list) -> list:
    candidates = []
    for s in stocks:
        short_ratio = s.get("short_ratio", 0)
        per = s.get("per", 999)
        if short_ratio > 5.0 and 0 < per < 20:
            candidates.append(s)
    return candidates


def calculate_squeeze_score(stock: dict) -> float:
    score = 0.0
    short_decrease = stock.get("short_ratio_change", 0)
    if short_decrease < 0:
        score += min(abs(short_decrease) / 2.0, 1.0) * 30
    vol_ratio = stock.get("volume_ratio", 1.0)
    score += min((vol_ratio - 1.0) / 4.0, 1.0) * 25
    price_bounce = stock.get("price_change_5d", 0)
    if price_bounce > 0:
        score += min(price_bounce / 10.0, 1.0) * 25
    foreign_net = stock.get("foreign_net", 0)
    if foreign_net > 0:
        score += min(foreign_net / 100.0, 1.0) * 20
    return round(min(score, 100), 1)


def format_squeeze_alert(candidates: list) -> str:
    if not candidates:
        return "<b>[공매도 역발상] 해당 종목 없음</b>"
    lines = ["<b>[공매도 역발상] 숏 스퀴즈 후보</b>", "━" * 20]
    for s in candidates[:5]:
        score = calculate_squeeze_score(s)
        lines.append(
            f"\n<b>{s.get('name', '')} ({s.get('code', '')})</b>\n"
            f"  공매도 비율: {s.get('short_ratio', 0):.1f}% | PER: {s.get('per', 0):.1f}\n"
            f"  스퀴즈 스코어: {score}/100"
        )
    lines.append("━" * 20)
    return "\n".join(lines)
