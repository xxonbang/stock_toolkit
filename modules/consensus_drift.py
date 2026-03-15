def detect_target_drift(stock_history: list) -> dict:
    """
    stock_history: list of {"date": str, "analyst": str, "target_price": int}
    Detects if analysts have been quietly raising or lowering targets.
    """
    if not stock_history:
        return {"direction": "없음", "drift_count": 0, "targets": []}
    sorted_history = sorted(stock_history, key=lambda x: x.get("date", ""))
    targets = [h.get("target_price", 0) for h in sorted_history if h.get("target_price")]
    if len(targets) < 2:
        return {"direction": "없음", "drift_count": 1, "targets": targets}
    up = sum(1 for i in range(1, len(targets)) if targets[i] > targets[i - 1])
    down = sum(1 for i in range(1, len(targets)) if targets[i] < targets[i - 1])
    if up > down and up >= 2:
        direction = "상향"
    elif down > up and down >= 2:
        direction = "하향"
    else:
        direction = "혼조"
    drift_pct = round((targets[-1] - targets[0]) / targets[0] * 100, 1) if targets[0] else 0.0
    return {
        "direction": direction,
        "drift_count": len(targets),
        "first_target": targets[0],
        "last_target": targets[-1],
        "drift_pct": drift_pct,
        "targets": targets,
    }


def calculate_drift_score(drift_data: dict) -> int:
    direction = drift_data.get("direction", "혼조")
    drift_pct = abs(drift_data.get("drift_pct", 0))
    count = drift_data.get("drift_count", 0)
    base = 50
    if direction == "상향":
        base += 25
    elif direction == "하향":
        base -= 25
    count_bonus = min(count * 5, 20)
    pct_bonus = min(drift_pct / 2, 15)
    score = int(min(max(base + count_bonus + pct_bonus, 0), 100))
    return score


def format_drift_alert(results: dict) -> str:
    score = calculate_drift_score(results)
    lines = [
        "<b>[기관 컨센서스 괴리 분석]</b>",
        "━" * 20,
        f"방향: <b>{results.get('direction', '없음')}</b>",
        f"목표가: {results.get('first_target', 0):,}원 → {results.get('last_target', 0):,}원 "
        f"({results.get('drift_pct', 0):+.1f}%)",
        f"분석건수: {results.get('drift_count', 0)}건",
        f"신뢰 점수: <b>{score}/100</b>",
        "━" * 20,
    ]
    return "\n".join(lines)
