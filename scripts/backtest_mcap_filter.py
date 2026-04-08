"""시가총액 필터 효과 검증 백테스트

갭업 모멘텀 전략에 시가총액(프록시) 필터를 적용했을 때의 성과 변화 분석.
- 시총 프록시: 일평균 거래대금 / 회전율 추정 (거래대금이 큰 종목 = 시총 큰 종목)
- 직접 시총 데이터 없으므로 거래대금 기반 프록시 + 가격대 필터 조합
- 2,618종목 × 500일(2024-03~2026-04) 전수 분석
"""
import json, math, sys
from pathlib import Path
from collections import defaultdict

DATA_PATH = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"


def load_data():
    print("데이터 로드 중...")
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def prepare(all_data):
    """각 종목의 bar를 기술 지표와 함께 날짜별 dict로 변환."""
    daily = defaultdict(dict)  # date -> {code: indicator}
    stock_avg_tv = {}  # code -> 20일 평균 거래대금 (시총 프록시)

    for code, info in all_data.items():
        bars = info.get("bars", [])
        name = info.get("name", code)
        if len(bars) < 201:
            continue
        closes, opens, volumes, tvs = [], [], [], []

        for i, b in enumerate(bars):
            c = int(b.get("stck_clpr", "0") or "0")
            o = int(b.get("stck_oprc", "0") or "0")
            vol = int(b.get("acml_vol", "0") or "0")
            tv = int(b.get("acml_tr_pbmn", "0") or "0")  # 거래대금(원)
            closes.append(c); opens.append(o); volumes.append(vol); tvs.append(tv)

            if i < 200 or c <= 0 or o <= 0:
                continue

            prev_close = closes[i - 1]
            if prev_close <= 0:
                continue

            gap = (o - prev_close) / prev_close * 100
            ma200 = sum(closes[i - 199:i + 1]) / 200
            ma20 = sum(closes[i - 19:i + 1]) / 20
            avg_vol_20 = sum(volumes[i - 19:i + 1]) / 20
            avg_tv_20 = sum(tvs[i - 19:i + 1]) / 20  # 20일 평균 거래대금
            prev_tv = tvs[i - 1]  # 전일 거래대금

            # 3일 과열: 최근 3일 변동폭 평균 + 누적등락
            if i >= 203:
                ranges_3 = []
                for j in range(i - 3, i):
                    h = int(bars[j].get("stck_hgpr", "0") or "0")
                    lo = int(bars[j].get("stck_lwpr", "0") or "0")
                    if lo > 0:
                        ranges_3.append((h - lo) / lo * 100)
                avg_range_3 = sum(ranges_3) / len(ranges_3) if ranges_3 else 0
                close_3d = closes[i - 3]
                cum_3d = (prev_close - close_3d) / close_3d * 100 if close_3d > 0 else 0
            else:
                avg_range_3 = 0
                cum_3d = 0

            oc_return = (c - o) / o * 100  # 당일 시가→종가 수익률

            d = b.get("stck_bsop_date", "")
            daily[d][code] = {
                "name": name, "c": c, "o": o, "gap": gap,
                "ma200": ma200, "ma20": ma20,
                "vol": vol, "avg_vol_20": avg_vol_20,
                "tv": tv, "prev_tv": prev_tv, "avg_tv_20": avg_tv_20,
                "avg_range_3": avg_range_3, "cum_3d": cum_3d,
                "oc_return": oc_return,
                "ok": 1000 <= c < 200000,
                "vol_rate": (vol / avg_vol_20 * 100) if avg_vol_20 > 0 else 0,
            }
    return daily


