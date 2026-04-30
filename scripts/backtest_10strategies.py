"""10대 자동매매 전략 백테스트 + 현재 전략 비교

데이터: daily_ohlcv_all.json (2,618종목 × 500일봉)
학습/검증 분리 (전반 50% / 후반 50%)
각 전략별 정확한 매매 규칙 → 개별 종목 단위 시뮬레이션

전략 목록:
1. RSI(2) Mean Reversion — RSI(2)<10 매수, >90 매도, MA200 필터
2. IBS Dip Buy — IBS<0.2 매수, 종가>전일고가 매도
3. Turnaround Tuesday — 월요일 종가 매수(2일 연속 하락 후), 종가>전일고가 매도
4. 5-Day Low + IBS — 5일 신저가 & IBS<0.25 매수, 종가>전일고가 매도
5. Bollinger Band Mean Reversion — 종가<하단밴드 매수, 종가>중앙밴드(MA20) 매도
6. Bollinger Squeeze Breakout — BBW 수축 후 상단 돌파+거래량 매수, ATR 기반 매도
7. Volume Breakout — 거래량 3배+20일 신고가 돌파 매수, 트레일링스톱 매도
8. Gap-Down Reversal — 갭다운 -3%+ 시가 매수, 당일 종가 매도
9. Golden Cross Momentum — MA5>MA20 교차 매수, MA5<MA20 교차 매도
10. 현재 전략 (5팩터+Criteria) — 모멘텀+저가주+수급+골든크로스+저항돌파 스코어링
"""
import json
import os
import sys
import time
from pathlib import Path
from collections import defaultdict
from datetime import datetime

os.environ["PYTHONUNBUFFERED"] = "1"

DATA_PATH = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"
RESULT_PATH = Path(__file__).parent.parent / "results" / "backtest_10strategies.json"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ══════════════════════════════════════════════════════════════
# 공통 지표 계산
# ══════════════════════════════════════════════════════════════

def prepare_stock(bars):
    """일봉 리스트 → 지표 포함 dict 리스트. 최소 201일 필요."""
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
            opens.append(o if o > 0 else (opens[-1] if opens else 0))
            highs.append(h if h > 0 else (highs[-1] if highs else 0))
            lows.append(lo if lo > 0 else (lows[-1] if lows else 0))
            volumes.append(0)
            results.append(None)
            continue

        closes.append(c)
        opens.append(o)
        highs.append(h)
        lows.append(lo)
        volumes.append(vol)

        if i < 200:
            results.append(None)
            continue

        # IBS (Internal Bar Strength) = (close - low) / (high - low)
        ibs = (c - lo) / (h - lo) if h != lo else 0.5

        # RSI(2)
        g = l = 0
        for k in (i - 1, i):
            diff = closes[k] - closes[k - 1]
            if diff > 0: g += diff
            else: l -= diff
        ag, al = g / 2, l / 2
        rsi2 = 100 - 100 / (1 + ag / al) if al > 0 else 100.0

        # MAs
        ma5 = sum(closes[i-4:i+1]) / 5
        ma20 = sum(closes[i-19:i+1]) / 20
        ma200 = sum(closes[i-199:i+1]) / 200

        # Bollinger Bands (20, 2)
        bb_slice = closes[i-19:i+1]
        bb_mean = ma20
        bb_std = (sum((x - bb_mean)**2 for x in bb_slice) / 20) ** 0.5
        bb_upper = bb_mean + 2 * bb_std
        bb_lower = bb_mean - 2 * bb_std
        bbw = (bb_upper - bb_lower) / bb_mean * 100 if bb_mean > 0 else 0

        # ATR(14)
        atr_sum = 0
        for k in range(i-13, i+1):
            tr = max(highs[k] - lows[k], abs(highs[k] - closes[k-1]), abs(lows[k] - closes[k-1]))
            atr_sum += tr
        atr14 = atr_sum / 14

        # Volume avg 20
        avg_vol_20 = sum(volumes[i-19:i+1]) / 20 if i >= 20 else vol

        # 5-day low
        low_5d = min(lows[i-4:i+1])

        # Previous day values
        prev_high = highs[i-1]
        prev_close = closes[i-1]
        prev_prev_close = closes[i-2] if i >= 2 else prev_close

        # Day of week (0=Mon ... 6=Sun)
        date_str = b.get("stck_bsop_date", "")
        dow = None
        if len(date_str) == 8:
            try:
                dow = datetime.strptime(date_str, "%Y%m%d").weekday()
            except:
                pass

        # BBW percentile (last 120 days)
        if i >= 120:
            recent_bbws = []
            # 간소화: 직전 20일의 BBW만 비교
            for k in range(max(0, i-119), i+1):
                sl = closes[k-19:k+1] if k >= 19 else closes[:k+1]
                if len(sl) >= 20:
                    m = sum(sl) / len(sl)
                    s = (sum((x-m)**2 for x in sl) / len(sl)) ** 0.5
                    recent_bbws.append((m + 2*s - (m - 2*s)) / m * 100 if m > 0 else 0)
            bbw_pctl = sum(1 for w in recent_bbws if w < bbw) / len(recent_bbws) * 100 if recent_bbws else 50
        else:
            bbw_pctl = 50

        # Prev MA5
        prev_ma5 = sum(closes[i-5:i]) / 5 if i >= 5 else ma5
        prev_ma20 = sum(closes[i-20:i]) / 20 if i >= 20 else ma20

        results.append({
            "d": date_str, "c": c, "o": o, "h": h, "l": lo,
            "vol": vol, "ibs": ibs, "rsi2": rsi2,
            "ma5": ma5, "ma20": ma20, "ma200": ma200,
            "bb_upper": bb_upper, "bb_lower": bb_lower, "bb_mean": bb_mean,
            "bbw": bbw, "bbw_pctl": bbw_pctl, "atr14": atr14,
            "avg_vol_20": avg_vol_20, "low_5d": low_5d,
            "prev_high": prev_high, "prev_close": prev_close,
            "prev_prev_close": prev_prev_close,
            "dow": dow, "prev_ma5": prev_ma5, "prev_ma20": prev_ma20,
            "price_ok": 1000 <= c < 200000,
        })

    return results


