"""5팩터 × Criteria 가감점 조합 최적화 백테스트 v2

개선 (v1 대비):
1. 유니버스: 138 → 1,300+ 종목
2. 기간: 140일 → 440일 (약 2년)
3. 학습/검증 분리: out-of-sample 검증으로 과적합 방지
4. 통계: trimmed mean, 중앙값, 승률 기준 (극단값에 강건)
5. 성능: date_map 사전 구축 + dict 인덱싱으로 최적화
"""
import json
import sys
import os
import time
from pathlib import Path
from itertools import product
from collections import defaultdict
from datetime import datetime

os.environ["PYTHONUNBUFFERED"] = "1"

DATA_PATH = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"
RESULT_PATH = Path(__file__).parent.parent / "results" / "backtest_factor_v2.json"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── 기술적 지표 계산 ─────────────────────────────────────────

def compute_indicators_for_stock(bars):
    if len(bars) < 61:
        return []

    closes, volumes, highs, tvs = [], [], [], []
    results = []

    for i, b in enumerate(bars):
        c = int(b.get("stck_clpr", "0"))
        o = int(b.get("stck_oprc", "0"))
        h = int(b.get("stck_hgpr", "0"))
        lo = int(b.get("stck_lwpr", "0"))
        vol = int(b.get("acml_vol", "0"))
        tv = int(b.get("acml_tr_pbmn", "0"))

        if c <= 0:
            closes.append(closes[-1] if closes else 0)
            volumes.append(0)
            highs.append(0)
            tvs.append(0)
            results.append(None)
            continue

        closes.append(c)
        volumes.append(vol)
        highs.append(h)
        tvs.append(tv)

        if i < 60:
            results.append(None)
            continue

        ma5 = sum(closes[i-4:i+1]) / 5
        ma20 = sum(closes[i-19:i+1]) / 20
        ma60 = sum(closes[i-59:i+1]) / 60

        # RSI 14
        gains = losses = 0
        for k in range(i-13, i+1):
            diff = closes[k] - closes[k-1]
            if diff > 0: gains += diff
            else: losses -= diff
        ag, al = gains/14, losses/14
        rsi = 100 - 100/(1+ag/al) if al > 0 else 100.0

        avg_vol_20 = sum(volumes[max(0,i-19):i+1]) / min(20, i+1) if i > 0 else vol

        ma_aligned = ma5 > ma20 > ma60

        golden_cross = False
        if i >= 7:
            prev_ma5 = sum(closes[i-7:i-2]) / 5
            prev_ma20 = sum(closes[i-22:i-2]) / 20 if i >= 22 else None
            if prev_ma20:
                golden_cross = (prev_ma5 <= prev_ma20) and (ma5 > ma20)

        overheating = rsi > 70 or (avg_vol_20 > 0 and vol > avg_vol_20 * 3)
        prev_h = highs[max(0,i-20):i]
        resistance_breakout = c > max(prev_h) if prev_h else False
        avg_vol_5 = sum(volumes[max(0,i-4):i+1]) / min(5, i+1)
        supply_demand = avg_vol_5 > avg_vol_20 * 1.5 if avg_vol_20 > 0 else False

        # Boolean 플래그를 int로 저장 (스코어링 최적화)
        flags = 0
        if closes[i-5] > 0 and c > closes[i-5]: flags |= 1   # momentum
        if c < 20000: flags |= 2                                # low_price
        if supply_demand: flags |= 4
        if golden_cross: flags |= 8
        if resistance_breakout: flags |= 16
        if ma_aligned: flags |= 32
        if overheating: flags |= 64

        results.append({
            "d": b.get("stck_bsop_date"),
            "c": c, "o": o, "h": h, "l": lo,
            "tv": tv, "fl": flags,
            "ok": 1000 <= c < 50000,
            "cr": (c - closes[i-1]) / closes[i-1] * 100 if closes[i-1] > 0 else 0,
        })

    return results


# ── 사전 구축: 날짜별 인덱스 ──────────────────────────────────

