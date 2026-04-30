"""4차 추가 10대 전략 백테스트 (기존 30개와 미중복)

31. 시가 레인지 돌파 — 첫 30분 고가 돌파 매수, 당일 종가 매도
32. 전일 대비 갭다운 반전 양봉 — 갭다운 후 양봉 전환 매수 (당일 매도)
33. 대량거래 음봉 후 갭업 — 전일 대량음봉 + 오늘 갭업 매수 (당일)
34. 연속 음봉 후 양봉 전환 — 3일 음봉 후 양봉 매수, 종가>전일고가 매도
35. RSI(14)+MACD 동시 매수 — RSI<40 + MACD 양전환 매수
36. 52주 신고가 돌파 — 52주 고가 돌파 + 거래량 매수
37. MA5/MA20 데드크로스 역매수 — 데드크로스 후 반등 매수
38. 전일 상한가 익일 매수 — 전일 +15%+ 종목 익일 시가 매수
39. 종가 대비 시가 갭업 + 양봉 — 갭업 + 당일 양봉 확인 매수 (당일)
40. 거래대금 폭발 + 상승 — 거래대금 5배 + 양봉 매수 (TP/SL)
"""
import json, os, sys, time
from pathlib import Path
from collections import defaultdict
from datetime import datetime

os.environ["PYTHONUNBUFFERED"] = "1"
DATA_PATH = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"
RESULT_PATH = Path(__file__).parent.parent / "results" / "backtest_10strategies_v4.json"

def load_json(path):
    with open(path, encoding="utf-8") as f: return json.load(f)

def prepare(bars):
    if len(bars)<201: return []
    closes,opens,highs,lows,volumes=[],[],[],[],[]
    results=[]
    for i,b in enumerate(bars):
        c=int(b.get("stck_clpr","0")); o=int(b.get("stck_oprc","0"))
        h=int(b.get("stck_hgpr","0")); lo=int(b.get("stck_lwpr","0"))
        vol=int(b.get("acml_vol","0")); tv=int(b.get("acml_tr_pbmn","0"))
        if c<=0:
            closes.append(closes[-1] if closes else 0); opens.append(opens[-1] if opens else 0)
            highs.append(highs[-1] if highs else 0); lows.append(lows[-1] if lows else 0)
            volumes.append(0); results.append(None); continue
        closes.append(c);opens.append(o);highs.append(h);lows.append(lo);volumes.append(vol)
        if i<200: results.append(None); continue

        ma5=sum(closes[i-4:i+1])/5; ma20=sum(closes[i-19:i+1])/20; ma200=sum(closes[i-199:i+1])/200
        avg_vol_20=sum(volumes[i-19:i+1])/20
        avg_tv_20=sum(int(bars[k].get("acml_tr_pbmn","0")) for k in range(max(0,i-19),i+1))/20
        gap=(o-closes[i-1])/closes[i-1]*100 if closes[i-1]>0 else 0
        oc=(c-o)/o*100 if o>0 else 0
        prev_change=(closes[i-1]-closes[i-2])/closes[i-2]*100 if i>=2 and closes[i-2]>0 else 0
        prev_oc=(closes[i-1]-opens[i-1])/opens[i-1]*100 if opens[i-1]>0 else 0

        # RSI(14)
        gains=losses=0
        for k in range(i-13,i+1):
            diff=closes[k]-closes[k-1]
            if diff>0: gains+=diff
            else: losses-=diff
        ag,al=gains/14,losses/14
        rsi14=100-100/(1+ag/al) if al>0 else 100

        # MACD (12,26 SMA 간소화)
        ema12=sum(closes[i-11:i+1])/12; ema26=sum(closes[i-25:i+1])/26
        macd=ema12-ema26
        prev_ema12=sum(closes[i-12:i])/12; prev_ema26=sum(closes[i-26:i])/26
        prev_macd=prev_ema12-prev_ema26

        prev_ma5=sum(closes[i-5:i])/5; prev_ma20=sum(closes[i-20:i])/20
        # 52주 고가
        high_250=max(highs[max(0,i-249):i]) if i>=250 else max(highs[:i]) if i>0 else h
        # 3일 연속 음봉
        three_bear=all(closes[i-k]<opens[i-k] for k in range(1,4)) if i>=4 else False
        bullish=c>o
        bearish=c<o
        prev_bearish=closes[i-1]<opens[i-1]
        prev_bullish=closes[i-1]>opens[i-1]

        results.append({
            "d":b.get("stck_bsop_date",""),"c":c,"o":o,"h":h,"l":lo,"vol":vol,"tv":tv,
            "ma5":ma5,"ma20":ma20,"ma200":ma200,"avg_vol_20":avg_vol_20,"avg_tv_20":avg_tv_20,
            "gap":gap,"oc":oc,"prev_change":prev_change,"prev_oc":prev_oc,
            "rsi14":rsi14,"macd":macd,"prev_macd":prev_macd,
            "prev_ma5":prev_ma5,"prev_ma20":prev_ma20,
            "high_250":high_250,"three_bear":three_bear,
            "bullish":bullish,"bearish":bearish,"prev_bearish":prev_bearish,"prev_bullish":prev_bullish,
            "prev_high":highs[i-1],"prev_close":closes[i-1],"prev_vol":volumes[i-1],
            "prev_open":opens[i-1],
            "ok":1000<=c<200000,
        })
    return results

