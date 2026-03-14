import numpy as np


def normalize_pattern(prices: list) -> list:
    if not prices or prices[0] == 0:
        return [0.0] * len(prices)
    base = prices[0]
    return [round((p - base) / base * 100, 2) for p in prices]


def calculate_similarity(p1: list, p2: list) -> float:
    if len(p1) != len(p2) or not p1:
        return 0.0
    a1 = np.array(p1, dtype=float)
    a2 = np.array(p2, dtype=float)
    norm1 = np.linalg.norm(a1)
    norm2 = np.linalg.norm(a2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    cosine = np.dot(a1, a2) / (norm1 * norm2)
    return round(float(max(0, cosine)), 4)


def find_similar_patterns(current_prices: list, history: list, top_k: int = 5, min_similarity: float = 0.8) -> list:
    current_norm = normalize_pattern(current_prices)
    results = []
    for item in history:
        hist_norm = normalize_pattern(item.get("prices", []))
        if len(hist_norm) != len(current_norm):
            continue
        sim = calculate_similarity(current_norm, hist_norm)
        if sim >= min_similarity:
            results.append({"code": item.get("code"), "date": item.get("date"), "similarity": sim, "future_return_d5": item.get("future_return_d5", 0)})
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]


def format_pattern_match(stock_name: str, matches: list) -> str:
    if not matches:
        return f"<b>{stock_name}</b> — 유사 패턴 없음"
    lines = [f"<b>[패턴 매칭] {stock_name}</b>", "━" * 20]
    returns_d5 = []
    for m in matches:
        lines.append(f"  {m['date']} (유사도 {m['similarity']:.0%}) → D+5: {m['future_return_d5']:+.1f}%")
        returns_d5.append(m["future_return_d5"])
    avg = sum(returns_d5) / len(returns_d5)
    pos_rate = sum(1 for r in returns_d5 if r > 0) / len(returns_d5) * 100
    lines.append(f"\n평균 D+5: {avg:+.1f}% | 상승 확률: {pos_rate:.0f}%")
    lines.append("━" * 20)
    return "\n".join(lines)
