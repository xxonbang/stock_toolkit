"""현재 시스템 vs RSI(2) 심층 비교 백테스트

분석 관점:
1. 전체 기간 + 학습/검증 분리
2. RSI 파라미터 변형 (임계값, MA필터, 보유기간)
3. 월별 성과 분해
4. 거래 수익률 분포 비교
5. 롤링 60일 윈도우 성과 추이
6. 연속 손실/승리 분석
7. 두 전략 결합 효과
8. 통계적 유의성 (부트스트랩)
"""
import json
import os
import sys
import time
import random
from pathlib import Path
from collections import defaultdict
from datetime import datetime

os.environ["PYTHONUNBUFFERED"] = "1"

DATA_PATH = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"
RESULT_PATH = Path(__file__).parent.parent / "results" / "backtest_deep_compare.json"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ══════════════════════════════════════════════════════════════
# 지표 계산
# ══════════════════════════════════════════════════════════════

def prepare_stock(bars):
    if len(bars) < 201:
        return []
    closes, opens, highs, lows, volumes = [], [], [], [], []
    results = []
    for i, b in enumerate(bars):
        c = int(b.get("stck_clpr", "0"))
        o = int(b.get("stck_oprc", "0"))
        h = int(b.get("stck_hgpr", "0"))
        lo = int(b.get("stck_lwpr", "0"))
        vol = int(b.get("acml_vol", "0"))
        if c <= 0:
            closes.append(closes[-1] if closes else 0)
            opens.append(opens[-1] if opens else 0)
            highs.append(highs[-1] if highs else 0)
            lows.append(lows[-1] if lows else 0)
            volumes.append(0)
            results.append(None)
            continue
        closes.append(c); opens.append(o); highs.append(h); lows.append(lo); volumes.append(vol)
        if i < 200:
            results.append(None)
            continue

        # RSI(2)
        g = l = 0
        for k in (i-1, i):
            diff = closes[k] - closes[k-1]
            if diff > 0: g += diff
            else: l -= diff
        ag, al = g/2, l/2
        rsi2 = 100 - 100/(1+ag/al) if al > 0 else 100.0

        # RSI(3) — 변형 테스트용
        g3 = l3 = 0
        for k in (i-2, i-1, i):
            diff = closes[k] - closes[k-1]
            if diff > 0: g3 += diff
            else: l3 -= diff
        ag3, al3 = g3/3, l3/3
        rsi3 = 100 - 100/(1+ag3/al3) if al3 > 0 else 100.0

        ma5 = sum(closes[i-4:i+1]) / 5
        ma20 = sum(closes[i-19:i+1]) / 20
        ma50 = sum(closes[i-49:i+1]) / 50
        ma200 = sum(closes[i-199:i+1]) / 200

        avg_vol_20 = sum(volumes[i-19:i+1]) / 20

        prev_ma5 = sum(closes[i-5:i]) / 5
        prev_ma20 = sum(closes[i-20:i]) / 20

        results.append({
            "d": b.get("stck_bsop_date", ""),
            "c": c, "o": o, "h": h, "l": lo, "vol": vol,
            "rsi2": rsi2, "rsi3": rsi3,
            "ma5": ma5, "ma20": ma20, "ma50": ma50, "ma200": ma200,
            "avg_vol_20": avg_vol_20,
            "prev_high": highs[i-1], "prev_close": closes[i-1],
            "prev_ma5": prev_ma5, "prev_ma20": prev_ma20,
            "ok": 1000 <= c < 200000,
        })
    return results


# ══════════════════════════════════════════════════════════════
# 전략 함수 (파라미터화)
# ══════════════════════════════════════════════════════════════

