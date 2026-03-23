"""최적 a,b,c 백테스트 — 일봉 200일 + 30분봉 10일

a: 익절 한계값 (%)
b: 손절 한계값 (%)
c: 급락 손절값 (%, 고점 대비 낙폭 = trailing stop)

시나리오:
1. 매집 후 수익률 >= a% → 익절
2. 매집 후 수익률 <= b% → 손절
3. 수익률 > 0% 이지만 고점 대비 c% 하락 → 즉시 매도
4. 장 마감(15:15) 시 강제 청산
"""
import json
import sys
from pathlib import Path
from itertools import product

# 데이터 경로
THEME_DATA = Path(__file__).parent.parent.parent / "theme_analysis" / "frontend" / "public" / "data"
STOCK_HISTORY = THEME_DATA / "stock-history.json"
INTRADAY_HISTORY = THEME_DATA / "intraday-history.json"
THEME_FORECAST = THEME_DATA / "theme-forecast.json"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_leader_codes():
    """theme-forecast에서 대장주 코드 추출"""
    codes = set()
    try:
        data = load_json(THEME_FORECAST)
        for theme in data.get("themes", []):
            for stock in theme.get("leader_stocks", theme.get("stocks", [])):
                if isinstance(stock, dict) and stock.get("code"):
                    codes.add(stock["code"])
    except Exception:
        pass
    # stock-history에 있는 종목만 필터
    return codes


def backtest_daily(a_pct, b_pct, c_pct, leader_codes=None):
    """일봉 기반 백테스트

    매일 아침 매수 → 보유 중 일봉 기준 익절/손절/trailing stop 체크
    당일 내 고가/저가로 c(급락) 판정
    """
    stock_hist = load_json(STOCK_HISTORY)

    trades = []

    for code, info in stock_hist.items():
        if leader_codes and code not in leader_codes:
            continue

        raw = info.get("raw_daily_prices", [])
        if len(raw) < 10:
            continue

        # 날짜 오름차순 정렬
        days = sorted(raw, key=lambda x: x.get("stck_bsop_date", ""))

        # 매 거래일 매수 시도 (전일 종가로 매수, 당일~이후 보유)
        i = 0
        while i < len(days) - 1:
            buy_day = days[i]
            buy_price = int(buy_day.get("stck_clpr", "0"))
            if buy_price <= 0:
                i += 1
                continue

            # 보유 시작
            peak_price = buy_price
            sold = False

            for j in range(i + 1, len(days)):
                hold_day = days[j]
                close = int(hold_day.get("stck_clpr", "0"))
                high = int(hold_day.get("stck_hgpr", "0"))
                low = int(hold_day.get("stck_lwpr", "0"))

                if close <= 0:
                    continue

                # 고점 갱신
                if high > peak_price:
                    peak_price = high

                # 일중 고가 기준 수익률
                high_pnl = (high - buy_price) / buy_price * 100
                # 일중 저가 기준 수익률
                low_pnl = (low - buy_price) / buy_price * 100
                # 종가 기준 수익률
                close_pnl = (close - buy_price) / buy_price * 100
                # 고점 대비 낙폭
                drop_from_peak = (close - peak_price) / peak_price * 100 if peak_price > 0 else 0

                reason = None
                sell_pnl = close_pnl

                # 1. 익절: 일중 고가가 a% 도달
                if high_pnl >= a_pct:
                    reason = "take_profit"
                    # 실제 매도가는 a% 지점으로 추정
                    sell_pnl = a_pct

                # 2. 손절: 일중 저가가 b% 도달
                elif low_pnl <= b_pct:
                    reason = "stop_loss"
                    sell_pnl = b_pct

                # 3. Trailing stop: 수익 > 0 이지만 고점 대비 c% 하락
                elif close_pnl > 0 and drop_from_peak <= c_pct:
                    reason = "trailing_stop"
                    sell_pnl = close_pnl

                if reason:
                    trades.append({
                        "code": code,
                        "buy_date": buy_day.get("stck_bsop_date"),
                        "sell_date": hold_day.get("stck_bsop_date"),
                        "hold_days": j - i,
                        "pnl": round(sell_pnl, 2),
                        "reason": reason,
                    })
                    i = j  # 매도일 다음날부터 다시 매수
                    sold = True
                    break

            if not sold:
                # 마지막 날까지 미매도 → 종가에 청산
                last = days[-1]
                last_close = int(last.get("stck_clpr", "0"))
                if last_close > 0:
                    pnl = (last_close - buy_price) / buy_price * 100
                    trades.append({
                        "code": code,
                        "buy_date": buy_day.get("stck_bsop_date"),
                        "sell_date": last.get("stck_bsop_date"),
                        "hold_days": len(days) - 1 - i,
                        "pnl": round(pnl, 2),
                        "reason": "eod_close",
                    })
                i = len(days)  # 종료
            else:
                i += 1

    return trades


