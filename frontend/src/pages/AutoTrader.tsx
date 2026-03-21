import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Clock, DollarSign, BarChart3, Sun, Moon, ArrowLeft } from "lucide-react";
import { supabase } from "../lib/supabase";

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

export default function AutoTrader({ onToggleTheme, isDark }: { onToggleTheme?: () => void; isDark?: boolean }) {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTrades();
  }, []);

  async function fetchTrades() {
    setLoading(true);
    const { data, error } = await supabase
      .from("auto_trades")
      .select("*")
      .order("created_at", { ascending: false });
    if (!error && data) setTrades(data as Trade[]);
    setLoading(false);
  }

  const active = trades.filter((t) => t.status === "filled");
  const pending = trades.filter((t) => t.status === "pending");
  const closed = trades.filter((t) => t.status === "sold");

  // 성과 요약
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

  // 보유 종목 평가
  const totalInvested = active.reduce((s, t) => s + (t.filled_price ?? t.order_price) * t.quantity, 0);

  return (
    <div className="min-h-screen pb-4" style={{ background: "var(--bg)" }}>
      {/* 헤더 */}
      <header
        className="sticky top-0 z-40 backdrop-blur-md border-b px-4 py-3"
        style={{ background: "var(--bg-header)", borderColor: "var(--border)" }}
      >
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <a href="#/" className="t-text-sub hover:t-text"><ArrowLeft size={18} /></a>
            <h1 className="text-base font-bold t-text">모의투자 리포트</h1>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={fetchTrades} className="text-xs t-text-sub hover:t-text px-2 py-1 rounded t-card-alt">새로고침</button>
            {onToggleTheme && (
              <button onClick={onToggleTheme} className="p-1.5 rounded-lg t-text-sub hover:t-text">
                {isDark ? <Sun size={16} /> : <Moon size={16} />}
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 pt-4 space-y-4">
        {loading ? (
          <div className="text-center py-20 t-text-sub">로딩 중...</div>
        ) : (
          <>
            {/* 성과 요약 */}
            <div className="grid grid-cols-2 gap-3">
              <SummaryCard icon={<BarChart3 size={16} />} label="총 매매" value={`${totalTrades}건`} sub={`승 ${wins} / 패 ${losses}`} />
              <SummaryCard icon={<TrendingUp size={16} />} label="승률" value={`${winRate}%`} sub={`평균 수익률 ${avgPnl}%`} />
              <SummaryCard icon={<DollarSign size={16} />} label="총 수익" value={formatKRW(Math.round(totalPnl))} color={totalPnl >= 0 ? "var(--success)" : "var(--danger)"} />
              <SummaryCard icon={<Clock size={16} />} label="보유 중" value={`${active.length}종목`} sub={`투자금 ${formatKRW(totalInvested)}`} />
            </div>

            {/* 보유 중 */}
            {active.length > 0 && (
              <Section title="보유 중" count={active.length}>
                {active.map((t) => (
                  <TradeRow key={t.id} trade={t} type="active" />
                ))}
              </Section>
            )}

            {/* 주문 대기 */}
            {pending.length > 0 && (
              <Section title="주문 대기" count={pending.length}>
                {pending.map((t) => (
                  <TradeRow key={t.id} trade={t} type="pending" />
                ))}
              </Section>
            )}

            {/* 매매 이력 */}
            <Section title="매매 이력" count={closed.length}>
              {closed.length === 0 ? (
                <div className="text-center py-8 t-text-sub text-sm">아직 완료된 매매가 없습니다</div>
              ) : (
                closed.map((t) => (
                  <TradeRow key={t.id} trade={t} type="closed" />
                ))
              )}
            </Section>
          </>
        )}
      </main>
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

function TradeRow({ trade, type }: { trade: Trade; type: "active" | "pending" | "closed" }) {
  const buyPrice = trade.filled_price ?? trade.order_price;
  const amount = buyPrice * trade.quantity;
  const pnl = trade.pnl_pct ?? 0;

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
        {type === "active" && (
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(37,99,235,0.1)", color: "var(--accent)" }}>
            보유 중
          </span>
        )}
        {type === "pending" && (
          <span className="text-xs px-2 py-0.5 rounded-full t-card-alt t-text-sub">주문 대기</span>
        )}
      </div>
      <div className="flex items-center justify-between text-xs t-text-sub">
        <div>
          {formatKRW(buyPrice)} × {trade.quantity.toLocaleString()}주
          <span className="ml-1">({formatKRW(amount)})</span>
        </div>
        <div>{formatDate(trade.created_at)}</div>
      </div>
      {type === "closed" && trade.sell_reason && (
        <div className="text-xs mt-1" style={{ color: trade.sell_reason === "take_profit" ? "var(--success)" : "var(--danger)" }}>
          {trade.sell_reason === "take_profit" ? "익절 +3%" : "손절 -3%"}
        </div>
      )}
    </div>
  );
}
