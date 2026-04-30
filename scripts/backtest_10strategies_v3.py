"""3차 추가 10대 전략 백테스트 (기존 20개와 미중복)

21. 갭업 모멘텀 — 시가 갭업 +2%+ 매수, 당일 종가 매도
22. Heikin-Ashi 2-Red — HA 2연속 적색봉 후 매수, 종가>전일고가 매도
23. 4일 연속 하락 반등 — 4일 연속 하락 매수, 종가>전일고가 매도
24. RSI(14) 과매도 — RSI(14)<30 매수, >50 매도
25. 5일 모멘텀 Top — 5일 수익률 양수 + 거래량 상위 매수
26. 패닉셀링 반등 — 거래량 2배+ & 하락 매수, 종가>전일고가 매도
27. MA20 터치 반등 — MA20 ±1% 범위 터치 + 양봉 매수
28. Donchian 20일 돌파 — 20일 고가 돌파 매수, 20일 저가 이탈 매도
29. 종가 하위20% 반등 — 종가가 당일 레인지 하위 20% + MA200 위 매수
30. 대량 음봉 후 양봉 — 전일 거래량 3배+음봉, 당일 양봉 전환 매수
"""
import json, os, sys, time
from pathlib import Path
from collections import defaultdict
from datetime import datetime

os.environ["PYTHONUNBUFFERED"] = "1"
DATA_PATH = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"
RESULT_PATH = Path(__file__).parent.parent / "results" / "backtest_10strategies_v3.json"

def load_json(path):
    with open(path, encoding="utf-8") as f: return json.load(f)

def prepare_stock(bars):
    if len(bars) < 201: return []
    closes, opens, highs, lows, volumes = [], [], [], [], []
    results = []
    for i, b in enumerate(bars):
        c = int(b.get("stck_clpr","0")); o = int(b.get("stck_oprc","0"))
        h = int(b.get("stck_hgpr","0")); lo = int(b.get("stck_lwpr","0"))
        vol = int(b.get("acml_vol","0"))
        if c <= 0:
            closes.append(closes[-1] if closes else 0); opens.append(opens[-1] if opens else 0)
            highs.append(highs[-1] if highs else 0); lows.append(lows[-1] if lows else 0)
            volumes.append(0); results.append(None); continue
        closes.append(c); opens.append(o); highs.append(h); lows.append(lo); volumes.append(vol)
        if i < 200: results.append(None); continue

        ma5 = sum(closes[i-4:i+1])/5
        ma20 = sum(closes[i-19:i+1])/20
        ma200 = sum(closes[i-199:i+1])/200
        prev_ma5 = sum(closes[i-5:i])/5
        prev_ma20 = sum(closes[i-20:i])/20
        avg_vol_20 = sum(volumes[i-19:i+1])/20

        # RSI(14)
        gains = losses = 0
        for k in range(i-13, i+1):
            diff = closes[k]-closes[k-1]
            if diff > 0: gains += diff
            else: losses -= diff
        ag14, al14 = gains/14, losses/14
        rsi14 = 100-100/(1+ag14/al14) if al14 > 0 else 100.0

        # IBS
        ibs = (c-lo)/(h-lo) if h != lo else 0.5

        # Heikin Ashi (간소화: 당일/전일)
        ha_close = (o+h+lo+c)//4
        ha_open_prev = (opens[i-1]+closes[i-1])//2
        ha_close_prev = (opens[i-1]+highs[i-1]+lows[i-1]+closes[i-1])//4
        ha_open_prev2 = (opens[i-2]+closes[i-2])//2
        ha_close_prev2 = (opens[i-2]+highs[i-2]+lows[i-2]+closes[i-2])//4
        ha_red_today = ha_close < (o+ha_close)//2  # 간소화
        ha_red_prev = ha_close_prev < ha_open_prev
        ha_red_prev2 = ha_close_prev2 < ha_open_prev2

        # 4일 연속 하락
        four_down = all(closes[i-k] < closes[i-k-1] for k in range(4))

        # 5일 수익률
        mom5 = (c-closes[i-5])/closes[i-5]*100 if closes[i-5] > 0 else 0

        # 갭업
        gap_up = (o-closes[i-1])/closes[i-1]*100 if closes[i-1] > 0 else 0

        # 전일 거래량/캔들
        prev_vol = volumes[i-1]
        prev_bearish = closes[i-1] < opens[i-1]
        today_bullish = c > o

        # 20일 고가/저가
        high_20d = max(highs[i-19:i])  # 전일까지
        low_20d = min(lows[i-19:i])

        # MA20 근접 (±1%)
        ma20_near = abs(c - ma20)/ma20 < 0.01 if ma20 > 0 else False

        results.append({
            "d": b.get("stck_bsop_date",""), "c": c, "o": o, "h": h, "l": lo, "vol": vol,
            "ma5": ma5, "ma20": ma20, "ma200": ma200,
            "prev_ma5": prev_ma5, "prev_ma20": prev_ma20,
            "avg_vol_20": avg_vol_20, "rsi14": rsi14, "ibs": ibs,
            "ha_2red": ha_red_prev and ha_red_prev2,
            "four_down": four_down, "mom5": mom5, "gap_up": gap_up,
            "prev_vol": prev_vol, "prev_bearish": prev_bearish,
            "today_bullish": today_bullish,
            "high_20d": high_20d, "low_20d": low_20d,
            "ma20_near": ma20_near,
            "prev_high": highs[i-1], "prev_close": closes[i-1],
            "ok": 1000 <= c < 200000,
        })
    return results

