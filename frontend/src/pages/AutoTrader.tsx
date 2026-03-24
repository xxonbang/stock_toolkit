import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Clock, DollarSign, BarChart3, Settings, ChevronDown, RefreshCw } from "lucide-react";
import { supabase, STORAGE_KEY, setAccessToken, fetchKisPrices } from "../lib/supabase";
import { getTradePct, setAlertConfig } from "../lib/supabase";

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

export default function AutoTrader() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<any>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [selling, setSelling] = useState<Set<string>>(new Set());
  const [takeProfit, setTakeProfit] = useState(7.0);
  const [stopLoss, setStopLoss] = useState(-2.0);
  const [prices, setPrices] = useState<Record<string, number>>({});
  const [priceRefreshing, setPriceRefreshing] = useState(false);
  const [showPctEdit, setShowPctEdit] = useState(false);
  const [pctSaving, setPctSaving] = useState(false);
  const [pctResult, setPctResult] = useState("");

  useEffect(() => {
    function loadData(u: any) {
      setUser(u);
      setAuthChecked(true);
      if (u) {
        fetchTrades();
        getTradePct().then(({ take_profit, stop_loss }) => {
          setTakeProfit(take_profit);
          setStopLoss(stop_loss);
        }).catch(() => {});
      } else {
        setLoading(false);
      }
    }

    // localStorage에서 즉시 세션 복원 (getUser() hang 방지)
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const raw = JSON.parse(stored);
        const sessionStr = (raw?.value && raw?.__expire__) ? raw.value : stored;
        const parsed = typeof sessionStr === "string" ? JSON.parse(sessionStr) : raw;
        if (parsed?.user) {
          setAccessToken(parsed.access_token ?? null);
          loadData(parsed.user);
        } else {
          setAuthChecked(true);
          setLoading(false);
        }
      } else {
        setAuthChecked(true);
        setLoading(false);
      }
    } catch {
      setAuthChecked(true);
      setLoading(false);
    }

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session?.user) {
        setAccessToken(session.access_token ?? null);
      }
      loadData(session?.user ?? null);
    });
    return () => { subscription.unsubscribe(); };
  }, []);

  async function fetchTrades() {
    setLoading(true);
    try {
      const { data, error } = await supabase
        .from("auto_trades")
        .select("*")
        .order("created_at", { ascending: false });
      if (!error && data) setTrades(data as Trade[]);
    } catch {}
    setLoading(false);
  }

  async function refreshPrices() {
    if (priceRefreshing) return;
    const codes = trades.filter(t => t.status === "filled").map(t => t.code).filter(Boolean);
    if (!codes.length) return;
    setPriceRefreshing(true);
    try {
      const kisData = await fetchKisPrices(codes);
      const map: Record<string, number> = {};
      for (const [code, p] of Object.entries(kisData)) {
        if (p.current_price) map[code] = p.current_price;
      }
      if (Object.keys(map).length > 0) setPrices(map);
    } catch (e) {
      console.warn("시세 조회 실패:", e);
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
        <div className="text-2xl mb-2">📊</div>
        데이터 로딩 중...
      </div>
    );
  }

  if (!user) {
    return (
      <div className="text-center py-20 t-text-sub">
        <div className="text-3xl mb-3">🔒</div>
        <div className="text-sm font-medium t-text mb-1">로그인이 필요합니다</div>
        <div className="text-xs t-text-dim">모의투자 현황을 확인하려면 로그인해주세요</div>
      </div>
    );
  }

  if (trades.length === 0) {
    return (
      <div className="text-center py-20 t-text-sub">
        <div className="text-3xl mb-3">📭</div>
        <div className="text-sm font-medium t-text mb-1">매매 이력 없음</div>
        <div className="text-xs t-text-dim">자동매매가 실행되면 여기에 표시됩니다</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 익절/손절 설정 */}
      <div className="rounded-xl p-3 border" style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-red-500 font-medium">익절 +{takeProfit}%</span>
            <span className="t-text-dim">/</span>
            <span className="text-blue-500 font-medium">손절 {stopLoss}%</span>
            <span className="t-text-dim">· 15:15 청산</span>
          </div>
          <button onClick={() => setShowPctEdit(!showPctEdit)}
            className="p-1.5 rounded-lg t-text-dim hover:t-text transition">
            <Settings size={14} />
          </button>
        </div>
        {showPctEdit && (
          <div className="mt-3 pt-3 border-t t-border-light space-y-3">
            <div className="flex gap-3">
              <div className="flex-1">
                <div className="text-[10px] t-text-dim mb-1">익절 (%)</div>
                <input type="number" step="0.5" min="0.5" max="30" value={takeProfit}
                  onChange={e => setTakeProfit(parseFloat(e.target.value) || 3.0)}
                  className="w-full text-[13px] px-3 py-2 rounded-lg t-text outline-none"
                  style={{ background: "var(--bg)", border: "1px solid var(--border)" }} />
              </div>
              <div className="flex-1">
                <div className="text-[10px] t-text-dim mb-1">손절 (%)</div>
                <input type="number" step="0.5" min="-30" max="-0.5" value={stopLoss}
                  onChange={e => setStopLoss(parseFloat(e.target.value) || -3.0)}
                  className="w-full text-[13px] px-3 py-2 rounded-lg t-text outline-none"
                  style={{ background: "var(--bg)", border: "1px solid var(--border)" }} />
              </div>
            </div>
            <button disabled={pctSaving} onClick={async () => {
              setPctSaving(true);
              const ok = await setAlertConfig({ take_profit_pct: takeProfit, stop_loss_pct: stopLoss });
              setPctResult(ok ? "✓ 저장 완료" : "✕ 저장 실패");
              setTimeout(() => setPctResult(""), 2000);
              setPctSaving(false);
            }}
              className="w-full text-[12px] font-medium py-2 rounded-lg text-white bg-blue-600 hover:bg-blue-500 transition disabled:opacity-40">
              {pctSaving ? "저장 중..." : "저장"}
            </button>
            {pctResult && (
              <div className={`text-[11px] text-center ${pctResult.includes("실패") ? "text-red-400" : "text-emerald-400"}`}>{pctResult}</div>
            )}
          </div>
        )}
      </div>

      {/* 성과 요약 */}
      <div className="grid grid-cols-2 gap-3">
        <SummaryCard icon={<BarChart3 size={16} />} label="총 매매" value={`${totalTrades}건`} sub={`승 ${wins} / 패 ${losses}`} />
        <SummaryCard icon={<TrendingUp size={16} />} label="승률" value={`${winRate}%`} sub={`평균 수익률 ${avgPnl}%`} />
        <SummaryCard icon={<DollarSign size={16} />} label="총 수익" value={formatKRW(Math.round(totalPnl))} color={totalPnl >= 0 ? "var(--success)" : "var(--danger)"} />
        <SummaryCard icon={<Clock size={16} />} label="보유 중" value={`${active.length}종목`} sub={`투자금 ${formatKRW(totalInvested)}`} />
      </div>

      {active.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <h2 className="text-sm font-semibold t-text">보유 중</h2>
            <span className="text-xs px-1.5 py-0.5 rounded-full t-card-alt t-text-sub">{active.length}</span>
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
                currentPrice={prices[t.code]} />
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

function TradeRow({ trade, type, onSell, selling, currentPrice }: {
  trade: Trade;
  type: "active" | "pending" | "closed" | "sell_requested";
  onSell?: () => void;
  selling?: boolean;
  currentPrice?: number;
}) {
  const buyPrice = trade.filled_price ?? trade.order_price;
  const amount = buyPrice * trade.quantity;
  const pnl = trade.pnl_pct ?? 0;
  const livePnl = currentPrice && buyPrice > 0 ? ((currentPrice - buyPrice) / buyPrice * 100) : null;
  const livePnlAmount = currentPrice && buyPrice > 0 ? (currentPrice - buyPrice) * trade.quantity : null;

  return (
    <div
      className="rounded-xl p-3 border"
      style={{ background: "var(--bg-card)", borderColor: "var(--border)", boxShadow: "var(--shadow-card)" }}
    >
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm t-text">{trade.name}</span>
          <span className="text-xs t-text-sub">{trade.code}</span>
        </div>
        {type === "closed" && (
          <span
            className="text-xs font-semibold px-2 py-0.5 rounded-full"
            style={{
              color: pnl >= 0 ? "var(--success)" : "var(--danger)",
              background: pnl >= 0 ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)",
            }}
          >
            {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}%
          </span>
        )}
        {type === "active" && livePnl !== null && (
          <span
            className="text-xs font-semibold px-2 py-0.5 rounded-full"
            style={{
              color: livePnl >= 0 ? "var(--success)" : "var(--danger)",
              background: livePnl >= 0 ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)",
            }}
          >
            {livePnl >= 0 ? "+" : ""}{livePnl.toFixed(2)}%
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
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(239,68,68,0.1)", color: "var(--danger)" }}>
            매도 대기
          </span>
        )}
      </div>
      <div className="flex items-center justify-between text-xs t-text-sub">
        <div>
          {formatKRW(buyPrice)} × {trade.quantity.toLocaleString()}주
          <span className="ml-1">({formatKRW(amount)})</span>
        </div>
        <div>{formatDate(trade.created_at)}</div>
      </div>
      {type === "active" && currentPrice != null && (
        <div className="flex items-center justify-between text-xs mt-1.5 pt-1.5 border-t t-border-light">
          <span className="t-text-sub">현재가 <span className="t-text font-medium">{formatKRW(currentPrice)}</span></span>
          {livePnlAmount !== null && (
            <span style={{ color: livePnlAmount >= 0 ? "var(--success)" : "var(--danger)" }} className="font-medium">
              {livePnlAmount >= 0 ? "+" : ""}{Math.round(livePnlAmount).toLocaleString("ko-KR")}원
            </span>
          )}
        </div>
      )}
      {type === "closed" && trade.sell_reason && (
        <div className="text-xs mt-1" style={{ color: trade.sell_reason === "take_profit" ? "var(--success)" : trade.sell_reason === "eod_close" ? "var(--text-secondary)" : "var(--danger)" }}>
          {trade.sell_reason === "take_profit" ? "익절" : trade.sell_reason === "eod_close" ? "장 마감 청산" : trade.sell_reason === "trailing_stop" ? "급락 손절" : trade.sell_reason === "manual_sell" ? "수동 매도" : "손절"}
        </div>
      )}
    </div>
  );
}

function HistoryByDate({ trades }: { trades: Trade[] }) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

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