def make_rsi2_strategy(buy_th=10, sell_th=90, ma_filter="ma200", rsi_period=2):
    """RSI(2) 전략 생성기 — 파라미터 변형 가능"""
    rsi_key = "rsi2" if rsi_period == 2 else "rsi3"
    def strategy(ind, holding):
        if holding:
            return "sell" if ind[rsi_key] > sell_th else "hold"
        rsi = ind[rsi_key]
        ma_val = ind.get(ma_filter, 0)
        if rsi < buy_th and ind["c"] > ma_val and ind["ok"]:
            return "buy"
        return None
    return strategy

def current_system_strategy(ind, holding):
    """현재 시스템 근사"""
    if holding:
        return "hold"
    score = 0
    c = ind["c"]
    if c > ind["prev_close"]: score += 5
    if c < 20000: score += 5
    if ind["vol"] > ind["avg_vol_20"] * 1.5: score += 10
    if ind["ma5"] > ind["ma20"] and ind["prev_ma5"] <= ind["prev_ma20"]: score += 5
    if c > ind["prev_high"]: score += 5
    if score >= 15 and ind["ok"]:
        return "buy"
    return None


# ══════════════════════════════════════════════════════════════
# 백테스트 엔진 (거래 상세 반환)
# ══════════════════════════════════════════════════════════════

def run_backtest_detailed(all_data, strat_fn, tp=0, sl=0, ts=0, max_hold=20,
                           date_range=None, max_pos=2):
    """거래 상세 리스트 반환: [{date, code, pnl, hold_days}, ...]"""
    date_stocks = defaultdict(dict)
    for code, inds in all_data.items():
        for ind in inds:
            if ind is None: continue
            d = ind["d"]
            if date_range and (d < date_range[0] or d > date_range[1]): continue
            date_stocks[d][code] = ind

    dates = sorted(date_stocks.keys())
    trades = []
    holdings = {}

    for di, date in enumerate(dates):
        stocks = date_stocks[date]
        sold = set()

        for code in list(holdings.keys()):
            ind = stocks.get(code)
            if ind is None: continue
            bp, bi, pk = holdings[code]
            h, lo, c = ind["h"], ind["l"], ind["c"]
            hold_days = di - bi
            if h > pk: pk = h; holdings[code] = (bp, bi, pk)

            high_pnl = (h-bp)/bp*100
            low_pnl = (lo-bp)/bp*100
            close_pnl = (c-bp)/bp*100
            drop = (c-pk)/pk*100 if pk > 0 else 0

            do_sell = False; sell_pnl = close_pnl
            action = strat_fn(ind, True)
            if action == "sell": do_sell = True
            if tp > 0 and high_pnl >= tp: do_sell = True; sell_pnl = tp
            if sl < 0 and low_pnl <= sl: do_sell = True; sell_pnl = sl
            if ts < 0 and close_pnl > 0 and drop <= ts: do_sell = True; sell_pnl = close_pnl
            if max_hold > 0 and hold_days >= max_hold: do_sell = True

            if do_sell:
                trades.append({"date": date, "code": code, "pnl": round(sell_pnl, 2),
                               "hold": hold_days, "month": date[:6]})
                del holdings[code]; sold.add(code)

        if len(holdings) >= max_pos: continue
        cands = [(code, ind) for code, ind in stocks.items()
                 if code not in holdings and code not in sold and strat_fn(ind, False) == "buy"]
        cands.sort(key=lambda x: -x[1]["vol"])
        for code, ind in cands[:max_pos - len(holdings)]:
            holdings[code] = (ind["c"], di, ind["c"])

    if dates:
        last = date_stocks[dates[-1]]
        for code, (bp, bi, pk) in holdings.items():
            ind = last.get(code)
            if ind:
                pnl = (ind["c"]-bp)/bp*100
                trades.append({"date": dates[-1], "code": code, "pnl": round(pnl, 2),
                               "hold": len(dates)-1-bi, "month": dates[-1][:6]})
    return trades