def analyze_trades(trades):
    """거래 결과 분석"""
    if not trades:
        return {"total": 0, "win_rate": 0, "avg_pnl": 0, "total_pnl": 0, "avg_hold": 0, "mdd": 0}

    total = len(trades)
    wins = sum(1 for t in trades if t["pnl"] > 0)
    pnls = [t["pnl"] for t in trades]
    holds = [t["hold_days"] for t in trades]

    # MDD (최대 누적 손실)
    cumulative = 0
    peak = 0
    mdd = 0
    for p in pnls:
        cumulative += p
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > mdd:
            mdd = dd

    return {
        "total": total,
        "win_rate": round(wins / total * 100, 1),
        "avg_pnl": round(sum(pnls) / total, 2),
        "total_pnl": round(sum(pnls), 1),
        "avg_hold": round(sum(holds) / total, 1),
        "mdd": round(mdd, 1),
        "by_reason": {
            r: sum(1 for t in trades if t["reason"] == r)
            for r in set(t["reason"] for t in trades)
        },
    }


def backtest_intraday(a_pct, b_pct, c_pct):
    """당일 매수 → 당일 장마감 전 청산 (일봉 고가/저가로 시뮬레이션)

    매일 시가 매수, 장중 고가/저가로 익절/손절/trailing 체크,
    조건 미충족 시 종가 청산.
    """
    stock_hist = load_json(STOCK_HISTORY)
    trades = []

    for code, info in stock_hist.items():
        raw = info.get("raw_daily_prices", [])
        if len(raw) < 5:
            continue

        days = sorted(raw, key=lambda x: x.get("stck_bsop_date", ""))

        for day in days:
            open_p = int(day.get("stck_oprc", "0"))
            high_p = int(day.get("stck_hgpr", "0"))
            low_p = int(day.get("stck_lwpr", "0"))
            close_p = int(day.get("stck_clpr", "0"))

            if open_p <= 0 or close_p <= 0:
                continue

            buy_price = open_p
            high_pnl = (high_p - buy_price) / buy_price * 100 if high_p > 0 else 0
            low_pnl = (low_p - buy_price) / buy_price * 100 if low_p > 0 else 0
            close_pnl = (close_p - buy_price) / buy_price * 100

            reason = None
            sell_pnl = close_pnl

            # 1. 장중 고가가 a% 도달 → 익절
            if high_pnl >= a_pct:
                reason = "take_profit"
                sell_pnl = a_pct

            # 2. 장중 저가가 b% 도달 → 손절
            elif low_pnl <= b_pct:
                reason = "stop_loss"
                sell_pnl = b_pct

            # 3. trailing stop: 고가 도달 후 c% 하락 (고가 - 종가)
            elif high_pnl > 0:
                drop = (close_p - high_p) / high_p * 100 if high_p > 0 else 0
                if drop <= c_pct and close_pnl > 0:
                    reason = "trailing_stop"
                    sell_pnl = close_pnl

            # 4. 장 마감 청산 (종가)
            if not reason:
                reason = "eod_close"
                sell_pnl = close_pnl

            trades.append({
                "code": code,
                "buy_date": day.get("stck_bsop_date"),
                "sell_date": day.get("stck_bsop_date"),
                "hold_days": 0,
                "pnl": round(sell_pnl, 2),
                "reason": reason,
            })

    return trades


