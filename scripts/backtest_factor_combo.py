"""5팩터 스코어 × Criteria 가감점 조합 최적화 백테스트

stock-history.json (140종목 × 200일봉 OHLCV)에서
기술적 지표를 역산하여 팩터/criteria를 재현하고,
수천 가지 가중치 조합별 수익률을 비교한다.

출력: docs/research/YYYY-MM-DD-factor-combo.md
"""
import json
import math
from pathlib import Path
from itertools import product
from collections import defaultdict
from datetime import datetime

# ── 데이터 경로 ──────────────────────────────────────────────
THEME_DATA = Path(__file__).parent.parent.parent / "theme_analysis" / "frontend" / "public" / "data"
STOCK_HISTORY = THEME_DATA / "stock-history.json"
OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "research"

# ── 매매 파라미터 (고정) ─────────────────────────────────────
TP_PCT = 7.0       # 익절
SL_PCT = -2.0      # 손절
TS_PCT = -3.0      # 트레일링 스톱 (고점 대비)
MAX_HOLD = 5       # 최대 보유일
TOP_N = 2          # 일일 선정 종목 수


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ══════════════════════════════════════════════════════════════
# 기술적 지표 계산
# ══════════════════════════════════════════════════════════════

def calc_ma(closes, period):
    """단순 이동평균"""
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def calc_rsi(closes, period=14):
    """RSI 계산"""
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(-period, 0):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def compute_daily_indicators(days):
    """일별 기술적 지표를 계산하여 dict list로 반환

    각 일자에 대해 closes[:i+1] 기준으로 지표를 계산.
    최소 60일 이상 데이터 필요.
    """
    if len(days) < 61:
        return []

    closes = []
    volumes = []
    highs = []
    results = []

    for i, d in enumerate(days):
        c = int(d.get("stck_clpr", "0"))
        o = int(d.get("stck_oprc", "0"))
        h = int(d.get("stck_hgpr", "0"))
        lo = int(d.get("stck_lwpr", "0"))
        vol = int(d.get("acml_vol", "0"))
        tv = int(d.get("acml_tr_pbmn", "0"))

        if c <= 0:
            closes.append(closes[-1] if closes else 0)
            volumes.append(0)
            highs.append(0)
            results.append(None)
            continue

        closes.append(c)
        volumes.append(vol)
        highs.append(h)

        if i < 60:
            results.append(None)
            continue

        ma5 = calc_ma(closes, 5)
        ma20 = calc_ma(closes, 20)
        ma60 = calc_ma(closes, 60)
        rsi = calc_rsi(closes)
        avg_vol_20 = sum(volumes[max(0, i-19):i+1]) / min(20, i+1) if i > 0 else vol

        # 기준 지표
        ma_aligned = ma5 > ma20 > ma60 if all([ma5, ma20, ma60]) else False

        # 골든크로스: MA5가 MA20 위로 교차 (3일 이내)
        golden_cross = False
        if i >= 63 and ma5 and ma20:
            prev_closes_5 = closes[i-3:i]
            prev_closes_20 = closes[max(0,i-22):max(0,i-2)]
            if len(prev_closes_5) >= 3 and len(prev_closes_20) >= 20:
                prev_ma5 = sum(closes[i-7:i-2]) / 5 if i >= 7 else None
                prev_ma20 = sum(closes[i-22:i-2]) / 20 if i >= 22 else None
                if prev_ma5 and prev_ma20:
                    golden_cross = (prev_ma5 <= prev_ma20) and (ma5 > ma20)

        # 과열: RSI > 70 또는 거래량 3배 이상
        overheating = rsi > 70 or (avg_vol_20 > 0 and vol > avg_vol_20 * 3)

        # 저항돌파: 종가 > 20일 최고가 (전일까지)
        prev_highs = highs[max(0, i-20):i]
        resistance_breakout = c > max(prev_highs) if prev_highs else False

        # 수급: 거래량 증가 추세 (5일 평균 > 20일 평균의 1.5배)
        avg_vol_5 = sum(volumes[max(0,i-4):i+1]) / min(5, i+1)
        supply_demand = avg_vol_5 > avg_vol_20 * 1.5 if avg_vol_20 > 0 else False

        # 거래대금 상위30 근사: 거래대금이 큰 종목 (나중에 일별 전체 기준으로 판단)
        # 시가총액: 종가 기준 (절대가격으로 근사)

        # 저가주
        low_price = c < 20000

        # 가격 필터
        price_ok = 1000 <= c < 50000

        # 모멘텀 (5일 수익률)
        mom_5d = (c - closes[i-5]) / closes[i-5] * 100 if i >= 5 and closes[i-5] > 0 else 0

        # 변동률
        prev_c = closes[i-1] if i > 0 else c
        change_rate = (c - prev_c) / prev_c * 100 if prev_c > 0 else 0

        results.append({
            "date": d.get("stck_bsop_date"),
            "close": c,
            "open": o,
            "high": h,
            "low": lo,
            "volume": vol,
            "trading_value": tv,
            "ma5": ma5,
            "ma20": ma20,
            "ma60": ma60,
            "rsi": rsi,
            "ma_aligned": ma_aligned,
            "golden_cross": golden_cross,
            "overheating": overheating,
            "resistance_breakout": resistance_breakout,
            "supply_demand": supply_demand,
            "low_price": low_price,
            "price_ok": price_ok,
            "mom_5d": mom_5d,
            "change_rate": change_rate,
        })

    return results