# ── 전략 함수 ─────────────────────────────────────────────────

def strat_gap_up_momentum(ind, holding):
    """21. 갭업 모멘텀: 시가 갭업 +2%+ → 당일 종가 매도"""
    if holding: return "sell"  # 항상 당일 매도
    if ind["gap_up"] >= 2 and ind["ok"]: return "buy"
    return None

def strat_ha_2red(ind, holding):
    """22. HA 2-Red: 2연속 HA 적색봉 후 매수"""
    if holding: return "sell" if ind["c"] > ind["prev_high"] else "hold"
    if ind["ha_2red"] and ind["c"] > ind["ma200"] and ind["ok"]: return "buy"
    return None

def strat_four_down(ind, holding):
    """23. 4일 연속 하락 반등"""
    if holding: return "sell" if ind["c"] > ind["prev_high"] else "hold"
    if ind["four_down"] and ind["c"] > ind["ma200"] and ind["ok"]: return "buy"
    return None

def strat_rsi14_oversold(ind, holding):
    """24. RSI(14) 과매도: <30 매수, >50 매도"""
    if holding: return "sell" if ind["rsi14"] > 50 else "hold"
    if ind["rsi14"] < 30 and ind["c"] > ind["ma200"] and ind["ok"]: return "buy"
    return None

def strat_momentum5(ind, holding):
    """25. 5일 모멘텀: 5일 수익률 +5%+ & 거래량 상위 매수"""
    if holding: return "hold"
    if ind["mom5"] >= 5 and ind["vol"] > ind["avg_vol_20"] * 1.5 and ind["ok"]: return "buy"
    return None

def strat_panic_sell_bounce(ind, holding):
    """26. 패닉셀링 반등: 거래량 2배+ & 하락 매수"""
    if holding: return "sell" if ind["c"] > ind["prev_high"] else "hold"
    if ind["vol"] > ind["avg_vol_20"] * 2 and ind["c"] < ind["prev_close"] and ind["c"] > ind["ma200"] and ind["ok"]:
        return "buy"
    return None

def strat_ma20_touch(ind, holding):
    """27. MA20 터치 반등: MA20 근접 + 양봉 매수"""
    if holding: return "sell" if ind["c"] > ind["prev_high"] else "hold"
    if ind["ma20_near"] and ind["today_bullish"] and ind["c"] > ind["ma200"] and ind["ok"]:
        return "buy"
    return None

def strat_donchian_breakout(ind, holding):
    """28. Donchian 20일 돌파: 종가>20일고가 매수, <20일저가 매도"""
    if holding:
        return "sell" if ind["c"] < ind["low_20d"] else "hold"
    if ind["c"] > ind["high_20d"] and ind["ok"]: return "buy"
    return None

def strat_close_bottom20(ind, holding):
    """29. 종가 하위20%: 종가가 당일레인지 하위20% + MA200 위 매수"""
    if holding: return "sell" if ind["c"] > ind["prev_high"] else "hold"
    if ind["ibs"] < 0.2 and ind["c"] > ind["ma200"] and ind["c"] > ind["ma20"] and ind["ok"]:
        return "buy"
    return None

