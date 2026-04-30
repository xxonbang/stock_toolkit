"""갭업 모멘텀 전략 심층 분석

분석 관점:
1. 전체/학습/검증 기본 비교 + 현재 시스템 대조
2. 갭업 임계값 변형 (1%, 2%, 3%, 5%, 7%, 10%)
3. 추가 필터 변형 (MA200, 거래량, 가격대)
4. 월별 성과 분해
5. 수익률 분포 비교
6. 롤링 60일 윈도우
7. 갭업 크기별 수익률 상관관계
8. 부트스트랩 통계 검정
9. 결합 전략 (현재+갭업)
"""
import json, os, sys, time, random
from pathlib import Path
from collections import defaultdict
from datetime import datetime

os.environ["PYTHONUNBUFFERED"] = "1"
DATA_PATH = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"
RESULT_PATH = Path(__file__).parent.parent / "results" / "backtest_gapup_deep.json"

def load_json(path):
    with open(path, encoding="utf-8") as f: return json.load(f)

def prepare_stock(bars):
    if len(bars) < 201: return []
    closes, opens, highs, lows, volumes = [], [], [], [], []
    results = []
    for i, b in enumerate(bars):
        c=int(b.get("stck_clpr","0")); o=int(b.get("stck_oprc","0"))
        h=int(b.get("stck_hgpr","0")); lo=int(b.get("stck_lwpr","0"))
        vol=int(b.get("acml_vol","0"))
        if c<=0:
            closes.append(closes[-1] if closes else 0); opens.append(opens[-1] if opens else 0)
            highs.append(highs[-1] if highs else 0); lows.append(lows[-1] if lows else 0)
            volumes.append(0); results.append(None); continue
        closes.append(c); opens.append(o); highs.append(h); lows.append(lo); volumes.append(vol)
        if i < 200: results.append(None); continue

        ma5=sum(closes[i-4:i+1])/5; ma20=sum(closes[i-19:i+1])/20; ma200=sum(closes[i-199:i+1])/200
        avg_vol_20=sum(volumes[i-19:i+1])/20
        prev_ma5=sum(closes[i-5:i])/5; prev_ma20=sum(closes[i-20:i])/20
        gap=(o-closes[i-1])/closes[i-1]*100 if closes[i-1]>0 else 0
        # 시가→종가 수익률 (갭업 전략의 실제 수익)
        oc_return=(c-o)/o*100 if o>0 else 0

        results.append({
            "d":b.get("stck_bsop_date",""), "c":c, "o":o, "h":h, "l":lo, "vol":vol,
            "ma5":ma5, "ma20":ma20, "ma200":ma200,
            "prev_ma5":prev_ma5, "prev_ma20":prev_ma20,
            "avg_vol_20":avg_vol_20,
            "gap":gap, "oc_return":oc_return,
            "prev_high":highs[i-1], "prev_close":closes[i-1],
            "ok":1000<=c<200000,
        })
    return results

def run_gapup(all_data, gap_th=2, ma_filter=None, vol_filter=0, max_price=200000,
              min_price=0, date_range=None, max_pos=2):
    """갭업 전략: 시가 매수, 당일 종가 매도. 상세 거래 리스트 반환."""
    ds = defaultdict(dict)
    for code, inds in all_data.items():
        for ind in inds:
            if ind is None: continue
            d = ind["d"]
            if date_range and (d<date_range[0] or d>date_range[1]): continue
            ds[d][code] = ind
    dates = sorted(ds.keys())
    trades = []
    for date in dates:
        stocks = ds[date]
        cands = []
        for code, ind in stocks.items():
            if not ind["ok"] or ind["o"] <= 0: continue
            if ind["c"] < min_price or ind["c"] >= max_price: continue
            if ind["gap"] < gap_th: continue
            if ma_filter and ind["c"] <= ind.get(ma_filter, 0): continue
            if vol_filter > 0 and ind["vol"] < ind["avg_vol_20"] * vol_filter: continue
            cands.append((code, ind))
        cands.sort(key=lambda x: -x[1]["vol"])
        for code, ind in cands[:max_pos]:
            pnl = ind["oc_return"]
            trades.append({"date": date, "code": code, "pnl": round(pnl, 2),
                           "gap": round(ind["gap"], 2), "month": date[:6]})
    return trades