# ══════════════════════════════════════════════════════════════
# 스코어링 함수
# ══════════════════════════════════════════════════════════════

def score_stock(ind, weights, is_top_tv=False):
    """종목의 일별 지표에 가중치를 적용하여 점수 계산

    weights dict:
        # 5팩터 계열
        "momentum": 모멘텀 양수 시 점수
        "low_price": 저가주 보너스
        "top_tv": 거래대금 상위 보너스 (대장주 대용)
        # criteria 가점
        "supply_demand": 수급 양호
        "golden_cross": 골든크로스
        "resistance_breakout": 저항돌파
        # criteria 감점
        "ma_aligned": 정배열 (이미 선반영 → 감점)
        "overheating": 과열
        "top30_tv": 거래대금 TOP30 (감점)
    """
    score = 0

    # 5팩터 계열
    if ind["mom_5d"] > 0:
        score += weights.get("momentum", 0)
    if ind["low_price"]:
        score += weights.get("low_price", 0)
    if is_top_tv:
        score += weights.get("top_tv", 0)

    # Criteria 가점
    if ind["supply_demand"]:
        score += weights.get("supply_demand", 0)
    if ind["golden_cross"]:
        score += weights.get("golden_cross", 0)
    if ind["resistance_breakout"]:
        score += weights.get("resistance_breakout", 0)

    # Criteria 감점
    if ind["ma_aligned"]:
        score += weights.get("ma_aligned", 0)  # 보통 음수
    if ind["overheating"]:
        score += weights.get("overheating", 0)  # 보통 음수

    return score


# ══════════════════════════════════════════════════════════════
# 백테스트 엔진
# ══════════════════════════════════════════════════════════════