def main():
    print("=" * 70)
    print("최적 a,b,c 백테스트 — 일봉 200일")
    print("=" * 70)

    # 대장주 코드
    leader_codes = get_leader_codes()
    print(f"\n대장주 종목: {len(leader_codes)}개")

    # 전체 종목도 포함 (대장주만으로는 표본 부족할 수 있음)
    stock_hist = load_json(STOCK_HISTORY)
    all_codes = set(stock_hist.keys())
    print(f"전체 종목: {len(all_codes)}개")

    # 탐색 범위
    a_values = [3, 5, 7, 10]       # 익절 %
    b_values = [-2, -3, -5, -7]    # 손절 %
    c_values = [-3, -5, -8]        # 급락(trailing) %

    results = []

    print(f"\n탐색: a={a_values}, b={b_values}, c={c_values}")
    print(f"조합: {len(a_values) * len(b_values) * len(c_values)}가지\n")

    for a, b, c in product(a_values, b_values, c_values):
        trades = backtest_daily(a, b, c)  # 전체 종목
        stats = analyze_trades(trades)
        results.append({"a": a, "b": b, "c": c, **stats})

    # 결과 정렬 (총 수익률 기준)
    results.sort(key=lambda x: x["total_pnl"], reverse=True)

    print(f"{'a':>4} {'b':>4} {'c':>4} | {'거래':>5} {'승률':>6} {'평균':>7} {'총수익':>8} {'보유일':>5} {'MDD':>6} | 매매사유")
    print("-" * 85)

    for r in results[:20]:
        by = r.get("by_reason", {})
        reason_str = f"익절{by.get('take_profit',0)} 손절{by.get('stop_loss',0)} TS{by.get('trailing_stop',0)} 청산{by.get('eod_close',0)}"
        print(f"{r['a']:>4} {r['b']:>4} {r['c']:>4} | {r['total']:>5} {r['win_rate']:>5.1f}% {r['avg_pnl']:>+6.2f}% {r['total_pnl']:>+7.1f}% {r['avg_hold']:>5.1f} {r['mdd']:>5.1f}% | {reason_str}")

    print(f"\n--- 최악 5 ---")
    for r in results[-5:]:
        by = r.get("by_reason", {})
        reason_str = f"익절{by.get('take_profit',0)} 손절{by.get('stop_loss',0)} TS{by.get('trailing_stop',0)} 청산{by.get('eod_close',0)}"
        print(f"{r['a']:>4} {r['b']:>4} {r['c']:>4} | {r['total']:>5} {r['win_rate']:>5.1f}% {r['avg_pnl']:>+6.2f}% {r['total_pnl']:>+7.1f}% {r['avg_hold']:>5.1f} {r['mdd']:>5.1f}% | {reason_str}")

    # 최적 조합 상세
    best = results[0]
    print(f"\n{'=' * 70}")
    print(f"최적 조합: a={best['a']}%, b={best['b']}%, c={best['c']}%")
    print(f"  총 거래: {best['total']}건")
    print(f"  승률: {best['win_rate']}%")
    print(f"  평균 수익률: {best['avg_pnl']:+.2f}%")
    print(f"  총 수익률: {best['total_pnl']:+.1f}%")
    print(f"  평균 보유일: {best['avg_hold']}일")
    print(f"  MDD: {best['mdd']:.1f}%")
    print(f"  매매사유: {best.get('by_reason', {})}")

    # ========== 당일 청산 시나리오 ==========
    print(f"\n\n{'=' * 70}")
    print("당일 청산 시나리오 (시가 매수 → 장마감 종가 청산)")
    print("=" * 70)

    intraday_results = []
    for a, b, c in product(a_values, b_values, c_values):
        trades2 = backtest_intraday(a, b, c)
        stats2 = analyze_trades(trades2)
        intraday_results.append({"a": a, "b": b, "c": c, **stats2})

    intraday_results.sort(key=lambda x: x["total_pnl"], reverse=True)

    print(f"\n{'a':>4} {'b':>4} {'c':>4} | {'거래':>5} {'승률':>6} {'평균':>7} {'총수익':>8} {'MDD':>6} | 매매사유")
    print("-" * 80)
    for r in intraday_results[:15]:
        by = r.get("by_reason", {})
        reason_str = f"익절{by.get('take_profit',0)} 손절{by.get('stop_loss',0)} TS{by.get('trailing_stop',0)} 청산{by.get('eod_close',0)}"
        print(f"{r['a']:>4} {r['b']:>4} {r['c']:>4} | {r['total']:>5} {r['win_rate']:>5.1f}% {r['avg_pnl']:>+6.2f}% {r['total_pnl']:>+7.1f}% {r['mdd']:>5.1f}% | {reason_str}")

    best_intraday = intraday_results[0]
    print(f"\n당일 청산 최적: a={best_intraday['a']}%, b={best_intraday['b']}%, c={best_intraday['c']}%")
    print(f"  총 거래: {best_intraday['total']}건, 승률: {best_intraday['win_rate']}%")
    print(f"  평균 수익률: {best_intraday['avg_pnl']:+.2f}%, 총 수익률: {best_intraday['total_pnl']:+.1f}%")
    print(f"  MDD: {best_intraday['mdd']:.1f}%")

    # JSON 저장
    output_path = Path(__file__).parent.parent / "results" / "backtest_abc.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "multi_day": {"best": best, "all_results": results},
            "intraday": {"best": best_intraday, "all_results": intraday_results},
        }, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {output_path}")


if __name__ == "__main__":
    main()
