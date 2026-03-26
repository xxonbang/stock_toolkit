import { Shield } from "lucide-react";
import { SectionHeader } from "../HelpDialog";

function Empty({ text = "현재 해당 데이터 없음" }: { text?: string }) {
  return (
    <div className="text-center py-5">
      <div className="t-text-dim text-lg mb-1">—</div>
      <div className="text-xs t-text-dim">{text}</div>
      <div className="text-[10px] t-text-dim mt-0.5">데이터 갱신 후 표시됩니다</div>
    </div>
  );
}

export default function RiskMonitorSection({ riskMonitor, ts }: {
  riskMonitor: any[] | null;
  ts: string;
}) {
  const risks = riskMonitor || [];
  if (!risks.length) return (
    <section className="t-card rounded-xl p-4">
      <SectionHeader id="risk" timestamp={ts} count={0}>위험 종목 모니터</SectionHeader>
      <Empty />
    </section>
  );

  // 보유 종목 코드 셋 (포트폴리오는 별도 페이지로 분리)
  const holdCodes = new Set<string>();

  // 위험도 점수: warnings 개수 + level 가중치
  const scored = risks.map((r: any) => {
    const warnCount = r.warnings?.length || 0;
    const levelScore = r.level === "높음" ? 2 : 1;
    const isHeld = holdCodes.has(r.code);
    return { ...r, score: warnCount * levelScore + (isHeld ? 100 : 0), isHeld };
  }).sort((a: any, b: any) => b.score - a.score);

  const held = scored.filter((r: any) => r.isHeld);
  const notHeld = scored.filter((r: any) => !r.isHeld);
  const show = notHeld.slice(0, 8);
  const rest = notHeld.slice(8);

  const gradeStyle = (r: any) => {
    const wc = r.warnings?.length || 0;
    if (r.level === "높음" && wc >= 2) return { grade: "위험", color: "text-red-500", bg: "bg-red-500/10 border-red-500/20" };
    if (r.level === "높음" || wc >= 2) return { grade: "경고", color: "text-orange-500", bg: "bg-orange-500/8 border-orange-500/15" };
    return { grade: "주의", color: "text-amber-500", bg: "bg-amber-500/6 border-amber-500/10" };
  };

  const renderItem = (r: any, i: number, dim = false) => {
    const g = gradeStyle(r);
    const foreignAmt = r.foreign_net ? Math.abs(r.foreign_net) : 0;
    const foreignStr = foreignAmt >= 100000000 ? `${(foreignAmt / 100000000).toFixed(1)}억` : foreignAmt >= 10000 ? `${Math.round(foreignAmt / 10000)}만` : "";
    return (
      <div key={i} className={`p-2 rounded-lg border ${g.bg} ${dim ? "opacity-50" : ""}`}>
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <Shield size={14} className={`shrink-0 ${g.color}`} />
            <span className="text-sm font-medium truncate">{r.name}</span>
            <span className={`text-[9px] px-1 py-0.5 rounded font-medium ${g.color}`}>{g.grade}</span>
            {r.isHeld && <span className="text-[9px] px-1 py-0.5 rounded bg-blue-500/15 text-blue-400 font-medium">보유 중</span>}
          </div>
          <div className="text-right text-[10px] shrink-0 t-text-dim">
            {foreignStr && <div className="text-blue-400">외인 -{foreignStr}</div>}
          </div>
        </div>
        <div className="flex gap-1 mt-1 ml-6 flex-wrap">
          {r.warnings?.map((w: string, j: number) => (
            <span key={j} className={`text-[10px] ${g.color}`}>{w}</span>
          ))}
        </div>
      </div>
    );
  };

  return (
  <section className="t-card rounded-xl p-4">
    <SectionHeader id="risk" timestamp={ts} count={risks.length}>위험 종목 모니터</SectionHeader>
    <div className="space-y-1.5">
      {held.length > 0 && (
        <div className="mb-2">
          <div className="text-[10px] text-red-400 font-semibold mb-1">내 보유 종목 주의</div>
          {held.map((r: any, i: number) => renderItem(r, i))}
        </div>
      )}
      {show.map((r: any, i: number) => renderItem(r, i))}
      {rest.length > 0 && (
        <details className="mt-1">
          <summary className="text-[10px] t-text-dim cursor-pointer hover:underline py-1">더 보기 ({rest.length})</summary>
          <div className="space-y-1.5 mt-1.5">
            {rest.map((r: any, i: number) => renderItem(r, i, true))}
          </div>
        </details>
      )}
    </div>
  </section>
  );
}