def run_backtest(daily, gap_range=(0, 5), require_ma200=True, require_ma20=True,
                 overheat=True, min_tv_억=3, min_avg_tv_억=0,
                 sort_method="vol_rate_x_log_tv", max_pos=2, label=""):
    """갭업 전략 백테스트. 다양한 거래대금/시총 프록시 필터 조합 테스트."""
    dates = sorted(daily.keys())
    trades = []
    for date in dates:
        stocks = daily[date]
        cands = []
        for code, ind in stocks.items():
            if not ind["ok"]:
                continue
            gap = ind["gap"]
            if gap < gap_range[0] or gap >= gap_range[1]:
                continue
            if require_ma200 and ind["c"] <= ind["ma200"]:
                continue
            if require_ma20 and ind["c"] <= ind["ma20"]:
                continue
            if overheat and (ind["avg_range_3"] >= 13 or ind["cum_3d"] >= 20):
                continue
            # 전일 거래대금 필터
            ptv = ind["prev_tv"] / 1e8  # 억원
            if min_tv_억 > 0 and ptv < min_tv_억:
                continue
            # 20일 평균 거래대금 필터 (시총 프록시)
            avg_tv = ind["avg_tv_20"] / 1e8  # 억원
            if min_avg_tv_억 > 0 and avg_tv < min_avg_tv_억:
                continue
            cands.append((code, ind, ptv, avg_tv))

        # 정렬
        if sort_method == "vol_rate_x_log_tv":
            for c in cands:
                c[1]["_score"] = c[1]["vol_rate"] * math.log(max(c[2] * 1e8, 1))
            cands.sort(key=lambda x: -x[1]["_score"])
        elif sort_method == "vol_rate":
            cands.sort(key=lambda x: -x[1]["vol_rate"])
        elif sort_method == "avg_tv":
            cands.sort(key=lambda x: -x[3])

        for code, ind, ptv, avg_tv in cands[:max_pos]:
            trades.append({
                "date": date, "code": code, "name": ind["name"],
                "pnl": round(ind["oc_return"], 2), "gap": round(ind["gap"], 2),
                "prev_tv": round(ptv, 1), "avg_tv_20": round(avg_tv, 1),
            })
    return trades