def strat_big_bear_bull_flip(ind, holding):
    """30. 대량 음봉→양봉: 전일 거래량3배+음봉 → 당일 양봉 매수"""
    if holding: return "hold"
    if (ind["prev_vol"] > ind["avg_vol_20"] * 3 and ind["prev_bearish"]
        and ind["today_bullish"] and ind["c"] > ind["ma200"] and ind["ok"]):
        return "buy"
    return None

def strat_current(ind, holding):
    if holding: return "hold"
    score = 0; c = ind["c"]
    if c > ind["prev_close"]: score += 5
    if c < 20000: score += 5
    if ind["vol"] > ind["avg_vol_20"]*1.5: score += 10
    if ind["ma5"] > ind["ma20"] and ind["prev_ma5"] <= ind["prev_ma20"]: score += 5
    if c > ind["prev_high"]: score += 5
    if score >= 15 and ind["ok"]: return "buy"
    return None

STRATEGIES = [
    ("21.GapUp_Mom", strat_gap_up_momentum, {"tp": 0, "sl": 0, "ts": 0, "max_hold": 1}),
    ("22.HA_2Red", strat_ha_2red, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 10}),
    ("23.Four_Down", strat_four_down, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 10}),
    ("24.RSI14_Oversold", strat_rsi14_oversold, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 20}),
    ("25.Momentum5", strat_momentum5, {"tp": 7, "sl": -2, "ts": -3, "max_hold": 5}),
    ("26.PanicSell_Bounce", strat_panic_sell_bounce, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 10}),
    ("27.MA20_Touch", strat_ma20_touch, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 10}),
    ("28.Donchian_Break", strat_donchian_breakout, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 30}),
    ("29.Close_Bot20", strat_close_bottom20, {"tp": 0, "sl": -5, "ts": 0, "max_hold": 10}),
    ("30.BigBear_BullFlip", strat_big_bear_bull_flip, {"tp": 7, "sl": -2, "ts": -3, "max_hold": 5}),
    ("현재시스템", strat_current, {"tp": 7, "sl": -2, "ts": -3, "max_hold": 5}),
]

def run_strategy(all_data, fn, params, date_range=None, max_pos=2):
    tp,sl,ts,mh = params["tp"],params["sl"],params["ts"],params["max_hold"]
    ds = defaultdict(dict)
    for code, inds in all_data.items():
        for ind in inds:
            if ind is None: continue
            d = ind["d"]
            if date_range and (d < date_range[0] or d > date_range[1]): continue
            ds[d][code] = ind
    dates = sorted(ds.keys()); pnls = []; holdings = {}
    for di, date in enumerate(dates):
        stocks = ds[date]; sold = set()
        for code in list(holdings.keys()):
            ind = stocks.get(code)
            if ind is None: continue
            bp,bi,pk = holdings[code]; h,lo,c = ind["h"],ind["l"],ind["c"]; hd = di-bi
            if h > pk: pk=h; holdings[code]=(bp,bi,pk)
            hp=(h-bp)/bp*100; lp=(lo-bp)/bp*100; cp=(c-bp)/bp*100
            drop=(c-pk)/pk*100 if pk>0 else 0
            do_sell=False; sp=cp
            if fn(ind, True) == "sell": do_sell=True
            if tp>0 and hp>=tp: do_sell=True; sp=tp
            if sl<0 and lp<=sl: do_sell=True; sp=sl
            if ts<0 and cp>0 and drop<=ts: do_sell=True; sp=cp
            if mh>0 and hd>=mh: do_sell=True
            if do_sell: pnls.append(round(sp,2)); del holdings[code]; sold.add(code)
        if len(holdings)>=max_pos: continue
        cands = [(code,ind) for code,ind in stocks.items()
                 if code not in holdings and code not in sold and fn(ind,False)=="buy"]
        cands.sort(key=lambda x: -x[1]["vol"])
        for code,ind in cands[:max_pos-len(holdings)]:
            bp = ind["o"] if fn == strat_gap_up_momentum else ind["c"]
            holdings[code]=(bp,di,bp)
    if dates:
        last = ds[dates[-1]]
        for code,(bp,bi,pk) in holdings.items():
            ind = last.get(code)
            if ind: pnls.append(round((ind["c"]-bp)/bp*100,2))
    return pnls

