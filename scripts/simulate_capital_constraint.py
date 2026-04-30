"""1000만원 시작 자본으로 각 시뮬 전략을 실제 운용했을 때 결과 비교

규칙:
- 시작 자본: 1000만원
- 매수 일자별 가용 자본을 그날 매수 종목 수로 균등 분할
  (예: 가용 1000만원 + 매수 종목 4개면 250만원씩)
- 청산 시 (매수금액 + 손익) 자본 회수 (복리)
- 보유 중 종목은 현재가 기준 unrealized로 평가

시뮬 종목들을 시간 순으로 매수→청산 시뮬레이션.
현재 화면 표시값(자본 무한 가정)과 비교.
"""
import os, sys, json
import requests
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import dotenv
dotenv.load_dotenv()

url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SECRET_KEY')
sb = {'apikey': key, 'Authorization': f'Bearer {key}'}
KST = timezone(timedelta(hours=9))

START_CAPITAL = 10_000_000   # 시작 자본 1천만원


def get_kis_token():
    cred = requests.get(
        f'{url}/rest/v1/api_credentials?service_name=eq.kis_mock&credential_type=eq.access_token&is_active=eq.true&select=credential_value',
        headers=sb).json()
    return json.loads(cred[0]['credential_value'])['access_token']


def get_price(code, token):
    KAK, KAS = os.getenv('KIS_APP_KEY', ''), os.getenv('KIS_APP_SECRET', '')
    h = {'content-type': 'application/json', 'authorization': f'Bearer {token}',
         'appkey': KAK, 'appsecret': KAS, 'tr_id': 'FHKST01010100', 'custtype': 'P'}
    try:
        r = requests.get('https://openapivts.koreainvestment.com:29443/uapi/domestic-stock/v1/quotations/inquire-price',
                         headers=h, params={'FID_COND_MRKT_DIV_CODE': 'J', 'FID_INPUT_ISCD': code}, timeout=5)
        return int(r.json().get('output', {}).get('stck_prpr', 0))
    except:
        return 0


def simulate(label, items, get_buy_price, get_sell_price, get_buy_time, get_sell_time, current_price_fn):
    """이벤트 기반 시뮬레이션 — 매일 가용 자본을 그날 매수 종목 수로 균등 분할.

    매수 일자별로 그룹핑 → 그 일자의 가용 자본 ÷ 매수 종목 수 = 종목당 금액
    청산 시 자본 회수 (복리).
    """
    print(f"\n{'='*70}")
    print(f"{label}")
    print('='*70)

    # 매수 일자별 그룹핑 (그날 매수 종목 수 계산용)
    buy_by_date = defaultdict(list)
    sell_events = []
    for i, t in enumerate(items):
        bt = get_buy_time(t)
        bp = get_buy_price(t)
        st = get_sell_time(t)
        sp = get_sell_price(t)
        if not bt or not bp:
            continue
        bdate = bt.astimezone(KST).strftime('%Y-%m-%d')
        buy_by_date[bdate].append((bt, i, bp))
        if st and sp:
            sell_events.append((st, i, sp))

    # 모든 이벤트를 시간 순으로 통합 (BUY는 일자별 그룹으로 묶어서 처리)
    all_events = []
    for bdate, buys in buy_by_date.items():
        # 그날 매수들의 가장 이른 시각 = BUY_BATCH 시점
        earliest = min(b[0] for b in buys)
        all_events.append((earliest, 'BUY_BATCH', bdate, buys))
    for st, i, sp in sell_events:
        all_events.append((st, 'SELL', i, sp))
    all_events.sort(key=lambda x: x[0])

    capital = START_CAPITAL
    holdings = {}  # i -> {'qty', 'invest', 'item', 'buy_price'}
    bought = 0
    closed_realized = 0

    for ev_time, ev_type, *args in all_events:
        if ev_type == 'BUY_BATCH':
            bdate, buys = args
            n = len(buys)
            if capital <= 0 or n == 0:
                continue
            per_stock = capital // n  # 그날 가용 자본 균등 분할
            for bt, i, price in buys:
                qty = per_stock // price
                if qty <= 0:
                    continue
                invest = qty * price
                capital -= invest
                holdings[i] = {'qty': qty, 'invest': invest, 'item': items[i], 'buy_price': price}
                bought += 1
        elif ev_type == 'SELL':
            i, price = args
            if i in holdings:
                h = holdings.pop(i)
                proceeds = h['qty'] * price
                profit = proceeds - h['invest']
                capital += proceeds
                closed_realized += profit

    # 보유 중 종목 평가
    unrealized = 0
    holdings_invest = 0
    for i, h in holdings.items():
        holdings_invest += h['invest']
        cp = current_price_fn(h['item'])
        if cp > 0:
            unrealized += (cp - h['buy_price']) * h['qty']

    total_now = capital + holdings_invest + unrealized
    total_pnl = total_now - START_CAPITAL
    total_pnl_pct = total_pnl / START_CAPITAL * 100

    print(f"  시작 자본: {START_CAPITAL:,}원 → 최종(평가포함) {total_now:,}원")
    print(f"  총 손익: {total_pnl:+,}원 ({total_pnl_pct:+.2f}%)")
    print(f"  실현 {closed_realized:+,}원 + 평가 {unrealized:+,}원")
    print(f"  매수 {bought}건 / 전체 {len(items)}건 (보유 중 {len(holdings)}종목)")
    return {
        'final_pnl_pct': total_pnl_pct,
        'final_pnl': total_pnl,
        'bought': bought,
        'skipped': len(items) - bought,
        'holdings': len(holdings),
    }


