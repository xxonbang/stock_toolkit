"""추가 10대 자동매매 전략 백테스트 (기존과 미중복)

전략 목록 (11~20):
11. Connors Double Seven — 7일 신저가 매수, 7일 신고가 매도, MA200 필터
12. Williams %R(2) — %R<-90 매수, >-20 매도
13. NR7 Breakout — 7일 최소 레인지 후 상단 돌파
14. MACD Histogram Reversal — 히스토그램 음→양 전환 매수
15. Cumulative RSI(2) 3일 — 3일 누적 RSI(2)<30 매수, >160 매도
16. 3일 연속 하락 반등 — 3일 연속 하락 매수, 종가>전일고가 매도
17. Engulfing + MA200 — 강세 감아안기 패턴 매수
18. Keltner Channel Reversion — Keltner 하단 터치 매수, 중앙 매도
19. ATR 수축→확장 — ATR 수축 후 확장+상승 매수
20. 대량거래 + 양봉 — 거래량 5배 + 양봉 매수, TP/SL 매도
+현재 시스템 (비교 기준)
"""
import json, os, sys, time
from pathlib import Path
from collections import defaultdict
from datetime import datetime

os.environ["PYTHONUNBUFFERED"] = "1"
DATA_PATH = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"
RESULT_PATH = Path(__file__).parent.parent / "results" / "backtest_10strategies_v2.json"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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

        # RSI(2) 3일 누적
        rsi2_list = []
        for offset in range(3):
            j = i - offset
            _g = _l = 0
            for k in (j-1, j):
                diff = closes[k] - closes[k-1]
                if diff > 0: _g += diff
                else: _l -= diff
            _ag, _al = _g/2, _l/2
            rsi2_list.append(100 - 100/(1+_ag/_al) if _al > 0 else 100.0)
        cum_rsi2_3 = sum(rsi2_list)

        # Williams %R(2) = (Highest High(2) - Close) / (Highest High(2) - Lowest Low(2)) * -100
        hh2 = max(highs[i-1:i+1])
        ll2 = min(lows[i-1:i+1])
        williams_r2 = ((hh2 - c) / (hh2 - ll2) * -100) if hh2 != ll2 else -50

        # MAs
        ma5 = sum(closes[i-4:i+1]) / 5
        ma20 = sum(closes[i-19:i+1]) / 20
        ma200 = sum(closes[i-199:i+1]) / 200
        prev_ma5 = sum(closes[i-5:i]) / 5
        prev_ma20 = sum(closes[i-20:i]) / 20

        # MACD (12, 26, 9) — 간소화: SMA 기반
        ema12 = sum(closes[i-11:i+1]) / 12
        ema26 = sum(closes[i-25:i+1]) / 26
        macd_line = ema12 - ema26
        # signal: 9일 평균 (간소화)
        macd_vals = []
        for k in range(i-8, i+1):
            e12 = sum(closes[k-11:k+1]) / 12
            e26 = sum(closes[k-25:k+1]) / 26
            macd_vals.append(e12 - e26)
        signal = sum(macd_vals) / 9
        histogram = macd_line - signal
        # 전일 히스토그램
        prev_hist = macd_vals[-2] - sum(macd_vals[:-1]) / 8 if len(macd_vals) >= 9 else 0

        # ATR(14)
        atr_sum = 0
        for k in range(i-13, i+1):
            tr = max(highs[k]-lows[k], abs(highs[k]-closes[k-1]), abs(lows[k]-closes[k-1]))
            atr_sum += tr
        atr14 = atr_sum / 14
        # ATR 20일 전
        atr_old = 0
        for k in range(i-33, i-19):
            tr = max(highs[k]-lows[k], abs(highs[k]-closes[k-1]), abs(lows[k]-closes[k-1]))
            atr_old += tr
        atr_old /= 14

        avg_vol_20 = sum(volumes[i-19:i+1]) / 20

        # Keltner Channel (MA20 ± 2*ATR14)
        kelt_upper = ma20 + 2 * atr14
        kelt_lower = ma20 - 2 * atr14

        # NR7: 오늘의 range가 최근 7일 중 최소
        ranges_7 = [highs[i-k] - lows[i-k] for k in range(7)]
        today_range = h - lo
        is_nr7 = today_range <= min(ranges_7)

        # 7일 고가/저가
        high_7d = max(highs[i-6:i+1])
        low_7d = min(lows[i-6:i+1])

        # 3일 연속 하락
        three_down = closes[i-2] < closes[i-3] and closes[i-1] < closes[i-2] and c < closes[i-1]

        # 강세 감아안기 (Bullish Engulfing)
        engulfing = (closes[i-1] < opens[i-1]) and (c > o) and (c > opens[i-1]) and (o < closes[i-1])

        results.append({
            "d": b.get("stck_bsop_date", ""),
            "c": c, "o": o, "h": h, "l": lo, "vol": vol,
            "rsi2": rsi2, "cum_rsi2_3": cum_rsi2_3,
            "wr2": williams_r2, "ma20": ma20, "ma200": ma200,
            "ma5": ma5, "prev_ma5": prev_ma5, "prev_ma20": prev_ma20,
            "hist": histogram, "prev_hist": prev_hist,
            "atr14": atr14, "atr_old": atr_old,
            "avg_vol_20": avg_vol_20,
            "kelt_lower": kelt_lower, "kelt_upper": kelt_upper,
            "is_nr7": is_nr7,
            "high_7d": high_7d, "low_7d": low_7d,
            "three_down": three_down, "engulfing": engulfing,
            "prev_high": highs[i-1], "prev_close": closes[i-1],
            "ok": 1000 <= c < 200000,
        })
    return results