# ── 전략 함수 ─────────────────────────────────────────────────

def s31_opening_range(ind, h):
    """31. 시가 레인지 돌파: 시가 대비 +1%+ 돌파 매수, 당일 종가 매도"""
    if h: return "sell"
    if ind["h"]>ind["o"]*1.01 and ind["c"]>ind["o"] and ind["ok"]: return "buy"
    return None

def s32_gapdown_bull_flip(ind, h):
    """32. 갭다운 반전 양봉: 갭다운 -1%+ & 양봉 매수"""
    if h: return "sell"
    if ind["gap"]<=-1 and ind["bullish"] and ind["c"]>ind["ma200"] and ind["ok"]: return "buy"
    return None

def s33_bigbear_gapup(ind, h):
    """33. 전일 대량음봉 + 오늘 갭업"""
    if h: return "sell"
    if (ind["prev_bearish"] and ind["prev_vol"]>ind["avg_vol_20"]*2
        and ind["gap"]>=1 and ind["ok"]): return "buy"
    return None

def s34_bear_to_bull(ind, h):
    """34. 3일 음봉 후 양봉 전환"""
    if h: return "sell" if ind["c"]>ind["prev_high"] else "hold"
    if ind["three_bear"] and ind["bullish"] and ind["c"]>ind["ma200"] and ind["ok"]: return "buy"
    return None

def s35_rsi_macd(ind, h):
    """35. RSI<40 + MACD 양전환"""
    if h: return "sell" if ind["c"]>ind["prev_high"] else "hold"
    if (ind["rsi14"]<40 and ind["macd"]>0 and ind["prev_macd"]<=0
        and ind["c"]>ind["ma200"] and ind["ok"]): return "buy"
    return None

def s36_52w_high(ind, h):
    """36. 52주 신고가 돌파 + 거래량"""
    if h: return "hold"
    if (ind["c"]>ind["high_250"] and ind["vol"]>ind["avg_vol_20"]*1.5 and ind["ok"]): return "buy"
    return None

def s37_dead_cross_bounce(ind, h):
    """37. MA5/MA20 데드크로스 후 반등"""
    if h: return "sell" if ind["c"]>ind["prev_high"] else "hold"
    # 데드크로스 발생 후 양봉
    if (ind["prev_ma5"]>ind["prev_ma20"] and ind["ma5"]<=ind["ma20"]
        and ind["bullish"] and ind["c"]>ind["ma200"] and ind["ok"]): return "buy"
    return None

def s38_limit_up_next(ind, h):
    """38. 전일 상한가(+15%+) 종목 익일 시가 매수"""
    if h: return "sell"
    if ind["prev_change"]>=15 and ind["ok"]: return "buy"
    return None

def s39_gapup_bull_confirm(ind, h):
    """39. 갭업 + 양봉 확인: 갭업 1~5% + 당일 양봉"""
    if h: return "sell"
    if 1<=ind["gap"]<5 and ind["bullish"] and ind["c"]>ind["ma200"] and ind["ok"]: return "buy"
    return None

def s40_tv_explosion(ind, h):
    """40. 거래대금 5배 + 양봉"""
    if h: return "hold"
    if (ind["avg_tv_20"]>0 and ind["tv"]>ind["avg_tv_20"]*5
        and ind["bullish"] and ind["ok"]): return "buy"
    return None

def s_current(ind, h):
    """현재 갭업 모멘텀"""
    if h: return "sell"
    if 2<=ind["gap"]<5 and ind["c"]>ind["ma200"] and ind["c"]>ind["ma20"] and ind["ok"]: return "buy"
    return None

STRATEGIES = [
    ("31.OpenRange", s31_opening_range, {"tp":0,"sl":0,"ts":0,"max_hold":1}),
    ("32.GapDn_BullFlip", s32_gapdown_bull_flip, {"tp":0,"sl":0,"ts":0,"max_hold":1}),
    ("33.BigBear_GapUp", s33_bigbear_gapup, {"tp":0,"sl":0,"ts":0,"max_hold":1}),
    ("34.3Bear_Bull", s34_bear_to_bull, {"tp":0,"sl":-5,"ts":0,"max_hold":10}),
    ("35.RSI_MACD", s35_rsi_macd, {"tp":0,"sl":-5,"ts":0,"max_hold":10}),
    ("36.52W_High", s36_52w_high, {"tp":7,"sl":-2,"ts":-3,"max_hold":5}),
    ("37.DeadX_Bounce", s37_dead_cross_bounce, {"tp":0,"sl":-5,"ts":0,"max_hold":10}),
    ("38.LimitUp_Next", s38_limit_up_next, {"tp":0,"sl":0,"ts":0,"max_hold":1}),
    ("39.GapUp_Bull", s39_gapup_bull_confirm, {"tp":0,"sl":0,"ts":0,"max_hold":1}),
    ("40.TV_Explosion", s40_tv_explosion, {"tp":7,"sl":-2,"ts":-3,"max_hold":5}),
    ("갭업모멘텀(현재)", s_current, {"tp":0,"sl":0,"ts":0,"max_hold":1}),
]

