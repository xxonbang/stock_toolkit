def detect_divergence(stock: dict) -> dict | None:
    price_change = stock.get("price_change", 0)
    volume_change = stock.get("volume_change", 0)
    if price_change == 0 or volume_change == 0:
        return None
    price_up = price_change > 0
    volume_up = volume_change > 0
    if price_up == volume_up:
        return None
    return {
        "code": stock.get("code"),
        "name": stock.get("name", ""),
        "price_change": price_change,
        "volume_change": volume_change,
        "divergence_type": "bearish" if price_up else "bullish",
    }


def classify_divergence(divergence: dict) -> dict:
    dtype = divergence.get("divergence_type", "")
    price_change = divergence.get("price_change", 0)
    volume_change = divergence.get("volume_change", 0)
    if dtype == "bearish":
        strength = "강" if abs(volume_change) > 30 else "약"
        return {
            "label": f"약세 괴리 ({strength})",
            "signal": "매도 압력 누적 — 단기 조정 가능성",
            "price_change": price_change,
            "volume_change": volume_change,
        }
    else:
        strength = "강" if abs(volume_change) > 30 else "약"
        return {
            "label": f"강세 괴리 ({strength})",
            "signal": "저점 매집 가능성 — 반등 준비 신호",
            "price_change": price_change,
            "volume_change": volume_change,
        }


def format_divergence_alert(results: list) -> str:
    if not results:
        return "<b>[거래량-가격 괴리] 괴리 종목 없음</b>"
    lines = ["<b>[거래량-가격 괴리] 이상 신호</b>", "━" * 20]
    for r in results[:5]:
        classified = classify_divergence(r)
        lines.append(
            f"\n<b>{r.get('name', '')} ({r.get('code', '')})</b> — {classified['label']}\n"
            f"  가격: {classified['price_change']:+.1f}% | 거래량: {classified['volume_change']:+.1f}%\n"
            f"  {classified['signal']}"
        )
    lines.append("━" * 20)
    return "\n".join(lines)
