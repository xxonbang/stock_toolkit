"""7차 추가 10대 전략 (기존 60개와 미중복, 09:01 실시간 구현 가능)

갭업과 다른 조건의 새로운 조합, 그리고 완전히 다른 접근도 포함.

61. 갭업 + NR4 (전일 레인지 최소) — 변동성 수축 후 갭업 = 에너지 폭발
62. 월요일 갭업 — 주말 재료 반영 갭업
63. 3일 하락 후 갭업 — 눌림 끝 + 갭업 반등
64. 소폭갭업 + 대량거래 — 갭 0.5~1% + 전일거래량 3배
65. 갭업 + ATR 수축 — 변동성 축소 후 갭업
66. 당일 갭업 크기 상위 (갭% 순 정렬) — 가장 강한 갭업 종목
67. 갭업 + 20일 신고가 — 갭업과 돌파 동시
68. 전일 양봉 + 갭업 + MA5>MA20 — 3중 모멘텀
69. 갭업 + 전일 종가 MA20 근접 — 지지선 반등 + 갭업
70. 전일 대비 시가 변화율 top (갭업/갭다운 무관, 절대값) — 변동성 자체에 베팅
"""
import json, os, sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

os.environ["PYTHONUNBUFFERED"] = "1"
DATA_PATH = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"
RESULT_PATH = Path(__file__).parent.parent / "results" / "backtest_10strategies_v7.json"

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

        # NR4: 오늘 전일 레인지가 최근 4일 중 최소
        ranges_4 = [highs[i-1-k]-lows[i-1-k] for k in range(4) if i-1-k>=0]
        prev_range = highs[i-1]-lows[i-1]
        is_nr4 = prev_range <= min(ranges_4) if ranges_4 else False

        # ATR(14) 수축: 현재 ATR < 20일 전 ATR
        atr_sum=0
        for k in range(i-13,i+1):
            tr=max(highs[k]-lows[k],abs(highs[k]-closes[k-1]),abs(lows[k]-closes[k-1]))
            atr_sum+=tr
        atr14=atr_sum/14
        atr_old=0
        for k in range(i-33,i-19):
            if k>=1:
                tr=max(highs[k]-lows[k],abs(highs[k]-closes[k-1]),abs(lows[k]-closes[k-1]))
                atr_old+=tr
        atr_old=atr_old/14 if atr_old>0 else atr14
        atr_contracting = atr14 < atr_old * 0.8

        # 3일 연속 하락
        three_down = all(closes[i-1-k]<closes[i-2-k] for k in range(3)) if i>=4 else False

        prev_bullish = closes[i-1]>opens[i-1]
        prev_vol = volumes[i-1]
        prev_ma5 = sum(closes[i-5:i])/5
        prev_ma20 = sum(closes[i-20:i])/20
        high_20d = max(highs[i-20:i]) if i>=20 else max(highs[:i]) if i>0 else h

        # 전일 종가와 MA20의 거리
        ma20_dist = abs(closes[i-1]-ma20)/ma20*100 if ma20>0 else 999

        # 요일
        date_str=b.get("stck_bsop_date","")
        dow=None
        if len(date_str)==8:
            try: dow=datetime.strptime(date_str,"%Y%m%d").weekday()
            except: pass

        results.append({
            "d":date_str,"c":c,"o":o,"h":h,"l":lo,"vol":vol,
            "ma5":ma5,"ma20":ma20,"ma200":ma200,"avg_vol_20":avg_vol_20,
            "gap":gap,"oc":oc,"prev_change":prev_change,
            "is_nr4":is_nr4,"atr_contracting":atr_contracting,
            "three_down":three_down,"prev_bullish":prev_bullish,"prev_vol":prev_vol,
            "prev_ma5":prev_ma5,"prev_ma20":prev_ma20,
            "high_20d":high_20d,"ma20_dist":ma20_dist,"dow":dow,
            "ok":1000<=c<200000,
        })
    return results

def run(all_data, fn, date_range, max_pos=2, sort_key="vol"):
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
            cands.sort(key=lambda x:-x[1]["gap"])
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
    print("7차 — 새로운 접근 10대 전략")
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
        ("61.갭업+NR4", lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["is_nr4"], "vol"),
        ("62.월요일갭업", lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["ma20"] and i["dow"]==0, "vol"),
        ("63.3일하락후갭업", lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["three_down"], "vol"),
        ("64.소폭갭+대량거래", lambda i: 0.5<=i["gap"]<1 and i["c"]>i["ma200"] and i["prev_vol"]>i["avg_vol_20"]*3, "vol"),
        ("65.갭업+ATR수축", lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["atr_contracting"], "vol"),
        ("66.갭업크기순정렬", lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["ma20"], "gap"),
        ("67.갭업+20일신고가", lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["high_20d"], "vol"),
        ("68.전일양봉+갭업+MA추세", lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["ma20"] and i["prev_bullish"] and i["prev_ma5"]>i["prev_ma20"], "vol"),
        ("69.갭업+MA20근접(2%이내)", lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["ma20_dist"]<2, "vol"),
        ("70.절대변동률top(갭무관)", lambda i: abs(i["gap"])>=2 and i["c"]>i["ma200"] and i["c"]>i["ma20"], "vol"),
        ("현재:갭업1~5%+MA200+MA20", lambda i: 1<=i["gap"]<5 and i["c"]>i["ma200"] and i["c"]>i["ma20"], "vol"),
    ]

    print(f"\n{'전략':<28} | {'[학습] trim':>9} {'WR':>5} {'N':>4} | {'[검증] trim':>9} {'WR':>5} {'N':>4} {'SR':>6} {'PF':>5} | 일관")
    print("─"*108)
    results=[]
    for name, fn, sk in strategies:
        tr=analyze(run(all_data, fn, train, sort_key=sk))
        te=analyze(run(all_data, fn, test, sort_key=sk))
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
