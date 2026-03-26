import { Flame, BarChart3 } from "lucide-react";
import { SectionHeader } from "../HelpDialog";

export default function ConsecutiveSignalSection({ consecutiveSignals, ts, setStreakPopup }: {
  consecutiveSignals: any;
  ts: string;
  setStreakPopup: (v: { name: string; dates: string[] } | null) => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
  const freshness = (r: any) => {
    const last = r.dates?.[r.dates.length - 1] || "";
    if (last >= today) return "active";
    if (last >= yesterday) return "watch";
    return "ended";
  };
  const badge = (f: string) => f === "active"
    ? <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 font-medium">진행 중</span>
    : f === "watch"
    ? <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500/15 text-amber-400 font-medium">관찰</span>
    : <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-gray-500/15 text-gray-400 font-medium">종료</span>;
  const sortByFreshness = (arr: any[]) => [...arr].sort((a, b) => {
    const la = a.dates?.[a.dates.length - 1] || "";
    const lb = b.dates?.[b.dates.length - 1] || "";
    if (la !== lb) return lb.localeCompare(la);
    return (b.streak || 0) - (a.streak || 0);
  });
  const renderList = (items: any[], color: string, showStreak: boolean) => {
    const sorted = sortByFreshness(items);
    const active = sorted.filter((r: any) => freshness(r) !== "ended");
    return (
      <>
        {active.map((r: any, i: number) => (
          <div key={i} className="flex items-center justify-between py-1.5 border-b t-border-light last:border-b-0">
            <div className="flex items-center gap-1.5">
              <span className="text-[13px] font-medium t-text">{r.name}</span>
              <span className="text-[10px] t-text-dim">{r.code}</span>
              {badge(freshness(r))}
            </div>
            <button onClick={() => r.dates?.length && setStreakPopup({ name: r.name, dates: r.dates })}
              className="flex items-center gap-2 hover:opacity-70 transition">
              <span className={`text-[11px] font-bold ${color}`}>{showStreak ? `${r.streak}일 연속` : `${r.streak}일`}</span>
              <span className="text-[10px] t-text-dim">{r.dates?.[r.dates.length - 1]}</span>
            </button>
          </div>
        ))}
      </>
    );
  };
  return (
  <section className="t-card rounded-xl p-4">
    <SectionHeader id="consecutive" timestamp={ts}>연속 시그널</SectionHeader>
    {(() => {
      const andItems = consecutiveSignals.and_condition || [];
      const orItems = consecutiveSignals.or_condition || [];
      const andActive = andItems.filter((r: any) => freshness(r) !== "ended");
      const orActive = orItems.filter((r: any) => freshness(r) !== "ended");
      const allEnded = [...andItems, ...orItems].filter((r: any) => freshness(r) === "ended");
      return <>
        {andActive.length > 0 && (
          <div className="mb-3">
            <div className="text-[11px] font-semibold text-red-400 mb-1.5 flex items-center gap-1"><Flame size={12} /> 매수 + 대장주 동시 (AND)</div>
            <div className="space-y-1">{renderList(andItems, "text-red-400", true)}</div>
          </div>
        )}
        {orActive.length > 0 && (
          <div>
            <div className="text-[11px] font-semibold text-amber-400 mb-1.5 flex items-center gap-1"><BarChart3 size={12} /> 매수 또는 대장주 (OR)</div>
            <div className="space-y-1">{renderList(orItems.slice(0, 15), "text-amber-400", false)}</div>
          </div>
        )}
        {andActive.length === 0 && orActive.length === 0 && allEnded.length > 0 && (
          <div className="text-[11px] t-text-dim">현재 활성 연속 신호 없음</div>
        )}
        {allEnded.length > 0 && (andActive.length > 0 || orActive.length > 0) && (
          <details className="mt-2">
            <summary className="text-[10px] t-text-dim cursor-pointer hover:underline py-1">종료된 신호 ({allEnded.length})</summary>
            {allEnded.map((r: any, i: number) => (
              <div key={i} className="flex items-center justify-between py-1 opacity-40">
                <div className="flex items-center gap-1.5">
                  <span className="text-[12px] t-text">{r.name}</span>
                  <span className="text-[10px] t-text-dim">{r.code}</span>
                </div>
                <span className="text-[10px] t-text-dim">{r.streak}일 · {r.dates?.[r.dates.length - 1]}</span>
              </div>
            ))}
          </details>
        )}
      </>;
    })()}
  </section>
  );
}
