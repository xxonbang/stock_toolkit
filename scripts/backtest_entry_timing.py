"""
매수 타이밍 백테스트: 09:05 vs 09:15~09:20 지연 매수 시뮬레이션

일봉 데이터만으로 직접적인 분봉 비교는 불가하므로,
다음 proxy 모델을 사용:

1. "시가 매수" = 09:00 시가에 매수 (가장 빠른 매수)
2. "확인 매수" = 시가 + α*(고가-시가) 에 매수 (모멘텀 확인 후 진입)
   - α=0.2 → 시가 대비 고가까지 상승분의 20% 지점 (09:10~09:15 추정)
   - α=0.4 → 시가 대비 고가까지 상승분의 40% 지점 (09:15~09:25 추정)
3. 매도: 종가 (15:15~15:30 청산)

추가 분석:
- 시가 dip 이후 매수: 시가가 아닌 "시가 하회 후 시가 회복 시점" 매수를 모델링
  → 저가 < 시가인 날 (intraday dip 발생): 시가에 재진입 가정
  → 저가 >= 시가인 날 (dip 없음): 시가 매수와 동일

핵심 가정: "확인 매수"는 상승 확인 후 진입하므로,
해당 일 종가 > 시가인 날만 진입 (하락일은 스킵 = 필터링 효과)
"""

import json
import sys
from collections import defaultdict

def load_data():
    print("Loading daily OHLCV...")
    with open('/Users/sonbyeongcheol/DEV/stock_toolkit/results/daily_ohlcv_all.json') as f:
        return json.load(f)

def run_backtest(ohlcv):
    # 전 종목 날짜별 거래대금 TOP2 추출
    # 필터: 가격 1,000~200,000원, ETF/ETN/스팩 제외 (code 6자리 숫자)

    date_stocks = defaultdict(list)

    for code, stock in ohlcv.items():
        # 코드 필터: 6자리 숫자만 (ETF/ETN/스팩 제외)
        if len(code) != 6 or not code.isdigit():
            continue
        name = stock.get('name', '')
        # 스팩/ETF 이름 필터
        if any(kw in name for kw in ['스팩', 'ETF', 'ETN', 'KODEX', 'TIGER', 'KOSEF', 'KBSTAR', 'HANARO', 'SOL', 'ACE']):
            continue

        for bar in stock.get('bars', []):
            dt = bar.get('stck_bsop_date', '')
            op = int(bar.get('stck_oprc', 0))
            hi = int(bar.get('stck_hgpr', 0))
            lo = int(bar.get('stck_lwpr', 0))
            cl = int(bar.get('stck_clpr', 0))
            tv = int(bar.get('acml_tr_pbmn', 0))
            vol = int(bar.get('acml_vol', 0))

            if op <= 0 or cl <= 0 or hi <= 0 or lo <= 0:
                continue
            # 가격 필터
            if op < 1000 or op > 200000:
                continue
            # 상승 출발 (시가 > 전일 종가는 확인 불가이므로 생략)
            # 거래대금 필터: 최소 10억
            if tv < 1_000_000_000:
                continue

            date_stocks[dt].append({
                'code': code, 'name': name,
                'open': op, 'high': hi, 'low': lo, 'close': cl,
                'tv': tv,
            })

    # 날짜 정렬
    dates = sorted(date_stocks.keys())
    print(f"분석 기간: {dates[0]}~{dates[-1]} ({len(dates)}거래일)")

    # 각 전략별 결과 수집
    results = {
        'open_buy': [],           # 시가 매수 → 종가 매도
        'confirm_20': [],         # 확인 매수 α=0.2
        'confirm_40': [],         # 확인 매수 α=0.4
        'confirm_20_filter': [],  # 확인 매수 α=0.2 + 상승 확인 필터
        'confirm_40_filter': [],  # 확인 매수 α=0.4 + 상승 확인 필터
    }

    # 쿨다운 추적 (3일 lookback)
    recent_traded = {}  # code → last_trade_date

    for dt in dates:
        stocks = date_stocks[dt]
        # 거래대금 TOP 정렬
        stocks.sort(key=lambda x: x['tv'], reverse=True)

        # 쿨다운 필터: 최근 3거래일 내 거래한 종목 제외
        filtered = []
        for s in stocks:
            last = recent_traded.get(s['code'])
            if last and _days_between(last, dt, dates) <= 3:
                continue
            filtered.append(s)
            if len(filtered) >= 2:
                break

        if len(filtered) < 2:
            # 쿨다운으로 2종목 미달 시 나머지에서 채움
            for s in stocks:
                if s not in filtered:
                    filtered.append(s)
                    if len(filtered) >= 2:
                        break

        top2 = filtered[:2]

        for s in top2:
            code = s['code']
            op, hi, lo, cl = s['open'], s['high'], s['low'], s['close']

            recent_traded[code] = dt

            # 1. 시가 매수
            pnl_open = (cl - op) / op * 100
            results['open_buy'].append(pnl_open)

            # 2. 확인 매수 (무조건 진입)
            if hi > op:
                entry_20 = op + 0.2 * (hi - op)
                entry_40 = op + 0.4 * (hi - op)
                pnl_20 = (cl - entry_20) / entry_20 * 100
                pnl_40 = (cl - entry_40) / entry_40 * 100
                results['confirm_20'].append(pnl_20)
                results['confirm_40'].append(pnl_40)
            else:
                # 시가 = 고가 (하락만 한 날)
                results['confirm_20'].append(pnl_open)
                results['confirm_40'].append(pnl_open)

            # 3. 확인 매수 + 상승 필터 (고가 > 시가*1.01 일때만 진입)
            if hi > op * 1.01:
                entry_20 = op + 0.2 * (hi - op)
                entry_40 = op + 0.4 * (hi - op)
                pnl_20f = (cl - entry_20) / entry_20 * 100
                pnl_40f = (cl - entry_40) / entry_40 * 100
                results['confirm_20_filter'].append(pnl_20f)
                results['confirm_40_filter'].append(pnl_40f)
            # 필터 미충족 시 거래 안 함 (스킵)

    return results

