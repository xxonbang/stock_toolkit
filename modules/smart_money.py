def calculate_smart_money_score(stock: dict) -> float:
    score = 0.0
    foreign_days = min(stock.get("foreign_consecutive_buy", 0), 10)
    score += (foreign_days / 10) * 25
    inst_days = min(stock.get("institution_consecutive_buy", 0), 10)
    score += (inst_days / 10) * 20
    ratio = min(stock.get("net_buy_ratio", 0), 0.05)
    score += (ratio / 0.05) * 20
    score += stock.get("accumulation_match", 0) * 20
    prog = stock.get("program_ratio", 0)
    score += max(0, (1 - prog / 0.5)) * 15
    return round(min(score, 100), 1)


def detect_accumulation_pattern(history: list, min_days: int = 5) -> dict:
    consecutive = 0
    total_net = 0
    total_price_change = 0
    for day in history:
        if day.get("foreign_net", 0) > 0:
            consecutive += 1
            total_net += day["foreign_net"]
            total_price_change += abs(day.get("price_change", 0))
        else:
            break
    if consecutive >= min_days:
        avg_change = total_price_change / consecutive if consecutive > 0 else 0
        if avg_change < 2.0:
            return {"pattern": "조용한 매집", "consecutive_days": consecutive, "total_net_buy": total_net, "avg_price_change": round(avg_change, 1)}
    return {"pattern": "없음", "consecutive_days": consecutive}


def classify_flow_pattern(history: list) -> str:
    if not history:
        return "데이터 없음"
    latest = history[-1]
    foreign = latest.get("foreign_net", 0)
    institution = latest.get("institution_net", 0)
    if foreign < 0 and institution < 0:
        return "쌍방 이탈"
    if len(history) >= 2:
        prev = history[-2].get("foreign_net", 0)
        if foreign > 0 and prev > 0 and foreign > prev * 3:
            return "급속 유입"
    if (foreign > 0 and institution < 0) or (foreign < 0 and institution > 0):
        return "교차 수급"
    if foreign > 0:
        return "외국인 매수"
    return "관망"


def format_smart_money_alert(stock: dict, pattern: dict, score: float) -> str:
    return (
        f"<b>[스마트 머니] {pattern['pattern']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>{stock.get('name', '')} ({stock.get('code', '')})</b>\n"
        f"외국인: {pattern.get('consecutive_days', 0)}일 연속 순매수\n"
        f"누적: +{pattern.get('total_net_buy', 0)}억\n"
        f"스마트 머니 스코어: {score}/100\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