# ══════════════════════════════════════════════════════════════
# 전략 정의
# ══════════════════════════════════════════════════════════════

def strat_rsi2_reversion(ind, prev_holding):
    """1. RSI(2) Mean Reversion: RSI(2)<10 & 종가>MA200 매수, RSI(2)>90 매도"""
    if prev_holding:
        return "sell" if ind["rsi2"] > 90 else "hold"
    if ind["rsi2"] < 10 and ind["c"] > ind["ma200"] and ind["price_ok"]:
        return "buy"
    return None

def strat_ibs_dip(ind, prev_holding):
    """2. IBS Dip Buy: IBS<0.2 매수, 종가>전일고가 매도"""
    if prev_holding:
        return "sell" if ind["c"] > ind["prev_high"] else "hold"
    if ind["ibs"] < 0.2 and ind["c"] > ind["ma200"] and ind["price_ok"]:
        return "buy"
    return None

def strat_turnaround_tuesday(ind, prev_holding):
    """3. Turnaround Tuesday: 월요일+2일연속하락 매수, 종가>전일고가 매도"""
    if prev_holding:
        return "sell" if ind["c"] > ind["prev_high"] else "hold"
    if ind["dow"] == 0 and ind["prev_close"] < ind["prev_prev_close"] and ind["c"] < ind["prev_close"] and ind["price_ok"]:
        return "buy"
    return None

def strat_5day_low_ibs(ind, prev_holding):
    """4. 5-Day Low + IBS: 종가<5일저가 & IBS<0.25 매수, 종가>전일고가 매도"""
    if prev_holding:
        return "sell" if ind["c"] > ind["prev_high"] else "hold"
    if ind["c"] <= ind["low_5d"] and ind["ibs"] < 0.25 and ind["price_ok"]:
        return "buy"
    return None

def strat_bb_reversion(ind, prev_holding):
    """5. Bollinger Band Mean Reversion: 종가<하단밴드 매수, 종가>MA20 매도"""
    if prev_holding:
        return "sell" if ind["c"] > ind["bb_mean"] else "hold"
    if ind["c"] < ind["bb_lower"] and ind["c"] > ind["ma200"] and ind["price_ok"]:
        return "buy"
    return None

def strat_bb_squeeze(ind, prev_holding):
    """6. Bollinger Squeeze Breakout: BBW하위20%→상단돌파+거래량 매수, ATR TS 매도"""
    if prev_holding:
        # ATR trailing: 고점 - 2*ATR 이하로 하락 시 매도, 최대 10일 보유
        return "hold"  # 매도는 엔진에서 max_hold+trailing로 처리
    if ind["bbw_pctl"] < 20 and ind["c"] > ind["bb_upper"] and ind["vol"] > ind["avg_vol_20"] * 1.5 and ind["price_ok"]:
        return "buy"
    return None

