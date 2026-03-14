from collections import Counter


def analyze_trading_pattern(trades: list) -> dict:
    if not trades:
        return {"biases": [], "total_trades": 0}
    total = len(trades)
    chase_count = sum(1 for t in trades if t.get("change_rate_at_buy", 0) >= 3.0)
    sectors = [t.get("sector", "기타") for t in trades]
    sector_counts = Counter(sectors)
    top_sector, top_count = sector_counts.most_common(1)[0]
    sector_concentration = top_count / total
    losses = [t.get("return_pct", 0) for t in trades if t.get("return_pct", 0) < 0]
    wins = [t.get("return_pct", 0) for t in trades if t.get("return_pct", 0) > 0]
    avg_loss = sum(losses) / len(losses) if losses else 0
    avg_win = sum(wins) / len(wins) if wins else 0
    biases = []
    if chase_count / total >= 0.3:
        biases.append({"type": "추격 매수", "frequency": f"{chase_count}/{total}건"})
    if sector_concentration >= 0.5:
        biases.append({"type": "섹터 편중", "detail": f"{top_sector} {sector_concentration*100:.0f}%"})
    if avg_loss != 0 and avg_win != 0 and abs(avg_loss) > avg_win * 1.5:
        biases.append({"type": "손실 회피 실패", "detail": f"평균 손실 {avg_loss:.1f}% vs 평균 수익 {avg_win:.1f}%"})
    return {
        "biases": biases,
        "total_trades": total,
        "win_rate": round(len(wins) / total * 100, 1) if total else 0,
        "top_sector": top_sector,
    }


def generate_mentor_advice(gemini_client, pattern_analysis: dict, market_context: dict) -> str:
    biases = pattern_analysis.get("biases", [])
    win_rate = pattern_analysis.get("win_rate", 0)
    bias_text = "\n".join(f"- {b['type']}: {b.get('detail', b.get('frequency', ''))}" for b in biases) or "- 특이 편향 없음"
    prompt = (
        f"투자자 매매 패턴 분석 결과:\n"
        f"승률: {win_rate}%\n"
        f"감지된 편향:\n{bias_text}\n\n"
        f"시장 현황: {market_context.get('summary', '정보 없음')}\n\n"
        f"위 내용을 바탕으로 투자자에게 200자 이내의 실용적인 코칭 메시지를 한국어로 작성해줘."
    )
    return gemini_client.generate(prompt)
