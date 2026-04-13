import { useEffect, useState, useRef } from "react";
import { createPortal } from "react-dom";
import { TrendingUp, TrendingDown, Clock, DollarSign, BarChart3, Settings, ChevronDown, ChevronRight, RefreshCw, Loader2, Lock, TimerOff, Inbox, Check, X, LogIn, HelpCircle } from "lucide-react";
import { supabase, STORAGE_KEY, setAccessToken, fetchKisPrices } from "../lib/supabase";
import { getTradePct, setAlertConfig, getStrategySimulations } from "../lib/supabase";

interface Trade {
  id: string;
  code: string;
  name: string;
  side: string;
  order_price: number;
  filled_price: number | null;
  quantity: number;
  status: string;
  pnl_pct: number | null;
  sell_reason: string | null;
  sell_price: number | null;
  created_at: string;
  filled_at: string | null;
  sold_at: string | null;
}

function formatKRW(n: number) {
  return n.toLocaleString("ko-KR") + "원";
}

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

/** UTC ISO 문자열 → KST 날짜 (YYYY-MM-DD) */
function toKstDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const kst = new Date(d.getTime() + 9 * 60 * 60 * 1000);
  return kst.toISOString().slice(0, 10);
}

async function requestSell(tradeId: string): Promise<boolean> {
  const { error } = await supabase
    .from("auto_trades")
    .update({ status: "sell_requested" })
    .eq("id", tradeId)
    .eq("status", "filled");
  if (error) { console.error("매도 요청 실패:", error.message); return false; }
  return true;
}

async function requestSellAll(trades: Trade[]): Promise<number> {
  let count = 0;
  for (const t of trades) {
    if (await requestSell(t.id)) count++;
  }
  return count;
}

function parseBuyMode(mode: string | undefined): { chart: boolean; indicator: boolean; top_leader: boolean; all_leaders: boolean; fallback_top_leader: boolean } {
  const defaults = { chart: false, indicator: false, top_leader: false, all_leaders: false, fallback_top_leader: false };
  if (!mode) return defaults;
  // 레거시 값 변환
  if (mode === "and") return { chart: true, indicator: true, top_leader: false, all_leaders: false, fallback_top_leader: false };
  if (mode === "or") return { chart: true, indicator: false, top_leader: false, all_leaders: false, fallback_top_leader: false };
  if (mode === "leader") return { chart: false, indicator: false, top_leader: false, all_leaders: true, fallback_top_leader: false };
  if (mode === "none") return { chart: false, indicator: false, top_leader: false, all_leaders: false, fallback_top_leader: false };
  const flags = mode.split(",");
  return { chart: flags.includes("chart"), indicator: flags.includes("indicator"), top_leader: flags.includes("top_leader"), all_leaders: flags.includes("all_leaders"), fallback_top_leader: flags.includes("fallback_top_leader") };
}

function restoreSessionFromStorage(): { access_token: string | null; user: any } | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return null;
    const raw = JSON.parse(stored);
    const sessionStr = (raw?.value && raw?.__expire__) ? raw.value : stored;
    const parsed = typeof sessionStr === "string" ? JSON.parse(sessionStr) : raw;
    if (parsed?.user) return { access_token: parsed.access_token ?? null, user: parsed.user };
    return null;
  } catch { return null; }
}