def to_dt(s):
    if not s: return None
    try: return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except: return None


def main():
    print(f"\n{'#'*70}")
    print(f"# 1000만원 시작 자본 시뮬레이션 (매일 가용 자본을 매수 종목 수로 균등 분할)")
    print(f"{'#'*70}")

    token = get_kis_token()

    # 데이터 로드
    print("\n데이터 로드 중...")
    sims_all = requests.get(f'{url}/rest/v1/strategy_simulations?select=*&order=created_at.asc',
                            headers=sb).json()
    trades_all = requests.get(f'{url}/rest/v1/auto_trades?select=*&order=created_at.asc',
                              headers=sb).json()
    trade_map = {t['id']: t for t in trades_all}
    print(f"  simulations: {len(sims_all)}, trades: {len(trades_all)}")

    # 현재가 캐시 (보유 종목용)
    price_cache = {}
    def cur_price_for_sim(s):
        mt = trade_map.get(s.get('trade_id'))
        if not mt: return 0
        code = mt.get('code', '')
        if not code: return 0
        if code not in price_cache:
            price_cache[code] = get_price(code, token)
        return price_cache[code]

    def cur_price_for_gapup(t):
        code = t.get('code', '')
        if not code: return 0
        if code not in price_cache:
            price_cache[code] = get_price(code, token)
        return price_cache[code]

    # 각 시뮬별 시뮬레이션
    results = []

    # 1. 5팩터 stepped
    sims = [s for s in sims_all if s['strategy_type'] == 'stepped']
    r = simulate(
        f"5팩터+Stepped (누적, {len(sims)}건)",
        sims,
        get_buy_price=lambda s: s.get('entry_price') or 0,
        get_sell_price=lambda s: s.get('exit_price') or 0,
        get_buy_time=lambda s: to_dt(s.get('created_at')),
        get_sell_time=lambda s: to_dt(s.get('exited_at')) if s.get('status') == 'closed' else None,
        current_price_fn=cur_price_for_sim,
    )
    results.append(('5팩터+Stepped', '+5.62%', r))

    # 2. 고정 익절/손절
    sims = [s for s in sims_all if s['strategy_type'] == 'fixed']
    r = simulate(
        f"고정 익절/손절 (누적, {len(sims)}건)",
        sims,
        get_buy_price=lambda s: s.get('entry_price') or 0,
        get_sell_price=lambda s: s.get('exit_price') or 0,
        get_buy_time=lambda s: to_dt(s.get('created_at')),
        get_sell_time=lambda s: to_dt(s.get('exited_at')) if s.get('status') == 'closed' else None,
        current_price_fn=cur_price_for_sim,
    )
    results.append(('고정 익절/손절', '-0.05%', r))

    # 3. 시간전략 11시
    sims = [s for s in sims_all if s['strategy_type'] == 'time_exit']
    r = simulate(
        f"시간전략 11시 (회전, {len(sims)}건)",
        sims,
        get_buy_price=lambda s: s.get('entry_price') or 0,
        get_sell_price=lambda s: s.get('exit_price') or 0,
        get_buy_time=lambda s: to_dt(s.get('created_at')),
        get_sell_time=lambda s: to_dt(s.get('exited_at')) if s.get('status') == 'closed' else None,
        current_price_fn=cur_price_for_sim,
    )
    results.append(('시간전략 11시', '+4.57%', r))

    # 4. 10시 청산
    sims = [s for s in sims_all if s['strategy_type'] == 'tv_time_exit']
    r = simulate(
        f"10시 청산 (회전, {len(sims)}건)",
        sims,
        get_buy_price=lambda s: s.get('entry_price') or 0,
        get_sell_price=lambda s: s.get('exit_price') or 0,
        get_buy_time=lambda s: to_dt(s.get('created_at')),
        get_sell_time=lambda s: to_dt(s.get('exited_at')) if s.get('status') == 'closed' else None,
        current_price_fn=cur_price_for_sim,
    )
    results.append(('10시 청산', '+5.04%', r))

    # 5. API매수∧대장주
    sims = [s for s in sims_all if s['strategy_type'] == 'api_leader']
    r = simulate(
        f"API매수∧대장주 (누적, {len(sims)}건)",
        sims,
        get_buy_price=lambda s: s.get('entry_price') or 0,
        get_sell_price=lambda s: s.get('exit_price') or 0,
        get_buy_time=lambda s: to_dt(s.get('created_at')),
        get_sell_time=lambda s: to_dt(s.get('exited_at')) if s.get('status') == 'closed' else None,
        current_price_fn=cur_price_for_sim,
    )
    results.append(('API매수∧대장주', '+3.73%', r))

    # 6. 갭업 모멘텀 (sim_only)
    gapup = [t for t in trades_all if t.get('status') == 'sim_only' and t.get('sell_reason') == 'gapup_sim']
    r = simulate(
        f"갭업 모멘텀 sim_only (회전, {len(gapup)}건)",
        gapup,
        get_buy_price=lambda t: t.get('order_price') or 0,
        get_sell_price=lambda t: t.get('sell_price') or 0,
        get_buy_time=lambda t: to_dt(t.get('created_at')),
        get_sell_time=lambda t: to_dt(t.get('sold_at') or t.get('created_at', '').replace('T00:', 'T15:').replace('00:00:', '15:15:') if t.get('sell_price') else None),
        current_price_fn=cur_price_for_gapup,
    )
    results.append(('갭업 모멘텀', '+0.95%', r))

    # 종합 비교
    print(f"\n{'#'*70}")
    print(f"# 종합 비교: 화면 표시값 vs 1000만원 자본 운용")
    print(f"{'#'*70}\n")
    print(f"{'시뮬':<20} {'현재 화면':>10} {'1000만원 자본':>15} {'매수/스킵':>15}")
    print('-' * 70)
    for label, cur_pct, r in results:
        diff = f"{r['final_pnl_pct']:+.2f}%"
        action = f"{r['bought']}/{r['skipped']}"
        print(f"{label:<20} {cur_pct:>10} {diff:>15} {action:>15}")


if __name__ == '__main__':
    main()
