#!/usr/bin/env python3
"""한국시장 시간대별 누적 거래량 곡선 추출 — 30일 순위 비선형 시간보정용.

intraday-history.json의 1484종목 × 30일 × 30분봉 데이터로 시장 평균 누적 비율 곡선 추출.
현재 선형 보정 (Portfolio.tsx:77) 대비 정확도 차이 측정.
"""
import json
import statistics
from collections import defaultdict


def main():
    d = json.load(open("frontend/public/data/intraday-history.json"))
    stocks = d["stocks"]
    print(f"종목 수: {len(stocks)}, updated_at: {d['updated_at']}")

    # 30분봉 시각 → 누적 종료 분(09:00 = 0분 기준)
    TIME_TO_END_MIN = {
        "09:30": 30, "10:00": 60, "10:30": 90, "11:00": 120, "11:30": 150,
        "12:00": 180, "12:30": 210, "13:00": 240, "13:30": 270, "14:00": 300,
        "14:30": 330, "15:00": 360, "15:30": 390,
    }
    cutoff_times = sorted(TIME_TO_END_MIN.values())

    # 각 종목 × 일자 단위로 시간대별 누적 비율 수집
    cum_ratios_at_time: dict[int, list[float]] = defaultdict(list)
    sample_count = 0

    for code, days in stocks.items():
        if not isinstance(days, list):
            continue
        for day in days:
            intervals = day.get("intervals_30m") or []
            if len(intervals) < 13:
                continue
            # 누적 거래량 계산
            cum = 0
            total = sum(iv.get("volume", 0) for iv in intervals)
            if total <= 0:
                continue
            for iv in intervals:
                t = iv.get("time", "")
                end_min = TIME_TO_END_MIN.get(t)
                if end_min is None:
                    continue
                cum += iv.get("volume", 0)
                cum_ratios_at_time[end_min].append(cum / total)
            sample_count += 1

    print(f"수집 표본: {sample_count}건 (종목×일자)")
    print()

    # 평균 / 중앙값 곡선 출력
    print(f"{'시각':>6} {'종료분':>6} {'선형':>8} {'평균비율':>10} {'중앙값':>10} {'선형오차':>10}")
    market_avg_curve = {}
    market_median_curve = {}
    for t, end_min in sorted(TIME_TO_END_MIN.items(), key=lambda x: x[1]):
        ratios = cum_ratios_at_time[end_min]
        if not ratios:
            continue
        avg = statistics.mean(ratios)
        med = statistics.median(ratios)
        linear = end_min / 390
        err = (avg - linear) / linear * 100
        print(f"{t:>6} {end_min:>6} {linear:>8.4f} {avg:>10.4f} {med:>10.4f} {err:>+9.2f}%")
        market_avg_curve[end_min] = avg
        market_median_curve[end_min] = med

    # 11:24 시점 (144분) 보간
    print("\n=== 11:24 (144분) 시점 추정 ===")
    # 10:30 = 90분 (cum_ratio), 11:00 = 120분, 11:30 = 150분
    # 11:24 = 11:30 - 6분
    # 선형 보간: 11:24 비율 = ratio_11:00 + (144-120)/(150-120) × (ratio_11:30 - ratio_11:00)
    r_1100 = market_avg_curve.get(120, 0)
    r_1130 = market_avg_curve.get(150, 0)
    interp = r_1100 + (144 - 120) / (150 - 120) * (r_1130 - r_1100)
    linear = 144 / 390
    print(f"  선형 가정: {linear:.4f} (36.92%)")
    print(f"  실제 시장 평균: {interp:.4f} ({interp*100:.2f}%)")
    print(f"  차이: {(interp - linear)/linear*100:+.1f}%")

    # SK하이닉스 5/20 11:24 시점 projected 재계산
    print("\n=== SK하이닉스 11:24 projected 재계산 ===")
    CUR_VOL = 4_427_100
    # 선형
    p_linear = CUR_VOL * 390 / 144
    # 비선형
    p_curve = CUR_VOL / interp
    print(f"  선형 projected:    {p_linear:>14,.0f} 주")
    print(f"  비선형 projected:  {p_curve:>14,.0f} 주")
    print(f"  차이: {(p_curve - p_linear)/p_linear*100:+.1f}%")

    # 30일 history와 순위 비교
    HIST = [6090287, 6396306, 11906741, 7998663, 5369802, 5242855, 8897661, 7524143, 5211225, 5607937,
            6256274, 6684824, 6004723, 9854593, 5388797, 8461155, 6021369, 5168665, 5358544, 10120675,
            11099704, 9908765, 7331920, 12911808, 15122207, 12803574, 9925086, 13151904, 10771377, 7805248]
    rank_linear = sorted(HIST + [round(p_linear)], reverse=True).index(round(p_linear)) + 1
    rank_curve = sorted(HIST + [round(p_curve)], reverse=True).index(round(p_curve)) + 1
    print(f"  선형 순위:   {rank_linear}/31")
    print(f"  비선형 순위: {rank_curve}/31")

    # 저장
    out = {
        "_meta": "시장 평균 시간대별 누적 거래량 비율 (30분봉 기준). 종목×일자 평균.",
        "_source": "intraday-history.json",
        "_samples": sample_count,
        "_updated_at": d["updated_at"],
        "cumulative_ratios": {
            f"end_min_{em}": {"time": t, "avg": market_avg_curve.get(em), "median": market_median_curve.get(em)}
            for t, em in TIME_TO_END_MIN.items() if em in market_avg_curve
        },
    }
    with open("docs/research/2026-05-20-intraday-curve.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n저장: docs/research/2026-05-20-intraday-curve.json")


if __name__ == "__main__":
    main()