def run_current(all_data, date_range=None, max_pos=2):
    """현재 시스템 (비교용)"""
    ds = defaultdict(dict)
    for code, inds in all_data.items():
        for ind in inds:
            if ind is None: continue
            d = ind["d"]
            if date_range and (d<date_range[0] or d>date_range[1]): continue
            ds[d][code] = ind
    dates = sorted(ds.keys()); pnls_list = []; holdings = {}
    for di, date in enumerate(dates):
        stocks = ds[date]; sold = set()
        for code in list(holdings.keys()):
            ind = stocks.get(code)
            if ind is None: continue
            bp,bi,pk = holdings[code]; h,lo,c = ind["h"],ind["l"],ind["c"]; hd=di-bi
            if h>pk: pk=h; holdings[code]=(bp,bi,pk)
            hp=(h-bp)/bp*100; lp=(lo-bp)/bp*100; cp=(c-bp)/bp*100
            drop=(c-pk)/pk*100 if pk>0 else 0
            do_sell=False; sp=cp
            if 7>0 and hp>=7: do_sell=True; sp=7
            if lp<=-2: do_sell=True; sp=-2
            if -3<0 and cp>0 and drop<=-3: do_sell=True; sp=cp
            if hd>=5: do_sell=True
            if do_sell:
                pnls_list.append({"date":date,"code":code,"pnl":round(sp,2),"gap":0,"month":date[:6]})
                del holdings[code]; sold.add(code)
        if len(holdings)>=max_pos: continue
        cands = []
        for code,ind in stocks.items():
            if code in holdings or code in sold: continue
            score=0; c=ind["c"]
            if c>ind["prev_close"]: score+=5
            if c<20000: score+=5
            if ind["vol"]>ind["avg_vol_20"]*1.5: score+=10
            if ind["ma5"]>ind["ma20"] and ind["prev_ma5"]<=ind["prev_ma20"]: score+=5
            if c>ind["prev_high"]: score+=5
            if score>=15 and ind["ok"]: cands.append((code,ind))
        cands.sort(key=lambda x: -x[1]["vol"])
        for code,ind in cands[:max_pos-len(holdings)]:
            holdings[code]=(ind["c"],di,ind["c"])
    return pnls_list

