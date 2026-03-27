import { Activity } from "lucide-react";
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

export default function SimulationSection({ simulation, ts }: {
  simulation: any[] | null;
  ts: string;
}) {
  return (
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
                    <div className="text-sm font-semibold tabular-nums">{s.total_trades}건</div>
                  </div>
                  <div>
                    <div className="text-[10px] t-text-dim">승률</div>
                    <div className={`text-sm font-semibold tabular-nums ${s.win_rate >= 50 ? "text-red-600" : "text-blue-600"}`}>{s.win_rate}%</div>
                  </div>
                  <div>
                    <div className="text-[10px] t-text-dim">평균수익</div>
                    <div className={`text-sm font-semibold tabular-nums ${(s.returns?.mean || 0) >= 0 ? "text-red-600" : "text-blue-600"}`}>
                      {s.returns?.mean >= 0 ? "+" : ""}{s.returns?.mean?.toFixed(1)}%
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-xs t-text-dim text-center py-2">
                  <div>데이터 부족 — 시그널 히스토리 축적 필요</div>
                  <div className="text-[10px] mt-0.5">일봉 데이터와 시그널 이력이 5일 이상 누적되면 결과 표시</div>
                </div>
              )}
            </div>
          );
        })}
      </div>
        {(simulation?.length ?? 0) > 0 && (() => {
          const main = (simulation || []).find((s: any) => !s.strategy?.includes("적극") && !s.strategy?.includes("stop"));
          const wr = main?.win_rate ?? 0;
          const avg = main?.returns?.mean ?? 0;
          return (
            <div className="mt-3 p-2.5 rounded-lg bg-amber-500/8 border border-amber-500/15 text-[10px] t-text-sub leading-relaxed">
              <span className="font-semibold text-amber-500">해석 안내</span>
              {wr <= 55 && <span> · 승률 {wr}%는 동전 던지기 수준으로 신호만으로 방향 예측이 어렵습니다.</span>}
              {avg > 0 && <span> · 평균수익이 양수인 이유는 소수의 큰 수익이 다수의 소손실을 상쇄하는 구조입니다.</span>}
              <span> · 과거 백테스트 결과이며 미래 수익을 보장하지 않습니다.</span>
            </div>
          );
        })()}
        {!simulation?.length && <Empty />}
    </section>
  );
}
