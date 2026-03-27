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
  const [savedToggles, setSavedToggles] = useState<{ chart: boolean; indicator: boolean; top_leader: boolean; all_leaders: boolean; fallback_top_leader: boolean }>({ chart: false, indicator: false, top_leader: false, all_leaders: false, fallback_top_leader: false });
  const [buySaving, setBuySaving] = useState(false);
  const [toastMsg, setToastMsg] = useState<{ text: string; type: "ok" | "fail" } | null>(null);
  const [strategyType, setStrategyType] = useState<"fixed" | "stepped">("fixed");
  const [savedStrategyType, setSavedStrategyType] = useState<"fixed" | "stepped">("fixed");
  const [strategySaving, setStrategySaving] = useState(false);
  const [showStrategyCompare, setShowStrategyCompare] = useState(false);
  const [strategyDetail, setStrategyDetail] = useState<"real" | "sim" | null>(null);
  const [simulations, setSimulations] = useState<any[]>([]);

  useEffect(() => {
    function loadData(u: any) {
      setUser(u);
      setAuthChecked(true);
      if (u) {
        fetchTrades();
        getTradePct().then(({ take_profit, stop_loss, trailing_stop, buy_signal_mode }) => {
          setTakeProfit(take_profit);
          setStopLoss(stop_loss);
          setTrailingStop(trailing_stop);
          { const t = parseBuyMode(buy_signal_mode); setBuyToggles(t); setSavedToggles(t); }
        }).catch(() => {});
        // strategy_type 로드
        Promise.resolve(supabase.from("alert_config").select("strategy_type").limit(1).maybeSingle()).then(({ data: cfg }) => {
          if (cfg?.strategy_type) { setStrategyType(cfg.strategy_type); setSavedStrategyType(cfg.strategy_type); }
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
        const activeCodes = (data as Trade[]).filter(t => t.status === "filled").map(t => t.code).filter(Boolean);
        if (activeCodes.length > 0) {
          fetchKisPrices(activeCodes).then(kisData => {
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
    getTradePct().then(({ take_profit, stop_loss, trailing_stop, buy_signal_mode }) => {
      setTakeProfit(take_profit); setStopLoss(stop_loss); setTrailingStop(trailing_stop);
      { const t = parseBuyMode(buy_signal_mode); setBuyToggles(t); setSavedToggles(t); }
    }).catch(() => {});
    Promise.resolve(supabase.from("alert_config").select("strategy_type").limit(1).maybeSingle()).then(({ data: cfg }) => {
      if (cfg?.strategy_type) { setStrategyType(cfg.strategy_type); setSavedStrategyType(cfg.strategy_type); }
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
      {/* 투자 전략 선택 */}
      <div className="rounded-xl p-3 border" style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}>
        <div className="text-[11px] font-semibold t-text mb-2">투자 전략</div>
        <div className="flex gap-2">
          {(["stepped", "fixed"] as const).map(st => (
            <button key={st} onClick={() => {
              setStrategyType(st);
              if (st === "stepped") setShowPctEdit(false);
            }}
              className={`flex-1 text-[11px] py-2 rounded-lg font-medium transition ${
                strategyType === st
                  ? "bg-blue-600 text-white"
                  : "t-text-sub hover:t-text"
              }`}
              style={strategyType !== st ? { background: "var(--bg)", border: "1px solid var(--border)" } : {}}>
              {st === "stepped" ? "Stepped Trailing" : "고정 익절/손절"}
            </button>
          ))}
        </div>
        {strategyType === "stepped" && (
          <details className="mt-2 rounded-lg" style={{ background: "var(--bg)" }}>
            <summary className="flex items-center gap-1 p-2.5 text-[9px] font-medium t-text-sub cursor-pointer hover:t-text transition select-none list-none [&::-webkit-details-marker]:hidden">
              <ChevronRight size={10} className="transition-transform [[open]>&]:rotate-90 shrink-0" />
              Step 구간
            </summary>
            <div className="px-2.5 pb-2.5 space-y-1">
              {[
                { trigger: "+5%", stop: "0%", color: "#94a3b8", barW: "20%" },
                { trigger: "+10%", stop: "+5%", color: "#22c55e", barW: "40%" },
                { trigger: "+15%", stop: "+10%", color: "#22c55e", barW: "60%" },
                { trigger: "+20%", stop: "+15%", color: "#16a34a", barW: "80%" },
                { trigger: "+25%+", stop: `고점${trailingStop}%`, color: "#15803d", barW: "100%" },
              ].map((s, i) => (
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
        {/* 익절/손절 설정 — 전략 카드 내부 */}
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
              const allRealTrades = [...soldTrades.map(t => ({ ...t, _isActive: false })), ...activeWithPnl];
              const realPnl = allRealTrades.reduce((sum, t) => sum + (t.pnl_pct || 0), 0);

              const closedSims = simulations.filter(s => s.status === "closed");
              const openSims = simulations.filter(s => s.status === "open");
              // open 시뮬레이션의 미실현 PnL (전략별 TP/SL 적용)
              const openSimsWithPnl = openSims.map((s: any) => {
                const matchTrade = activeTrades.find(t => t.id === s.trade_id);
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
              const simPnl = allSims.reduce((sum, s: any) => sum + (s.pnl_pct || 0), 0);

              const simStrategy = closedSims[0]?.strategy_type || openSims[0]?.strategy_type || (strategyType === "stepped" ? "fixed" : "stepped");
              const realLabel = strategyType === "stepped" ? "Stepped Trailing" : "고정 익절/손절";
              const simLabel = simStrategy === "stepped" ? "Stepped Trailing" : "고정 익절/손절";
              const realWins = realPnl >= simPnl;

              return (
                <>
                  <div className="flex gap-2">
                    <button onClick={() => setStrategyDetail("real")}
                      className={`flex-1 p-2 rounded-lg text-center border cursor-pointer transition ${realWins ? "border-red-500/30" : "border-transparent"}`} style={{ background: "var(--bg)" }}>
                      <div className="text-[9px] t-text-dim mb-0.5">{realLabel} (실제) {realWins && allRealTrades.length > 0 && "✓"}</div>
                      <div className={`text-sm font-bold tabular-nums ${realPnl >= 0 ? "text-red-400" : "text-blue-400"}`}>
                        {realPnl >= 0 ? "+" : ""}{realPnl.toFixed(1)}%
                      </div>
                      <div className="text-[9px] t-text-dim">{allRealTrades.length}건</div>
                    </button>
                    <button onClick={() => setStrategyDetail("sim")}
                      className={`flex-1 p-2 rounded-lg text-center border cursor-pointer transition ${!realWins ? "border-red-500/30" : "border-transparent"}`} style={{ background: "var(--bg)" }}>
                      <div className="text-[9px] t-text-dim mb-0.5">{simLabel} (가상) {!realWins && allSims.length > 0 && "✓"}</div>
                      <div className={`text-sm font-bold tabular-nums ${simPnl >= 0 ? "text-red-400" : "text-blue-400"}`}>
                        {simPnl >= 0 ? "+" : ""}{simPnl.toFixed(1)}%
                      </div>
                      <div className="text-[9px] t-text-dim">{allSims.length}건</div>
                    </button>
                  </div>
                  {allRealTrades.length === 0 && allSims.length === 0 && (
                    <div className="text-[10px] t-text-dim text-center py-2">아직 비교 데이터가 없습니다</div>
                  )}
                  {/* 바텀시트 */}
                  {strategyDetail && createPortal(
                    <div className="fixed inset-0 z-[9999] anim-fade-in" onClick={() => setStrategyDetail(null)}>
                      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
                      <div className="fixed bottom-0 left-0 right-0 z-[61] max-h-[70vh] overflow-y-auto rounded-t-2xl t-card border-t t-border-light p-5 sm:max-w-lg sm:mx-auto sm:rounded-2xl sm:bottom-auto sm:top-1/2 sm:-translate-y-1/2 anim-slide-up sm:anim-scale-in"
                        style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 1.5rem)' }} onClick={e => e.stopPropagation()}>
                        {/* 드래그 핸들 + 닫기 */}
                        <div className="flex items-center justify-center relative mb-3">
                          <div className="w-8 h-1 rounded-full sm:hidden" style={{ background: 'var(--border)' }} />
                          <button onClick={() => setStrategyDetail(null)} className="absolute right-0 top-1/2 -translate-y-1/2 p-1 t-text-dim hover:t-text transition">
                            <X size={18} />
                          </button>
                        </div>
                        <h3 className="text-sm font-bold t-text mb-3">
                          {strategyDetail === "real" ? `${realLabel} (실제)` : `${simLabel} (가상)`}
                        </h3>
                        {/* 합산 */}
                        <div className="flex items-center gap-3 mb-3 p-2.5 rounded-lg" style={{ background: "var(--bg)" }}>
                          <div className={`text-lg font-bold tabular-nums ${(strategyDetail === "real" ? realPnl : simPnl) >= 0 ? "text-red-400" : "text-blue-400"}`}>
                            {(strategyDetail === "real" ? realPnl : simPnl) >= 0 ? "+" : ""}{(strategyDetail === "real" ? realPnl : simPnl).toFixed(2)}%
                          </div>
                          <div className="text-[10px] t-text-dim">
                            {strategyDetail === "real" ? allRealTrades.length : allSims.length}건
                          </div>
                        </div>
                        {/* 종목 리스트 — 날짜별 그룹핑 */}
                        {(() => {
                          const items = strategyDetail === "real"
                            ? allRealTrades.map((t: any) => ({ ...t, _date: t.created_at?.slice(0, 10) || "보유", _displayName: t.name, _displaySub: t.code }))
                            : allSims.map((s: any) => {
                                const mt = [...soldTrades, ...activeTrades].find(t => t.id === s.trade_id);
                                return { ...s, _date: mt?.created_at?.slice(0, 10) || "보유", _displayName: s._name || mt?.name || "—", _displaySub: `${s.entry_price?.toLocaleString()}원` };
                              });
                          // 날짜별 그룹핑
                          const grouped: Record<string, typeof items> = {};
                          for (const item of items) {
                            const key = item._date;
                            if (!grouped[key]) grouped[key] = [];
                            grouped[key].push(item);
                          }
                          const dates = Object.keys(grouped).sort((a, b) => b.localeCompare(a));
                          const todayStr = new Date().toISOString().slice(0, 10);

                          return (
                            <div className="space-y-3">
                              {dates.map(date => {
                                const group = grouped[date];
                                const dayPnl = group.reduce((s: number, t: any) => s + (t.pnl_pct ?? 0), 0);
                                const isToday = date === todayStr || date === "보유";
                                return (
                                  <details key={date} open={isToday}>
                                    <summary className="flex items-center justify-between px-2 py-1.5 rounded-lg cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden hover:opacity-80 transition" style={{ background: "var(--bg)" }}>
                                      <div className="flex items-center gap-2">
                                        <ChevronDown size={12} className="t-text-dim transition-transform [details:not([open])>&]:-rotate-90" />
                                        <span className="text-[11px] font-medium t-text">{date}</span>
                                        <span className="text-[10px] t-text-dim">{group.length}건</span>
                                      </div>
                                      <span className={`text-[11px] font-semibold tabular-nums ${dayPnl >= 0 ? "text-red-400" : "text-blue-400"}`}>
                                        {dayPnl >= 0 ? "+" : ""}{dayPnl.toFixed(2)}%
                                      </span>
                                    </summary>
                                    <div className="space-y-1 mt-1">
                                      {group.map((item: any, i: number) => (
                                        <div key={i} className="flex items-center justify-between text-[11px] px-2.5 py-2 rounded-lg" style={{ background: "var(--bg)" }}>
                                          <div className="flex items-center gap-2 min-w-0">
                                            <span className="t-text font-medium truncate">{item._displayName}</span>
                                            <span className="text-[10px] t-text-dim">{item._displaySub}</span>
                                            {item._isActive && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-blue-500/10 text-blue-400">보유</span>}
                                            {item._isCapped && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-red-500/10 text-red-400">{(item.pnl_pct ?? 0) >= 0 ? "익절" : "손절"}</span>}
                                          </div>
                                          <span className={`tabular-nums font-bold shrink-0 ${(item.pnl_pct ?? 0) >= 0 ? "text-red-400" : "text-blue-400"}`}>
                                            {(item.pnl_pct ?? 0) >= 0 ? "+" : ""}{(item.pnl_pct ?? 0).toFixed(2)}%
                                          </span>
                                        </div>
                                      ))}
                                    </div>
                                  </details>
                                );
                              })}
                            </div>
                          );
                        })()}
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

      {/* 매집 종목 선정 기준 설정 — 토글 */}
      <details open className="rounded-xl border" style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}>
        <summary className="flex items-center justify-between p-3 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden">
          <div className="flex items-center gap-1">
            <ChevronRight size={10} className="transition-transform [[open]>&]:rotate-90 t-text-dim shrink-0" />
            <span className="text-[11px] font-semibold t-text">매집 종목 선정 기준 설정</span>
          </div>
          <button onClick={(e) => { e.preventDefault(); setShowBuyHelp(true); }} className="t-text-dim hover:t-text transition">
            <HelpCircle size={13} />
          </button>
        </summary>
        <div className="px-3 pb-3 space-y-0.5">
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
                    // 대장주 1위 ON → 나머지 전부 OFF (독립 모드)
                    if (opt.key === "top_leader" && !isOn) {
                      next.chart = false; next.indicator = false;
                      next.all_leaders = false; next.fallback_top_leader = false;
                    }
                    // 차트/지표/대장주전체/fallback ON → 대장주 1위 OFF (공존 가능)
                    if ((opt.key === "chart" || opt.key === "indicator" || opt.key === "all_leaders" || opt.key === "fallback_top_leader") && !isOn) {
                      next.top_leader = false;
                    }
                    // fallback ON → 차트/지표/대장주전체 자동 ON
                    if (opt.key === "fallback_top_leader" && !isOn) {
                      next.chart = true; next.indicator = true; next.all_leaders = true;
                    }
                    // 차트/지표/대장주전체 모두 OFF가 되면 fallback도 OFF
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
        </div>
        {/* 조합 미리보기 + 확인 버튼 */}
        <div className="mx-3 mb-3 mt-2 pt-2 border-t" style={{ borderColor: "var(--border)" }}>
          <div className="text-[10px] t-text-sub mb-2">
            {(() => {
              const { chart, indicator, top_leader, all_leaders, fallback_top_leader } = buyToggles;
              if (top_leader) return "테마별 거래대금 1위 종목만 매집 (독립 모드)";
              const parts = [chart && "차트", indicator && "지표", all_leaders && "대장주전체"].filter(Boolean) as string[];
              if (parts.length === 0 && !fallback_top_leader) return "매집 중지 — 모든 조건 OFF";
              let desc = parts.length === 1 ? `${parts[0]} 조건 매집` : parts.length >= 2 ? `${parts.join(" + ")} AND 조건 매집` : "";
              if (fallback_top_leader) desc += desc ? " → 0건 시 대장주 1위로 대체" : "대장주 1위로 매집";
              return desc;
            })()}
          </div>
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
        </div>
      </details>

      {/* 성과 요약 */}
      <div className="grid grid-cols-2 gap-3">
        <SummaryCard icon={<BarChart3 size={16} />} label="총 매매" value={`${totalTrades}건`} sub={`승 ${wins} / 패 ${losses}`} />
        <SummaryCard icon={<TrendingUp size={16} />} label="승률" value={`${winRate}%`} sub={`평균 수익률 ${avgPnl}%`} />
        <SummaryCard icon={<DollarSign size={16} />} label="총 수익" value={formatKRW(Math.round(totalPnl))} color={totalPnl >= 0 ? "var(--up)" : "var(--down)"} />
        <SummaryCard icon={<Clock size={16} />} label="보유 중" value={`${active.length}종목`} sub={`투자금 ${formatKRW(totalInvested)}`} />
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
      <div className="flex items-center gap-1.5 mb-1">
        <span className="t-text-sub">{icon}</span>
        <span className="text-xs t-text-sub">{label}</span>
      </div>
      <div className="text-lg font-bold" style={{ color: color || "var(--text-primary)" }}>{value}</div>
      {sub && <div className="text-xs t-text-sub mt-0.5">{sub}</div>}
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
      <div className="flex items-center justify-between text-[10px] t-text-dim">
        <span>{formatKRW(buyPrice)} × {trade.quantity.toLocaleString()}주 ({formatKRW(amount)})</span>
        <span>매수 {formatDate(trade.created_at)}</span>
      </div>
      {type === "closed" && (
        <div className="text-xs mt-1 space-y-0.5">
          {trade.sell_reason && (
            <div style={{ color: (trade.sell_reason === "take_profit" || trade.sell_reason === "stepped_trailing") ? "var(--up)" : trade.sell_reason === "eod_close" ? "var(--text-secondary)" : "var(--down)" }}>
              {trade.sell_reason === "take_profit" ? "익절" : trade.sell_reason === "stepped_trailing" ? "Stepped 익절" : trade.sell_reason === "eod_close" ? "장 마감 청산" : trade.sell_reason === "trailing_stop" ? "급락 손절" : trade.sell_reason === "manual_sell" ? "수동 매도" : trade.sell_reason === "stop_loss" ? "손절" : trade.sell_reason || "매도"}
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
                  <span className="text-xs font-medium t-text">{date}</span>
                  <span className="text-[10px] t-text-dim">{items.length}건</span>
                </div>
                <span className={`text-[11px] font-medium ${avgPnl > 0 ? "text-red-500" : avgPnl < 0 ? "text-blue-500" : "t-text-dim"}`}>
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