def run_backtest(all_indicators, weights, min_score=0, top_n=2,
                 tp=7.0, sl=-2.0, ts=-3.0, max_hold=5,
                 exclude_overheated_5=True):
    """전체 종목 × 전체 날짜에 대해 팩터 스코어 기반 선정 → 매매 시뮬레이션

    all_indicators: {code: [daily_indicator_dict, ...]}
    """
    # 날짜별 인덱스 구축
    date_map = defaultdict(list)  # date → [(code, indicator)]
    for code, inds in all_indicators.items():
        for ind in inds:
            if ind is None:
                continue
            if not ind["price_ok"]:
                continue
            date_map[ind["date"]].append((code, ind))

    dates = sorted(date_map.keys())
    trades = []
    holding = {}  # code → {buy_price, buy_date, buy_idx, peak}

    for di, date in enumerate(dates):
        stocks_today = date_map[date]

        # 1) 보유 종목 체크 (매도 판정)
        codes_sold_today = set()
        for code in list(holding.keys()):
            pos = holding[code]
            # 오늘 해당 종목 데이터 찾기
            today_data = None
            for c, ind in stocks_today:
                if c == code:
                    today_data = ind
                    break
            if today_data is None:
                continue

            buy_price = pos["buy_price"]
            high = today_data["high"]
            low = today_data["low"]
            close = today_data["close"]
            hold_days = di - pos["buy_idx"]

            if high > pos["peak"]:
                pos["peak"] = high

            high_pnl = (high - buy_price) / buy_price * 100
            low_pnl = (low - buy_price) / buy_price * 100
            close_pnl = (close - buy_price) / buy_price * 100
            drop_from_peak = (close - pos["peak"]) / pos["peak"] * 100 if pos["peak"] > 0 else 0

            reason = None
            sell_pnl = close_pnl

            # 익절
            if high_pnl >= tp:
                reason = "take_profit"
                sell_pnl = tp
            # 손절
            elif low_pnl <= sl:
                reason = "stop_loss"
                sell_pnl = sl
            # 트레일링 스톱
            elif close_pnl > 0 and drop_from_peak <= ts:
                reason = "trailing_stop"
                sell_pnl = close_pnl
            # 최대 보유일 초과
            elif hold_days >= max_hold:
                reason = "time_exit"
                sell_pnl = close_pnl

            if reason:
                trades.append({
                    "code": code,
                    "buy_date": pos["buy_date"],
                    "sell_date": date,
                    "hold_days": hold_days,
                    "pnl": round(sell_pnl, 2),
                    "reason": reason,
                })
                del holding[code]
                codes_sold_today.add(code)

        # 2) 새 종목 선정 (보유 중이 아닌 종목만)
        if len(holding) < top_n:
            # 거래대금 상위30 판별
            tv_sorted = sorted(stocks_today, key=lambda x: x[1]["trading_value"], reverse=True)
            top30_codes = {c for c, _ in tv_sorted[:30]}

            candidates = []
            for code, ind in stocks_today:
                if code in holding or code in codes_sold_today:
                    continue

                # 과열 5개 이상 제외
                if exclude_overheated_5:
                    met = sum([
                        ind["ma_aligned"],
                        ind["supply_demand"],
                        ind["golden_cross"],
                        ind["resistance_breakout"],
                        ind["overheating"],
                        code in top30_codes,
                    ])
                    if met >= 5:
                        continue

                is_top = code in top30_codes
                s = score_stock(ind, weights, is_top_tv=is_top)
                if s >= min_score:
                    candidates.append((code, ind, s))

            # 점수 > 거래대금 > 변동률 순 정렬
            candidates.sort(key=lambda x: (-x[2], -x[1]["trading_value"], -x[1]["change_rate"]))

            slots = top_n - len(holding)
            for code, ind, s in candidates[:slots]:
                holding[code] = {
                    "buy_price": ind["close"],
                    "buy_date": date,
                    "buy_idx": di,
                    "peak": ind["close"],
                }

    # 미청산 포지션 처리
    for code, pos in holding.items():
        last_date = dates[-1]
        for c, ind in date_map[last_date]:
            if c == code:
                pnl = (ind["close"] - pos["buy_price"]) / pos["buy_price"] * 100
                trades.append({
                    "code": code,
                    "buy_date": pos["buy_date"],
                    "sell_date": last_date,
                    "hold_days": len(dates) - 1 - pos["buy_idx"],
                    "pnl": round(pnl, 2),
                    "reason": "eod_final",
                })
                break

    return trades


def analyze(trades):
    if not trades:
        return {"total": 0, "win_rate": 0, "avg_pnl": 0, "total_pnl": 0,
                "avg_hold": 0, "mdd": 0, "sharpe": 0, "profit_factor": 0}

    total = len(trades)
    pnls = [t["pnl"] for t in trades]
    wins = sum(1 for p in pnls if p > 0)
    holds = [t["hold_days"] for t in trades]

    # MDD
    cum = 0
    peak = 0
    mdd = 0
    for p in pnls:
        cum += p
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > mdd:
            mdd = dd

    avg_pnl = sum(pnls) / total
    std_pnl = (sum((p - avg_pnl) ** 2 for p in pnls) / total) ** 0.5 if total > 1 else 1

    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))

    return {
        "total": total,
        "win_rate": round(wins / total * 100, 1),
        "avg_pnl": round(avg_pnl, 2),
        "total_pnl": round(sum(pnls), 1),
        "avg_hold": round(sum(holds) / total, 1),
        "mdd": round(mdd, 1),
        "sharpe": round(avg_pnl / std_pnl, 3) if std_pnl > 0 else 0,
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else 999,
        "by_reason": {
            r: sum(1 for t in trades if t["reason"] == r)
            for r in set(t["reason"] for t in trades)
        },
    }


# ══════════════════════════════════════════════════════════════
# 조합 생성
# ══════════════════════════════════════════════════════════════

