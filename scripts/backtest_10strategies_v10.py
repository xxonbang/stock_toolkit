"""10차 — 보유 기간·매도 타이밍·복합 스코어 등 근본적으로 다른 접근

91. 갭업 시가매수 → 익일 시가매도 (오버나이트) — 당일 종가 아닌 익일 시가
92. 갭업 + 반일 보유 (고가의 50%에서 매도 근사) — 장중 절반만 보유
93. 갭업 × 거래량 복합스코어 — gap% × log(vol) 순 정렬
94. 전일 레인지 확대(ATR↑) + 갭업 — 변동성 확대 후 모멘텀
95. MA200 거리 10% 이내 + 갭업 — MA200 근처(지지선 반등) + 갭업
96. 갭업 + 전일 2일 연속 양봉 — 연속 상승 모멘텀 + 갭업
97. 갭업 + 전일 거래량 감소 (5d avg < 20d avg) — 축적 후 폭발
98. 전일 갭업 + 오늘도 갭업 (연속 갭업) — 이틀 연속 모멘텀
99. 갭업 1~5% + MA200 + MA20 + top 1 (집중, 최종 확인)
100. 갭업 1~5% + MA200 + MA20 + top 3 (분산, 최종 확인)
"""
import json, os, sys, math
from pathlib import Path
from collections import defaultdict
from datetime import datetime

os.environ["PYTHONUNBUFFERED"] = "1"
DATA_PATH = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"
RESULT_PATH = Path(__file__).parent.parent / "results" / "backtest_10strategies_v10.json"

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
        avg_vol_5=sum(volumes[max(0,i-4):i+1])/5
        avg_vol_20=sum(volumes[i-19:i+1])/20
        gap=(o-closes[i-1])/closes[i-1]*100 if closes[i-1]>0 else 0
        prev_gap=(opens[i-1]-closes[i-2])/closes[i-2]*100 if i>=2 and closes[i-2]>0 else 0
        oc=(c-o)/o*100 if o>0 else 0
        # 시가→(시가+고가)/2 수익률 (반일 보유 근사)
        half_day=((o+h)/2-o)/o*100 if o>0 else 0
        # 익일 시가 (다음 봉)
        next_open=opens[i+1] if i+1<len(opens) and opens[i+1]>0 else 0
        overnight=(next_open-c)/c*100 if c>0 and next_open>0 else 0
        # 시가→익일 시가
        open_to_next=(next_open-o)/o*100 if o>0 and next_open>0 else 0

        prev_change=(closes[i-1]-closes[i-2])/closes[i-2]*100 if i>=2 and closes[i-2]>0 else 0
        prev_bullish=closes[i-1]>opens[i-1]
        prev2_bullish=closes[i-2]>opens[i-2] if i>=2 else False
        # ATR 확대
        atr_sum=0
        for k in range(i-13,i+1):
            tr=max(highs[k]-lows[k],abs(highs[k]-closes[k-1]),abs(lows[k]-closes[k-1]))
            atr_sum+=tr
        atr14=atr_sum/14
        atr_old=0
        for k in range(i-33,i-19):
            if k>=1:
                tr2=max(highs[k]-lows[k],abs(highs[k]-closes[k-1]),abs(lows[k]-closes[k-1]))
                atr_old+=tr2
        atr_old=atr_old/14 if atr_old>0 else atr14
        atr_expanding=atr14>atr_old*1.2
        # MA200 거리
        ma200_dist=abs(c-ma200)/ma200*100 if ma200>0 else 999
        # 복합 스코어
        composite=gap*math.log(max(vol,1)) if gap>0 else 0

        results.append({
            "d":b.get("stck_bsop_date",""),"c":c,"o":o,"h":h,"l":lo,"vol":vol,
            "ma5":ma5,"ma20":ma20,"ma200":ma200,
            "gap":gap,"prev_gap":prev_gap,"oc":oc,"half_day":half_day,
            "open_to_next":open_to_next,
            "prev_bullish":prev_bullish,"prev2_bullish":prev2_bullish,
            "atr_expanding":atr_expanding,"ma200_dist":ma200_dist,
            "avg_vol_5":avg_vol_5,"avg_vol_20":avg_vol_20,
            "composite":composite,
            "ok":1000<=c<200000,
        })
    return results

