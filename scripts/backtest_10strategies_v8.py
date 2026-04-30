"""8차 — 갭업이 아닌 완전히 다른 접근 (09:01 시가 매수 → 종가 매도)

기존 70개는 대부분 갭업 변형. 이번에는 갭업과 무관한 전략으로 접근.
모두 "09:01에 판단 가능한 조건으로 시가 매수 → 당일 종가 매도" 데이트레이딩.

71. 매일 무조건 매수 (기준선) — 랜덤 진입의 기대 수익
72. 전일 등락률 상위 (모멘텀) — 어제 가장 많이 오른 종목
73. 전일 등락률 하위 (역추세) — 어제 가장 많이 내린 종목
74. 전일 거래량 상위 — 어제 가장 활발했던 종목
75. 전일 IBS 하위 (종가가 레인지 바닥) — 당일 반등 기대
76. 5일 모멘텀 상위 — 5일간 가장 많이 오른 종목
77. 5일 역모멘텀 (mean reversion) — 5일간 가장 많이 내린 종목
78. MA200 대비 가장 높은 종목 — 강한 장기 추세
79. 연속 상승일 최다 — 4일+ 연속 상승 종목
80. 전일 거래량 최저 (20일 중) + 갭업 — 침묵 후 폭발
"""
import json, os, sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

os.environ["PYTHONUNBUFFERED"] = "1"
DATA_PATH = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"
RESULT_PATH = Path(__file__).parent.parent / "results" / "backtest_10strategies_v8.json"

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
        ma200=sum(closes[i-199:i+1])/200; ma20=sum(closes[i-19:i+1])/20
        avg_vol_20=sum(volumes[i-19:i+1])/20
        gap=(o-closes[i-1])/closes[i-1]*100 if closes[i-1]>0 else 0
        oc=(c-o)/o*100 if o>0 else 0
        prev_change=(closes[i-1]-closes[i-2])/closes[i-2]*100 if i>=2 and closes[i-2]>0 else 0
        # IBS 전일
        prev_ibs=(closes[i-1]-lows[i-1])/(highs[i-1]-lows[i-1]) if highs[i-1]!=lows[i-1] else 0.5
        # 5일 모멘텀
        mom5=(closes[i-1]-closes[i-6])/closes[i-6]*100 if i>=6 and closes[i-6]>0 else 0
        # MA200 대비 위치
        ma200_pct=(closes[i-1]-ma200)/ma200*100 if ma200>0 else 0
        # 연속 상승일
        consec_up=0
        for k in range(1,10):
            if i-k>=1 and closes[i-k]>closes[i-k-1]: consec_up+=1
            else: break
        # 전일 거래량이 20일 중 최저
        vols_20=[volumes[i-1-k] for k in range(20) if i-1-k>=0]
        prev_vol_min = volumes[i-1]<=min(vols_20) if vols_20 else False

        results.append({
            "d":b.get("stck_bsop_date",""),"c":c,"o":o,"vol":vol,
            "ma200":ma200,"ma20":ma20,"avg_vol_20":avg_vol_20,
            "gap":gap,"oc":oc,"prev_change":prev_change,"prev_ibs":prev_ibs,
            "mom5":mom5,"ma200_pct":ma200_pct,"consec_up":consec_up,
            "prev_vol":volumes[i-1],"prev_vol_min":prev_vol_min,
            "ok":1000<=c<200000,
        })
    return results

def run_sorted(all_data, filter_fn, sort_fn, date_range, max_pos=2, ascending=False):
    """filter_fn으로 후보 선정 후 sort_fn으로 정렬하여 상위 N개 매수"""
    ds=defaultdict(dict)
    for code,inds in all_data.items():
        for ind in inds:
            if ind is None: continue
            d=ind["d"]
            if date_range and (d<date_range[0] or d>date_range[1]): continue
            ds[d][code]=ind
    pnls=[]
    for date in sorted(ds.keys()):
        cands=[(code,ind) for code,ind in ds[date].items() if ind["ok"] and ind["o"]>0 and filter_fn(ind)]
        cands.sort(key=lambda x:sort_fn(x[1]), reverse=not ascending)
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
    print("8차 — 갭업 무관 전략 10개 (시가 매수 → 종가 매도)")
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

    base = lambda i: i["c"]>i["ma200"]
    strategies = [
        ("71.매일무조건(기준선)", base, lambda i: i["vol"], False),
        ("72.전일등락률상위(모멘텀)", base, lambda i: i["prev_change"], False),
        ("73.전일등락률하위(역추세)", base, lambda i: i["prev_change"], True),
        ("74.전일거래량상위", base, lambda i: i["prev_vol"], False),
        ("75.전일IBS하위(바닥종가)", base, lambda i: i["prev_ibs"], True),
        ("76.5일모멘텀상위", base, lambda i: i["mom5"], False),
        ("77.5일역모멘텀(하락종목)", base, lambda i: i["mom5"], True),
        ("78.MA200대비최고", base, lambda i: i["ma200_pct"], False),
        ("79.연속상승4일+", lambda i: i["c"]>i["ma200"] and i["consec_up"]>=4, lambda i: i["vol"], False),
        ("80.전일거래량최저+갭업", lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["prev_vol_min"], lambda i: i["vol"], False),
        ("현재:갭업1~5%+MA200+MA20", lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["ma20"], lambda i: i["vol"], False),
    ]

    print(f"\n{'전략':<28} | {'[학습] trim':>9} {'WR':>5} {'N':>4} | {'[검증] trim':>9} {'WR':>5} {'N':>4} {'SR':>6} {'PF':>5} | 일관")
    print("─"*108)
    results=[]
    for name, filt, sort, asc in strategies:
        tr=analyze(run_sorted(all_data, filt, sort, train, ascending=asc))
        te=analyze(run_sorted(all_data, filt, sort, test, ascending=asc))
        ok="O" if tr["n"]>=10 and te["n"]>=10 and (tr["trim"]>0)==(te["trim"]>0) else "X"
        results.append({"name":name,"train":tr,"test":te,"consistent":ok})
        print(f"  {name:<26} | {tr['trim']:>+8.2f}% {tr['wr']:>4.1f}% {tr['n']:>4} | "
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