def generate_weight_combos():
    """가중치 조합 생성 — 현실적 범위로 제한"""

    # 5팩터 계열 가중치
    momentum_vals = [0, 15, 30]         # 모멘텀 (API/Vision 매수 대용)
    low_price_vals = [0, 5]             # 저가주 보너스
    top_tv_vals = [0, 15, 25]           # 대장주(거래대금 1위) 보너스

    # Criteria 가점
    supply_vals = [0, 5, 10]            # 수급
    golden_vals = [0, 5, 8]             # 골든크로스
    resist_vals = [0, 3, 5]             # 저항돌파

    # Criteria 감점
    ma_align_vals = [0, -5, -10]        # 정배열 감점
    overheat_vals = [0, -5, -8]         # 과열 감점

    combos = []
    for mom, lp, ttv, sd, gc, rb, ma, oh in product(
        momentum_vals, low_price_vals, top_tv_vals,
        supply_vals, golden_vals, resist_vals,
        ma_align_vals, overheat_vals
    ):
        # 최소한 1개 팩터는 활성화
        if mom == 0 and lp == 0 and ttv == 0 and sd == 0 and gc == 0 and rb == 0:
            continue
        combos.append({
            "momentum": mom,
            "low_price": lp,
            "top_tv": ttv,
            "supply_demand": sd,
            "golden_cross": gc,
            "resistance_breakout": rb,
            "ma_aligned": ma,
            "overheating": oh,
        })

    return combos


def generate_advanced_combos():
    """확장 조합: min_score, top_n, exclude_overheated_5 변형"""
    base_combos = generate_weight_combos()
    advanced = []
    for w in base_combos:
        for ms in [0, 10, 20]:
            for exc5 in [True, False]:
                advanced.append((w, ms, exc5))
    return advanced


