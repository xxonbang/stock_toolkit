import { useEffect, useState } from "react";
import {
  ScatterChart, Scatter, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell,
} from "recharts";
import {
  TrendingUp, TrendingDown, Shield,
  Activity, BarChart3, Zap, LineChart, ChevronUp, Sun, Moon, RefreshCw,
} from "lucide-react";
import { dataService } from "../services/dataService";
import { SectionHeader } from "../components/HelpDialog";
import RefreshButtons from "../components/RefreshButtons";
import { supabase, fetchKisPrices, searchKisStock, fetchHoldingsFromDB, insertHolding, updateHolding, deleteHolding } from "../lib/supabase";
import type { KisStockPrice, PortfolioHolding } from "../lib/supabase";

const STAGE_FILL: Record<string, string> = {
  "탄생": "#22c55e", "성장": "#eab308", "과열": "#ef4444", "쇠퇴": "#9ca3af",
};
const STAGE_DOT: Record<string, string> = {
  "탄생": "bg-green-500", "성장": "bg-yellow-500", "과열": "bg-red-500", "쇠퇴": "bg-gray-400",
};

function Gauge({ value, max, label, color }: { value: number; max: number; label: string; color: string }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="t-text-sub">{label}</span>
        <span className="font-medium t-text">{value}</span>
      </div>
      <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--bg-muted)' }}>
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

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

function Empty({ text = "현재 해당 데이터 없음" }: { text?: string }) {
  return (
    <div className="text-center py-5">
      <div className="t-text-dim text-lg mb-1">—</div>
      <div className="text-xs t-text-dim">{text}</div>
      <div className="text-[10px] t-text-dim mt-0.5">데이터 갱신 후 표시됩니다</div>
    </div>
  );
}

function signalBadge(signal: string) {
  if (signal?.includes("적극매수")) return <Badge variant="danger">적극매수</Badge>;
  if (signal?.includes("매수")) return <Badge variant="danger">매수</Badge>;
  if (signal?.includes("적극매도")) return <Badge variant="blue">적극매도</Badge>;
  if (signal?.includes("매도")) return <Badge variant="blue">매도</Badge>;
  return <Badge>중립</Badge>;
}