def _days_between(dt1, dt2, all_dates):
    """두 날짜 사이의 거래일 수"""
    try:
        i1 = all_dates.index(dt1)
        i2 = all_dates.index(dt2)
        return abs(i2 - i1)
    except ValueError:
        return 999

def print_results(results):
    print("\n" + "=" * 70)
    print("백테스트 결과: 거래대금 TOP2 매수 → 종가 청산")
    print("=" * 70)

    for label, key in [
        ("① 시가 매수 (09:00 즉시)", 'open_buy'),
        ("② 확인 매수 α=0.2 (시가~고가 20% 지점)", 'confirm_20'),
        ("③ 확인 매수 α=0.4 (시가~고가 40% 지점)", 'confirm_40'),
        ("④ 확인 매수 α=0.2 + 상승>1% 필터", 'confirm_20_filter'),
        ("⑤ 확인 매수 α=0.4 + 상승>1% 필터", 'confirm_40_filter'),
    ]:
        data = results[key]
        if not data:
            continue
        n = len(data)
        avg = sum(data) / n
        wins = sum(1 for x in data if x > 0)
        losses = sum(1 for x in data if x <= 0)
        win_rate = wins / n * 100

        # 승률이 아닌 평균 수익도 중요
        win_avg = sum(x for x in data if x > 0) / wins if wins else 0
        loss_avg = sum(x for x in data if x <= 0) / losses if losses else 0

        # 누적 수익률 (단리)
        cumulative = sum(data)

        # 최대 연속 손실
        max_streak = 0
        streak = 0
        for x in data:
            if x <= 0:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0

        print(f"\n{label}")
        print(f"  거래 수: {n}건")
        print(f"  평균 수익률: {avg:+.2f}%")
        print(f"  승률: {win_rate:.1f}% ({wins}W / {losses}L)")
        print(f"  평균 이익: {win_avg:+.2f}% | 평균 손실: {loss_avg:+.2f}%")
        print(f"  손익비: {abs(win_avg/loss_avg):.2f}" if loss_avg != 0 else "  손익비: N/A")
        print(f"  누적 수익: {cumulative:+.1f}% (단리)")
        print(f"  최대 연속 손실: {max_streak}거래")

    # 직접 비교: 동일 날짜에서 시가 vs 확인매수 차이
    open_data = results['open_buy']
    confirm_data = results['confirm_20']
    n = min(len(open_data), len(confirm_data))

    better_open = sum(1 for i in range(n) if open_data[i] > confirm_data[i])
    better_confirm = sum(1 for i in range(n) if confirm_data[i] > open_data[i])
    same = n - better_open - better_confirm

    print(f"\n{'=' * 70}")
    print(f"직접 비교 (동일 {n}건):")
    print(f"  시가 매수 > 확인 매수: {better_open}건 ({better_open/n*100:.1f}%)")
    print(f"  확인 매수 > 시가 매수: {better_confirm}건 ({better_confirm/n*100:.1f}%)")
    print(f"  동일: {same}건")

    # 연도별/월별 분석
    print(f"\n{'=' * 70}")
    print("확인 매수 α=0.2 + 상승필터 vs 시가 매수 — 연간 비교")
    print(f"  시가 매수 연간 합계: {sum(open_data):+.1f}%")
    if results['confirm_20_filter']:
        print(f"  확인 매수(필터) 연간 합계: {sum(results['confirm_20_filter']):+.1f}%")
        print(f"  거래 수 차이: {len(open_data)} → {len(results['confirm_20_filter'])} (필터로 {len(open_data)-len(results['confirm_20_filter'])}건 스킵)")

if __name__ == '__main__':
    ohlcv = load_data()
    results = run_backtest(ohlcv)
    print_results(results)
