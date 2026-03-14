def screen_undervalued(stocks: list, criteria: dict | None = None) -> list:
    if criteria is None:
        criteria = {"per_max": 10, "pbr_max": 1.0}
    per_max = criteria.get("per_max", 10)
    pbr_max = criteria.get("pbr_max", 1.0)
    results = []
    for s in stocks:
        per = s.get("per", 999)
        pbr = s.get("pbr", 999)
        if 0 < per <= per_max and 0 < pbr <= pbr_max:
            results.append(s)
    return results


def calculate_value_score(stock: dict) -> float:
    score = 0.0
    per = stock.get("per", 999)
    if 0 < per <= 5:
        score += 30
    elif 0 < per <= 10:
        score += 20
    elif 0 < per <= 15:
        score += 10
    pbr = stock.get("pbr", 999)
    if 0 < pbr <= 0.5:
        score += 30
    elif 0 < pbr <= 1.0:
        score += 20
    elif 0 < pbr <= 1.5:
        score += 10
    roe = stock.get("roe", 0)
    score += min(roe / 20.0, 1.0) * 20
    dividend_yield = stock.get("dividend_yield", 0)
    score += min(dividend_yield / 5.0, 1.0) * 20
    return round(min(score, 100), 1)


def format_valuation_alert(results: list) -> str:
    if not results:
        return "<b>[밸류에이션] 저평가 종목 없음</b>"
    scored = sorted(results, key=calculate_value_score, reverse=True)
    lines = ["<b>[밸류에이션] 저평가 종목 스크리닝</b>", "━" * 20]
    for s in scored[:5]:
        score = calculate_value_score(s)
        lines.append(
            f"\n<b>{s.get('name', '')} ({s.get('code', '')})</b>\n"
            f"  PER: {s.get('per', 0):.1f} | PBR: {s.get('pbr', 0):.2f} | ROE: {s.get('roe', 0):.1f}%\n"
            f"  밸류 스코어: {score}/100"
        )
    lines.append("━" * 20)
    return "\n".join(lines)
