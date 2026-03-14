def calculate_surprise_score(stock: dict) -> float:
    score = 0.0
    foreign_trend = stock.get("foreign_net_7d", 0)
    if foreign_trend > 0:
        score += min(foreign_trend / 500.0, 1.0) * 30
    inst_trend = stock.get("institution_net_7d", 0)
    if inst_trend > 0:
        score += min(inst_trend / 300.0, 1.0) * 25
    vol_change = stock.get("volume_change_7d", 0)
    if vol_change > 0:
        score += min(vol_change / 50.0, 1.0) * 25
    price_change = stock.get("price_change_7d", 0)
    if price_change > 0:
        score += min(price_change / 10.0, 1.0) * 20
    return round(min(score, 100), 1)


def format_earnings_preview(stocks: list) -> str:
    if not stocks:
        return "<b>[실적 프리뷰] 주목 종목 없음</b>"
    scored = sorted(stocks, key=calculate_surprise_score, reverse=True)
    lines = ["<b>[실적 프리뷰] 서프라이즈 후보</b>", "━" * 20]
    for s in scored[:5]:
        score = calculate_surprise_score(s)
        lines.append(
            f"\n<b>{s.get('name', '')} ({s.get('code', '')})</b>\n"
            f"  외국인 7일: {s.get('foreign_net_7d', 0):+.0f}억 | 기관 7일: {s.get('institution_net_7d', 0):+.0f}억\n"
            f"  서프라이즈 스코어: {score}/100"
        )
    lines.append("━" * 20)
    return "\n".join(lines)