def strat_volume_breakout(ind, prev_holding):
    """7. Volume Breakout: 거래량3배+20일신고가 매수, 트레일링스톱 매도"""
    if prev_holding:
        return "hold"
    if ind["vol"] > ind["avg_vol_20"] * 3 and ind["c"] > ind["prev_high"] and ind["price_ok"]:
        # 20일 신고가 확인은 간소화 (전일 고가 돌파로 대체)
        return "buy"
    return None

def strat_gap_down_reversal(ind, prev_holding):
    """8. Gap-Down Reversal: 시가가 전일종가 대비 -3% 갭다운 매수, 당일종가 매도"""
    if prev_holding:
        return "sell"  # 항상 당일 매도
    gap = (ind["o"] - ind["prev_close"]) / ind["prev_close"] * 100 if ind["prev_close"] > 0 else 0
    if gap <= -3 and ind["price_ok"]:
        return "buy"
    return None

def strat_golden_cross(ind, prev_holding):
    """9. Golden Cross Momentum: MA5>MA20 교차 매수, MA5<MA20 교차 매도"""
    if prev_holding:
        if ind["ma5"] < ind["ma20"] and ind["prev_ma5"] >= ind["prev_ma20"]:
            return "sell"
        return "hold"
    if ind["ma5"] > ind["ma20"] and ind["prev_ma5"] <= ind["prev_ma20"] and ind["price_ok"]:
        return "buy"
    return None

def strat_current_system(ind, prev_holding):
    """10. 현재 시스템 근사: 모멘텀+저가주+수급+골든크로스+저항돌파 스코어링"""
    if prev_holding:
        return "hold"
    score = 0
    c = ind["c"]
    # 모멘텀 (5일 상승)
    if c > ind["prev_close"]: score += 5
    # 저가주
    if c < 20000: score += 5
    # 수급 (거래량 증가)
    if ind["vol"] > ind["avg_vol_20"] * 1.5: score += 10
    # 골든크로스
    if ind["ma5"] > ind["ma20"] and ind["prev_ma5"] <= ind["prev_ma20"]: score += 5
    # 저항돌파
    if c > ind["prev_high"]: score += 5
    if score >= 15 and ind["price_ok"]:
        return "buy"
    return None


STRATEGIES = [
    ("1.RSI(2)Reversion", strat_rsi2_reversion, {"tp": 0, "sl": 0, "ts": 0, "max_hold": 20}),
    ("2.IBS_Dip", strat_ibs_dip, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 10}),
    ("3.Turnaround_Tue", strat_turnaround_tuesday, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 10}),
    ("4.5DayLow+IBS", strat_5day_low_ibs, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 10}),
    ("5.BB_Reversion", strat_bb_reversion, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 15}),
    ("6.BB_Squeeze", strat_bb_squeeze, {"tp": 10, "sl": -3, "ts": -5, "max_hold": 10}),
    ("7.Vol_Breakout", strat_volume_breakout, {"tp": 7, "sl": -2, "ts": -3, "max_hold": 5}),
    ("8.GapDown_Rev", strat_gap_down_reversal, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 1}),
    ("9.Golden_Cross", strat_golden_cross, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 30}),
    ("10.Current_System", strat_current_system, {"tp": 7, "sl": -2, "ts": -3, "max_hold": 5}),
]


# ══════════════════════════════════════════════════════════════
# 백테스트 엔진
# ══════════════════════════════════════════════════════════════