def stats(trades, label):
    if not trades:
        return {"label": label, "n": 0}
    pnls = [t["pnl"] for t in trades]
    n = len(pnls)
    wins = sum(1 for p in pnls if p > 0)
    avg = sum(pnls) / n
    med = sorted(pnls)[n // 2]
    total = sum(pnls)
    sharpe = (avg / (sum((p - avg) ** 2 for p in pnls) / n) ** 0.5) if n > 1 else 0
    worst = min(pnls)
    best = max(pnls)
    return {
        "label": label, "n": n, "avg": round(avg, 3), "median": round(med, 2),
        "total": round(total, 1), "wins": wins, "wr": round(wins / n * 100, 1),
        "sharpe": round(sharpe, 3), "best": best, "worst": worst,
    }


def print_stats(s):
    if s["n"] == 0:
        print(f"  {s['label']}: 거래 0건")
        return
    print(f"  {s['label']}: {s['n']}건 | 평균 {s['avg']:+.3f}% | 중위 {s['median']:+.2f}% | "
          f"승률 {s['wr']:.1f}% ({s['wins']}/{s['n']}) | 총합 {s['total']:+.1f}% | "
          f"샤프 {s['sharpe']:.3f} | 최대 {s['best']:+.2f}% / {s['worst']:+.2f}%")


def main():
    all_data = load_data()
    print(f"종목 수: {len(all_data)}")
    daily = prepare(all_data)
    print(f"거래일 수: {len(daily)}")

    # ========== 1) 기본 전략 (현재 시스템) ==========
    print("\n" + "=" * 80)
    print("1. 기본 전략 (현재 시스템: 갭0~5%, MA200↑, MA20↑, 과열필터, TV≥3억)")
    baseline = run_backtest(daily, gap_range=(0, 5), min_tv_억=3)
    bs = stats(baseline, "기본")
    print_stats(bs)

    # ========== 2) 거래대금 기반 시총 프록시 필터 ==========
    print("\n" + "=" * 80)
    print("2. 전일 거래대금(TV) 임계값별 성과")
    for tv in [0, 1, 3, 5, 10, 20, 30, 50, 100]:
        trades = run_backtest(daily, gap_range=(0, 5), min_tv_억=tv)
        s = stats(trades, f"TV≥{tv}억")
        print_stats(s)

    # ========== 3) 20일 평균 거래대금 필터 (더 안정적 시총 프록시) ==========
    print("\n" + "=" * 80)
    print("3. 20일 평균 거래대금(avgTV) 임계값별 성과 (시총 프록시)")
    for atv in [0, 1, 3, 5, 10, 20, 30, 50, 100]:
        trades = run_backtest(daily, gap_range=(0, 5), min_tv_억=3, min_avg_tv_억=atv)
        s = stats(trades, f"TV≥3억+avgTV≥{atv}억")
        print_stats(s)

    # ========== 4) 가격대 필터 (시총 프록시) ==========
    print("\n" + "=" * 80)
    print("4. 가격대별 성과 분석")
    all_trades = run_backtest(daily, gap_range=(0, 5), min_tv_억=3)
    price_brackets = [
        ("1천~3천", 1000, 3000), ("3천~5천", 3000, 5000),
        ("5천~1만", 5000, 10000), ("1만~3만", 10000, 30000),
        ("3만~5만", 30000, 50000), ("5만~10만", 50000, 100000),
        ("10만~20만", 100000, 200000),
    ]
    for label, lo, hi in price_brackets:
        subset = [t for t in all_trades if lo <= next(
            (daily[t["date"]][t["code"]]["c"] for _ in [1] if t["code"] in daily.get(t["date"], {})), 0) < hi]
        s = stats(subset, label)
        print_stats(s)

    # ========== 5) 20일 평균 거래대금 구간별 상세 분석 ==========
    print("\n" + "=" * 80)
    print("5. 20일 평균 거래대금 구간별 상세 (TV≥3억 기본)")
    atv_brackets = [
        ("avgTV<1억", 0, 1), ("1~3억", 1, 3), ("3~5억", 3, 5),
        ("5~10억", 5, 10), ("10~30억", 10, 30), ("30~50억", 30, 50),
        ("50~100억", 50, 100), ("100억+", 100, 99999),
    ]
    for label, lo, hi in atv_brackets:
        subset = [t for t in all_trades if lo <= t.get("avg_tv_20", 0) < hi]
        s = stats(subset, label)
        print_stats(s)

    # ========== 6) 복합 필터 조합 ==========
    print("\n" + "=" * 80)
    print("6. 복합 필터 조합 (유망 조합 탐색)")
    combos = [
        ("기본(TV≥3)", 3, 0),
        ("TV≥3+avgTV≥5", 3, 5),
        ("TV≥3+avgTV≥10", 3, 10),
        ("TV≥5+avgTV≥10", 5, 10),
        ("TV≥5+avgTV≥20", 5, 20),
        ("TV≥10+avgTV≥10", 10, 10),
        ("TV≥10+avgTV≥20", 10, 20),
        ("TV≥10+avgTV≥30", 10, 30),
        ("TV≥20+avgTV≥20", 20, 20),
        ("TV≥30+avgTV≥30", 30, 30),
        ("TV≥50+avgTV≥50", 50, 50),
    ]
    for label, tv, atv in combos:
        trades = run_backtest(daily, gap_range=(0, 5), min_tv_억=tv, min_avg_tv_억=atv)
        s = stats(trades, label)
        print_stats(s)

    # ========== 7) 거래대금/시총 프록시 vs 정렬 방식 교차 ==========
    print("\n" + "=" * 80)
    print("7. 정렬 방식 × 필터 교차 비교")
    for sort in ["vol_rate_x_log_tv", "vol_rate", "avg_tv"]:
        for tv, atv in [(3, 0), (3, 10), (10, 20)]:
            trades = run_backtest(daily, gap_range=(0, 5), min_tv_억=tv,
                                  min_avg_tv_억=atv, sort_method=sort)
            s = stats(trades, f"{sort}|TV≥{tv}+avgTV≥{atv}")
            print_stats(s)

    # ========== 8) 거래대금 상한 (대형주 제외 효과) ==========
    print("\n" + "=" * 80)
    print("8. 대형주 제외 효과 (20일 평균 거래대금 상한)")
    for atv_max in [50, 100, 200, 500, 99999]:
        trades = [t for t in all_trades if t.get("avg_tv_20", 0) < atv_max]
        s = stats(trades, f"avgTV<{atv_max}억")
        print_stats(s)

    # 상한+하한 조합
    print("\n  -- 상/하한 조합 --")
    for lo, hi in [(5, 100), (5, 200), (10, 100), (10, 200), (10, 500), (20, 200), (20, 500)]:
        trades = [t for t in all_trades if lo <= t.get("avg_tv_20", 0) < hi]
        s = stats(trades, f"avgTV {lo}~{hi}억")
        print_stats(s)


if __name__ == "__main__":
    main()
