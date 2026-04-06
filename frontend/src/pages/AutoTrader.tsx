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
  const [savedSteppedPreset, setSavedSteppedPreset] = useState<"default" | "aggressive">("default");
  const [showStrategyCompare, setShowStrategyCompare] = useState(false);
  const [strategyDetail, setStrategyDetail] = useState<"real" | "sim" | "time" | "api_leader" | "gapup" | null>(null);
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
          fetchKisPrices(priceCodes).then(kisData => {
            const map: Record<string, { price: number; changeRate: number }> = {};
            for (const [code, p] of Object.entries(kisData)) {
              if (p.current_price) map[code] = { price: p.current_price, changeRate: p.change_rate ?? 0 };
            }
            if (Object.keys(map).length > 0) setPrices(map);
          }).catch(() => {});
        }
      }
    } catch {
      // 네트워크 오류 등 — 세션 만료가 아님
    }
    setLoading(false);
  }

  async function refreshPrices() {
    if (priceRefreshing) return;
    const codes = trades.filter(t => t.status === "filled").map(t => t.code).filter(Boolean);
    if (!codes.length) return;
    setPriceRefreshing(true);
    try {
      const kisData = await fetchKisPrices(codes);
      const map: Record<string, { price: number; changeRate: number }> = {};
      for (const [code, p] of Object.entries(kisData)) {
        if (p.current_price) map[code] = { price: p.current_price, changeRate: p.change_rate ?? 0 };
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
    const pnl = (t.pnl_pct ?? 0) / 100 * buy * t.quantity;
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
            {savedStrategyType === "gapup" ? "갭업 모멘텀" : savedStrategyType === "stepped" ? `Stepped Trailing${savedSteppedPreset === "aggressive" ? " (공격형)" : ""}` : "고정 익절/손절"}
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
              {st === "gapup" ? "갭업 모멘텀" : st === "stepped" ? "Stepped Trailing" : "고정 익절/손절"}
            </button>
          ))}
        </div>
        {strategyType === "gapup" && (
          <div className="mt-2 p-3 rounded-lg text-[10px] t-text-sub leading-relaxed space-y-2" style={{ background: "var(--bg)" }}>
            <div className="space-y-1">
              <div className="flex items-center gap-2"><span className="font-semibold" style={{ color: "#ef4444" }}>갭업</span><span className="t-text-dim">시가 갭업 1~5%</span></div>
              <div className="flex items-center gap-2"><span className="font-semibold" style={{ color: "#3b82f6" }}>MA200</span><span className="t-text-dim">현재가 &gt; 200일 이동평균</span></div>
              <div className="flex items-center gap-2"><span className="font-semibold" style={{ color: "#f59e0b" }}>스캔</span><span className="t-text-dim">09:01 200종목 스캔 → 09:30 거래량 보완</span></div>
              <div className="flex items-center gap-2"><span className="font-semibold" style={{ color: "#22c55e" }}>매도</span><span className="t-text-dim">당일 15:15 장 마감 청산</span></div>
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
                    <div className="text-[11px] font-semibold t-text mb-1">갭업 모멘텀 종목 선정</div>
                    <div className="space-y-1">
                      <div className="flex items-center gap-2"><span className="font-semibold" style={{ color: "#ef4444" }}>09:01</span><span className="t-text-dim">200종목 스캔 → 갭업 1~5% + MA200 필터</span></div>
                      <div className="flex items-center gap-2"><span className="font-semibold" style={{ color: "#f59e0b" }}>09:30</span><span className="t-text-dim">매수 0건 시 → 거래량 2배 필터 추가 재스캔</span></div>
                      <div className="flex items-center gap-2"><span className="font-semibold" style={{ color: "#3b82f6" }}>선정</span><span className="t-text-dim">거래량 순 상위 2종목 즉시 매수</span></div>
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
              // 보유 중 종목의 미실현 PnL 계산
              const activeWithPnl = activeTrades.map(t => {
                const cp = prices[t.code]?.price || 0;
                const bp = t.filled_price ?? t.order_price;
                const pnl = cp > 0 && bp > 0 ? ((cp - bp) / bp * 100) : 0;
                return { ...t, pnl_pct: Math.round(pnl * 100) / 100, _isActive: true };
              });
              // stepped 시뮬 (5팩터 가상 추적분)을 실거래와 합산
              const steppedClosedSims = simulations.filter(s => s.status === "closed" && s.strategy_type === "stepped");
              const steppedOpenSims = simulations.filter(s => s.status === "open" && s.strategy_type === "stepped").map((s: any) => {
                const mt = trades.find(t => t.id === s.trade_id);
                const cp = mt ? (prices[mt.code]?.price || 0) : 0;
                const pnl = cp > 0 && s.entry_price > 0 ? ((cp - s.entry_price) / s.entry_price * 100) : 0;
                return { ...s, pnl_pct: Math.round(pnl * 100) / 100, _isActive: true, _name: mt?.name };
              });
              // 시뮬로 전환된 종목의 실거래 "장마감" 기록 제외 (시뮬이 대체)
              const steppedSimCodes = new Set([...steppedClosedSims, ...steppedOpenSims].map((s: any) => {
                const mt = trades.find(t => t.id === s.trade_id);
                return mt?.code || "";
              }).filter(Boolean));
              const filteredSold = soldTrades.filter(t => !(steppedSimCodes.has(t.code) && t.sell_reason === "eod_close"));
              // 갭업 매수 종목은 5팩터 카드에서 제외 (갭업 카드에 표시)
              // 갭업 매수분 = 오늘 매수된 filled (갭업 전략 전환 후 생성된 것)
              // 5팩터 카드에는 이전 전략의 sold + stepped 시뮬만 표시
              const allRealTrades = [
                ...filteredSold.map(t => ({ ...t, _isActive: false })),
                ...steppedClosedSims.map((s: any) => ({ ...s, _isActive: false })),
                ...steppedOpenSims,
              ];
              const realPnl = allRealTrades.length > 0 ? allRealTrades.reduce((sum, t) => sum + (t.pnl_pct || 0), 0) / allRealTrades.length : 0;

              // stepped 시뮬은 5팩터+Stepped 카드에 합산, 나머지(fixed)만 sim 카드
              const closedSims = simulations.filter(s => s.status === "closed" && !["time_exit","api_leader","stepped"].includes(s.strategy_type));
              const openSims = simulations.filter(s => s.status === "open" && !["time_exit","api_leader","stepped"].includes(s.strategy_type));
              // 시간전략 시뮬레이션 별도 집계
              const timeClosedSims = simulations.filter(s => s.status === "closed" && s.strategy_type === "time_exit");
              const timeOpenSims = simulations.filter(s => s.status === "open" && s.strategy_type === "time_exit");
              const allTimeSims = [...timeClosedSims, ...timeOpenSims.map((s: any) => {
                const mt = trades.find(t => t.id === s.trade_id);
                const cp = mt ? (prices[mt.code]?.price || 0) : 0;
                const pnl = cp > 0 && s.entry_price > 0 ? ((cp - s.entry_price) / s.entry_price * 100) : 0;
                return { ...s, pnl_pct: Math.round(pnl * 100) / 100, _name: mt?.name };
              })];
              const timePnl = allTimeSims.length > 0 ? allTimeSims.reduce((sum, s: any) => sum + (s.pnl_pct || 0), 0) / allTimeSims.length : 0;
              // API매수∧테마대장주 시뮬
              const apiLeaderSims = simulations.filter(s => s.strategy_type === "api_leader");
              const apiLeaderPnl = apiLeaderSims.length > 0 ? apiLeaderSims.reduce((sum, s: any) => sum + (s.pnl_pct || 0), 0) / apiLeaderSims.length : 0;
              // stepped 시뮬 (독립 생성분 포함)은 closedSims/openSims에 포함
              // open 시뮬레이션의 미실현 PnL (전략별 TP/SL 적용)
              const openSimsWithPnl = openSims.map((s: any) => {
                const matchTrade = trades.find(t => t.id === s.trade_id);
                const cp = matchTrade ? (prices[matchTrade.code]?.price || 0) : 0;
                let pnl = cp > 0 && s.entry_price > 0 ? ((cp - s.entry_price) / s.entry_price * 100) : 0;
                let isCapped = false;
                // fixed 전략 시뮬레이션: TP/SL 초과 시 cap
                if (s.strategy_type === "fixed") {
                  if (pnl >= takeProfit) { pnl = takeProfit; isCapped = true; }
                  if (pnl <= stopLoss) { pnl = stopLoss; isCapped = true; }
                }
                return { ...s, pnl_pct: Math.round(pnl * 100) / 100, _isActive: !isCapped, _isCapped: isCapped, _name: matchTrade?.name };
              });
              const allSims = [...closedSims.map((s: any) => ({ ...s, _isActive: false })), ...openSimsWithPnl];
              const simPnl = allSims.length > 0 ? allSims.reduce((sum, s: any) => sum + (s.pnl_pct || 0), 0) / allSims.length : 0;

              const simStrategy = closedSims[0]?.strategy_type || openSims[0]?.strategy_type || (strategyType === "stepped" ? "fixed" : "stepped");
              const simLabel = simStrategy === "stepped" ? "Stepped Trailing" : "고정 익절/손절";

              // 실제 카드: 갭업 모멘텀 거래만 (TODO: 갭업 거래 분류 추가 시 필터)
              // 현재는 allRealTrades가 기존 5팩터 거래이므로, 기존 거래를 "5팩터+Stepped (가상)"으로 표시
              const simCards: { key: string; label: string; pnl: number; count: number; onClick: () => void }[] = [
                { key: "real_legacy", label: "5팩터+Stepped", pnl: realPnl, count: allRealTrades.length, onClick: () => setStrategyDetail("real") },
                { key: "sim", label: simLabel, pnl: simPnl, count: allSims.length, onClick: () => setStrategyDetail("sim") },
                { key: "time", label: "시간전략", pnl: timePnl, count: allTimeSims.length, onClick: () => allTimeSims.length > 0 ? setStrategyDetail("time") : undefined },
                { key: "api_leader", label: "API매수∧대장주", pnl: apiLeaderPnl, count: apiLeaderSims.length, onClick: () => apiLeaderSims.length > 0 ? setStrategyDetail("api_leader") : undefined },
              ];

              // 갭업 모멘텀 실제 거래: 현재 보유(filled) + 갭업 전환 후 sold (eod_close)
              const gapupTrades = [...activeWithPnl, ...soldTrades.filter(t => t.sell_reason === "eod_close" && steppedSimCodes.has(t.code) === false)];
              // 갭업 전환 시점 이후 매도분만 (4/6~)
              const gapupSoldAfterSwitch = soldTrades.filter(t => t.sold_at && t.sold_at >= "2026-04-06" && t.sell_reason === "eod_close" && !steppedSimCodes.has(t.code));
              const allGapupTrades = [...gapupSoldAfterSwitch.map(t => ({ ...t, _isActive: false })), ...activeWithPnl];
              const gapupPnl = allGapupTrades.length > 0 ? allGapupTrades.reduce((sum, t) => sum + (t.pnl_pct || 0), 0) / allGapupTrades.length : 0;

              return (
                <>
                  {/* 실제 전략: 갭업 모멘텀 */}
                  <button onClick={() => setStrategyDetail("gapup")}
                    className="w-full p-3 rounded-lg text-center border border-transparent cursor-pointer transition relative group" style={{ background: "var(--bg)" }}>
                    <div className="text-[10px] t-text-sub font-medium mb-1">갭업 모멘텀 (실제)</div>
                    {allGapupTrades.length > 0 ? (
                      <>
                        <div className={`text-lg font-bold tabular-nums ${gapupPnl >= 0 ? "text-red-500" : "text-blue-500"}`}>
                          {gapupPnl >= 0 ? "+" : ""}{gapupPnl.toFixed(1)}%
                        </div>
                        <div className="text-[10px] t-text-sub mt-0.5">{allGapupTrades.length}건</div>
                      </>
                    ) : (
                      <div className="text-[9px] t-text-dim mt-1">축적 중</div>
                    )}
                    <ChevronRight size={12} className="absolute right-2 top-1/2 -translate-y-1/2 t-text-dim opacity-40 group-hover:opacity-100 transition" />
                  </button>
                  {/* 가상 전략 */}
                  <div className="flex gap-2 mt-2 flex-wrap">
                    {simCards.map(c => (
                      <button key={c.key} onClick={c.onClick}
                        className="flex-1 p-2.5 rounded-lg text-center border border-transparent cursor-pointer transition relative group" style={{ background: "var(--bg)" }}>
                        <div className="text-[9px] t-text-sub font-medium mb-1">{c.label}</div>
                        {c.count > 0 ? (
                          <>
                            <div className={`text-sm font-bold tabular-nums ${c.pnl >= 0 ? "text-red-500" : "text-blue-500"}`}>
                              {c.pnl >= 0 ? "+" : ""}{c.pnl.toFixed(1)}%
                            </div>
                            <div className="text-[9px] t-text-sub mt-0.5">{c.count}건</div>
                            <ChevronRight size={10} className="absolute right-1.5 top-1/2 -translate-y-1/2 t-text-dim opacity-30 group-hover:opacity-100 transition" />
                          </>
                        ) : (
                          <div className="text-[9px] t-text-sub mt-1">축적 중</div>
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
                            {strategyDetail === "gapup" ? "갭업 모멘텀 (실제)" : strategyDetail === "real" ? "5팩터+Stepped (가상)" : strategyDetail === "time" ? "시간전략 09:30→11:00 (가상)" : strategyDetail === "api_leader" ? "API매수∧대장주 (가상)" : `${simLabel} (가상)`}
                            <button onClick={(e) => { e.stopPropagation(); setStrategyHelpOpen(strategyDetail); }} className="t-text-dim hover:t-text transition shrink-0"><HelpCircle size={14} /></button>
                          </h3>
                        </div>
                        <div className="flex-1 overflow-y-auto px-5 pb-5">
                        {/* 종목 리스트 — 날짜별 그룹핑 + 체크박스 */}
                        {(() => {
                          const items = strategyDetail === "gapup"
                            ? allGapupTrades.map((t: any) => ({ ...t, _date: t.created_at?.slice(0, 10) || "보유", _displayName: t.name, _displaySub: t.code }))
                            : strategyDetail === "real"
                            ? allRealTrades.map((t: any) => {
                                // stepped 시뮬은 원본 sold 거래의 날짜+종목명 사용
                                if (t.strategy_type === "stepped") {
                                  const mt = trades.find(tr => tr.id === t.trade_id);
                                  const simCode = mt?.code || "";
                                  // sim_only의 code로 원본 sold 거래를 역추적
                                  const origTrade = simCode ? soldTrades.find(tr => tr.code === simCode) : null;
                                  const origDate = origTrade?.created_at?.slice(0, 10) || t.created_at?.slice(0, 10) || "보유";
                                  return { ...t, _date: origDate, _displayName: t._name || mt?.name || "—", _displaySub: "시뮬 매수 " + (t.entry_price?.toLocaleString() || "") + "원" };
                                }
                                return { ...t, _date: t.created_at?.slice(0, 10) || "보유", _displayName: t.name, _displaySub: t.code };
                              })
                            : (strategyDetail === "time" ? allTimeSims : strategyDetail === "api_leader" ? apiLeaderSims : allSims).map((s: any) => {
                                const mt = [...soldTrades, ...activeTrades].find(t => t.id === s.trade_id);
                                return { ...s, _date: mt?.created_at?.slice(0, 10) || "보유", _displayName: s._name || mt?.name || "—", _displaySub: `매수 ${s.entry_price?.toLocaleString()}원` };
                              });
                          if (items.length === 0) {
                            return (
                              <div className="text-center py-10 space-y-3">
                                <div className="text-2xl">📭</div>
                                <div className="text-sm font-medium t-text">아직 데이터가 없습니다</div>
                                <div className="text-xs t-text-dim leading-relaxed">
                                  {strategyDetail === "api_leader"
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
                          const todayStr = new Date().toISOString().slice(0, 10);
                          // 체크된 날짜의 합산
                          const includedItems = items.filter(it => !excludedDates.has(it._date));
                          const filteredPnl = includedItems.length > 0 ? includedItems.reduce((s: number, t: any) => s + (t.pnl_pct ?? 0), 0) / includedItems.length : 0;
                          const allChecked = excludedDates.size === 0;

                          return (
                            <>
                            {/* 합산 + 전체선택 */}
                            <div className="flex items-center justify-between mb-3 p-2.5 rounded-lg" style={{ background: "var(--bg)" }}>
                              <div className="flex items-center gap-3">
                                <div className={`text-lg font-bold tabular-nums ${filteredPnl >= 0 ? "text-red-400" : "text-blue-400"}`}>
                                  {filteredPnl >= 0 ? "+" : ""}{filteredPnl.toFixed(2)}%
                                </div>
                                <div className="text-[10px] t-text-dim">{includedItems.length}건</div>
                              </div>
                              <button onClick={() => setExcludedDates(allChecked ? new Set(dates) : new Set())}
                                className="text-[10px] t-text-dim hover:t-text transition px-2 py-1 rounded-lg" style={{ border: "1px solid var(--border)" }}>
                                {allChecked ? "전체 해제" : "전체 선택"}
                              </button>
                            </div>
                            <div className="space-y-2">
                              {dates.map(date => {
                                const group = grouped[date];
                                const dayPnl = group.reduce((s: number, t: any) => s + (t.pnl_pct ?? 0), 0);
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
                                      </div>
                                      <span className={`text-[11px] font-semibold tabular-nums ${dayPnl >= 0 ? "text-red-400" : "text-blue-400"}`}>
                                        {dayPnl >= 0 ? "+" : ""}{dayPnl.toFixed(2)}%
                                      </span>
                                    </summary>
                                    <div className="ml-4 mt-1.5 pl-3 space-y-1 border-l-2" style={{ borderColor: 'var(--border)' }}>
                                      {group.map((item: any, i: number) => {
                                        const buyPrice = item.entry_price || item.filled_price || item.order_price || 0;
                                        const sellPrice = item.exit_price || item.sell_price || 0;
                                        const buyTime = (item.filled_at || item.created_at || "")?.slice(11, 16);
                                        const sellTime = (item.exited_at || item.sold_at || "")?.slice(11, 16);
                                        const formatTime = (t: string) => {
                                          if (!t) return "";
                                          const [h, m] = t.split(":").map(Number);
                                          const kh = (h + 9) % 24;  // UTC→KST
                                          return `${kh}:${m.toString().padStart(2, "0")}`;
                                        };
                                        return (
                                        <div key={i} className={`text-[11px] px-2.5 py-2 rounded-lg ${isChecked ? "" : "opacity-40"}`} style={{ background: "var(--bg)" }}>
                                          <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2 min-w-0">
                                              <span className="t-text font-medium truncate">{item._displayName}</span>
                                              {item._isActive && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-blue-500/10 text-blue-400">보유</span>}
                                              {item._isCapped && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-red-500/10 text-red-400">{(item.pnl_pct ?? 0) >= 0 ? "익절" : "손절"}</span>}
                                              {(item.exit_reason || item.sell_reason) && !item._isActive && (() => { const r = item.exit_reason || item.sell_reason; return <span className="text-[9px] px-1.5 py-0.5 rounded-full t-text-dim" style={{ background: "var(--bg-muted)" }}>{r === "stop_loss" ? "손절" : r === "take_profit" ? "익절" : r === "time_exit" ? "시간매도" : r === "stepped_trailing" ? "Stepped" : r === "trailing_stop" ? "급락손절" : r === "eod_close" ? "장마감" : r === "manual_sell" ? "수동매도" : r === "false_stop" ? "오류매도" : r === "parent_sold" ? "실전매도" : r}</span>; })()}
                                            </div>
                                            <span className={`tabular-nums font-bold shrink-0 ${(item.pnl_pct ?? 0) >= 0 ? "text-red-400" : "text-blue-400"}`}>
                                              {(item.pnl_pct ?? 0) >= 0 ? "+" : ""}{(item.pnl_pct ?? 0).toFixed(2)}%
                                            </span>
                                          </div>
                                          <div className="flex items-center gap-1 mt-1 text-[9px] t-text-sub">
                                            {buyPrice > 0 && <><span className="t-text-dim">매수</span> <span className="font-medium tabular-nums">{buyPrice.toLocaleString()}</span>{buyTime && <span className="t-text-dim ml-0.5">{formatTime(buyTime)}</span>}</>}
                                            {sellPrice > 0 && <><span className="t-text-dim ml-2">→</span> <span className="t-text-dim ml-1">매도</span> <span className="font-medium tabular-nums">{sellPrice.toLocaleString()}</span>{sellTime && <span className="t-text-dim ml-0.5">{formatTime(sellTime)}</span>}</>}
                                          </div>
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
                            {strategyHelpOpen === "gapup" ? "갭업 모멘텀" : strategyHelpOpen === "real" ? "5팩터+Stepped" : strategyHelpOpen === "sim" ? "고정 익절/손절" : strategyHelpOpen === "time" ? "시간전략" : "API매수∧대장주"}
                          </h4>
                          <button onClick={() => setStrategyHelpOpen(null)} className="t-text-dim hover:t-text transition"><X size={16} /></button>
                        </div>
                        <div className="text-[11px] t-text-sub leading-relaxed whitespace-pre-line">
                          {strategyHelpOpen === "gapup" ? "30개 전략 백테스트에서 Sharpe·PF·승률·일관성 모두 1위를 기록한 갭업 모멘텀 전략입니다.\n\n[종목 선정]\n① 전일 종가 대비 시가 갭업 1~5%\n② 현재가 > MA200 (200일 이동평균)\n③ 1,000원 ≤ 현재가 < 200,000원\n→ 거래량 순 상위 2종목 선정\n\n[매매 타이밍]\n09:01 — 200종목 스캔 → 즉시 매수\n09:30 — 09:01 매수 0건 시 보완 스캔\n         (거래량 전일 대비 2배 필터 추가)\n15:15 — 전 포지션 당일 청산\n\n[백테스트 성과 (검증기간)]\ntrim +5.63% | 승률 73.5% | Sharpe 0.639\nPF 6.17 | 오버나이트 리스크 없음"
                           : strategyHelpOpen === "real" ? "기존 실전 적용했던 5팩터 스코어 + Stepped Trailing 전략입니다.\n현재는 갭업 모멘텀으로 전환되어 가상 추적 중입니다.\n\n[종목 선정: 5팩터 스코어]\n① API 매수 +30점 (적극매수 +10 추가)\n② Vision 매수 +20점 (적극매수 +5 추가)\n③ 대장주 1등 +25점 / 테마소속 +15점\n④ 저가주 <2만원 +5점\n⑤ 급락반등 -10%↓&외인50만주↑ +35점\n→ 최소 20점 이상, 상위 2종목 선정\n\n[Criteria 가점 필터 (선택)]\n수급 양호 +10 / 골든크로스 +5 / 저항돌파 +5\n\n[매도: Stepped Trailing 공격형]\n+7%→본전, +15%→+7%, +20%→+15%\n+25%→+20%, +30%+→고점-3%\nSL: -2% (기본 손절)"
                           : strategyHelpOpen === "sim" ? "고정 익절/손절 전략 시뮬레이션입니다.\n\n실전 매수와 동일한 종목·가격으로 가상 포지션을 생성하고, 고정 TP/SL 조건으로 매도 시뮬레이션합니다.\n\nTP: +7% (보유일수 연동 상향)\nSL: -2%\nTrailing: 고점 대비 -3% 하락 시 매도"
                           : strategyHelpOpen === "time" ? "시간 기반 매도 전략 시뮬레이션입니다.\n\n실전 매수와 동일한 종목·가격으로 가상 포지션을 생성하고, 11:00 KST에 무조건 매도합니다.\n\n매수: 09:30 (실전과 동일)\n매도: 11:00 KST (시장 열기 피크)\nSL: -2% (11:00 전 손절)\n\n장 초반 모멘텀만 캡처하는 단기 전략으로, 오버나이트 리스크가 없습니다."
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
        <div className="grid grid-cols-2 gap-3">
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
                currentPrice={prices[t.code]?.price} todayChangeRate={prices[t.code]?.changeRate} />
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
    <div className="rounded-xl p-3 border" style={{ background: "var(--bg-card)", borderColor: "var(--border)", boxShadow: "var(--shadow-card)" }}>
      <div className="flex items-center gap-1.5 mb-1.5">
        <span className="t-text-sub">{icon}</span>
        <span className="text-[11px] font-medium t-text-sub">{label}</span>
      </div>
      <div className="text-xl font-bold" style={{ color: color || "var(--text-primary)" }}>{value}</div>
      {sub && <div className="text-[11px] t-text-sub mt-1">{sub}</div>}
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

function TradeRow({ trade, type, onSell, selling, currentPrice, todayChangeRate }: {
  trade: Trade;
  type: "active" | "pending" | "closed" | "sell_requested";
  onSell?: () => void;
  selling?: boolean;
  currentPrice?: number;
  todayChangeRate?: number;
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
      {type === "active" && currentPrice != null && (
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
                {trade.pnl_pct >= 0 ? "+" : ""}{Math.round(trade.filled_price * trade.quantity * trade.pnl_pct / 100).toLocaleString("ko-KR")}원
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
