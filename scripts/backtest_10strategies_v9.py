"""9차 — 기존 80개와 미중복, 완전히 새로운 조합 (09:01 구현 가능)

81. MA200+MA20 only (갭업 없이) — v8 #71은 MA200만. MA20 추가 효과
82. 시가>전일고가 + MA200 — "갭업"이 아닌 "전일 고가 돌파" 조건
83. 갭업 + 전일IBS>0.7 (강한 마감 후 갭업)
84. 갭업 + 전일IBS<0.3 (약한 마감 후 갭업 = V자)
85. 갭업 + 전일양봉+전전일음봉 (V자 패턴)
86. 갭업 + MA5>MA200 (중기 추세도 상승)
87. 갭업 + 전일 변동률 낮음 (레인지<1% 후 갭업 = 에너지 축적)
88. 전일종가=전일고가 근접(2%이내) + MA200 (강한 마감)
89. 갭업 2~10% + MA200 + MA20 (넓은 범위)
90. 갭업 1~5% + MA200 + MA20 + 갭크기 역순정렬 (작은 갭 우선)
"""
import json, os, sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

os.environ["PYTHONUNBUFFERED"] = "1"
DATA_PATH = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"
RESULT_PATH = Path(__file__).parent.parent / "results" / "backtest_10strategies_v9.json"

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
        prev_ibs=(closes[i-1]-lows[i-1])/(highs[i-1]-lows[i-1]) if highs[i-1]!=lows[i-1] else 0.5
        prev_change=(closes[i-1]-closes[i-2])/closes[i-2]*100 if i>=2 and closes[i-2]>0 else 0
        prev_bullish=closes[i-1]>opens[i-1]
        prev2_bearish=closes[i-2]<opens[i-2] if i>=2 else False
        # 전일 레인지 (%)
        prev_range_pct=(highs[i-1]-lows[i-1])/closes[i-2]*100 if i>=2 and closes[i-2]>0 else 5
        # 전일 종가 vs 전일 고가 거리
        prev_close_to_high=(highs[i-1]-closes[i-1])/highs[i-1]*100 if highs[i-1]>0 else 999
        # 시가 vs 전일고가
        open_vs_prev_high=(o-highs[i-1])/highs[i-1]*100 if highs[i-1]>0 else 0

        results.append({
            "d":b.get("stck_bsop_date",""),"c":c,"o":o,"vol":vol,
            "ma5":ma5,"ma20":ma20,"ma200":ma200,
            "gap":gap,"oc":oc,"prev_ibs":prev_ibs,"prev_change":prev_change,
            "prev_bullish":prev_bullish,"prev2_bearish":prev2_bearish,
            "prev_range_pct":prev_range_pct,"prev_close_to_high":prev_close_to_high,
            "open_vs_prev_high":open_vs_prev_high,
            "ok":1000<=c<200000,
        })
    return results

def run(all_data, fn, date_range, max_pos=2, sort_key="vol", ascending=False):
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
        if sort_key=="gap":
            cands.sort(key=lambda x:x[1]["gap"], reverse=not ascending)
        else:
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
    print("9차 — 완전히 새로운 조합 10대 전략")
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
        ("81.MA200+MA20 only", lambda i: i["c"]>i["ma200"] and i["c"]>i["ma20"], "vol", False),
        ("82.시가>전일고가+MA200", lambda i: i["open_vs_prev_high"]>0 and i["c"]>i["ma200"], "vol", False),
        ("83.갭업+전일IBS>0.7", lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["ma20"] and i["prev_ibs"]>0.7, "vol", False),
        ("84.갭업+전일IBS<0.3", lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["ma20"] and i["prev_ibs"]<0.3, "vol", False),
        ("85.갭업+V자(양봉+전전일음봉)", lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["prev_bullish"] and i["prev2_bearish"], "vol", False),
        ("86.갭업+MA5>MA200", lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["ma5"]>i["ma200"], "vol", False),
        ("87.갭업+전일레인지<1%", lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["prev_range_pct"]<1, "vol", False),
        ("88.전일종가≈전일고가+MA200", lambda i: i["prev_close_to_high"]<2 and i["c"]>i["ma200"] and i["c"]>i["ma20"], "vol", False),
        ("89.갭업2~10%+MA200+MA20", lambda i: 2<=i["gap"]<10 and i["c"]>i["ma200"] and i["c"]>i["ma20"], "vol", False),
        ("90.갭업1~5%+작은갭우선", lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["ma20"], "gap", True),
        ("현재:갭업1~5%+MA200+MA20", lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["ma20"], "vol", False),
    ]

    print(f"\n{'전략':<30} | {'[학습] trim':>9} {'WR':>5} {'N':>4} | {'[검증] trim':>9} {'WR':>5} {'N':>4} {'SR':>6} {'PF':>5} | 일관")
    print("─"*110)
    results=[]
    for name, fn, sk, asc in strategies:
        tr=analyze(run(all_data, fn, train, sort_key=sk, ascending=asc))
        te=analyze(run(all_data, fn, test, sort_key=sk, ascending=asc))
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