# ══════════════════════════════════════════════════════════════
# 메인
# ══════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("5팩터 × Criteria 가감점 조합 최적화 백테스트")
    print("=" * 70)

    # 데이터 로드
    stock_hist = load_json(STOCK_HISTORY)
    print(f"종목 수: {len(stock_hist)}")

    # 모든 종목 기술적 지표 계산
    print("기술적 지표 계산 중...")
    all_indicators = {}
    valid_count = 0
    for code, info in stock_hist.items():
        raw = info.get("raw_daily_prices", [])
        if len(raw) < 61:
            continue
        days = sorted(raw, key=lambda x: x.get("stck_bsop_date", ""))
        inds = compute_daily_indicators(days)
        if inds:
            all_indicators[code] = inds
            valid_count += 1

    print(f"유효 종목: {valid_count}개")

    # 날짜 범위 확인
    all_dates = set()
    for inds in all_indicators.values():
        for ind in inds:
            if ind:
                all_dates.add(ind["date"])
    dates = sorted(all_dates)
    print(f"날짜 범위: {dates[0]} ~ {dates[-1]} ({len(dates)}일)")

    # ── Phase 1: 기본 가중치 조합 탐색 ──────────────────────
    print(f"\n{'='*70}")
    print("Phase 1: 기본 가중치 조합 탐색")
    combos = generate_weight_combos()
    print(f"조합 수: {len(combos)}")

    results = []
    for i, w in enumerate(combos):
        if i % 200 == 0:
            print(f"  진행: {i}/{len(combos)}...")
        trades = run_backtest(all_indicators, w, min_score=10, top_n=2)
        stats = analyze(trades)
        results.append({"weights": w, "min_score": 10, "exclude_5": True, **stats})

    # 총 수익률 기준 정렬
    results.sort(key=lambda x: x["total_pnl"], reverse=True)

    print(f"\n{'─'*100}")
    print(f"{'순위':>4} {'총수익':>8} {'승률':>6} {'평균':>7} {'거래':>5} {'보유':>4} {'MDD':>6} {'샤프':>6} {'PF':>5} | 가중치")
    print(f"{'─'*100}")

    for rank, r in enumerate(results[:30], 1):
        w = r["weights"]
        w_str = f"M{w['momentum']} LP{w['low_price']} TV{w['top_tv']} SD{w['supply_demand']} GC{w['golden_cross']} RB{w['resistance_breakout']} MA{w['ma_aligned']} OH{w['overheating']}"
        print(f"{rank:>4} {r['total_pnl']:>+7.1f}% {r['win_rate']:>5.1f}% {r['avg_pnl']:>+6.2f}% {r['total']:>5} {r['avg_hold']:>4.1f} {r['mdd']:>5.1f}% {r['sharpe']:>6.3f} {r['profit_factor']:>5.2f} | {w_str}")

    # ── Phase 2: 상위 조합에 대해 min_score/exclude 변형 탐색 ─
    print(f"\n{'='*70}")
    print("Phase 2: 상위 30 조합 × min_score/exclude 변형 (확장)")

    top_weights = [r["weights"] for r in results[:30]]
    phase2_results = []

    for w in top_weights:
        for ms in [0, 5, 10, 15, 20, 30]:
            for exc5 in [True, False]:
                for tn in [1, 2, 3]:
                    trades = run_backtest(all_indicators, w, min_score=ms,
                                          top_n=tn, exclude_overheated_5=exc5)
                    stats = analyze(trades)
                    phase2_results.append({
                        "weights": w, "min_score": ms,
                        "exclude_5": exc5, "top_n": tn, **stats
                    })

    phase2_results.sort(key=lambda x: x["total_pnl"], reverse=True)

    print(f"\n조합 수: {len(phase2_results)}")
    print(f"{'─'*120}")
    print(f"{'순위':>4} {'총수익':>8} {'승률':>6} {'평균':>7} {'거래':>5} {'보유':>4} {'MDD':>6} {'샤프':>6} {'PF':>5} {'ms':>3} {'ex5':>3} {'TN':>2} | 가중치")
    print(f"{'─'*120}")

    for rank, r in enumerate(phase2_results[:30], 1):
        w = r["weights"]
        w_str = f"M{w['momentum']} LP{w['low_price']} TV{w['top_tv']} SD{w['supply_demand']} GC{w['golden_cross']} RB{w['resistance_breakout']} MA{w['ma_aligned']} OH{w['overheating']}"
        ex5 = "Y" if r["exclude_5"] else "N"
        print(f"{rank:>4} {r['total_pnl']:>+7.1f}% {r['win_rate']:>5.1f}% {r['avg_pnl']:>+6.2f}% {r['total']:>5} {r['avg_hold']:>4.1f} {r['mdd']:>5.1f}% {r['sharpe']:>6.3f} {r['profit_factor']:>5.2f} {r['min_score']:>3} {ex5:>3} {r['top_n']:>2} | {w_str}")

    # ── Phase 3: 효율성 분석 (Sharpe / Profit Factor 기준) ──
    print(f"\n{'='*70}")
    print("Phase 3: 효율성 순위 (Sharpe Ratio 기준)")

    efficient = [r for r in phase2_results if r["total"] >= 20]  # 최소 20건
    efficient.sort(key=lambda x: x["sharpe"], reverse=True)

    print(f"{'─'*120}")
    print(f"{'순위':>4} {'샤프':>6} {'총수익':>8} {'승률':>6} {'평균':>7} {'거래':>5} {'MDD':>6} {'PF':>5} {'ms':>3} {'ex5':>3} {'TN':>2} | 가중치")
    print(f"{'─'*120}")

    for rank, r in enumerate(efficient[:20], 1):
        w = r["weights"]
        w_str = f"M{w['momentum']} LP{w['low_price']} TV{w['top_tv']} SD{w['supply_demand']} GC{w['golden_cross']} RB{w['resistance_breakout']} MA{w['ma_aligned']} OH{w['overheating']}"
        ex5 = "Y" if r["exclude_5"] else "N"
        print(f"{rank:>4} {r['sharpe']:>6.3f} {r['total_pnl']:>+7.1f}% {r['win_rate']:>5.1f}% {r['avg_pnl']:>+6.2f}% {r['total']:>5} {r['mdd']:>5.1f}% {r['profit_factor']:>5.2f} {r['min_score']:>3} {ex5:>3} {r['top_n']:>2} | {w_str}")

    # ── Phase 4: Profit Factor 기준 ──
    print(f"\n{'='*70}")
    print("Phase 4: 안정성 순위 (Profit Factor 기준)")

    pf_sorted = [r for r in phase2_results if r["total"] >= 20]
    pf_sorted.sort(key=lambda x: x["profit_factor"], reverse=True)

    print(f"{'─'*120}")
    for rank, r in enumerate(pf_sorted[:20], 1):
        w = r["weights"]
        w_str = f"M{w['momentum']} LP{w['low_price']} TV{w['top_tv']} SD{w['supply_demand']} GC{w['golden_cross']} RB{w['resistance_breakout']} MA{w['ma_aligned']} OH{w['overheating']}"
        ex5 = "Y" if r["exclude_5"] else "N"
        print(f"{rank:>4} {r['profit_factor']:>5.2f} {r['total_pnl']:>+7.1f}% {r['win_rate']:>5.1f}% {r['avg_pnl']:>+6.2f}% {r['total']:>5} {r['mdd']:>5.1f}% {r['sharpe']:>6.3f} {r['min_score']:>3} {ex5:>3} {r['top_n']:>2} | {w_str}")

    # ── Phase 5: 팩터별 기여도 분석 ──
    print(f"\n{'='*70}")
    print("Phase 5: 팩터별 기여도 분석")

    factor_names = ["momentum", "low_price", "top_tv", "supply_demand",
                    "golden_cross", "resistance_breakout", "ma_aligned", "overheating"]

    for fname in factor_names:
        active = [r for r in results if r["weights"][fname] != 0]
        inactive = [r for r in results if r["weights"][fname] == 0]
        if active and inactive:
            avg_act = sum(r["total_pnl"] for r in active) / len(active)
            avg_inact = sum(r["total_pnl"] for r in inactive) / len(inactive)
            avg_wr_act = sum(r["win_rate"] for r in active) / len(active)
            avg_wr_inact = sum(r["win_rate"] for r in inactive) / len(inactive)
            diff = avg_act - avg_inact
            print(f"  {fname:>22}: 활성={avg_act:>+7.1f}% ({len(active):>4}건), "
                  f"비활성={avg_inact:>+7.1f}% ({len(inactive):>4}건), "
                  f"차이={diff:>+6.1f}%, 승률차={avg_wr_act - avg_wr_inact:>+5.1f}%")

    # ── Phase 6: 개별 팩터 ON/OFF 비교 ──
    print(f"\n{'='*70}")
    print("Phase 6: 개별 팩터 ON/OFF 단독 효과")

    baseline_w = {f: 0 for f in factor_names}
    base_trades = run_backtest(all_indicators, baseline_w, min_score=-999, top_n=2)
    base_stats = analyze(base_trades)
    print(f"  베이스라인 (랜덤): 총수익={base_stats['total_pnl']:>+.1f}%, "
          f"승률={base_stats['win_rate']}%, 거래={base_stats['total']}건")

    single_effects = {}
    for fname in factor_names:
        for val in [-10, -8, -5, 0, 3, 5, 8, 10, 15, 20, 25, 30]:
            test_w = {f: 0 for f in factor_names}
            test_w[fname] = val
            if val == 0:
                continue
            trades = run_backtest(all_indicators, test_w, min_score=0, top_n=2)
            stats = analyze(trades)
            if fname not in single_effects:
                single_effects[fname] = []
            single_effects[fname].append({
                "value": val, **stats
            })

    for fname in factor_names:
        if fname in single_effects:
            print(f"\n  {fname}:")
            for e in single_effects[fname]:
                if e["total"] > 0:
                    print(f"    값={e['value']:>+3}: 총수익={e['total_pnl']:>+7.1f}%, "
                          f"승률={e['win_rate']:>5.1f}%, 거래={e['total']:>4}건, "
                          f"샤프={e['sharpe']:>6.3f}")

    # ── 결과 저장 ─────────────────────────────────────────────
    # 상위 결과 저장
    top50_return = phase2_results[:50]
    top20_sharpe = efficient[:20]
    top20_pf = pf_sorted[:20]

    # 현재 설정과 비교
    current_weights = {
        "momentum": 30,
        "low_price": 5,
        "top_tv": 25,
        "supply_demand": 10,
        "golden_cross": 8,
        "resistance_breakout": 5,
        "ma_aligned": -10,
        "overheating": -8,
    }
    current_trades = run_backtest(all_indicators, current_weights, min_score=20, top_n=2)
    current_stats = analyze(current_trades)

    print(f"\n{'='*70}")
    print("현재 설정 성과:")
    print(f"  총수익={current_stats['total_pnl']:>+.1f}%, 승률={current_stats['win_rate']}%, "
          f"거래={current_stats['total']}건, 평균={current_stats['avg_pnl']:>+.2f}%, "
          f"MDD={current_stats['mdd']}%, 샤프={current_stats['sharpe']:.3f}, PF={current_stats['profit_factor']:.2f}")

    best = phase2_results[0]
    print(f"\n최적 조합 (총수익 기준):")
    w = best["weights"]
    print(f"  모멘텀={w['momentum']}, 저가주={w['low_price']}, 대장주={w['top_tv']}")
    print(f"  수급={w['supply_demand']}, 골든크로스={w['golden_cross']}, 저항돌파={w['resistance_breakout']}")
    print(f"  정배열={w['ma_aligned']}, 과열={w['overheating']}")
    print(f"  min_score={best['min_score']}, exclude_5={best['exclude_5']}, top_n={best['top_n']}")
    print(f"  총수익={best['total_pnl']:>+.1f}%, 승률={best['win_rate']}%, "
          f"거래={best['total']}건, 평균={best['avg_pnl']:>+.2f}%, "
          f"MDD={best['mdd']}%, 샤프={best['sharpe']:.3f}, PF={best['profit_factor']:.2f}")

    best_eff = efficient[0] if efficient else None
    if best_eff:
        print(f"\n최적 조합 (효율 기준 - Sharpe):")
        w = best_eff["weights"]
        print(f"  모멘텀={w['momentum']}, 저가주={w['low_price']}, 대장주={w['top_tv']}")
        print(f"  수급={w['supply_demand']}, 골든크로스={w['golden_cross']}, 저항돌파={w['resistance_breakout']}")
        print(f"  정배열={w['ma_aligned']}, 과열={w['overheating']}")
        print(f"  min_score={best_eff['min_score']}, exclude_5={best_eff['exclude_5']}, top_n={best_eff['top_n']}")
        print(f"  총수익={best_eff['total_pnl']:>+.1f}%, 승률={best_eff['win_rate']}%, "
              f"거래={best_eff['total']}건, 샤프={best_eff['sharpe']:.3f}, PF={best_eff['profit_factor']:.2f}")

    # JSON 저장
    output_json = Path(__file__).parent.parent / "results" / "backtest_factor_combo.json"
    save_data = {
        "generated_at": datetime.now().isoformat(),
        "data_range": f"{dates[0]}~{dates[-1]}",
        "total_stocks": valid_count,
        "total_combos_phase1": len(results),
        "total_combos_phase2": len(phase2_results),
        "current_config": {
            "weights": current_weights,
            "min_score": 20,
            "top_n": 2,
            "stats": current_stats,
        },
        "best_by_return": {
            "weights": best["weights"],
            "min_score": best["min_score"],
            "exclude_5": best["exclude_5"],
            "top_n": best["top_n"],
            "stats": {k: v for k, v in best.items() if k not in ("weights", "min_score", "exclude_5", "top_n")},
        },
        "best_by_sharpe": {
            "weights": best_eff["weights"],
            "min_score": best_eff["min_score"],
            "exclude_5": best_eff["exclude_5"],
            "top_n": best_eff["top_n"],
            "stats": {k: v for k, v in best_eff.items() if k not in ("weights", "min_score", "exclude_5", "top_n")},
        } if best_eff else None,
        "top50_by_return": [
            {
                "rank": i+1,
                "weights": r["weights"],
                "min_score": r["min_score"],
                "exclude_5": r["exclude_5"],
                "top_n": r["top_n"],
                "total_pnl": r["total_pnl"],
                "win_rate": r["win_rate"],
                "avg_pnl": r["avg_pnl"],
                "total": r["total"],
                "mdd": r["mdd"],
                "sharpe": r["sharpe"],
                "profit_factor": r["profit_factor"],
            }
            for i, r in enumerate(phase2_results[:50])
        ],
        "top20_by_sharpe": [
            {
                "rank": i+1,
                "weights": r["weights"],
                "min_score": r["min_score"],
                "exclude_5": r["exclude_5"],
                "top_n": r["top_n"],
                "total_pnl": r["total_pnl"],
                "win_rate": r["win_rate"],
                "sharpe": r["sharpe"],
                "profit_factor": r["profit_factor"],
                "total": r["total"],
            }
            for i, r in enumerate(efficient[:20])
        ],
        "factor_single_effects": single_effects,
    }

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    print(f"\n결과 JSON 저장: {output_json}")


if __name__ == "__main__":
    main()