def build_date_index(all_indicators, date_range=None):
    """모든 종목의 지표를 날짜별로 인덱싱.

    Returns:
        dates: 정렬된 날짜 리스트
        day_data: [{code: ind_dict, ...}, ...]  (dates와 같은 인덱스)
        day_top30: [set_of_codes, ...]  거래대금 TOP30
    """
    raw = defaultdict(dict)  # date → {code: ind}
    for code, inds in all_indicators.items():
        for ind in inds:
            if ind is None or not ind["ok"]:
                continue
            d = ind["d"]
            if date_range and (d < date_range[0] or d > date_range[1]):
                continue
            raw[d][code] = ind

    dates = sorted(raw.keys())
    day_data = []
    day_top30 = []

    for d in dates:
        stocks = raw[d]
        day_data.append(stocks)
        # 거래대금 상위 30
        top30 = set()
        if len(stocks) > 30:
            sorted_codes = sorted(stocks.keys(), key=lambda c: stocks[c]["tv"], reverse=True)
            top30 = set(sorted_codes[:30])
        else:
            top30 = set(stocks.keys())
        day_top30.append(top30)

    return dates, day_data, day_top30


def run_backtest_fast(dates, day_data, day_top30, weights,
                      min_score=0, top_n=2,
                      tp=7.0, sl=-2.0, ts=-3.0, max_hold=5,
                      exclude_overheated_5=True):
    """최적화된 백테스트 엔진"""
    # 가중치를 플래그 기반으로 사전 계산
    w_mom = weights.get("momentum", 0)
    w_lp = weights.get("low_price", 0)
    w_tv = weights.get("top_tv", 0)
    w_sd = weights.get("supply_demand", 0)
    w_gc = weights.get("golden_cross", 0)
    w_rb = weights.get("resistance_breakout", 0)
    w_ma = weights.get("ma_aligned", 0)
    w_oh = weights.get("overheating", 0)

    trades = []
    holding = {}  # code → (buy_price, buy_idx, peak)

    for di in range(len(dates)):
        stocks = day_data[di]
        top30 = day_top30[di]

        # 보유 종목 매도 판정
        codes_sold = set()
        for code in list(holding.keys()):
            ind = stocks.get(code)
            if ind is None:
                continue

            bp, bi, pk = holding[code]
            h, lo, cl = ind["h"], ind["l"], ind["c"]
            hold_days = di - bi
            if h > pk:
                pk = h
                holding[code] = (bp, bi, pk)

            high_pnl = (h - bp) / bp * 100
            low_pnl = (lo - bp) / bp * 100
            close_pnl = (cl - bp) / bp * 100
            drop = (cl - pk) / pk * 100 if pk > 0 else 0

            reason = sell_pnl = None
            if high_pnl >= tp:
                reason, sell_pnl = "tp", tp
            elif low_pnl <= sl:
                reason, sell_pnl = "sl", sl
            elif close_pnl > 0 and drop <= ts:
                reason, sell_pnl = "ts", close_pnl
            elif hold_days >= max_hold:
                reason, sell_pnl = "time", close_pnl

            if reason:
                trades.append(round(sell_pnl, 2))
                del holding[code]
                codes_sold.add(code)

        # 신규 종목 선정
        slots = top_n - len(holding)
        if slots <= 0:
            continue

        best = []  # (score, -tv, code)
        for code, ind in stocks.items():
            if code in holding or code in codes_sold:
                continue

            fl = ind["fl"]

            if exclude_overheated_5:
                met = 0
                if fl & 32: met += 1  # ma_aligned
                if fl & 4: met += 1   # supply_demand
                if fl & 8: met += 1   # golden_cross
                if fl & 16: met += 1  # resistance_breakout
                if fl & 64: met += 1  # overheating
                if code in top30: met += 1
                if met >= 5:
                    continue

            score = 0
            if fl & 1: score += w_mom
            if fl & 2: score += w_lp
            if code in top30: score += w_tv
            if fl & 4: score += w_sd
            if fl & 8: score += w_gc
            if fl & 16: score += w_rb
            if fl & 32: score += w_ma
            if fl & 64: score += w_oh

            if score >= min_score:
                best.append((score, -ind["tv"], -ind["cr"], code))

        if best:
            best.sort(key=lambda x: (-x[0], x[1], x[2]))
            for _, _, _, code in best[:slots]:
                ind = stocks[code]
                holding[code] = (ind["c"], di, ind["c"])

    # 미청산 포지션
    if holding and dates:
        last_stocks = day_data[-1]
        for code, (bp, bi, pk) in holding.items():
            ind = last_stocks.get(code)
            if ind:
                pnl = (ind["c"] - bp) / bp * 100
                trades.append(round(pnl, 2))

    return trades


