import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation, Outlet } from "react-router-dom";
import {
  TrendingUp, TrendingDown,
  BarChart3, Zap, LineChart, ChevronUp, Sun, Moon, X,
  Target, Search as SearchIcon, Bot, Circle,
} from "lucide-react";
import { dataService } from "../services/dataService";
import { SectionHeader } from "../components/HelpDialog";
import RefreshButtons from "../components/RefreshButtons";
import BriefingSection from "../components/dashboard/BriefingSection";
import FocusedStockSection from "../components/dashboard/FocusedStockSection";
import ConsecutiveSignalSection from "../components/dashboard/ConsecutiveSignalSection";
import LifecycleSection from "../components/dashboard/LifecycleSection";
import RiskMonitorSection from "../components/dashboard/RiskMonitorSection";
import SimulationSection from "../components/dashboard/SimulationSection";
import { supabase, getAlertMode, setAlertMode, setAccessToken, STORAGE_KEY } from "../lib/supabase";
import type { AlertMode } from "../lib/supabase";

function Gauge({ value, max, label, color }: { value: number; max: number; label: string; color: string }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div>
      <div className="flex justify-between text-xs mb-1.5">
        <span className="t-text-sub">{label}</span>
        <span className="font-semibold t-text tabular-nums">{value}</span>
      </div>
      <div className="relative h-2 rounded-full overflow-hidden" style={{ background: 'var(--bg-muted)' }}>
        <div className={`h-full rounded-full ${color} transition-all duration-500`} style={{ width: `${pct}%` }} />
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

export default function Dashboard({ onToggleTheme, isDark }: { onToggleTheme?: () => void; isDark?: boolean }) {
  const location = useLocation();
  const isIndexRoute = location.pathname === "/";
  const [performance, setPerformance] = useState<any>(null);
  const [sectors, setSectors] = useState<Record<string, any> | null>(null);
  const [anomalies, setAnomalies] = useState<any[] | null>(null);
  const [smartMoney, setSmartMoney] = useState<any[] | null>(null);
  const [crossSignal, setCrossSignal] = useState<any[] | null>(null);
  const [stockDetail, setStockDetail] = useState<any>(null);
  const [showDualExp, setShowDualExp] = useState(false);
  const [showMacroHelp, setShowMacroHelp] = useState(false);
  const [showStockSearch, setShowStockSearch] = useState(false);
  const [globalSearchQuery, setGlobalSearchQuery] = useState("");
  const [confExp, setConfExp] = useState<{ theme: string; confidence: string; catalyst?: string } | null>(null);
  const [headerRefreshing, setHeaderRefreshing] = useState(false);
  const [allStockList, setAllStockList] = useState<any[]>([]);
  const [supaUser, setSupaUser] = useState<any>(null);
  const [showLogin, setShowLogin] = useState(false);
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPw, setLoginPw] = useState("");
  const [loginError, setLoginError] = useState("");
  const [alertMode, setAlertModeState] = useState<AlertMode>("all");
  const [showHeaderMenu, setShowHeaderMenu] = useState(false);
  const [toastMsg, setToastMsg] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [settingsResult, setSettingsResult] = useState("");
  const [pendingAlertMode, setPendingAlertMode] = useState<AlertMode | null>(null);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [streakPopup, setStreakPopup] = useState<{ name: string; dates: string[] } | null>(null);
  const [lifecyclePopup, setLifecyclePopup] = useState<{ theme: string; stocks: string[]; stage: string; strategy?: string } | null>(null);
  const [badgePopup, setBadgePopup] = useState<{ label: string; desc: string; x: number; y: number } | null>(null);
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
  const [tradingValue, setTradingValue] = useState<any[] | null>(null);
  const [forecastAccuracy, setForecastAccuracy] = useState<any>(null);
  const [volumeProfile, setVolumeProfile] = useState<any[] | null>(null);
  const [signalConsistency, setSignalConsistency] = useState<any[] | null>(null);
  const [intradayStockFlow, setIntradayStockFlow] = useState<any[] | null>(null);
  const [indicatorHistory, setIndicatorHistory] = useState<any>(null);
  const [consecutiveSignals, setConsecutiveSignals] = useState<any>(null);
  const [forecastExpanded, setForecastExpanded] = useState<Set<string>>(new Set());

  // 모달/bottom sheet 열림 시 body 스크롤 잠금
  const anyModalOpen = !!(stockDetail || showLogin || showSettings || confExp || streakPopup || lifecyclePopup || badgePopup || showStockSearch);
  useEffect(() => {
    document.body.style.overflow = anyModalOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [anyModalOpen]);

  const loadAllData = (showToast = false) => {
    const promises = [
      dataService.getPerformance().then(setPerformance),
      dataService.getSectorFlow().then(setSectors),
      dataService.getAnomalies().then(setAnomalies),
      dataService.getSmartMoney().then(setSmartMoney),
      dataService.getCrossSignal().then(setCrossSignal),
      dataService.getLifecycle().then(setLifecycle),
      dataService.getRiskMonitor().then(setRiskMonitor),
      dataService.getNewsImpact().then(setNewsImpact),
      dataService.getBriefing().then(setBriefing),
      dataService.getSimulation().then(setSimulation),
      dataService.getPattern().then(setPattern),
      dataService.getSentiment().then(setSentiment),
      dataService.getShortSqueeze().then(setShortSqueeze),
      dataService.getGapAnalysis().then(setGapAnalysis),
      dataService.getValuation().then(setValuation),
      dataService.getVolumeDivergence().then(setDivergence),
      dataService.getPremarket().then(setPremarket),
      dataService.getSupplyCluster().then(setSupplyCluster),
      dataService.getExitOptimizer().then(setExitOptimizer),
      dataService.getEventCalendar().then(setEventCalendar),
      dataService.getThemePropagation().then(setPropagation),
      dataService.getProgramTrading().then(setProgramTrading),
      dataService.getIntradayHeatmap().then(setHeatmap),
      dataService.getInsiderTrades().then(setInsiderTrades),
      dataService.getConsensus().then(setConsensus),
      dataService.getAuction().then(setAuction),
      dataService.getOrderbook().then(setOrderbook),
      dataService.getTradingValue().then(setTradingValue),
      dataService.getForecastAccuracy().then(setForecastAccuracy),
      fetch(import.meta.env.BASE_URL + "data/volume_profile_alerts.json").then(r => r.ok ? r.json() : null).then(d => { if (d?.length) setVolumeProfile(d); else dataService.getVolumeProfile().then(setVolumeProfile); }).catch(() => dataService.getVolumeProfile().then(setVolumeProfile)),
      dataService.getSignalConsistency().then(setSignalConsistency),
      dataService.getIntradayStockFlow().then(setIntradayStockFlow),
      dataService.getStockMaster().then((m: any) => { if (m?.stocks) setAllStockList(m.stocks.map((s: any) => ({ code: s.code, name: s.name, market: s.market || "" }))); }),
      dataService.getIndicatorHistory().then(setIndicatorHistory),
      dataService.getConsecutiveSignals().then(setConsecutiveSignals),
    ];
    if (showToast) {
      Promise.allSettled(promises).then((results) => {
        const failed = results.filter((r) => r.status === "rejected").length;
        if (failed === 0) {
          setToastMsg("데이터 새로고침 완료");
        } else {
          setToastMsg(`새로고침 일부 실패 (${failed}/${results.length})`);
        }
        setTimeout(() => setToastMsg(""), 2500);
      });
    }
  };

  useEffect(() => {
    loadAllData();
    // 즉시 localStorage에서 세션 복원 (SDK 초기화/navigator.locks 대기 없음)
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const raw = JSON.parse(stored);
        // ExpireStorage 래핑 형식 처리
        const sessionStr = (raw?.value && raw?.__expire__) ? raw.value : stored;
        const parsed = typeof sessionStr === "string" ? JSON.parse(sessionStr) : raw;
        if (parsed?.user) {
          setSupaUser(parsed.user);
          setAccessToken(parsed.access_token ?? null);
          getAlertMode().then(setAlertModeState).catch(() => {});
        }
      }
    } catch { /* 파싱 실패 */ }
    // 세션 복원 실패 시 로그인 모달 표시
    if (!localStorage.getItem(STORAGE_KEY)) setShowLogin(true);

    const authed = { current: false };
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
      if (event === "SIGNED_IN" || event === "TOKEN_REFRESHED") authed.current = true;
      // SIGNED_OUT 무시 — 명시적 로그아웃에서 직접 상태 정리
      if (event === "SIGNED_OUT") return;
      // 인증 상태에서 null session 무시
      if (authed.current && !session?.user) return;
      if (session?.user) {
        setSupaUser(session.user);
        setAccessToken(session.access_token ?? null);
      }
      // session이 null이지만 SIGNED_OUT이 아닌 경우 → 기존 상태 유지
    });
    // 앱 복귀 시 세션 갱신 (백그라운드에서 access_token 만료 대응, 5초 타임아웃)
    const handleVisibility = () => {
      if (document.visibilityState !== "visible") return;
      const timeout = new Promise<null>((resolve) => setTimeout(() => resolve(null), 5000));
      Promise.race([
        supabase.auth.getSession().then(({ data: { session } }) => session),
        timeout,
      ]).then((session) => {
        if (session?.user) {
          setSupaUser(session.user);
          setAccessToken(session.access_token ?? null);
          getAlertMode().then(setAlertModeState).catch(() => {});
        } else {
          // 타임아웃 또는 세션 없음 — localStorage에서 재시도
          try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored) {
              const raw = JSON.parse(stored);
              const sessionStr = (raw?.value && raw?.__expire__) ? raw.value : stored;
              const parsed = typeof sessionStr === "string" ? JSON.parse(sessionStr) : raw;
              if (parsed?.user) {
                setSupaUser(parsed.user);
                setAccessToken(parsed.access_token ?? null);
              }
            }
          } catch {}
        }
      }).catch(() => {});
    };
    document.addEventListener("visibilitychange", handleVisibility);

    // 장중 5분, 장외 10분 자동 폴링 (매 틱마다 장중/장외 재판단)
    let pollTimer: ReturnType<typeof setTimeout> | null = null;
    const schedulePoll = () => {
      const h = new Date().getHours();
      const delay = (h >= 9 && h < 16) ? 5 * 60 * 1000 : 10 * 60 * 1000;
      pollTimer = setTimeout(() => {
        if (document.visibilityState === "visible") loadAllData();
        schedulePoll();
      }, delay);
    };
    schedulePoll();
    return () => { if (pollTimer) clearTimeout(pollTimer); subscription.unsubscribe(); document.removeEventListener("visibilitychange", handleVisibility); };
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
    { id: "cat-market", label: "시장", icon: <BarChart3 size={14} /> },
    { id: "cat-signal", label: "신호", icon: <Target size={14} /> },
    { id: "cat-analysis", label: "분석", icon: <SearchIcon size={14} /> },
    { id: "cat-strategy", label: "전략", icon: <Zap size={14} /> },
    { id: "cat-system", label: "시스템", icon: <Bot size={14} /> },
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
      {showLogin && createPortal(
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-6 anim-fade-in" onClick={() => { if (!loginLoading && supaUser) setShowLogin(false); }}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-md" />
          <div className="relative w-full max-w-[340px] rounded-2xl overflow-hidden anim-scale-in" onClick={e => e.stopPropagation()}
            style={{ background: "var(--bg-card)", border: "1px solid var(--border)", boxShadow: "0 8px 32px rgba(0,0,0,0.3)" }}>
            {/* 헤더 */}
            <div className="px-5 pt-5 pb-3">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-bold t-text">로그인</h3>
                {supaUser && (
                <button onClick={() => { if (!loginLoading) setShowLogin(false); }} className="p-1 rounded-lg t-text-dim hover:t-text transition">
                  <X size={18} />
                </button>
                )}
              </div>
              <p className="text-[11px] t-text-dim mt-1">포트폴리오 관리 및 실시간 시세 조회</p>
            </div>
            {/* 본문 */}
            <form className="px-5 pb-5" onSubmit={async (e) => {
              e.preventDefault();
              if (loginLoading || !loginEmail.trim() || !loginPw) return;
              setLoginError("");
              setLoginLoading(true);
              try {
                const { data, error } = await Promise.race([
                  supabase.auth.signInWithPassword({ email: loginEmail.trim(), password: loginPw }),
                  new Promise<never>((_, reject) => setTimeout(() => reject(new Error("로그인 응답 시간 초과. 다시 시도해주세요.")), 10000)),
                ]);
                if (error) {
                  const msg = error.message.includes("rate limit") ? "잠시 후 다시 시도해주세요"
                    : error.message.includes("Invalid login") ? "이메일 또는 비밀번호가 올바르지 않습니다"
                    : error.message;
                  setLoginError(msg);
                  return;
                }
                if (data?.session) {
                  setSupaUser(data.session.user);
                  setAccessToken(data.session.access_token ?? null);
                  setShowLogin(false);
                  setLoginEmail("");
                  setLoginPw("");
                  getAlertMode().then(setAlertModeState).catch(() => {});
                } else {
                  setLoginError("로그인 응답에 세션이 없습니다. 다시 시도해주세요.");
                }
              } catch (e: any) {
                setLoginError(e?.message || "네트워크 오류. 다시 시도해주세요.");
              } finally {
                setLoginLoading(false);
              }
            }}>
              {loginError && (
                <div className="flex items-center gap-2 text-[11px] text-red-400 mb-3 p-2.5 rounded-lg" style={{ background: "rgba(239,68,68,0.08)" }}>
                  <span className="shrink-0">!</span>
                  <span>{loginError}</span>
                </div>
              )}
              <input type="email" placeholder="이메일" value={loginEmail} onChange={e => setLoginEmail(e.target.value)}
                autoComplete="email" autoFocus
                className="w-full text-[14px] px-3.5 py-2.5 rounded-xl t-text mb-2 outline-none transition"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", }} />
              <input type="password" placeholder="비밀번호" value={loginPw} onChange={e => setLoginPw(e.target.value)}
                autoComplete="current-password"
                className="w-full text-[14px] px-3.5 py-2.5 rounded-xl t-text mb-4 outline-none transition"
                style={{ background: "var(--bg)", border: "1px solid var(--border)", }} />
              <button type="submit" disabled={loginLoading || !loginEmail.trim() || !loginPw}
                className="w-full text-sm font-semibold py-2.5 rounded-xl text-white transition disabled:opacity-40"
                style={{ background: loginLoading ? "#4b5563" : "#2563eb" }}>
                {loginLoading ? "로그인 중..." : "로그인"}
              </button>
            </form>
          </div>
        </div>,
        document.body
      )}
      {/* 헤더 드롭다운 메뉴 */}
      {/* 설정 메뉴 — createPortal로 document.body에 직접 렌더 */}
      {showHeaderMenu && createPortal(
        <>
          <div onClick={() => setShowHeaderMenu(false)}
            className="fixed inset-0 z-[9998] bg-black/30 backdrop-blur-sm anim-fade-in" />
          <div className="fixed z-[9999] w-[200px] t-card rounded-2xl shadow-lg overflow-hidden anim-scale-in" style={{ top: 52, right: 16 }}>
            <div className="p-1">
              <button onClick={() => setShowHeaderMenu(false)}
                className="w-full flex justify-end p-1.5 t-text-dim hover:t-text transition">
                <X size={16} />
              </button>
              <RefreshButtons menuMode />
              <div className="border-t t-border-light my-1" />
              <button onClick={() => { setShowHeaderMenu(false); setShowSettings(true); }}
                className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[13px] t-text-sub hover:t-text transition">
                <span className="text-[18px]">⚙</span> 설정
              </button>
              <div className="border-t t-border-light my-1" />
              {supaUser ? (
                <button onClick={() => {
                  setShowHeaderMenu(false);
                  setSupaUser(null);
                  setAccessToken(null);
                  localStorage.removeItem(STORAGE_KEY);
                  supabase.auth.signOut().catch(() => {});
                  setShowLogin(true);
                }}
                  className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[13px] text-red-400 hover:bg-red-500/10 transition">
                  <span>↪</span> 로그아웃
                </button>
              ) : (
                <button onClick={() => { setShowHeaderMenu(false); setShowLogin(true); }}
                  className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[13px] text-blue-400 hover:bg-blue-500/10 transition">
                  <span>→</span> 로그인
                </button>
              )}
            </div>
          </div>
        </>,
        document.body
      )}
      {/* 설정 팝업 */}
      {showSettings && createPortal(
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-6 anim-fade-in" onClick={() => setShowSettings(false)}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-md" />
          <div className="relative w-full max-w-[340px] rounded-2xl overflow-hidden anim-scale-in"
            style={{ background: "var(--bg-card)", border: "1px solid var(--border)", boxShadow: "0 8px 32px rgba(0,0,0,0.3)" }}
            onClick={e => e.stopPropagation()}>
            <div className="px-5 pt-5 pb-1">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-bold t-text">설정</h3>
                <button onClick={() => setShowSettings(false)} className="p-2 -mr-1 rounded-lg t-text-dim hover:t-text transition">
                  <X size={18} />
                </button>
              </div>
            </div>
            <div className="px-5 pb-6 space-y-4 pt-3">
              {!supaUser ? (
                <div className="text-center py-6">
                  <div className="text-2xl mb-2">🔒</div>
                  <div className="text-sm t-text mb-1">로그인이 필요합니다</div>
                  <div className="text-[11px] t-text-dim mb-4">설정을 변경하려면 먼저 로그인해주세요</div>
                  <button onClick={() => { setShowSettings(false); setShowLogin(true); }}
                    className="text-sm font-medium px-6 py-2 rounded-xl bg-blue-600 text-white hover:bg-blue-500 transition">로그인</button>
                </div>
              ) : <>
              {/* 계정 정보 */}
              <div>
                <div className="text-[12px] font-semibold t-text-sub mb-1.5">계정</div>
                <div className="text-[13px] t-text px-3 py-2.5 rounded-xl" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
                  {supaUser.email}
                </div>
              </div>
              {/* 알림 대상 */}
              <div>
                <div className="text-[12px] font-semibold t-text-sub mb-2">실시간 알림 대상</div>
                <div className="space-y-1.5">
                  {([["all", "교차신호 + 포트폴리오", "교차 신호와 포트폴리오 종목 모두 알림"], ["portfolio_only", "포트폴리오만", "보유 종목만 알림"], ["off", "전체 OFF", "모든 알림 중단"]] as [AlertMode, string, string][]).map(([mode, label, desc]) => {
                    const selected = (pendingAlertMode ?? alertMode) === mode;
                    const isOff = mode === "off";
                    return (
                    <button key={mode} disabled={!supaUser}
                      onClick={() => { if (supaUser) setPendingAlertMode(mode); }}
                      className={`w-full flex items-center gap-3 px-3.5 py-3 rounded-xl transition ${!supaUser ? "opacity-40 cursor-not-allowed" : ""} ${selected
                        ? isOff ? "bg-red-600/10 border-red-500/40" : "bg-blue-600/10 border-blue-500/40"
                        : "hover:opacity-80"}`}
                      style={{ border: `1px solid ${selected ? undefined : "var(--border)"}` }}>
                      {/* 라디오 인디케이터 */}
                      <div className={`w-[18px] h-[18px] rounded-full border-2 shrink-0 flex items-center justify-center transition ${
                        selected
                          ? isOff ? "border-red-400 bg-red-400" : "border-blue-400 bg-blue-400"
                          : "border-gray-400"
                      }`}>
                        {selected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                      </div>
                      <div className="text-left flex-1">
                        <div className={`text-[13px] font-medium ${selected ? (isOff ? "text-red-400" : "text-blue-400") : isOff ? "t-text-sub" : "t-text"}`}>{label}</div>
                        <div className={`text-[10px] ${isOff && !selected ? "t-text-dim" : "t-text-dim"}`}>{desc}</div>
                      </div>
                    </button>
                    );
                  })}
                </div>
                {pendingAlertMode && pendingAlertMode !== alertMode && (
                  <button disabled={settingsSaving}
                    onClick={async () => {
                      setSettingsSaving(true);
                      try {
                        const ok = await setAlertMode(pendingAlertMode);
                        if (ok) {
                          setAlertModeState(pendingAlertMode);
                          setPendingAlertMode(null);
                          setSettingsResult("✓ 설정이 저장되었습니다");
                        } else {
                          setSettingsResult("✕ 저장 실패 — 다시 시도해주세요");
                        }
                      } catch {
                        setSettingsResult("✕ 저장 실패 — 네트워크를 확인해주세요");
                      }
                      setSettingsSaving(false);
                      setTimeout(() => setSettingsResult(""), 2000);
                    }}
                    className="w-full mt-3 text-[13px] font-semibold py-2.5 rounded-xl text-white bg-blue-600 hover:bg-blue-500 transition disabled:opacity-40">
                    {settingsSaving ? "저장 중..." : "확인"}
                  </button>
                )}
                {settingsResult && (
                  <div className={`text-[11px] text-center mt-2 py-1.5 rounded-lg ${settingsResult.includes("실패") ? "text-red-400 bg-red-500/10" : "text-emerald-400 bg-emerald-500/10"}`}>
                    {settingsResult}
                  </div>
                )}
              </div>
              </>}
            </div>
          </div>
        </div>,
        document.body
      )}
      {/* 신뢰도 설명 팝업 */}
      {confExp && createPortal(
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-6" onClick={() => setConfExp(null)}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-md" />
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
        </div>,
        document.body
      )}
      {/* 종목 상세 팝업 */}
      {stockDetail && createPortal(
        <div className="fixed inset-0 z-[9999]" onClick={() => { setStockDetail(null); setShowDualExp(false); }}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-md" />
          <div className="fixed bottom-0 left-0 right-0 z-[61] max-h-[85vh] overflow-y-auto rounded-t-2xl t-card border-t t-border-light p-5 sm:max-w-lg sm:mx-auto sm:rounded-2xl sm:bottom-auto sm:top-1/2 sm:-translate-y-1/2 anim-slide-up sm:anim-scale-in" style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 2.5rem)' }} onClick={e => e.stopPropagation()}>
            {/* 드래그 핸들 + 닫기 버튼 */}
            <div className="flex items-center justify-center relative mb-3">
              <div className="w-8 h-1 rounded-full sm:hidden" style={{ background: 'var(--border)' }} />
              <button onClick={() => { setStockDetail(null); setShowDualExp(false); }} className="absolute right-0 top-1/2 -translate-y-1/2 p-1 t-text-dim hover:t-text transition">
                <X size={18} />
              </button>
            </div>
            {/* 헤더 */}
            <div className="flex items-center justify-between mb-4">
              <div>
                <a href={`https://m.stock.naver.com/domestic/stock/${stockDetail.code}/total`}
                  target="_blank" rel="noopener noreferrer"
                  className="text-base font-bold t-text hover:text-blue-400 transition">
                  {stockDetail.name} ↗
                </a>
                <div className="text-[11px] t-text-dim">{stockDetail.code}{stockDetail.market ? ` · ${stockDetail.market}` : ""}</div>
              </div>
              <div className="flex items-center gap-2">
                {(() => {
                  // 실제 데이터 기반 dual_signal 재계산
                  const vs = stockDetail.vision_signal || "";
                  const as_ = stockDetail.api_signal || "";
                  const buysSet = new Set(["매수", "적극매수"]);
                  const ds = buysSet.has(vs) && buysSet.has(as_) ? "쌍방매수"
                    : buysSet.has(vs) ? "Vision매수"
                    : buysSet.has(as_) ? "API매수"
                    : vs && as_ && vs !== as_ ? "혼조" : "";
                  if (!ds) return null;
                  const explanations: Record<string, string> = {
                    "쌍방매수": `Vision AI(${vs})와 KIS API(${as_}) 양쪽 모두 매수 신호가 일치합니다. 두 독립 분석의 합의로 신뢰도가 높습니다.`,
                    "Vision매수": `Vision AI는 매수(${vs}) 신호이나, KIS API는 ${as_ || "없음"}입니다. Vision AI 차트 분석 기반 단독 매수 신호입니다.`,
                    "API매수": `KIS API만 매수(${as_}) 신호이고, Vision AI는 ${vs || "없음"}입니다. KIS 정량 분석 기반 단독 매수 신호입니다.`,
                    "혼조": `Vision AI(${vs})와 KIS API(${as_})의 판단이 서로 다릅니다. 신중한 접근이 필요합니다.`,
                  };
                  return (
                    <div className="relative">
                      <span onClick={(e) => { e.stopPropagation(); setShowDualExp(!showDualExp); }} className={`text-[11px] font-semibold px-2 py-0.5 rounded-full cursor-pointer ${
                        ds === "쌍방매수" ? "bg-emerald-500/10 text-emerald-500" :
                        ds === "API매수" ? "bg-blue-500/10 text-blue-500" :
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
              </div>
            </div>
            {/* 분석 데이터 없음 안내 */}
            {stockDetail._noData && (
              <div className="text-center py-8">
                <BarChart3 size={24} className="mx-auto mb-2 t-text-dim" />
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
        </div>,
        document.body
      )}
      {/* 연속 시그널 날짜 팝업 */}
      {streakPopup && createPortal(
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-6" onClick={() => setStreakPopup(null)}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-md" />
          <div className="relative w-full max-w-[300px] rounded-2xl overflow-hidden"
            style={{ background: "var(--bg-card)", border: "1px solid var(--border)", boxShadow: "0 8px 32px rgba(0,0,0,0.3)" }}
            onClick={e => e.stopPropagation()}>
            <div className="px-4 pt-4 pb-2 flex items-center justify-between">
              <h3 className="text-sm font-bold t-text">{streakPopup.name}</h3>
              <button onClick={() => setStreakPopup(null)} className="p-1 t-text-dim hover:t-text"><X size={16} /></button>
            </div>
            <div className="px-4 pb-4">
              <div className="text-[11px] t-text-dim mb-2">{streakPopup.dates.length}일 연속 · {streakPopup.dates[0]} ~ {streakPopup.dates[streakPopup.dates.length - 1]}</div>
              <div className="flex flex-wrap gap-1.5">
                {streakPopup.dates.map((d, i) => (
                  <span key={i} className="text-[11px] px-2 py-1 rounded-lg t-text" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
                    {d.slice(5)}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
      {/* 라이프사이클 팝업 */}
      {lifecyclePopup && createPortal(
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-6" onClick={() => setLifecyclePopup(null)}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-md" />
          <div className="relative w-full max-w-[320px] rounded-2xl overflow-hidden"
            style={{ background: "var(--bg-card)", border: "1px solid var(--border)", boxShadow: "0 8px 32px rgba(0,0,0,0.3)" }}
            onClick={e => e.stopPropagation()}>
            <div className="px-4 pt-4 pb-2 flex items-center justify-between">
              <h3 className="text-sm font-bold t-text">{lifecyclePopup.theme}</h3>
              <button onClick={() => setLifecyclePopup(null)} className="p-1 t-text-dim hover:t-text"><X size={16} /></button>
            </div>
            <div className="px-4 pb-4 space-y-3">
              <div>
                <div className="text-[10px] t-text-dim mb-1">단계</div>
                <div className="text-sm font-medium t-text">
                  {lifecyclePopup.stage === "탄생" && <><Circle size={12} className="inline text-emerald-400 fill-emerald-400 mr-1" /> 탄생 — 테마 초기 등장. 대장주 중심으로 관심 종목 형성 시작.</>}
                  {lifecyclePopup.stage === "성장" && <><Circle size={12} className="inline text-amber-400 fill-amber-400 mr-1" /> 성장 — 테마 확산 중. 종목 수와 거래량 증가, 수익 기대 구간.</>}
                  {lifecyclePopup.stage === "과열" && <><Circle size={12} className="inline text-red-400 fill-red-400 mr-1" /> 과열 — 급등 후 과열 경고. 차익 실현 및 리스크 관리 필요.</>}
                  {lifecyclePopup.stage === "쇠퇴" && <><Circle size={12} className="inline text-gray-400 fill-gray-400 mr-1" /> 쇠퇴 — 관심 감소, 거래량 축소. 신규 진입 비추천.</>}
                </div>
              </div>
              {lifecyclePopup.strategy && (
                <div>
                  <div className="text-[10px] t-text-dim mb-1">전략</div>
                  <div className="text-xs t-text-sub">{lifecyclePopup.strategy}</div>
                </div>
              )}
              {lifecyclePopup.stocks.length > 0 && (
                <div>
                  <div className="text-[10px] t-text-dim mb-1">포함 종목 ({lifecyclePopup.stocks.length})</div>
                  <div className="flex flex-wrap gap-1.5">
                    {lifecyclePopup.stocks.map((s, i) => (
                      <span key={i} className="text-[11px] px-2 py-1 rounded-lg t-text" style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>{s}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}
      {/* 뱃지 설명 팝업 */}
      {badgePopup && createPortal(
        <div className="fixed inset-0 z-[9999]" onClick={() => setBadgePopup(null)}>
          <div className="fixed max-w-[260px] px-3 py-2 rounded-xl text-xs t-text-sub shadow-lg"
            style={{ background: "var(--bg-card)", border: "1px solid var(--border)", top: badgePopup.y, left: Math.min(badgePopup.x, window.innerWidth - 270), transform: "translateX(-50%)" }}>
            <span className="font-semibold t-text">{badgePopup.label}</span> — {badgePopup.desc}
          </div>
        </div>,
        document.body
      )}
      {/* 종목 검색 모달 */}
      {showStockSearch && createPortal(
        <div className="fixed inset-0 z-[9999]" onClick={() => setShowStockSearch(false)}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
          <div className="fixed top-0 left-0 right-0 z-[61] max-h-[85vh] overflow-y-auto t-card sm:max-w-lg sm:mx-auto sm:mt-16 sm:rounded-xl" onClick={e => e.stopPropagation()}>
            <div className="sticky top-0 t-card p-4 border-b t-border-light">
              <div className="flex items-center gap-2">
                <SearchIcon size={16} className="t-text-dim shrink-0" />
                <input
                  autoFocus
                  value={globalSearchQuery}
                  onChange={e => setGlobalSearchQuery(e.target.value)}
                  placeholder="종목명 또는 코드 검색..."
                  className="flex-1 text-sm bg-transparent t-text outline-none"
                />
                <button onClick={() => setShowStockSearch(false)} className="t-text-dim"><X size={18} /></button>
              </div>
            </div>
            <div className="p-4">
              {globalSearchQuery.length >= 2 && (() => {
                const q = globalSearchQuery.toLowerCase();
                const match = (s: any) => (s?.name || "").toLowerCase().includes(q) || (s?.code || "").includes(q);
                const sections: { label: string; sectionId: string; items: { stock: any; detail: string }[] }[] = [];
                // AI 주목 종목 (cross_signal)
                const csMatches = (crossSignal || []).filter(match);
                if (csMatches.length) sections.push({ label: "교차 신호 (대장주)", sectionId: "cross", items: csMatches.map(s => ({ stock: s, detail: `vision: ${s.vision_signal || "-"} | api: ${s.api_signal || "-"} | dual: ${s.dual_signal || "-"}` })) });
                const smMatches = (smartMoney || []).filter(match);
                if (smMatches.length) sections.push({ label: "스마트 머니", sectionId: "smartmoney", items: smMatches.map(s => ({ stock: s, detail: `점수: ${s.smart_money_score || "-"} | api: ${s.api_signal || "-"} | 외인: ${s.foreign_net > 0 ? "매수" : s.foreign_net < 0 ? "매도" : "-"}` })) });
                const anMatches = (anomalies || []).filter(match);
                if (anMatches.length) sections.push({ label: "이상 거래 감지", sectionId: "anomaly", items: anMatches.map(a => ({ stock: a, detail: `${a.type || ""} | ${a.change_rate != null ? (a.change_rate >= 0 ? "+" : "") + a.change_rate + "%" : ""} | 거래량 x${a.ratio || "-"}` })) });
                const consAll = [...(consecutiveSignals?.and_condition || []), ...(consecutiveSignals?.or_condition || [])];
                const consMatches = consAll.filter(match);
                if (consMatches.length) sections.push({ label: "연속 시그널", sectionId: "consecutive", items: consMatches.map(r => ({ stock: r, detail: `${r.streak}일 연속 | ${r.dates?.[r.dates.length - 1] || ""}` })) });
                const riskMatches = (riskMonitor || []).filter(match);
                if (riskMatches.length) sections.push({ label: "위험 종목", sectionId: "risk", items: riskMatches.map(r => ({ stock: r, detail: `등급: ${r.level || "-"} | ${(r.warnings || []).join(", ")}` })) });
                const sqMatches = (shortSqueeze || []).filter(match);
                if (sqMatches.length) sections.push({ label: "수급 다이버전스", sectionId: "squeeze", items: sqMatches.map(s => ({ stock: s, detail: `점수: ${s.divergence_score ?? s.squeeze_score ?? "-"}` })) });
                const valMatches = (valuation || []).filter(match);
                if (valMatches.length) sections.push({ label: "밸류에이션", sectionId: "valuation", items: valMatches.map(v => ({ stock: v, detail: `점수: ${v.value_score || "-"} | PER: ${v.per || "-"}` })) });

                if (!sections.length) return <div className="text-center py-8 text-sm t-text-dim">"{globalSearchQuery}" 검색 결과 없음</div>;
                return sections.map(sec => (
                  <div key={sec.label} className="mb-4">
                    <div onClick={() => {
                      setShowStockSearch(false);
                      setTimeout(() => document.getElementById(sec.sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
                    }} className="text-[11px] font-semibold t-text-sub mb-1.5 cursor-pointer hover:text-blue-500 transition">{sec.label} ({sec.items.length})</div>
                    <div className="space-y-1">
                      {sec.items.map((item, j) => (
                        <div key={j} onClick={() => {
                          const detail = [...(crossSignal || []), ...(smartMoney || [])].find((s: any) => s.code === item.stock.code);
                          setStockDetail(detail || { name: item.stock.name, code: item.stock.code, _noData: true });
                          setShowStockSearch(false);
                        }} className="flex items-center justify-between p-2 t-card-alt rounded-lg cursor-pointer hover:opacity-80 transition border t-border-light">
                          <div className="min-w-0">
                            <span className="text-sm font-medium t-text">{item.stock.name}</span>
                            <span className="text-[10px] t-text-dim ml-1.5">{item.stock.code}</span>
                          </div>
                          <div className="text-[10px] t-text-dim shrink-0 max-w-[50%] text-right truncate">{item.detail}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ));
              })()}
              {globalSearchQuery.length < 2 && <div className="text-center py-8 text-sm t-text-dim">2글자 이상 입력하세요</div>}
            </div>
          </div>
        </div>,
        document.body
      )}
      {/* 토스트 메시지 */}
      {toastMsg && createPortal(
        <div className={`fixed top-16 left-1/2 z-[9999] px-4 py-2.5 rounded-xl text-sm font-medium shadow-lg anim-toast ${
          toastMsg.includes("실패") ? "text-red-200" : "text-white"
        }`}
          style={{ background: toastMsg.includes("실패") ? "rgba(127,29,29,0.9)" : "rgba(30,30,30,0.9)", backdropFilter: "blur(8px)", transform: "translateX(-50%)" }}>
          {toastMsg}
        </div>,
        document.body
      )}
      {/* 헤더 — 컴팩트 sticky */}
      <div className="sticky z-50 -mx-4 px-4 pt-2 pb-0 backdrop-blur-md" style={{ top: 'env(safe-area-inset-top, 0px)', background: 'var(--bg-header)', borderBottom: '1px solid var(--border-light)' }}>
        <div className="flex items-center justify-between h-10">
          <h1
            className={`text-lg font-bold t-text flex items-center gap-2 shrink-0 cursor-pointer active:scale-95 transition-all ${headerRefreshing ? "animate-bounce" : ""}`}
            style={headerRefreshing ? { opacity: 0.6 } : undefined}
            onClick={() => {
              if (headerRefreshing) return;
              setHeaderRefreshing(true);
              window.scrollTo({ top: 0, behavior: "smooth" });
              if (window.location.hash !== "#/") window.location.hash = "#/";
              loadAllData(true);
              setTimeout(() => setHeaderRefreshing(false), 2000);
            }}
          >
            <img src={import.meta.env.BASE_URL + "favicon.svg"} alt="logo"
              className="w-5 h-5 shrink-0 hover:rotate-12 transition-transform" />
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
            <button onClick={() => { setShowStockSearch(true); setGlobalSearchQuery(""); }} className="p-1.5 rounded-lg hover:opacity-80 transition t-text-sub" title="종목 검색">
              <SearchIcon size={16} />
            </button>
            <button onClick={() => setShowHeaderMenu(true)} className="p-1.5 rounded-lg hover:opacity-80 transition t-text-sub text-lg leading-none">⋮</button>
          </div>
        </div>
        {/* 페이지 탭 */}
        <div className="flex -mx-1 relative">
          {[
            { href: "#/", label: "대시보드", path: "/" },
            { href: "#/portfolio", label: "포트폴리오", path: "/portfolio" },
            { href: "#/scanner", label: "스캐너", path: "/scanner" },
            { href: "#/auto-trader", label: "모의투자", path: "/auto-trader" },
          ].map((tab, idx, arr) => {
            const active = location.pathname === tab.path;
            return <a key={tab.path} href={tab.href} className={`flex-1 text-center py-3 text-sm font-medium transition-colors ${active ? "font-semibold t-accent" : "t-text-dim hover:t-text-sub"}`}>{tab.label}</a>;
          })}
          {/* 슬라이딩 인디케이터 */}
          <div className="absolute bottom-0 h-[3px] rounded-full transition-all duration-300 ease-out" style={{
            background: 'var(--accent)',
            width: '25%',
            left: `${["/", "/portfolio", "/scanner", "/auto-trader"].indexOf(location.pathname) * 25}%`,
          }} />
        </div>
      </div>
      {/* 헤더-컨텐츠 여백 */}

      {/* 자식 라우트 컨텐츠 (Portfolio, AutoTrader 등) */}
      {!isIndexRoute && (
        <Outlet context={{ supaUser, onShowLogin: () => setShowLogin(true), onStockDetail: setStockDetail, setToastMsg, crossSignal, smartMoney, riskMonitor, consecutiveSignals }} />
      )}

      {/* ===== 시장 카테고리 (대시보드만) ===== */}
      {isIndexRoute && <>
      <div id="cat-market" className="scroll-mt-24 mt-3" />

      {/* 장전 프리마켓 */}
      {premarket && (
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="premarket" timestamp={ts}>장전 프리마켓</SectionHeader>
          {/* 예측 결과 + 핵심 요인 */}
          <div className={`rounded-xl p-3 mb-3 ${premarket.prediction?.includes("상승") || premarket.prediction?.includes("강세") ? "bg-red-500/10 border border-red-500/20" : premarket.prediction?.includes("하락") || premarket.prediction?.includes("약세") ? "bg-blue-500/10 border border-blue-500/20" : "t-card-alt border t-border-light"}`}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] t-text-dim">시장 출발 예상</span>
              <span className={`text-sm font-bold ${premarket.prediction?.includes("상승") || premarket.prediction?.includes("강세") ? "text-red-600" : premarket.prediction?.includes("하락") || premarket.prediction?.includes("약세") ? "text-blue-600" : "t-text"}`}>
                {premarket.prediction}
              </span>
            </div>
            {premarket.key_factors?.length > 0 && (
              <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                {premarket.key_factors.map((f: string, i: number) => {
                  const isPositive = f.includes("+") || f.includes("상승") || f.includes("매수");
                  const isNegative = f.includes("-") || f.includes("하락") || f.includes("공포") || f.includes("경고") || f.includes("우려");
                  return (
                    <div key={i} className="flex items-center gap-1 text-[11px]">
                      <span className={`shrink-0 text-[9px] ${isPositive ? "text-red-400" : isNegative ? "text-blue-400" : "t-text-dim"}`}>
                        {isPositive ? "▲" : isNegative ? "▼" : "·"}
                      </span>
                      <span className="t-text-sub truncate">{f}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>
      )}

      {/* AI 모닝 브리핑 */}
      {briefing?.morning && <BriefingSection briefing={briefing} performance={performance} crossSignal={crossSignal} smartMoney={smartMoney} briefTs={briefTs} setStockDetail={setStockDetail} setConfExp={setConfExp} />}

      {/* 시장 현황 (심리 온도계 통합) */}
      {performance && (
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="market" timestamp={ts}>시장 현황</SectionHeader>

          {/* 시장 심리 — 시장 현황 상단에 통합 */}
          {sentiment && (
            <div className="mb-4 pb-4 border-b t-border-light">
              <div className="flex items-center gap-4 mb-2">
                <div className="text-2xl font-bold t-text tabular-nums">{sentiment.score}<span className="text-xs font-normal t-text-dim">/100</span></div>
                <div>
                  <div className={`text-sm font-semibold ${sentiment.score < 30 ? "text-blue-600" : sentiment.score < 60 ? "t-text-sub" : "text-red-600"}`}>
                    {sentiment.label}
                  </div>
                  <div className="text-[10px] t-text-dim">{sentiment.strategy}</div>
                </div>
              </div>
              <div className="relative h-2 t-muted rounded-full overflow-hidden mb-1.5">
                <div className={`h-full rounded-full transition-all duration-500 ${sentiment.score < 30 ? "bg-blue-500" : sentiment.score < 60 ? "bg-gray-400" : "bg-red-500"}`} style={{ width: `${sentiment.score}%` }} />
                {/* 현재 위치 마커 */}
                <div className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full border-2 border-white shadow-sm transition-all duration-500"
                  style={{ left: `${sentiment.score}%`, marginLeft: -6, background: sentiment.score < 30 ? '#3b82f6' : sentiment.score < 60 ? '#9ca3af' : '#ef4444' }} />
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
            {performance.kospi?.current && (() => {
              const k = performance.kospi;
              const chg = k.change ?? (k.ma5 ? +(k.current - k.ma5).toFixed(2) : null);
              const pct = chg != null && k.ma5 ? +(chg / k.ma5 * 100).toFixed(2) : null;
              const up = (chg || 0) >= 0;
              return (
                <div className="flex items-center gap-2 min-w-0">
                  {up ? <TrendingUp size={14} className="text-red-400 shrink-0" /> : <TrendingDown size={14} className="text-blue-400 shrink-0" />}
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{k.current.toLocaleString()}</div>
                    <div className="text-xs t-text-sub">KOSPI {chg != null && <span className={up ? "text-red-500" : "text-blue-500"}>{up ? "▲" : "▼"}{Math.abs(chg).toFixed(2)}{pct != null && ` (${up ? "+" : ""}${pct.toFixed(2)}%)`}</span>}</div>
                  </div>
                </div>
              );
            })()}
            {performance.kosdaq?.current && (() => {
              const k = performance.kosdaq;
              const chg = k.change ?? (k.ma5 ? +(k.current - k.ma5).toFixed(2) : null);
              const pct = chg != null && k.ma5 ? +(chg / k.ma5 * 100).toFixed(2) : null;
              const up = (chg || 0) >= 0;
              return (
                <div className="flex items-center gap-2 min-w-0">
                  {up ? <TrendingUp size={14} className="text-red-400 shrink-0" /> : <TrendingDown size={14} className="text-blue-400 shrink-0" />}
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{k.current.toLocaleString()}</div>
                    <div className="text-xs t-text-sub">KOSDAQ {chg != null && <span className={up ? "text-red-500" : "text-blue-500"}>{up ? "▲" : "▼"}{Math.abs(chg).toFixed(2)}{pct != null && ` (${up ? "+" : ""}${pct.toFixed(2)}%)`}</span>}</div>
                  </div>
                </div>
              );
            })()}
          </div>
          {/* 글로벌 매크로 */}
          {indicatorHistory?.macro && Object.keys(indicatorHistory.macro).length > 0 && (
            <div className="mt-3 pt-3 border-t t-border-light">
              <div className="text-xs font-semibold t-text mb-2 flex items-center justify-between">
                <span>글로벌 매크로</span>
                {sentiment?.components?.macro_score?.value != null && (
                  <div className="flex items-center gap-1.5 relative">
                    <span onClick={() => setShowMacroHelp(!showMacroHelp)} className="w-4 h-4 rounded-full border t-border-light text-[9px] font-medium t-text-dim flex items-center justify-center cursor-pointer hover:t-text-sub hover:border-current">?</span>
                    <span className={`text-[11px] font-bold ${(sentiment.components.macro_score.value ?? 5) >= 5 ? "text-red-400" : "text-blue-400"}`}>
                      {sentiment.components.macro_score.value}/10
                    </span>
                    {showMacroHelp && (
                      <div className="absolute right-0 top-6 w-72 p-3 rounded-xl t-card border t-border-light shadow-lg z-10" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between mb-2">
                          <div className="text-[11px] font-semibold t-text">글로벌 매크로 점수</div>
                          <span onClick={() => setShowMacroHelp(false)} className="text-[10px] t-text-dim cursor-pointer">닫기</span>
                        </div>
                        <div className="text-[10px] t-text-sub leading-relaxed space-y-1.5">
                          <p>6개 글로벌 지표의 변동률을 가중평균하여 0~10점으로 산출합니다. 5점이 중립, 5 이상 강세, 미만 약세.</p>
                          <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 mt-1">
                            <span>나스닥(NQ) <b>×2.0</b></span><span>반도체(SOXX) <b>×2.0</b></span>
                            <span>KOSPI200 <b>×1.5</b></span><span>한국ETF(EWY) <b>×1.0</b></span>
                            <span>마이크론(MU) <b>×1.0</b></span><span>한국3X(KORU) <b>×0.5</b></span>
                          </div>
                          <p className="t-text-dim">이 점수는 시장 심리지수(100점)에서 10점 비중으로 반영됩니다.</p>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
              <div className="grid grid-cols-2 gap-1.5">
                {(["NQ=F", "KOSPI200", "MU", "SOXX", "EWY", "KORU"] as string[]).map(symbol => {
                  const macro = indicatorHistory.macro as Record<string, any[]>;
                  const history = macro[symbol];
                  const arr = Array.isArray(history) ? history : [];
                  const latest = arr[arr.length - 1];
                  const prev = arr[arr.length - 2];
                  if (!latest) return null;
                  const nameMap: Record<string, string> = { "NQ=F": "나스닥선물", "KOSPI200": "KODEX 200", "MU": "마이크론", "SOXX": "SOXX(반도체)", "EWY": "EWY(한국ETF)", "KORU": "KORU(한국3X)" };
                  return (
                    <div key={symbol} className="t-card-alt rounded-lg p-2">
                      <div className="text-[11px] font-medium t-text-sub mb-0.5">{nameMap[symbol] || symbol}</div>
                      <div className="flex items-baseline gap-1.5">
                        <span className="text-sm font-semibold t-text">{latest.price?.toLocaleString()}</span>
                        {latest.change_pct != null && (
                          <span className={`text-[10px] font-medium ${latest.change_pct >= 0 ? "text-red-500" : "text-blue-500"}`}>
                            {latest.change_pct >= 0 ? "+" : ""}{latest.change_pct}%
                          </span>
                        )}
                      </div>
                      {(() => {
                        const prevPrice = prev?.price ?? (latest.change_pct && latest.price ? Math.round(latest.price / (1 + latest.change_pct / 100) * 100) / 100 : null);
                        return prevPrice != null ? <div className="text-[10px] t-text-dim mt-0.5">전일 {prevPrice.toLocaleString()}</div> : null;
                      })()}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 주요 선물 */}
          {performance.futures?.length > 0 && (
            <div className="mt-3 pt-3 border-t t-border-light">
              <div className="text-xs font-semibold t-text mb-2">주요 선물</div>
              <div className="grid grid-cols-3 gap-1.5">
                {performance.futures.map((ft: any, i: number) => (
                  <div key={i} className="t-card-alt rounded-lg p-2 text-center">
                    <div className="text-[11px] font-medium t-text-sub truncate">{ft.name}</div>
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
              <div className="text-xs font-semibold t-text mb-2">환율</div>
              <div className="grid grid-cols-2 gap-1.5">
                {performance.exchange.slice(0, 4).map((r: any, i: number) => {
                  const label: Record<string, string> = { USD: "원/달러", JPY: "원/엔", EUR: "원/유로", CNY: "원/위안" };
                  const cur = r.currency || r.name || "";
                  return (
                    <div key={i} className="t-card-alt rounded-lg p-2">
                      <div className="text-[11px] font-medium t-text-sub mb-0.5">{label[cur] || cur}</div>
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

      {/* AI 주목 종목 */}
      {performance?.by_source?.combined && <FocusedStockSection performance={performance} crossSignal={crossSignal} smartMoney={smartMoney} consecutiveSignals={consecutiveSignals} ts={ts} setStockDetail={setStockDetail} />}

      {/* ===== 신호 카테고리 ===== */}
      <div id="cat-signal" className="scroll-mt-24 flex items-center gap-3 mt-6 mb-1">
        <div className="h-px flex-1" style={{ background: 'var(--border)' }} />
        <span className="text-[10px] font-semibold tracking-wider t-text-dim">신호</span>
        <div className="h-px flex-1" style={{ background: 'var(--border)' }} />
      </div>

      {/* 연속 시그널 추적 */}
      {consecutiveSignals && (consecutiveSignals.and_condition?.length > 0 || consecutiveSignals.or_condition?.length > 0) && <ConsecutiveSignalSection consecutiveSignals={consecutiveSignals} ts={ts} setStreakPopup={setStreakPopup} />}

      {/* 교차 신호 */}
      {(() => {
        const gapMap = new Map((gapAnalysis || []).filter((g: any) => Math.abs(g.gap_pct) >= 2).map((g: any) => [g.code, g]));
        return (
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="cross" timestamp={ts} count={crossSignal?.length ?? 0}>교차 신호</SectionHeader>
          <div className="space-y-2">
            {(crossSignal || []).map((s, i) => {
              const intra = s.intraday || {};
              const ageH = s.signal_age_hours || 0;
              const gap = gapMap.get(s.code) as any;
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
                    {gap && (
                      <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${gap.gap_pct >= 0 ? "bg-red-500/10 text-red-400" : "bg-blue-500/10 text-blue-400"}`}>
                        {gap.gap_pct >= 0 ? "▲" : "▼"}시가 {gap.gap_pct >= 0 ? "+" : ""}{gap.gap_pct}%
                      </span>
                    )}
                    {s.dual_signal && (
                      <Badge variant={s.dual_signal === "쌍방매수" ? "success" : s.dual_signal === "API매수" ? "blue" : s.dual_signal === "혼조" ? "warning" : "default"}>
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
                  {intra.validation && (() => {
                    const sig = s.vision_signal || s.api_signal || "";
                    const isBuy = ["매수", "적극매수"].includes(sig);
                    const isSell = ["매도", "적극매도"].includes(sig);
                    const arrow = intra.validation === "신호 유효" ? (isBuy ? "↑ 매수 유효" : isSell ? "↓ 매도 유효" : null) : intra.validation;
                    if (!arrow) return null;
                    return (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                      intra.validation === "신호 유효" ? "bg-emerald-500/10 text-emerald-400" :
                      intra.validation === "신호 약화" ? "bg-amber-500/10 text-amber-400" :
                      intra.validation === "신호 무효화" ? "bg-red-500/10 text-red-400" :
                      "bg-gray-500/10 t-text-dim"
                    }`}>{arrow}</span>
                    );
                  })()}
                  {ageH > 0 && <span className={`text-[10px] ${ageColor}`}>{Math.round(ageH)}시간 전</span>}
                </div>
              </div>
              );
            })}
          </div>
            {!crossSignal?.length && <Empty />}
        </section>
        );
      })()}

      {/* 테마 라이프사이클 */}
      <LifecycleSection lifecycle={lifecycle} ts={ts} setLifecyclePopup={setLifecyclePopup} />

      {/* 이상 거래 감지 */}
      {(() => {
        // 1. 종목별 그룹핑
        const grouped: Record<string, { code: string; name: string; types: string[]; ratio?: number; change_rate?: number }> = {};
        for (const a of (anomalies || [])) {
          const key = a.code || a.name;
          if (!grouped[key]) grouped[key] = { code: a.code, name: a.name, types: [], ratio: a.ratio, change_rate: a.change_rate };
          else { if (a.ratio && (!grouped[key].ratio || a.ratio > grouped[key].ratio)) grouped[key].ratio = a.ratio; }
          if (!grouped[key].types.includes(a.type)) grouped[key].types.push(a.type);
        }
        const items = Object.values(grouped);

        // 2. 컨텍스트: 교차 신호 포함 여부, 수급 동향
        const crossCodes = new Set((crossSignal || []).map((s: any) => s.code));
        const investorMap: Record<string, any> = {};
        for (const sm of (Array.isArray(smartMoney) ? smartMoney : [])) {
          if (sm?.code) investorMap[sm.code] = sm;
        }

        // 3. 액션 분류
        const classify = (item: typeof items[0]) => {
          const cr = item.change_rate ?? 0;
          const inv = investorMap[item.code];
          const hasForeignBuy = inv && inv.foreign_net > 0;
          if (hasForeignBuy && cr > 0) return { label: "수급 동반", color: "bg-emerald-500/10 border-emerald-500/20", text: "text-emerald-500", desc: "외국인/기관 순매수 + 가격 상승 동반. 수급과 가격이 같은 방향 → 신뢰도 높은 상승." };
          if (cr >= 25) return { label: "추격 주의", color: "bg-red-500/10 border-red-500/20", text: "text-red-400", desc: "등락률 25% 이상 급등. 이미 큰 폭 상승 → 추격 매수 시 고점 물림 위험." };
          if (cr >= 10 && (item.ratio ?? 0) >= 2) return { label: "급등 확인", color: "bg-orange-500/10 border-orange-500/20", text: "text-orange-400", desc: "거래량 폭발(x2 이상) + 등락률 10~25%. 거래량이 뒷받침된 확인된 급등 → 모멘텀 추세." };
          if (cr < 10 && (item.ratio ?? 0) >= 2) return { label: "초기 급등", color: "bg-amber-500/10 border-amber-500/20", text: "text-amber-500", desc: "거래량 폭발(x2 이상) + 등락률 10% 미만. 아직 초기 단계 → 진입 여지 있음." };
          return { label: "", color: "bg-red-500/6 border-red-500/15", text: "", desc: "" };
        };

        // 4. 정렬: 수급동반 > 초기급등 > 나머지 > 추격주의
        const order: Record<string, number> = { "수급 동반": 0, "급등 확인": 1, "초기 급등": 2, "": 3, "추격 주의": 4 };
        items.sort((a, b) => (order[classify(a).label] ?? 2) - (order[classify(b).label] ?? 2) || (b.change_rate ?? 0) - (a.change_rate ?? 0));

        const show = items.slice(0, 10);
        const rest = items.slice(10);

        return (
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="anomaly" timestamp={ts} count={items.length}>이상 거래 감지</SectionHeader>
          <div className="space-y-1.5">
            {show.map((a, i) => {
              const cls = classify(a);
              const inv = investorMap[a.code];
              const isCross = crossCodes.has(a.code);
              return (
              <div key={i} onClick={() => {
                const detail = [...(crossSignal || []), ...(smartMoney || [])].find((s: any) => s.code === a.code);
                setStockDetail(detail || { name: a.name, code: a.code, _noData: true });
              }} className={`flex items-center justify-between p-2 border rounded-lg gap-2 cursor-pointer hover:opacity-80 transition ${cls.color}`}>
                <div className="flex items-center gap-2 min-w-0">
                  <Zap size={14} className="text-red-400 shrink-0" />
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-medium truncate">{a.name}</span>
                      {isCross && <span className="text-[9px] px-1 py-0.5 rounded bg-blue-500/15 text-blue-400">관심</span>}
                      {cls.label && <span onClick={(e) => { e.stopPropagation(); const r = (e.target as HTMLElement).getBoundingClientRect(); setBadgePopup({ label: cls.label, desc: cls.desc, x: r.left + r.width / 2, y: r.bottom + 8 }); }}
                        className={`text-[9px] px-1 py-0.5 rounded font-medium cursor-pointer ${cls.text} ${cls.color}`}>{cls.label}</span>}
                    </div>
                    <div className="text-[10px] t-text-dim">{a.types.join(" + ")}</div>
                  </div>
                </div>
                <div className="text-right text-xs shrink-0">
                  {a.ratio && <div className="text-amber-600 font-medium">거래량 x{a.ratio}</div>}
                  {a.change_rate != null && (
                    <div className={a.change_rate >= 0 ? "text-red-600" : "text-blue-600"}>
                      {a.change_rate >= 0 ? "+" : ""}{a.change_rate}%
                    </div>
                  )}
                  {inv && <div className={`text-[10px] ${inv.foreign_net > 0 ? "text-red-400" : "text-blue-400"}`}>외인 {inv.foreign_net > 0 ? "매수" : "매도"}</div>}
                </div>
              </div>
              );
            })}
            {rest.length > 0 && (
              <details className="mt-1">
                <summary className="text-[10px] t-text-dim cursor-pointer hover:underline py-1">더 보기 ({rest.length})</summary>
                <div className="space-y-1.5 mt-1.5">
                  {rest.map((a, i) => {
                    const cls = classify(a);
                    return (
                    <div key={i} onClick={() => {
                      const detail = [...(crossSignal || []), ...(smartMoney || [])].find((s: any) => s.code === a.code);
                      setStockDetail(detail || { name: a.name, code: a.code, _noData: true });
                    }} className={`flex items-center justify-between p-2 border rounded-lg gap-2 opacity-60 cursor-pointer hover:opacity-80 transition ${cls.color}`}>
                      <div className="flex items-center gap-2 min-w-0">
                        <Zap size={12} className="text-red-400 shrink-0" />
                        <div className="min-w-0">
                          <span className="text-xs font-medium truncate">{a.name}</span>
                          <span className="text-[10px] t-text-dim ml-1">{a.types.join("+")}</span>
                        </div>
                      </div>
                      <div className="text-[10px] t-text-sub shrink-0">{a.change_rate != null ? `${a.change_rate >= 0 ? "+" : ""}${a.change_rate}%` : ""}</div>
                    </div>
                    );
                  })}
                </div>
              </details>
            )}
          </div>
          {!items.length && <Empty />}
        </section>
        );
      })()}

      {/* 위험 종목 모니터 */}
      <RiskMonitorSection riskMonitor={riskMonitor} ts={ts} />

      {/* 스마트 머니 TOP */}
      {(() => {
        const gapMap2 = new Map((gapAnalysis || []).filter((g: any) => Math.abs(g.gap_pct) >= 2).map((g: any) => [g.code, g]));
        return (
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="smartmoney" timestamp={ts} count={smartMoney?.length ?? 0}>스마트 머니 TOP</SectionHeader>
          <div className="space-y-1.5">
            {(smartMoney || []).slice(0, 8).map((s, i) => {
              const intra = s.intraday || {};
              const gap = gapMap2.get(s.code) as any;
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
                        {gap && (
                          <span className={`text-[10px] font-medium px-1 py-0.5 rounded ${gap.gap_pct >= 0 ? "bg-red-500/10 text-red-400" : "bg-blue-500/10 text-blue-400"}`}>
                            {gap.gap_pct >= 0 ? "▲" : "▼"}시가 {gap.gap_pct >= 0 ? "+" : ""}{gap.gap_pct}%
                          </span>
                        )}
                        {s.dual_signal && (
                          <span className={`text-[10px] ${s.dual_signal === "쌍방매수" ? "text-emerald-500" : s.dual_signal === "API매수" ? "text-blue-400" : "t-text-dim"}`}>
                            {s.dual_signal}
                          </span>
                        )}
                        {intra.validation && (() => {
                          const sig2 = s.vision_signal || s.api_signal || "";
                          const isBuy2 = ["매수", "적극매수"].includes(sig2);
                          const isSell2 = ["매도", "적극매도"].includes(sig2);
                          const arrow2 = intra.validation === "신호 유효" ? (isBuy2 ? "↑ 매수 유효" : isSell2 ? "↓ 매도 유효" : null) : intra.validation;
                          if (!arrow2) return null;
                          return (
                          <span className={`text-[10px] ${
                            intra.validation === "신호 유효" ? "text-emerald-400" :
                            intra.validation === "신호 약화" ? "text-amber-400" :
                            intra.validation === "신호 무효화" ? "text-red-400" : "t-text-dim"
                          }`}>{arrow2}</span>
                          );
                        })()}
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
        );
      })()}

      {/* 전략 시뮬레이션 */}
      <SimulationSection simulation={simulation} ts={ts} />

      {/* 차트 패턴 매칭 */}
      {(
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="pattern" timestamp={ts}>차트 패턴 매칭</SectionHeader>
          <div className="space-y-3">
            {(pattern || []).filter((p: any) => p.matches?.length > 0).map((p: any, i: number) => (
              <div key={i}>
                <div className="text-[12px] font-medium t-text flex items-center gap-1.5 mb-2">
                  <LineChart size={13} className="t-text-dim shrink-0" />
                  {p.name} <span className="t-text-dim font-normal">{p.code}</span>
                </div>
                {p.matches?.slice(0, 3).map((m: any, j: number) => {
                  const dateLabel = m.date ? m.date.slice(5) : "";
                  const matchName = m.name || m.code || "?";
                  const dr = m.daily_returns || {};
                  const sim = (m.similarity * 100).toFixed(0);
                  return (
                  <div key={j} className="ml-5 mb-2 last:mb-0">
                    <div className="text-[11px] t-text-sub mb-1">{dateLabel} {matchName} <span className="t-text-dim">{sim}%</span></div>
                    <div className="flex gap-1">
                      {[1,2,3,4,5].map(d => {
                        const v = dr[`d${d}`];
                        return v != null ? (
                          <span key={d} className={`text-[10px] px-1.5 py-0.5 rounded ${v >= 0 ? "text-red-500 bg-red-500/8" : "text-blue-500 bg-blue-500/8"}`}>
                            D{d} {v >= 0 ? "+" : ""}{v.toFixed(1)}
                          </span>
                        ) : null;
                      })}
                    </div>
                  </div>
                  );
                })}
              </div>
            ))}
            <p className="text-[10px] t-text-dim">D1~D5 = 패턴 발생 후 각 거래일의 실제 수익률(%)</p>
          </div>
            {!pattern?.length && <Empty />}
        </section>
      )}

      {/* ===== 분석 카테고리 ===== */}
      <div id="cat-analysis" className="scroll-mt-24 flex items-center gap-3 mt-6 mb-1">
        <div className="h-px flex-1" style={{ background: 'var(--border)' }} />
        <span className="text-[10px] font-semibold tracking-wider t-text-dim">분석</span>
        <div className="h-px flex-1" style={{ background: 'var(--border)' }} />
      </div>

      {/* 뉴스 임팩트 */}
      {(
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="news" timestamp={ts}>뉴스 임팩트</SectionHeader>
          <div className="space-y-3">
            {(() => {
              // 관심 종목 코드셋 (매수 신호)
              const watchCodes = new Set([...(crossSignal || []), ...(smartMoney || [])].map((s: any) => s.name));
              const entries = Object.entries(newsImpact || {}).filter(([cat, data]) => cat !== "generated_at" && typeof data === "object" && data?.count > 0);
              return entries.map(([cat, data]: [string, any]) => {
                // 관심 종목 뉴스 우선 정렬
                const titles = [...(data.titles || [])].sort((a: any, b: any) => {
                  const aw = watchCodes.has(a.stock) ? 0 : 1;
                  const bw = watchCodes.has(b.stock) ? 0 : 1;
                  return aw - bw;
                });
                return (
                <div key={cat} className="p-3 t-card-alt rounded-lg">
                  <div className="flex justify-between items-center mb-2">
                    <Badge variant="purple">{cat}</Badge>
                    <span className="text-xs t-text-dim">{data.count}건</span>
                  </div>
                  {titles.slice(0, 3).map((t: any, i: number) => (
                    <div key={i} onClick={() => {
                      if (t.code) {
                        const detail = [...(crossSignal || []), ...(smartMoney || [])].find((s: any) => s.code === t.code);
                        setStockDetail(detail || { name: t.stock, code: t.code, _noData: true });
                      }
                    }} className={`text-xs t-text-sub mb-1.5 flex items-center gap-2 ${t.code ? "cursor-pointer hover:opacity-70" : ""}`}>
                      <span className="truncate min-w-0">{t.title}</span>
                      <span className="shrink-0 flex items-center gap-1">
                        {watchCodes.has(t.stock) && <span className="text-[8px] px-1 py-0.5 rounded bg-blue-500/10 text-blue-400">관심</span>}
                        <span className="t-text-dim">{t.stock}</span>
                        {t.change_rate != null && (
                          <span className={`font-medium ${t.change_rate >= 0 ? "text-red-500" : "text-blue-500"}`}>
                            {t.change_rate >= 0 ? "+" : ""}{t.change_rate}%
                          </span>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
                );
              });
            })()}
          </div>
            {!Object.keys(newsImpact || {}).length && <Empty />}
        </section>
      )}


      {/* 수급 다이버전스 */}
      {(
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="squeeze" timestamp={ts} count={shortSqueeze?.length ?? 0}>수급 다이버전스</SectionHeader>
          <div className="space-y-1.5">
            {(shortSqueeze || []).slice(0, 6).map((s, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-orange-500/10 border border-orange-500/20 rounded-lg gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{s.name}</div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {(s.factors || []).map((f: string, j: number) => (
                      <span key={j} className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/15 text-orange-600 dark:text-orange-400">{f}</span>
                    ))}
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-sm font-bold text-orange-600">{s.divergence_score ?? s.squeeze_score}</div>
                  <div className="text-[10px] t-text-dim">스코어</div>
                </div>
              </div>
            ))}
            <p className="text-[10px] t-text-dim">가격 하락 + 수급 유입 괴리 = 반전 가능성</p>
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
      <div id="cat-strategy" className="scroll-mt-24 flex items-center gap-3 mt-6 mb-1">
        <div className="h-px flex-1" style={{ background: 'var(--border)' }} />
        <span className="text-[10px] font-semibold tracking-wider t-text-dim">전략</span>
        <div className="h-px flex-1" style={{ background: 'var(--border)' }} />
      </div>

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


      {/* 거래대금 이상 감지 — 조건 충족 종목만 표시, 0건이면 섹션 숨김 */}
      {(() => {
        const highlights = (tradingValue || []).filter((tv: any) => {
          const vr = tv.volume_rate || 0;
          const cr = tv.change_rate || 0;
          return tv.flow_signal || (vr >= 200 && cr >= 10) || tv.is_new;
        });
        if (!highlights.length) return null;
        return (
        <section className="t-card rounded-xl p-4">
          <SectionHeader id="trading_value" timestamp={ts} count={highlights.length}>거래대금 이상 감지</SectionHeader>
          <div className="space-y-1.5">
            {highlights.map((tv: any, i: number) => {
              const vr = tv.volume_rate || 0;
              const cr = tv.change_rate || 0;
              const isSurge = vr >= 200 && cr >= 10;
              const detail = [...(crossSignal || []), ...(smartMoney || [])].find((s: any) => s.code === tv.code);
              const flowColor: Record<string, string> = {
                "자금 급유입": "bg-red-500/15 text-red-400",
                "자금 유입": "bg-amber-500/10 text-amber-400",
                "자금 소폭 이탈": "bg-blue-500/10 text-blue-400",
                "자금 이탈": "bg-blue-500/15 text-blue-500",
              };
              return (
              <div key={i} className="flex items-center justify-between p-2.5 t-card-alt rounded-lg gap-2 cursor-pointer hover:border-blue-500/30 hover:border transition-colors"
                onClick={() => detail ? setStockDetail(detail) : setStockDetail({ name: tv.name, code: tv.code, _noData: true })}>
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="w-5 h-5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-bold flex items-center justify-center shrink-0">
                    {tv.rank || i + 1}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-sm font-medium truncate">{tv.name}</span>
                      {tv.market && <span className="text-[9px] t-text-dim">{tv.market === "KOSDAQ" ? "코스닥" : "코스피"}</span>}
                      {tv.is_new && <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-400 font-medium">신규진입</span>}
                      {isSurge && <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-500/15 text-red-400 font-medium">폭증+급등</span>}
                      {tv.flow_signal && <span className={`text-[9px] px-1.5 py-0.5 rounded font-medium ${flowColor[tv.flow_signal] || "t-muted t-text-sub"}`}>{tv.flow_signal}</span>}
                    </div>
                    <div className="flex items-center gap-1.5 text-[10px] t-text-dim mt-0.5">
                      {vr > 0 && <span>거래량 {Math.round(vr)}%</span>}
                      {tv.trading_value && <span>· {(tv.trading_value / 100000000).toFixed(0)}억</span>}
                    </div>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className={`text-sm font-medium tabular-nums ${cr >= 0 ? "text-red-600" : "text-blue-600"}`}>
                    {cr >= 0 ? "+" : ""}{cr}%
                  </div>
                </div>
              </div>
              );
            })}
          </div>
        </section>
        );
      })()}

      {/* 예측 적중률 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="forecast" timestamp={ts}>예측 적중률</SectionHeader>
        {(() => {
          const preds = forecastAccuracy?.predictions || [];
          if (!preds.length) return <Empty />;
          // 날짜별 합산
          const byDate: Record<string, { total: number; hits: number; themes: { name: string; hit: boolean; confidence?: string }[] }> = {};
          for (const p of preds) {
            const d = p.date;
            if (!byDate[d]) byDate[d] = { total: 0, hits: 0, themes: [] };
            for (let i = 0; i < (p.themes || []).length; i++) {
              const hit = p.hits?.[i] ?? false;
              byDate[d].total++;
              if (hit) byDate[d].hits++;
              byDate[d].themes.push({ name: p.themes[i], hit, confidence: p.confidence?.[i] });
            }
          }
          const dates = Object.keys(byDate).sort().reverse();

          // 테마 대분류별 적중률
          const catMap: Record<string, { total: number; hits: number }> = {};
          for (const p of preds) {
            for (const det of p.details || []) {
              let cat = det.theme;
              if (/AI|반도체|HBM|5G/.test(cat)) cat = "AI/반도체";
              else if (/2차전지|전기차/.test(cat)) cat = "2차전지";
              else if (/바이오|헬스|제약/.test(cat)) cat = "바이오";
              else if (/건설|인프라/.test(cat)) cat = "건설";
              else if (/에너지|원전|신재생|유가|정유/.test(cat)) cat = "에너지";
              else if (/해운|물류/.test(cat)) cat = "해운";
              else if (/방산/.test(cat)) cat = "방산";
              else if (/증권|금융|밸류/.test(cat)) cat = "금융";
              else cat = "기타";
              if (!catMap[cat]) catMap[cat] = { total: 0, hits: 0 };
              catMap[cat].total++;
              if (det.hit) catMap[cat].hits++;
            }
          }
          const cats = Object.entries(catMap).sort((a, b) => b[1].total - a[1].total);
          const overall = forecastAccuracy?.overall_accuracy ?? 0;

          return (<>
          {/* 전체 적중률 + 테마별 신뢰도 */}
          <div className="flex items-center gap-3 mb-3">
            <div className="text-2xl font-bold t-text">{overall}%</div>
            <div className="text-xs t-text-sub">
              전체 적중률 ({forecastAccuracy?.total_hits}/{forecastAccuracy?.total_predictions})
            </div>
          </div>
          {/* 테마별 적중률 — 투자 신뢰도 지표 */}
          <div className="flex flex-wrap gap-1.5 mb-3">
            {cats.map(([cat, v]) => {
              const rate = v.total ? Math.round(v.hits / v.total * 100) : 0;
              const color = rate >= 70 ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/20" : rate >= 40 ? "bg-amber-500/10 text-amber-400 border-amber-500/20" : "bg-red-500/10 text-red-400 border-red-500/20";
              return (
                <span key={cat} className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${color}`}>
                  {cat} {rate}% <span className="opacity-60">({v.hits}/{v.total})</span>
                </span>
              );
            })}
          </div>
          <p className="text-[10px] t-text-dim mb-2">테마별 적중률이 높을수록 해당 테마 예측 신뢰도 높음</p>
          {/* 일별 합산 (최근 5일) */}
          <div className="space-y-1.5">
            {dates.slice(0, 5).map((d) => {
              const info = byDate[d];
              const rate = info.total ? Math.round(info.hits / info.total * 100) : 0;
              const hitThemes = [...new Set(info.themes.filter(t => t.hit).map(t => t.name))];
              const missThemes = [...new Set(info.themes.filter(t => !t.hit).map(t => t.name))];
              const expanded = forecastExpanded.has(d);
              const rateColor = rate >= 60 ? "text-emerald-400" : rate >= 40 ? "text-amber-400" : "text-red-400";
              const barColor = rate >= 60 ? "bg-emerald-400" : rate >= 40 ? "bg-amber-400" : "bg-red-400";
              return (
              <div key={d} className="t-card-alt rounded-lg overflow-hidden">
                <button
                  className="w-full p-2.5 flex items-center gap-3 text-left"
                  onClick={() => setForecastExpanded(prev => {
                    const next = new Set(prev);
                    next.has(d) ? next.delete(d) : next.add(d);
                    return next;
                  })}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs t-text-sub">{d}</span>
                      <span className={`text-xs font-medium ${rateColor}`}>{info.hits}/{info.total} 적중 ({rate}%)</span>
                    </div>
                    {/* 적중률 바 */}
                    <div className="w-full h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                      <div className={`h-full rounded-full transition-all duration-500 ${barColor}`} style={{ width: `${rate}%` }} />
                    </div>
                  </div>
                  <svg className={`w-4 h-4 shrink-0 t-text-dim transition-transform ${expanded ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path d="M19 9l-7 7-7-7" /></svg>
                </button>
                {expanded && (
                  <div className="px-2.5 pb-2.5 space-y-1.5">
                    {hitThemes.length > 0 && (
                      <div>
                        <div className="text-[10px] text-emerald-400 font-medium mb-1">✓ 적중 ({hitThemes.length})</div>
                        <div className="space-y-0.5">
                          {hitThemes.map((t, j) => (
                            <div key={j} className="flex items-center gap-1.5 text-[11px] t-text-sub py-0.5 px-1.5 rounded" style={{ background: 'var(--bg)' }}>
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
                              <span className="truncate">{t}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {missThemes.length > 0 && (
                      <div>
                        <div className="text-[10px] t-text-dim font-medium mb-1">✗ 미적중 ({missThemes.length})</div>
                        <div className="space-y-0.5">
                          {missThemes.map((t, j) => (
                            <div key={j} className="flex items-center gap-1.5 text-[11px] t-text-dim py-0.5 px-1.5 rounded" style={{ background: 'var(--bg)' }}>
                              <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: 'var(--border)' }} />
                              <span className="truncate">{t}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
              );
            })}
          </div>
          </>);
        })()}
      </section>

      {/* Volume Profile 지지/저항 경보 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="volume_profile" timestamp={ts} count={volumeProfile?.length ?? 0}>매물대 지지/저항</SectionHeader>
        <div className="space-y-1.5">
          {(volumeProfile || []).slice(0, 12).map((vp: any, i: number) => {
            const cp = vp.current_price || 0;
            const sup = vp.support || 0;
            const res = vp.resistance || 0;
            const status = vp.status || "";
            const hasAlert = !!status;
            const gapSup = sup && cp ? Math.round((cp - sup) / sup * 100) : 0;
            const gapRes = res && cp ? Math.round((res - cp) / cp * 100) : 0;
            const statusColor = status.includes("이탈") ? "bg-red-500/15 text-red-400" : status.includes("지지") ? "bg-emerald-500/15 text-emerald-400" : status.includes("돌파") ? "bg-blue-500/15 text-blue-400" : "bg-amber-500/15 text-amber-400";
            const detail = [...(crossSignal || []), ...(smartMoney || [])].find((s: any) => s.code === vp.code);
            return (
            <div key={i} className="p-2 t-card-alt rounded-lg cursor-pointer hover:border-blue-500/30 hover:border transition-colors"
              onClick={() => detail ? setStockDetail(detail) : setStockDetail({ name: vp.name, code: vp.code, _noData: true })}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium truncate">{vp.name}</span>
                {hasAlert && <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${statusColor}`}>{status}</span>}
              </div>
              <div className="flex items-center gap-2 text-[10px]">
                {cp > 0 && <span className="t-text">현재 {cp.toLocaleString()}원</span>}
                {sup > 0 && sup === res ? (
                  <span className="t-text-dim">매물대 {sup.toLocaleString()}<span className={gapSup >= 0 ? "text-red-500" : "text-blue-500"}> ({gapSup >= 0 ? "+" : ""}{gapSup}%)</span></span>
                ) : (<>
                  {sup > 0 && <span className="t-text-dim">지지 {sup.toLocaleString()}<span className={gapSup >= 0 ? "text-red-500" : "text-blue-500"}> ({gapSup >= 0 ? "+" : ""}{gapSup}%)</span></span>}
                  {res > 0 && <span className="t-text-dim">저항 {res.toLocaleString()}<span className={gapRes <= 0 ? "text-red-500" : "text-blue-500"}> ({gapRes >= 0 ? "+" : ""}{-gapRes}%)</span></span>}
                </>)}
              </div>
            </div>
            );
          })}
          <p className="text-[10px] t-text-dim">매물대 지지/저항선 근접 종목만 표시 · 현재가 대비 괴리율</p>
        </div>
        {!volumeProfile?.length && <Empty />}
      </section>

      {/* 신호 일관성 추적 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="consistency" timestamp={ts}>신호 변동 모니터</SectionHeader>
        {(() => {
          // 실제 변화가 있는 종목만 필터 + 변동 방향 분류
          const items = (signalConsistency || []).filter((sc: any) => {
            const sigs = (sc.signals || []).filter(Boolean);
            return new Set(sigs).size > 1;
          }).map((sc: any) => {
            const sigs = (sc.signals || []).filter(Boolean);
            const current = sc.current || sigs[sigs.length - 1] || "중립";
            const prev = sigs.length >= 2 ? sigs[sigs.length - 2] : "중립";
            const isBuy = current.includes("매수");
            const isSell = current.includes("매도");
            const wasBuy = prev.includes("매수");
            const wasSell = prev.includes("매도");
            let tag = "";
            let tagType: "danger" | "success" | "warning" | "default" = "default";
            if (isBuy && !wasBuy) { tag = "매수 전환"; tagType = "danger"; }
            else if (isSell && !wasSell) { tag = "매도 전환"; tagType = "success"; }
            else if (!isBuy && !isSell && wasBuy) { tag = "매수→중립"; tagType = "warning"; }
            else if (!isBuy && !isSell && wasSell) { tag = "매도→중립"; tagType = "warning"; }
            else { tag = "신호 변동"; tagType = "warning"; }
            // 정렬 우선순위: 매수전환 > 매도전환 > 나머지
            const order = tag === "매수 전환" ? 0 : tag === "매도 전환" ? 1 : 2;
            const detail = [...(crossSignal || []), ...(smartMoney || [])].find((s: any) => s.code === sc.code);
            return { ...sc, _tag: tag, _tagType: tagType, _current: current, _order: order, _detail: detail };
          });
          items.sort((a: any, b: any) => a._order - b._order);
          if (items.length === 0) return <div className="text-xs t-text-dim text-center py-4">최근 5일간 신호 변동 종목 없음</div>;
          return (<>
          <div className="space-y-1.5">
            {items.map((sc: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2 cursor-pointer hover:border-blue-500/30 hover:border transition-colors"
                onClick={() => sc._detail ? setStockDetail(sc._detail) : setStockDetail({ name: sc.name, code: sc.code, _noData: true })}>
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-medium truncate">{sc.name}</span>
                    {signalBadge(sc._current)}
                  </div>
                  <div className="text-[10px] t-text-dim mt-0.5">
                    {(sc.signals || []).filter(Boolean).join(" → ")}
                  </div>
                </div>
                <Badge variant={sc._tagType}>{sc._tag}</Badge>
              </div>
            ))}
          </div>
          <p className="text-[10px] t-text-dim mt-1.5">최근 5일 내 시그널이 변경된 종목만 표시</p>
          </>);
        })()}
      </section>

      {/* ===== 시스템 카테고리 ===== */}
      <div id="cat-system" className="scroll-mt-24 flex items-center gap-3 mt-6 mb-1">
        <div className="h-px flex-1" style={{ background: 'var(--border)' }} />
        <span className="text-[10px] font-semibold tracking-wider t-text-dim">시스템</span>
        <div className="h-px flex-1" style={{ background: 'var(--border)' }} />
      </div>


      {/* 장중 종목별 수급 */}
      <section className="t-card rounded-xl p-4">
        <SectionHeader id="intraday_flow" timestamp={ts} count={intradayStockFlow?.length ?? 0}>장중 종목별 수급</SectionHeader>
        {(() => {
          const nameMap: Record<string, string> = {};
          for (const s of allStockList) if (s.code) nameMap[s.code] = s.name;
          const scannerMap: Record<string, any> = {};
          for (const s of crossSignal || []) if (s.code) scannerMap[s.code] = s;
          for (const s of smartMoney || []) if (s.code && !scannerMap[s.code]) scannerMap[s.code] = s;
          const items = (intradayStockFlow || []).map((isf: any) => {
            const f = isf.foreign || 0;
            const inst = isf.institution || 0;
            const tag = f > 0 && inst > 0 ? "쌍끌이 매수" : f < 0 && inst < 0 ? "쌍끌이 매도" : null;
            return { ...isf, _name: nameMap[isf.code] || isf.code, _tag: tag, _sig: scannerMap[isf.code]?.signal || null, _detail: scannerMap[isf.code] };
          });
          // 쌍끌이 매수 → 쌍끌이 매도 → 나머지 (각 그룹 내 abs(foreign) 순)
          const order = (t: string | null) => t === "쌍끌이 매수" ? 0 : t === "쌍끌이 매도" ? 1 : 2;
          items.sort((a: any, b: any) => order(a._tag) - order(b._tag) || Math.abs(b.foreign || 0) - Math.abs(a.foreign || 0));
          return (<>
        <div className="space-y-1.5">
          {items.slice(0, 15).map((isf: any, i: number) => (
            <div key={i} className="flex items-center justify-between p-2 t-card-alt rounded-lg gap-2 cursor-pointer hover:border-blue-500/30 hover:border transition-colors"
              onClick={() => isf._detail ? setStockDetail(isf._detail) : setStockDetail({ name: isf._name, code: isf.code, _noData: true })}>
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-medium truncate">{isf._name}</span>
                  {isf._tag && (
                    <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${isf._tag === "쌍끌이 매수" ? "bg-red-500/15 text-red-400" : "bg-blue-500/15 text-blue-400"}`}>{isf._tag}</span>
                  )}
                  {isf._sig && signalBadge(isf._sig)}
                </div>
                <div className="text-xs t-text-sub">
                  {isf.code}
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
          <p className="text-[10px] t-text-dim">외국인 수급 변동 상위 종목 · 장중 가집계 기준</p>
        </div>
          </>);
        })()}
        {!intradayStockFlow?.length && <Empty />}
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
      {isIndexRoute && <>
      <div className="fixed bottom-0 left-0 right-0 z-20 px-3 pt-1.5 pb-1" style={{ background: 'var(--bg-nav)', borderTop: '1px solid var(--border)', paddingBottom: 'calc(env(safe-area-inset-bottom, 8px) + 4px)' }}>
        <div className="flex gap-1 rounded-xl p-1 max-w-2xl mx-auto relative" style={{ background: 'var(--bg-pill)' }}>
          {/* 슬라이딩 pill 배경 */}
          <div className="absolute rounded-lg transition-all duration-300 ease-out" style={{
            background: 'var(--bg-pill-active)',
            boxShadow: 'var(--shadow-card)',
            width: `calc(${100 / categories.length}% - 4px)`,
            height: 'calc(100% - 8px)',
            top: '4px',
            left: `calc(${categories.findIndex(c => c.id === activeCategory) * (100 / categories.length)}% + 2px)`,
          }} />
          {categories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => {
                setActiveCategory(cat.id);
                document.getElementById(cat.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
              }}
              className="relative z-10 flex-1 flex items-center justify-center gap-1 py-3 text-xs font-medium rounded-lg transition-colors duration-200"
              style={{ color: activeCategory === cat.id ? 'var(--text-pill-active)' : 'var(--text-tertiary)' }}
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
