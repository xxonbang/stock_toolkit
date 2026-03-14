from collections import Counter

def match_trade_context(trade: dict, signal_history: dict, theme_history: dict) -> dict:
    date = trade.get("date", "")
    code = trade.get("code", "")
    ctx = {"signal": None, "score": None, "theme": None}
    signals = signal_history.get(date, [])
    for s in signals:
        if s.get("code") == code:
            ctx["signal"] = s.get("signal")
            ctx["score"] = s.get("score")
            break
    themes = theme_history.get(date, [])
    for t in themes:
        for leader in t.get("leaders", []):
            if leader.get("code") == code:
                ctx["theme"] = t.get("name")
                break
    return ctx


def detect_trading_bias(trades: list) -> list:
    biases = []
    buy_trades = [t for t in trades if t.get("action") == "buy"]
    chasing = [t for t in buy_trades if t.get("change_at_buy", 0) >= 3.0]
    if len(chasing) >= 2:
        biases.append({"type": "추격 매수", "count": len(chasing), "total_buys": len(buy_trades), "message": f"매수 {len(buy_trades)}건 중 {len(chasing)}건이 +3% 이상 상승 시점. 눌림목 대기 권장."})
    theme_counts = Counter(t.get("theme") for t in buy_trades if t.get("theme"))
    for theme, count in theme_counts.items():
        if count >= 3:
            biases.append({"type": "섹터 편중", "theme": theme, "count": count, "message": f"{theme} 테마에 {count}건 집중 매수. 분산 필요."})
    return biases


def calculate_trade_stats(trades: list) -> dict:
    if not trades:
        return {"total": 0, "win_rate": 0, "avg_return": 0}
    returns = [t.get("return_pct", 0) for t in trades]
    wins = sum(1 for r in returns if r > 0)
    return {"total": len(trades), "wins": wins, "losses": len(trades) - wins, "win_rate": round(wins / len(trades) * 100, 1), "avg_return": round(sum(returns) / len(returns), 2), "max_return": round(max(returns), 2), "min_return": round(min(returns), 2)}


JOURNAL_PROMPT = """당신은 투자 코치입니다. 아래 매매 기록과 당시 시장 상황을 분석하여 매매 일지를 작성하세요.

매매 기록:
{trades}

시장 상황:
{context}

편향 분석:
{biases}

출력 형식 (텔레그램 HTML):
1. 오늘의 매매 — 각 매매에 대한 평가 (시스템 신호 일치 여부)
2. 잘한 점 — 시스템에 부합하는 매매
3. 개선 포인트 — 감지된 편향 및 개선 제안
20줄 이내 간결하게."""


def generate_journal(gemini_client, trades: list, context: dict, biases: list) -> str:
    import json
    prompt = JOURNAL_PROMPT.format(
        trades=json.dumps(trades, ensure_ascii=False, indent=2),
        context=json.dumps(context, ensure_ascii=False, indent=2),
        biases=json.dumps(biases, ensure_ascii=False, indent=2),
    )
    return gemini_client.generate(prompt)