def analyze(pnls):
    n=len(pnls)
    if n==0: return {"n":0,"wr":0,"trim":0,"sharpe":0,"pf":0,"mdd":0,"med":0}
    s=sorted(pnls); wins=sum(1 for p in pnls if p>0); avg=sum(pnls)/n; med=s[n//2]
    lo,hi=int(n*0.05),n-int(n*0.05)
    trim=sum(s[lo:hi])/(hi-lo) if hi>lo else avg
    std=(sum((p-avg)**2 for p in pnls)/n)**0.5 if n>1 else 1
    cum=pk=mdd=0
    for p in pnls:
        cum+=p
        if cum>pk: pk=cum
        dd=pk-cum
        if dd>mdd: mdd=dd
    gp=sum(p for p in pnls if p>0); gl=abs(sum(p for p in pnls if p<0))
    return {"n":n,"wr":round(wins/n*100,1),"trim":round(trim,2),"med":round(med,2),
            "sharpe":round(avg/std,3) if std>0 else 0,"pf":round(gp/gl,2) if gl>0 else 999,"mdd":round(mdd,1)}

def main():
    print("="*90); print("3차 추가 10대 전략 백테스트"); print("="*90)
    data = load_json(DATA_PATH)
    all_data = {}
    for code, info in data.items():
        bars = info.get("bars",[])
        if len(bars)<300: continue
        tvs=[int(b.get("acml_tr_pbmn","0")) for b in bars[-100:]]
        if sum(tvs)/len(tvs)<1_000_000_000: continue
        inds = prepare_stock(bars)
        if inds: all_data[code]=inds
    print(f"유효: {len(all_data)}종목")
    all_dates = sorted({ind["d"] for inds in all_data.values() for ind in inds if ind})
    mid = len(all_dates)//2
    train=(all_dates[0],all_dates[mid]); test=(all_dates[mid+1],all_dates[-1])
    print(f"학습: {train[0]}~{train[1]} | 검증: {test[0]}~{test[1]}")

    print(f"\n{'전략':<22} | {'[학습] trim':>9} {'WR':>5} {'N':>5} {'SR':>6} {'PF':>5} | {'[검증] trim':>9} {'WR':>5} {'N':>5} {'SR':>6} {'PF':>5} | 일관")
    print("─"*115)
    results = []
    for name,fn,params in STRATEGIES:
        tr=analyze(run_strategy(all_data,fn,params,date_range=train))
        te=analyze(run_strategy(all_data,fn,params,date_range=test))
        ok="O" if tr["n"]>=10 and te["n"]>=10 and (tr["trim"]>0)==(te["trim"]>0) else "X"
        results.append({"name":name,"train":tr,"test":te,"consistent":ok})
        print(f"{name:<22} | {tr['trim']:>+8.2f}% {tr['wr']:>4.1f}% {tr['n']:>5} {tr['sharpe']:>6.3f} {tr['pf']:>5.2f} "
              f"| {te['trim']:>+8.2f}% {te['wr']:>4.1f}% {te['n']:>5} {te['sharpe']:>6.3f} {te['pf']:>5.2f} | {ok}")

    ranked=sorted(results,key=lambda x:x["test"]["trim"],reverse=True)
    cur=next((r for r in results if "현재" in r["name"]),None)
    print(f"\n{'='*90}"); print("검증 Top 3 + 현재 비교"); print("─"*90)
    for i,r in enumerate(ranked[:3],1):
        te=r["test"]
        print(f"  {i}위: {r['name']} — trim={te['trim']:>+.2f}%, WR={te['wr']}%, N={te['n']}, SR={te['sharpe']:.3f}, PF={te['pf']:.2f}, 일관={r['consistent']}")
    if cur:
        ce=cur["test"]
        print(f"\n  현재: {cur['name']} — trim={ce['trim']:>+.2f}%, WR={ce['wr']}%, N={ce['n']}, SR={ce['sharpe']:.3f}, PF={ce['pf']:.2f}")
        print(f"\n  Top3 vs 현재:")
        for i,r in enumerate(ranked[:3],1):
            te=r["test"]
            print(f"    {i}위 {r['name']:22s}: trim {te['trim']-ce['trim']:>+.2f}%p, WR {te['wr']-ce['wr']:>+.1f}%p, SR {te['sharpe']:.3f} vs {ce['sharpe']:.3f}")

    with open(RESULT_PATH,"w",encoding="utf-8") as f:
        json.dump({"generated_at":datetime.now().isoformat(),"strategies":[
            {"rank":i+1,**r} for i,r in enumerate(ranked)]},f,ensure_ascii=False,indent=2)
    print(f"\n결과 저장: {RESULT_PATH}")

if __name__=="__main__": main()
