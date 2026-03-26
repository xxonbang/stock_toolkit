import { useEffect, useState, useRef } from "react";
import { createPortal } from "react-dom";
import { useOutletContext } from "react-router-dom";
import {
  BarChart3, RefreshCw, X, HelpCircle,
} from "lucide-react";
import { dataService } from "../services/dataService";
import { supabase, fetchKisPrices, searchKisStock, fetchHoldingsFromDB, insertHolding, updateHolding, deleteHolding, setAccessToken, STORAGE_KEY } from "../lib/supabase";
import type { PortfolioHolding } from "../lib/supabase";

function Badge({ children, variant = "default" }: { children: React.ReactNode; variant?: string }) {
  const cls: Record<string, string> = {
    danger: "bg-red-500/10 text-red-400 border-red-500/20",
    warning: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    success: "bg-green-500/10 text-green-400 border-green-500/20",
    blue: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    purple: "bg-purple-500/10 text-purple-400 border-purple-500/20",
    default: "t-muted t-text-sub border-transparent",
  };
  return (
    <span className={`inline-flex items-center text-xs font-medium px-2 py-0.5 rounded-full border whitespace-nowrap ${cls[variant] || cls.default}`}>
      {children}
    </span>
  );
}

function signalBadge(signal: string) {
  if (signal?.includes("적극매수")) return <Badge variant="danger">적극매수</Badge>;
  if (signal?.includes("매수")) return <Badge variant="danger">매수</Badge>;
  if (signal?.includes("적극매도")) return <Badge variant="blue">적극매도</Badge>;
  if (signal?.includes("매도")) return <Badge variant="blue">매도</Badge>;
  return <Badge>중립</Badge>;
}

interface PortfolioContext {
  supaUser: any;
  onShowLogin: () => void;
  onStockDetail: (detail: any) => void;
  setToastMsg: (msg: string) => void;
  crossSignal: any[] | null;
  smartMoney: any[] | null;
  riskMonitor: any[] | null;
  consecutiveSignals: any;
}