# ── 전략 함수 ─────────────────────────────────────────────────

def strat_double_seven(ind, holding):
    """11. Connors Double Seven: 종가=7일 저가 매수, 종가=7일 고가 매도, MA200 필터"""
    if holding:
        return "sell" if ind["c"] >= ind["high_7d"] else "hold"
    if ind["c"] <= ind["low_7d"] and ind["c"] > ind["ma200"] and ind["ok"]:
        return "buy"
    return None

def strat_williams_r(ind, holding):
    """12. Williams %R(2): <-90 매수, >-20 매도"""
    if holding:
        return "sell" if ind["wr2"] > -20 else "hold"
    if ind["wr2"] < -90 and ind["c"] > ind["ma200"] and ind["ok"]:
        return "buy"
    return None

def strat_nr7_breakout(ind, holding):
    """13. NR7 Breakout: NR7일 후 전일고가 돌파 매수"""
    if holding:
        return "hold"
    if ind["is_nr7"] and ind["c"] > ind["prev_high"] and ind["c"] > ind["ma200"] and ind["ok"]:
        return "buy"
    return None

def strat_macd_reversal(ind, holding):
    """14. MACD Histogram: 음→양 전환 매수, 양→음 전환 매도"""
    if holding:
        return "sell" if ind["hist"] < 0 and ind["prev_hist"] >= 0 else "hold"
    if ind["hist"] > 0 and ind["prev_hist"] <= 0 and ind["c"] > ind["ma200"] and ind["ok"]:
        return "buy"
    return None

def strat_cum_rsi(ind, holding):
    """15. Cumulative RSI(2) 3일: 누적<30 매수, >160 매도"""
    if holding:
        return "sell" if ind["cum_rsi2_3"] > 160 else "hold"
    if ind["cum_rsi2_3"] < 30 and ind["c"] > ind["ma200"] and ind["ok"]:
        return "buy"
    return None

def strat_three_down(ind, holding):
    """16. 3일 연속 하락 반등: 3일 연속 하락 매수, 종가>전일고가 매도"""
    if holding:
        return "sell" if ind["c"] > ind["prev_high"] else "hold"
    if ind["three_down"] and ind["c"] > ind["ma200"] and ind["ok"]:
        return "buy"
    return None

def strat_engulfing(ind, holding):
    """17. Engulfing + MA200: 강세 감아안기 매수, 종가>전일고가 매도"""
    if holding:
        return "sell" if ind["c"] > ind["prev_high"] else "hold"
    if ind["engulfing"] and ind["c"] > ind["ma200"] and ind["ok"]:
        return "buy"
    return None