def run_strategy(all_data, strat_fn, params, date_range=None, max_positions=2):
    """전략 함수를 모든 종목에 적용하여 거래 리스트 반환"""
    tp, sl, ts_pct, max_hold = params["tp"], params["sl"], params["ts"], params["max_hold"]
    trades = []
    holdings = {}  # code → (buy_price, buy_idx, peak, global_di)

    # 날짜별 인덱스 구축
    date_stocks = defaultdict(dict)
    for code, inds in all_data.items():
        for ind in inds:
            if ind is None:
                continue
            d = ind["d"]
            if date_range and (d < date_range[0] or d > date_range[1]):
                continue
            date_stocks[d][code] = ind

    dates = sorted(date_stocks.keys())

    for di, date in enumerate(dates):
        stocks = date_stocks[date]

        # 1) 보유 종목 체크
        sold_today = set()
        for code in list(holdings.keys()):
            ind = stocks.get(code)
            if ind is None:
                continue

            bp, bi, peak, _ = holdings[code]
            h, lo, c = ind["h"], ind["l"], ind["c"]
            hold_days = di - bi

            if h > peak:
                peak = h
                holdings[code] = (bp, bi, peak, di)

            high_pnl = (h - bp) / bp * 100
            low_pnl = (lo - bp) / bp * 100
            close_pnl = (c - bp) / bp * 100
            drop = (c - peak) / peak * 100 if peak > 0 else 0

            sell = False
            sell_pnl = close_pnl

            # 전략 자체 매도 시그널
            action = strat_fn(ind, True)
            if action == "sell":
                sell = True

            # TP/SL/TS
            if tp > 0 and high_pnl >= tp:
                sell = True; sell_pnl = tp
            if sl < 0 and low_pnl <= sl:
                sell = True; sell_pnl = sl
            if ts_pct < 0 and close_pnl > 0 and drop <= ts_pct:
                sell = True; sell_pnl = close_pnl
            if max_hold > 0 and hold_days >= max_hold:
                sell = True

            if sell:
                trades.append(round(sell_pnl, 2))
                del holdings[code]
                sold_today.add(code)

        # 2) 신규 매수
        if len(holdings) >= max_positions:
            continue

        candidates = []
        for code, ind in stocks.items():
            if code in holdings or code in sold_today:
                continue
            action = strat_fn(ind, False)
            if action == "buy":
                candidates.append((code, ind))

        # 거래대금 순 정렬
        candidates.sort(key=lambda x: -x[1].get("vol", 0))
        slots = max_positions - len(holdings)
        for code, ind in candidates[:slots]:
            buy_price = ind["c"]
            if strat_fn == strat_gap_down_reversal:
                buy_price = ind["o"]  # 갭다운은 시가 매수
            holdings[code] = (buy_price, di, buy_price, di)

    # 미청산
    if dates:
        last_stocks = date_stocks[dates[-1]]
        for code, (bp, bi, pk, _) in holdings.items():
            ind = last_stocks.get(code)
            if ind:
                pnl = (ind["c"] - bp) / bp * 100
                trades.append(round(pnl, 2))

    return trades


