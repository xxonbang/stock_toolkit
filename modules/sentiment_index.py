def calculate_sentiment(
    fear_greed: float = 50,
    vix: float = 20,
    kospi_data: dict | None = None,
    foreign_net: float = 0,
    advance_decline_ratio: float = 1.0,
    volume_change: float = 0,
    short_balance: float = 0,
) -> float:
    score = 0.0
    score += min(fear_greed / 100.0, 1.0) * 20
    vix_norm = max(0, 1 - (vix - 10) / 40)
    score += vix_norm * 20
    if kospi_data:
        change = kospi_data.get("change_rate", 0)
        score += min(max((change + 3) / 6, 0), 1.0) * 15
    foreign_norm = min(max((foreign_net + 5000) / 10000, 0), 1.0)
    score += foreign_norm * 20
    ad_norm = min(advance_decline_ratio / 3.0, 1.0)
    score += ad_norm * 15
    vol_norm = min(max(volume_change / 50.0 + 0.5, 0), 1.0)
    score += vol_norm * 5
    short_norm = max(0, 1 - short_balance / 100.0)
    score += short_norm * 5
    return round(min(score, 100), 1)


def classify_sentiment(score: float) -> dict:
    if score >= 75:
        return {"label": "탐욕", "strategy": "차익 실현 검토, 신규 매수 자제"}
    elif score >= 55:
        return {"label": "낙관", "strategy": "기존 포지션 유지, 분할 매수 가능"}
    elif score >= 45:
        return {"label": "중립", "strategy": "시장 추이 관망, 우량주 중심 접근"}
    elif score >= 25:
        return {"label": "공포", "strategy": "분할 매수 기회 탐색, 방어주 비중 확대"}
    else:
        return {"label": "극도 공포", "strategy": "현금 비중 최대화, 저점 분할 매수 준비"}


def format_sentiment_alert(score: float, components: dict) -> str:
    info = classify_sentiment(score)
    lines = [
        "<b>[시장 심리 온도계]</b>",
        "━" * 20,
        f"심리 지수: <b>{score}/100</b> — {info['label']}",
        f"전략: {info['strategy']}",
    ]
    if components:
        lines.append("\n<b>구성 요소</b>")
        for k, v in components.items():
            lines.append(f"  {k}: {v}")
    lines.append("━" * 20)
    return "\n".join(lines)
