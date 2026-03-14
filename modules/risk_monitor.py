from collections import defaultdict

def evaluate_risk(stock: dict) -> dict:
    warnings = []
    prev = stock.get("signal_prev", "")
    now = stock.get("signal_now", "")
    if prev in ("적극매수", "매수") and now in ("매도", "적극매도"):
        warnings.append(f"신호 악화: {prev} → {now}")
    sell_days = stock.get("foreign_consecutive_sell", 0)
    if sell_days >= 3:
        warnings.append(f"외국인 {sell_days}일 연속 순매도")
    if stock.get("below_ma20"):
        warnings.append("20일 이동평균선 하향 이탈")
    short = stock.get("short_ratio", 0)
    if short >= 5.0:
        warnings.append(f"공매도 비율 {short}% (경고)")
    vol_ratio = stock.get("volume_ratio", 1.0)
    if vol_ratio >= 3.0 and stock.get("change_rate", 0) < -2:
        warnings.append(f"거래량 {vol_ratio}배 + 하락 — 투매 징후")
    level = "낮음"
    if len(warnings) >= 3:
        level = "높음"
    elif len(warnings) >= 1:
        level = "주의"
    return {"code": stock.get("code"), "name": stock.get("name"), "level": level, "warnings": warnings}


def detect_concentration(portfolio: list, threshold: float = 0.5) -> list:
    theme_weights = defaultdict(float)
    for stock in portfolio:
        theme = stock.get("theme", "기타")
        theme_weights[theme] += stock.get("weight", 0)
    warnings = []
    for theme, weight in theme_weights.items():
        if weight >= threshold:
            warnings.append({"theme": theme, "total_weight": round(weight, 2), "message": f"{theme} 비중 {weight*100:.0f}% — 섹터 편중 주의"})
    return warnings


def format_risk_alert(risks: list, concentrations: list) -> str:
    lines = ["<b>[리스크 경고] 포트폴리오</b>", "━" * 20]
    level_emoji = {"높음": "🔴", "주의": "🟡", "낮음": "🟢"}
    for r in risks:
        if r["level"] == "낮음":
            continue
        emoji = level_emoji[r["level"]]
        lines.append(f"\n{emoji} <b>{r['name']} ({r['code']})</b> — {r['level']}")
        for w in r["warnings"]:
            lines.append(f"  • {w}")
    for c in concentrations:
        lines.append(f"\n⚠️ {c['message']}")
    lines.append("━" * 20)
    return "\n".join(lines)
