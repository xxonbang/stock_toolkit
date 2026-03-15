def track_program_trading(stock: dict) -> dict:
    """
    stock: {"name": str, "code": str,
            "arb_buy": int, "arb_sell": int,
            "non_arb_buy": int, "non_arb_sell": int}
    """
    arb_net = stock.get("arb_buy", 0) - stock.get("arb_sell", 0)
    non_arb_net = stock.get("non_arb_buy", 0) - stock.get("non_arb_sell", 0)
    total_net = arb_net + non_arb_net
    if total_net > 0:
        direction = "순매수"
    elif total_net < 0:
        direction = "순매도"
    else:
        direction = "중립"
    return {
        "code": stock.get("code", ""),
        "name": stock.get("name", ""),
        "arb_net": arb_net,
        "non_arb_net": non_arb_net,
        "total_net": total_net,
        "direction": direction,
    }


def detect_program_reversal(history: list) -> dict:
    """
    history: [{"date": str, "total_net": int}, ...]  sorted ascending by date
    Detects sign change in program trading direction.
    """
    if len(history) < 2:
        return {"reversal": False, "from_direction": None, "to_direction": None}
    prev_net = history[-2].get("total_net", 0)
    curr_net = history[-1].get("total_net", 0)
    reversal = (prev_net > 0 and curr_net < 0) or (prev_net < 0 and curr_net > 0)
    return {
        "reversal": reversal,
        "from_direction": "순매수" if prev_net > 0 else "순매도",
        "to_direction": "순매수" if curr_net > 0 else "순매도",
        "prev_net": prev_net,
        "curr_net": curr_net,
    }


def format_program_alert(results: dict) -> str:
    tracking = results.get("tracking", {})
    reversal = results.get("reversal", {})
    lines = [
        "<b>[프로그램 매매 분석]</b>",
        "━" * 20,
        f"차익: {tracking.get('arb_net', 0):+,}주 | 비차익: {tracking.get('non_arb_net', 0):+,}주",
        f"합계: <b>{tracking.get('total_net', 0):+,}주</b> ({tracking.get('direction', '')})",
    ]
    if reversal.get("reversal"):
        lines.append(
            f"\n<b>방향 전환 감지:</b> {reversal.get('from_direction')} → {reversal.get('to_direction')}"
        )
    lines.append("━" * 20)
    return "\n".join(lines)
