#!/usr/bin/env python3
"""대규모 파라미터 스윕 백테스트.

데이터: results/daily_ohlcv_all.json (353MB, 2618종목×500일)
Baseline: 거래대금 TOP2, 가격 1000~200000, 상승출발, 갭<10%, 쿨다운 3일, 종가청산
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"
OUT_PATH = Path(__file__).parent.parent / "docs" / "research" / "2026-04-10-parameter-sweep.md"

# ETF/ETN/스팩 제외 패턴
EXCLUDE_NAMES = re.compile(r"KODEX|TIGER|KOSEF|ACE|SOL|KBSTAR|HANARO|ETN|스팩|선물")
CODE_PATTERN = re.compile(r"^\d{6}$")


def load_data():
    print("데이터 로딩 중...")
    with open(DATA_PATH) as f:
        raw = json.load(f)

    # 전처리: 숫자 변환 + 날짜별 인덱싱
    stocks = {}  # code -> {name, bars_by_date}
    all_dates = set()

    for code, info in raw.items():
        if not CODE_PATTERN.match(code):
            continue
        if EXCLUDE_NAMES.search(info["name"]):
            continue

        bars_by_date = {}
        for b in info["bars"]:
            d = b["stck_bsop_date"]
            bars_by_date[d] = {
                "date": d,
                "close": int(b["stck_clpr"]),
                "open": int(b["stck_oprc"]),
                "high": int(b["stck_hgpr"]),
                "low": int(b["stck_lwpr"]),
                "volume": int(b["acml_vol"]),
                "tv": int(b["acml_tr_pbmn"]),
                "sign": b["prdy_vrss_sign"],
                "vrss": int(b["prdy_vrss"]),
            }
            all_dates.add(d)

        if bars_by_date:
            stocks[code] = {"name": info["name"], "bars": bars_by_date}

    dates = sorted(all_dates)
    print(f"종목 {len(stocks)}개, 거래일 {len(dates)}일 로드 완료")
    return stocks, dates


def get_prev_date(dates, date_idx):
    """date_idx의 전일 인덱스 반환."""
    return date_idx - 1 if date_idx > 0 else None


def run_backtest(stocks, dates, *,
                 top_n=2, gap_max=0.10, cooldown=3,
                 stop_loss=None,  # None=없음, -0.02 등
                 price_min=1000, price_max=200000,
                 sort_mode="absolute",  # "absolute", "increase_rate", "composite"
                 price_range=None,  # (min, max) for 가격대 필터 (G 테스트)
                 gap_range=None,  # (min, max) for 갭 크기 필터 (H 테스트)
                 pattern_filter=None,  # "upper_tail", "bearish", "streak3", None
                 pattern_invert=False,  # True면 패턴 아닌 것만
                 ):
    """백테스트 실행. 매일 필터 통과 종목 중 top_n 매수 → 당일 청산."""

    trades = []  # list of pnl%
    cooldown_map = defaultdict(int)  # code -> 마지막 매수 date_idx

    for di in range(1, len(dates)):
        today = dates[di]
        prev_idx = di - 1
        yesterday = dates[prev_idx]

        candidates = []
        for code, sinfo in stocks.items():
            bar = sinfo["bars"].get(today)
            prev_bar = sinfo["bars"].get(yesterday)
            if not bar or not prev_bar:
                continue

            # 쿨다운 체크
            if cooldown > 0 and cooldown_map.get(code, -999) > di - cooldown:
                continue

            o, c, h, l = bar["open"], bar["close"], bar["high"], bar["low"]
            prev_c = prev_bar["close"]
            tv = bar["tv"]

            if prev_c == 0 or o == 0:
                continue

            # 가격 필터
            if not (price_min <= o <= price_max):
                continue

            # 가격대 필터 (G 테스트용)
            if price_range and not (price_range[0] <= o < price_range[1]):
                continue

            # 상승 출발 (시가 > 전일종가)
            gap = (o - prev_c) / prev_c
            if gap <= 0:
                continue

            # 갭 상한
            if gap_max is not None and gap > gap_max:
                continue

            # 갭 크기 필터 (H 테스트용)
            if gap_range and not (gap_range[0] <= gap < gap_range[1]):
                continue

            # 전일 패턴 필터 (I 테스트용)
            if pattern_filter:
                match = _check_pattern(stocks, code, dates, prev_idx, pattern_filter)
                if pattern_invert:
                    if match:
                        continue
                else:
                    if not match:
                        continue

            # 전일 거래대금 (sort_mode에 필요)
            prev_tv = prev_bar["tv"]

            if sort_mode == "absolute":
                score = tv
            elif sort_mode == "increase_rate":
                score = tv / prev_tv if prev_tv > 0 else 0
            elif sort_mode == "composite":
                rate = tv / prev_tv if prev_tv > 0 else 0
                score = tv * rate
            else:
                score = tv

            candidates.append((code, score, bar))

        # TOP N 선정
        candidates.sort(key=lambda x: x[1], reverse=True)
        selected = candidates[:top_n]

        for code, _, bar in selected:
            o = bar["open"]
            c = bar["close"]
            h = bar["high"]
            l = bar["low"]

            # 손절 체크
            if stop_loss is not None and l <= o * (1 + stop_loss):
                exit_price = o * (1 + stop_loss)
            else:
                exit_price = c

            pnl = (exit_price - o) / o
            trades.append(pnl)
            cooldown_map[code] = di

    return _summarize(trades)


def _check_pattern(stocks, code, dates, prev_idx, pattern):
    """전일(prev_idx) 기준으로 패턴 체크."""
    sinfo = stocks[code]

    if pattern == "upper_tail":
        # 전일 윗꼬리 > 3%
        bar = sinfo["bars"].get(dates[prev_idx])
        if not bar:
            return False
        h, c, o = bar["high"], bar["close"], bar["open"]
        body_top = max(c, o)
        if h == 0:
            return False
        tail = (h - body_top) / h
        return tail > 0.03

    elif pattern == "bearish":
        # 전일 음봉 (종가 < 시가)
        bar = sinfo["bars"].get(dates[prev_idx])
        if not bar:
            return False
        return bar["close"] < bar["open"]

    elif pattern == "streak3":
        # 연속 상승 3일+
        if prev_idx < 2:
            return False
        for i in range(3):
            idx = prev_idx - i
            bar = sinfo["bars"].get(dates[idx])
            if not bar:
                return False
            if bar["close"] <= bar["open"]:
                return False
            # 전일 대비 상승도 체크
            if idx > 0:
                prev_bar = sinfo["bars"].get(dates[idx - 1])
                if prev_bar and bar["close"] <= prev_bar["close"]:
                    return False
        return True

    return False


def _summarize(trades):
    """거래 리스트 → 요약 dict."""
    if not trades:
        return {"n": 0, "avg": 0, "win_rate": 0, "profit_factor": 0, "cumul": 0}

    n = len(trades)
    avg = sum(trades) / n * 100
    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t <= 0]
    win_rate = len(wins) / n * 100

    total_win = sum(wins) if wins else 0
    total_loss = abs(sum(losses)) if losses else 0.0001
    pf = total_win / total_loss if total_loss > 0 else 999

    cumul = sum(trades) * 100  # 단리 누적 (%)

    return {"n": n, "avg": round(avg, 3), "win_rate": round(win_rate, 1),
            "profit_factor": round(pf, 2), "cumul": round(cumul, 1)}


def fmt_row(label, s):
    return f"| {label} | {s['n']} | {s['avg']:.3f}% | {s['win_rate']:.1f}% | {s['profit_factor']:.2f} | {s['cumul']:.1f}% |"


def main():
    stocks, dates = load_data()

    results = []  # (section_title, rows)
    header = "| 조건 | 거래수 | 평균수익률 | 승률 | 손익비 | 누적수익(단리) |"
    sep = "|------|--------|-----------|------|--------|--------------|"

    # ── A. 종목 수 ──
    print("\n=== A. 종목 수 ===")
    rows = []
    for top_n in [1, 2, 3, 5]:
        s = run_backtest(stocks, dates, top_n=top_n)
        label = f"TOP{top_n}" + (" ★baseline" if top_n == 2 else "")
        rows.append(fmt_row(label, s))
        print(f"  TOP{top_n}: {s}")
    results.append(("A. 종목 수 (TOP N)", rows))

    # ── B. 갭 상한 ──
    print("\n=== B. 갭 상한 ===")
    rows = []
    for gap in [0.05, 0.07, 0.10, 0.15, 0.20, None]:
        s = run_backtest(stocks, dates, gap_max=gap)
        label = f"갭≤{int(gap*100)}%" if gap else "제한없음"
        if gap == 0.10:
            label += " ★baseline"
        rows.append(fmt_row(label, s))
        print(f"  gap_max={gap}: {s}")
    results.append(("B. 갭 상한", rows))

    # ── C. 쿨다운 ──
    print("\n=== C. 쿨다운 ===")
    rows = []
    for cd in [0, 1, 3, 5]:
        s = run_backtest(stocks, dates, cooldown=cd)
        label = f"{cd}일" + (" ★baseline" if cd == 3 else "")
        rows.append(fmt_row(label, s))
        print(f"  cooldown={cd}: {s}")
    results.append(("C. 쿨다운", rows))

    # ── D. 손절 ──
    print("\n=== D. 손절 (저가 proxy) ===")
    rows = []
    for sl in [None, -0.02, -0.03, -0.05, -0.07]:
        s = run_backtest(stocks, dates, stop_loss=sl)
        label = f"SL {int(sl*100)}%" if sl else "없음(종가청산) ★baseline"
        rows.append(fmt_row(label, s))
        print(f"  stop_loss={sl}: {s}")
    results.append(("D. 손절 (저가 기반 proxy)", rows))

    # ── E. 스킵 (look-ahead) ──

    # ── F. 거래대금 정렬 방식 ──
    print("\n=== F. 거래대금 정렬 ===")
    rows = []
    for mode in ["absolute", "increase_rate", "composite"]:
        s = run_backtest(stocks, dates, sort_mode=mode)
        label_map = {
            "absolute": "절대 거래대금 ★baseline",
            "increase_rate": "전일대비 증가율",
            "composite": "절대×증가율 복합",
        }
        rows.append(fmt_row(label_map[mode], s))
        print(f"  sort={mode}: {s}")
    results.append(("F. 거래대금 정렬 방식", rows))

    # ── G. 가격대별 성과 ──
    print("\n=== G. 가격대별 성과 ===")
    rows = []
    for pmin, pmax in [(1000, 5000), (5000, 10000), (10000, 50000), (50000, 200000)]:
        s = run_backtest(stocks, dates, price_range=(pmin, pmax))
        rows.append(fmt_row(f"{pmin:,}~{pmax:,}", s))
        print(f"  price {pmin}-{pmax}: {s}")
    results.append(("G. 가격대별 성과", rows))

    # ── H. 갭 크기별 성과 ──
    print("\n=== H. 갭 크기별 성과 ===")
    rows = []
    for gmin, gmax in [(0, 0.02), (0.02, 0.05), (0.05, 0.10), (0.10, 0.15), (0.15, 1.0)]:
        s = run_backtest(stocks, dates, gap_max=None, gap_range=(gmin, gmax))
        label = f"갭 {gmin*100:.0f}~{gmax*100:.0f}%"
        if gmax == 1.0:
            label = "갭 15%+"
        rows.append(fmt_row(label, s))
        print(f"  gap {gmin}-{gmax}: {s}")
    results.append(("H. 갭 크기별 성과", rows))

    # ── I. 전일 패턴 가점 검증 ──
    print("\n=== I. 전일 패턴 검증 ===")
    rows = []
    for pat, pat_name in [("upper_tail", "윗꼬리>3%"), ("bearish", "전일 음봉"), ("streak3", "연속상승 3일+")]:
        s_yes = run_backtest(stocks, dates, pattern_filter=pat, pattern_invert=False)
        s_no = run_backtest(stocks, dates, pattern_filter=pat, pattern_invert=True)
        rows.append(fmt_row(f"{pat_name} O", s_yes))
        rows.append(fmt_row(f"{pat_name} X", s_no))
        print(f"  {pat_name} O: {s_yes}")
        print(f"  {pat_name} X: {s_no}")
    results.append(("I. 전일 패턴 가점 검증", rows))

    # ── 마크다운 출력 ──
    lines = [
        "# 파라미터 스윕 백테스트 결과",
        "",
        f"- **데이터:** daily_ohlcv_all.json ({len(stocks)}종목, {len(dates)}거래일)",
        f"- **기간:** {dates[0]} ~ {dates[-1]}",
        "- **Baseline:** 거래대금 TOP2, 가격 1000~200000, 상승출발, 갭<10%, 쿨다운 3일, 종가청산",
        "- **수익 계산:** 시가 매수 → 종가 청산 (단리)",
        "",
    ]

    for title, rows in results:
        lines.append(f"## {title}")
        lines.append("")
        lines.append(header)
        lines.append(sep)
        for r in rows:
            lines.append(r)
        lines.append("")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n결과 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