def analyze(pnls):
    if not pnls:
        return {"total": 0, "win_rate": 0, "avg": 0, "med": 0, "trim": 0,
                "total_pnl": 0, "mdd": 0, "sharpe": 0, "pf": 0}
    n = len(pnls)
    s = sorted(pnls)
    wins = sum(1 for p in pnls if p > 0)
    med = s[n // 2]
    lo, hi = int(n * 0.05), n - int(n * 0.05)
    trimmed = s[lo:hi] if hi > lo else s
    trim_avg = sum(trimmed) / len(trimmed) if trimmed else 0
    avg = sum(pnls) / n
    std = (sum((p - avg)**2 for p in pnls) / n) ** 0.5 if n > 1 else 1
    cum = pk = mdd = 0
    for p in pnls:
        cum += p
        if cum > pk: pk = cum
        dd = pk - cum
        if dd > mdd: mdd = dd
    gp = sum(p for p in pnls if p > 0)
    gl = abs(sum(p for p in pnls if p < 0))
    return {
        "total": n, "win_rate": round(wins/n*100, 1),
        "avg": round(avg, 2), "med": round(med, 2), "trim": round(trim_avg, 2),
        "total_pnl": round(sum(pnls), 1), "mdd": round(mdd, 1),
        "sharpe": round(avg/std, 3) if std > 0 else 0,
        "pf": round(gp/gl, 2) if gl > 0 else 999,
    }


def main():
    print("=" * 80)
    print("10대 자동매매 전략 백테스트 (학습/검증 분리)")
    print("=" * 80)

    data = load_json(DATA_PATH)
    print(f"원본: {len(data)}종목")

    # 유효 종목 필터 (300일+, 거래대금 10억+)
    all_data = {}
    for code, info in data.items():
        bars = info.get("bars", [])
        if len(bars) < 300:
            continue
        tvs = [int(b.get("acml_tr_pbmn", "0")) for b in bars[-100:]]
        if sum(tvs) / len(tvs) < 1_000_000_000:
            continue
        inds = prepare_stock(bars)
        if inds:
            all_data[code] = inds

    print(f"유효: {len(all_data)}종목")

    # 날짜 범위
    all_dates = set()
    for inds in all_data.values():
        for ind in inds:
            if ind: all_dates.add(ind["d"])
    dates = sorted(all_dates)
    mid = len(dates) // 2
    train_range = (dates[0], dates[mid])
    test_range = (dates[mid+1], dates[-1])
    print(f"전체: {dates[0]}~{dates[-1]} ({len(dates)}일)")
    print(f"학습: {train_range[0]}~{train_range[1]}")
    print(f"검증: {test_range[0]}~{test_range[1]}")

    # 전략별 백테스트
    print(f"\n{'='*80}")
    print(f"{'전략':<22} | {'[학습] trim':>9} {'WR':>5} {'N':>5} {'SR':>6} {'PF':>5} | {'[검증] trim':>9} {'WR':>5} {'N':>5} {'SR':>6} {'PF':>5} | 일관")
    print("─" * 115)

    results = []
    t0 = time.time()

    for name, fn, params in STRATEGIES:
        tr_pnls = run_strategy(all_data, fn, params, date_range=train_range)
        te_pnls = run_strategy(all_data, fn, params, date_range=test_range)
        tr = analyze(tr_pnls)
        te = analyze(te_pnls)
        consistent = "O" if (tr["trim"] > 0) == (te["trim"] > 0) and tr["total"] >= 10 and te["total"] >= 10 else "X"

        results.append({
            "name": name, "train": tr, "test": te, "consistent": consistent,
        })

        print(f"{name:<22} | {tr['trim']:>+8.2f}% {tr['win_rate']:>4.1f}% {tr['total']:>5} {tr['sharpe']:>6.3f} {tr['pf']:>5.2f} "
              f"| {te['trim']:>+8.2f}% {te['win_rate']:>4.1f}% {te['total']:>5} {te['sharpe']:>6.3f} {te['pf']:>5.2f} | {consistent}")

    elapsed = time.time() - t0
    print(f"\n소요: {elapsed:.0f}초")

    # 검증기간 trimmed_avg 기준 TOP 3
    ranked = sorted(results, key=lambda x: x["test"]["trim"], reverse=True)
    print(f"\n{'='*80}")
    print("검증기간 Top 3 전략")
    print("─" * 80)
    for i, r in enumerate(ranked[:3], 1):
        te = r["test"]
        print(f"  {i}위: {r['name']}")
        print(f"    검증: trim={te['trim']:>+.2f}%, WR={te['win_rate']}%, N={te['total']}, "
              f"Sharpe={te['sharpe']:.3f}, PF={te['pf']:.2f}, MDD={te['mdd']:.1f}%")

    # 현재 전략과 비교
    current = next((r for r in results if "Current" in r["name"]), None)
    if current:
        print(f"\n  현재: {current['name']}")
        ce = current["test"]
        print(f"    검증: trim={ce['trim']:>+.2f}%, WR={ce['win_rate']}%, N={ce['total']}, "
              f"Sharpe={ce['sharpe']:.3f}, PF={ce['pf']:.2f}, MDD={ce['mdd']:.1f}%")

    print(f"\n{'='*80}")
    print("Top3 vs 현재 전략 비교")
    print("─" * 80)
    if current:
        ce = current["test"]
        for i, r in enumerate(ranked[:3], 1):
            te = r["test"]
            diff_trim = te["trim"] - ce["trim"]
            diff_wr = te["win_rate"] - ce["win_rate"]
            print(f"  {i}위 {r['name']:22s}: trim {diff_trim:>+.2f}%p, WR {diff_wr:>+.1f}%p, "
                  f"Sharpe {te['sharpe']:.3f} vs {ce['sharpe']:.3f}")

    # 저장
    save_data = {
        "generated_at": datetime.now().isoformat(),
        "universe": len(all_data),
        "date_range": f"{dates[0]}~{dates[-1]}",
        "train_range": f"{train_range[0]}~{train_range[1]}",
        "test_range": f"{test_range[0]}~{test_range[1]}",
        "strategies": [
            {"rank": i+1, "name": r["name"], "train": r["train"], "test": r["test"], "consistent": r["consistent"]}
            for i, r in enumerate(ranked)
        ],
    }
    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {RESULT_PATH}")


if __name__ == "__main__":
    main()