def analyze(trades_list):
    pnls = [t["pnl"] for t in trades_list] if isinstance(trades_list[0], dict) else trades_list
    n = len(pnls)
    if n == 0:
        return {"n": 0}
    s = sorted(pnls)
    wins = sum(1 for p in pnls if p > 0)
    avg = sum(pnls) / n
    med = s[n//2]
    lo, hi = int(n*0.05), n - int(n*0.05)
    trim = sum(s[lo:hi]) / (hi-lo) if hi > lo else avg
    std = (sum((p-avg)**2 for p in pnls)/n)**0.5 if n > 1 else 1
    cum = pk = mdd = 0
    for p in pnls:
        cum += p
        if cum > pk: pk = cum
        dd = pk - cum
        if dd > mdd: mdd = dd
    gp = sum(p for p in pnls if p > 0)
    gl = abs(sum(p for p in pnls if p < 0))
    # 연속 손실/승리
    max_win_streak = max_loss_streak = cur_w = cur_l = 0
    for p in pnls:
        if p > 0: cur_w += 1; cur_l = 0
        else: cur_l += 1; cur_w = 0
        max_win_streak = max(max_win_streak, cur_w)
        max_loss_streak = max(max_loss_streak, cur_l)
    return {
        "n": n, "wr": round(wins/n*100, 1), "avg": round(avg, 2),
        "med": round(med, 2), "trim": round(trim, 2),
        "total_pnl": round(sum(pnls), 1), "mdd": round(mdd, 1),
        "sharpe": round(avg/std, 3) if std > 0 else 0,
        "pf": round(gp/gl, 2) if gl > 0 else 999,
        "max_win": max_win_streak, "max_loss": max_loss_streak,
        "avg_hold": round(sum(t["hold"] for t in trades_list)/n, 1) if isinstance(trades_list[0], dict) else 0,
    }


def print_stats(label, stats):
    print(f"  {label:<35s} N={stats['n']:>4} WR={stats['wr']:>5.1f}% "
          f"trim={stats['trim']:>+6.2f}% med={stats['med']:>+6.2f}% "
          f"SR={stats['sharpe']:>6.3f} PF={stats['pf']:>5.2f} "
          f"MDD={stats['mdd']:>5.1f}% hold={stats.get('avg_hold',0):.1f}d "
          f"W{stats['max_win']}L{stats['max_loss']}")


def main():
    print("=" * 90)
    print("현재 시스템 vs RSI(2) 심층 비교 백테스트")
    print("=" * 90)

    data = load_json(DATA_PATH)
    all_data = {}
    for code, info in data.items():
        bars = info.get("bars", [])
        if len(bars) < 300: continue
        tvs = [int(b.get("acml_tr_pbmn", "0")) for b in bars[-100:]]
        if sum(tvs)/len(tvs) < 1_000_000_000: continue
        inds = prepare_stock(bars)
        if inds: all_data[code] = inds
    print(f"유효 종목: {len(all_data)}")

    all_dates = sorted({ind["d"] for inds in all_data.values() for ind in inds if ind})
    mid = len(all_dates) // 2
    train = (all_dates[0], all_dates[mid])
    test = (all_dates[mid+1], all_dates[-1])
    print(f"전체: {all_dates[0]}~{all_dates[-1]} ({len(all_dates)}일)")
    print(f"학습: {train[0]}~{train[1]} | 검증: {test[0]}~{test[1]}")

    # ═══════════════════════════════════════════════════════════
    # Phase 1: 기본 비교 (전체/학습/검증)
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'='*90}")
    print("Phase 1: 기본 비교 (전체 / 학습 / 검증)")
    print("─" * 90)

    configs = [
        ("현재시스템 (TP7/SL-2/TS-3/5일)", current_system_strategy, {"tp": 7, "sl": -2, "ts": -3, "max_hold": 5}),
        ("RSI(2)<10/>90 MA200 (20일)", make_rsi2_strategy(10, 90, "ma200"), {"tp": 0, "sl": 0, "ts": 0, "max_hold": 20}),
    ]

    for label, fn, params in configs:
        print(f"\n  [{label}]")
        for period_name, dr in [("전체", None), ("학습", train), ("검증", test)]:
            trades = run_backtest_detailed(all_data, fn, **params, date_range=dr)
            if trades:
                s = analyze(trades)
                print_stats(f"  {period_name}", s)

    # ═══════════════════════════════════════════════════════════
    # Phase 2: RSI(2) 파라미터 변형
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'='*90}")
    print("Phase 2: RSI 파라미터 변형 (검증기간)")
    print("─" * 90)

    rsi_variants = [
        # (label, buy_th, sell_th, ma_filter, rsi_period, max_hold, tp, sl)
        ("RSI(2)<5/>95 MA200 20d", 5, 95, "ma200", 2, 20, 0, 0),
        ("RSI(2)<10/>90 MA200 20d", 10, 90, "ma200", 2, 20, 0, 0),
        ("RSI(2)<15/>85 MA200 20d", 15, 85, "ma200", 2, 20, 0, 0),
        ("RSI(2)<20/>80 MA200 20d", 20, 80, "ma200", 2, 20, 0, 0),
        ("RSI(2)<10/>90 MA50 20d", 10, 90, "ma50", 2, 20, 0, 0),
        ("RSI(2)<10/>90 MA20 20d", 10, 90, "ma20", 2, 20, 0, 0),
        ("RSI(2)<10/>90 없음 20d", 10, 90, "c", 2, 20, 0, 0),  # MA필터 없음 (c>c=항상참은 아니므로 별도 처리)
        ("RSI(3)<10/>90 MA200 20d", 10, 90, "ma200", 3, 20, 0, 0),
        ("RSI(2)<10/>90 MA200 5d", 10, 90, "ma200", 2, 5, 0, 0),
        ("RSI(2)<10/>90 MA200 10d", 10, 90, "ma200", 2, 10, 0, 0),
        ("RSI(2)<10 +TP7/SL-2/TS-3 5d", 10, 90, "ma200", 2, 5, 7, -2),
        ("RSI(2)<10 +SL-2만 20d", 10, 90, "ma200", 2, 20, 0, -2),
    ]

    rsi_results = []
    for label, buy_th, sell_th, ma, rsi_p, mh, tp, sl in rsi_variants:
        # MA필터 없음 처리
        if ma == "c":
            def no_ma_strat(ind, holding, _bt=buy_th, _st=sell_th, _rp=rsi_p):
                rk = "rsi2" if _rp == 2 else "rsi3"
                if holding: return "sell" if ind[rk] > _st else "hold"
                if ind[rk] < _bt and ind["ok"]: return "buy"
                return None
            fn = no_ma_strat
        else:
            fn = make_rsi2_strategy(buy_th, sell_th, ma, rsi_p)
        ts_val = -3 if tp > 0 else 0

        # 학습 + 검증
        tr_trades = run_backtest_detailed(all_data, fn, tp=tp, sl=sl, ts=ts_val, max_hold=mh, date_range=train)
        te_trades = run_backtest_detailed(all_data, fn, tp=tp, sl=sl, ts=ts_val, max_hold=mh, date_range=test)
        tr_s = analyze(tr_trades) if tr_trades else {"n": 0, "trim": 0, "wr": 0, "sharpe": 0, "pf": 0}
        te_s = analyze(te_trades) if te_trades else {"n": 0, "trim": 0, "wr": 0, "sharpe": 0, "pf": 0}
        consistent = "O" if tr_s["n"] >= 5 and te_s["n"] >= 5 and (tr_s["trim"] > 0) == (te_s["trim"] > 0) else "X"

        rsi_results.append({"label": label, "train": tr_s, "test": te_s, "consistent": consistent})
        print(f"  {label:<35s} 학습 trim={tr_s['trim']:>+6.2f}% N={tr_s['n']:>3} | "
              f"검증 trim={te_s['trim']:>+6.2f}% N={te_s['n']:>3} WR={te_s['wr']:>5.1f}% "
              f"SR={te_s['sharpe']:>6.3f} PF={te_s['pf']:>5.2f} | {consistent}")

    # ═══════════════════════════════════════════════════════════
    # Phase 3: 월별 성과 분해
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'='*90}")
    print("Phase 3: 월별 성과 분해 (전체 기간)")
    print("─" * 90)

    cur_trades = run_backtest_detailed(all_data, current_system_strategy, tp=7, sl=-2, ts=-3, max_hold=5)
    rsi_trades = run_backtest_detailed(all_data, make_rsi2_strategy(10, 90, "ma200"), tp=0, sl=0, ts=0, max_hold=20)

    # 월별 그룹핑
    def monthly_breakdown(trades):
        by_month = defaultdict(list)
        for t in trades:
            by_month[t["month"]].append(t["pnl"])
        return by_month

    cur_monthly = monthly_breakdown(cur_trades)
    rsi_monthly = monthly_breakdown(rsi_trades)
    all_months = sorted(set(cur_monthly.keys()) | set(rsi_monthly.keys()))

    print(f"  {'월':>8} | {'현재시스템':>28} | {'RSI(2)':>28}")
    print(f"  {'':>8} | {'N':>3} {'WR':>5} {'avg':>7} {'sum':>7} | {'N':>3} {'WR':>5} {'avg':>7} {'sum':>7}")
    print("  " + "─" * 75)

    for m in all_months:
        cp = cur_monthly.get(m, [])
        rp = rsi_monthly.get(m, [])
        c_n, c_wr, c_avg, c_sum = len(cp), (sum(1 for p in cp if p>0)/len(cp)*100 if cp else 0), (sum(cp)/len(cp) if cp else 0), sum(cp)
        r_n, r_wr, r_avg, r_sum = len(rp), (sum(1 for p in rp if p>0)/len(rp)*100 if rp else 0), (sum(rp)/len(rp) if rp else 0), sum(rp)
        print(f"  {m:>8} | {c_n:>3} {c_wr:>4.0f}% {c_avg:>+6.2f}% {c_sum:>+6.1f}% | "
              f"{r_n:>3} {r_wr:>4.0f}% {r_avg:>+6.2f}% {r_sum:>+6.1f}%")

    # 월별 승패 카운트
    cur_win_months = sum(1 for m in all_months if sum(cur_monthly.get(m, [0])) > 0)
    rsi_win_months = sum(1 for m in all_months if sum(rsi_monthly.get(m, [0])) > 0)
    print(f"\n  수익 월: 현재시스템 {cur_win_months}/{len(all_months)}, RSI(2) {rsi_win_months}/{len(all_months)}")

    # ═══════════════════════════════════════════════════════════
    # Phase 4: 수익률 분포 비교
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'='*90}")
    print("Phase 4: 수익률 분포 비교")
    print("─" * 90)

    for label, trades in [("현재시스템", cur_trades), ("RSI(2)", rsi_trades)]:
        pnls = sorted([t["pnl"] for t in trades])
        n = len(pnls)
        if n == 0: continue
        buckets = {"≤-5%": 0, "-5~-2%": 0, "-2~0%": 0, "0~2%": 0, "2~5%": 0, "5~7%": 0, "≥7%": 0}
        for p in pnls:
            if p <= -5: buckets["≤-5%"] += 1
            elif p <= -2: buckets["-5~-2%"] += 1
            elif p < 0: buckets["-2~0%"] += 1
            elif p <= 2: buckets["0~2%"] += 1
            elif p <= 5: buckets["2~5%"] += 1
            elif p <= 7: buckets["5~7%"] += 1
            else: buckets["≥7%"] += 1
        print(f"\n  {label} (N={n}):")
        for bucket, cnt in buckets.items():
            bar = "█" * int(cnt / n * 50)
            print(f"    {bucket:>8}: {cnt:>4} ({cnt/n*100:>5.1f}%) {bar}")
        print(f"    최소={pnls[0]:>+.2f}%, P25={pnls[n//4]:>+.2f}%, "
              f"P50={pnls[n//2]:>+.2f}%, P75={pnls[3*n//4]:>+.2f}%, 최대={pnls[-1]:>+.2f}%")

    # ═══════════════════════════════════════════════════════════
    # Phase 5: 롤링 60일 윈도우 성과 추이
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'='*90}")
    print("Phase 5: 롤링 60일 윈도우 성과 추이")
    print("─" * 90)

    def rolling_performance(trades, window=60):
        by_date = defaultdict(list)
        for t in trades:
            by_date[t["date"]].append(t["pnl"])
        dates_sorted = sorted(by_date.keys())
        results = []
        for i in range(0, len(dates_sorted) - window + 1, 30):  # 30일 간격
            chunk_dates = dates_sorted[i:i+window]
            chunk_pnls = []
            for d in chunk_dates:
                chunk_pnls.extend(by_date[d])
            if chunk_pnls:
                avg = sum(chunk_pnls) / len(chunk_pnls)
                wr = sum(1 for p in chunk_pnls if p > 0) / len(chunk_pnls) * 100
                results.append({"start": chunk_dates[0], "end": chunk_dates[-1],
                                "n": len(chunk_pnls), "avg": round(avg, 2), "wr": round(wr, 1)})
        return results

    cur_rolling = rolling_performance(cur_trades)
    rsi_rolling = rolling_performance(rsi_trades)

    print(f"  {'기간':>22} | {'현재시스템':>20} | {'RSI(2)':>20}")
    print("  " + "─" * 68)
    max_len = max(len(cur_rolling), len(rsi_rolling))
    for i in range(max_len):
        cr = cur_rolling[i] if i < len(cur_rolling) else None
        rr = rsi_rolling[i] if i < len(rsi_rolling) else None
        period = (cr or rr)["start"][:6] + "~" + (cr or rr)["end"][:6]
        c_str = f"avg={cr['avg']:>+5.2f}% WR={cr['wr']:>4.1f}% N={cr['n']:>3}" if cr else "  —"
        r_str = f"avg={rr['avg']:>+5.2f}% WR={rr['wr']:>4.1f}% N={rr['n']:>3}" if rr else "  —"
        print(f"  {period:>22} | {c_str} | {r_str}")

    # ═══════════════════════════════════════════════════════════
    # Phase 6: 두 전략 결합 효과
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'='*90}")
    print("Phase 6: 두 전략 결합 효과 (OR 조건)")
    print("─" * 90)

    def combined_strategy(ind, holding):
        """현재 시스템 OR RSI(2) 중 하나라도 매수 시그널이면 매수"""
        if holding:
            # RSI(2) 매도 시그널
            if ind["rsi2"] > 90:
                return "sell"
            return "hold"
        # 현재 시스템 매수
        score = 0
        c = ind["c"]
        if c > ind["prev_close"]: score += 5
        if c < 20000: score += 5
        if ind["vol"] > ind["avg_vol_20"] * 1.5: score += 10
        if ind["ma5"] > ind["ma20"] and ind["prev_ma5"] <= ind["prev_ma20"]: score += 5
        if c > ind["prev_high"]: score += 5
        if score >= 15 and ind["ok"]:
            return "buy"
        # RSI(2) 매수
        if ind["rsi2"] < 10 and ind["c"] > ind["ma200"] and ind["ok"]:
            return "buy"
        return None

    for period_name, dr in [("학습", train), ("검증", test), ("전체", None)]:
        trades = run_backtest_detailed(all_data, combined_strategy, tp=7, sl=-2, ts=-3, max_hold=10, date_range=dr)
        if trades:
            s = analyze(trades)
            print_stats(f"  결합 [{period_name}]", s)

    # ═══════════════════════════════════════════════════════════
    # Phase 7: 부트스트랩 통계 검정
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'='*90}")
    print("Phase 7: 부트스트랩 통계 검정 (10,000회)")
    print("─" * 90)

    random.seed(42)
    N_BOOT = 10000

    for label, trades in [("현재시스템", cur_trades), ("RSI(2)", rsi_trades)]:
        pnls = [t["pnl"] for t in trades]
        n = len(pnls)
        if n < 10:
            print(f"  {label}: 거래수 부족 (N={n})")
            continue
        boot_means = []
        for _ in range(N_BOOT):
            sample = [random.choice(pnls) for _ in range(n)]
            boot_means.append(sum(sample) / n)
        boot_means.sort()
        ci_lo = boot_means[int(N_BOOT * 0.025)]
        ci_hi = boot_means[int(N_BOOT * 0.975)]
        mean = sum(pnls) / n
        pct_positive = sum(1 for m in boot_means if m > 0) / N_BOOT * 100
        print(f"  {label} (N={n}): 평균={mean:>+.3f}%, "
              f"95% CI=[{ci_lo:>+.3f}%, {ci_hi:>+.3f}%], "
              f"양수 확률={pct_positive:.1f}%")

    # 차이 검정
    cur_pnls = [t["pnl"] for t in cur_trades]
    rsi_pnls = [t["pnl"] for t in rsi_trades]
    if cur_pnls and rsi_pnls:
        diff_boots = []
        for _ in range(N_BOOT):
            c_sample = [random.choice(cur_pnls) for _ in range(len(cur_pnls))]
            r_sample = [random.choice(rsi_pnls) for _ in range(len(rsi_pnls))]
            diff_boots.append(sum(r_sample)/len(r_sample) - sum(c_sample)/len(c_sample))
        diff_boots.sort()
        ci_lo = diff_boots[int(N_BOOT * 0.025)]
        ci_hi = diff_boots[int(N_BOOT * 0.975)]
        pct_rsi_better = sum(1 for d in diff_boots if d > 0) / N_BOOT * 100
        print(f"\n  RSI(2) - 현재시스템 차이: 95% CI=[{ci_lo:>+.3f}%, {ci_hi:>+.3f}%], "
              f"RSI(2)이 나을 확률={pct_rsi_better:.1f}%")

    # ═══════════════════════════════════════════════════════════
    # 최종 요약
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'='*90}")
    print("최종 요약")
    print("─" * 90)

    cur_test = run_backtest_detailed(all_data, current_system_strategy, tp=7, sl=-2, ts=-3, max_hold=5, date_range=test)
    rsi_test = run_backtest_detailed(all_data, make_rsi2_strategy(10, 90, "ma200"), tp=0, sl=0, ts=0, max_hold=20, date_range=test)
    cs = analyze(cur_test)
    rs = analyze(rsi_test)

    print(f"  {'지표':<20} {'현재시스템':>12} {'RSI(2)':>12} {'차이':>12}")
    print("  " + "─" * 60)
    for k, label in [("trim", "Trimmed Mean"), ("wr", "승률"), ("sharpe", "Sharpe"),
                      ("pf", "Profit Factor"), ("n", "거래수"), ("mdd", "MDD"),
                      ("max_loss", "최대 연속손실"), ("avg_hold", "평균 보유일")]:
        cv, rv = cs.get(k, 0), rs.get(k, 0)
        if k in ("trim", "wr", "mdd", "avg_hold"):
            print(f"  {label:<20} {cv:>+11.2f}% {rv:>+11.2f}% {rv-cv:>+11.2f}%")
        else:
            print(f"  {label:<20} {cv:>12} {rv:>12} {rv-cv:>+12}")

    # JSON 저장
    save_data = {
        "generated_at": datetime.now().isoformat(),
        "universe": len(all_data),
        "date_range": f"{all_dates[0]}~{all_dates[-1]}",
        "current_system_test": cs,
        "rsi2_test": rs,
        "rsi_variants": rsi_results,
    }
    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {RESULT_PATH}")


if __name__ == "__main__":
    main()