export default function AutoTrader() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<any>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [selling, setSelling] = useState<Set<string>>(new Set());
  const [takeProfit, setTakeProfit] = useState(7.0);
  const [stopLoss, setStopLoss] = useState(-2.0);
  const [trailingStop, setTrailingStop] = useState(-3.0);
  const [prices, setPrices] = useState<Record<string, { price: number; changeRate: number }>>({});
  const [pricesLoading, setPricesLoading] = useState(true);
  const [priceRefreshing, setPriceRefreshing] = useState(false);
  const [priceTime, setPriceTime] = useState("");
  const [showPctEdit, setShowPctEdit] = useState(false);
  const [pctSaving, setPctSaving] = useState(false);
  const [pctResult, setPctResult] = useState("");
  const [sessionExpired, setSessionExpired] = useState(false);
  const sessionExpiredRef = useRef(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [showBuyHelp, setShowBuyHelp] = useState(false);
  const [buyToggles, setBuyToggles] = useState<{ chart: boolean; indicator: boolean; top_leader: boolean; all_leaders: boolean; fallback_top_leader: boolean }>({ chart: false, indicator: false, top_leader: false, all_leaders: false, fallback_top_leader: false });
  const [useResearchOptimal, setUseResearchOptimal] = useState(false);
  const [savedResearchOptimal, setSavedResearchOptimal] = useState(false);
  const [criteriaFilter, setCriteriaFilter] = useState(false);
  const [savedCriteriaFilter, setSavedCriteriaFilter] = useState(false);
  const [savedToggles, setSavedToggles] = useState<{ chart: boolean; indicator: boolean; top_leader: boolean; all_leaders: boolean; fallback_top_leader: boolean }>({ chart: false, indicator: false, top_leader: false, all_leaders: false, fallback_top_leader: false });
  const [buySaving, setBuySaving] = useState(false);
  const [tradeEnabled, setTradeEnabled] = useState(false);
  const [savedTradeEnabled, setSavedTradeEnabled] = useState(false);
  const [toastMsg, setToastMsg] = useState<{ text: string; type: "ok" | "fail" } | null>(null);
  const [strategyType, setStrategyType] = useState<"fixed" | "stepped" | "gapup">("fixed");
  const [savedStrategyType, setSavedStrategyType] = useState<"fixed" | "stepped" | "gapup">("fixed");
  const [strategySaving, setStrategySaving] = useState(false);
  const [steppedPreset, setSteppedPreset] = useState<"default" | "aggressive">("default");
  const [emergencySl, setEmergencySl] = useState<"none" | "-5" | "-15">("-5");
  const [savedEmergencySl, setSavedEmergencySl] = useState<"none" | "-5" | "-15">("-5");
  const [emergencySlSaving, setEmergencySlSaving] = useState(false);
  const [savedSteppedPreset, setSavedSteppedPreset] = useState<"default" | "aggressive">("default");
  const [showStrategyCompare, setShowStrategyCompare] = useState(false);
  const [strategyDetail, setStrategyDetail] = useState<"tv_momentum" | "gapup_sim" | "stepped_sim" | "fixed_sim" | "time_sim" | "tv_time_sim" | "api_leader_sim" | null>(null);
  const [strategyHelpOpen, setStrategyHelpOpen] = useState<string | null>(null);
  useEffect(() => {
    if (strategyDetail) { document.body.style.overflow = "hidden"; }
    return () => { document.body.style.overflow = ""; };
  }, [strategyDetail]);
  const [excludedDates, setExcludedDates] = useState<Set<string>>(new Set());
  const [simulations, setSimulations] = useState<any[]>([]);

  useEffect(() => {
    function loadData(u: any) {
      setUser(u);
      setAuthChecked(true);
      if (u) {
        fetchTrades();
        getTradePct().then(({ take_profit, stop_loss, trailing_stop, buy_signal_mode, criteria_filter }) => {
          setTakeProfit(take_profit);
          setStopLoss(stop_loss);
          setTrailingStop(trailing_stop);
          setCriteriaFilter(!!criteria_filter); setSavedCriteriaFilter(!!criteria_filter);
          const active = buy_signal_mode !== "none" && buy_signal_mode !== "";
          setTradeEnabled(active); setSavedTradeEnabled(active);
          if (buy_signal_mode === "research_optimal") {
            setUseResearchOptimal(true); setSavedResearchOptimal(true);
          } else {
            setUseResearchOptimal(false); setSavedResearchOptimal(false);
            const t = parseBuyMode(buy_signal_mode); setBuyToggles(t); setSavedToggles(t);
          }
        }).catch(() => {});
        // strategy_type 로드
        Promise.resolve(supabase.from("alert_config").select("strategy_type").limit(1).maybeSingle()).then(({ data: cfg }) => {
          if (cfg?.strategy_type) { setStrategyType(cfg.strategy_type); setSavedStrategyType(cfg.strategy_type); }
        }).catch(() => {});
        // stepped_preset 별도 로드 (컬럼 미존재 시 안전)
        Promise.resolve(supabase.from("alert_config").select("stepped_preset").limit(1).maybeSingle()).then(({ data: cfg }) => {
          if (cfg?.stepped_preset) { setSteppedPreset(cfg.stepped_preset); setSavedSteppedPreset(cfg.stepped_preset); }
        }).catch(() => {});
        // emergency_sl 로드
        Promise.resolve(supabase.from("alert_config").select("emergency_sl").limit(1).maybeSingle()).then(({ data: cfg }) => {
          if (cfg?.emergency_sl) { setEmergencySl(cfg.emergency_sl); setSavedEmergencySl(cfg.emergency_sl); }
        }).catch(() => {});
        getStrategySimulations().then(setSimulations);
      } else {
        setLoading(false);
      }
    }

    // localStorage에서 즉시 세션 복원 (getUser() hang 방지)
    const restored = restoreSessionFromStorage();
    if (restored) {
      setAccessToken(restored.access_token);
      loadData(restored.user);
    } else {
      setAuthChecked(true);
      setLoading(false);
    }

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (_event === "TOKEN_REFRESHED" || _event === "SIGNED_IN") {
        // 토큰 갱신/로그인 시 세션 만료 상태 해제
        sessionExpiredRef.current = false;
        setSessionExpired(false);
      }
      if (sessionExpiredRef.current) return;
      if (session?.user) {
        setAccessToken(session.access_token ?? null);
      }
      loadData(session?.user ?? null);
    });

    // 앱 복귀 시 세션 갱신 (백그라운드에서 access_token 만료 대응)
    const handleVisibility = () => {
      if (document.visibilityState !== "visible") return;
      // getSession()에 5초 타임아웃 — iOS PWA hang 방지
      const timeout = new Promise<null>((resolve) => setTimeout(() => resolve(null), 5000));
      Promise.race([
        supabase.auth.getSession().then(({ data: { session } }) => session),
        timeout,
      ]).then((session) => {
        if (session?.user) {
          setAccessToken(session.access_token ?? null);
          sessionExpiredRef.current = false;
          setSessionExpired(false);
          loadData(session.user);
        } else if (!sessionExpiredRef.current) {
          // 타임아웃 또는 세션 없음 — localStorage에서 재시도
          const fallback = restoreSessionFromStorage();
          if (fallback) {
            setAccessToken(fallback.access_token);
            loadData(fallback.user);
          }
        }
      }).catch(() => {});
    };
    document.addEventListener("visibilitychange", handleVisibility);

    return () => { subscription.unsubscribe(); document.removeEventListener("visibilitychange", handleVisibility); };
  }, []);

  async function fetchTrades() {
    setLoading(true);
    try {
      const { data, error } = await supabase
        .from("auto_trades")
        .select("*")
        .order("created_at", { ascending: false });
      if (error) {
        const msg = (error.message || "").toLowerCase();
        if (msg.includes("jwt") || msg.includes("token") || msg.includes("auth") || error.code === "PGRST301") {
          setSessionExpired(true); sessionExpiredRef.current = true;
          setUser(null);
        }
        setLoading(false);
        return;
      }
      if (data) {
        setTrades(data as Trade[]);
        // filled + 최근 7일 이내 sold 종목 모두 시세 조회 (시뮬레이션 open 포지션 대응)
        const recentCutoff = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
        const priceCodes = [...new Set((data as Trade[])
          .filter(t => t.status === "filled" || t.status === "sim_only" || (t.status === "sold" && t.created_at >= recentCutoff))
          .map(t => t.code).filter(Boolean))];
        if (priceCodes.length > 0) {
          // KIS proxy 최대 20개 제한 → 분할 호출
          const chunks: string[][] = [];
          for (let i = 0; i < priceCodes.length; i += 20) chunks.push(priceCodes.slice(i, i + 20));
          Promise.all(chunks.map(chunk => fetchKisPrices(chunk).catch(() => ({})))).then(results => {
            const map: Record<string, { price: number; changeRate: number }> = {};
            for (const kisData of results) {
              for (const [code, p] of Object.entries(kisData)) {
                if (p.current_price) map[code] = { price: p.current_price, changeRate: p.change_rate ?? 0 };
              }
            }
            if (Object.keys(map).length > 0) setPrices(map);
          }).catch(() => {}).finally(() => setPricesLoading(false));
        } else {
          setPricesLoading(false);
        }
      }
    } catch {
      setPricesLoading(false);
      // 네트워크 오류 등 — 세션 만료가 아님
    }
    setLoading(false);
  }

  async function refreshPrices() {
    if (priceRefreshing) return;
    const recentCutoff = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
    const codes = [...new Set(trades.filter(t => t.status === "filled" || t.status === "sim_only" || (t.status === "sold" && t.created_at >= recentCutoff)).map(t => t.code).filter(Boolean))];
    if (!codes.length) return;
    setPriceRefreshing(true);
    // 시세 + 시뮬 + 거래 내역을 모두 병렬 실행
    // KIS proxy 최대 20개 제한 → 분할 호출
    const chunks: string[][] = [];
    for (let i = 0; i < codes.length; i += 20) chunks.push(codes.slice(i, i + 20));
    const pricePromise = Promise.all(chunks.map(chunk => fetchKisPrices(chunk).catch(() => ({})))).catch(() => null);
    getStrategySimulations().then(setSimulations).catch(() => {});
    Promise.resolve(supabase.from("auto_trades").select("*").order("created_at", { ascending: false }))
      .then(({ data }) => { if (data) setTrades(data as Trade[]); }).catch(() => {});
    try {
      const results = await pricePromise;
      if (results) {
        const map: Record<string, { price: number; changeRate: number }> = {};
        for (const kisData of results) {
          for (const [code, p] of Object.entries(kisData)) {
            if (p.current_price) map[code] = { price: p.current_price, changeRate: p.change_rate ?? 0 };
          }
        }
        if (Object.keys(map).length > 0) {
          setPrices(map);
          const now = new Date();
          const h = now.getHours();
          setPriceTime(`${h < 12 ? "오전" : "오후"} ${h === 0 ? 12 : h > 12 ? h - 12 : h}:${now.getMinutes().toString().padStart(2, "0")}`);
        } else {
          setToastMsg({ text: "시세 조회 실패 — 장 운영시간에 다시 시도해주세요", type: "fail" });
          setTimeout(() => setToastMsg(null), 3000);
        }
      }
    } catch (e) {
      console.warn("시세 조회 실패:", e);
      setToastMsg({ text: "시세 조회 실패 — 네트워크를 확인해주세요", type: "fail" });
      setTimeout(() => setToastMsg(null), 3000);
    }
    setPriceRefreshing(false);
  }

  const active = trades.filter((t) => t.status === "filled");
  const pending = trades.filter((t) => t.status === "pending" || t.status === "sell_requested");
  const closed = trades.filter((t) => t.status === "sold");

  const totalTrades = closed.length;
  const wins = closed.filter((t) => (t.pnl_pct ?? 0) > 0).length;
  const losses = closed.filter((t) => (t.pnl_pct ?? 0) < 0).length;
  const winRate = totalTrades > 0 ? ((wins / totalTrades) * 100).toFixed(1) : "0.0";
  const avgPnl = totalTrades > 0 ? (closed.reduce((s, t) => s + (t.pnl_pct ?? 0), 0) / totalTrades).toFixed(2) : "0.00";
  const totalPnl = closed.reduce((s, t) => {
    const buy = t.filled_price ?? t.order_price;
    const pnl = t.sell_price && buy > 0 ? (t.sell_price - buy) * t.quantity : (t.pnl_pct ?? 0) / 100 * buy * t.quantity;
    return s + pnl;
  }, 0);
  const totalInvested = active.reduce((s, t) => s + (t.filled_price ?? t.order_price) * t.quantity, 0);

  // 미실현 포함 계산
  const [summaryTab, setSummaryTab] = useState<"realized" | "all">("realized");
  const unrealizedPnl = active.reduce((s, t) => {
    const bp = t.filled_price ?? t.order_price;
    const cp = prices[t.code]?.price || 0;
    return s + (cp > 0 && bp > 0 ? (cp - bp) * t.quantity : 0);
  }, 0);
  const unrealizedPnlPct = active.map(t => {
    const bp = t.filled_price ?? t.order_price;
    const cp = prices[t.code]?.price || 0;
    return cp > 0 && bp > 0 ? (cp - bp) / bp * 100 : 0;
  });
  const allTotalTrades = totalTrades + active.length;
  const allWins = wins + unrealizedPnlPct.filter(p => p > 0).length;
  const allLosses = losses + unrealizedPnlPct.filter(p => p < 0).length;
  const allWinRate = allTotalTrades > 0 ? ((allWins / allTotalTrades) * 100).toFixed(1) : "0.0";
  const allAvgPnl = allTotalTrades > 0 ? ((closed.reduce((s, t) => s + (t.pnl_pct ?? 0), 0) + unrealizedPnlPct.reduce((s, p) => s + p, 0)) / allTotalTrades).toFixed(2) : "0.00";
  const allTotalPnl = totalPnl + unrealizedPnl;

  async function handleSell(trade: Trade) {
    setSelling(prev => new Set(prev).add(trade.id));
    const ok = await requestSell(trade.id);
    if (ok) {
      setTrades(prev => prev.map(t => t.id === trade.id ? { ...t, status: "sell_requested" } : t));
    }
    setSelling(prev => { const s = new Set(prev); s.delete(trade.id); return s; });
  }

  async function handleSellAll() {
    if (!active.length || !confirm(`보유 ${active.length}종목 전체 매도 요청하시겠습니까?`)) return;
    setSelling(new Set(active.map(t => t.id)));
    const count = await requestSellAll(active);
    if (count > 0) {
      setTrades(prev => prev.map(t =>
        t.status === "filled" ? { ...t, status: "sell_requested" } : t
      ));
    }
    setSelling(new Set());
  }

  if (loading || !authChecked) {
    return (
      <div className="text-center py-20 t-text-sub">
        <Loader2 size={28} className="mx-auto mb-2 t-text-sub animate-spin" />
        데이터 로딩 중...
      </div>
    );
  }

  const handleLoginSuccess = (u: any, token: string) => {
    setAccessToken(token); setUser(u); setSessionExpired(false); sessionExpiredRef.current = false; setShowLoginModal(false);
    fetchTrades();
    getTradePct().then(({ take_profit, stop_loss, trailing_stop, buy_signal_mode, criteria_filter }) => {
      setTakeProfit(take_profit); setStopLoss(stop_loss); setTrailingStop(trailing_stop);
      setCriteriaFilter(!!criteria_filter); setSavedCriteriaFilter(!!criteria_filter);
      const active = buy_signal_mode !== "none" && buy_signal_mode !== "";
      setTradeEnabled(active); setSavedTradeEnabled(active);
      if (buy_signal_mode === "research_optimal") {
        setUseResearchOptimal(true); setSavedResearchOptimal(true);
      } else {
        setUseResearchOptimal(false); setSavedResearchOptimal(false);
        const t = parseBuyMode(buy_signal_mode); setBuyToggles(t); setSavedToggles(t);
      }
    }).catch(() => {});
    Promise.resolve(supabase.from("alert_config").select("strategy_type").limit(1).maybeSingle()).then(({ data: cfg }) => {
      if (cfg?.strategy_type) { setStrategyType(cfg.strategy_type); setSavedStrategyType(cfg.strategy_type); }
    }).catch(() => {});
    Promise.resolve(supabase.from("alert_config").select("stepped_preset").limit(1).maybeSingle()).then(({ data: cfg }) => {
      if (cfg?.stepped_preset) { setSteppedPreset(cfg.stepped_preset); setSavedSteppedPreset(cfg.stepped_preset); }
    }).catch(() => {});
    getStrategySimulations().then(setSimulations);
  };

  if (!user) {
    return (
      <>
        <div className="text-center py-20 t-text-sub">
          {sessionExpired ? <TimerOff size={32} className="mx-auto mb-3 t-text-sub" /> : <Lock size={32} className="mx-auto mb-3 t-text-sub" />}
          <div className="text-sm font-medium t-text mb-1">{sessionExpired ? "세션이 만료되었습니다" : "로그인이 필요합니다"}</div>
          <div className="text-xs t-text-dim mb-5">{sessionExpired ? "다시 로그인해주세요" : "모의투자 현황을 확인하려면 로그인해주세요"}</div>
          <button onClick={() => setShowLoginModal(true)}
            className="inline-flex items-center gap-2 text-[13px] font-medium px-5 py-2.5 rounded-xl text-white bg-blue-600 hover:bg-blue-500 transition">
            <LogIn size={15} />
            로그인
          </button>
        </div>
        {showLoginModal && <LoginModal onClose={() => setShowLoginModal(false)} onSuccess={handleLoginSuccess} />}
      </>
    );
  }

  if (trades.length === 0) {
    return (
      <div className="text-center py-20 t-text-sub">
        <Inbox size={32} className="mx-auto mb-3 t-text-sub" />
        <div className="text-sm font-medium t-text mb-1">매매 이력 없음</div>
        <div className="text-xs t-text-dim">자동매매가 실행되면 여기에 표시됩니다</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 모의투자 실행 */}
      <div className="rounded-xl p-3 border" style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}>
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold t-text">모의투자 실행</span>
          <button onClick={() => setTradeEnabled(!tradeEnabled)}
            className={`w-10 h-5 rounded-full transition-colors relative ${tradeEnabled ? "bg-blue-500" : "bg-gray-300"}`}>
            <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${tradeEnabled ? "translate-x-5" : "translate-x-0.5"}`} />
          </button>
        </div>
        {tradeEnabled !== savedTradeEnabled && (
          <div className="flex items-center gap-2 mt-2">
            <button disabled={buySaving} onClick={async () => {
              setBuySaving(true);
              if (!tradeEnabled) {
                const ok = await setAlertConfig({ buy_signal_mode: "none" });
                if (ok) { setSavedTradeEnabled(false); setSavedResearchOptimal(false); setUseResearchOptimal(false); setSavedToggles({ chart: false, indicator: false, top_leader: false, all_leaders: false, fallback_top_leader: false }); setBuyToggles({ chart: false, indicator: false, top_leader: false, all_leaders: false, fallback_top_leader: false }); setToastMsg({ text: "모의투자 중지", type: "ok" }); }
                else { setTradeEnabled(savedTradeEnabled); setToastMsg({ text: "저장 실패", type: "fail" }); }
              } else {
                const ok = await setAlertConfig({ buy_signal_mode: "research_optimal" });
                if (ok) { setSavedTradeEnabled(true); setSavedResearchOptimal(true); setUseResearchOptimal(true); setToastMsg({ text: "모의투자 재개 (연구 최적)", type: "ok" }); }
                else { setTradeEnabled(savedTradeEnabled); setToastMsg({ text: "저장 실패", type: "fail" }); }
              }
              setTimeout(() => setToastMsg(null), 2500); setBuySaving(false);
            }} className="flex-1 text-[11px] font-medium py-1.5 rounded-lg text-white bg-blue-600 hover:bg-blue-500 transition disabled:opacity-40">
              {buySaving ? "저장 중..." : "확인"}
            </button>
            <button onClick={() => setTradeEnabled(savedTradeEnabled)} className="text-[11px] font-medium py-1.5 px-3 rounded-lg t-text-sub border transition hover:opacity-80" style={{ borderColor: "var(--border)" }}>취소</button>
          </div>
        )}
      </div>

      {/* 투자 전략 선택 */}
      <div className="rounded-xl p-3 border" style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}>
        <div className="text-xs font-semibold t-text mb-1.5">투자 전략</div>
        {/* 현재 적용 중인 설정 */}
        <div className="text-[10px] t-text-dim mb-2 px-2.5 py-1.5 rounded-lg flex items-center gap-1.5 flex-wrap" style={{ background: "var(--bg)" }}>
          <span className="font-medium t-text-sub">적용 중:</span>
          <span className={savedStrategyType === "gapup" ? "text-red-500" : savedStrategyType === "stepped" ? "text-blue-500" : "text-amber-500"}>
            {savedStrategyType === "gapup" ? "거래대금 모멘텀" : savedStrategyType === "stepped" ? `Stepped Trailing${savedSteppedPreset === "aggressive" ? " (공격형)" : ""}` : "고정 익절/손절"}
          </span>
          <span className="t-text-dim">·</span>
          <span className={savedResearchOptimal ? "text-indigo-500" : "text-emerald-500"}>
            {savedResearchOptimal ? "연구 최적 전략" : (() => {
              const { chart, indicator, top_leader, all_leaders, fallback_top_leader } = savedToggles;
              if (top_leader) return "대장주 1위";
              const parts = [chart && "차트", indicator && "지표", all_leaders && "대장주"].filter(Boolean) as string[];
              if (parts.length === 0 && !fallback_top_leader) return "매집 중지";
              let desc = parts.join("+");
              if (fallback_top_leader) desc += desc ? "+FB" : "대장주 1위";
              return desc || "수동";
            })()}
          </span>
        </div>
        <div className="flex gap-2">
          {(["gapup", "stepped", "fixed"] as const).map(st => (
            <button key={st} onClick={() => {
              setStrategyType(st);
              if (st !== "fixed") setShowPctEdit(false);
            }}
              className={`flex-1 text-[11px] py-2 rounded-lg font-medium transition ${
                strategyType === st
                  ? (st === "gapup" ? "bg-red-500 text-white" : "bg-blue-600 text-white")
                  : "t-text-sub hover:t-text"
              }`}
              style={strategyType !== st ? { background: "var(--bg)", border: "1px solid var(--border)" } : {}}>
              {st === "gapup" ? "거래대금 모멘텀" : st === "stepped" ? "Stepped Trailing" : "고정 익절/손절"}
            </button>
          ))}
        </div>
        {strategyType === "gapup" && (
          <div className="mt-2 p-3 rounded-lg text-[10px] t-text-sub leading-relaxed space-y-2" style={{ background: "var(--bg)" }}>
            <div className="space-y-1">
              <div className="flex items-center gap-2"><span className="font-semibold" style={{ color: "#ef4444" }}>선정</span><span className="t-text-dim">거래대금 상위 + 상승 출발 + 갭 &lt;10%</span></div>
              <div className="flex items-center gap-2"><span className="font-semibold" style={{ color: "#f59e0b" }}>가점</span><span className="t-text-dim">윗꼬리&gt;3% ×2.0 · 음봉 ×1.2 · 회전율&lt;5% ×1.5 · 연속3일↑ ×0.7</span></div>
              <div className="flex items-center gap-2"><span className="font-semibold" style={{ color: "#3b82f6" }}>쿨다운</span><span className="t-text-dim">전일 매매 종목 1일 제외</span></div>
              <div className="flex items-center gap-2"><span className="font-semibold" style={{ color: "#22c55e" }}>매도</span><span className="t-text-dim">09:05 스캔 → TOP2 매수 → 15:15 청산</span></div>
            </div>
            <div className="pt-1.5 border-t t-border-light text-[9px] t-text-dim">
              상위 2종목 | 자본 100% 배분 | 오버나이트 리스크 없음
            </div>
          </div>
        )}
        {strategyType === "stepped" && (
          <details className="mt-2 rounded-lg" style={{ background: "var(--bg)" }}>
            <summary className="flex items-center gap-1 p-2.5 text-[9px] font-medium t-text-sub cursor-pointer hover:t-text transition select-none list-none [&::-webkit-details-marker]:hidden">
              <ChevronRight size={10} className="transition-transform [[open]>&]:rotate-90 shrink-0" />
              Step 구간
              <span className="ml-auto text-[8px] font-semibold" style={{ color: savedSteppedPreset === "aggressive" ? "#2563eb" : "var(--text-secondary)" }}>
                {savedSteppedPreset === "aggressive" ? "공격형" : "기본"}
              </span>
            </summary>
            <div className="px-2.5 pb-2.5">
              <div className="flex gap-1 mb-2">
                {([["default", "기본"], ["aggressive", "공격형"]] as const).map(([key, label]) => (
                  <button key={key} onClick={() => setSteppedPreset(key)}
                    className="flex-1 text-[9px] font-medium py-1 rounded-md transition"
                    style={{ background: steppedPreset === key ? "var(--blue-600, #2563eb)" : "var(--bg-muted)", color: steppedPreset === key ? "#fff" : "var(--text-secondary)" }}>
                    {label}
                  </button>
                ))}
              </div>
              <div className="space-y-1">
                {(steppedPreset === "aggressive" ? [
                  { trigger: "+7%", stop: "0%", color: "#94a3b8", barW: "20%" },
                  { trigger: "+15%", stop: "+7%", color: "#22c55e", barW: "40%" },
                  { trigger: "+20%", stop: "+15%", color: "#22c55e", barW: "60%" },
                  { trigger: "+25%", stop: "+20%", color: "#16a34a", barW: "80%" },
                  { trigger: "+30%+", stop: `고점${trailingStop}%`, color: "#15803d", barW: "100%" },
                ] : [
                  { trigger: "+5%", stop: "0%", color: "#94a3b8", barW: "20%" },
                  { trigger: "+10%", stop: "+5%", color: "#22c55e", barW: "40%" },
                  { trigger: "+15%", stop: "+10%", color: "#22c55e", barW: "60%" },
                  { trigger: "+20%", stop: "+15%", color: "#16a34a", barW: "80%" },
                  { trigger: "+25%+", stop: `고점${trailingStop}%`, color: "#15803d", barW: "100%" },
                ]).map((s, i) => (
                  <div key={s.trigger} className="flex items-center gap-2 text-[10px]">
                    <div className="w-1 h-4 rounded-full shrink-0" style={{ background: s.color, opacity: 0.5 + i * 0.12 }} />
                    <span className="w-11 shrink-0 font-semibold tabular-nums t-text">{s.trigger}</span>
                    <div className="flex-1 h-1 rounded-full overflow-hidden" style={{ background: 'var(--bg-muted)' }}>
                      <div className="h-full rounded-full" style={{ width: s.barW, background: s.color, opacity: 0.4 }} />
                    </div>
                    <span className="w-16 shrink-0 text-right tabular-nums t-text-sub">stop {s.stop}</span>
                  </div>
                ))}
              </div>
              {steppedPreset !== savedSteppedPreset && (
                <button onClick={async () => {
                  const ok = await setAlertConfig({ stepped_preset: steppedPreset });
                  if (ok) setSavedSteppedPreset(steppedPreset);
                  setToastMsg({ text: ok ? "Step 구간 변경 완료" : "변경 실패", type: ok ? "ok" : "fail" });
                }}
                  className="w-full mt-2 text-[10px] font-medium py-1 rounded-md text-white bg-blue-600 hover:bg-blue-500 transition">
                  Step 구간 변경 확인
                </button>
              )}
            </div>
          </details>
        )}
        {strategyType !== savedStrategyType && (
          <button disabled={strategySaving} onClick={async () => {
            setStrategySaving(true);
            const ok = await setAlertConfig({ strategy_type: strategyType });
            if (ok) setSavedStrategyType(strategyType);
            setToastMsg({ text: ok ? "전략 변경 완료" : "전략 변경 실패", type: ok ? "ok" : "fail" });
            setStrategySaving(false);
          }}
            className="w-full mt-2 text-[11px] font-medium py-1.5 rounded-lg text-white bg-blue-600 hover:bg-blue-500 transition disabled:opacity-40">
            {strategySaving ? "저장 중..." : "전략 변경 확인"}
          </button>
        )}
        {/* 익절/손절 설정 — 전략 카드 내부 (갭업에서는 숨김) */}
        {strategyType !== "gapup" && (
        <div className="mt-3 pt-3" style={{ borderTop: "1px solid var(--border)" }}>
          <div className="flex items-center justify-between">
            {strategyType === "stepped" ? (
              <div className="flex items-center gap-3 text-[11px]">
                <div className="flex items-center gap-1">
                  <span className="t-text-dim">익절</span>
                  <span className="font-semibold" style={{ color: "var(--success)" }}>자동추종</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="t-text-dim">손절</span>
                  <span className="font-semibold" style={{ color: "#3b82f6" }}>{stopLoss}%</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="t-text-dim">급락</span>
                  <span className="font-semibold" style={{ color: "#f59e0b" }}>{trailingStop}%</span>
                </div>
              </div>
            ) : (
            <div className="flex items-center gap-3 text-[11px]">
              {[
                { label: "익절", value: `+${takeProfit}%↑`, color: "var(--success)" },
                { label: "손절", value: `${stopLoss}%`, color: "#3b82f6" },
                { label: "급락", value: `${trailingStop}%`, color: "#f59e0b" },
              ].map(item => (
                <div key={item.label} className="flex items-center gap-1">
                  <span className="t-text-dim">{item.label}</span>
                  <span className="font-semibold" style={{ color: item.color }}>{item.value}</span>
                </div>
              ))}
            </div>
            )}
            <button onClick={() => setShowPctEdit(!showPctEdit)}
              className="p-1 rounded-lg t-text-dim hover:t-text transition">
              <Settings size={13} />
            </button>
          </div>
        {showPctEdit && strategyType === "stepped" && (
          <div className="mt-2.5 pt-2.5 space-y-2.5" style={{ borderTop: "1px solid var(--border)" }}>
            {/* 익절 — 수치 대신 설명 */}
            <div className="p-2.5 rounded-lg" style={{ background: "var(--bg)" }}>
              <div className="text-[9px] font-medium mb-1.5" style={{ color: "var(--success)" }}>익절</div>
              <div className="text-[10px] t-text-sub leading-relaxed">Stepped 전략은 고정 익절 없이, 수익률 구간별로 stop이 자동 상향되어 상승분을 최대한 추종합니다.</div>
            </div>
            {/* 손절 + 급락 입력 + 저장 버튼 한 줄 */}
            <div className="flex gap-2 items-end">
              {[
                { label: "손절", desc: "매수가 대비 기본 하한선", value: stopLoss, set: setStopLoss, min: -30, max: -0.5, fallback: -2.0, color: "#3b82f6" },
                { label: "급락", desc: "+25% 이상 고점 대비", value: trailingStop, set: setTrailingStop, min: -30, max: -0.5, fallback: -3.0, color: "#f59e0b" },
              ].map(f => (
                <div key={f.label} className="flex-1">
                  <div className="text-[9px] font-medium mb-0.5" style={{ color: f.color }}>{f.label} (%)</div>
                  <div className="text-[8px] t-text-dim mb-1">{f.desc}</div>
                  <input type="number" step="0.5" min={f.min} max={f.max} value={f.value}
                    onChange={e => f.set(parseFloat(e.target.value) || f.fallback)}
                    className="w-full text-[12px] px-2.5 py-1.5 rounded-lg t-text outline-none transition focus:ring-1 focus:ring-blue-500/30"
                    style={{ background: "var(--bg)", border: "1px solid var(--border)" }} />
                </div>
              ))}
              <div className="flex items-center gap-1.5 shrink-0 pb-0.5">
                <button disabled={pctSaving} onClick={async () => {
                  setPctSaving(true);
                  const ok = await setAlertConfig({ stop_loss_pct: stopLoss, trailing_stop_pct: trailingStop });
                  setPctResult(ok ? "saved" : "failed");
                  setTimeout(() => setPctResult(""), 2000);
                  setPctSaving(false);
                }}
                  className="text-[11px] font-medium py-1.5 px-4 rounded-lg text-white bg-blue-600 hover:bg-blue-500 transition disabled:opacity-40">
                  {pctSaving ? "저장 중..." : "저장"}
                </button>
                {pctResult && (
                  <div className={`flex items-center gap-1 text-[10px] ${pctResult === "failed" ? "text-red-400" : "text-green-400"}`}>
                    {pctResult === "failed" ? <X size={11} /> : <Check size={11} />}
                    {pctResult === "failed" ? "실패" : "완료"}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
        {showPctEdit && strategyType !== "stepped" && (
          <div className="mt-2.5 pt-2.5 space-y-2.5" style={{ borderTop: "1px solid var(--border)" }}>
            <div className="flex gap-2 items-end">
              {[
                { label: "익절", value: takeProfit, set: setTakeProfit, min: 0.5, max: 30, fallback: 7.0, color: "var(--success)" },
                { label: "손절", value: stopLoss, set: setStopLoss, min: -30, max: -0.5, fallback: -2.0, color: "#3b82f6" },
                { label: "급락", value: trailingStop, set: setTrailingStop, min: -30, max: -0.5, fallback: -3.0, color: "#f59e0b" },
              ].map(f => (
                <div key={f.label} className="flex-1">
                  <div className="text-[9px] font-medium mb-1" style={{ color: f.color }}>{f.label} (%)</div>
                  <input type="number" step="0.5" min={f.min} max={f.max} value={f.value}
                    onChange={e => f.set(parseFloat(e.target.value) || f.fallback)}
                    className="w-full text-[12px] px-2.5 py-1.5 rounded-lg t-text outline-none transition focus:ring-1 focus:ring-blue-500/30"
                    style={{ background: "var(--bg)", border: "1px solid var(--border)" }} />
                </div>
              ))}
              <div className="flex items-center gap-1.5 shrink-0 pb-0.5">
                <button disabled={pctSaving} onClick={async () => {
                  setPctSaving(true);
                  const ok = await setAlertConfig({ take_profit_pct: takeProfit, stop_loss_pct: stopLoss, trailing_stop_pct: trailingStop });
                  setPctResult(ok ? "saved" : "failed");
                  setTimeout(() => setPctResult(""), 2000);
                  setPctSaving(false);
                }}
                  className="text-[11px] font-medium py-1.5 px-4 rounded-lg text-white bg-blue-600 hover:bg-blue-500 transition disabled:opacity-40">
                  {pctSaving ? "저장 중..." : "저장"}
                </button>
                {pctResult && (
                  <div className={`flex items-center gap-1 text-[10px] ${pctResult === "failed" ? "text-red-400" : "text-green-400"}`}>
                    {pctResult === "failed" ? <X size={11} /> : <Check size={11} />}
                    {pctResult === "failed" ? "실패" : "완료"}
                  </div>
                )}
              </div>
            </div>
            {/* 보유일별 익절/보유 기준 미니 테이블 */}
            <div className="text-[9px] t-text-dim p-2 rounded-lg" style={{ background: "var(--bg)" }}>
              <div className="flex gap-1 mb-1 font-medium t-text-sub">
                {["D+0","D+1","D+2","D+3","D+4+"].map(d => <span key={d} className="flex-1 text-center">{d}</span>)}
              </div>
              <div className="flex gap-1" style={{ color: "var(--success)" }}>
                {[0,3,8,13,18].map((off,i) => <span key={i} className="flex-1 text-center font-medium">+{takeProfit+off}%</span>)}
              </div>
              <div className="flex gap-1 mt-0.5 t-text-dim">
                {[3,5,8,12,15].map((thr,i) => <span key={i} className="flex-1 text-center">≥{thr}%보유</span>)}
              </div>
            </div>
          </div>
        )}
        </div>
        )}
        {/* 매집 종목 선정 기준 */}
        <div className="mt-3 pt-3" style={{ borderTop: "1px solid var(--border)" }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold t-text">매집 종목 선정</span>
            {strategyType !== "gapup" && (
            <button onClick={(e) => { e.preventDefault(); setShowBuyHelp(true); }} className="t-text-dim hover:t-text transition">
              <HelpCircle size={13} />
            </button>
            )}
          </div>
          {/* 모드 전환: 연구 최적 vs 수동 설정 (갭업에서는 숨김) */}
          {strategyType !== "gapup" && (
          <div className="flex gap-1 p-0.5 rounded-lg mb-2" style={{ background: "var(--bg-pill)" }}>
            <button onClick={() => setUseResearchOptimal(true)}
              className={`flex-1 text-[11px] font-medium py-1.5 rounded-md transition ${useResearchOptimal ? "t-text shadow-sm" : "t-text-dim"}`}
              style={useResearchOptimal ? { background: "var(--bg-pill-active)" } : {}}>
              연구 최적 전략
            </button>
            <button onClick={() => setUseResearchOptimal(false)}
              className={`flex-1 text-[11px] font-medium py-1.5 rounded-md transition ${!useResearchOptimal ? "t-text shadow-sm" : "t-text-dim"}`}
              style={!useResearchOptimal ? { background: "var(--bg-pill-active)" } : {}}>
              수동 설정
            </button>
          </div>
          )}
          {/* 연구 최적 전략 설명 (갭업은 항상 표시) */}
          {(strategyType === "gapup" || useResearchOptimal) && (
            <div>
              <div className="p-3 rounded-lg text-[10px] t-text-sub leading-relaxed space-y-2" style={{ background: "var(--bg)" }}>
                {strategyType === "gapup" ? (
                  <>
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold shrink-0" style={{ color: "#a855f7" }}>손절</span>
                        <div className="flex items-center gap-1.5">
                          {([["none", "없음"], ["-5", "-5%"], ["-15", "-15%"]] as const).map(([val, label]) => (
                            <button key={val} onClick={() => setEmergencySl(val as any)}
                              className={`px-2.5 py-0.5 rounded-md text-[9px] font-semibold transition-all ${emergencySl === val ? "text-white shadow-sm" : "t-text-dim hover:opacity-80"}`}
                              style={emergencySl === val ? { background: val === "none" ? "#3b82f6" : val === "-5" ? "#f59e0b" : "#ef4444" } : { background: "var(--bg-card-alt)" }}>
                              {label}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="flex items-center justify-between ml-[calc(2ch+0.5rem)] -mt-0.5">
                        <span className="text-[8px] t-text-dim">
                          {emergencySl === "none" ? "15:15 전량 청산 (손절 없음)" : `장중 ${emergencySl}% 도달 시 손절`}
                        </span>
                        {emergencySl !== savedEmergencySl && (
                          <button onClick={async () => {
                            setEmergencySlSaving(true);
                            const ok = await setAlertConfig({ emergency_sl: emergencySl });
                            if (ok) {
                              setSavedEmergencySl(emergencySl);
                              setToastMsg({ text: `손절 옵션 변경: ${emergencySl === "none" ? "없음" : emergencySl + "%"}`, type: "ok" });
                            } else {
                              setEmergencySl(savedEmergencySl);
                              setToastMsg({ text: "손절 옵션 변경 실패", type: "fail" });
                            }
                            setTimeout(() => setToastMsg(null), 2500);
                            setEmergencySlSaving(false);
                          }} disabled={emergencySlSaving}
                            className="text-[9px] font-semibold px-3 py-0.5 rounded-md bg-emerald-500 text-white hover:bg-emerald-400 transition disabled:opacity-50 shrink-0 ml-2">
                            {emergencySlSaving ? "저장 중..." : "변경 확인"}
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="pt-1.5 border-t t-border-light text-[9px] t-text-dim">
                      자본 100% 배분
                    </div>
                  </>
                ) : (
                  <>
                    <div className="text-[11px] font-semibold t-text mb-1">5팩터 스코어 Top-2 자동 선정</div>
                    <div className="space-y-1">
                      <div className="flex items-center gap-2"><span className="font-semibold" style={{ color: "#3b82f6" }}>API 매수</span><span className="t-text-dim">+30점 (적극매수 +10 추가)</span></div>
                      <div className="flex items-center gap-2"><span className="font-semibold" style={{ color: "#8b5cf6" }}>Vision 매수</span><span className="t-text-dim">+20점 (적극매수 +5 추가)</span></div>
                      <div className="flex items-center gap-2"><span className="font-semibold" style={{ color: "#f59e0b" }}>대장주 1등</span><span className="t-text-dim">+25점 / 전체 +15점</span></div>
                      <div className="flex items-center gap-2"><span className="font-semibold" style={{ color: "#22c55e" }}>저가주</span><span className="t-text-dim">&lt;2만원 +5점</span></div>
                      <div className="flex items-center gap-2"><span className="font-semibold" style={{ color: "#ef4444" }}>급락반등</span><span className="t-text-dim">-10%↓ &amp; 외인50만주↑ +35점</span></div>
                    </div>
                    <div className="pt-1.5 border-t t-border-light text-[9px] t-text-dim">
                      가격 &lt; 5만원 | 최소 20점 | 상위 2종목 | 자본 100% 배분
                    </div>
                  </>
                )}
                {/* Criteria 가점 필터 — Stepped Trailing 선택 시에만 */}
                {strategyType === "stepped" && (
                <div className="mt-2 pt-2 border-t t-border-light">
                  <div className="flex items-center justify-between mb-1">
                    <div className="text-[11px] font-medium t-text">Criteria 가점 필터</div>
                  <button onClick={async () => {
                    const next = !criteriaFilter;
                    setCriteriaFilter(next);
                    const ok = await setAlertConfig({ criteria_filter: next });
                    if (ok) { setSavedCriteriaFilter(next); setToastMsg({ text: next ? "Criteria 필터 ON" : "Criteria 필터 OFF", type: "ok" }); }
                    else { setCriteriaFilter(savedCriteriaFilter); setToastMsg({ text: "저장 실패", type: "fail" }); }
                    setTimeout(() => setToastMsg(null), 2500);
                  }} className={`w-10 h-5 rounded-full transition-colors relative ${criteriaFilter ? "bg-blue-500" : "bg-gray-300"}`}>
                    <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${criteriaFilter ? "translate-x-5" : "translate-x-0.5"}`} />
                  </button>
                  </div>
                  <div className="text-[9px] t-text-dim leading-relaxed">
                    가점: 수급+10 · 골든크로스+5 · 저항돌파+5
                  </div>
                </div>
                )}
              </div>
              {useResearchOptimal !== savedResearchOptimal && (
                <div className="flex items-center gap-2 mt-2">
                  <button disabled={buySaving} onClick={async () => {
                    setBuySaving(true);
                    const ok = await setAlertConfig({ buy_signal_mode: "research_optimal" });
                    if (ok) { setSavedResearchOptimal(true); setSavedToggles({ chart: false, indicator: false, top_leader: false, all_leaders: false, fallback_top_leader: false }); setToastMsg({ text: "연구 최적 전략 적용 완료", type: "ok" }); }
                    else { setUseResearchOptimal(savedResearchOptimal); setToastMsg({ text: "저장 실패", type: "fail" }); }
                    setTimeout(() => setToastMsg(null), 2500); setBuySaving(false);
                  }} className="flex-1 text-[11px] font-medium py-1.5 rounded-lg text-white bg-blue-600 hover:bg-blue-500 transition disabled:opacity-40">
                    {buySaving ? "저장 중..." : "확인"}
                  </button>
                  <button onClick={() => setUseResearchOptimal(savedResearchOptimal)} className="text-[11px] font-medium py-1.5 px-3 rounded-lg t-text-sub border transition hover:opacity-80" style={{ borderColor: "var(--border)" }}>취소</button>
                </div>
              )}
            </div>
          )}
          {/* 수동 설정 — 기존 토글 */}
          {!useResearchOptimal && <div className="space-y-0.5">
            {([
              { key: "chart", label: "차트 시그널", desc: "AI 차트 분석 매수 신호" },
              { key: "indicator", label: "지표 시그널", desc: "API 기술 지표 매수 신호" },
              { key: "all_leaders", label: "대장주 전체", desc: "모든 테마 대장주 포함" },
              { key: "top_leader", label: "대장주 1위", desc: "테마별 거래대금 1위만 (독립 모드)" },
              { key: "fallback_top_leader", label: "Fallback 대장주 1위", desc: "AND 조건 매칭 0건 시 대장주 1위로 대체" },
            ] as const).map(opt => {
              const isOn = buyToggles[opt.key];
              return (
                <div key={opt.key} className="flex items-center justify-between py-1.5">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className="text-[11px] font-medium" style={{ color: isOn ? "var(--text-primary)" : "var(--text-secondary)" }}>{opt.label}</span>
                    <span className="text-[9px] t-text-dim">{opt.desc}</span>
                  </div>
                  <button
                    onClick={() => {
                      const next = { ...buyToggles, [opt.key]: !isOn };
                      if (opt.key === "top_leader" && !isOn) {
                        next.chart = false; next.indicator = false;
                        next.all_leaders = false; next.fallback_top_leader = false;
                      }
                      if ((opt.key === "chart" || opt.key === "indicator" || opt.key === "all_leaders" || opt.key === "fallback_top_leader") && !isOn) {
                        next.top_leader = false;
                      }
                      if (opt.key === "fallback_top_leader" && !isOn) {
                        next.chart = true; next.indicator = true; next.all_leaders = true;
                      }
                      if ((opt.key === "chart" || opt.key === "indicator" || opt.key === "all_leaders") && isOn) {
                        if (!next.chart && !next.indicator && !next.all_leaders) next.fallback_top_leader = false;
                      }
                      setBuyToggles(next);
                    }}
                    className="relative flex-shrink-0 ml-2 w-8 h-[16px] rounded-full transition-colors duration-200"
                    style={{ background: isOn ? "#3b82f6" : "var(--border)" }}>
                    <span
                      className="absolute top-[2px] left-[2px] w-[12px] h-[12px] rounded-full bg-white shadow-sm transition-transform duration-200"
                      style={{ transform: isOn ? "translateX(16px)" : "translateX(0)" }} />
                  </button>
                </div>
              );
            })}
          </div>}
          {!useResearchOptimal && <div className="mt-2 pt-2 border-t" style={{ borderColor: "var(--border)" }}>
            {(buyToggles.chart !== savedToggles.chart || buyToggles.indicator !== savedToggles.indicator || buyToggles.top_leader !== savedToggles.top_leader || buyToggles.all_leaders !== savedToggles.all_leaders || buyToggles.fallback_top_leader !== savedToggles.fallback_top_leader) && (
              <div className="flex items-center gap-2">
                <button disabled={buySaving} onClick={async () => {
                  setBuySaving(true);
                  const mode = [buyToggles.chart && "chart", buyToggles.indicator && "indicator", buyToggles.top_leader && "top_leader", buyToggles.all_leaders && "all_leaders", buyToggles.fallback_top_leader && "fallback_top_leader"].filter(Boolean).join(",") || "none";
                  const ok = await setAlertConfig({ buy_signal_mode: mode });
                  if (ok) {
                    setSavedToggles({ ...buyToggles });
                    setToastMsg({ text: "매집 기준이 저장되었습니다", type: "ok" });
                  } else {
                    setBuyToggles({ ...savedToggles });
                    setToastMsg({ text: "저장 실패 — 다시 시도해주세요", type: "fail" });
                  }
                  setTimeout(() => setToastMsg(null), 2500);
                  setBuySaving(false);
                }}
                  className="flex-1 text-[11px] font-medium py-1.5 rounded-lg text-white bg-blue-600 hover:bg-blue-500 transition disabled:opacity-40">
                  {buySaving ? "저장 중..." : "확인"}
                </button>
                <button onClick={() => setBuyToggles({ ...savedToggles })}
                  className="text-[11px] font-medium py-1.5 px-3 rounded-lg t-text-sub border transition hover:opacity-80"
                  style={{ borderColor: "var(--border)" }}>
                  취소
                </button>
              </div>
            )}
          </div>}
        </div>
        {/* 전략 비교 펼치기/접기 */}
        <button onClick={() => setShowStrategyCompare(!showStrategyCompare)}
          className="w-full mt-3 pt-3 text-[10px] t-text-dim flex items-center gap-1 hover:t-text transition"
          style={{ borderTop: "1px solid var(--border)" }}>
          <ChevronRight size={10} className={`transition-transform ${showStrategyCompare ? "rotate-90" : ""}`} />
          전략 비교 성과
        </button>
        {showStrategyCompare && (
          <div className="mt-2 space-y-2">
            {(() => {
              const soldTrades = trades.filter(t => t.status === "sold");
              const activeTrades = trades.filter(t => t.status === "filled");
              // === 완전 분리: 각 카드는 하나의 데이터 소스만 사용 ===
              // 5팩터+Stepped 카드: strategy_simulations type=stepped ONLY
              const steppedClosedSims = simulations.filter(s => s.status === "closed" && s.strategy_type === "stepped");
              const steppedOpenSims = simulations.filter(s => s.status === "open" && s.strategy_type === "stepped").map((s: any) => {
                const mt = trades.find(t => t.id === s.trade_id);
                const cp = mt ? (prices[mt.code]?.price || 0) : 0;
                const pnl = cp > 0 && s.entry_price > 0 ? ((cp - s.entry_price) / s.entry_price * 100) : null;
                return { ...s, pnl_pct: pnl != null ? Math.round(pnl * 100) / 100 : null, _isActive: true, _name: mt?.name, _noPrice: cp <= 0 };
              });
              const allRealTrades = [
                ...steppedClosedSims.map((s: any) => ({ ...s, _isActive: false })),
                ...steppedOpenSims,
              ];
              const realPnl = allRealTrades.length > 0 ? allRealTrades.reduce((sum, t) => sum + (t.pnl_pct || 0), 0) / allRealTrades.length : 0;

              // stepped 시뮬은 5팩터+Stepped 카드에 합산, 나머지(fixed)만 sim 카드
              const closedSims = simulations.filter(s => s.status === "closed" && !["time_exit","tv_time_exit","api_leader","stepped"].includes(s.strategy_type));
              const openSims = simulations.filter(s => s.status === "open" && !["time_exit","tv_time_exit","api_leader","stepped"].includes(s.strategy_type));
              // 시간전략 시뮬레이션 별도 집계
              const timeClosedSims = simulations.filter(s => s.status === "closed" && s.strategy_type === "time_exit");
              const timeOpenSims = simulations.filter(s => s.status === "open" && s.strategy_type === "time_exit");
              // 거래대금 10:00 청산 시뮬
              const tvTimeClosedSims = simulations.filter(s => s.status === "closed" && s.strategy_type === "tv_time_exit");
              const tvTimeOpenSims = simulations.filter(s => s.status === "open" && s.strategy_type === "tv_time_exit").map((s: any) => {
                const mt = trades.find(t => t.id === s.trade_id);
                const cp = mt ? (prices[mt.code]?.price || 0) : 0;
                const pnl = cp > 0 && s.entry_price > 0 ? ((cp - s.entry_price) / s.entry_price * 100) : null;
                return { ...s, pnl_pct: pnl != null ? Math.round(pnl * 100) / 100 : null, _name: mt?.name, _noPrice: cp <= 0 };
              });
              const allTvTimeSims = [...tvTimeClosedSims, ...tvTimeOpenSims];
              const tvTimePnl = allTvTimeSims.length > 0 ? allTvTimeSims.filter((s: any) => s.pnl_pct != null).reduce((sum, s: any) => sum + (s.pnl_pct || 0), 0) / (allTvTimeSims.filter((s: any) => s.pnl_pct != null).length || 1) : 0;
              const allTimeSims = [...timeClosedSims, ...timeOpenSims.map((s: any) => {
                const mt = trades.find(t => t.id === s.trade_id);
                const cp = mt ? (prices[mt.code]?.price || 0) : 0;
                const pnl = cp > 0 && s.entry_price > 0 ? ((cp - s.entry_price) / s.entry_price * 100) : null;
                return { ...s, pnl_pct: pnl != null ? Math.round(pnl * 100) / 100 : null, _name: mt?.name, _noPrice: cp <= 0 };
              })];
              const timePnl = allTimeSims.length > 0 ? allTimeSims.reduce((sum, s: any) => sum + (s.pnl_pct || 0), 0) / allTimeSims.length : 0;
              // API매수∧테마대장주 시뮬
              const apiLeaderSims = simulations.filter(s => s.strategy_type === "api_leader");
              const apiLeaderPnl = apiLeaderSims.length > 0 ? apiLeaderSims.reduce((sum, s: any) => sum + (s.pnl_pct || 0), 0) / apiLeaderSims.length : 0;
              // open 시뮬레이션의 미실현 PnL (전략별 TP/SL 적용)
              const openSimsWithPnl = openSims.map((s: any) => {
                const matchTrade = trades.find(t => t.id === s.trade_id);
                const cp = matchTrade ? (prices[matchTrade.code]?.price || 0) : 0;
                const noPrice = cp <= 0;
                let pnl = cp > 0 && s.entry_price > 0 ? ((cp - s.entry_price) / s.entry_price * 100) : 0;
                let isCapped = false;
                if (s.strategy_type === "fixed" && !noPrice) {
                  if (pnl >= takeProfit) { pnl = takeProfit; isCapped = true; }
                  if (pnl <= stopLoss) { pnl = stopLoss; isCapped = true; }
                }
                return { ...s, pnl_pct: noPrice ? null : Math.round(pnl * 100) / 100, _isActive: !isCapped, _isCapped: isCapped, _name: matchTrade?.name, _noPrice: noPrice };
              });
              const allSims = [...closedSims.map((s: any) => ({ ...s, _isActive: false })), ...openSimsWithPnl];
              const simPnl = allSims.length > 0 ? allSims.reduce((sum, s: any) => sum + (s.pnl_pct || 0), 0) / allSims.length : 0;

              const simStrategy = closedSims[0]?.strategy_type || openSims[0]?.strategy_type || (strategyType === "stepped" ? "fixed" : "stepped");
              const simLabel = simStrategy === "stepped" ? "Stepped Trailing" : "고정 익절/손절";

              // 갭업 모멘텀 시뮬 (sim_only 거래 중 거래대금 전략 전환 이후)
              const gapupSimOnly = trades.filter(t => t.status === "sim_only" && t.sell_reason === "gapup_sim");

              // 전략 전환 시점: gapup_sim 태그가 처음 나타난 날짜 = 거래대금 전략 시작일
              const tvCutoff = gapupSimOnly.length > 0
                ? gapupSimOnly.map((t: any) => toKstDate(t.created_at)).filter(Boolean).sort()[0] || ""
                : "";
              // 갭업 전환 시점 (5팩터→갭업) = 첫 stepped simulation 생성일
              const gapupCutoff = [...steppedClosedSims, ...steppedOpenSims]
                .map((s: any) => toKstDate(s.created_at)).filter(Boolean).sort()[0] || "";

              // 거래대금 모멘텀 (실제): tvCutoff 이후 실전 매매만
              const tvSold = tvCutoff
                ? soldTrades.filter(t => toKstDate(t.created_at) >= tvCutoff && t.sell_reason !== "gapup_sim")
                : [];
              const tvActive = tvCutoff
                ? activeTrades.filter(t => toKstDate(t.created_at) >= tvCutoff).map(t => {
                    const cp = prices[t.code]?.price || 0;
                    const bp = t.filled_price ?? t.order_price;
                    const pnl = cp > 0 && bp > 0 ? ((cp - bp) / bp * 100) : 0;
                    return { ...t, pnl_pct: Math.round(pnl * 100) / 100, _isActive: true };
                  })
                : [];
              const allTvTrades = [...tvSold.map(t => ({ ...t, _isActive: false })), ...tvActive];
              const tvPnl = allTvTrades.length > 0 ? allTvTrades.reduce((sum, t) => sum + (t.pnl_pct || 0), 0) / allTvTrades.length : 0;

              // 기존 갭업 모멘텀 (실제 과거 이력): gapupCutoff ~ tvCutoff 사이
              const gapupSold = gapupCutoff
                ? soldTrades.filter(t => {
                    const d = toKstDate(t.created_at);
                    return d >= gapupCutoff && (!tvCutoff || d < tvCutoff);
                  })
                : [];
              const gapupActive = (!tvCutoff)
                ? activeTrades.map(t => {
                    const cp = prices[t.code]?.price || 0;
                    const bp = t.filled_price ?? t.order_price;
                    const pnl = cp > 0 && bp > 0 ? ((cp - bp) / bp * 100) : 0;
                    return { ...t, pnl_pct: Math.round(pnl * 100) / 100, _isActive: true };
                  })
                : [];
              const allGapupTrades = [...gapupSold.map(t => ({ ...t, _isActive: false })), ...gapupActive];
              const gapupPnl = allGapupTrades.length > 0 ? allGapupTrades.reduce((sum, t) => sum + (t.pnl_pct || 0), 0) / allGapupTrades.length : 0;

              // 갭업 모멘텀 시뮬: 과거 실전 이력 + sim_only (장중 실시간 P&L 계산)
              const gapupSimWithPrices = gapupSimOnly.map((t: any) => {
                const cp = prices[t.code]?.price || 0;
                const bp = t.order_price || 0;
                const pnl = t.pnl_pct ?? (cp > 0 && bp > 0 ? Math.round((cp - bp) / bp * 10000) / 100 : null);
                return { ...t, pnl_pct: pnl, _isActive: t.sell_price == null, _noPrice: cp <= 0 && t.sell_price == null };
              });
              const allGapupSimTrades = [...allGapupTrades, ...gapupSimWithPrices];
              const gapupSimPnl = allGapupSimTrades.length > 0 ? allGapupSimTrades.reduce((sum, t) => sum + (t.pnl_pct || 0), 0) / allGapupSimTrades.length : 0;

              const simCards: { key: string; label: string; pnl: number; count: number; onClick: () => void }[] = [
                { key: "gapup_sim", label: "갭업 모멘텀", pnl: gapupSimPnl, count: allGapupSimTrades.length, onClick: () => setStrategyDetail("gapup_sim") },
                { key: "real_legacy", label: "5팩터+Stepped", pnl: realPnl, count: allRealTrades.length, onClick: () => setStrategyDetail("stepped_sim") },
                { key: "sim", label: simLabel, pnl: simPnl, count: allSims.length, onClick: () => setStrategyDetail("fixed_sim") },
                { key: "time", label: "시간전략", pnl: timePnl, count: allTimeSims.length, onClick: () => allTimeSims.length > 0 ? setStrategyDetail("time_sim") : undefined },
                { key: "tv_time", label: "10시청산", pnl: tvTimePnl, count: allTvTimeSims.length, onClick: () => allTvTimeSims.length > 0 ? setStrategyDetail("tv_time_sim") : undefined },
                { key: "api_leader", label: "API매수∧대장주", pnl: apiLeaderPnl, count: apiLeaderSims.length, onClick: () => apiLeaderSims.length > 0 ? setStrategyDetail("api_leader_sim") : undefined },
              ];

              return (
                <>
                  {/* Row 1: 거래대금 모멘텀 (실제) */}
                  <button onClick={() => setStrategyDetail("tv_momentum")}
                    className="w-full px-4 py-3 rounded-xl cursor-pointer transition relative group flex items-center" style={{ background: "var(--bg)" }}>
                    <div className="flex-1 min-w-0">
                      <div className="text-[9px] t-text-dim font-medium">실제 매매</div>
                      <div className="text-[11px] t-text font-semibold">거래대금 모멘텀</div>
                    </div>
                    {allTvTrades.length > 0 ? (
                      <div className="flex items-baseline gap-1.5 shrink-0">
                        <span className={`text-xl font-bold tabular-nums ${tvPnl >= 0 ? "text-red-500" : "text-blue-500"}`}>
                          {tvPnl >= 0 ? "+" : ""}{tvPnl.toFixed(1)}%
                        </span>
                        <span className="text-[9px] t-text-dim">{allTvTrades.length}건</span>
                      </div>
                    ) : (
                      <span className="text-[9px] t-text-dim shrink-0">축적 중</span>
                    )}
                    <ChevronRight size={10} className="t-text-dim opacity-30 group-hover:opacity-100 ml-2 shrink-0" />
                  </button>
                  {/* Row 2: 시뮬 5개 균등 배분 */}
                  <div className="grid grid-cols-5 gap-1 mt-1.5">
                    {simCards.map(c => (
                      <button key={c.key} onClick={c.onClick}
                        className="p-1.5 rounded-lg text-center cursor-pointer transition" style={{ background: "var(--bg)" }}>
                        <div className="text-[8px] t-text-dim font-medium truncate leading-tight">{c.label}</div>
                        {c.count > 0 ? (
                          <>
                            <div className={`text-[11px] font-bold tabular-nums mt-0.5 ${c.pnl >= 0 ? "text-red-500" : "text-blue-500"}`}>
                              {c.pnl >= 0 ? "+" : ""}{c.pnl.toFixed(1)}%
                            </div>
                            <div className="text-[8px] t-text-dim">{c.count}건</div>
                          </>
                        ) : (
                          <div className="text-[8px] t-text-dim mt-1">—</div>
                        )}
                      </button>
                    ))}
                  </div>
                  {allRealTrades.length === 0 && allSims.length === 0 && (
                    <div className="text-[10px] t-text-dim text-center py-2">아직 비교 데이터가 없습니다</div>
                  )}
                  {/* 바텀시트 */}
                  {strategyDetail && createPortal(
                    <div className="fixed inset-0 z-[9999] anim-fade-in" onClick={() => setStrategyDetail(null)}>
                      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
                      <div className="fixed bottom-0 left-0 right-0 z-[61] max-h-[70vh] flex flex-col rounded-t-2xl t-card border-t t-border-light sm:max-w-lg sm:mx-auto sm:rounded-2xl sm:bottom-auto sm:top-1/2 sm:-translate-y-1/2 anim-slide-up sm:anim-scale-in"
                        style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 1.5rem)' }} onClick={e => e.stopPropagation()}>
                        {/* 드래그 핸들 + 닫기 (고정) */}
                        <div className="flex-shrink-0 px-5 pt-5">
                          <div className="flex items-center justify-center relative mb-3">
                            <div className="w-8 h-1 rounded-full sm:hidden" style={{ background: 'var(--border)' }} />
                            <button onClick={() => setStrategyDetail(null)} className="absolute right-0 top-1/2 -translate-y-1/2 p-1 t-text-dim hover:t-text transition">
                              <X size={18} />
                            </button>
                          </div>
                          <h3 className="text-sm font-bold t-text mb-3 flex items-center gap-1.5">
                            {strategyDetail === "tv_momentum" ? "거래대금 모멘텀 (실제)" : strategyDetail === "gapup_sim" ? "갭업 모멘텀 (가상)" : strategyDetail === "stepped_sim" ? "5팩터+Stepped (가상)" : strategyDetail === "time_sim" ? "시간전략 09:30→11:00 (가상)" : strategyDetail === "tv_time_sim" ? "10시 청산 (가상)" : strategyDetail === "api_leader_sim" ? "API매수∧대장주 (가상)" : `${simLabel} (가상)`}
                            <button onClick={(e) => { e.stopPropagation(); setStrategyHelpOpen(strategyDetail); }} className="t-text-dim hover:t-text transition shrink-0"><HelpCircle size={14} /></button>
                            {priceTime && <span className="ml-auto text-[9px] text-green-400 tabular-nums shrink-0">{priceTime}</span>}
                            <button onClick={(e) => { e.stopPropagation(); refreshPrices(); }} disabled={priceRefreshing}
                              className={`${priceTime ? "ml-1" : "ml-auto"} text-[10px] px-2 py-0.5 rounded-lg font-medium t-text-sub border t-border-light hover:opacity-80 transition disabled:opacity-40 flex items-center gap-1 shrink-0`}>
                              <RefreshCw size={10} className={priceRefreshing ? "animate-spin" : ""} />
                              시세
                            </button>
                          </h3>
                        </div>
                        <div className="flex-1 overflow-y-auto px-5 pb-5">
                        {/* 종목 리스트 — 날짜별 그룹핑 + 체크박스 */}
                        {(() => {
                          const items = strategyDetail === "tv_momentum"
                            ? allTvTrades.map((t: any) => ({ ...t, _date: toKstDate(t.created_at) || "보유", _displayName: t.name, _displaySub: t.code }))
                            : strategyDetail === "gapup_sim"
                            ? allGapupSimTrades.map((t: any) => {
                                const isSim = t.status === "sim_only";
                                const sub = isSim ? `시뮬 ${(t.order_price || 0).toLocaleString()}원` : t.code;
                                const isOpen = isSim && t.sell_price == null;
                                return { ...t, _date: toKstDate(t.created_at) || "—", _displayName: t.name, _displaySub: sub, _isActive: isOpen };
                              })
                            : strategyDetail === "stepped_sim"
                            ? allRealTrades.map((t: any) => {
                                const mt = trades.find(tr => tr.id === t.trade_id);
                                const simCode = mt?.code || "";
                                const mtCreated = toKstDate(mt?.created_at);
                                const origSold = simCode ? soldTrades.filter(tr => tr.code === simCode && (tr.created_at || "") < (mt?.created_at || "")).pop() : null;
                                const displayDate = toKstDate(origSold?.created_at) || mtCreated || toKstDate(t.created_at) || "보유";
                                // origSold의 시간 정보를 사용 (날짜+시간 출처 통일)
                                const origTime = origSold?.filled_at || origSold?.created_at || mt?.created_at || t.created_at;
                                return { ...t, _date: displayDate, _displayName: t._name || mt?.name || "—", _displaySub: "시뮬 매수 " + (t.entry_price?.toLocaleString() || "") + "원", filled_at: origTime, created_at: origTime };
                              })
                            : (strategyDetail === "time_sim" ? allTimeSims : strategyDetail === "tv_time_sim" ? allTvTimeSims : strategyDetail === "api_leader_sim" ? apiLeaderSims : allSims).map((s: any) => {
                                const mt = trades.find(t => t.id === s.trade_id);
                                return { ...s, _date: toKstDate(mt?.created_at) || "보유", _displayName: s._name || mt?.name || "—", _displaySub: `매수 ${s.entry_price?.toLocaleString()}원` };
                              });
                          if (items.length === 0) {
                            return (
                              <div className="text-center py-10 space-y-3">
                                <div className="text-2xl">📭</div>
                                <div className="text-sm font-medium t-text">아직 데이터가 없습니다</div>
                                <div className="text-xs t-text-dim leading-relaxed">
                                  {strategyDetail === "api_leader_sim"
                                    ? "API매수 신호와 AI 예측 테마 대장주 조건을\n동시에 충족하는 종목이 발생하면 자동 시뮬레이션됩니다."
                                    : "매매가 실행되면 자동으로 시뮬레이션이 생성됩니다."}
                                </div>
                              </div>
                            );
                          }
                          const grouped: Record<string, typeof items> = {};
                          for (const item of items) {
                            const key = item._date;
                            if (!grouped[key]) grouped[key] = [];
                            grouped[key].push(item);
                          }
                          const dates = Object.keys(grouped).sort((a, b) => b.localeCompare(a));
                          const todayStr = toKstDate(new Date().toISOString());
                          // 체크된 날짜의 합산
                          const includedItems = items.filter(it => !excludedDates.has(it._date));
                          const closedOnly = includedItems.filter(it => !it._isActive);
                          const activeOnly = includedItems.filter(it => it._isActive);
                          // 실거래 여부: quantity가 있으면 실제 거래
                          const isRealTrades = strategyDetail === "tv_momentum";
                          // 가상 시뮬 균등 매수 가정 금액 (종목당 150만원 ~ 300만원/2종목)
                          const SIM_AMOUNT_PER_STOCK = 1500000;
                          // 종목별 매수금액 계산 (실거래는 quantity, 시뮬은 균등 가정)
                          const getInvestAmt = (t: any): number => {
                            if (isRealTrades) {
                              const buy = t.filled_price || t.entry_price || t.order_price || 0;
                              const qty = t.quantity || 0;
                              return buy * qty;
                            }
                            return SIM_AMOUNT_PER_STOCK;
                          };
                          // 손익(원) 계산
                          const getProfitKrw = (t: any): number => {
                            const buy = t.filled_price || t.entry_price || t.order_price || 0;
                            const sell = t.exit_price || t.sell_price || 0;
                            if (!buy || !sell) return 0;
                            if (isRealTrades) {
                              const qty = t.quantity || 0;
                              return (sell - buy) * qty;
                            }
                            // 시뮬: 균등 매수 가정 (가상 quantity = 1500000 / buy)
                            const virtQty = Math.floor(SIM_AMOUNT_PER_STOCK / buy);
                            return (sell - buy) * virtQty;
                          };
                          // 가중평균 = 총손익(원) / 총매수금액(원) × 100
                          const calcWeighted = (arr: any[]): number => {
                            const totalBuy = arr.reduce((s, t) => s + getInvestAmt(t), 0);
                            const totalProfit = arr.reduce((s, t) => s + getProfitKrw(t), 0);
                            return totalBuy > 0 ? (totalProfit / totalBuy) * 100 : 0;
                          };
                          const filteredPnl = isRealTrades
                            ? calcWeighted(closedOnly.length > 0 ? closedOnly : includedItems)
                            : (includedItems.length > 0 ? includedItems.reduce((s: number, t: any) => s + (t.pnl_pct ?? 0), 0) / includedItems.length : 0);
                          const closedPnl = isRealTrades
                            ? calcWeighted(closedOnly)
                            : (closedOnly.length > 0 ? closedOnly.reduce((s: number, t: any) => s + (t.pnl_pct ?? 0), 0) / closedOnly.length : 0);
                          const totalProfitKrw = closedOnly.reduce((s, t) => s + getProfitKrw(t), 0);
                          const totalInvestKrw = closedOnly.reduce((s, t) => s + getInvestAmt(t), 0);
                          const allChecked = excludedDates.size === 0;

                          return (
                            <>
                            {/* 합산 + 전체선택 */}
                            <div className="flex items-center justify-between mb-3 p-2.5 rounded-lg" style={{ background: "var(--bg)" }}>
                              <div className="flex flex-col gap-0.5">
                                <div className="flex items-center gap-3">
                                  <div className={`text-lg font-bold tabular-nums ${filteredPnl >= 0 ? "text-red-400" : "text-blue-400"}`}>
                                    {filteredPnl >= 0 ? "+" : ""}{filteredPnl.toFixed(2)}%
                                  </div>
                                  <div className="text-[10px] t-text-dim">{includedItems.length}건{activeOnly.length > 0 ? ` (보유 ${activeOnly.length})` : ""}</div>
                                </div>
                                {closedOnly.length > 0 && totalInvestKrw > 0 && (
                                  <div className="text-[10px] t-text-sub tabular-nums">
                                    <span className={`font-semibold ${totalProfitKrw >= 0 ? "text-red-400" : "text-blue-400"}`}>
                                      {totalProfitKrw >= 0 ? "+" : ""}{totalProfitKrw.toLocaleString()}원
                                    </span>
                                    <span className="t-text-dim ml-1">/ {totalInvestKrw.toLocaleString()}원 투자</span>
                                    {!isRealTrades && <span className="text-[8px] t-text-dim ml-1">(가상 {(SIM_AMOUNT_PER_STOCK/10000).toFixed(0)}만원/종목)</span>}
                                  </div>
                                )}
                              </div>
                              <button onClick={() => setExcludedDates(allChecked ? new Set(dates) : new Set())}
                                className="text-[10px] t-text-dim hover:t-text transition px-2 py-1 rounded-lg" style={{ border: "1px solid var(--border)" }}>
                                {allChecked ? "전체 해제" : "전체 선택"}
                              </button>
                            </div>
                            {activeOnly.length > 0 && (
                              <div className="text-[9px] t-text-dim mb-2 px-2.5">
                                확정 수익률 (보유 제외): <span className={`font-semibold ${closedPnl >= 0 ? "text-red-400" : "text-blue-400"}`}>{closedPnl >= 0 ? "+" : ""}{closedPnl.toFixed(2)}%</span> ({closedOnly.length}건)
                              </div>
                            )}
                            <div className="space-y-2">
                              {dates.map(date => {
                                const group = grouped[date];
                                const dayPnl = isRealTrades
                                  ? calcWeighted(group)
                                  : (group.length > 0 ? group.reduce((s: number, t: any) => s + (t.pnl_pct ?? 0), 0) / group.length : 0);
                                const dayProfit = group.reduce((s: number, t: any) => s + getProfitKrw(t), 0);
                                const dayClosed = group.filter((t: any) => !t._isActive);
                                const isToday = date === todayStr || date === "보유";
                                const isChecked = !excludedDates.has(date);
                                return (
                                  <details key={date} open={isToday} onToggle={(e) => {
                                    const el = e.currentTarget;
                                    if (el.open) requestAnimationFrame(() => el.scrollIntoView({ behavior: "smooth", block: "nearest" }));
                                  }}>
                                    <summary className={`flex items-center justify-between px-2.5 py-2 rounded-xl cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden transition ${isChecked ? "" : "opacity-40"}`}
                                      style={{ background: "var(--bg-card-alt)", border: "1px solid var(--border-light)" }}>
                                      <div className="flex items-center gap-2">
                                        <input type="checkbox" checked={isChecked}
                                          onChange={(e) => { e.stopPropagation(); setExcludedDates(prev => { const s = new Set(prev); isChecked ? s.add(date) : s.delete(date); return s; }); }}
                                          onClick={(e) => e.stopPropagation()}
                                          className="custom-check" />
                                        <ChevronDown size={12} className="t-text-dim transition-transform [details:not([open])>&]:-rotate-90" />
                                        <span className="text-[11px] font-semibold t-text">{date}</span>
                                        <span className="text-[10px] t-text-dim">{group.length}건</span>
                                        {group.some((it: any) => it._isActive) && <span className="text-[8px] px-1 py-0.5 rounded bg-blue-500/10 text-blue-400">보유 {group.filter((it: any) => it._isActive).length}</span>}
                                      </div>
                                      <div className="flex flex-col items-end gap-0.5">
                                        <span className={`text-[11px] font-semibold tabular-nums ${dayPnl >= 0 ? "text-red-400" : "text-blue-400"}`}>
                                          {dayPnl >= 0 ? "+" : ""}{dayPnl.toFixed(2)}%
                                        </span>
                                        {dayClosed.length > 0 && Math.abs(dayProfit) > 0 && (
                                          <span className={`text-[9px] tabular-nums ${dayProfit >= 0 ? "text-red-400/70" : "text-blue-400/70"}`}>
                                            {dayProfit >= 0 ? "+" : ""}{dayProfit.toLocaleString()}원
                                          </span>
                                        )}
                                      </div>
                                    </summary>
                                    <div className="ml-4 mt-1.5 pl-3 space-y-1 border-l-2" style={{ borderColor: 'var(--border)' }}>
                                      {group.map((item: any, i: number) => {
                                        const buyPrice = item.entry_price || item.filled_price || item.order_price || 0;
                                        const sellPrice = item.exit_price || item.sell_price || 0;
                                        const buyIso = item.filled_at || item.created_at || "";
                                        const sellIso = item.exited_at || item.sold_at || "";
                                        const buyDateKst = toKstDate(buyIso);
                                        const sellDateKst = toKstDate(sellIso);
                                        const formatTimeKst = (iso: string) => {
                                          if (!iso) return "";
                                          const t = iso.slice(11, 16);
                                          if (!t) return "";
                                          const [h, m] = t.split(":").map(Number);
                                          const kh = (h + 9) % 24;
                                          return `${kh}:${m.toString().padStart(2, "0")}`;
                                        };
                                        const formatDateShort = (d: string) => {
                                          if (!d || d.length < 10) return "";
                                          return `${d.slice(5, 7)}/${d.slice(8, 10)}`;
                                        };
                                        const groupDate = date;
                                        const buyDateLabel = buyDateKst && buyDateKst !== groupDate ? formatDateShort(buyDateKst) + " " : "";
                                        const sellDateLabel = sellDateKst && sellDateKst !== groupDate ? formatDateShort(sellDateKst) + " " : "";
                                        return (
                                        <div key={i} className={`text-[11px] px-2.5 py-2 rounded-lg ${isChecked ? "" : "opacity-40"}`} style={{ background: "var(--bg)" }}>
                                          <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2 min-w-0">
                                              <span className="t-text font-medium truncate">{item._displayName}</span>
                                              {item._isActive && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-blue-500/10 text-blue-400">보유</span>}
                                              {item._isCapped && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-red-500/10 text-red-400">{(item.pnl_pct ?? 0) >= 0 ? "익절" : "손절"}</span>}
                                              {(item.exit_reason || item.sell_reason) && !item._isActive && (() => { const r = item.exit_reason || item.sell_reason; return <span className="text-[9px] px-1.5 py-0.5 rounded-full t-text-dim" style={{ background: "var(--bg-muted)" }}>{r === "stop_loss" ? "손절" : r === "take_profit" ? "익절" : r === "time_exit" ? "시간매도" : r === "stepped_trailing" ? "Stepped" : r === "trailing_stop" ? "급락손절" : r === "eod_close" ? "장마감" : r === "manual_sell" ? "수동매도" : r === "false_stop" ? "오류매도" : r === "parent_sold" ? "실전매도" : r === "gapup_sim" ? "장마감" : r}</span>; })()}
                                            </div>
                                            <span className={`tabular-nums font-bold shrink-0 ${(item.pnl_pct ?? 0) >= 0 ? "text-red-400" : "text-blue-400"}`}>
                                              {item._noPrice ? (pricesLoading ? <span className="inline-block w-12 h-3 rounded animate-pulse" style={{ background: "var(--bg-muted)" }} /> : "시세 없음") : `${(item.pnl_pct ?? 0) >= 0 ? "+" : ""}${(item.pnl_pct ?? 0).toFixed(2)}%`}
                                            </span>
                                          </div>
                                          <div className="flex items-center gap-1 mt-1 text-[9px] t-text-sub">
                                            {buyPrice > 0 && <><span className="t-text-dim">매수</span> <span className="font-medium tabular-nums">{buyPrice.toLocaleString()}</span><span className="t-text-dim ml-0.5">{buyDateLabel}{formatTimeKst(buyIso)}</span></>}
                                            {sellPrice > 0 && <><span className="t-text-dim ml-2">→</span> <span className="t-text-dim ml-1">매도</span> <span className="font-medium tabular-nums">{sellPrice.toLocaleString()}</span><span className="t-text-dim ml-0.5">{sellDateLabel}{formatTimeKst(sellIso)}</span></>}
                                          </div>
                                          {(() => {
                                            const invest = getInvestAmt(item);
                                            const profit = getProfitKrw(item);
                                            if (invest <= 0) return null;
                                            const qty = isRealTrades ? (item.quantity || 0) : Math.floor(SIM_AMOUNT_PER_STOCK / (buyPrice || 1));
                                            return (
                                              <div className="flex items-center gap-1 mt-0.5 text-[9px] t-text-dim tabular-nums">
                                                <span>{qty}주 × {buyPrice.toLocaleString()}원 = {invest.toLocaleString()}원</span>
                                                {sellPrice > 0 && profit !== 0 && (
                                                  <span className={`ml-1 font-medium ${profit >= 0 ? "text-red-400/70" : "text-blue-400/70"}`}>
                                                    ({profit >= 0 ? "+" : ""}{profit.toLocaleString()}원)
                                                  </span>
                                                )}
                                              </div>
                                            );
                                          })()}
                                        </div>
                                        );
                                      })}
                                    </div>
                                  </details>
                                );
                              })}
                            </div>
                            </>
                          );
                        })()}
                        </div>
                      </div>
                    </div>,
                    document.body
                  )}
                  {/* 전략 설명 팝업 */}
                  {strategyHelpOpen && createPortal(
                    <div className="fixed inset-0 z-[10000] flex items-center justify-center anim-fade-in" onClick={() => setStrategyHelpOpen(null)}>
                      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
                      <div className="relative z-10 mx-6 max-w-sm w-full rounded-2xl p-5 t-card border t-border-light" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between mb-3">
                          <h4 className="text-sm font-bold t-text">
                            {strategyHelpOpen === "tv_momentum" ? "거래대금 모멘텀" : strategyHelpOpen === "gapup_sim" ? "갭업 모멘텀" : strategyHelpOpen === "stepped_sim" ? "5팩터+Stepped" : strategyHelpOpen === "fixed_sim" ? "고정 익절/손절" : strategyHelpOpen === "time_sim" ? "시간전략" : strategyHelpOpen === "tv_time_sim" ? "10시 청산" : "API매수∧대장주"}
                          </h4>
                          <button onClick={() => setStrategyHelpOpen(null)} className="t-text-dim hover:t-text transition"><X size={16} /></button>
                        </div>
                        <div className="text-[11px] t-text-sub leading-relaxed whitespace-pre-line">
                          {strategyHelpOpen === "tv_momentum" ? "장 초반 거래대금 상위 종목에 집중 투자하는 당일 매매 전략입니다.\n\n[종목 선정]\n① 거래대금 상위 (volume-rank API)\n② 상승 출발 (등락률 > 0%)\n③ 갭 < 10%\n④ 1,000원 ≤ 현재가 < 200,000원\n⑤ 전일 매매 종목 1일 쿨다운\n\n[가점 스코어링]\n· 전일 윗꼬리 > 3%: ×2.0 (미완의 상승 반등)\n· 전일 음봉: ×1.2 (하락 후 반등 매수세)\n· 전일 회전율 < 5%: ×1.5 (신규 관심 종목)\n· 연속 3일+ 상승: ×0.7 (과열 감점)\n→ 거래대금 × 가점 상위 2종목 선정\n\n[매매 타이밍]\n09:05 — volume-rank 스캔 → 즉시 매수\n15:15 — 전 포지션 당일 청산 (SL -5%)\n\n오버나이트 리스크 없음"
                           : strategyHelpOpen === "gapup_sim" ? "기존 갭업 모멘텀 전략의 종목 선정 결과를 가상으로 추적하는 시뮬레이션입니다.\n\n[종목 선정]\n① 갭업 0~5% + MA200↑ + MA20↑\n② 과열 필터 + 거래대금 ≥ 3억\n③ vol_rate × log(TV) 스코어 정렬\n→ 상위 2종목 선정 (매수 없이 기록만)\n\n거래대금 모멘텀과 종목 선정 결과를 비교하기 위한 용도입니다."
                           : strategyHelpOpen === "stepped_sim" ? "기존 실전 적용했던 5팩터 스코어 + Stepped Trailing 전략입니다.\n현재는 거래대금 모멘텀으로 전환되어 가상 추적 중입니다.\n\n[종목 선정: 5팩터 스코어]\n① API 매수 +30점 (적극매수 +10 추가)\n② Vision 매수 +20점 (적극매수 +5 추가)\n③ 대장주 1등 +25점 / 테마소속 +15점\n④ 저가주 <2만원 +5점\n⑤ 급락반등 -10%↓&외인50만주↑ +35점\n→ 최소 20점 이상, 상위 2종목 선정\n\n[Criteria 가점 필터 (선택)]\n수급 양호 +10 / 골든크로스 +5 / 저항돌파 +5\n\n[매도: Stepped Trailing 공격형]\n+7%→본전, +15%→+7%, +20%→+15%\n+25%→+20%, +30%+→고점-3%\nSL: -2% (기본 손절)"
                           : strategyHelpOpen === "fixed_sim" ? "고정 익절/손절 전략 시뮬레이션입니다.\n\n실전 매수와 동일한 종목·가격으로 가상 포지션을 생성하고, 고정 TP/SL 조건으로 매도 시뮬레이션합니다.\n\nTP: +7% (보유일수 연동 상향)\nSL: -2%\nTrailing: 고점 대비 -3% 하락 시 매도"
                           : strategyHelpOpen === "time_sim" ? "시간 기반 매도 전략 시뮬레이션입니다.\n\n실전 매수와 동일한 종목·가격으로 가상 포지션을 생성하고, 11:00 KST에 무조건 매도합니다.\n\n매수: 09:30 (실전과 동일)\n매도: 11:00 KST (시장 열기 피크)\nSL: -2% (11:00 전 손절)\n\n장 초반 모멘텀만 캡처하는 단기 전략으로, 오버나이트 리스크가 없습니다."
                           : "API 매수 시그널 + 테마 대장주 교집합 종목 선정 시뮬레이션입니다.\n\n[종목 선정 조건 (모두 AND)]\n① API 신호 = 매수 또는 적극매수\n② 가격: 1,000원 ≤ 현재가 < 50,000원\n③ AI 예측 테마 대장주 Top5\n→ 상위 2종목 선정 (스코어 순)\n\n[매도 조건]\nStepped Trailing 공격형과 동일\nSL: -2% (기본 손절)"}
                        </div>
                      </div>
                    </div>,
                    document.body
                  )}
                </>
              );
            })()}
          </div>
        )}
      </div>

      {/* 성과 요약 */}
      <div>
        <div className="flex gap-1 mb-3 p-0.5 rounded-lg" style={{ background: "var(--bg-pill)" }}>
          {([["realized", "실현 손익"], ["all", "미실현 포함"]] as const).map(([key, label]) => (
            <button key={key} onClick={() => setSummaryTab(key)}
              className={`flex-1 text-[11px] font-medium py-1.5 rounded-md transition ${summaryTab === key ? "t-text shadow-sm" : "t-text-dim"}`}
              style={summaryTab === key ? { background: "var(--bg-pill-active)" } : {}}>
              {label}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-2">
          {summaryTab === "realized" ? (<>
            <SummaryCard icon={<BarChart3 size={16} />} label="총 매매" value={`${totalTrades}건`} sub={`승 ${wins} / 패 ${losses}`} />
            <SummaryCard icon={<TrendingUp size={16} />} label="승률" value={`${winRate}%`} sub={`평균 수익률 ${avgPnl}%`} />
            <SummaryCard icon={<DollarSign size={16} />} label="총 수익" value={formatKRW(Math.round(totalPnl))} color={totalPnl >= 0 ? "var(--up)" : "var(--down)"} />
            <SummaryCard icon={<Clock size={16} />} label="보유 중" value={`${active.length}종목`} sub={`투자금 ${formatKRW(totalInvested)}`} />
          </>) : (<>
            <SummaryCard icon={<BarChart3 size={16} />} label="총 매매" value={`${allTotalTrades}건`} sub={`승 ${allWins} / 패 ${allLosses}`} />
            <SummaryCard icon={<TrendingUp size={16} />} label="승률" value={`${allWinRate}%`} sub={`평균 수익률 ${allAvgPnl}%`} />
            <SummaryCard icon={<DollarSign size={16} />} label="총 수익" value={formatKRW(Math.round(allTotalPnl))} color={allTotalPnl >= 0 ? "var(--up)" : "var(--down)"} sub={`미실현 ${formatKRW(Math.round(unrealizedPnl))}`} />
            <SummaryCard icon={<Clock size={16} />} label="보유 중" value={`${active.length}종목`} sub={`투자금 ${formatKRW(totalInvested)}`} />
          </>)}
        </div>
      </div>

      {active.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <h2 className="text-sm font-semibold t-text">보유 중</h2>
            <span className="text-xs px-1.5 py-0.5 rounded-full t-card-alt t-text-sub">{active.length}</span>
            {priceTime && (
              <span className="text-[10px] text-green-400 ml-1 tabular-nums">{priceTime}</span>
            )}
            <button onClick={refreshPrices} disabled={priceRefreshing}
              className="ml-auto text-[11px] px-2 py-1 rounded-lg font-medium t-text-sub border t-border-light hover:opacity-80 transition disabled:opacity-40 flex items-center gap-1">
              <RefreshCw size={12} className={priceRefreshing ? "animate-spin" : ""} />
              시세
            </button>
            <button onClick={handleSellAll}
              className="text-[11px] px-3 py-1 rounded-lg font-medium text-red-400 border border-red-400/30 hover:bg-red-500/10 transition">
              전체 매도
            </button>
          </div>
          <div className="space-y-2">
            {active.map((t) => (
              <TradeRow key={t.id} trade={t} type="active"
                onSell={() => handleSell(t)} selling={selling.has(t.id)}
                currentPrice={prices[t.code]?.price} todayChangeRate={prices[t.code]?.changeRate} pricesLoading={pricesLoading} />
            ))}
          </div>
        </div>
      )}

      {pending.length > 0 && (
        <Section title="주문 대기" count={pending.length}>
          {pending.map((t) => (
            <TradeRow key={t.id} trade={t} type={t.status === "sell_requested" ? "sell_requested" : "pending"} />
          ))}
        </Section>
      )}

      <HistoryByDate trades={closed} />

      {showBuyHelp && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-6" onClick={() => setShowBuyHelp(false)}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-md" />
          <div className="relative w-full max-w-[320px] rounded-2xl overflow-hidden" onClick={e => e.stopPropagation()}
            style={{ background: "var(--bg-card)", border: "1px solid var(--border)", boxShadow: "0 8px 32px rgba(0,0,0,0.3)" }}>
            <div className="px-4 pt-4 pb-3 flex items-center justify-between">
              <h3 className="text-sm font-bold t-text">매집 종목 선정 기준 설정</h3>
              <button onClick={() => setShowBuyHelp(false)} className="p-1 rounded-lg t-text-dim hover:t-text transition"><X size={16} /></button>
            </div>
            <div className="px-4 pb-4 text-[11px] t-text-sub leading-relaxed space-y-2.5">
              <p>ON 상태인 토글들의 조건이 <span className="font-semibold t-text">AND</span>로 결합됩니다.</p>
              <div className="space-y-1.5 text-[10px]">
                <div><span className="font-semibold t-text">차트 시그널</span> — AI 차트 분석 매수 신호</div>
                <div><span className="font-semibold t-text">지표 시그널</span> — API 기술 지표 매수 신호</div>
                <div><span className="font-semibold t-text">대장주 1위</span> — 각 테마 내 거래대금 1위 종목만</div>
                <div><span className="font-semibold t-text">대장주 전체</span> — 모든 테마의 모든 대장주 포함</div>
              </div>
              <p className="t-text-dim">대장주 1위와 전체는 상호 배타 (하나만 선택 가능)</p>
            </div>
          </div>
        </div>
      )}

      {toastMsg && createPortal(
        <div className="fixed top-16 left-1/2 z-[9999] flex items-center gap-2 px-4 py-2.5 rounded-xl text-[13px] font-medium text-white shadow-lg anim-toast"
          style={{ background: toastMsg.type === "fail" ? "rgba(220,38,38,0.92)" : "rgba(30,30,30,0.92)", backdropFilter: "blur(8px)", transform: "translateX(-50%)" }}>
          {toastMsg.type === "fail" ? <X size={14} /> : <Check size={14} />}
          {toastMsg.text}
        </div>,
        document.body
      )}
    </div>
  );
}