def run(all_data, fn, params, date_range=None, max_pos=2):
    tp,sl,ts,mh=params["tp"],params["sl"],params["ts"],params["max_hold"]
    ds=defaultdict(dict)
    for code,inds in all_data.items():
        for ind in inds:
            if ind is None: continue
            d=ind["d"]
            if date_range and (d<date_range[0] or d>date_range[1]): continue
            ds[d][code]=ind
    dates=sorted(ds.keys()); pnls=[]; holdings={}
    for di,date in enumerate(dates):
        stocks=ds[date]; sold=set()
        for code in list(holdings.keys()):
            ind=stocks.get(code)
            if ind is None: continue
            bp,bi,pk=holdings[code]; h_,lo_,c_=ind["h"],ind["l"],ind["c"]; hd=di-bi
            if h_>pk: pk=h_; holdings[code]=(bp,bi,pk)
            hp=(h_-bp)/bp*100; lp=(lo_-bp)/bp*100; cp=(c_-bp)/bp*100
            drop=(c_-pk)/pk*100 if pk>0 else 0
            do_sell=False; sp=cp
            act=fn(ind,True)
            if act=="sell": do_sell=True
            if tp>0 and hp>=tp: do_sell=True; sp=tp
            if sl<0 and lp<=sl: do_sell=True; sp=sl
            if ts<0 and cp>0 and drop<=ts: do_sell=True; sp=cp
            if mh>0 and hd>=mh: do_sell=True
            if do_sell: pnls.append(round(sp,2)); del holdings[code]; sold.add(code)
        if len(holdings)>=max_pos: continue
        cands=[(code,ind) for code,ind in stocks.items()
               if code not in holdings and code not in sold and fn(ind,False)=="buy"]
        cands.sort(key=lambda x:-x[1]["vol"])
        for code,ind in cands[:max_pos-len(holdings)]:
            bp=ind["o"] if fn in (s31_opening_range,s32_gapdown_bull_flip,s33_bigbear_gapup,
                                   s38_limit_up_next,s39_gapup_bull_confirm,s_current) else ind["c"]
            holdings[code]=(bp,di,bp)
    if dates:
        last=ds[dates[-1]]
        for code,(bp,bi,pk) in holdings.items():
            ind=last.get(code)
            if ind: pnls.append(round((ind["c"]-bp)/bp*100,2))
    return pnls

def analyze(pnls):
    n=len(pnls)
    if n==0: return {"n":0,"wr":0,"trim":0,"sharpe":0,"pf":0,"med":0}
    s=sorted(pnls); wins=sum(1 for p in pnls if p>0); avg=sum(pnls)/n; med=s[n//2]
    lo,hi=int(n*0.05),n-int(n*0.05)
    trim=sum(s[lo:hi])/(hi-lo) if hi>lo else avg
    std=(sum((p-avg)**2 for p in pnls)/n)**0.5 if n>1 else 1
    gp=sum(p for p in pnls if p>0); gl=abs(sum(p for p in pnls if p<0))
    return {"n":n,"wr":round(wins/n*100,1),"trim":round(trim,2),"med":round(med,2),
            "sharpe":round(avg/std,3) if std>0 else 0,"pf":round(gp/gl,2) if gl>0 else 999}

def main():
    print("="*90); print("4차 추가 10대 전략 백테스트"); print("="*90)
    data=load_json(DATA_PATH)
    all_data={}
    for code,info in data.items():
        bars=info.get("bars",[])
        if len(bars)<300: continue
        tvs=[int(b.get("acml_tr_pbmn","0")) for b in bars[-100:]]
        if sum(tvs)/len(tvs)<1_000_000_000: continue
        inds=prepare(bars)
        if inds: all_data[code]=inds
    print(f"유효: {len(all_data)}종목")
    all_dates=sorted({ind["d"] for inds in all_data.values() for ind in inds if ind})
    mid=len(all_dates)//2
    train=(all_dates[0],all_dates[mid]); test=(all_dates[mid+1],all_dates[-1])
    print(f"학습: {train[0]}~{train[1]} | 검증: {test[0]}~{test[1]}")

    print(f"\n{'전략':<22} | {'[학습] trim':>9} {'WR':>5} {'N':>5} {'SR':>6} {'PF':>5} | {'[검증] trim':>9} {'WR':>5} {'N':>5} {'SR':>6} {'PF':>5} | 일관")
    print("─"*115)
    results=[]
    for name,fn,params in STRATEGIES:
        tr=analyze(run(all_data,fn,params,date_range=train))
        te=analyze(run(all_data,fn,params,date_range=test))
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
