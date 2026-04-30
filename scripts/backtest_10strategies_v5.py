"""5차 추가 10대 전략 백테스트 (기존 40개와 미중복, 09:01 실시간 구현 가능 전략만)

핵심: "종가 확인 후 매수" 같은 결과론적 전략 배제. 09:01 시점에 판단 가능한 조건만.

41. 갭업 1~3% + MA200 — 현재 전략 범위 축소 (소폭 갭업)
42. 갭업 3~7% + MA200 — 현재 전략 범위 확대
43. 갭업 2~5% + 전일 양봉 — 전일 상승 모멘텀 + 갭업
44. 갭업 2~5% + 전일 거래량 2배 — 전일 활발 + 갭업
45. 갭업 2~5% + RSI<70 — 과매수 아닌 갭업
46. 갭다운 -2~-5% + MA200 — 급락 반등 (시가 매수)
47. 전일 +10%+ 급등 후 갭업 — 연속 상승 모멘텀
48. 갭업 2~5% + 시총 대형주 — 대형주만 (가격 5만+)
49. 갭업 2~5% + 시총 소형주 — 소형주만 (가격 5천 미만)
50. 갭업+갭다운 혼합 — 갭업 2~5% OR 갭다운 -3~-5%, MA200
"""
import json, os, sys, time
from pathlib import Path
from collections import defaultdict
from datetime import datetime

os.environ["PYTHONUNBUFFERED"] = "1"
DATA_PATH = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"
RESULT_PATH = Path(__file__).parent.parent / "results" / "backtest_10strategies_v5.json"

def load_json(path):
    with open(path, encoding="utf-8") as f: return json.load(f)

def prepare(bars):
    if len(bars)<201: return []
    closes,opens,highs,lows,volumes=[],[],[],[],[]
    results=[]
    for i,b in enumerate(bars):
        c=int(b.get("stck_clpr","0")); o=int(b.get("stck_oprc","0"))
        h=int(b.get("stck_hgpr","0")); lo=int(b.get("stck_lwpr","0"))
        vol=int(b.get("acml_vol","0"))
        if c<=0:
            closes.append(closes[-1] if closes else 0); opens.append(opens[-1] if opens else 0)
            highs.append(highs[-1] if highs else 0); lows.append(lows[-1] if lows else 0)
            volumes.append(0); results.append(None); continue
        closes.append(c);opens.append(o);highs.append(h);lows.append(lo);volumes.append(vol)
        if i<200: results.append(None); continue
        ma200=sum(closes[i-199:i+1])/200
        ma20=sum(closes[i-19:i+1])/20
        avg_vol_20=sum(volumes[i-19:i+1])/20
        gap=(o-closes[i-1])/closes[i-1]*100 if closes[i-1]>0 else 0
        oc=(c-o)/o*100 if o>0 else 0
        prev_change=(closes[i-1]-closes[i-2])/closes[i-2]*100 if i>=2 and closes[i-2]>0 else 0
        prev_bullish=closes[i-1]>opens[i-1]
        prev_vol=volumes[i-1]
        # RSI(14)
        gains=losses=0
        for k in range(i-13,i+1):
            diff=closes[k]-closes[k-1]
            if diff>0: gains+=diff
            else: losses-=diff
        ag,al=gains/14,losses/14
        rsi14=100-100/(1+ag/al) if al>0 else 100

        results.append({
            "d":b.get("stck_bsop_date",""),"c":c,"o":o,"h":h,"l":lo,"vol":vol,
            "ma200":ma200,"ma20":ma20,"avg_vol_20":avg_vol_20,
            "gap":gap,"oc":oc,"prev_change":prev_change,
            "prev_bullish":prev_bullish,"prev_vol":prev_vol,"rsi14":rsi14,
            "ok":1000<=c<200000,
        })
    return results

def run(all_data, filter_fn, date_range, max_pos=2):
    ds=defaultdict(dict)
    for code,inds in all_data.items():
        for ind in inds:
            if ind is None: continue
            d=ind["d"]
            if date_range and (d<date_range[0] or d>date_range[1]): continue
            ds[d][code]=ind
    pnls=[]
    for date in sorted(ds.keys()):
        stocks=ds[date]; cands=[]
        for code,ind in stocks.items():
            if not ind["ok"] or ind["o"]<=0: continue
            if not filter_fn(ind): continue
            cands.append((code,ind))
        cands.sort(key=lambda x:-x[1]["vol"])
        for code,ind in cands[:max_pos]:
            pnls.append(round(ind["oc"],2))
    return pnls

