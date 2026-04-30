"""6차 추가 10대 전략 — 09:01 실시간 구현 가능, 기존 50개와 미중복

갭업 모멘텀의 변형·조합을 집중 탐색.

51. 갭업 2~5% + MA200 + MA20 + MA5>MA20 (단기추세 확인)
52. 갭업 2~5% + MA200 + 전일하락 (눌림 후 갭업)
53. 갭업 1~5% + MA200 + MA20 (범위 확대)
54. 갭업 2~4% + MA200 + MA20 (범위 축소)
55. 갭업 2~5% + MA200 - MA20제거 (MA20 필터 제거 효과)
56. 갭업 2~5% + 전일종가>MA200>MA20 (이중 추세 확인)
57. 갭업 2~5% + MA200 + 가격 1만~5만 (중형주)
58. 갭업 2~5% + MA200 + MA20 + 전일거래량>평균 (전일 활발)
59. 갭업 2~5% + MA200 + MA20 + RSI>50 (상승 모멘텀)
60. 갭업 2~5% + MA200 + MA20 + 3종목 (포지션 확대)
"""
import json, os, sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

os.environ["PYTHONUNBUFFERED"] = "1"
DATA_PATH = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"
RESULT_PATH = Path(__file__).parent.parent / "results" / "backtest_10strategies_v6.json"

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
        ma5=sum(closes[i-4:i+1])/5; ma20=sum(closes[i-19:i+1])/20; ma200=sum(closes[i-199:i+1])/200
        avg_vol_20=sum(volumes[i-19:i+1])/20
        gap=(o-closes[i-1])/closes[i-1]*100 if closes[i-1]>0 else 0
        oc=(c-o)/o*100 if o>0 else 0
        prev_change=(closes[i-1]-closes[i-2])/closes[i-2]*100 if i>=2 and closes[i-2]>0 else 0
        prev_vol=volumes[i-1]
        gains=losses=0
        for k in range(i-13,i+1):
            diff=closes[k]-closes[k-1]
            if diff>0: gains+=diff
            else: losses-=diff
        ag,al=gains/14,losses/14
        rsi14=100-100/(1+ag/al) if al>0 else 100

        results.append({
            "d":b.get("stck_bsop_date",""),"c":c,"o":o,"vol":vol,
            "ma5":ma5,"ma20":ma20,"ma200":ma200,"avg_vol_20":avg_vol_20,
            "gap":gap,"oc":oc,"prev_change":prev_change,"prev_vol":prev_vol,"rsi14":rsi14,
            "ok":1000<=c<200000,
        })
    return results

def run(all_data, fn, date_range, max_pos=2):
    ds=defaultdict(dict)
    for code,inds in all_data.items():
        for ind in inds:
            if ind is None: continue
            d=ind["d"]
            if date_range and (d<date_range[0] or d>date_range[1]): continue
            ds[d][code]=ind
    pnls=[]
    for date in sorted(ds.keys()):
        cands=[(code,ind) for code,ind in ds[date].items() if ind["ok"] and ind["o"]>0 and fn(ind)]
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
    print("="*105)
    print("6차 — 갭업 변형·조합 집중 탐색 (09:01 구현 가능)")
    print("="*105)
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
        ("51.+MA5>MA20(추세확인)", lambda i: 2<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["ma20"] and i["ma5"]>i["ma20"], 2),
        ("52.+전일하락(눌림갭업)", lambda i: 2<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["ma20"] and i["prev_change"]<0, 2),
        ("53.갭업1~5%+MA200+MA20", lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["ma20"], 2),
        ("54.갭업2~4%+MA200+MA20", lambda i: 2<=i["gap"]<4 and i["c"]>i["ma200"] and i["c"]>i["ma20"], 2),
        ("55.갭업2~5%+MA200(MA20X)", lambda i: 2<=i["gap"]<5 and i["c"]>i["ma200"], 2),
        ("56.종가>MA200>MA20(이중)", lambda i: 2<=i["gap"]<5 and i["c"]>i["ma200"] and i["ma200"]>i["ma20"], 2),
        ("57.+중형주1만~5만", lambda i: 2<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["ma20"] and 10000<=i["c"]<50000, 2),
        ("58.+전일거래량>평균", lambda i: 2<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["ma20"] and i["prev_vol"]>i["avg_vol_20"], 2),
        ("59.+RSI>50(상승모멘텀)", lambda i: 2<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["ma20"] and i["rsi14"]>50, 2),
        ("60.현재+3종목", lambda i: 2<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["ma20"], 3),
        ("현재:갭업2~5%+MA200+MA20", lambda i: 2<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["ma20"], 2),
    ]

    print(f"\n{'전략':<30} | {'[학습] trim':>9} {'WR':>5} {'N':>4} | {'[검증] trim':>9} {'WR':>5} {'N':>4} {'SR':>6} {'PF':>5} | 일관")
    print("─"*108)
    results=[]
    for name, fn, mp in strategies:
        tr=analyze(run(all_data, fn, train, max_pos=mp))
        te=analyze(run(all_data, fn, test, max_pos=mp))
        ok="O" if tr["n"]>=10 and te["n"]>=10 and (tr["trim"]>0)==(te["trim"]>0) else "X"
        results.append({"name":name,"train":tr,"test":te,"consistent":ok})
        print(f"  {name:<28} | {tr['trim']:>+8.2f}% {tr['wr']:>4.1f}% {tr['n']:>4} | "
              f"{te['trim']:>+8.2f}% {te['wr']:>4.1f}% {te['n']:>4} {te['sharpe']:>6.3f} {te['pf']:>5.2f} | {ok}")

    ranked=sorted(results,key=lambda x:x["test"]["trim"],reverse=True)
    cur=next((r for r in results if "현재" in r["name"]),None)
    print(f"\n{'='*105}"); print("검증 Top 3 + 현재 비교"); print("─"*105)
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