def analyze(trades):
    pnls = [t["pnl"] for t in trades] if trades and isinstance(trades[0], dict) else trades
    n=len(pnls)
    if n==0: return {"n":0,"wr":0,"trim":0,"med":0,"sharpe":0,"pf":0,"mdd":0,"avg":0}
    s=sorted(pnls); wins=sum(1 for p in pnls if p>0); avg=sum(pnls)/n; med=s[n//2]
    lo,hi=int(n*0.05),n-int(n*0.05)
    trim=sum(s[lo:hi])/(hi-lo) if hi>lo else avg
    std=(sum((p-avg)**2 for p in pnls)/n)**0.5 if n>1 else 1
    cum=pk=mdd=0
    max_w=max_l=cur_w=cur_l=0
    for p in pnls:
        cum+=p
        if cum>pk: pk=cum
        dd=pk-cum
        if dd>mdd: mdd=dd
        if p>0: cur_w+=1; cur_l=0
        else: cur_l+=1; cur_w=0
        max_w=max(max_w,cur_w); max_l=max(max_l,cur_l)
    gp=sum(p for p in pnls if p>0); gl=abs(sum(p for p in pnls if p<0))
    return {"n":n,"wr":round(wins/n*100,1),"avg":round(avg,2),"trim":round(trim,2),"med":round(med,2),
            "sharpe":round(avg/std,3) if std>0 else 0,"pf":round(gp/gl,2) if gl>0 else 999,
            "mdd":round(mdd,1),"max_w":max_w,"max_l":max_l,"total_pnl":round(sum(pnls),1)}

def ps(label, s):
    print(f"  {label:<40s} N={s['n']:>4} WR={s['wr']:>5.1f}% trim={s['trim']:>+6.2f}% "
          f"med={s['med']:>+6.2f}% SR={s['sharpe']:>6.3f} PF={s['pf']:>5.2f} "
          f"MDD={s['mdd']:>5.1f}% W{s.get('max_w',0)}L{s.get('max_l',0)}")

def main():
    print("="*90); print("갭업 모멘텀 전략 심층 분석"); print("="*90)
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
    mid=len(all_dates)//2
    train=(all_dates[0],all_dates[mid]); test=(all_dates[mid+1],all_dates[-1])
    print(f"학습: {train[0]}~{train[1]} | 검증: {test[0]}~{test[1]}")

    # ═══ Phase 1: 기본 비교 ═══
    print(f"\n{'='*90}"); print("Phase 1: 기본 비교 (전체/학습/검증)"); print("─"*90)
    for label, dr in [("전체",None),("학습",train),("검증",test)]:
        gt = run_gapup(all_data, gap_th=2, date_range=dr)
        ct = run_current(all_data, date_range=dr)
        ps(f"갭업2% [{label}]", analyze(gt))
        ps(f"현재시스템 [{label}]", analyze(ct))

    # ═══ Phase 2: 갭업 임계값 변형 ═══
    print(f"\n{'='*90}"); print("Phase 2: 갭업 임계값 변형 (학습 + 검증)"); print("─"*90)
    for gap_th in [1, 1.5, 2, 3, 5, 7, 10]:
        tr=analyze(run_gapup(all_data, gap_th=gap_th, date_range=train))
        te=analyze(run_gapup(all_data, gap_th=gap_th, date_range=test))
        ok="O" if tr["n"]>=10 and te["n"]>=10 and (tr["trim"]>0)==(te["trim"]>0) else "X"
        print(f"  갭업≥{gap_th:>4.1f}%: 학습 trim={tr['trim']:>+6.2f}% WR={tr['wr']:>5.1f}% N={tr['n']:>4} | "
              f"검증 trim={te['trim']:>+6.2f}% WR={te['wr']:>5.1f}% N={te['n']:>4} SR={te['sharpe']:>6.3f} PF={te['pf']:>5.2f} | {ok}")

    # ═══ Phase 3: 추가 필터 변형 ═══
    print(f"\n{'='*90}"); print("Phase 3: 추가 필터 변형 (갭업 2%, 검증기간)"); print("─"*90)
    filters = [
        ("기본 (필터 없음)", {}),
        ("+ MA200 필터", {"ma_filter":"ma200"}),
        ("+ MA20 필터", {"ma_filter":"ma20"}),
        ("+ 거래량 1.5배", {"vol_filter":1.5}),
        ("+ 거래량 2배", {"vol_filter":2}),
        ("+ 저가주 <2만원", {"max_price":20000}),
        ("+ 고가주 2만~20만", {"min_price":20000}),
        ("+ MA200 + 거래량2배", {"ma_filter":"ma200","vol_filter":2}),
        ("+ MA200 + 저가주", {"ma_filter":"ma200","max_price":20000}),
    ]
    for label, kwargs in filters:
        tr=analyze(run_gapup(all_data, gap_th=2, date_range=train, **kwargs))
        te=analyze(run_gapup(all_data, gap_th=2, date_range=test, **kwargs))
        ok="O" if tr["n"]>=10 and te["n"]>=10 and (tr["trim"]>0)==(te["trim"]>0) else "X"
        print(f"  {label:<30s} 학습 trim={tr['trim']:>+6.2f}% N={tr['n']:>4} | "
              f"검증 trim={te['trim']:>+6.2f}% WR={te['wr']:>5.1f}% N={te['n']:>4} SR={te['sharpe']:>6.3f} PF={te['pf']:>5.2f} | {ok}")

    # ═══ Phase 4: 월별 성과 분해 ═══
    print(f"\n{'='*90}"); print("Phase 4: 월별 성과 분해"); print("─"*90)
    gt_all = run_gapup(all_data, gap_th=2)
    ct_all = run_current(all_data)
    def monthly(trades):
        bm = defaultdict(list)
        for t in trades: bm[t["month"]].append(t["pnl"])
        return bm
    gm = monthly(gt_all); cm = monthly(ct_all)
    months = sorted(set(gm)|set(cm))
    print(f"  {'월':>8} | {'갭업 모멘텀':>28} | {'현재시스템':>28}")
    print(f"  {'':>8} | {'N':>3} {'WR':>5} {'avg':>7} {'sum':>7} | {'N':>3} {'WR':>5} {'avg':>7} {'sum':>7}")
    print("  "+"─"*75)
    g_win_m=c_win_m=0
    for m in months:
        gp=gm.get(m,[]); cp=cm.get(m,[])
        gn=len(gp); gwr=(sum(1 for p in gp if p>0)/gn*100 if gn else 0); gavg=(sum(gp)/gn if gn else 0); gsum=sum(gp)
        cn=len(cp); cwr=(sum(1 for p in cp if p>0)/cn*100 if cn else 0); cavg=(sum(cp)/cn if cn else 0); csum=sum(cp)
        if gsum>0: g_win_m+=1
        if csum>0: c_win_m+=1
        print(f"  {m:>8} | {gn:>3} {gwr:>4.0f}% {gavg:>+6.2f}% {gsum:>+6.1f}% | "
              f"{cn:>3} {cwr:>4.0f}% {cavg:>+6.2f}% {csum:>+6.1f}%")
    print(f"\n  수익 월: 갭업 {g_win_m}/{len(months)}, 현재 {c_win_m}/{len(months)}")

    # ═══ Phase 5: 수익률 분포 ═══
    print(f"\n{'='*90}"); print("Phase 5: 수익률 분포"); print("─"*90)
    for label, trades in [("갭업 모멘텀", gt_all), ("현재시스템", ct_all)]:
        pnls = sorted([t["pnl"] for t in trades]); n=len(pnls)
        if not n: continue
        bk = {"≤-10%":0,"-10~-5%":0,"-5~-2%":0,"-2~0%":0,"0~2%":0,"2~5%":0,"5~10%":0,"≥10%":0}
        for p in pnls:
            if p<=-10: bk["≤-10%"]+=1
            elif p<=-5: bk["-10~-5%"]+=1
            elif p<=-2: bk["-5~-2%"]+=1
            elif p<0: bk["-2~0%"]+=1
            elif p<=2: bk["0~2%"]+=1
            elif p<=5: bk["2~5%"]+=1
            elif p<=10: bk["5~10%"]+=1
            else: bk["≥10%"]+=1
        print(f"\n  {label} (N={n}):")
        for bucket, cnt in bk.items():
            bar="█"*int(cnt/n*50)
            print(f"    {bucket:>8}: {cnt:>4} ({cnt/n*100:>5.1f}%) {bar}")
        print(f"    P5={pnls[n//20]:>+.2f}%, P25={pnls[n//4]:>+.2f}%, P50={pnls[n//2]:>+.2f}%, "
              f"P75={pnls[3*n//4]:>+.2f}%, P95={pnls[int(n*0.95)]:>+.2f}%")

    # ═══ Phase 6: 갭업 크기별 수익률 ═══
    print(f"\n{'='*90}"); print("Phase 6: 갭업 크기 vs 시가→종가 수익률 상관"); print("─"*90)
    gap_bins = [(1,2),(2,3),(3,5),(5,7),(7,10),(10,20),(20,100)]
    for lo_g, hi_g in gap_bins:
        subset = [t for t in gt_all if lo_g <= t["gap"] < hi_g]
        if not subset: continue
        pnls = [t["pnl"] for t in subset]
        avg = sum(pnls)/len(pnls)
        wr = sum(1 for p in pnls if p>0)/len(pnls)*100
        print(f"  갭업 {lo_g:>2}~{hi_g:>3}%: N={len(subset):>4}, avg={avg:>+6.2f}%, WR={wr:>5.1f}%, "
              f"sum={sum(pnls):>+7.1f}%")

    # ═══ Phase 7: 롤링 60일 ═══
    print(f"\n{'='*90}"); print("Phase 7: 롤링 60일 성과 추이"); print("─"*90)
    def rolling(trades, window=60):
        bd = defaultdict(list)
        for t in trades: bd[t["date"]].append(t["pnl"])
        ds = sorted(bd.keys()); res = []
        for i in range(0, len(ds)-window+1, 30):
            chunk = ds[i:i+window]; cp = []
            for d in chunk: cp.extend(bd[d])
            if cp:
                res.append({"p":f"{chunk[0][:6]}~{chunk[-1][:6]}","n":len(cp),
                            "avg":round(sum(cp)/len(cp),2),"wr":round(sum(1 for p in cp if p>0)/len(cp)*100,1)})
        return res
    gr=rolling(gt_all); cr=rolling(ct_all)
    print(f"  {'기간':>16} | {'갭업':>20} | {'현재':>20}")
    print("  "+"─"*62)
    for i in range(max(len(gr),len(cr))):
        g=gr[i] if i<len(gr) else None; c_=cr[i] if i<len(cr) else None
        p=(g or c_)["p"]
        gs=f"avg={g['avg']:>+5.2f}% WR={g['wr']:>4.1f}% N={g['n']:>3}" if g else "—"
        cs=f"avg={c_['avg']:>+5.2f}% WR={c_['wr']:>4.1f}% N={c_['n']:>3}" if c_ else "—"
        print(f"  {p:>16} | {gs} | {cs}")

    # ═══ Phase 8: 결합 전략 ═══
    print(f"\n{'='*90}"); print("Phase 8: 결합 전략 (현재 + 갭업 동시 운용)"); print("─"*90)
    # 두 전략의 거래를 합산 (동일 날짜 동일 종목이면 중복 제거)
    for label, dr in [("학습",train),("검증",test),("전체",None)]:
        gt=run_gapup(all_data, gap_th=2, date_range=dr)
        ct=run_current(all_data, date_range=dr)
        # 합산 (중복 제거: 같은 날짜+종목은 갭업 우선)
        seen = set()
        combined = []
        for t in gt: seen.add((t["date"],t["code"])); combined.append(t)
        for t in ct:
            if (t["date"],t["code"]) not in seen: combined.append(t)
        cs = analyze(combined)
        gs = analyze(gt)
        curs = analyze(ct)
        print(f"  [{label}] 갭업 trim={gs['trim']:>+.2f}% N={gs['n']} | "
              f"현재 trim={curs['trim']:>+.2f}% N={curs['n']} | "
              f"결합 trim={cs['trim']:>+.2f}% WR={cs['wr']}% N={cs['n']} SR={cs['sharpe']:.3f} PF={cs['pf']:.2f}")

    # ═══ Phase 9: 부트스트랩 ═══
    print(f"\n{'='*90}"); print("Phase 9: 부트스트랩 통계 검정 (10,000회)"); print("─"*90)
    random.seed(42)
    N_BOOT=10000
    for label, trades in [("갭업 모멘텀", gt_all), ("현재시스템", ct_all)]:
        pnls=[t["pnl"] for t in trades]; n=len(pnls)
        if n<10: continue
        bm=[sum(random.choices(pnls,k=n))/n for _ in range(N_BOOT)]
        bm.sort()
        ci_lo=bm[int(N_BOOT*0.025)]; ci_hi=bm[int(N_BOOT*0.975)]
        pct_pos=sum(1 for m in bm if m>0)/N_BOOT*100
        print(f"  {label} (N={n}): 평균={sum(pnls)/n:>+.3f}%, "
              f"95% CI=[{ci_lo:>+.3f}%, {ci_hi:>+.3f}%], 양수확률={pct_pos:.1f}%")

    # 차이 검정
    gp=[t["pnl"] for t in gt_all]; cp=[t["pnl"] for t in ct_all]
    diff_boots=[]
    for _ in range(N_BOOT):
        gs=random.choices(gp,k=len(gp)); cs=random.choices(cp,k=len(cp))
        diff_boots.append(sum(gs)/len(gs)-sum(cs)/len(cs))
    diff_boots.sort()
    ci_lo=diff_boots[int(N_BOOT*0.025)]; ci_hi=diff_boots[int(N_BOOT*0.975)]
    pct=sum(1 for d in diff_boots if d>0)/N_BOOT*100
    print(f"\n  갭업-현재 차이: 95% CI=[{ci_lo:>+.3f}%, {ci_hi:>+.3f}%], 갭업이 나을 확률={pct:.1f}%")

    # ═══ 최종 요약 ═══
    print(f"\n{'='*90}"); print("최종 요약 (검증기간)"); print("─"*90)
    gs=analyze(run_gapup(all_data, gap_th=2, date_range=test))
    cs=analyze(run_current(all_data, date_range=test))
    print(f"  {'지표':<20} {'갭업 모멘텀':>12} {'현재시스템':>12} {'차이':>12}")
    print("  "+"─"*60)
    for k,lb in [("trim","Trim Mean"),("wr","승률"),("sharpe","Sharpe"),("pf","PF"),
                  ("n","거래수"),("mdd","MDD"),("max_l","최대연속손실")]:
        gv,cv=gs.get(k,0),cs.get(k,0)
        if k in ("trim","wr","mdd"): print(f"  {lb:<20} {gv:>+11.2f}% {cv:>+11.2f}% {gv-cv:>+11.2f}%")
        else: print(f"  {lb:<20} {gv:>12} {cv:>12} {gv-cv:>+12}")

    with open(RESULT_PATH,"w",encoding="utf-8") as f:
        json.dump({"generated_at":datetime.now().isoformat(),"gap_up_test":gs,"current_test":cs},
                  f,ensure_ascii=False,indent=2)
    print(f"\n결과 저장: {RESULT_PATH}")

if __name__=="__main__": main()