function SummaryCard({ icon, label, value, sub, color }: { icon: React.ReactNode; label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="rounded-xl px-3.5 py-3" style={{ background: "var(--bg-card-alt)" }}>
      <div className="flex items-center gap-1 mb-1">
        <span className="t-text-dim" style={{ opacity: 0.45 }}>{icon}</span>
        <span className="text-[10px] font-medium t-text-dim">{label}</span>
      </div>
      <div className="text-[22px] font-bold tabular-nums leading-tight" style={{ color: color || "var(--text-primary)", letterSpacing: "-0.03em" }}>{value}</div>
      {sub && <div className="text-[10px] t-text-dim mt-0.5 tabular-nums">{sub}</div>}
    </div>
  );
}

function Section({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <h2 className="text-sm font-semibold t-text">{title}</h2>
        <span className="text-xs px-1.5 py-0.5 rounded-full t-card-alt t-text-sub">{count}</span>
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function TradeRow({ trade, type, onSell, selling, currentPrice, todayChangeRate, pricesLoading }: {
  trade: Trade;
  type: "active" | "pending" | "closed" | "sell_requested";
  onSell?: () => void;
  selling?: boolean;
  currentPrice?: number;
  todayChangeRate?: number;
  pricesLoading?: boolean;
}) {
  const buyPrice = trade.filled_price ?? trade.order_price;
  const amount = buyPrice * trade.quantity;
  const pnl = trade.pnl_pct ?? 0;
  const livePnl = currentPrice && buyPrice > 0 ? ((currentPrice - buyPrice) / buyPrice * 100) : null;
  const livePnlAmount = currentPrice && buyPrice > 0 ? (currentPrice - buyPrice) * trade.quantity : null;

  const accentBorder = type === "active" ? "border-l-[3px] border-l-blue-400"
    : type === "sell_requested" ? "border-l-[3px] border-l-amber-400"
    : type === "pending" ? "border-l-[3px] border-l-gray-400"
    : "border-l-[3px] border-l-transparent";

  return (
    <div
      className={`rounded-xl p-3 border ${accentBorder}`}
      style={{ background: "var(--bg-card)", borderColor: "var(--border)", boxShadow: "var(--shadow-card)" }}
    >
      {/* 1단계: 종목명 + 수익률 뱃지 + 액션 */}
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-semibold text-[15px] t-text truncate">{trade.name}</span>
          <span className="text-[11px] t-text-dim shrink-0">{trade.code}</span>
          {type === "active" && (() => {
            const filled = trade.filled_at || trade.created_at;
            if (!filled) return null;
            const buyDate = new Date(filled);
            const now = new Date();
            const buyDay = new Date(buyDate.getFullYear(), buyDate.getMonth(), buyDate.getDate());
            const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
            let biz = 0;
            const d = new Date(buyDay);
            while (d < today) { d.setDate(d.getDate() + 1); const dow = d.getDay(); if (dow !== 0 && dow !== 6) biz++; }
            const label = biz === 0 ? "D" : `D+${biz}`;
            const opacity = Math.min(0.4 + biz * 0.12, 1);
            return (
              <span className="shrink-0 text-[9px] font-semibold tracking-wider px-1.5 py-0.5 rounded-md"
                style={{ background: `rgba(99,102,241,${opacity * 0.12})`, color: `rgba(99,102,241,${opacity})` }}>
                {label}
              </span>
            );
          })()}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {type === "closed" && (
            <span className="text-xs font-bold px-2.5 py-1 rounded-lg tabular-nums"
              style={{ color: pnl >= 0 ? "var(--up)" : "var(--down)", background: pnl >= 0 ? "rgba(239,68,68,0.1)" : "rgba(59,130,246,0.1)" }}>
              {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}%
            </span>
          )}
          {type === "active" && (
            <button onClick={onSell} disabled={selling}
              className="text-[11px] px-2.5 py-1 rounded-lg font-medium text-red-400 border border-red-400/30 hover:bg-red-500/10 transition disabled:opacity-40">
              {selling ? "요청 중..." : "매도"}
            </button>
          )}
          {type === "pending" && (
            <span className="text-xs px-2 py-0.5 rounded-full t-card-alt t-text-sub">주문 대기</span>
          )}
          {type === "sell_requested" && (
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(239,68,68,0.1)", color: "var(--danger)" }}>매도 대기</span>
          )}
        </div>
      </div>
      {/* 2단계: 현재가 + 당일등락률 + 손익금 (active만) */}
      {type === "active" && (
        currentPrice != null ? (
          <div className="flex justify-between mb-1.5">
            <div>
              <div className="text-[15px] font-bold t-text tabular-nums">{formatKRW(currentPrice)}</div>
              {todayChangeRate != null && todayChangeRate !== 0 && (
                <div className="text-[11px] font-medium tabular-nums t-text-sub">
                  당일 <span style={{ color: todayChangeRate >= 0 ? "#f97316" : "#8b5cf6" }}>{todayChangeRate >= 0 ? "+" : ""}{todayChangeRate.toFixed(2)}%</span>
                </div>
              )}
            </div>
            {livePnlAmount !== null && (
              <div className="text-right" style={{ color: livePnlAmount >= 0 ? "var(--up)" : "var(--down)" }}>
                <div className="text-[14px] font-bold tabular-nums">
                  {livePnlAmount >= 0 ? "+" : ""}{Math.round(livePnlAmount).toLocaleString("ko-KR")}원
                </div>
                {livePnl !== null && (
                  <div className="text-[11px] font-semibold tabular-nums">
                    {livePnl >= 0 ? "+" : ""}{livePnl.toFixed(2)}%
                  </div>
                )}
              </div>
            )}
          </div>
        ) : pricesLoading ? (
          <div className="flex justify-between mb-1.5">
            <div>
              <div className="h-5 w-24 rounded animate-pulse mb-1" style={{ background: "var(--bg-muted)" }} />
              <div className="h-3 w-16 rounded animate-pulse" style={{ background: "var(--bg-muted)" }} />
            </div>
            <div className="text-right">
              <div className="h-5 w-28 rounded animate-pulse mb-1 ml-auto" style={{ background: "var(--bg-muted)" }} />
              <div className="h-3 w-14 rounded animate-pulse ml-auto" style={{ background: "var(--bg-muted)" }} />
            </div>
          </div>
        ) : null
      )}
      {/* 3단계: 매수 상세 — compact dimmed */}
      <div className="flex items-center justify-between text-[11px] t-text-dim">
        <span>{formatKRW(buyPrice)} × {trade.quantity.toLocaleString()}주 ({formatKRW(amount)})</span>
        <span>매수 {formatDate(trade.created_at)}</span>
      </div>
      {type === "closed" && (
        <div className="text-xs mt-1 space-y-0.5">
          {trade.sell_reason && (
            <div style={{ color: (trade.sell_reason === "take_profit" || (trade.sell_reason === "stepped_trailing" && (trade.pnl_pct ?? 0) >= 0)) ? "var(--up)" : trade.sell_reason === "eod_close" || trade.sell_reason === "false_stop" ? "var(--text-secondary)" : "var(--down)" }}>
              {trade.sell_reason === "take_profit" ? "익절" : trade.sell_reason === "stepped_trailing" ? ((trade.pnl_pct ?? 0) >= 0 ? "Stepped 익절" : "Stepped 손절") : trade.sell_reason === "eod_close" ? "장 마감 청산" : trade.sell_reason === "trailing_stop" ? "급락 손절" : trade.sell_reason === "manual_sell" ? "수동 매도" : trade.sell_reason === "stop_loss" ? "손절" : trade.sell_reason === "false_stop" ? "오류 매도" : trade.sell_reason || "매도"}
              {trade.sell_price ? ` (${trade.sell_price.toLocaleString("ko-KR")}원)` : ""}
            </div>
          )}
          <div className="flex items-center justify-between t-text-dim">
            {trade.sold_at && <span>매도 {formatDate(trade.sold_at)}</span>}
            {trade.pnl_pct != null && trade.filled_price && (
              <span style={{ color: trade.pnl_pct >= 0 ? "var(--up)" : "var(--down)" }} className="font-medium">
                {trade.pnl_pct >= 0 ? "+" : ""}{Math.round(trade.sell_price && trade.filled_price > 0 ? (trade.sell_price - trade.filled_price) * trade.quantity : trade.filled_price * trade.quantity * trade.pnl_pct / 100).toLocaleString("ko-KR")}원
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function HistoryByDate({ trades }: { trades: Trade[] }) {
  const today = new Date();
  const todayKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  const [collapsed, setCollapsed] = useState<Set<string>>(() => {
    // 오늘 이외 날짜는 기본 접기
    const s = new Set<string>();
    for (const t of trades) {
      const d = new Date(t.created_at);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      if (key !== todayKey) s.add(key);
    }
    return s;
  });

  if (trades.length === 0) {
    return (
      <div>
        <div className="flex items-center gap-2 mb-2">
          <h2 className="text-sm font-semibold t-text">매매 이력</h2>
          <span className="text-xs px-1.5 py-0.5 rounded-full t-card-alt t-text-sub">0</span>
        </div>
        <div className="text-center py-8 t-text-sub text-sm">아직 완료된 매매가 없습니다</div>
      </div>
    );
  }

  // 날짜별 그룹핑
  const grouped: Record<string, Trade[]> = {};
  for (const t of trades) {
    const d = new Date(t.created_at);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(t);
  }
  const dates = Object.keys(grouped).sort((a, b) => b.localeCompare(a));

  const toggle = (date: string) => {
    setCollapsed(prev => {
      const s = new Set(prev);
      if (s.has(date)) s.delete(date); else s.add(date);
      return s;
    });
  };

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <h2 className="text-sm font-semibold t-text">매매 이력</h2>
        <span className="text-xs px-1.5 py-0.5 rounded-full t-card-alt t-text-sub">{trades.length}</span>
      </div>
      <div className="space-y-3">
        {dates.map(date => {
          const items = grouped[date];
          const isOpen = !collapsed.has(date);
          const dayPnl = items.reduce((s, t) => s + (t.pnl_pct ?? 0), 0);
          const avgPnl = items.length > 0 ? dayPnl / items.length : 0;
          return (
            <div key={date}>
              <button onClick={() => toggle(date)}
                className="w-full flex items-center justify-between px-2 py-1.5 rounded-lg transition hover:opacity-80"
                style={{ background: "var(--bg)" }}>
                <div className="flex items-center gap-2">
                  <ChevronDown size={14} className={`t-text-dim transition-transform ${isOpen ? "" : "-rotate-90"}`} />
                  <span className="text-[13px] font-semibold t-text">{date}</span>
                  <span className="text-[11px] t-text-dim">{items.length}건</span>
                </div>
                <span className={`text-xs font-semibold tabular-nums ${avgPnl > 0 ? "text-red-500" : avgPnl < 0 ? "text-blue-500" : "t-text-dim"}`}>
                  평균 {avgPnl >= 0 ? "+" : ""}{avgPnl.toFixed(2)}%
                </span>
              </button>
              {isOpen && (
                <div className="space-y-2 mt-2">
                  {items.map(t => <TradeRow key={t.id} trade={t} type="closed" />)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function LoginModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: (user: any, token: string) => void }) {
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-6" onClick={() => { if (!loading) onClose(); }}>
      <div className="absolute inset-0 bg-black/50 backdrop-blur-md" />
      <div className="relative w-full max-w-[340px] rounded-2xl overflow-hidden" onClick={e => e.stopPropagation()}
        style={{ background: "var(--bg-card)", border: "1px solid var(--border)", boxShadow: "0 8px 32px rgba(0,0,0,0.3)" }}>
        <div className="px-5 pt-5 pb-3">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold t-text">로그인</h3>
            <button onClick={() => { if (!loading) onClose(); }} className="p-1 rounded-lg t-text-dim hover:t-text transition">
              <X size={18} />
            </button>
          </div>
          <p className="text-[11px] t-text-dim mt-1">모의투자 현황을 확인하려면 로그인해주세요</p>
        </div>
        <form className="px-5 pb-5" onSubmit={async (e) => {
          e.preventDefault();
          if (loading || !email.trim() || !pw) return;
          setError(""); setLoading(true);
          try {
            const { data, error: err } = await supabase.auth.signInWithPassword({ email: email.trim(), password: pw });
            if (err) {
              setError(err.message.includes("Invalid login") ? "이메일 또는 비밀번호가 올바르지 않습니다" : err.message);
              return;
            }
            if (data?.session) onSuccess(data.session.user, data.session.access_token ?? "");
            else setError("로그인 응답에 세션이 없습니다");
          } catch (e: any) {
            setError(e?.message || "네트워크 오류");
          } finally { setLoading(false); }
        }}>
          {error && <div className="text-[11px] text-red-400 mb-3 p-2.5 rounded-lg" style={{ background: "rgba(239,68,68,0.08)" }}>{error}</div>}
          <input type="email" placeholder="이메일" value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" autoFocus
            className="w-full text-[14px] px-3.5 py-2.5 rounded-xl t-text mb-2 outline-none"
            style={{ background: "var(--bg)", border: "1px solid var(--border)" }} />
          <input type="password" placeholder="비밀번호" value={pw} onChange={e => setPw(e.target.value)} autoComplete="current-password"
            className="w-full text-[14px] px-3.5 py-2.5 rounded-xl t-text mb-4 outline-none"
            style={{ background: "var(--bg)", border: "1px solid var(--border)" }} />
          <button type="submit" disabled={loading || !email.trim() || !pw}
            className="w-full flex items-center justify-center gap-2 text-[13px] font-medium py-2.5 rounded-xl text-white bg-blue-600 hover:bg-blue-500 transition disabled:opacity-40">
            {loading ? <Loader2 size={14} className="animate-spin" /> : <LogIn size={14} />}
            {loading ? "로그인 중..." : "로그인"}
          </button>
        </form>
      </div>
    </div>
  );
}