def strat_keltner(ind, holding):
    """18. Keltner Channel: 종가<하단 매수, 종가>MA20 매도"""
    if holding:
        return "sell" if ind["c"] > ind["ma20"] else "hold"
    if ind["c"] < ind["kelt_lower"] and ind["c"] > ind["ma200"] and ind["ok"]:
        return "buy"
    return None

def strat_atr_expansion(ind, holding):
    """19. ATR 수축→확장: ATR 현재 > ATR 20일전 × 1.5 + 상승 매수"""
    if holding:
        return "hold"
    if ind["atr_old"] > 0 and ind["atr14"] > ind["atr_old"] * 1.5:
        if ind["c"] > ind["prev_close"] and ind["c"] > ind["ma200"] and ind["ok"]:
            return "buy"
    return None

def strat_massive_volume_bullish(ind, holding):
    """20. 대량거래 양봉: 거래량 5배 + 양봉(종가>시가) 매수"""
    if holding:
        return "hold"
    if ind["vol"] > ind["avg_vol_20"] * 5 and ind["c"] > ind["o"] and ind["ok"]:
        return "buy"
    return None

def strat_current_system(ind, holding):
    """현재 시스템 (비교 기준)"""
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


STRATEGIES = [
    ("11.Double_Seven", strat_double_seven, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 15}),
    ("12.Williams_%R", strat_williams_r, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 15}),
    ("13.NR7_Breakout", strat_nr7_breakout, {"tp": 7, "sl": -2, "ts": -3, "max_hold": 5}),
    ("14.MACD_Reversal", strat_macd_reversal, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 20}),
    ("15.Cum_RSI(2)x3", strat_cum_rsi, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 15}),
    ("16.Three_Down", strat_three_down, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 10}),
    ("17.Engulfing+MA", strat_engulfing, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 10}),
    ("18.Keltner_Rev", strat_keltner, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 15}),
    ("19.ATR_Expansion", strat_atr_expansion, {"tp": 7, "sl": -2, "ts": -3, "max_hold": 5}),
    ("20.MassVol_Bull", strat_massive_volume_bullish, {"tp": 7, "sl": -2, "ts": -3, "max_hold": 5}),
    ("현재시스템", strat_current_system, {"tp": 7, "sl": -2, "ts": -3, "max_hold": 5}),
]


# ── 백테스트 엔진 ─────────────────────────────────────────────

def run_strategy(all_data, strat_fn, params, date_range=None, max_pos=2):
    tp, sl, ts, mh = params["tp"], params["sl"], params["ts"], params["max_hold"]
    date_stocks = defaultdict(dict)
    for code, inds in all_data.items():
        for ind in inds:
            if ind is None: continue
            d = ind["d"]
            if date_range and (d < date_range[0] or d > date_range[1]): continue
            date_stocks[d][code] = ind
    dates = sorted(date_stocks.keys())
    pnls = []
    holdings = {}
    for di, date in enumerate(dates):
        stocks = date_stocks[date]
        sold = set()
        for code in list(holdings.keys()):
            ind = stocks.get(code)
            if ind is None: continue
            bp, bi, pk = holdings[code]
            h, lo, c = ind["h"], ind["l"], ind["c"]
            hd = di - bi
            if h > pk: pk = h; holdings[code] = (bp, bi, pk)
            hp = (h-bp)/bp*100; lp = (lo-bp)/bp*100; cp = (c-bp)/bp*100
            drop = (c-pk)/pk*100 if pk > 0 else 0
            do_sell = False; sp = cp
            action = strat_fn(ind, True)
            if action == "sell": do_sell = True
            if tp > 0 and hp >= tp: do_sell = True; sp = tp
            if sl < 0 and lp <= sl: do_sell = True; sp = sl
            if ts < 0 and cp > 0 and drop <= ts: do_sell = True; sp = cp
            if mh > 0 and hd >= mh: do_sell = True
            if do_sell:
                pnls.append(round(sp, 2))
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
                pnls.append(round((ind["c"]-bp)/bp*100, 2))
    return pnls