export default function Portfolio() {
  const { supaUser, onShowLogin, onStockDetail, setToastMsg, crossSignal, smartMoney, riskMonitor, consecutiveSignals } = useOutletContext<PortfolioContext>();
  const [portfolio, setPortfolio] = useState<any>(null);
  const [portfolioRaw, setPortfolioRaw] = useState<any>(null);
  const [dbHoldings, setDbHoldings] = useState<PortfolioHolding[]>([]);
  const dbHoldingsRef = useRef(dbHoldings);
  dbHoldingsRef.current = dbHoldings;
  const [dbLoading, setDbLoading] = useState(false);
  const [showPortfolioEdit, setShowPortfolioEdit] = useState(false);
  const [editHoldings, setEditHoldings] = useState<any[]>([]);
  const [priceRefreshing, setPriceRefreshing] = useState(false);
  const [livePriceTime, setLivePriceTime] = useState("");
  const [excludedCodes, setExcludedCodes] = useState<Set<string>>(new Set());
  const [showHealthHelp, setShowHealthHelp] = useState(false);
  const [stockSearch, setStockSearch] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [allStockList, setAllStockList] = useState<any[]>([]);

  // 모달 열림 시 body 스크롤 잠금
  const anyModalOpen = !!(showPortfolioEdit);
  useEffect(() => {
    document.body.style.overflow = anyModalOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [anyModalOpen]);

  // portfolioRaw 또는 dbHoldings 변경 시 병합 — DB avg_price가 항상 우선
  useEffect(() => {
    if (!portfolioRaw?.holdings) return;
    const serverHoldings = portfolioRaw.holdings;
    const userHoldings = dbHoldings.length > 0 ? dbHoldings : serverHoldings;
    const merged = userHoldings.map((lh: any) => {
      const server = serverHoldings.find((sh: any) => sh.code === lh.code) || {};
      const avgPrice = lh.avg_price || 0;
      const qty = lh.quantity || 0;
      const cp = (server as any).current_price || lh.current_price || 0;
      return {
        ...server, ...lh,
        avg_price: avgPrice,
        quantity: qty,
        current_price: cp,
        signal: (server as any).signal || "분석 대상 외",
        profit_rate: avgPrice && cp ? Math.round((cp - avgPrice) / avgPrice * 10000) / 100 : 0,
        profit_amount: avgPrice && cp ? (cp - avgPrice) * qty : 0,
        invested: avgPrice * qty,
        current_value: cp * qty,
      };
    });
    const totalInv = merged.reduce((s: number, h: any) => s + h.invested, 0);
    const totalVal = merged.reduce((s: number, h: any) => s + h.current_value, 0);
    merged.forEach((h: any) => { h.weight = totalInv ? Math.round(h.invested / totalInv * 100) : 0; });
    setPortfolio({ ...portfolioRaw, holdings: merged, summary: {
      total_invested: totalInv, total_value: totalVal,
      total_profit_rate: totalInv ? Math.round((totalVal - totalInv) / totalInv * 10000) / 100 : 0,
      total_profit_amount: totalVal - totalInv, total_holdings: merged.length,
    }});
  }, [dbHoldings, portfolioRaw]);

  // 포트폴리오 데이터 로드
  useEffect(() => {
    dataService.getPortfolio().then((p) => { if (p) setPortfolioRaw(p); });
    dataService.getStockMaster().then((m: any) => {
      if (m?.stocks) setAllStockList(m.stocks.map((s: any) => ({ code: s.code, name: s.name, market: s.market || "" })));
    });
  }, []);

  // 로그인 상태 시 DB에서 보유 종목 로드
  useEffect(() => {
    if (supaUser) {
      setDbLoading(true);
      fetchHoldingsFromDB().then(setDbHoldings).catch(() => {}).finally(() => setDbLoading(false));
    } else {
      setDbHoldings([]);
    }
  }, [supaUser]);

  const refreshPortfolioPrices = async () => {
    if (priceRefreshing) return;
    if (!portfolio?.holdings?.length) {
      setToastMsg("포트폴리오 데이터가 없습니다");
      setTimeout(() => setToastMsg(""), 2500);
      return;
    }
    setPriceRefreshing(true);
    try {
      const codes = portfolio.holdings.map((h: any) => h.code).filter(Boolean);
      let priceMap: Record<string, number> = {};
      let source = "";
      if (supaUser && codes.length > 0) {
        try {
          // 세션 유효성 먼저 확인 — 무효 시 Edge Function hang 방지
          const { data: { session } } = await supabase.auth.getSession();
          if (session?.access_token) {
            const kisData = await Promise.race([
              fetchKisPrices(codes),
              new Promise<never>((_, reject) => setTimeout(() => reject(new Error("KIS timeout")), 8000)),
            ]);
            for (const [code, p] of Object.entries(kisData)) {
              if (p.current_price) priceMap[code] = p.current_price;
            }
            if (Object.keys(priceMap).length > 0) source = "KIS";
          }
        } catch (e) {
          console.warn("KIS Edge Function 실패:", e);
        }
      }
      if (!source) {
        try {
          const [tvRes, pfRes] = await Promise.all([
            fetch(import.meta.env.BASE_URL + "data/trading_value.json"),
            fetch(import.meta.env.BASE_URL + "data/portfolio.json"),
          ]);
          if (tvRes.ok) for (const s of await tvRes.json() || []) {
            if (s.code && s.current_price && !priceMap[s.code]) priceMap[s.code] = s.current_price;
          }
          if (pfRes.ok) for (const h of (await pfRes.json())?.holdings || []) {
            if (h.code && h.current_price && !priceMap[h.code]) priceMap[h.code] = h.current_price;
          }
          if (Object.keys(priceMap).length > 0) source = "캐시";
        } catch {}
      }
      if (Object.keys(priceMap).length > 0) {
        const updated = portfolio.holdings.map((h: any) => {
          const cp = priceMap[h.code] || h.current_price || 0;
          const ap = h.avg_price || 0;
          const qty = h.quantity || 0;
          return { ...h, current_price: cp, profit_rate: ap && cp ? Math.round((cp - ap) / ap * 10000) / 100 : 0,
            profit_amount: ap && cp ? (cp - ap) * qty : 0, invested: ap * qty, current_value: cp * qty };
        });
        const totalInv = updated.reduce((s: number, h: any) => s + h.invested, 0);
        const totalVal = updated.reduce((s: number, h: any) => s + h.current_value, 0);
        updated.forEach((h: any) => { h.weight = totalInv ? Math.round(h.invested / totalInv * 100) : 0; });
        setPortfolio((prev: any) => ({ ...prev, holdings: updated, summary: {
          total_invested: totalInv, total_value: totalVal,
          total_profit_rate: totalInv ? Math.round((totalVal - totalInv) / totalInv * 10000) / 100 : 0,
          total_profit_amount: totalVal - totalInv, total_holdings: updated.length,
        }}));
        const now = new Date();
        const hh = now.getHours();
        setLivePriceTime(`${hh < 12 ? "오전" : "오후"} ${hh === 0 ? 12 : hh > 12 ? hh - 12 : hh}:${now.getMinutes().toString().padStart(2,"0")}`);
      } else {
        setToastMsg("시세 조회 실패 — 장 운영시간에 다시 시도해주세요");
        setTimeout(() => setToastMsg(""), 3000);
      }
    } catch (e) {
      console.error("price refresh failed:", e);
      setToastMsg("시세 새로고침 실패 — 네트워크를 확인해주세요");
      setTimeout(() => setToastMsg(""), 3000);
    }
    finally { setPriceRefreshing(false); }
  };

  if (!supaUser) {
    return (
      <section className="t-card rounded-xl p-6 text-center">
        <BarChart3 size={28} className="mx-auto mb-3 t-text-dim" />
        <div className="text-sm font-semibold t-text mb-1">내 포트폴리오</div>
        <div className="text-[12px] t-text-sub mb-4">로그인하면 보유 종목을 관리하고<br/>실시간 수익률을 확인할 수 있습니다.</div>
        <button onClick={onShowLogin}
          className="text-sm font-medium px-6 py-2 rounded-xl bg-blue-600 text-white hover:bg-blue-500 transition">로그인</button>
      </section>
    );
  }

  if (!portfolio) {
    return (
      <section className="t-card rounded-xl p-6 text-center">
        <BarChart3 size={24} className="mx-auto mb-2 t-text-dim" />
        <div className="text-sm t-text-sub">포트폴리오 데이터 로딩 중...</div>
      </section>
    );
  }

  const sm = portfolio.summary || {};
  const profitColor = (r: number) => r > 0 ? "text-red-500" : r < 0 ? "text-blue-500" : "t-text";

  return (<>
    <section className="t-card rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <h2 className="text-base font-semibold t-text">내 포트폴리오 <span className="text-sm font-normal t-text-dim">({portfolio.holdings?.length})</span></h2>
        <div className="ml-auto flex items-center gap-2">
          {livePriceTime && (
            <div className="text-center">
              <div className="text-[9px] font-bold text-emerald-400 tracking-wider">LIVE</div>
              <div className="text-[10px] t-text-dim">{livePriceTime}</div>
            </div>
          )}
          <button onClick={refreshPortfolioPrices} disabled={priceRefreshing}
            className="p-2 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 transition disabled:opacity-50">
            <RefreshCw size={16} className={`text-emerald-500 ${priceRefreshing ? "animate-spin" : ""}`} />
          </button>
          <button onClick={() => {
            const source = dbHoldings.length > 0 ? dbHoldings : (portfolio.holdings || []);
            const sectorMap: Record<string, string> = {};
            for (const hh of portfolio.holdings || []) if (hh.code && hh.sector) sectorMap[hh.code] = hh.sector;
            const merged = JSON.parse(JSON.stringify(source)).map((hh: any) => ({
              ...hh, sector: hh.sector || sectorMap[hh.code] || "",
            }));
            setEditHoldings(merged);
            setShowPortfolioEdit(true);
          }}
            className="text-[11px] px-2.5 py-1.5 rounded-xl border border-blue-500/30 text-blue-400 hover:bg-blue-500/10 transition font-medium">편집</button>
        </div>
      </div>
      {/* 총 손익 요약 — 체크된 종목만 계산 */}
      {(() => {
        const included = (portfolio.holdings || []).filter((h: any) => !excludedCodes.has(h.code));
        const filtInv = included.reduce((s: number, h: any) => s + (h.invested || 0), 0);
        const filtVal = included.reduce((s: number, h: any) => s + (h.current_value || 0), 0);
        const filtRate = filtInv ? Math.round((filtVal - filtInv) / filtInv * 10000) / 100 : 0;
        return filtInv > 0 ? (
        <div className="flex items-center justify-between mb-3 p-3 t-card-alt rounded-xl">
          <div>
            <div className="text-[10px] t-text-dim">총 투자금</div>
            <div className="text-sm font-semibold t-text">{filtInv.toLocaleString()}원</div>
          </div>
          <div>
            <div className="text-[10px] t-text-dim">평가금</div>
            <div className="text-sm font-semibold t-text">{filtVal.toLocaleString()}원</div>
          </div>
          <div className="text-right">
            <div className="text-[10px] t-text-dim">총 수익률</div>
            <div className={`text-sm font-bold ${profitColor(filtRate)}`}>
              {filtRate >= 0 ? "+" : ""}{filtRate}%
            </div>
            <div className={`text-[10px] font-medium ${profitColor(filtVal - filtInv)}`}>
              {filtVal - filtInv >= 0 ? "+" : ""}{(filtVal - filtInv).toLocaleString()}원
            </div>
          </div>
        </div>
        ) : null;
      })()}
      {/* 종목별 */}
      <div className="space-y-1.5 mb-3">
        {portfolio.holdings?.map((h: any, i: number) => {
          const isExcluded = excludedCodes.has(h.code);
          const detail = [...(crossSignal || []), ...(smartMoney || []), ...(portfolioRaw?.holdings || [])].find((s: any) => s.code === h.code);
          return (
          <div key={i} className={`p-2.5 t-card-alt rounded-lg cursor-pointer hover:border-blue-500/30 hover:border transition-colors ${isExcluded ? "opacity-40" : ""}`}
            onClick={() => detail ? onStockDetail(detail) : onStockDetail({ name: h.name, code: h.code, _noData: true })}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <input type="checkbox" checked={!isExcluded}
                  onChange={() => setExcludedCodes(prev => {
                    const next = new Set(prev);
                    next.has(h.code) ? next.delete(h.code) : next.add(h.code);
                    return next;
                  })}
                  onClick={(e) => e.stopPropagation()}
                  className="w-4 h-4 rounded accent-blue-500 shrink-0 cursor-pointer" />
                <div className="min-w-0">
                  <span className="text-sm font-medium t-text">{h.name}</span>
                  <span className="text-[10px] t-text-dim ml-1">{h.code}</span>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {h.profit_rate != null && h.current_price > 0 && (
                  <span className={`text-xs font-bold ${profitColor(h.profit_rate)}`}>
                    {h.profit_rate >= 0 ? "+" : ""}{h.profit_rate}%
                  </span>
                )}
                {signalBadge(h.signal)}
              </div>
            </div>
            <div className="flex items-center gap-3 mt-1 text-[10px] t-text-dim">
              <span>평단 {(h.avg_price || 0).toLocaleString()}</span>
              {h.current_price > 0 && <span>현재 {h.current_price.toLocaleString()}</span>}
              <span>{h.quantity}주</span>
              <span>비중 {h.weight}%</span>
            </div>
            {h.profit_amount != null && h.current_price > 0 && (
              <div className={`text-[10px] font-medium mt-0.5 ${profitColor(h.profit_amount)}`}>
                평가손익 {h.profit_amount >= 0 ? "+" : ""}{h.profit_amount.toLocaleString()}원
              </div>
            )}
          </div>
          );
        })}
      </div>
      {/* 리밸런싱 제안 — 시그널+수급+위험 기반 */}
      {(() => {
        const h = portfolio.holdings || [];
        const riskMap: Record<string, any> = {};
        for (const r of riskMonitor || []) if (r.code) riskMap[r.code] = r;
        const streakMap: Record<string, number> = {};
        for (const r of (consecutiveSignals?.and_condition || [])) if (r.code) streakMap[r.code] = r.streak;
        for (const r of (consecutiveSignals?.or_condition || [])) if (r.code && !streakMap[r.code]) streakMap[r.code] = r.streak;

        type Suggestion = { text: string; priority: number; type: "danger" | "warn" | "opportunity" };
        const suggestions: Suggestion[] = [];

        for (const x of h) {
          const sig = x.signal || "";
          const isSell = sig.includes("매도");
          const risk = riskMap[x.code];
          const riskLevel = risk?.level || "";
          const foreignNet = x.foreign_net ?? 0;
          const pr = x.profit_rate ?? 0;
          const streak = streakMap[x.code];
          const items: Suggestion[] = [];

          if (isSell && riskLevel === "높음") items.push({ text: `${x.name} 매도 신호 + 고위험 — 즉시 비중 축소 검토`, priority: 1, type: "danger" });
          else if (isSell) items.push({ text: `${x.name} 매도 신호 감지 — 비중 축소 검토`, priority: 2, type: "warn" });
          if (foreignNet < 0 && (riskLevel === "주의" || riskLevel === "높음")) items.push({ text: `${x.name} 외국인 이탈 + ${riskLevel} — 주의 필요`, priority: 3, type: "warn" });
          if (streak && streak >= 2) items.push({ text: `${x.name} ${streak}일 연속 매집 신호 — 추가 매수 검토`, priority: 4, type: "opportunity" });
          if (pr <= -5) items.push({ text: `${x.name} 손실 ${pr}% — 손절 검토`, priority: 5, type: "warn" });
          else if (pr >= 20) items.push({ text: `${x.name} 수익 +${pr}% — 익절 검토`, priority: 6, type: "opportunity" });

          items.sort((a, b) => a.priority - b.priority);
          suggestions.push(...items.slice(0, 2));
        }
        const sectors = h.map((x: any) => x.sector).filter(Boolean);
        if (sectors.length > 0 && new Set(sectors).size < sectors.length) suggestions.push({ text: "동일 섹터 편중 — 섹터 분산 필요", priority: 7, type: "warn" });

        if (suggestions.length === 0) return null;
        suggestions.sort((a, b) => a.priority - b.priority);
        const typeColor = { danger: "text-red-400", warn: "text-amber-400", opportunity: "text-emerald-400" };
        return (
          <div className="bg-orange-500/8 border border-orange-500/15 rounded-lg p-2.5 mb-3">
            <div className="text-xs font-medium text-orange-400 mb-1">리밸런싱 제안</div>
            {suggestions.map((s, i) => (
              <div key={i} className="text-xs t-text-sub">
                <span className={typeColor[s.type]}>·</span> {s.text}
              </div>
            ))}
          </div>
        );
      })()}
      {/* 건강도 — 다차원 가중 점수 */}
      {(() => {
        const h = portfolio.holdings || [];
        const n = h.length || 1;
        // 1) 수익 건전성 (30점) — 평균 수익률 기반
        const avgPr = h.reduce((s: number, x: any) => s + (x.profit_rate ?? 0), 0) / n;
        const profitScore = Math.max(0, 30 + Math.min(avgPr, 0) * 1.5); // 손실 1%당 -1.5점, 최대 -30
        // 2) 시그널 정합성 (25점) — 매도 신호 종목 비중
        const sellCount = h.filter((x: any) => (x.signal || "").includes("매도")).length;
        const signalScore = Math.max(0, 25 - (sellCount / n) * 50);
        // 3) 수급 방향 (20점) — 외국인 순매도 종목 비중
        const foreignSellCount = h.filter((x: any) => (x.foreign_net ?? 0) < 0).length;
        const supplyScore = Math.max(0, 20 - (foreignSellCount / n) * 40);
        // 4) 분산도 (15점) — HHI + 종목 수
        const sectors = h.map((x: any) => x.sector).filter(Boolean);
        const sectorCounts: Record<string, number> = {};
        sectors.forEach((s: string) => { sectorCounts[s] = (sectorCounts[s] || 0) + 1; });
        const hhi = Object.values(sectorCounts).reduce((s: number, c: number) => s + (c / n) ** 2, 0);
        let diverseScore = 15 * (1 - hhi);
        if (n < 3) diverseScore = Math.max(0, diverseScore - 5);
        diverseScore = Math.max(0, diverseScore);
        // 5) 위험 노출 (10점) — riskMonitor 기반
        const riskMap2: Record<string, string> = {};
        for (const r of riskMonitor || []) if (r.code) riskMap2[r.code] = r.level;
        const highRiskCount = h.filter((x: any) => riskMap2[x.code] === "높음").length;
        const cautionCount = h.filter((x: any) => riskMap2[x.code] === "주의").length;
        const riskScore = Math.max(0, 10 - (highRiskCount / n) * 20 - (cautionCount / n) * 8);
        const total = Math.round(profitScore + signalScore + supplyScore + diverseScore + riskScore);
        const healthColor = total >= 70 ? "text-emerald-500" : total >= 50 ? "text-amber-500" : "text-red-500";
        const healthLabel = total >= 70 ? "양호" : total >= 50 ? "보통" : "개선 필요";
        const axes = [
          { label: "수익", score: Math.round(profitScore), max: 30 },
          { label: "시그널", score: Math.round(signalScore), max: 25 },
          { label: "수급", score: Math.round(supplyScore), max: 20 },
          { label: "분산", score: Math.round(diverseScore), max: 15 },
          { label: "위험", score: Math.round(riskScore), max: 10 },
        ];
        return (<>
      <div className="flex items-center gap-2 text-xs t-text-dim">
        <span>건강도 {total}/100</span>
        <span className={`font-medium ${healthColor}`}>{healthLabel}</span>
        <button onClick={() => setShowHealthHelp(true)} className="t-text-dim hover:t-text-sub"><HelpCircle size={13} /></button>
      </div>
      {/* 건강도 축별 바 */}
      <div className="flex gap-1 mt-1.5">
        {axes.map((a) => (
          <div key={a.label} className="flex-1" title={`${a.label} ${a.score}/${a.max}`}>
            <div className="h-1 rounded-full bg-gray-700 overflow-hidden">
              <div className="h-full rounded-full transition-all" style={{ width: `${(a.score / a.max) * 100}%`, backgroundColor: (a.score / a.max) >= 0.7 ? "#10b981" : (a.score / a.max) >= 0.4 ? "#f59e0b" : "#ef4444" }} />
            </div>
            <div className="text-[8px] t-text-dim text-center mt-0.5">{a.label}</div>
          </div>
        ))}
      </div>
      {/* 건강도 설명 팝업 */}
      {showHealthHelp && createPortal(
        <div className="fixed inset-0 z-[9999]" onClick={() => setShowHealthHelp(false)}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
          <div className="fixed bottom-0 left-0 right-0 z-[10000] max-h-[70vh] overflow-y-auto rounded-t-2xl t-card border-t t-border-light p-5 sm:max-w-md sm:mx-auto sm:rounded-2xl sm:bottom-auto sm:top-1/2 sm:-translate-y-1/2"
            onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold t-text">건강도 계산 방법</h3>
              <button onClick={() => setShowHealthHelp(false)} className="t-text-dim hover:t-text"><X size={16} /></button>
            </div>
            <div className="space-y-2 text-xs t-text-sub">
              <p className="t-text font-medium">5개 축의 합산 점수 (100점 만점)</p>
              {axes.map((a) => (
                <div key={a.label} className="flex items-center gap-2">
                  <span className="font-medium t-text w-12">{a.label}</span>
                  <div className="flex-1 h-1.5 rounded-full bg-gray-700 overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${(a.score / a.max) * 100}%`, backgroundColor: (a.score / a.max) >= 0.7 ? "#10b981" : (a.score / a.max) >= 0.4 ? "#f59e0b" : "#ef4444" }} />
                  </div>
                  <span className="w-14 text-right">{a.score}/{a.max}</span>
                </div>
              ))}
              <div className="border-t t-border-light pt-2 mt-2 space-y-1.5 text-[11px]">
                <div><span className="font-medium t-text">수익 (30점)</span> — 보유 종목 평균 수익률 기반. 손실 1%당 1.5점 감점</div>
                <div><span className="font-medium t-text">시그널 (25점)</span> — 매도/적극매도 신호 종목 비중이 높을수록 감점</div>
                <div><span className="font-medium t-text">수급 (20점)</span> — 외국인 순매도 종목 비중이 높을수록 감점</div>
                <div><span className="font-medium t-text">분산 (15점)</span> — 섹터 집중도(HHI) + 종목 수 3개 미만 시 추가 감점</div>
                <div><span className="font-medium t-text">위험 (10점)</span> — 고위험/주의 등급 종목 비중이 높을수록 감점</div>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
      </>);
      })()}
    </section>
    {/* 포트폴리오 편집 모달 */}
    {showPortfolioEdit && (
      <div className="fixed inset-0 z-[60]" onClick={() => setShowPortfolioEdit(false)}>
        <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
        <div className="fixed bottom-0 left-0 right-0 z-[61] max-h-[85vh] overflow-y-auto rounded-t-2xl t-card border-t t-border-light p-5 sm:max-w-lg sm:mx-auto sm:rounded-2xl sm:bottom-auto sm:top-1/2 sm:-translate-y-1/2"
          style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 2.5rem)' }} onClick={e => e.stopPropagation()}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-bold t-text">포트폴리오 편집</h3>
            <button onClick={() => setShowPortfolioEdit(false)} className="t-text-dim hover:t-text"><X size={18} /></button>
          </div>
          <div className="space-y-3 mb-4">
            {editHoldings.map((h: any, i: number) => (
              <div key={i} className="p-3 t-card-alt rounded-xl">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium t-text">{h.name} <span className="text-[10px] t-text-dim">{h.code}</span></span>
                  <button onClick={() => setEditHoldings(editHoldings.filter((_: any, j: number) => j !== i))}
                    className="text-xs text-red-400 hover:text-red-300">삭제</button>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] t-text-dim block mb-0.5">평균단가</label>
                    <input type="number" value={h.avg_price || ""} onChange={e => { const v = [...editHoldings]; v[i] = {...h, avg_price: Number(e.target.value)}; setEditHoldings(v); }}
                      className="w-full text-[16px] p-1.5 rounded-lg t-card border t-border-light t-text" />
                  </div>
                  <div>
                    <label className="text-[10px] t-text-dim block mb-0.5">수량</label>
                    <input type="number" value={h.quantity || ""} onChange={e => { const v = [...editHoldings]; v[i] = {...h, quantity: Number(e.target.value)}; setEditHoldings(v); }}
                      className="w-full text-[16px] p-1.5 rounded-lg t-card border t-border-light t-text" />
                  </div>
                </div>
              </div>
            ))}
          </div>
          {/* 종목 검색 + 추가 (stock-master 2,618종목 + KIS API fallback) */}
          <div className="mb-4">
            <div className="relative">
              <input
                type="text"
                value={stockSearch}
                onChange={async (e) => {
                  const q = e.target.value;
                  setStockSearch(q);
                  if (q.length < 2) { setSearchResults([]); return; }
                  // stock-master.json 로드 (2,618종목)
                  let list = allStockList;
                  if (!list.length) {
                    setSearchLoading(true);
                    try {
                      const res = await fetch(import.meta.env.BASE_URL + "data/stock-master.json");
                      if (res.ok) {
                        const master = await res.json();
                        const stocks = (master?.stocks || []).map((s: any) => ({
                          code: s.code, name: s.name, market: s.market || "",
                        }));
                        setAllStockList(stocks);
                        list = stocks;
                      }
                    } catch {}
                    setSearchLoading(false);
                  }
                  // 로컬 검색 (종목명 또는 코드)
                  const results = list.filter((s: any) =>
                    s.name?.includes(q) || s.code?.includes(q)
                  ).slice(0, 10);
                  setSearchResults(results);
                  // 6자리 코드인데 결과 없으면 KIS API fallback
                  if (results.length === 0 && /^\d{6}$/.test(q) && supaUser) {
                    setSearchLoading(true);
                    try {
                      const kis = await searchKisStock(q);
                      if (kis) {
                        setSearchResults([{ code: kis.code, name: kis.name, market: "", current_price: kis.current_price, fromKis: true }]);
                      }
                    } catch {}
                    setSearchLoading(false);
                  }
                }}
                placeholder="종목명 또는 코드 검색 (2,618종목)..."
                className="w-full text-[16px] p-2.5 rounded-lg t-card border t-border-light t-text pr-8"
              />
              {searchLoading && <span className="absolute right-3 top-2.5 text-[10px] t-text-dim animate-pulse">검색 중...</span>}
            </div>
            {searchResults.length > 0 ? (
              <div className="mt-1 border t-border-light rounded-lg overflow-hidden max-h-48 overflow-y-auto">
                {searchResults.map((s: any, si: number) => (
                  <button key={si}
                    onClick={() => {
                      if (!editHoldings.find((h: any) => h.code === s.code)) {
                        const autoSector = (portfolio?.holdings || []).find((h: any) => h.code === s.code)?.sector || "";
                        setEditHoldings([...editHoldings, { name: s.name, code: s.code, sector: autoSector, avg_price: 0, quantity: 0 }]);
                      }
                      setStockSearch("");
                      setSearchResults([]);
                    }}
                    className="w-full text-left px-3 py-2 text-xs t-text hover:bg-blue-500/10 transition flex items-center justify-between border-b t-border-light last:border-b-0"
                  >
                    <div>
                      <span className="font-medium">{s.name}</span>
                      <span className="t-text-dim ml-1">{s.code}</span>
                      {s.market && <span className="t-text-dim ml-1 text-[10px]">{s.market}</span>}
                    </div>
                    <div className="flex items-center gap-1">
                      {s.current_price > 0 && <span className="t-text-dim">{s.current_price.toLocaleString()}원</span>}
                      {s.fromKis && <span className="text-[9px] px-1 py-0.5 rounded bg-emerald-500/10 text-emerald-400">KIS</span>}
                    </div>
                  </button>
                ))}
              </div>
            ) : stockSearch.length >= 2 && !searchLoading && (
              <div className="mt-1 p-3 border t-border-light rounded-lg text-center">
                <div className="text-xs t-text-dim">검색 결과 없음</div>
                {/^\d{6}$/.test(stockSearch) ? (
                  supaUser
                    ? <div className="text-[10px] text-emerald-400 mt-1">KIS API로 실시간 조회 중...</div>
                    : <div className="text-[10px] t-text-dim mt-1">로그인하면 KIS API로 실시간 조회 가능</div>
                ) : (
                  <div className="text-[10px] t-text-dim mt-1">종목 코드 6자리 입력 시 KIS API로 실시간 조회합니다</div>
                )}
              </div>
            )}
          </div>
          {/* 저장 */}
          <button onClick={async () => {
            // DB 연동 (로그인 시)
            if (supaUser) {
              const prevCodes = new Set(dbHoldings.map(h => h.code));
              const newCodes = new Set(editHoldings.map((h: any) => h.code));
              // 삭제: DB에 있지만 편집본에 없는 것
              for (const prev of dbHoldings) {
                if (!newCodes.has(prev.code) && prev.id) {
                  await deleteHolding(prev.id);
                }
              }
              // 추가/수정
              for (const h of editHoldings) {
                const existing = dbHoldings.find(d => d.code === h.code);
                if (existing?.id) {
                  // 수정 (avg_price 또는 quantity 변경 시)
                  if (existing.avg_price !== h.avg_price || existing.quantity !== h.quantity) {
                    await updateHolding(existing.id, { avg_price: h.avg_price, quantity: h.quantity, name: h.name });
                  }
                } else {
                  // 신규 추가
                  await insertHolding(h);
                }
              }
              // DB에서 최신 데이터 리로드
              const fresh = await fetchHoldingsFromDB();
              setDbHoldings(fresh);
            }
            // localStorage 폴백 (항상 저장)
            localStorage.setItem("portfolio_holdings", JSON.stringify(editHoldings));
            // 화면 즉시 업데이트
            const totalInvested = editHoldings.reduce((s: number, h: any) => s + (h.avg_price || 0) * (h.quantity || 0), 0);
            const updated = editHoldings.map((h: any) => ({
              ...h,
              weight: totalInvested ? Math.round((h.avg_price || 0) * (h.quantity || 0) / totalInvested * 100) : 0,
              current_price: portfolio?.holdings?.find((ph: any) => ph.code === h.code)?.current_price || 0,
              profit_rate: (h.avg_price && portfolio?.holdings?.find((ph: any) => ph.code === h.code)?.current_price)
                ? Math.round(((portfolio.holdings.find((ph: any) => ph.code === h.code)?.current_price || 0) - h.avg_price) / h.avg_price * 10000) / 100 : 0,
              profit_amount: (h.avg_price && portfolio?.holdings?.find((ph: any) => ph.code === h.code)?.current_price)
                ? ((portfolio.holdings.find((ph: any) => ph.code === h.code)?.current_price || 0) - h.avg_price) * (h.quantity || 0) : 0,
              invested: (h.avg_price || 0) * (h.quantity || 0),
              current_value: (portfolio?.holdings?.find((ph: any) => ph.code === h.code)?.current_price || 0) * (h.quantity || 0),
              signal: portfolio?.holdings?.find((ph: any) => ph.code === h.code)?.signal || "분석 대상 외",
            }));
            const totalValue = updated.reduce((s: number, h: any) => s + h.current_value, 0);
            setPortfolio({
              ...portfolio,
              holdings: updated,
              summary: {
                total_invested: totalInvested,
                total_value: totalValue,
                total_profit_rate: totalInvested ? Math.round((totalValue - totalInvested) / totalInvested * 10000) / 100 : 0,
                total_profit_amount: totalValue - totalInvested,
                total_holdings: updated.length,
              },
            });
            setShowPortfolioEdit(false);
          }} className="w-full text-sm font-medium py-2.5 rounded-xl bg-blue-600 text-white hover:bg-blue-500 transition">
            {supaUser ? "저장 (클라우드)" : "저장 (로컬)"}
          </button>
        </div>
      </div>
    )}
  </>);
}
