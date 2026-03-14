def build_premarket_report(macro: dict, futures: dict, night_news: list) -> dict:
    return {
        "macro": {
            "us_market": macro.get("us_market", "정보 없음"),
            "dollar_index": macro.get("dollar_index", 0),
            "us_10y_yield": macro.get("us_10y_yield", 0),
            "oil_price": macro.get("oil_price", 0),
        },
        "futures": {
            "kospi200_futures": futures.get("kospi200", 0),
            "kospi200_change": futures.get("kospi200_change", 0),
            "foreign_futures_net": futures.get("foreign_net", 0),
        },
        "top_news": night_news[:5],
        "news_count": len(night_news),
    }


def calculate_market_open_prediction(report: dict) -> dict:
    score = 0
    futures_change = report.get("futures", {}).get("kospi200_change", 0)
    score += max(-2, min(2, futures_change / 0.5))
    foreign_net = report.get("futures", {}).get("foreign_futures_net", 0)
    if foreign_net > 500:
        score += 1
    elif foreign_net < -500:
        score -= 1
    us_market = report.get("macro", {}).get("us_market", "보합")
    if us_market in ("강세", "상승"):
        score += 1
    elif us_market in ("약세", "하락"):
        score -= 1
    if score >= 2:
        direction = "강세 출발"
    elif score >= 0.5:
        direction = "소폭 상승"
    elif score > -0.5:
        direction = "보합 출발"
    elif score > -2:
        direction = "소폭 하락"
    else:
        direction = "약세 출발"
    return {"direction": direction, "score": round(score, 1)}


def format_premarket_alert(report: dict) -> str:
    prediction = calculate_market_open_prediction(report)
    macro = report.get("macro", {})
    futures = report.get("futures", {})
    futures_change = futures.get("kospi200_change", 0)
    lines = [
        "<b>[장전 프리마켓]</b>",
        "━" * 20,
        f"시장 예상: <b>{prediction['direction']}</b>",
        f"코스피200 선물: {futures_change:+.2f}%",
        f"미국 시장: {macro.get('us_market', '정보 없음')}",
        f"달러인덱스: {macro.get('dollar_index', 0):.2f} | 미국채10Y: {macro.get('us_10y_yield', 0):.2f}%",
    ]
    news = report.get("top_news", [])
    if news:
        lines.append("\n<b>주요 뉴스</b>")
        for n in news[:3]:
            title = n.get("title", "") if isinstance(n, dict) else str(n)
            lines.append(f"  • {title}")
    lines.append("━" * 20)
    return "\n".join(lines)