def analyze(pnls):
    n = len(pnls)
    if n == 0: return {"n": 0, "wr": 0, "trim": 0, "sharpe": 0, "pf": 0, "mdd": 0, "med": 0}
    s = sorted(pnls)
    wins = sum(1 for p in pnls if p > 0)
    avg = sum(pnls) / n
    med = s[n//2]
    lo, hi = int(n*0.05), n-int(n*0.05)
    trim = sum(s[lo:hi])/(hi-lo) if hi > lo else avg
    std = (sum((p-avg)**2 for p in pnls)/n)**0.5 if n > 1 else 1
    cum = pk = mdd = 0
    for p in pnls:
        cum += p
        if cum > pk: pk = cum
        dd = pk - cum
        if dd > mdd: mdd = dd
    gp = sum(p for p in pnls if p > 0)
    gl = abs(sum(p for p in pnls if p < 0))
    return {"n": n, "wr": round(wins/n*100, 1), "trim": round(trim, 2), "med": round(med, 2),
            "sharpe": round(avg/std, 3) if std > 0 else 0,
            "pf": round(gp/gl, 2) if gl > 0 else 999, "mdd": round(mdd, 1)}


def main():
    print("=" * 90)
    print("추가 10대 전략 백테스트 + 현재 시스템 비교")
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
    print(f"유효: {len(all_data)}종목")

    all_dates = sorted({ind["d"] for inds in all_data.values() for ind in inds if ind})
    mid = len(all_dates) // 2
    train = (all_dates[0], all_dates[mid])
    test = (all_dates[mid+1], all_dates[-1])
    print(f"학습: {train[0]}~{train[1]} | 검증: {test[0]}~{test[1]}")

    print(f"\n{'전략':<22} | {'[학습] trim':>9} {'WR':>5} {'N':>5} {'SR':>6} {'PF':>5} | {'[검증] trim':>9} {'WR':>5} {'N':>5} {'SR':>6} {'PF':>5} | 일관")
    print("─" * 115)

    results = []
    for name, fn, params in STRATEGIES:
        tr_pnls = run_strategy(all_data, fn, params, date_range=train)
        te_pnls = run_strategy(all_data, fn, params, date_range=test)
        tr = analyze(tr_pnls)
        te = analyze(te_pnls)
        ok = "O" if tr["n"] >= 10 and te["n"] >= 10 and (tr["trim"] > 0) == (te["trim"] > 0) else "X"
        results.append({"name": name, "train": tr, "test": te, "consistent": ok})
        print(f"{name:<22} | {tr['trim']:>+8.2f}% {tr['wr']:>4.1f}% {tr['n']:>5} {tr['sharpe']:>6.3f} {tr['pf']:>5.2f} "
              f"| {te['trim']:>+8.2f}% {te['wr']:>4.1f}% {te['n']:>5} {te['sharpe']:>6.3f} {te['pf']:>5.2f} | {ok}")

    # Top 3
    ranked = sorted(results, key=lambda x: x["test"]["trim"], reverse=True)
    cur = next((r for r in results if "현재" in r["name"]), None)

    print(f"\n{'='*90}")
    print("검증기간 Top 3 + 현재 비교")
    print("─" * 90)
    for i, r in enumerate(ranked[:3], 1):
        te = r["test"]
        print(f"  {i}위: {r['name']} — trim={te['trim']:>+.2f}%, WR={te['wr']}%, N={te['n']}, "
              f"SR={te['sharpe']:.3f}, PF={te['pf']:.2f}, 일관={r['consistent']}")
    if cur:
        ce = cur["test"]
        print(f"\n  현재: {cur['name']} — trim={ce['trim']:>+.2f}%, WR={ce['wr']}%, N={ce['n']}, "
              f"SR={ce['sharpe']:.3f}, PF={ce['pf']:.2f}, 일관={cur['consistent']}")
        print(f"\n  Top3 vs 현재:")
        for i, r in enumerate(ranked[:3], 1):
            te = r["test"]
            print(f"    {i}위 {r['name']:22s}: trim {te['trim']-ce['trim']:>+.2f}%p, "
                  f"WR {te['wr']-ce['wr']:>+.1f}%p, SR {te['sharpe']:.3f} vs {ce['sharpe']:.3f}")

    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump({"generated_at": datetime.now().isoformat(), "strategies": [
            {"rank": i+1, **r} for i, r in enumerate(ranked)]}, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {RESULT_PATH}")


if __name__ == "__main__":
    main()
