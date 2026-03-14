from collections import defaultdict


def diagnose_portfolio(holdings: list, signals: dict) -> dict:
    sector_weights = defaultdict(float)
    total_weight = sum(h.get("weight", 0) for h in holdings)
    for h in holdings:
        sector = h.get("sector", "기타")
        w = h.get("weight", 0) / total_weight if total_weight > 0 else 0
        sector_weights[sector] += w
    concentration_issues = [
        {"sector": s, "weight": round(w, 2)}
        for s, w in sector_weights.items() if w >= 0.4
    ]
    signal_conflicts = []
    for h in holdings:
        code = h.get("code")
        sig = signals.get(code, "")
        if sig in ("매도", "적극매도"):
            signal_conflicts.append({"code": code, "name": h.get("name", ""), "signal": sig})
    return {
        "sector_weights": dict(sector_weights),
        "concentration_issues": concentration_issues,
        "signal_conflicts": signal_conflicts,
        "total_holdings": len(holdings),
    }


def suggest_rebalancing(diagnosis: dict) -> list:
    suggestions = []
    for issue in diagnosis.get("concentration_issues", []):
        suggestions.append(f"{issue['sector']} 비중 {issue['weight']*100:.0f}% — 일부 매도 후 분산 권장")
    for conflict in diagnosis.get("signal_conflicts", []):
        suggestions.append(f"{conflict['name']} ({conflict['code']}) 신호 {conflict['signal']} — 비중 축소 검토")
    if not suggestions:
        suggestions.append("포트폴리오 균형 양호 — 현재 비중 유지")
    return suggestions


def calculate_health_score(diagnosis: dict) -> float:
    score = 100.0
    score -= len(diagnosis.get("concentration_issues", [])) * 20
    score -= len(diagnosis.get("signal_conflicts", [])) * 15
    n = diagnosis.get("total_holdings", 1)
    if n < 3:
        score -= 20
    elif n > 15:
        score -= 10
    return round(max(score, 0), 1)