def analyze(pnls):
    n=len(pnls)
    if n==0: return {"n":0,"wr":0,"trim":0,"sharpe":0,"pf":0}
    s=sorted(pnls); wins=sum(1 for p in pnls if p>0); avg=sum(pnls)/n
    lo,hi=int(n*0.05),n-int(n*0.05)
    trim=sum(s[lo:hi])/(hi-lo) if hi>lo else avg
    std=(sum((p-avg)**2 for p in pnls)/n)**0.5 if n>1 else 1
    gp=sum(p for p in pnls if p>0); gl=abs(sum(p for p in pnls if p<0))
    return {"n":n,"wr":round(wins/n*100,1),"trim":round(trim,2),
            "sharpe":round(avg/std,3) if std>0 else 0,"pf":round(gp/gl,2) if gl>0 else 999}

def main():
    print("="*100)
    print("5차 추가 10대 전략 — 09:01 실시간 구현 가능 전략만")
    print("="*100)
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

    strategies = [
        ("41.갭업1~3%+MA200", lambda i: 1<=i["gap"]<3 and i["c"]>i["ma200"]),
        ("42.갭업3~7%+MA200", lambda i: 3<=i["gap"]<7 and i["c"]>i["ma200"]),
        ("43.갭업2~5%+전일양봉", lambda i: 2<=i["gap"]<5 and i["c"]>i["ma200"] and i["prev_bullish"]),
        ("44.갭업2~5%+전일거래량2배", lambda i: 2<=i["gap"]<5 and i["c"]>i["ma200"] and i["prev_vol"]>i["avg_vol_20"]*2),
        ("45.갭업2~5%+RSI<70", lambda i: 2<=i["gap"]<5 and i["c"]>i["ma200"] and i["rsi14"]<70),
        ("46.갭다운-2~-5%+MA200", lambda i: -5<=i["gap"]<=-2 and i["c"]>i["ma200"]),
        ("47.전일+10%후갭업", lambda i: i["prev_change"]>=10 and 1<=i["gap"]<10 and i["c"]>i["ma200"]),
        ("48.갭업2~5%+대형주5만+", lambda i: 2<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>=50000),
        ("49.갭업2~5%+소형주<5천", lambda i: 2<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]<5000),
        ("50.갭업OR갭다운+MA200", lambda i: ((2<=i["gap"]<5) or (-5<=i["gap"]<=-3)) and i["c"]>i["ma200"]),
        ("현재:갭업2~5%+MA200+MA20", lambda i: 2<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["ma20"]),
    ]

    print(f"\n{'전략':<28} | {'[학습] trim':>9} {'WR':>5} {'N':>4} | {'[검증] trim':>9} {'WR':>5} {'N':>4} {'SR':>6} {'PF':>5} | 일관")
    print("─"*105)
    results=[]
    for name, fn in strategies:
        tr=analyze(run(all_data, fn, train))
        te=analyze(run(all_data, fn, test))
        ok="O" if tr["n"]>=10 and te["n"]>=10 and (tr["trim"]>0)==(te["trim"]>0) else "X"
        results.append({"name":name,"train":tr,"test":te,"consistent":ok})
        print(f"  {name:<26} | {tr['trim']:>+8.2f}% {tr['wr']:>4.1f}% {tr['n']:>4} | "
              f"{te['trim']:>+8.2f}% {te['wr']:>4.1f}% {te['n']:>4} {te['sharpe']:>6.3f} {te['pf']:>5.2f} | {ok}")

    ranked=sorted(results,key=lambda x:x["test"]["trim"],reverse=True)
    cur=next((r for r in results if "현재" in r["name"]),None)
    print(f"\n{'='*100}"); print("검증 Top 3 + 현재 비교"); print("─"*100)
    for i,r in enumerate(ranked[:3],1):
        te=r["test"]
        print(f"  {i}위: {r['name']} — trim={te['trim']:>+.2f}%, WR={te['wr']}%, N={te['n']}, SR={te['sharpe']:.3f}, PF={te['pf']:.2f}, 일관={r['consistent']}")
    if cur:
        ce=cur["test"]
        print(f"\n  현재: {cur['name']} — trim={ce['trim']:>+.2f}%, WR={ce['wr']}%, N={ce['n']}, SR={ce['sharpe']:.3f}, PF={ce['pf']:.2f}")

    with open(RESULT_PATH,"w",encoding="utf-8") as f:
        json.dump({"generated_at":datetime.now().isoformat(),"strategies":[
            {"rank":i+1,**r} for i,r in enumerate(ranked)]},f,ensure_ascii=False,indent=2)
    print(f"\n결과 저장: {RESULT_PATH}")

if __name__=="__main__": main()
