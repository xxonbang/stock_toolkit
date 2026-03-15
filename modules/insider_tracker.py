import urllib.request
import json


def fetch_insider_trades(dart_api_key: str, corp_code: str) -> list:
    url = (
        f"https://opendart.fss.or.kr/api/majorstock.json"
        f"?crtfc_key={dart_api_key}&corp_code={corp_code}"
    )
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        return data.get("list", [])
    except Exception:
        return []


def analyze_insider_signal(trades: list) -> dict:
    if not trades:
        return {"score": 0, "signal": "데이터 없음", "buy_count": 0, "sell_count": 0}
    buy_count = sell_count = 0
    buy_shares = sell_shares = 0
    for t in trades:
        change = int(t.get("change_shares", "0").replace(",", "") or 0)
        if change > 0:
            buy_count += 1
            buy_shares += change
        elif change < 0:
            sell_count += 1
            sell_shares += abs(change)
    total = buy_shares + sell_shares
    score = round(buy_shares / total * 100, 1) if total > 0 else 50.0
    if score >= 70:
        signal = "내부자 순매수 — 긍정적"
    elif score <= 30:
        signal = "내부자 순매도 — 주의"
    else:
        signal = "혼조"
    return {
        "score": score,
        "signal": signal,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "buy_shares": buy_shares,
        "sell_shares": sell_shares,
    }


def format_insider_alert(results: dict) -> str:
    lines = [
        "<b>[내부자 거래 추적]</b>",
        "━" * 20,
        f"신호: <b>{results.get('signal', '없음')}</b>",
        f"매수: {results.get('buy_count', 0)}건 ({results.get('buy_shares', 0):,}주)",
        f"매도: {results.get('sell_count', 0)}건 ({results.get('sell_shares', 0):,}주)",
        f"매수 비중: {results.get('score', 0):.1f}%",
        "━" * 20,
    ]
    return "\n".join(lines)
