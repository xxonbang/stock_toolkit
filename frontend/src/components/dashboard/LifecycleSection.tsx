import {
  ScatterChart, Scatter, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell,
} from "recharts";
import { SectionHeader } from "../HelpDialog";

const STAGE_FILL: Record<string, string> = {
  "탄생": "#22c55e", "성장": "#eab308", "과열": "#ef4444", "쇠퇴": "#9ca3af",
};
const STAGE_DOT: Record<string, string> = {
  "탄생": "bg-green-500", "성장": "bg-yellow-500", "과열": "bg-red-500", "쇠퇴": "bg-gray-400",
};

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

export default function LifecycleSection({ lifecycle, ts, setLifecyclePopup }: {
  lifecycle: any[] | null;
  ts: string;
  setLifecyclePopup: (v: { theme: string; stocks: string[]; stage: string; strategy?: string } | null) => void;
}) {
  return (
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
            <button onClick={() => l.stocks?.length && setLifecyclePopup({ theme: l.theme, stocks: l.stocks, stage: l.stage, strategy: l.strategy })}
              className="text-sm font-medium truncate min-w-0 text-left hover:underline">{l.theme}</button>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs t-text-sub">{l.avg_change >= 0 ? "+" : ""}{l.avg_change}%</span>
              <button onClick={() => setLifecyclePopup({ theme: l.theme, stocks: l.stocks || [], stage: l.stage, strategy: l.strategy })}>
                <Badge variant={l.stage === "과열" ? "danger" : l.stage === "성장" ? "warning" : l.stage === "탄생" ? "success" : "default"}>{l.stage}</Badge>
              </button>
            </div>
          </div>
        ))}
      </div>
        {!lifecycle?.length && <Empty />}
    </section>
  );
}