def run(all_data, fn, date_range, max_pos=2, sort_fn=None, pnl_key="oc"):
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
        if sort_fn:
            cands.sort(key=lambda x:sort_fn(x[1]), reverse=True)
        else:
            cands.sort(key=lambda x:-x[1]["vol"])
        for code,ind in cands[:max_pos]:
            pnls.append(round(ind.get(pnl_key, ind["oc"]),2))
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
    print("10차 — 보유기간·매도타이밍·복합스코어 (최종)")
    print("="*105)
    data=load_json(DATA_PATH)
    all_data={}
    for code,info in data.items():
        bars=info.get("bars",[])
        if len(bars)<302: continue
        tvs=[int(b.get("acml_tr_pbmn","0")) for b in bars[-100:]]
        if sum(tvs)/len(tvs)<1_000_000_000: continue
        inds=prepare(bars)
        if inds: all_data[code]=inds
    print(f"유효: {len(all_data)}종목")
    all_dates=sorted({ind["d"] for inds in all_data.values() for ind in inds if ind})
    mid=len(all_dates)//2
    train=(all_dates[0],all_dates[mid]); test=(all_dates[mid+1],all_dates[-1])
    print(f"학습: {train[0]}~{train[1]} | 검증: {test[0]}~{test[1]}")

    base=lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["ma20"]
    strategies = [
        ("91.갭업→익일시가매도", base, None, "open_to_next", 2),
        ("92.갭업→반일보유(근사)", base, None, "half_day", 2),
        ("93.갭%×거래량 복합순", base, lambda i:i["composite"], "oc", 2),
        ("94.ATR확대+갭업", lambda i:base(i) and i["atr_expanding"], None, "oc", 2),
        ("95.MA200근접(10%이내)+갭업", lambda i:base(i) and i["ma200_dist"]<10, None, "oc", 2),
        ("96.전일2일양봉+갭업", lambda i:base(i) and i["prev_bullish"] and i["prev2_bullish"], None, "oc", 2),
        ("97.거래량감소(5d<20d)+갭업", lambda i:base(i) and i["avg_vol_5"]<i["avg_vol_20"], None, "oc", 2),
        ("98.연속갭업(전일도갭업)", lambda i:base(i) and i["prev_gap"]>=1, None, "oc", 2),
        ("99.현재+top1", base, None, "oc", 1),
        ("100.현재+top3", base, None, "oc", 3),
        ("현재:갭업1~5%+MA200+MA20", base, None, "oc", 2),
    ]

    print(f"\n{'전략':<30} | {'[학습] trim':>9} {'WR':>5} {'N':>4} | {'[검증] trim':>9} {'WR':>5} {'N':>4} {'SR':>6} {'PF':>5} | 일관")
    print("─"*110)
    results=[]
    for name, fn, sf, pk, mp in strategies:
        tr=analyze(run(all_data, fn, train, max_pos=mp, sort_fn=sf, pnl_key=pk))
        te=analyze(run(all_data, fn, test, max_pos=mp, sort_fn=sf, pnl_key=pk))
        ok="O" if tr["n"]>=10 and te["n"]>=10 and (tr["trim"]>0)==(te["trim"]>0) else "X"
        results.append({"name":name,"train":tr,"test":te,"consistent":ok})
        print(f"  {name:<28} | {tr['trim']:>+8.2f}% {tr['wr']:>4.1f}% {tr['n']:>4} | "
              f"{te['trim']:>+8.2f}% {te['wr']:>4.1f}% {te['n']:>4} {te['sharpe']:>6.3f} {te['pf']:>5.2f} | {ok}")

    ranked=sorted(results,key=lambda x:x["test"]["trim"],reverse=True)
    cur=next((r for r in results if "현재:" in r["name"]),None)
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