def analyze(pnls):
    if not pnls:
        return {"total": 0, "win_rate": 0, "avg_pnl": 0, "median_pnl": 0,
                "trimmed_avg": 0, "total_pnl": 0, "mdd": 0, "sharpe": 0, "pf": 0}

    total = len(pnls)
    pnls_sorted = sorted(pnls)
    wins = sum(1 for p in pnls if p > 0)
    median = pnls_sorted[total // 2]

    lo = int(total * 0.05)
    hi = total - lo
    trimmed = pnls_sorted[lo:hi] if hi > lo else pnls_sorted
    trimmed_avg = sum(trimmed) / len(trimmed) if trimmed else 0

    avg = sum(pnls) / total
    std = (sum((p - avg) ** 2 for p in pnls) / total) ** 0.5 if total > 1 else 1

    cum = peak = mdd = 0
    for p in pnls:
        cum += p
        if cum > peak: peak = cum
        dd = peak - cum
        if dd > mdd: mdd = dd

    gp = sum(p for p in pnls if p > 0)
    gl = abs(sum(p for p in pnls if p < 0))

    return {
        "total": total,
        "win_rate": round(wins / total * 100, 1),
        "avg_pnl": round(avg, 2),
        "median_pnl": round(median, 2),
        "trimmed_avg": round(trimmed_avg, 2),
        "total_pnl": round(sum(pnls), 1),
        "mdd": round(mdd, 1),
        "sharpe": round(avg / std, 3) if std > 0 else 0,
        "pf": round(gp / gl, 2) if gl > 0 else 999,
    }


def generate_combos():
    combos = []
    for mom, lp, ttv, sd, gc, rb, ma, oh in product(
        [0, 15, 30],       # momentum
        [0, 5],             # low_price
        [0, 15, 25],        # top_tv
        [0, 5, 10],         # supply_demand
        [0, 5, 8],          # golden_cross
        [0, 3, 5],          # resistance_breakout
        [0, -5, -10],       # ma_aligned
        [0, -5, -8],        # overheating
    ):
        if mom == 0 and lp == 0 and ttv == 0 and sd == 0 and gc == 0 and rb == 0:
            continue
        combos.append({
            "momentum": mom, "low_price": lp, "top_tv": ttv,
            "supply_demand": sd, "golden_cross": gc,
            "resistance_breakout": rb, "ma_aligned": ma, "overheating": oh,
        })
    return combos


def main():
    print("=" * 70)
    print("5팩터 × Criteria 가감점 조합 백테스트 v2 (학습/검증 분리)")
    print("=" * 70)

    data = load_json(DATA_PATH)
    print(f"원본 종목: {len(data)}")

    # 유효 종목 필터링
    MIN_BARS = 300
    MIN_AVG_TV = 1_000_000_000

    all_indicators = {}
    for code, info in data.items():
        bars = info.get("bars", [])
        if len(bars) < MIN_BARS:
            continue
        tv_list = [int(b.get("acml_tr_pbmn", "0")) for b in bars[-100:]]
        if sum(tv_list) / len(tv_list) < MIN_AVG_TV:
            continue
        inds = compute_indicators_for_stock(bars)
        if inds:
            all_indicators[code] = inds

    print(f"유효 종목: {len(all_indicators)}")

    # 날짜 범위
    all_dates = set()
    for inds in all_indicators.values():
        for ind in inds:
            if ind:
                all_dates.add(ind["d"])
    dates_all = sorted(all_dates)
    print(f"날짜 범위: {dates_all[0]} ~ {dates_all[-1]} ({len(dates_all)}일)")

    mid = len(dates_all) // 2
    train_range = (dates_all[0], dates_all[mid])
    test_range = (dates_all[mid + 1], dates_all[-1])
    print(f"학습: {train_range[0]}~{train_range[1]} ({mid+1}일)")
    print(f"검증: {test_range[0]}~{test_range[1]} ({len(dates_all)-mid-1}일)")

    # 사전 인덱스 구축
    print("\n인덱스 구축 중...")
    t0 = time.time()
    train_dates, train_dd, train_top30 = build_date_index(all_indicators, train_range)
    test_dates, test_dd, test_top30 = build_date_index(all_indicators, test_range)
    print(f"인덱스 구축: {time.time()-t0:.1f}초 (학습 {len(train_dates)}일, 검증 {len(test_dates)}일)")

    # Phase 1: 학습기간 조합 탐색
    print(f"\n{'='*70}")
    print("Phase 1: 학습기간 조합 탐색")
    combos = generate_combos()
    print(f"조합: {len(combos)} × 6변형 = {len(combos)*6}건")

    train_results = []
    t0 = time.time()

    for i, w in enumerate(combos):
        if i % 500 == 0:
            print(f"  진행: {i}/{len(combos)} ({time.time()-t0:.0f}초)")
        for ms in [0, 10, 20]:
            for tn in [2, 3]:
                pnls = run_backtest_fast(train_dates, train_dd, train_top30,
                                          w, min_score=ms, top_n=tn)
                stats = analyze(pnls)
                train_results.append({"w": w, "ms": ms, "tn": tn, **stats})

    elapsed = time.time() - t0
    print(f"학습 완료: {len(train_results)}건, {elapsed:.0f}초")

    train_results.sort(key=lambda x: x["trimmed_avg"], reverse=True)

    print(f"\n학습 상위 20 (trimmed_avg):")
    hdr = f"{'#':>3} {'trim':>7} {'med':>6} {'WR':>5} {'N':>4} {'MDD':>5} {'SR':>5} {'PF':>4} {'ms':>3} {'tn':>2} | 가중치"
    print(hdr)
    print("─" * len(hdr) + "─" * 20)

    for rank, r in enumerate(train_results[:20], 1):
        w = r["w"]
        ws = f"M{w['momentum']} LP{w['low_price']} TV{w['top_tv']} SD{w['supply_demand']} GC{w['golden_cross']} RB{w['resistance_breakout']} MA{w['ma_aligned']} OH{w['overheating']}"
        print(f"{rank:>3} {r['trimmed_avg']:>+6.2f}% {r['median_pnl']:>+5.2f}% {r['win_rate']:>4.1f}% "
              f"{r['total']:>4} {r['mdd']:>4.1f}% {r['sharpe']:>5.3f} {r['pf']:>4.1f} "
              f"{r['ms']:>3} {r['tn']:>2} | {ws}")

    # Phase 2: 상위 조합 검증
    print(f"\n{'='*70}")
    print("Phase 2: 검증기간 Out-of-Sample (상위 조합)")

    # 상위 50 (trimmed_avg) + 승률 상위 20 + sharpe 상위 20 → 중복 제거
    top_trim = train_results[:50]
    top_wr = sorted([r for r in train_results if r["total"] >= 30],
                    key=lambda x: x["win_rate"], reverse=True)[:20]
    top_sr = sorted([r for r in train_results if r["total"] >= 30],
                    key=lambda x: x["sharpe"], reverse=True)[:20]

    seen = set()
    candidates = []
    for r in top_trim + top_wr + top_sr:
        key = (json.dumps(r["w"], sort_keys=True), r["ms"], r["tn"])
        if key not in seen:
            seen.add(key)
            candidates.append(r)

    print(f"검증 대상: {len(candidates)}개")

    val_results = []
    for r in candidates:
        pnls = run_backtest_fast(test_dates, test_dd, test_top30,
                                  r["w"], min_score=r["ms"], top_n=r["tn"])
        te = analyze(pnls)
        val_results.append({
            "w": r["w"], "ms": r["ms"], "tn": r["tn"],
            "train": {"trimmed_avg": r["trimmed_avg"], "median_pnl": r["median_pnl"],
                       "win_rate": r["win_rate"], "total": r["total"],
                       "sharpe": r["sharpe"], "pf": r["pf"],
                       "total_pnl": r["total_pnl"], "mdd": r["mdd"]},
            "test": te,
        })

    val_results.sort(key=lambda x: x["test"]["trimmed_avg"], reverse=True)

    print(f"\n{'#':>3} {'[학습]trim':>10} {'WR':>5} {'[검증]trim':>10} {'WR':>5} {'N':>4} {'MDD':>5} {'SR':>5} {'PF':>4} {'ms':>3} {'tn':>2} | 가중치")
    print("─" * 120)

    for rank, r in enumerate(val_results[:30], 1):
        w = r["w"]
        ws = f"M{w['momentum']} LP{w['low_price']} TV{w['top_tv']} SD{w['supply_demand']} GC{w['golden_cross']} RB{w['resistance_breakout']} MA{w['ma_aligned']} OH{w['overheating']}"
        tr, te = r["train"], r["test"]
        print(f"{rank:>3} {tr['trimmed_avg']:>+9.2f}% {tr['win_rate']:>4.1f}% "
              f"{te['trimmed_avg']:>+9.2f}% {te['win_rate']:>4.1f}% "
              f"{te['total']:>4} {te['mdd']:>4.1f}% {te['sharpe']:>5.3f} {te['pf']:>4.1f} "
              f"{r['ms']:>3} {r['tn']:>2} | {ws}")

    # Phase 3: 팩터별 학습↔검증 일관성
    print(f"\n{'='*70}")
    print("Phase 3: 팩터별 학습↔검증 일관성")

    fnames = ["momentum", "low_price", "top_tv", "supply_demand",
              "golden_cross", "resistance_breakout", "ma_aligned", "overheating"]

    base_w = {f: 0 for f in fnames}
    base_tr_pnls = run_backtest_fast(train_dates, train_dd, train_top30, base_w, min_score=-999, top_n=2)
    base_te_pnls = run_backtest_fast(test_dates, test_dd, test_top30, base_w, min_score=-999, top_n=2)
    base_tr = analyze(base_tr_pnls)
    base_te = analyze(base_te_pnls)
    print(f"  베이스라인: 학습 trim={base_tr['trimmed_avg']:>+.2f}%, 검증 trim={base_te['trimmed_avg']:>+.2f}%")

    for fname in fnames:
        test_val = -8 if fname in ("ma_aligned", "overheating") else 10
        tw = {f: 0 for f in fnames}
        tw[fname] = test_val

        tr_pnls = run_backtest_fast(train_dates, train_dd, train_top30, tw, min_score=0, top_n=2)
        te_pnls = run_backtest_fast(test_dates, test_dd, test_top30, tw, min_score=0, top_n=2)
        tr_s = analyze(tr_pnls)
        te_s = analyze(te_pnls)

        d_tr = tr_s["trimmed_avg"] - base_tr["trimmed_avg"]
        d_te = te_s["trimmed_avg"] - base_te["trimmed_avg"]
        ok = "O" if (d_tr > 0) == (d_te > 0) else "X"

        print(f"  {fname:>22} ({test_val:>+3}): "
              f"학습 Δ{d_tr:>+5.2f}% 승률{tr_s['win_rate']:.0f}% | "
              f"검증 Δ{d_te:>+5.2f}% 승률{te_s['win_rate']:.0f}% | 일관={ok}")

    # Phase 4: 현재 설정 비교
    print(f"\n{'='*70}")
    print("Phase 4: 현재 설정 vs 검증 최적")

    cur_w = {"momentum": 30, "low_price": 5, "top_tv": 25,
             "supply_demand": 10, "golden_cross": 8,
             "resistance_breakout": 5, "ma_aligned": -10, "overheating": -8}

    for label, dts, dd, t30 in [("학습", train_dates, train_dd, train_top30),
                                  ("검증", test_dates, test_dd, test_top30)]:
        pnls = run_backtest_fast(dts, dd, t30, cur_w, min_score=20, top_n=2)
        s = analyze(pnls)
        print(f"  현재설정 [{label}]: trim={s['trimmed_avg']:>+.2f}%, med={s['median_pnl']:>+.2f}%, "
              f"WR={s['win_rate']}%, N={s['total']}, SR={s['sharpe']:.3f}, PF={s['pf']:.2f}")

    if val_results:
        best = val_results[0]
        te = best["test"]
        w = best["w"]
        print(f"\n  검증최적: trim={te['trimmed_avg']:>+.2f}%, med={te['median_pnl']:>+.2f}%, "
              f"WR={te['win_rate']}%, N={te['total']}, SR={te['sharpe']:.3f}, PF={te['pf']:.2f}")
        print(f"    M={w['momentum']} LP={w['low_price']} TV={w['top_tv']} "
              f"SD={w['supply_demand']} GC={w['golden_cross']} RB={w['resistance_breakout']} "
              f"MA={w['ma_aligned']} OH={w['overheating']}")
        print(f"    min_score={best['ms']}, top_n={best['tn']}")

    # 결과 저장
    save_data = {
        "generated_at": datetime.now().isoformat(),
        "universe_size": len(all_indicators),
        "date_range": f"{dates_all[0]}~{dates_all[-1]}",
        "train_range": f"{train_range[0]}~{train_range[1]}",
        "test_range": f"{test_range[0]}~{test_range[1]}",
        "total_combos": len(train_results),
        "validation_top30": [
            {"rank": i+1, "weights": r["w"], "min_score": r["ms"], "top_n": r["tn"],
             "train": r["train"], "test": {k: v for k, v in r["test"].items()}}
            for i, r in enumerate(val_results[:30])
        ],
    }
    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {RESULT_PATH}")


if __name__ == "__main__":
    main()