export default function Dashboard({ onToggleTheme, isDark, page }: { onToggleTheme?: () => void; isDark?: boolean; page?: string }) {
  const isPortfolioPage = page === "portfolio";
  const [performance, setPerformance] = useState<any>(null);
  const [sectors, setSectors] = useState<Record<string, any> | null>(null);
  const [anomalies, setAnomalies] = useState<any[] | null>(null);
  const [smartMoney, setSmartMoney] = useState<any[] | null>(null);
  const [crossSignal, setCrossSignal] = useState<any[] | null>(null);
  const [stockDetail, setStockDetail] = useState<any>(null);
  const [showDualExp, setShowDualExp] = useState(false);
  const [confExp, setConfExp] = useState<{ theme: string; confidence: string; catalyst?: string } | null>(null);
  const [showPortfolioEdit, setShowPortfolioEdit] = useState(false);
  const [editHoldings, setEditHoldings] = useState<any[]>([]);
  const [priceRefreshing, setPriceRefreshing] = useState(false);
  const [stockSearch, setStockSearch] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [allStockList, setAllStockList] = useState<any[]>([]);
  const [supaUser, setSupaUser] = useState<any>(null);
  const [showLogin, setShowLogin] = useState(false);
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPw, setLoginPw] = useState("");
  const [loginError, setLoginError] = useState("");
  const [livePriceTime, setLivePriceTime] = useState("");
  const [dbHoldings, setDbHoldings] = useState<PortfolioHolding[]>([]);
  const [dbLoading, setDbLoading] = useState(false);
  const [showHeaderMenu, setShowHeaderMenu] = useState(false);
  const [lifecycle, setLifecycle] = useState<any[] | null>(null);
  const [riskMonitor, setRiskMonitor] = useState<any[] | null>(null);
  const [newsImpact, setNewsImpact] = useState<Record<string, any> | null>(null);
  const [briefing, setBriefing] = useState<any>(null);
  const [simulation, setSimulation] = useState<any[] | null>(null);
  const [pattern, setPattern] = useState<any[] | null>(null);
  const [sentiment, setSentiment] = useState<any>(null);
  const [shortSqueeze, setShortSqueeze] = useState<any[] | null>(null);
  const [gapAnalysis, setGapAnalysis] = useState<any[] | null>(null);
  const [valuation, setValuation] = useState<any[] | null>(null);
  const [divergence, setDivergence] = useState<any[] | null>(null);
  const [premarket, setPremarket] = useState<any>(null);
  const [portfolio, setPortfolio] = useState<any>(null);
  const [supplyCluster, setSupplyCluster] = useState<any>(null);
  const [exitOptimizer, setExitOptimizer] = useState<any[] | null>(null);
  const [eventCalendar, setEventCalendar] = useState<any>(null);
  const [propagation, setPropagation] = useState<any[] | null>(null);
  const [programTrading, setProgramTrading] = useState<any>(null);
  const [heatmap, setHeatmap] = useState<any>(null);
  const [insiderTrades, setInsiderTrades] = useState<any[] | null>(null);
  const [consensus, setConsensus] = useState<any[] | null>(null);
  const [auction, setAuction] = useState<any[] | null>(null);
  const [orderbook, setOrderbook] = useState<any[] | null>(null);
  const [correlationData, setCorrelationData] = useState<any>(null);
  const [earningsCalendar, setEarningsCalendar] = useState<any>(null);
  const [aiMentor, setAiMentor] = useState<any>(null);
  const [tradingJournal, setTradingJournal] = useState<any>(null);
  const [memberTrading, setMemberTrading] = useState<any[] | null>(null);
  const [tradingValue, setTradingValue] = useState<any[] | null>(null);
  const [paperTrading, setPaperTrading] = useState<any>(null);
  const [forecastAccuracy, setForecastAccuracy] = useState<any>(null);
  const [volumeProfile, setVolumeProfile] = useState<any[] | null>(null);
  const [signalConsistency, setSignalConsistency] = useState<any[] | null>(null);
  const [simulationHistory, setSimulationHistory] = useState<any[] | null>(null);
  const [intradayStockFlow, setIntradayStockFlow] = useState<any[] | null>(null);
  const [indicatorHistory, setIndicatorHistory] = useState<any>(null);
  const [consecutiveSignals, setConsecutiveSignals] = useState<any>(null);

  const dbHoldingsRef = { current: dbHoldings };
  dbHoldingsRef.current = dbHoldings;

  const loadAllData = () => {
    dataService.getPerformance().then(setPerformance);
    dataService.getSectorFlow().then(setSectors);
    dataService.getAnomalies().then(setAnomalies);
    dataService.getSmartMoney().then(setSmartMoney);
    dataService.getCrossSignal().then(setCrossSignal);
    dataService.getLifecycle().then(setLifecycle);
    dataService.getRiskMonitor().then(setRiskMonitor);
    dataService.getNewsImpact().then(setNewsImpact);
    dataService.getBriefing().then(setBriefing);
    dataService.getSimulation().then(setSimulation);
    dataService.getPattern().then(setPattern);
    dataService.getSentiment().then(setSentiment);
    dataService.getShortSqueeze().then(setShortSqueeze);
    dataService.getGapAnalysis().then(setGapAnalysis);
    dataService.getValuation().then(setValuation);
    dataService.getVolumeDivergence().then(setDivergence);
    dataService.getPremarket().then(setPremarket);
    dataService.getPortfolio().then(async (p) => {
      if (!p) return;
      // DB holdings을 직접 로드하여 최신 데이터 보장 (타이밍 이슈 방지)
      let userHoldings = dbHoldingsRef.current;
      if (userHoldings.length === 0) {
        try { userHoldings = await fetchHoldingsFromDB(); } catch {}
      }
      if (userHoldings.length === 0) {
        const saved = localStorage.getItem("portfolio_holdings");
        if (saved) { try { userHoldings = JSON.parse(saved); } catch {} }
      }
      // DB avg_price가 항상 우선 — server(portfolio.json)의 avg_price 무시
      const merged = (userHoldings.length > 0 ? userHoldings : p.holdings || []).map((lh: any) => {
        const server = p.holdings?.find((sh: any) => sh.code === lh.code) || {};
        const avgPrice = lh.avg_price || 0;
        const qty = lh.quantity || 0;
        const cp = (server as any).current_price || 0;
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
      p.holdings = merged;
      p.summary = { total_invested: totalInv, total_value: totalVal, total_profit_rate: totalInv ? Math.round((totalVal - totalInv) / totalInv * 10000) / 100 : 0, total_profit_amount: totalVal - totalInv, total_holdings: merged.length };
      setPortfolio(p);
    });
    dataService.getSupplyCluster().then(setSupplyCluster);
    dataService.getExitOptimizer().then(setExitOptimizer);
    dataService.getEventCalendar().then(setEventCalendar);
    dataService.getThemePropagation().then(setPropagation);
    dataService.getProgramTrading().then(setProgramTrading);
    dataService.getIntradayHeatmap().then(setHeatmap);
    dataService.getInsiderTrades().then(setInsiderTrades);
    dataService.getConsensus().then(setConsensus);
    dataService.getAuction().then(setAuction);
    dataService.getOrderbook().then(setOrderbook);
    dataService.getCorrelation().then(setCorrelationData);
    dataService.getEarningsCalendar().then(setEarningsCalendar);
    dataService.getAiMentor().then(setAiMentor);
    dataService.getTradingJournal().then(setTradingJournal);
    dataService.getMemberTrading().then(setMemberTrading);
    dataService.getTradingValue().then(setTradingValue);
    dataService.getPaperTrading().then(setPaperTrading);
    dataService.getForecastAccuracy().then(setForecastAccuracy);
    dataService.getVolumeProfile().then(setVolumeProfile);
    dataService.getSignalConsistency().then(setSignalConsistency);
    dataService.getSimulationHistory().then(setSimulationHistory);
    dataService.getIntradayStockFlow().then(setIntradayStockFlow);
    dataService.getIndicatorHistory().then(setIndicatorHistory);
    dataService.getConsecutiveSignals().then(setConsecutiveSignals);
  };

  useEffect(() => {
    loadAllData();
    // Supabase 세션 확인
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      setSupaUser(session?.user || null);
      if (session?.user) {
        setDbLoading(true);
        const holdings = await fetchHoldingsFromDB();
        setDbHoldings(holdings);
        setDbLoading(false);
      }
    });
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (_event, session) => {
      setSupaUser(session?.user || null);
      if (session?.user) {
        setDbLoading(true);
        const holdings = await fetchHoldingsFromDB();
        setDbHoldings(holdings);
        setDbLoading(false);
      } else {
        setDbHoldings([]);
      }
    });
    // 장중 5분, 장외 10분 자동 폴링
    const now = new Date();
    const h = now.getHours();
    const isMarketHours = h >= 9 && h < 16;
    const interval = setInterval(loadAllData, isMarketHours ? 5 * 60 * 1000 : 10 * 60 * 1000);
    return () => { clearInterval(interval); subscription.unsubscribe(); };
  }, []);

  // 공통 타임스탬프 (performance.json 기준, 대부분 동일 시점)
  const ts = performance?.generated_at || "";
  const briefTs = briefing?.generated_at || ts;
  const sentimentTs = sentiment?.generated_at || ts;

  const fgScore = performance?.fear_greed?.score ?? 0;
  const fgLabel = fgScore < 25 ? "극단적 공포" : fgScore < 45 ? "공포" : fgScore < 55 ? "중립" : fgScore < 75 ? "탐욕" : "극단적 탐욕";
  const fgColor = fgScore < 25 ? "bg-red-500" : fgScore < 45 ? "bg-orange-400" : fgScore < 55 ? "bg-gray-400" : fgScore < 75 ? "bg-green-400" : "bg-green-600";
  const vixVal = performance?.vix?.current ?? 0;
  const vixLabel = vixVal < 15 ? "안정" : vixVal < 20 ? "보통" : vixVal < 30 ? "불안" : "공포";
  const vixColor = vixVal < 15 ? "bg-green-500" : vixVal < 20 ? "bg-yellow-500" : vixVal < 30 ? "bg-orange-500" : "bg-red-500";

  // 카테고리 퀵 네비게이션
  const categories = [
    { id: "cat-market", label: "시장", icon: "📊" },
    { id: "cat-signal", label: "신호", icon: "🎯" },
    { id: "cat-analysis", label: "분석", icon: "🔍" },
    { id: "cat-strategy", label: "전략", icon: "⚡" },
    { id: "cat-system", label: "시스템", icon: "🤖" },
  ];
  const [activeCategory, setActiveCategory] = useState("cat-market");
  const [showScrollTop, setShowScrollTop] = useState(false);

  // 스크롤 위치에 따라 활성 카테고리 추적
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        // 최상단이면 항상 시장
        if (window.scrollY < 100) {
          setActiveCategory("cat-market");
          return;
        }
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveCategory(entry.target.id);
          }
        }
      },
      { rootMargin: "-100px 0px -60% 0px", threshold: 0 }
    );
    categories.forEach((cat) => {
      const el = document.getElementById(cat.id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, []);

  // 스크롤 위치 감지 — 최상단 버튼 표시
  useEffect(() => {
    const onScroll = () => setShowScrollTop(window.scrollY > 600);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="max-w-2xl mx-auto px-4 pt-0 pb-16 space-y-5">
      {/* 로그인 모달 */}
      {showLogin && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center" onClick={() => setShowLogin(false)}>
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
          <div className="relative w-[85%] max-w-sm t-card border t-border-light rounded-2xl p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm font-bold t-text">로그인</span>
              <button onClick={() => setShowLogin(false)} className="t-text-dim hover:t-text text-lg">✕</button>
            </div>
            <input type="email" placeholder="이메일" value={loginEmail} onChange={e => setLoginEmail(e.target.value)}
              className="w-full text-[16px] p-2.5 rounded-lg t-card border t-border-light t-text mb-2" />
            <input type="password" placeholder="비밀번호" value={loginPw} onChange={e => setLoginPw(e.target.value)}
              className="w-full text-[16px] p-2.5 rounded-lg t-card border t-border-light t-text mb-3" />
            {loginError && <p className="text-[11px] text-red-400 mb-2">{loginError}</p>}
            <button onClick={async () => {
              setLoginError("");
              const { error } = await supabase.auth.signInWithPassword({ email: loginEmail, password: loginPw });
              if (error) { setLoginError(error.message); return; }
              setShowLogin(false);
              setLoginEmail("");
              setLoginPw("");
            }} className="w-full text-sm font-medium py-2.5 rounded-xl bg-blue-600 text-white hover:bg-blue-500 transition">로그인</button>
            {supaUser && (
              <button onClick={async () => { await supabase.auth.signOut(); setSupaUser(null); setShowLogin(false); }}
                className="w-full text-xs py-2 mt-2 t-text-dim hover:text-red-400 transition">로그아웃</button>
            )}
          </div>
        </div>
      )}
      {/* 신뢰도 설명 팝업 */}
      {confExp && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center" onClick={() => setConfExp(null)}>
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
          <div className="relative w-[85%] max-w-sm t-card border t-border-light rounded-2xl p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-bold t-text">{confExp.theme}</span>
              <button onClick={() => setConfExp(null)} className="t-text-dim hover:t-text text-lg">✕</button>
            </div>
            <div className="mb-3">
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                confExp.confidence.includes("높") ? "bg-emerald-500/10 text-emerald-500" :
                confExp.confidence.includes("보통") ? "bg-amber-500/10 text-amber-500" :
                "bg-gray-500/10 t-text-dim"
              }`}>신뢰도: {confExp.confidence}</span>
            </div>
            <div className="text-[12px] t-text-sub leading-relaxed space-y-2">
              <p>{confExp.confidence.includes("높")
                ? "AI가 이 테마의 상승 가능성을 높게 판단합니다. 강력한 촉매(재료)가 확인되었고, 대장주의 수급과 기술적 신호가 일치합니다."
                : confExp.confidence.includes("보통")
                ? "AI가 이 테마에 주목하고 있으나, 일부 불확실성이 존재합니다. 촉매는 있으나 수급이 불안정하거나, 대장주 신호가 엇갈릴 수 있습니다."
                : "AI가 이 테마를 관찰 중이나, 상승 동력이 약하거나 리스크가 높습니다. 단기 변동성에 주의가 필요합니다."
              }</p>
              {confExp.catalyst && (
                <p><span className="font-semibold t-text">촉매:</span> {confExp.catalyst}</p>
              )}
              {(confExp as any).description && (
                <p><span className="font-semibold t-text">상세:</span> {(confExp as any).description}</p>
              )}
            </div>
          </div>
        </div>
      )}
      {/* 종목 상세 팝업 */}
      {stockDetail && (
        <div className="fixed inset-0 z-[60]" onClick={() => { setStockDetail(null); setShowDualExp(false); }}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
          <div className="fixed bottom-0 left-0 right-0 z-[61] max-h-[85vh] overflow-y-auto rounded-t-2xl t-card border-t t-border-light p-5 sm:max-w-lg sm:mx-auto sm:rounded-2xl sm:bottom-auto sm:top-1/2 sm:-translate-y-1/2" style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 2.5rem)' }} onClick={e => e.stopPropagation()}>
            {/* 헤더 */}
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-base font-bold t-text">{stockDetail.name}</h3>
                <span className="text-[11px] t-text-dim">{stockDetail.code}{stockDetail.market ? ` · ${stockDetail.market}` : ""}</span>
              </div>
              <div className="flex items-center gap-2">
                {stockDetail.dual_signal && (() => {
                  const ds = stockDetail.dual_signal;
                  const explanations: Record<string, string> = {
                    "고확신": "Vision AI와 KIS API 양쪽 모두 매수 신호가 일치합니다. 두 독립 분석의 합의로 신뢰도가 높습니다.",
                    "확인필요": "Vision AI는 매수 신호이나, KIS API는 중립 또는 다른 판단입니다. 한쪽만 매수이므로 추가 확인이 필요합니다.",
                    "KIS매수": "KIS API만 매수 신호이고, Vision AI는 중립입니다. KIS 정량 분석 기반이며 AI 차트 판단은 미동의 상태입니다.",
                    "혼조": "Vision AI와 KIS API의 판단이 서로 다릅니다. 신중한 접근이 필요합니다.",
                  };
                  return (
                    <div className="relative">
                      <span onClick={(e) => { e.stopPropagation(); setShowDualExp(!showDualExp); }} className={`text-[11px] font-semibold px-2 py-0.5 rounded-full cursor-pointer ${
                        ds === "고확신" ? "bg-emerald-500/10 text-emerald-500" :
                        ds === "KIS매수" ? "bg-blue-500/10 text-blue-500" :
                        "bg-amber-500/10 text-amber-500"
                      }`}>{ds}</span>
                      {showDualExp && (
                        <div className="absolute right-0 top-8 w-64 p-3 rounded-xl t-card border t-border-light shadow-lg z-10" onClick={e => e.stopPropagation()}>
                          <div className="text-[11px] font-semibold t-text mb-1">{ds}</div>
                          <div className="text-[11px] t-text-sub leading-relaxed">{explanations[ds] || ""}</div>
                        </div>
                      )}
                    </div>
                  );
                })()}
                <button onClick={() => { setStockDetail(null); setShowDualExp(false); }} className="text-lg t-text-dim hover:t-text">✕</button>
              </div>
            </div>
            {/* 분석 데이터 없음 안내 */}
            {stockDetail._noData && (
              <div className="text-center py-8">
                <div className="text-2xl mb-2">📊</div>
                <div className="text-sm t-text-sub mb-1">분석 데이터가 아직 없습니다</div>
                <div className="text-[11px] t-text-dim">이 종목은 현재 AI 분석 대상에 포함되지 않았습니다.<br/>다음 분석 시점에 포함될 수 있습니다.</div>
              </div>
            )}
            {/* 신호 요약 */}
            {!stockDetail._noData && <><div className="grid grid-cols-2 gap-2 mb-4">
              <div className="t-card-alt rounded-lg p-2.5">
                <div className="text-[10px] t-text-dim mb-1">Vision AI</div>
                <div className={`text-xs font-semibold ${stockDetail.vision_signal === "매수" || stockDetail.vision_signal === "적극매수" ? "text-red-500" : "t-text"}`}>
                  {stockDetail.vision_signal || "-"} {stockDetail.vision_confidence ? `(${Math.round(stockDetail.vision_confidence * 100)}%)` : ""}
                </div>
              </div>
              <div className="t-card-alt rounded-lg p-2.5">
                <div className="text-[10px] t-text-dim mb-1">KIS API</div>
                <div className={`text-xs font-semibold ${stockDetail.api_signal === "매수" || stockDetail.api_signal === "적극매수" ? "text-red-500" : "t-text"}`}>
                  {stockDetail.api_signal || "-"} {stockDetail.api_confidence ? `(${Math.round(stockDetail.api_confidence * 100)}%)` : ""}
                </div>
              </div>
            </div>
            {/* 핵심 요인 (api_key_factors) */}
            {stockDetail.api_key_factors && Object.keys(stockDetail.api_key_factors).length > 0 && (
              <div className="mb-4">
                <div className="text-[11px] font-semibold t-text mb-1.5">핵심 요인</div>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(stockDetail.api_key_factors).map(([k, v]: [string, any]) => {
                    const label: Record<string, string> = { price_trend: "추세", volume_signal: "거래량", foreign_flow: "외국인", institution_flow: "기관", valuation: "밸류에이션" };
                    return (
                      <span key={k} className={`text-[11px] px-2 py-0.5 rounded-full ${
                        String(v).includes("매수") || String(v).includes("상승") || String(v).includes("급증") ? "bg-red-500/8 text-red-400" :
                        String(v).includes("매도") || String(v).includes("하락") || String(v).includes("고평가") ? "bg-blue-500/8 text-blue-400" :
                        "t-card-alt t-text-sub"
                      }`}>{label[k] || k}: {String(v)}</span>
                    );
                  })}
                </div>
              </div>
            )}
            {/* 재료 분석 */}
            {(stockDetail.vision_reason || stockDetail.api_reason) && (
              <div className="mb-4">
                <div className="text-[11px] font-semibold t-text mb-1.5">재료 분석</div>
                {stockDetail.vision_reason && (
                  <div className="mb-2">
                    <div className="text-[10px] t-text-dim mb-0.5">Vision AI</div>
                    <p className="text-[12px] t-text-sub leading-relaxed">{stockDetail.vision_reason}</p>
                  </div>
                )}
                {stockDetail.api_reason && (
                  <div>
                    <div className="text-[10px] t-text-dim mb-0.5">KIS API</div>
                    <p className="text-[12px] t-text-sub leading-relaxed">{stockDetail.api_reason}</p>
                  </div>
                )}
              </div>
            )}
            {/* 관련 뉴스 */}
            {((stockDetail.vision_news?.length > 0) || (stockDetail.api_news?.length > 0)) && (
              <div>
                <div className="text-[11px] font-semibold t-text mb-1.5">관련 뉴스</div>
                <div className="space-y-1.5">
                  {[...(stockDetail.vision_news || []), ...(stockDetail.api_news || [])].reduce((acc: any[], n: any) => {
                    if (!acc.find((a: any) => a.title === n.title)) acc.push(n);
                    return acc;
                  }, []).slice(0, 6).map((n: any, i: number) => (
                    <a key={i} href={n.originallink || n.link} target="_blank" rel="noopener noreferrer"
                       className="block t-card-alt rounded-lg p-2.5 hover:bg-blue-500/5 transition-colors">
                      <div className="text-[12px] font-medium t-text leading-snug">{n.title}</div>
                      {n.description && <div className="text-[11px] t-text-dim mt-0.5 line-clamp-2">{n.description}</div>}
                      {n.pubDate && <div className="text-[10px] t-text-dim mt-1">{n.pubDate}</div>}
                    </a>
                  ))}
                </div>
              </div>
            )}
            </>}
          </div>
        </div>
      )}
      {/* 헤더 — 컴팩트 sticky */}
      <div className="sticky top-0 z-10 -mx-4 px-4 pt-2 pb-0 backdrop-blur-md" style={{ background: 'var(--bg-header)', borderBottom: '1px solid var(--border-light)' }}>
        <div className="flex items-center justify-between h-10">
          <h1
            className="text-lg font-bold t-text flex items-center gap-2 shrink-0 cursor-pointer"
            onClick={async () => {
              if ("caches" in window) {
                const keys = await caches.keys();
                await Promise.all(keys.map((k) => caches.delete(k)));
              }
              const regs = await navigator.serviceWorker?.getRegistrations();
              if (regs) await Promise.all(regs.map((r) => r.unregister()));
              window.scrollTo(0, 0);
              window.location.href = window.location.pathname + window.location.search;
            }}
          >
            <img src={import.meta.env.BASE_URL + "favicon.svg"} alt="logo" className="w-5 h-5 shrink-0" />
            Stock Toolkit
          </h1>
          <div className="flex items-center gap-1.5 shrink-0">
            {/* 신선도 */}
            {ts && (() => {
              const m = ts.match(/(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})/);
              if (!m) return null;
              const diffMin = Math.round((Date.now() - new Date(+m[1], +m[2]-1, +m[3], +m[4], +m[5]).getTime()) / 60000);
              const label = diffMin < 5 ? "방금" : diffMin < 60 ? `${diffMin}분 전` : diffMin < 1440 ? `${Math.round(diffMin/60)}시간 전` : `${Math.round(diffMin/1440)}일 전`;
              const color = diffMin < 30 ? "text-emerald-400" : diffMin < 180 ? "text-amber-400" : "text-red-400";
              return <span className={`text-[10px] ${color}`}>{label}</span>;
            })()}
            {/* 테마 토글 */}
            {onToggleTheme && (
              <button onClick={onToggleTheme} className="p-1.5 rounded-lg hover:opacity-80 transition" title={isDark ? "라이트 모드" : "다크 모드"}>
                {isDark ? <Sun size={16} className="text-amber-400" /> : <Moon size={16} className="t-text-sub" />}
              </button>
            )}
            {/* ... 메뉴 버튼 */}
            <div className="relative">
              <button onClick={() => setShowHeaderMenu(!showHeaderMenu)} className="p-1.5 rounded-lg hover:opacity-80 transition t-text-sub text-lg leading-none">⋮</button>
              {showHeaderMenu && (
                <>
                  <div className="fixed inset-0 z-30" onClick={() => setShowHeaderMenu(false)} />
                  <div className="absolute right-0 top-9 z-40 w-48 t-card border t-border-light rounded-xl shadow-lg overflow-hidden">
                    <div className="p-1">
                      <RefreshButtons menuMode />
                      <div className="border-t t-border-light my-1" />
                      {supaUser ? (
                        <button onClick={async () => { await supabase.auth.signOut(); setSupaUser(null); setShowHeaderMenu(false); }}
                          className="w-full flex items-center gap-2.5 px-3 py-2.5 text-[13px] text-red-400 hover:bg-red-500/10 rounded-lg transition">
                          <span className="text-base">↪</span>
                          로그아웃
                        </button>
                      ) : (
                        <button onClick={() => { setShowLogin(true); setShowHeaderMenu(false); }}
                          className="w-full flex items-center gap-2.5 px-3 py-2.5 text-[13px] text-blue-400 hover:bg-blue-500/10 rounded-lg transition">
                          <span className="text-base">→</span>
                          로그인
                        </button>
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
        {/* 페이지 탭 */}
        <div className="flex -mx-1">
          <a href="#/" className={`flex-1 text-center py-3 text-sm font-medium transition border-b-[3px] ${!isPortfolioPage ? "font-semibold t-accent border-current" : "t-text-dim hover:t-text-sub border-transparent"}`}>대시보드</a>
          <a href="#/portfolio" className={`flex-1 text-center py-3 text-sm font-medium transition border-b-[3px] ${isPortfolioPage ? "font-semibold t-accent border-current" : "t-text-dim hover:t-text-sub border-transparent"}`}>포트폴리오</a>
          <a href="#/scanner" className="flex-1 text-center py-3 text-sm font-medium t-text-dim hover:t-text-sub transition border-b-[3px] border-transparent">스캐너</a>
          <a href="#/auto-trader" className="flex-1 text-center py-3 text-sm font-medium t-text-dim hover:t-text-sub transition border-b-[3px] border-transparent">모의투자</a>
        </div>
      </div>
      {/* 헤더-컨텐츠 여백 */}

      {/* ===== 시장 카테고리 ===== */}
      {!isPortfolioPage && <>
      <div id="cat-market" className="scroll-mt-24" />

      {/* 장전 프리마켓 */}
      {premarket && (
        <section className="t-card rounded-xl p-4 border-l-4 border-l-cyan-500/50">
          <SectionHeader id="premarket" timestamp={ts}>장전 프리마켓</SectionHeader>
          {/* 예측 결과 카드 */}
          <div className={`rounded-lg p-3 mb-3 text-center ${premarket.prediction?.includes("상승") || premarket.prediction?.includes("강세") ? "bg-red-500/10 border border-red-500/20" : premarket.prediction?.includes("하락") || premarket.prediction?.includes("약세") ? "bg-blue-500/10 border border-blue-500/20" : "t-card-alt border t-border-light"}`}>
            <div className="text-[10px] t-text-dim mb-1">시장 출발 예상</div>
            <div className={`text-lg font-bold ${premarket.prediction?.includes("상승") || premarket.prediction?.includes("강세") ? "text-red-600" : premarket.prediction?.includes("하락") || premarket.prediction?.includes("약세") ? "text-blue-600" : "t-text"}`}>
              {premarket.prediction}
            </div>
          </div>
          {/* 핵심 요인 */}
          {premarket.key_factors?.length > 0 && (
            <div>
              <div className="text-xs font-medium t-text-sub mb-1.5">핵심 요인</div>
              <div className="space-y-1">
                {premarket.key_factors.map((f: string, i: number) => {
                  const isPositive = f.includes("+") || f.includes("상승") || f.includes("매수");
                  const isNegative = f.includes("-") || f.includes("하락") || f.includes("공포") || f.includes("경고") || f.includes("우려");
                  return (
                    <div key={i} className="flex items-start gap-1.5 text-xs">
                      <span className={`shrink-0 mt-0.5 ${isPositive ? "text-red-400" : isNegative ? "text-blue-400" : "t-text-dim"}`}>
                        {isPositive ? "▲" : isNegative ? "▼" : "·"}
                      </span>
                      <span className="t-text-sub">{f}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </section>
      )}

      {/* AI 모닝 브리핑 */}
      {briefing?.morning && (() => {
        const raw = briefing.morning as string;
        // HTML 태그 정리
        const strip = (s: string) => s.replace(/<\/?[bi]>/g, "").replace(/<br\s*\/?>/gi, "\n").replace(/&nbsp;/g, " ").trim();
        // 범용 섹션 파서: Gemini 형식 변동에 대응
        let sections: { title: string; body: string }[] = [];
        // 모든 가능한 제목 패턴을 순서대로 시도
        const patterns = [
          // 1) "<i><b>제목:</b></i>" 또는 "<i><b>제목</b></i>"
          /(?:<i>\s*)?<b>([^<]{2,30}?)(?::?\s*)<\/b>(?:\s*<\/i>)?/g,
          // 2) "N. <b>제목</b>" 또는 "<b>N. 제목</b>"
          /(?:<b>\s*)?\d+\.\s*(?:<b>)?([^<\n]{2,30}?)(?:<\/b>)/g,
          // 3) "**제목**"
          /\*\*([^*\n]{2,30}?)\*\*/g,
        ];
        for (const regex of patterns) {
          if (sections.length >= 2) break;
          sections = [];
          const matches = [...raw.matchAll(regex)];
          // 첫 매칭이 날짜/타이틀이면 건너뛰기
          const filtered = matches.filter(m => {
            const t = strip(m[1]);
            return t && t.length >= 2 && t.length <= 30 && !t.includes("모닝") && !t.includes("브리프") && !t.includes("년 ");
          });
          if (filtered.length >= 2) {
            for (let i = 0; i < filtered.length; i++) {
              const title = strip(filtered[i][1]).replace(/:$/, "").replace(/^\d+\.\s*/, "");
              const start = filtered[i].index! + filtered[i][0].length;
              const end = i < filtered.length - 1 ? filtered[i + 1].index! : raw.length;
              const body = strip(raw.slice(start, end)).replace(/\n\d+\.\s*$/, "").replace(/^\d+\.\s*/, "");
              if (title) sections.push({ title, body });
            }
          }
        }
        // 최종 폴백
        if (sections.length < 2) {
          sections = [{ title: "AI 분석", body: strip(raw) }];
        }
        // "주목 테마" 섹션은 테마 예측 카드에 통합 → AI 브리핑에서 제거
        const hasThemeForecast = performance?.theme_forecast?.themes?.length > 0;
        if (hasThemeForecast) {
          sections = sections.filter(sec => {
            const t = sec.title;
            return !(t.includes("테마") && (t.includes("주목") || t.includes("주요")));
          });
        }
        // "주목 테마" 섹션의 촉매 설명을 추출 (테마 예측 카드에서 활용)
        const themeCatalystMap: Record<string, string> = {};
        const origThemeSec = raw.match(/\d+\.\s*<b>[^<]*주목[^<]*<\/b>([\s\S]*?)(?=\d+\.\s*<b>|$)/);
        if (origThemeSec) {
          const lines = origThemeSec[1].replace(/<\/?[bi]>/g, "").split("\n").filter((l: string) => l.trim());
          for (const line of lines) {
            const m = line.match(/[✔️✅·\-\*]\s*(.+?)\s*\((.+)\)/);
            if (m) themeCatalystMap[m[1].trim()] = m[2].trim();
          }
        }
        const matchKey = (title: string) => {
          if (title.includes("글로벌") || title.includes("환경") || title.includes("시장")) return "글로벌 환경";
          if (title.includes("테마") && (title.includes("주목") || title.includes("주요"))) return "오늘의 주목 테마";
          if (title.includes("핵심") || title.includes("고확신") || title.includes("관심") || title.includes("종목")) return "고확신 종목";
          if (title.includes("주의") || title.includes("위험")) return "주의 종목";
          if (title.includes("전략") || title.includes("제안")) return "전략 제안";
          return title;
        };
        const iconMap: Record<string, string> = {
          "글로벌 환경": "🌍", "오늘의 주목 테마": "🔥", "고확신 종목": "🎯",
          "주의 종목": "⚠️", "전략 제안": "💡",
        };
        const accentMap: Record<string, string> = {
          "글로벌 환경": "border-l-slate-400", "오늘의 주목 테마": "border-l-cyan-400",
          "고확신 종목": "border-l-emerald-400", "주의 종목": "border-l-rose-400", "전략 제안": "border-l-indigo-400",
        };
        // 종목명(코드) 패턴을 클릭 가능한 요소로 변환
        const allStockData = [...(crossSignal || []), ...(smartMoney || [])];
        const renderTextWithStockLinks = (text: string) => {
          // "종목명(6자리코드)" 패턴 매칭
          const parts = text.split(/([가-힣A-Za-z\s]+\(\d{6}\))/g);
          return parts.map((part, k) => {
            const m = part.match(/^(.+)\((\d{6})\)$/);
            if (m) {
              const name = m[1].trim();
              const code = m[2];
              const detail = allStockData.find((s: any) => s.code === code);
              return (
                <span key={k}
                  onClick={() => detail ? setStockDetail(detail) : setStockDetail({ name, code, _noData: true })}
                  className="font-semibold text-blue-400 cursor-pointer hover:underline"
                >{name}({code})</span>
              );
            }
            return <span key={k}>{part}</span>;
          });
        };
        // 본문 라인 렌더링
        const renderBody = (body: string) => {
          return body.split("\n").filter(l => l.trim()).map((line: string, j: number) => {
            let trimmed = line.trim();
            // 잔여 번호 제거 ("2.", "3." 등 단독 라인 또는 앞쪽 번호)
            if (/^\d+\.\s*$/.test(trimmed)) return null;
            trimmed = trimmed.replace(/^\d+\.\s*/, "");
            // 앞쪽 콜론 제거 (": 설명" → "설명")
            trimmed = trimmed.replace(/^:\s*/, "");
            if (!trimmed) return null;
            // 체크 항목 (✔️, ✅, ·, -, *)
            if (/^[✔️✅·\-\*]/.test(trimmed)) {
              const text = trimmed.replace(/^[✔️✅·\-\*]+\s*/, "");
              if (!text) return null;
              return (
                <div key={j} className="flex items-start gap-2 py-0.5">
                  <span className="text-emerald-400 mt-0.5 text-[10px]">●</span>
                  <span className="t-text-sub text-[13px] leading-relaxed">{renderTextWithStockLinks(text)}</span>
                </div>
              );
            }
            // 주의/전략 라벨 제거
            const cleaned = trimmed.replace(/^(주의 종목:|전략 제안:)\s*/i, "");
            return <p key={j} className="t-text text-[13px] leading-[1.7]">{renderTextWithStockLinks(cleaned)}</p>;
          }).filter(Boolean);
        };
        return (
          <section className="space-y-3">
            <SectionHeader id="briefing" timestamp={briefTs}>AI 모닝 브리핑</SectionHeader>
            {sections.map((sec: any, i: number) => {
              const key = matchKey(sec.title);
              return (
              <div key={i} className={`rounded-xl border t-border-light border-l-[3px] ${accentMap[key] || "border-l-gray-400"} t-card-alt p-4`}>
                <div className="flex items-center gap-2 mb-2.5">
                  <span className="text-base">{iconMap[key] || "📌"}</span>
                  <span className="text-[13px] font-bold t-text tracking-tight">{sec.title}</span>
                </div>
                <div className="space-y-1">
                  {renderBody(sec.body).length > 0
                    ? renderBody(sec.body)
                    : <p className="text-[12px] t-text-dim italic">해당 항목 없음</p>
                  }
                </div>
              </div>
              );
            })}
            {/* 오늘의 테마 예측 — AI 브리핑 주목 테마 통합 */}
            {performance?.theme_forecast?.themes?.length > 0 && (
              <div className="rounded-xl border t-border-light border-l-[3px] border-l-cyan-400/60 t-card-alt p-4">
                <div className="flex items-center gap-2 mb-2.5">
                  <span className="text-base">🔥</span>
                  <span className="text-[13px] font-bold t-text tracking-tight">오늘의 주목 테마</span>
                </div>
                {performance.theme_forecast.market_context && (
                  <p className="text-[13px] t-text-sub leading-[1.7] mb-3">
                    {performance.theme_forecast.market_context}
                  </p>
                )}
                <div className="space-y-0">
                  {performance.theme_forecast.themes.slice(0, 5).map((t: any, i: number) => {
                    const themeName = t.theme_name || t.name || "";
                    const conf = t.confidence;
                    const confLabel = typeof conf === "number" ? `${conf}%` : conf || "";
                    const isHigh = confLabel.includes("높") || (typeof conf === "number" && conf >= 70);
                    const isMid = confLabel.includes("보통") || (typeof conf === "number" && conf >= 40 && conf < 70);
                    // 촉매: theme_forecast 원본 우선, AI 브리핑 파싱 폴백
                    const catalyst = t.catalyst || Object.entries(themeCatalystMap).find(([k]) => themeName.includes(k) || k.includes(themeName))?.[1] || "";
                    const description = t.description || "";
                    const leaders = (t.leader_stocks || []).slice(0, 3);
                    return (
                      <div key={i} className="py-2.5 border-b t-border-light last:border-b-0">
                        <div className="flex items-center justify-between">
                          <span className="text-[13px] font-medium t-text">{themeName}</span>
                          {confLabel && (
                            <span onClick={() => setConfExp({ theme: themeName, confidence: confLabel, catalyst, description } as any)}
                              className={`text-[11px] font-semibold px-2 py-0.5 rounded-full shrink-0 cursor-pointer ${
                              isHigh ? "bg-emerald-500/10 text-emerald-500" :
                              isMid ? "bg-amber-500/10 text-amber-500" :
                              "bg-gray-500/10 t-text-dim"
                            }`}>{confLabel}</span>
                          )}
                        </div>
                        {(catalyst || leaders.length > 0) && (
                          <div className="mt-1.5 space-y-1">
                            {catalyst && <div className="text-[12px] t-text-sub leading-relaxed">{catalyst}</div>}
                            {leaders.length > 0 && (
                              <div className="flex flex-wrap gap-1">
                                {leaders.map((l: any, li: number) => {
                                  const detail = [...(crossSignal || []), ...(smartMoney || [])].find((s: any) => s.code === l.code);
                                  return (
                                    <span key={li}
                                      onClick={(e) => { e.stopPropagation(); detail ? setStockDetail(detail) : setStockDetail({ name: l.name, code: l.code, _noData: true }); }}
                                      className="text-[11px] px-1.5 py-0.5 rounded bg-blue-500/8 t-text-sub cursor-pointer hover:bg-blue-500/20 transition-colors"
                                    >{l.name}</span>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </section>
        );
      })()}

      {/* 시장 현황 (심리 온도계 통합) */}
      {performance && (
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="market" timestamp={ts}>시장 현황</SectionHeader>

          {/* 시장 심리 — 시장 현황 상단에 통합 */}
          {sentiment && (
            <div className="mb-4 pb-4 border-b t-border-light">
              <div className="flex items-center gap-4 mb-2">
                <div className="text-2xl font-bold t-text">{sentiment.score}<span className="text-xs font-normal t-text-dim">/100</span></div>
                <div>
                  <div className={`text-sm font-semibold ${sentiment.score < 30 ? "text-blue-600" : sentiment.score < 60 ? "t-text-sub" : "text-red-600"}`}>
                    {sentiment.label}
                  </div>
                  <div className="text-[10px] t-text-dim">{sentiment.strategy}</div>
                </div>
              </div>
              <div className="h-1.5 t-muted rounded-full overflow-hidden mb-1.5">
                <div className={`h-full rounded-full ${sentiment.score < 30 ? "bg-blue-500" : sentiment.score < 60 ? "bg-gray-400" : "bg-red-500"}`} style={{ width: `${sentiment.score}%` }} />
              </div>
              <div className="flex justify-between text-[10px] t-text-dim">
                <span>극단적 공포 0</span><span>중립 50</span><span>극단적 탐욕 100</span>
              </div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Gauge value={fgScore} max={100} label="공포·탐욕 지수" color={fgColor} />
              <p className="text-xs t-text-sub">{fgLabel} 구간</p>
            </div>
            <div className="space-y-2">
              <Gauge value={vixVal} max={50} label="VIX 변동성" color={vixColor} />
              <p className="text-xs t-text-sub">{vixLabel}</p>
            </div>
            {performance.kospi && (
              <div className="flex items-center gap-2 min-w-0">
                {(performance.kospi.change || 0) >= 0
                  ? <TrendingUp size={14} className="text-red-400 shrink-0" />
                  : <TrendingDown size={14} className="text-blue-400 shrink-0" />}
                <div className="min-w-0">
                  <div className="text-sm font-medium">{performance.kospi.current?.toLocaleString()}</div>
                  <div className="text-xs t-text-sub">KOSPI {performance.kospi.change != null && <span className={`${(performance.kospi.change || 0) >= 0 ? "text-red-500" : "text-blue-500"}`}>{performance.kospi.change >= 0 ? "▲" : "▼"}{Math.abs(performance.kospi.change || 0).toFixed(2)}</span>}</div>
                </div>
              </div>
            )}
            {performance.kosdaq && (
              <div className="flex items-center gap-2 min-w-0">
                {(performance.kosdaq.change || 0) >= 0
                  ? <TrendingUp size={14} className="text-red-400 shrink-0" />
                  : <TrendingDown size={14} className="text-blue-400 shrink-0" />}
                <div className="min-w-0">
                  <div className="text-sm font-medium">{performance.kosdaq.current?.toLocaleString()}</div>
                  <div className="text-xs t-text-sub">KOSDAQ {performance.kosdaq.change != null && <span className={`${(performance.kosdaq.change || 0) >= 0 ? "text-red-500" : "text-blue-500"}`}>{performance.kosdaq.change >= 0 ? "▲" : "▼"}{Math.abs(performance.kosdaq.change || 0).toFixed(2)}</span>}</div>
                </div>
              </div>
            )}
          </div>
          {/* 글로벌 매크로 */}
          {indicatorHistory?.macro && Object.keys(indicatorHistory.macro).length > 0 && (
            <div className="mt-3 pt-3 border-t t-border-light">
              <div className="text-xs font-medium t-text-sub mb-1.5">글로벌 매크로</div>
              <div className="grid grid-cols-2 gap-1.5">
                {Object.entries(indicatorHistory.macro as Record<string, any[]>).slice(0, 6).map(([symbol, history]: [string, any]) => {
                  const arr = Array.isArray(history) ? history : [];
                  const latest = arr[arr.length - 1];
                  const prev = arr[arr.length - 2];
                  if (!latest) return null;
                  const nameMap: Record<string, string> = { "NQ=F": "나스닥선물", "069500": "KODEX 200", "MU": "마이크론", "SOXX": "SOXX(반도체)", "EWY": "EWY(한국ETF)", "KORU": "KORU(한국3X)", "KOSPI200F": "코스피200선물", "^VIX": "VIX", "FNG": "F&G" };
                  return (
                    <div key={symbol} className="t-card-alt rounded-lg p-2">
                      <div className="text-[10px] t-text-dim mb-0.5">{nameMap[symbol] || symbol}</div>
                      <div className="flex items-baseline gap-1.5">
                        <span className="text-sm font-semibold t-text">{latest.price?.toLocaleString()}</span>
                        {latest.change_pct != null && (
                          <span className={`text-[10px] font-medium ${latest.change_pct >= 0 ? "text-red-500" : "text-blue-500"}`}>
                            {latest.change_pct >= 0 ? "+" : ""}{latest.change_pct}%
                          </span>
                        )}
                      </div>
                      {prev && <div className="text-[10px] t-text-dim mt-0.5">전일 {prev.price?.toLocaleString()}</div>}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 주요 선물 */}
          {performance.futures?.length > 0 && (
            <div className="mt-3 pt-3 border-t t-border-light">
              <div className="text-xs font-medium t-text-sub mb-1.5">주요 선물</div>
              <div className="grid grid-cols-3 gap-1.5">
                {performance.futures.map((ft: any, i: number) => (
                  <div key={i} className="t-card-alt rounded-lg p-2 text-center">
                    <div className="text-[10px] t-text-dim truncate">{ft.name}</div>
                    <div className="text-sm font-semibold t-text">{ft.price?.toLocaleString()}</div>
                    <div className={`text-[10px] font-medium ${(ft.change_pct || 0) >= 0 ? "text-red-500" : "text-blue-500"}`}>
                      {ft.change_pct >= 0 ? "▲" : "▼"}{Math.abs(ft.change_pct)}%
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 환율 */}
          {performance.exchange?.length > 0 && (
            <div className="mt-3 pt-3 border-t t-border-light">
              <div className="text-xs font-medium t-text-sub mb-1.5">환율</div>
              <div className="grid grid-cols-2 gap-1.5">
                {performance.exchange.slice(0, 4).map((r: any, i: number) => {
                  const label: Record<string, string> = { USD: "원/달러", JPY: "원/엔", EUR: "원/유로", CNY: "원/위안" };
                  const cur = r.currency || r.name || "";
                  return (
                    <div key={i} className="t-card-alt rounded-lg p-2">
                      <div className="text-[10px] t-text-dim mb-0.5">{label[cur] || cur}</div>
                      <div className="flex items-baseline gap-1.5">
                        <span className="text-sm font-semibold t-text">{r.rate?.toLocaleString()}</span>
                        {r.change_rate != null && (
                          <span className={`text-[10px] font-medium ${r.change_rate >= 0 ? "text-red-500" : "text-blue-500"}`}>
                            {r.change_rate >= 0 ? "+" : ""}{r.change_rate}%
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {/* 투자자 동향 + 수급 국면 — 시장 현황 내 통합 */}
          {sentiment?.components?.investor_trend?.length > 0 && (
            <div className="mt-3 pt-3 border-t t-border-light">
              <div className="flex items-center justify-between mb-1.5">
                <div className="text-xs font-medium t-text-sub">투자자 동향 (KOSPI)</div>
                {supplyCluster && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-purple-500/15 text-purple-400">{supplyCluster.regime}</span>
                  </div>
                )}
              </div>
              {supplyCluster?.strategy && (
                <div className="text-[10px] t-text-dim mb-1.5">{supplyCluster.strategy}</div>
              )}
              <div className="grid grid-cols-1 gap-1">
                {sentiment.components.investor_trend.slice(-3).reverse().map((day: any, i: number) => {
                  const k = day.kospi || day;
                  return (
                    <div key={i} className="grid grid-cols-4 text-[10px] t-card-alt rounded px-1.5 py-1.5 items-center">
                      <span className="t-text-sub">{day.date}</span>
                      <span className={`font-medium text-right ${(k.foreign || 0) >= 0 ? "text-red-500" : "text-blue-500"}`}>
                        외국인 {(k.foreign || 0) >= 0 ? "+" : ""}{((k.foreign || 0) / 100).toFixed(0)}억
                      </span>
                      <span className={`font-medium text-right ${(k.institution || 0) >= 0 ? "text-red-500" : "text-blue-500"}`}>
                        기관 {(k.institution || 0) >= 0 ? "+" : ""}{((k.institution || 0) / 100).toFixed(0)}억
                      </span>
                      <span className={`font-medium text-right ${(k.individual || 0) >= 0 ? "text-red-500" : "text-blue-500"}`}>
                        개인 {(k.individual || 0) >= 0 ? "+" : ""}{((k.individual || 0) / 100).toFixed(0)}억
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </section>
      )}

      </>}
      {/* 내 포트폴리오 — 포트폴리오 탭에서만 표시 */}
      {isPortfolioPage && (!supaUser ? (
        <section className="t-card rounded-xl p-6 text-center">
          <div className="text-3xl mb-3">📊</div>
          <div className="text-sm font-semibold t-text mb-1">내 포트폴리오</div>
          <div className="text-[12px] t-text-sub mb-4">로그인하면 보유 종목을 관리하고<br/>실시간 수익률을 확인할 수 있습니다.</div>
          <button onClick={() => setShowLogin(true)}
            className="text-sm font-medium px-6 py-2 rounded-xl bg-blue-600 text-white hover:bg-blue-500 transition">로그인</button>
        </section>
      ) : portfolio && (() => {
        const sm = portfolio.summary || {};
        const profitColor = (r: number) => r > 0 ? "text-red-500" : r < 0 ? "text-blue-500" : "t-text";
        const refreshPortfolioPrices = async () => {
          if (priceRefreshing || !portfolio?.holdings?.length) return;
          setPriceRefreshing(true);
          try {
            const codes = portfolio.holdings.map((h: any) => h.code).filter(Boolean);
            let priceMap: Record<string, number> = {};
            let source = "";
            // 1) KIS API 실시간 (로그인 시 Edge Function)
            if (supaUser && codes.length > 0) {
              try {
                const kisData = await fetchKisPrices(codes);
                for (const [code, p] of Object.entries(kisData)) {
                  if (p.current_price) priceMap[code] = p.current_price;
                }
                if (Object.keys(priceMap).length > 0) source = "KIS";
              } catch (e) {
                console.warn("KIS Edge Function 실패:", e);
              }
            }
            // 2) 폴백: 배포 데이터
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
              // 포트폴리오 재계산
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
              // 시각 표시
              const now = new Date();
              const hh = now.getHours();
              setLivePriceTime(`${hh < 12 ? "오전" : "오후"} ${hh === 0 ? 12 : hh > 12 ? hh - 12 : hh}:${now.getMinutes().toString().padStart(2,"0")}`);
            }
          } catch (e) { console.error("price refresh failed:", e); }
          finally { setPriceRefreshing(false); }
        };
        return (
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
            </div>
          </div>
          {/* 총 손익 요약 */}
          {sm.total_invested > 0 && (
            <div className="flex items-center justify-between mb-3 p-3 t-card-alt rounded-xl">
              <div>
                <div className="text-[10px] t-text-dim">총 투자금</div>
                <div className="text-sm font-semibold t-text">{(sm.total_invested || 0).toLocaleString()}원</div>
              </div>
              <div>
                <div className="text-[10px] t-text-dim">평가금</div>
                <div className="text-sm font-semibold t-text">{(sm.total_value || 0).toLocaleString()}원</div>
              </div>
              <div className="text-right">
                <div className="text-[10px] t-text-dim">총 수익률</div>
                <div className={`text-sm font-bold ${profitColor(sm.total_profit_rate || 0)}`}>
                  {(sm.total_profit_rate || 0) >= 0 ? "+" : ""}{sm.total_profit_rate || 0}%
                </div>
              </div>
            </div>
          )}
          {/* 종목별 */}
          <div className="space-y-1.5 mb-3">
            {portfolio.holdings?.map((h: any, i: number) => (
              <div key={i} className="p-2.5 t-card-alt rounded-lg">
                <div className="flex items-center justify-between">
                  <div className="min-w-0">
                    <span className="text-sm font-medium t-text">{h.name}</span>
                    <span className="text-[10px] t-text-dim ml-1">{h.code}</span>
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
            ))}
          </div>
          {/* 리밸런싱 제안 */}
          {portfolio.suggestions?.length > 0 && (
            <div className="bg-orange-500/8 border border-orange-500/15 rounded-lg p-2.5 mb-3">
              <div className="text-xs font-medium text-orange-400 mb-1">리밸런싱 제안</div>
              {portfolio.suggestions.map((s: string, i: number) => (
                <div key={i} className="text-xs t-text-sub">· {s}</div>
              ))}
            </div>
          )}
          {/* 건강도 */}
          <div className="flex items-center gap-2 text-xs t-text-dim">
            <span>건강도 {portfolio.health_score}/100</span>
            <span className={`font-medium ${portfolio.health_score >= 70 ? "text-emerald-500" : portfolio.health_score >= 50 ? "text-amber-500" : "text-red-500"}`}>
              {portfolio.health_score >= 70 ? "양호" : portfolio.health_score >= 50 ? "보통" : "개선 필요"}
            </span>
            <button onClick={() => {
              // DB holdings 우선, 없으면 portfolio.holdings 사용
              const source = dbHoldings.length > 0 ? dbHoldings : (portfolio.holdings || []);
              setEditHoldings(JSON.parse(JSON.stringify(source)));
              setShowPortfolioEdit(true);
            }}
              className="ml-auto text-[11px] px-2.5 py-1 rounded-lg border border-blue-500/30 text-blue-400 hover:bg-blue-500/10 transition font-medium">편집</button>
          </div>
        </section>
        );
      })())}
      {/* 포트폴리오 편집 모달 */}
      {showPortfolioEdit && (
        <div className="fixed inset-0 z-[60]" onClick={() => setShowPortfolioEdit(false)}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
          <div className="fixed bottom-0 left-0 right-0 z-[61] max-h-[85vh] overflow-y-auto rounded-t-2xl t-card border-t t-border-light p-5 sm:max-w-lg sm:mx-auto sm:rounded-2xl sm:bottom-auto sm:top-1/2 sm:-translate-y-1/2"
            style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 2.5rem)' }} onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold t-text">포트폴리오 편집</h3>
              <button onClick={() => setShowPortfolioEdit(false)} className="text-lg t-text-dim hover:t-text">✕</button>
            </div>
            <div className="space-y-3 mb-4">
              {editHoldings.map((h: any, i: number) => (
                <div key={i} className="p-3 t-card-alt rounded-xl">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium t-text">{h.name} <span className="text-[10px] t-text-dim">{h.code}</span></span>
                    <button onClick={() => setEditHoldings(editHoldings.filter((_: any, j: number) => j !== i))}
                      className="text-xs text-red-400 hover:text-red-300">삭제</button>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
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
                    <div>
                      <label className="text-[10px] t-text-dim block mb-0.5">섹터</label>
                      <input type="text" value={h.sector || ""} onChange={e => { const v = [...editHoldings]; v[i] = {...h, sector: e.target.value}; setEditHoldings(v); }}
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
                          setEditHoldings([...editHoldings, { name: s.name, code: s.code, sector: "", avg_price: 0, quantity: 0 }]);
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

      {!isPortfolioPage && <>
      {/* AI 주목 종목 */}
      {performance?.by_source?.combined && (() => {
        const c = performance.by_source.combined;
        const total = c.total || 0;
        const buyCount = (c["적극매수"] || 0) + (c["매수"] || 0);
        // 매수 종목: crossSignal + smartMoney에서 추출 (중복 제거, 객체 보존)
        const seen = new Set<string>();
        const strongBuyStocks: any[] = [];
        const buyStocks: any[] = [];
        (crossSignal || []).forEach((s: any) => {
          const sig = s.vision_signal || s.signal || "";
          if (sig === "적극매수" && !seen.has(s.name)) { strongBuyStocks.push(s); seen.add(s.name); }
          else if (sig === "매수" && !seen.has(s.name)) { buyStocks.push(s); seen.add(s.name); }
        });
        (smartMoney || []).forEach((s: any) => {
          if ((s.signal === "매수" || s.signal === "적극매수") && !seen.has(s.name)) { buyStocks.push(s); seen.add(s.name); }
        });
        return (
          <section className="t-card rounded-xl p-4">
            <SectionHeader id="signals" timestamp={ts}>AI 주목 종목</SectionHeader>
            <div className="text-xs t-text-sub mb-3">
              AI 분석 {total}종목 중 <span className="text-red-500 font-semibold">매수 신호 {strongBuyStocks.length + buyStocks.length}종목</span>
            </div>
            {strongBuyStocks.length > 0 && (
              <div className="mb-2">
                <div className="text-[10px] t-text-dim mb-1">적극매수</div>
                <div className="flex flex-wrap gap-1">
                  {strongBuyStocks.map((s, i) => (
                    <span key={i} onClick={() => setStockDetail(s)} className="text-xs font-medium px-2 py-0.5 rounded-full bg-red-500/15 text-red-400 cursor-pointer hover:bg-red-500/25 transition-colors">{s.name}</span>
                  ))}
                </div>
              </div>
            )}
            {buyStocks.length > 0 && (
              <div>
                <div className="text-[10px] t-text-dim mb-1">매수</div>
                <div className="flex flex-wrap gap-1">
                  {buyStocks.map((s, i) => (
                    <span key={i} onClick={() => setStockDetail(s)} className="text-xs font-medium px-2 py-0.5 rounded-full bg-red-500/10 t-text-sub cursor-pointer hover:bg-red-500/20 transition-colors">{s.name}</span>
                  ))}
                </div>
              </div>
            )}
            {buyCount === 0 && <Empty text="현재 매수 신호 종목 없음" />}
          </section>
        );
      })()}

      {/* ===== 신호 카테고리 ===== */}
      <div id="cat-signal" className="scroll-mt-24" />

      {/* 연속 시그널 추적 */}
      {consecutiveSignals && (consecutiveSignals.and_condition?.length > 0 || consecutiveSignals.or_condition?.length > 0) && (
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="consecutive" timestamp={ts}>연속 시그널</SectionHeader>
          {/* AND 조건 */}
          {consecutiveSignals.and_condition?.length > 0 && (
            <div className="mb-3">
              <div className="text-[11px] font-semibold text-red-400 mb-1.5">🔥 매수 + 대장주 동시 (AND)</div>
              <div className="space-y-1">
                {consecutiveSignals.and_condition.map((r: any, i: number) => (
                  <div key={i} className="flex items-center justify-between py-1.5 border-b t-border-light last:border-b-0">
                    <div>
                      <span className="text-[13px] font-medium t-text">{r.name}</span>
                      <span className="text-[10px] t-text-dim ml-1">{r.code}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-bold text-red-400">{r.streak}일 연속</span>
                      <span className="text-[10px] t-text-dim">{r.dates?.[r.dates.length - 1]}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {/* OR 조건 */}
          {consecutiveSignals.or_condition?.length > 0 && (
            <div>
              <div className="text-[11px] font-semibold text-amber-400 mb-1.5">📊 매수 또는 대장주 (OR)</div>
              <div className="space-y-1">
                {consecutiveSignals.or_condition.slice(0, 8).map((r: any, i: number) => (
                  <div key={i} className="flex items-center justify-between py-1.5 border-b t-border-light last:border-b-0">
                    <div>
                      <span className="text-[13px] font-medium t-text">{r.name}</span>
                      <span className="text-[10px] t-text-dim ml-1">{r.code}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-semibold text-amber-400">{r.streak}일</span>
                      <span className="text-[10px] t-text-dim">{r.total_days}일 등장</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {/* 교차 신호 */}
      {(
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="cross" timestamp={ts} count={crossSignal?.length ?? 0}>교차 신호</SectionHeader>
          <div className="space-y-2">
            {(crossSignal || []).map((s, i) => {
              const intra = s.intraday || {};
              const ageH = s.signal_age_hours || 0;
              const ageLbl = ageH >= 12 ? "매우 오래됨" : ageH >= 6 ? "오래됨" : ageH >= 3 ? "주의" : "최근";
              const ageColor = ageH >= 12 ? "text-gray-400" : ageH >= 6 ? "text-amber-400" : ageH >= 3 ? "text-yellow-400" : "text-emerald-400";
              return (
              <div key={i} onClick={() => setStockDetail(s)} className="p-2.5 t-card-alt border t-border-light rounded-lg cursor-pointer hover:border-blue-500/30 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="min-w-0 mr-2">
                    <span className="font-medium text-sm t-text">{s.name}</span>
                    <span className="text-xs t-text-dim ml-1">{s.code}</span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {s.dual_signal && (
                      <Badge variant={s.dual_signal === "고확신" ? "success" : s.dual_signal === "KIS매수" ? "blue" : s.dual_signal === "혼조" ? "warning" : "default"}>
                        {s.dual_signal}
                      </Badge>
                    )}
                  </div>
                </div>
                <div className="text-[11px] t-text-sub mt-1.5">{s.theme}</div>
                {/* Intraday Overlay */}
                <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                  {intra.change_rate != null && intra.change_rate !== 0 && (
                    <span className={`text-[11px] font-medium ${intra.change_rate >= 0 ? "text-red-400" : "text-blue-400"}`}>
                      {intra.change_rate >= 0 ? "+" : ""}{intra.change_rate}%
                    </span>
                  )}
                  {intra.validation && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                      intra.validation === "신호 유효" ? "bg-emerald-500/10 text-emerald-400" :
                      intra.validation === "신호 약화" ? "bg-amber-500/10 text-amber-400" :
                      intra.validation === "신호 무효화" ? "bg-red-500/10 text-red-400" :
                      "bg-gray-500/10 t-text-dim"
                    }`}>{intra.validation}</span>
                  )}
                  {ageH > 0 && <span className={`text-[10px] ${ageColor}`}>{Math.round(ageH)}시간 전</span>}
                </div>
              </div>
              );
            })}
          </div>
            {!crossSignal?.length && <Empty />}
        </section>
      )}

      {/* 테마 라이프사이클 */}
      {(
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="lifecycle" timestamp={ts} count={lifecycle?.length ?? 0}>테마 라이프사이클</SectionHeader>
          <div className="t-card-alt rounded-lg p-2 mb-3">
            <ResponsiveContainer width="100%" height={160}>
              <ScatterChart margin={{ top: 5, right: 5, bottom: 20, left: 0 }}>
                <XAxis dataKey="stock_count" type="number" tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={{ stroke: '#e5e7eb' }} label={{ value: '종목수', position: 'bottom', fill: '#9ca3af', fontSize: 10, offset: -5 }} />
                <YAxis dataKey="avg_change" type="number" tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={{ stroke: '#e5e7eb' }} label={{ value: '%', position: 'top', fill: '#9ca3af', fontSize: 10, offset: -5 }} />
                <Tooltip content={({ payload }) => {
                  if (!payload?.length) return null;
                  const d = payload[0].payload;
                  return (<div className="bg-white border border-gray-200 rounded-lg shadow p-2 text-xs"><div className="font-semibold">{d.theme}</div><div className="t-text-sub">{d.stage} · {d.stock_count}종목 · {d.avg_change >= 0 ? "+" : ""}{d.avg_change}%</div></div>);
                }} />
                <Scatter data={lifecycle || []}>{(lifecycle || []).map((l: any, i: number) => (<Cell key={i} fill={STAGE_FILL[l.stage] || "#6b7280"} r={Math.max(6, l.stock_count * 3)} />))}</Scatter>
              </ScatterChart>
            </ResponsiveContainer>
            <div className="flex justify-center gap-3 text-xs t-text-dim">
              {Object.entries(STAGE_DOT).map(([s, c]) => (
                <span key={s} className="flex items-center gap-1"><span className={`w-2 h-2 rounded-full ${c}`} />{s}</span>
              ))}
            </div>
          </div>
          <div className="space-y-1.5">
            {(lifecycle || []).map((l: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
                <span className="text-sm font-medium truncate min-w-0">{l.theme}</span>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs t-text-sub">{l.avg_change >= 0 ? "+" : ""}{l.avg_change}%</span>
                  <Badge variant={l.stage === "과열" ? "danger" : l.stage === "성장" ? "warning" : l.stage === "탄생" ? "success" : "default"}>{l.stage}</Badge>
                </div>
              </div>
            ))}
          </div>
            {!lifecycle?.length && <Empty />}
        </section>
      )}

      {/* 이상 거래 감지 */}
      {(
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="anomaly" timestamp={ts} count={anomalies?.length ?? 0}>이상 거래 감지</SectionHeader>
          <div className="space-y-1.5">
            {(anomalies || []).slice(0, 6).map((a, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-red-500/10 border border-red-500/20 rounded-lg gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <Zap size={14} className="text-red-400 shrink-0" />
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{a.name}</div>
                    <div className="text-xs t-text-sub">{a.type}</div>
                  </div>
                </div>
                <div className="text-right text-xs shrink-0">
                  {a.ratio && <div className="text-amber-600 font-medium">거래량 x{a.ratio}</div>}
                  {a.rsi && <div className="text-purple-600 font-medium">RSI {a.rsi}</div>}
                  {a.change_rate != null && (
                    <div className={a.change_rate >= 0 ? "text-red-600" : "text-blue-600"}>
                      등락 {a.change_rate >= 0 ? "+" : ""}{a.change_rate}%
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
            {!anomalies?.length && <Empty />}
        </section>
      )}

      {/* 위험 종목 모니터 */}
      {(
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="risk" timestamp={ts} count={riskMonitor?.length ?? 0}>위험 종목 모니터</SectionHeader>
          <div className="space-y-1.5">
            {(riskMonitor || []).slice(0, 6).map((r, i) => (
              <div key={i} className="p-2 t-card-alt rounded-lg">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Shield size={14} className={`shrink-0 ${r.level === "높음" ? "text-red-500" : "text-amber-500"}`} />
                    <span className="text-sm font-medium truncate">{r.name}</span>
                    <span className="text-xs t-text-dim shrink-0">{r.code}</span>
                  </div>
                </div>
                <div className="flex gap-1 mt-1.5 ml-6">
                  {r.warnings?.map((w: string, j: number) => (
                    <Badge key={j} variant={r.level === "높음" ? "danger" : "warning"}>{w}</Badge>
                  ))}
                </div>
              </div>
            ))}
          </div>
            {!riskMonitor?.length && <Empty />}
        </section>
      )}

      {/* 스마트 머니 TOP */}
      {(
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="smartmoney" timestamp={ts} count={smartMoney?.length ?? 0}>스마트 머니 TOP</SectionHeader>
          <div className="space-y-1.5">
            {(smartMoney || []).slice(0, 8).map((s, i) => {
              const intra = s.intraday || {};
              return (
              <div key={i} onClick={() => setStockDetail(s)} className="p-2 t-card-alt rounded-lg cursor-pointer hover:border-blue-500/20 hover:border transition-colors">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 text-[10px] font-bold flex items-center justify-center shrink-0">
                      {i + 1}
                    </div>
                    <div className="min-w-0">
                      <span className="text-sm font-medium truncate block t-text">{s.name}</span>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        {s.dual_signal && (
                          <span className={`text-[10px] ${s.dual_signal === "고확신" ? "text-emerald-500" : s.dual_signal === "KIS매수" ? "text-blue-400" : "t-text-dim"}`}>
                            {s.dual_signal}
                          </span>
                        )}
                        {intra.validation && (
                          <span className={`text-[10px] ${
                            intra.validation === "신호 유효" ? "text-emerald-400" :
                            intra.validation === "신호 약화" ? "text-amber-400" :
                            intra.validation === "신호 무효화" ? "text-red-400" : "t-text-dim"
                          }`}>{intra.validation}</span>
                        )}
                        {intra.change_rate != null && intra.change_rate !== 0 && (
                          <span className={`text-[10px] font-medium ${intra.change_rate >= 0 ? "text-red-400" : "text-blue-400"}`}>
                            {intra.change_rate >= 0 ? "+" : ""}{intra.change_rate}%
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-sm font-bold text-blue-500">{s.smart_money_score}</div>
                    <div className="text-[10px] t-text-dim">스코어</div>
                  </div>
                </div>
              </div>
              );
            })}
          </div>
            {!smartMoney?.length && <Empty />}
        </section>
      )}

      {/* 전략 시뮬레이션 */}
      {(
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="simulation" timestamp={ts}>전략 시뮬레이션</SectionHeader>
          <div className="space-y-2">
            {(simulation || []).map((s, i) => {
              const strategyLabel = (s.strategy || "")
                .replace("signal=적극매수", "적극매수 신호")
                .replace("signal=매수", "매수 신호")
                .replace(/hold=(\d+)/, "→ $1일 보유")
                .replace(/stop=(-?\d+)/, "· 손절 $1%");
              return (
                <div key={i} className="p-3 t-card-alt rounded-lg">
                  <div className="text-xs text-blue-600 font-medium mb-2 flex items-center gap-1">
                    <Activity size={12} className="shrink-0" />
                    <span className="truncate">{strategyLabel || s.strategy}</span>
                  </div>
                  {s.total_trades > 0 ? (
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div>
                        <div className="text-[10px] t-text-dim">총 거래</div>
                        <div className="text-sm font-semibold">{s.total_trades}건</div>
                      </div>
                      <div>
                        <div className="text-[10px] t-text-dim">승률</div>
                        <div className={`text-sm font-semibold ${s.win_rate >= 50 ? "text-red-600" : "text-blue-600"}`}>{s.win_rate}%</div>
                      </div>
                      <div>
                        <div className="text-[10px] t-text-dim">평균수익</div>
                        <div className={`text-sm font-semibold ${(s.returns?.mean || 0) >= 0 ? "text-red-600" : "text-blue-600"}`}>
                          {s.returns?.mean >= 0 ? "+" : ""}{s.returns?.mean?.toFixed(1)}%
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-xs t-text-dim text-center py-1">거래 데이터 축적 중</div>
                  )}
                </div>
              );
            })}
          </div>
            {!simulation?.length && <Empty />}
        </section>
      )}

      {/* 차트 패턴 매칭 */}
      {(
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="pattern" timestamp={ts}>차트 패턴 매칭</SectionHeader>
          <div className="space-y-3">
            {(pattern || []).map((p, i) => (
              <div key={i}>
                <div className="font-medium text-sm flex items-center gap-1 mb-1.5">
                  <LineChart size={14} className="t-text-dim shrink-0" />
                  <span className="truncate">{p.name}</span>
                  <span className="text-xs t-text-dim shrink-0">{p.code}</span>
                </div>
                {p.matches?.slice(0, 3).map((m: any, j: number) => (
                  <div key={j} className="flex justify-between text-xs py-1 border-b t-border-light last:border-0 gap-2">
                    <span className="t-text-sub truncate">{m.date} · 유사도 {(m.similarity * 100).toFixed(0)}%</span>
                    <span className={`shrink-0 ${m.future_return_d5 >= 0 ? "text-red-600 font-medium" : "text-blue-600 font-medium"}`}>
                      D+5 {m.future_return_d5 >= 0 ? "+" : ""}{m.future_return_d5?.toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            ))}
            <p className="text-[10px] t-text-dim">D+5 = 패턴 발생 후 5거래일 뒤 수익률</p>
          </div>
            {!pattern?.length && <Empty />}
        </section>
      )}

      {/* ===== 분석 카테고리 ===== */}
      <div id="cat-analysis" className="scroll-mt-24" />

      {/* 뉴스 임팩트 */}
      {(
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="news" timestamp={ts}>뉴스 임팩트</SectionHeader>
          <div className="space-y-3">
            {Object.entries(newsImpact || {}).filter(([cat, data]) => cat !== "generated_at" && typeof data === "object" && data?.count > 0).map(([cat, data]: [string, any]) => (
              <div key={cat} className="p-3 t-card-alt rounded-lg">
                <div className="flex justify-between items-center mb-2">
                  <Badge variant="purple">{cat}</Badge>
                  <span className="text-xs t-text-dim">{data.count}건</span>
                </div>
                {data.titles?.slice(0, 2).map((t: any, i: number) => (
                  <div key={i} className="text-xs t-text-sub mb-1 flex justify-between gap-2">
                    <span className="truncate min-w-0">{t.title}</span>
                    <span className="shrink-0 t-text-dim">{t.stock}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
            {!Object.keys(newsImpact || {}).length && <Empty />}
        </section>
      )}

      {/* 갭 분석 */}
      {(
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="gap" timestamp={ts} count={gapAnalysis?.length ?? 0}>갭 분석</SectionHeader>
          <div className="space-y-1.5">
            {(gapAnalysis || []).slice(0, 6).map((g, i) => (
              <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{g.name}</div>
                  <div className="text-xs t-text-sub">{g.direction}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className={`text-sm font-bold ${g.gap_pct >= 0 ? "text-red-600" : "text-blue-600"}`}>
                    {g.gap_pct >= 0 ? "+" : ""}{g.gap_pct}%
                  </div>
                  <div className="text-[10px] t-text-dim">메꿈 확률 {g.fill_probability}%</div>
                </div>
              </div>
            ))}
          </div>
            {!gapAnalysis?.length && <Empty />}
        </section>
      )}

      {/* 공매도 역발상 */}
      {(
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="squeeze" timestamp={ts} count={shortSqueeze?.length ?? 0}>역발상 시그널</SectionHeader>
          <div className="space-y-1.5">
            {(shortSqueeze || []).slice(0, 6).map((s, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-orange-500/10 border border-orange-500/20 rounded-lg gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{s.name}</div>
                  <div className="text-xs t-text-sub truncate">{s.overheating}</div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {signalBadge(s.signal)}
                  <div className="text-right shrink-0">
                    <div className="text-sm font-bold text-orange-600">{s.squeeze_score}</div>
                    <div className="text-[10px] t-text-dim">역발상</div>
                  </div>
                </div>
              </div>
            ))}
            <p className="text-[10px] t-text-dim">과열 경고 + 외국인 매수 전환 = 역발상 매수 기회</p>
          </div>
            {!shortSqueeze?.length && <Empty />}
        </section>
      )}

      {/* 밸류에이션 */}
      {(
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="valuation" timestamp={ts} count={valuation?.length ?? 0}>밸류에이션 스크리너</SectionHeader>
          <div className="space-y-1.5">
            {(valuation || []).slice(0, 6).map((v, i) => (
              <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{v.name}</div>
                  <div className="text-xs t-text-sub leading-relaxed">
                    <div>{v.per ? `PER ${v.per}` : v.ma_aligned ? "MA정배열" : ""}{v.pbr ? ` · PBR ${v.pbr}` : ""}{v.roe ? ` · ROE ${v.roe}%` : ""}</div>
                    {(v.opm || v.debt_ratio) && <div>{v.opm ? `영업이익률 ${v.opm}%` : ""}{v.debt_ratio ? `${v.opm ? " · " : ""}부채비율 ${v.debt_ratio}%` : ""}</div>}
                    {!v.per && v.foreign_net > 0 && <div>외국인 순매수</div>}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {signalBadge(v.signal)}
                  <div className="text-right shrink-0">
                    <div className="text-sm font-bold text-green-700">{v.value_score}</div>
                    <div className="text-[10px] t-text-dim">밸류</div>
                  </div>
                </div>
              </div>
            ))}
            <p className="text-[10px] t-text-dim">PER · PBR · ROE + 매매신호 종합 밸류 스코어</p>
          </div>
            {!valuation?.length && <Empty />}
        </section>
      )}

      {/* 거래량-가격 괴리 */}
      {(
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="divergence" timestamp={ts} count={divergence?.length ?? 0}>거래량-가격 괴리</SectionHeader>
          <div className="space-y-1.5">
            {(divergence || []).slice(0, 6).map((d, i) => (
              <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{d.name}</div>
                  <div className="text-xs t-text-sub">{d.type}</div>
                </div>
                <div className="text-right shrink-0 text-xs">
                  <div className="text-amber-600">거래량 x{(d.volume_change / 100).toFixed(1)}</div>
                  <div className={d.price_change >= 0 ? "text-red-600" : "text-blue-600"}>
                    가격 {d.price_change >= 0 ? "+" : ""}{d.price_change}%
                  </div>
                </div>
              </div>
            ))}
            <p className="text-[10px] t-text-dim">거래량과 가격의 방향이 다르면 추세 전환 가능성</p>
          </div>
            {!divergence?.length && <Empty />}
        </section>
      )}

      {/* 테마별 자금 흐름 */}
      {(
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="sector" timestamp={ts}>테마별 자금 흐름</SectionHeader>
          <div className="space-y-1.5">
            {Object.entries(sectors || {})
              .sort(([, a]: any, [, b]: any) => (b.total_foreign_net || 0) - (a.total_foreign_net || 0))
              .map(([name, data]: [string, any]) => {
                const net = data.total_foreign_net || 0;
                const isPos = net >= 0;
                return (
                  <div key={name} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
                    <div className="min-w-0">
                      <span className="text-sm font-medium truncate block">{name}</span>
                      <span className="text-xs t-text-dim">{data.stock_count}종목</span>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      {isPos ? <TrendingUp size={14} className="text-red-500" /> : <TrendingDown size={14} className="text-blue-500" />}
                      <span className={`text-sm font-medium ${isPos ? "text-red-600" : "text-blue-600"}`}>
                        {isPos ? "+" : ""}{(net / 1000).toFixed(0)}천주
                      </span>
                    </div>
                  </div>
                );
              })}
          </div>
            {!Object.keys(sectors || {}).length && <Empty />}
        </section>
      )}

      {/* 테마 전이 예측 */}
      {(
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="propagation" timestamp={ts} count={propagation?.length ?? 0}>테마 전이 예측</SectionHeader>
          <div className="space-y-2">
            {(propagation || []).map((p, i) => (
              <div key={i} className="p-2.5 bg-violet-500/10 border border-violet-500/20 rounded-lg">
                <div className="text-sm font-medium t-text mb-1">{p.theme}</div>
                <div className="text-xs t-text-sub">
                  <span className="text-violet-600 font-medium">{p.leader}</span>
                  <span className="t-text-dim mx-1">→</span>
                  {p.followers?.join(", ")}
                </div>
                <div className="text-[10px] t-text-dim mt-1">예상 전이 시간: ~{p.lag_minutes}분</div>
              </div>
            ))}
          </div>
            {!propagation?.length && <Empty />}
        </section>
      )}

      {/* ===== 전략 카테고리 ===== */}
      <div id="cat-strategy" className="scroll-mt-24" />

      {/* 손절/익절 최적화 */}
      {(
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="exit" timestamp={ts} count={exitOptimizer?.length ?? 0}>손절/익절 최적화</SectionHeader>
          <div className="space-y-1.5">
            {(exitOptimizer || []).slice(0, 6).map((e, i) => (
              <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{e.name}</div>
                  <div className="text-xs t-text-sub">{e.signal}</div>
                </div>
                <div className="flex gap-3 shrink-0 text-xs">
                  <div className="text-center">
                    <div className="text-blue-600 font-medium">{e.stop_loss}%</div>
                    <div className="text-[10px] t-text-dim">손절</div>
                  </div>
                  <div className="text-center">
                    <div className="text-red-600 font-medium">+{e.take_profit}%</div>
                    <div className="text-[10px] t-text-dim">익절</div>
                  </div>
                  <div className="text-center">
                    <div className="text-amber-600 font-medium">{e.trailing_stop}%</div>
                    <div className="text-[10px] t-text-dim">추적</div>
                  </div>
                </div>
              </div>
            ))}
            <p className="text-[10px] t-text-dim">추적 = 최고점 대비 하락 시 자동 매도 기준</p>
          </div>
            {!exitOptimizer?.length && <Empty />}
        </section>
      )}

      {/* 이벤트 캘린더 */}
      {(
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="events" timestamp={ts} count={eventCalendar?.events?.length ?? 0}>이벤트 캘린더</SectionHeader>
          <div className="space-y-1.5">
            {(eventCalendar?.events || []).map((ev: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium">{ev.name}</div>
                  <div className="text-xs t-text-sub">{ev.date}</div>
                </div>
                <Badge variant={ev.impact === "high" ? "danger" : ev.impact === "medium" ? "warning" : "default"}>
                  {ev.impact === "high" ? "고영향" : ev.impact === "medium" ? "중영향" : "저영향"}
                </Badge>
              </div>
            ))}
          </div>
            {!(eventCalendar?.events || []).length && <Empty />}
        </section>
      )}

      {/* 프로그램 매매 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="program" timestamp={ts}>프로그램 매매</SectionHeader>
        {programTrading?.data ? (
          <div className="space-y-1.5">
            {(programTrading.data.kospi || []).slice(0, 5).map((p: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
                <span className="text-sm t-text">{p.investor}</span>
                <div className="flex gap-3 text-xs shrink-0">
                  <span className={`font-medium ${p.all_ntby_amt >= 0 ? "text-red-600" : "text-blue-600"}`}>
                    {p.all_ntby_amt >= 0 ? "+" : ""}{(p.all_ntby_amt / 100).toFixed(0)}억
                  </span>
                </div>
              </div>
            ))}
            {/* 종목별 프로그램 매매 */}
            {programTrading.by_stock?.length > 0 && (
              <div className="mt-2 pt-2 border-t t-border-light">
                <div className="text-xs font-medium t-text-sub mb-1.5">종목별 프로그램 순매수</div>
                {programTrading.by_stock.slice(0, 5).map((ps: any, i: number) => (
                  <div key={i} className="flex items-center justify-between text-xs py-1">
                    <span className="t-text truncate">{ps.name}</span>
                    <span className={`font-medium ${ps.program_net >= 0 ? "text-red-600" : "text-blue-600"}`}>
                      {ps.program_net >= 0 ? "+" : ""}{(ps.program_net / 1000).toFixed(0)}천주
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : <Empty />}
      </section>

      {/* 시간대별 수익률 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="heatmap" timestamp={ts}>시간대별 수익률</SectionHeader>
        {heatmap?.snapshots?.length ? (
          <div className="space-y-1.5">
            {heatmap.snapshots.map((snap: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
                <div className="text-xs t-text-sub">{snap.time}</div>
                <div className="flex gap-3 text-xs">
                  <span className={`font-medium ${(snap.foreign || 0) >= 0 ? "text-red-600" : "text-blue-600"}`}>
                    외국인 {snap.foreign >= 0 ? "+" : ""}{(snap.foreign / 100000000).toFixed(1)}억
                  </span>
                  <span className={`font-medium ${(snap.institution || 0) >= 0 ? "text-red-600" : "text-blue-600"}`}>
                    기관 {snap.institution >= 0 ? "+" : ""}{(snap.institution / 100000000).toFixed(1)}억
                  </span>
                </div>
              </div>
            ))}
            <p className="text-[10px] t-text-dim">장중 시간대별 외국인·기관 순매매 추이</p>
          </div>
        ) : heatmap?.hours ? (
          <div className="grid grid-cols-7 gap-1">
            {Object.entries(heatmap.hours).map(([hour, ret]: [string, any]) => (
              <div key={hour} className={`text-center p-2 rounded-lg ${ret >= 0.5 ? "bg-red-500/10" : ret >= 0 ? "t-card-alt" : "bg-blue-500/10"}`}>
                <div className="text-[10px] t-text-dim">{hour}시</div>
                <div className={`text-xs font-medium ${ret >= 0.5 ? "text-red-600" : ret >= 0 ? "t-text-sub" : "text-blue-600"}`}>
                  {ret >= 0 ? "+" : ""}{ret}%
                </div>
              </div>
            ))}
          </div>
        ) : <Empty />}
        {!heatmap?.snapshots?.length && <p className="text-[10px] t-text-dim mt-2">시간대별 평균 수익률 (양수=상승 경향, 음수=하락 경향)</p>}
      </section>

      {/* 내부자 거래 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="insider" timestamp={ts} count={insiderTrades?.length ?? 0}>내부자 거래</SectionHeader>
        <div className="space-y-1.5">
          {(insiderTrades || []).map((t, i) => (
            <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{t.name || t.corp_name}</div>
                <div className="text-xs t-text-sub">{t.executive} · {t.position}</div>
              </div>
              <div className="text-right shrink-0">
                <div className={`text-xs font-medium ${t.type === "매수" ? "text-red-600" : "text-blue-600"}`}>{t.type} {t.shares?.toLocaleString()}주</div>
                <div className="text-[10px] t-text-dim">{t.date}</div>
              </div>
            </div>
          ))}
        </div>
        {!insiderTrades?.length && <Empty />}
      </section>

      {/* 컨센서스 괴리 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="consensus" timestamp={ts} count={consensus?.length ?? 0}>컨센서스 괴리</SectionHeader>
        <div className="space-y-1.5">
          {(consensus || []).map((c, i) => (
            <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{c.name}</div>
                <div className="text-xs t-text-sub">
                  {c.current_price > 0 ? `현재가 ${c.current_price?.toLocaleString()}원` : "매수 신호 종목"}
                </div>
              </div>
              <div className="text-right shrink-0">
                {c.target_price > 0 ? (
                  <>
                    <div className="text-xs font-medium text-amber-600">목표 {c.target_price?.toLocaleString()}원</div>
                    <div className={`text-[10px] ${c.gap_pct >= 0 ? "text-red-500" : "text-blue-500"}`}>
                      괴리 {c.gap_pct >= 0 ? "+" : ""}{c.gap_pct}%
                    </div>
                  </>
                ) : (
                  <div className="text-xs t-text-dim">목표가 수집 중</div>
                )}
              </div>
            </div>
          ))}
        </div>
        {!consensus?.length && <Empty />}
      </section>

      {/* 동시호가 분석 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="auction" timestamp={ts} count={auction?.length ?? 0}>동시호가 분석</SectionHeader>
        <div className="space-y-1.5">
          {(auction || []).map((a, i) => (
            <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{a.name}</div>
                <div className="text-xs t-text-sub">{a.session === "opening" ? "시가" : "종가"} 동시호가</div>
              </div>
              <div className="text-right shrink-0">
                <div className={`text-xs font-medium ${a.pressure === "매수우위" ? "text-red-600" : "text-blue-600"}`}>{a.pressure}</div>
                <div className="text-[10px] t-text-dim">비율 {a.ratio}</div>
              </div>
            </div>
          ))}
        </div>
        {!auction?.length && <Empty />}
        <p className="text-[10px] t-text-dim mt-1">장중 실시간 호가 기반 · 휴장 시 최근 데이터</p>
      </section>

      {/* 호가창 압력 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="orderbook" timestamp={ts} count={orderbook?.length ?? 0}>호가창 압력</SectionHeader>
        <div className="space-y-1.5">
          {(orderbook || []).map((o, i) => {
            const buyPct = o.bid_volume && o.ask_volume ? Math.round(o.bid_volume / (o.bid_volume + o.ask_volume) * 100) : (o.buy_pct || 50);
            return (
              <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{o.name}</div>
                  {(o.bid_volume != null || o.ask_volume != null) && (
                    <div className="text-xs t-text-sub">
                      매수 {o.bid_volume?.toLocaleString()}주 · 매도 {o.ask_volume?.toLocaleString()}주
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <div className="w-16 h-2 t-muted rounded-full overflow-hidden flex">
                    <div className="bg-red-400 h-full" style={{width: `${buyPct}%`}} />
                    <div className="bg-blue-400 h-full" style={{width: `${100 - buyPct}%`}} />
                  </div>
                  <span className={`text-xs font-medium ${buyPct > 50 ? "text-red-600" : "text-blue-600"}`}>
                    {buyPct > 50 ? "매수" : "매도"}우위 {buyPct}%
                  </span>
                </div>
              </div>
            );
          })}
        </div>
        {!orderbook?.length && <Empty />}
      </section>

      {/* 상관관계 네트워크 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="correlation" timestamp={ts}>상관관계 네트워크</SectionHeader>
        {correlationData?.pairs?.length ? (
          <div className="space-y-1.5">
            {correlationData.pairs.map((p: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
                <div className="text-sm min-w-0">
                  <span className="font-medium">{p.stock_a}</span>
                  <span className="t-text-dim mx-1">↔</span>
                  <span className="font-medium">{p.stock_b}</span>
                </div>
                <div className="shrink-0">
                  <div className={`w-12 h-2 t-muted rounded-full overflow-hidden`}>
                    <div className={`h-full rounded-full ${p.correlation > 0.7 ? "bg-red-400" : p.correlation > 0.3 ? "bg-amber-400" : "bg-green-400"}`} style={{width: `${Math.abs(p.correlation) * 100}%`}} />
                  </div>
                  <div className="text-[10px] t-text-sub text-right">{p.correlation?.toFixed(2)} {Math.abs(p.correlation) > 0.7 ? "높음" : Math.abs(p.correlation) > 0.3 ? "보통" : "낮음"}</div>
                </div>
              </div>
            ))}
            <p className="text-[10px] t-text-dim">0.7 이상 = 높은 상관 (분산 효과 낮음)</p>
          </div>
        ) : <Empty />}
      </section>

      {/* 실적 프리뷰 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="earnings" timestamp={ts} count={earningsCalendar?.items?.length ?? 0}>실적 프리뷰</SectionHeader>
        <div className="space-y-1.5">
          {(earningsCalendar?.items || []).slice(0, 6).map((e: any, i: number) => (
            <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{e.corp_name || e.name}</div>
                <div className="text-xs t-text-sub">{e.report_type || "실적 공시"}</div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-xs t-text">{e.date}</div>
              </div>
            </div>
          ))}
        </div>
        {!(earningsCalendar?.items || []).length && <Empty />}
      </section>

      {/* AI 투자 멘토 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="mentor" timestamp={ts}>AI 투자 멘토</SectionHeader>
        {aiMentor?.advice?.length ? (
          <div className="space-y-2">
            {aiMentor.advice.map((a: any, i: number) => (
              <div key={i} className="p-2.5 bg-indigo-500/10 border border-indigo-500/20 rounded-lg">
                <div className="text-xs font-medium text-indigo-700 mb-1">{a.category}</div>
                <div className="text-sm t-text">{a.message}</div>
              </div>
            ))}
          </div>
        ) : <Empty />}
      </section>

      {/* 증권사 매매 동향 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="member" timestamp={ts} count={memberTrading?.length ?? 0}>증권사 매매 동향</SectionHeader>
        <div className="space-y-1.5">
          {(memberTrading || []).slice(0, 6).map((m, i) => (
            <div key={i} className="p-2 t-card-alt rounded-lg">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium truncate">{m.name}</span>
                <span className={`text-xs font-medium ${(m.foreign_net || 0) >= 0 ? "text-red-600" : "text-blue-600"}`}>
                  외국인 {m.foreign_net >= 0 ? "+" : ""}{(m.foreign_net / 1000).toFixed(0)}천주
                </span>
              </div>
              <div className="text-xs t-text-sub truncate">
                매수: {m.buy_top5?.map((b: any) => typeof b === "string" ? b : b?.name || b?.member || "").filter(Boolean).join(", ") || "-"}
              </div>
            </div>
          ))}
        </div>
        {!memberTrading?.length && <Empty />}
      </section>

      {/* 거래대금 TOP */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="trading_value" timestamp={ts} count={tradingValue?.length ?? 0}>거래대금 TOP</SectionHeader>
        <div className="space-y-1.5">
          {(tradingValue || []).slice(0, 10).map((tv, i) => (
            <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-5 h-5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-bold flex items-center justify-center shrink-0">
                  {i + 1}
                </div>
                <span className="text-sm font-medium truncate">{tv.name}</span>
              </div>
              <div className="text-right shrink-0 text-xs">
                <div className={`font-medium ${(tv.change_rate || 0) >= 0 ? "text-red-600" : "text-blue-600"}`}>
                  {(tv.change_rate || 0) >= 0 ? "+" : ""}{tv.change_rate}%
                </div>
                {tv.trading_value && <div className="t-text-dim">거래대금 {(tv.trading_value / 100000000).toFixed(0)}억원</div>}
              </div>
            </div>
          ))}
        </div>
        {!tradingValue?.length && <Empty />}
      </section>

      {/* 모의투자 현황 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="paper_trading" timestamp={ts}>모의투자 현황</SectionHeader>
        {paperTrading?.stocks?.length ? (
          <div className="space-y-1.5">
            <div className="text-xs t-text-sub mb-2">날짜: {paperTrading.date}</div>
            {paperTrading.stocks.slice(0, 6).map((s: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
                <span className="text-sm font-medium truncate">{s.name || s.code}</span>
                <div className="text-right shrink-0 text-xs">
                  {s.return_pct != null && (
                    <span className={`font-medium ${s.return_pct >= 0 ? "text-red-600" : "text-blue-600"}`}>
                      {s.return_pct >= 0 ? "+" : ""}{s.return_pct}%
                    </span>
                  )}
                </div>
              </div>
            ))}
            {paperTrading.summary && (
              <div className="text-xs t-text-sub mt-2 bg-blue-500/10 rounded p-2">
                총 수익률: {paperTrading.summary.total_return ?? "-"}%
              </div>
            )}
          </div>
        ) : <Empty />}
      </section>

      {/* 예측 적중률 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="forecast" timestamp={ts}>예측 적중률</SectionHeader>
        {forecastAccuracy?.overall_accuracy != null && (
          <div className="flex items-center gap-3 mb-3">
            <div className="text-2xl font-bold t-text">{forecastAccuracy.overall_accuracy}%</div>
            <div className="text-xs t-text-sub">
              전체 적중률 ({forecastAccuracy.total_hits}/{forecastAccuracy.total_predictions})
            </div>
          </div>
        )}
        <div className="space-y-1.5">
          {(forecastAccuracy?.predictions || []).map((fc: any, i: number) => (
            <div key={i} className="p-2 t-card-alt rounded-lg">
              <div className="flex justify-between text-xs t-text-sub mb-1">
                <span>{fc.date}</span>
                <span>{fc.hit_count}/{fc.total} 적중</span>
              </div>
              <div className="flex flex-wrap gap-1">
                {(fc.themes || []).map((t: string, j: number) => (
                  <Badge key={j} variant={fc.hits?.[j] ? "success" : "default"}>
                    {fc.hits?.[j] ? "✓ " : ""}{t}
                  </Badge>
                ))}
              </div>
            </div>
          ))}
        </div>
        {!(forecastAccuracy?.predictions || []).length && <Empty />}
      </section>

      {/* Volume Profile 지지/저항 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="volume_profile" timestamp={ts} count={volumeProfile?.length ?? 0}>매물대 지지/저항</SectionHeader>
        <div className="space-y-1.5">
          {(volumeProfile || []).slice(0, 8).map((vp, i) => (
            <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{vp.name}</div>
              </div>
              <div className="flex gap-2 text-xs shrink-0">
                {vp.poc_1week ? <div className="text-center"><div className="t-text-dim">1주 POC</div><div className="font-medium">{vp.poc_1week?.toLocaleString()}원</div></div> : null}
                {vp.poc_1month ? <div className="text-center"><div className="t-text-dim">1개월 POC</div><div className="font-medium">{vp.poc_1month?.toLocaleString()}원</div></div> : null}
                {vp.poc_3month ? <div className="text-center"><div className="t-text-dim">3개월 POC</div><div className="font-medium">{vp.poc_3month?.toLocaleString()}원</div></div> : null}
              </div>
            </div>
          ))}
          <p className="text-[10px] t-text-dim">POC = 가장 많이 거래된 핵심 가격대 (지지/저항선)</p>
        </div>
        {!volumeProfile?.length && <Empty />}
      </section>

      {/* 신호 일관성 추적 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="consistency" timestamp={ts} count={signalConsistency?.length ?? 0}>신호 일관성</SectionHeader>
        <div className="space-y-1.5">
          {(signalConsistency || []).slice(0, 8).map((sc, i) => (
            <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{sc.name}</div>
                <div className="text-xs t-text-sub">
                  {sc.signals?.join(" → ")} ({sc.days}일)
                </div>
              </div>
              <Badge variant={sc.consistency === "일관" ? "success" : sc.consistency === "변동" ? "danger" : "warning"}>
                {sc.consistency === "일관" ? `${sc.days}일 연속` : sc.consistency === "변동" ? "신호 불안정" : "부분 일치"}
              </Badge>
            </div>
          ))}
          <p className="text-[10px] t-text-dim">연속 동일 신호 = 높은 신뢰도 · 잦은 변동 = 주의</p>
        </div>
        {!signalConsistency?.length && <Empty />}
      </section>

      {/* ===== 시스템 카테고리 ===== */}
      <div id="cat-system" className="scroll-mt-24" />

      {/* 시뮬레이션 히스토리 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="sim_history" timestamp={ts} count={simulationHistory?.length ?? 0}>시뮬레이션 히스토리</SectionHeader>
        <div className="space-y-1.5">
          {(simulationHistory || []).map((sh, i) => (
            <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
              <div className="text-xs t-text-sub">{sh.date}</div>
              <div className="flex gap-3 text-xs shrink-0">
                <div className="text-center">
                  <div className="t-text-dim">거래수</div>
                  <div className="font-medium">{sh.total_trades}</div>
                </div>
                <div className="text-center">
                  <div className="t-text-dim">승률</div>
                  <div className={`font-medium ${(sh.win_rate || 0) >= 50 ? "text-red-600" : "text-blue-600"}`}>{sh.win_rate}%</div>
                </div>
                <div className="text-center">
                  <div className="t-text-dim">수익</div>
                  <div className={`font-medium ${(sh.avg_return || 0) >= 0 ? "text-red-600" : "text-blue-600"}`}>
                    {(sh.avg_return || 0) >= 0 ? "+" : ""}{sh.avg_return?.toFixed(1)}%
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
        {!simulationHistory?.length && <Empty />}
      </section>

      {/* 장중 종목별 수급 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="intraday_flow" timestamp={ts} count={intradayStockFlow?.length ?? 0}>장중 종목별 수급</SectionHeader>
        <div className="space-y-1.5">
          {(intradayStockFlow || []).slice(0, 10).map((isf, i) => (
            <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{isf.name || isf.code}</div>
                <div className="text-xs t-text-sub">
                  {isf.name ? isf.code : ""}
                  {isf.current_price > 0 && <span className="ml-1">{isf.current_price?.toLocaleString()}원</span>}
                  {isf.change_rate != null && (
                    <span className={`ml-1 ${(isf.change_rate || 0) >= 0 ? "text-red-500" : "text-blue-500"}`}>
                      {isf.change_rate >= 0 ? "+" : ""}{isf.change_rate}%
                    </span>
                  )}
                </div>
              </div>
              <div className="flex gap-2 text-xs shrink-0">
                <div className={`text-center ${(isf.foreign || 0) >= 0 ? "text-red-600" : "text-blue-600"}`}>
                  <div className="t-text-dim">외국인</div>
                  <div className="font-medium">{isf.foreign >= 0 ? "+" : ""}{Math.abs(isf.foreign) >= 10000 ? `${(isf.foreign / 10000).toFixed(0)}만주` : `${isf.foreign?.toLocaleString()}주`}</div>
                </div>
                <div className={`text-center ${(isf.institution || 0) >= 0 ? "text-red-600" : "text-blue-600"}`}>
                  <div className="t-text-dim">기관</div>
                  <div className="font-medium">{isf.institution >= 0 ? "+" : ""}{Math.abs(isf.institution) >= 10000 ? `${(isf.institution / 10000).toFixed(0)}만주` : `${isf.institution?.toLocaleString()}주`}</div>
                </div>
              </div>
            </div>
          ))}
          <p className="text-[10px] t-text-dim">최근 장중 가집계 시점 기준 종목별 투자자 동향</p>
        </div>
        {!intradayStockFlow?.length && <Empty />}
      </section>

      {/* 매매 일지 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="journal" timestamp={ts} count={tradingJournal?.entries?.length ?? 0}>매매 일지</SectionHeader>
        <div className="space-y-1.5">
          {(tradingJournal?.entries || []).map((e: any, i: number) => (
            <div key={i} className="p-2.5 t-card-alt rounded-lg">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium">{e.name}</span>
                <Badge variant={e.action === "매수" ? "danger" : "blue"}>{e.action}</Badge>
              </div>
              <div className="text-xs t-text-sub">{e.date} · {e.reason}</div>
            </div>
          ))}
        </div>
        {!(tradingJournal?.entries || []).length && <Empty />}
      </section>

      {/* 최상단 이동 플로팅 버튼 */}
      {showScrollTop && (
        <button
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          className="fixed right-4 z-40 w-10 h-10 flex items-center justify-center rounded-full bg-gray-500/40 backdrop-blur-md text-white hover:bg-gray-500/60 transition-all duration-200"
          style={{ bottom: 'calc(env(safe-area-inset-bottom, 0px) + 60px)' }}
          aria-label="최상단으로 이동"
        >
          <ChevronUp size={20} />
        </button>
      )}
      </>}
      {/* 카테고리 퀵 점프 — 하단 고정 (최상위 레벨, 대시보드만) */}
      {!isPortfolioPage && <>
      <div className="fixed bottom-0 left-0 right-0 z-20 px-3" style={{ background: 'var(--bg-nav)', borderTop: '1px solid var(--border)', paddingBottom: 'env(safe-area-inset-bottom, 8px)' }}>
        <div className="flex gap-1 rounded-xl p-1 max-w-2xl mx-auto">
          {categories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => {
                setActiveCategory(cat.id);
                document.getElementById(cat.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
              }}
              className="flex-1 flex items-center justify-center gap-1 py-2 text-xs font-medium rounded-lg transition-all duration-200"
              style={activeCategory === cat.id
                ? { background: 'var(--bg-pill-active)', color: 'var(--text-pill-active)', boxShadow: 'var(--shadow-card)' }
                : { color: 'var(--text-tertiary)' }}
            >
              <span className="text-[10px]">{cat.icon}</span>
              {cat.label}
            </button>
          ))}
        </div>
      </div>
      </>}
    </div>
  );
}
