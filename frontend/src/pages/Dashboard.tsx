import { useEffect, useState } from "react";
import { ScatterChart, Scatter, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { dataService } from "../services/dataService";

const STAGE_FILL: Record<string, string> = {
  "탄생": "#4ade80",
  "성장": "#facc15",
  "과열": "#f87171",
  "쇠퇴": "#9ca3af",
};

const STAGE_COLORS: Record<string, string> = {
  "탄생": "text-green-400",
  "성장": "text-yellow-400",
  "과열": "text-red-400",
  "쇠퇴": "text-gray-400",
};

const STAGE_BG: Record<string, string> = {
  "탄생": "bg-green-950 border-green-800",
  "성장": "bg-yellow-950 border-yellow-800",
  "과열": "bg-red-950 border-red-800",
  "쇠퇴": "bg-gray-800 border-gray-600",
};

export default function Dashboard() {
  const [performance, setPerformance] = useState<any>(null);
  const [sectors, setSectors] = useState<Record<string, any> | null>(null);
  const [anomalies, setAnomalies] = useState<any[] | null>(null);
  const [smartMoney, setSmartMoney] = useState<any[] | null>(null);
  const [crossSignal, setCrossSignal] = useState<any[] | null>(null);
  const [lifecycle, setLifecycle] = useState<any[] | null>(null);
  const [riskMonitor, setRiskMonitor] = useState<any[] | null>(null);
  const [newsImpact, setNewsImpact] = useState<Record<string, any> | null>(null);
  const [briefing, setBriefing] = useState<any>(null);
  const [simulation, setSimulation] = useState<any[] | null>(null);
  const [pattern, setPattern] = useState<any[] | null>(null);

  useEffect(() => {
    dataService.getPerformance().then(setPerformance);
    dataService.getSectorFlow().then(setSectors);
    dataService.getAnomalies().then(setAnomalies);
    dataService.getSmartMoney().then(setSmartMoney);
    dataService.getCrossSignal().then(setCrossSignal);
    dataService.getLifecycle().then(setLifecycle);
    dataService.getRiskMonitor().then(setRiskMonitor);
    dataService.getNewsImpact().then(setNewsImpact);
    dataService.getBriefing().then(setBriefing);
    dataService.getSimulation().then(setSimulation);
    dataService.getPattern().then(setPattern);
  }, []);

  return (
    <div className="min-h-screen bg-gray-950 text-white p-4 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Stock Toolkit</h1>

      {/* AI 브리핑 */}
      {briefing?.morning && (
        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">AI 모닝 브리프</h2>
          <div
            className="bg-indigo-950 border border-indigo-800 rounded-lg p-4 text-sm leading-relaxed whitespace-pre-line"
            dangerouslySetInnerHTML={{ __html: briefing.morning }}
          />
        </section>
      )}

      {/* 시장 현황 */}
      {performance && (
        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">시장 현황</h2>
          <div className="bg-gray-900 rounded-lg p-4 space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-gray-400">시장 심리</span>
              <span className={`text-xl font-bold ${
                performance.fear_greed?.score < 25 ? "text-red-500" :
                performance.fear_greed?.score < 45 ? "text-orange-400" :
                performance.fear_greed?.score < 55 ? "text-gray-300" :
                "text-green-400"
              }`}>
                {performance.current_regime}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Fear & Greed</span>
              <span className="text-orange-400">{performance.fear_greed?.score ?? "—"}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">VIX</span>
              <span className="text-orange-400">{performance.vix?.current ?? "—"}</span>
            </div>
            {performance.kospi && (
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">KOSPI</span>
                <span>{performance.kospi.current?.toLocaleString()} <span className="text-gray-600">({performance.kospi.status})</span></span>
              </div>
            )}
            {performance.kosdaq && (
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">KOSDAQ</span>
                <span>{performance.kosdaq.current?.toLocaleString()} <span className="text-gray-600">({performance.kosdaq.status})</span></span>
              </div>
            )}
          </div>
        </section>
      )}

      {/* 신호 분포 */}
      {performance?.by_source?.combined && (
        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">신호 분포 ({performance.by_source.combined.total}종목)</h2>
          <div className="grid grid-cols-5 gap-1">
            {[
              { label: "적극매수", key: "적극매수", color: "bg-red-600" },
              { label: "매수", key: "매수", color: "bg-red-900" },
              { label: "중립", key: "중립", color: "bg-gray-700" },
              { label: "매도", key: "매도", color: "bg-blue-900" },
              { label: "적극매도", key: "적극매도", color: "bg-blue-600" },
            ].map(({ label, key, color }) => (
              <div key={key} className={`${color} rounded-lg p-2 text-center`}>
                <div className="text-lg font-bold">{performance.by_source.combined[key] ?? 0}</div>
                <div className="text-xs text-gray-300">{label}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 교차 신호 고확신 종목 */}
      {crossSignal && crossSignal.length > 0 && (
        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">교차 신호 (테마+시그널)</h2>
          {crossSignal.map((s, i) => (
            <div key={i} className="bg-emerald-950 border border-emerald-800 rounded-lg p-3 mb-2">
              <div className="flex justify-between items-center">
                <div>
                  <span className="font-medium">{s.name}</span>
                  <span className="text-gray-500 text-sm ml-1">({s.code})</span>
                </div>
                <span className="text-emerald-400 font-bold">{s.signal}</span>
              </div>
              <div className="text-sm text-gray-400 mt-1">
                테마: {s.theme} · 신뢰도 {((s.confidence || 0) * 100).toFixed(0)}%
              </div>
            </div>
          ))}
        </section>
      )}

      {/* 테마 라이프사이클 */}
      {lifecycle && lifecycle.length > 0 && (
        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">테마 라이프사이클</h2>
          {/* 버블차트 */}
          <div className="bg-gray-900 rounded-lg p-3 mb-3">
            <ResponsiveContainer width="100%" height={200}>
              <ScatterChart margin={{ top: 10, right: 10, bottom: 10, left: 0 }}>
                <XAxis
                  dataKey="stock_count"
                  name="종목수"
                  type="number"
                  tick={{ fill: '#9ca3af', fontSize: 12 }}
                  axisLine={{ stroke: '#374151' }}
                  label={{ value: '종목수', position: 'bottom', fill: '#6b7280', fontSize: 11, offset: -5 }}
                />
                <YAxis
                  dataKey="avg_change"
                  name="평균등락률"
                  type="number"
                  tick={{ fill: '#9ca3af', fontSize: 12 }}
                  axisLine={{ stroke: '#374151' }}
                  label={{ value: '%', position: 'top', fill: '#6b7280', fontSize: 11, offset: -5 }}
                />
                <Tooltip
                  content={({ payload }) => {
                    if (!payload?.length) return null;
                    const d = payload[0].payload;
                    return (
                      <div className="bg-gray-800 border border-gray-700 rounded p-2 text-xs">
                        <div className="font-bold">{d.theme}</div>
                        <div>단계: {d.stage}</div>
                        <div>종목수: {d.stock_count}</div>
                        <div>평균: {d.avg_change >= 0 ? "+" : ""}{d.avg_change}%</div>
                      </div>
                    );
                  }}
                />
                <Scatter data={lifecycle}>
                  {lifecycle.map((l: any, i: number) => (
                    <Cell key={i} fill={STAGE_FILL[l.stage] || "#6b7280"} r={Math.max(8, l.stock_count * 4)} />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
            <div className="flex justify-center gap-4 text-xs text-gray-500 mt-1">
              {Object.entries(STAGE_FILL).map(([stage, color]) => (
                <span key={stage} className="flex items-center gap-1">
                  <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                  {stage}
                </span>
              ))}
            </div>
          </div>
          {lifecycle.map((l: any, i: number) => (
            <div key={i} className={`border rounded-lg p-3 mb-2 ${STAGE_BG[l.stage] || "bg-gray-900 border-gray-700"}`}>
              <div className="flex justify-between items-center">
                <span className="font-medium">{l.theme}</span>
                <span className={`font-bold ${STAGE_COLORS[l.stage] || "text-gray-300"}`}>{l.stage}</span>
              </div>
              <div className="text-sm text-gray-400 mt-1">
                {l.stock_count}종목 · 평균 {l.avg_change >= 0 ? "+" : ""}{l.avg_change}%
              </div>
            </div>
          ))}
        </section>
      )}

      {/* 이상 거래 */}
      {anomalies && anomalies.length > 0 && (
        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">이상 거래 감지</h2>
          {anomalies.slice(0, 8).map((a, i) => (
            <div key={i} className="bg-red-950 border border-red-800 rounded-lg p-3 mb-2 flex justify-between items-center">
              <div>
                <span className="text-red-400 font-medium text-sm">{a.type}</span>
                {a.name && <span className="ml-2">{a.name}</span>}
              </div>
              <div className="text-right text-sm">
                {a.ratio && <span className="text-yellow-400">x{a.ratio}</span>}
                {a.change_rate != null && (
                  <span className={`ml-2 ${a.change_rate >= 0 ? "text-red-400" : "text-blue-400"}`}>
                    {a.change_rate >= 0 ? "+" : ""}{a.change_rate}%
                  </span>
                )}
              </div>
            </div>
          ))}
        </section>
      )}

      {/* 위험 종목 */}
      {riskMonitor && riskMonitor.length > 0 && (
        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">위험 종목 모니터</h2>
          {riskMonitor.slice(0, 8).map((r, i) => (
            <div key={i} className="bg-gray-900 rounded-lg p-3 mb-2">
              <div className="flex justify-between items-center">
                <div>
                  <span className="font-medium">{r.name}</span>
                  <span className="text-gray-500 text-sm ml-1">({r.code})</span>
                </div>
                <span className={`font-bold text-sm ${r.level === "높음" ? "text-red-500" : "text-orange-400"}`}>
                  {r.level}
                </span>
              </div>
              <div className="flex flex-wrap gap-1 mt-1">
                {r.warnings?.map((w: string, j: number) => (
                  <span key={j} className="text-xs bg-red-900/50 text-red-300 px-2 py-0.5 rounded">
                    {w}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </section>
      )}

      {/* 스마트 머니 */}
      {smartMoney && smartMoney.length > 0 && (
        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">스마트 머니 TOP</h2>
          {smartMoney.slice(0, 10).map((s, i) => (
            <div key={i} className="bg-gray-900 rounded-lg p-3 mb-2 flex justify-between items-center">
              <div>
                <span className="font-medium">{s.name}</span>
                <span className="text-gray-500 text-sm ml-1">({s.code})</span>
                <span className="text-green-400 text-sm ml-2">{s.signal}</span>
              </div>
              <span className="text-yellow-400 font-bold">{s.smart_money_score}</span>
            </div>
          ))}
        </section>
      )}

      {/* 시나리오 시뮬레이션 */}
      {simulation && simulation.length > 0 && (
        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">전략 시뮬레이션</h2>
          <div className="grid grid-cols-1 gap-2">
            {simulation.map((s, i) => (
              <div key={i} className="bg-cyan-950 border border-cyan-800 rounded-lg p-3">
                <div className="text-cyan-400 font-medium text-sm mb-2">{s.strategy}</div>
                <div className="grid grid-cols-3 gap-2 text-center text-sm">
                  <div>
                    <div className="text-gray-400">매매 수</div>
                    <div className="font-bold">{s.total_trades}건</div>
                  </div>
                  <div>
                    <div className="text-gray-400">승률</div>
                    <div className={`font-bold ${s.win_rate >= 50 ? "text-red-400" : "text-blue-400"}`}>
                      {s.win_rate}%
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400">평균 수익</div>
                    <div className={`font-bold ${(s.returns?.mean || 0) >= 0 ? "text-red-400" : "text-blue-400"}`}>
                      {s.returns?.mean >= 0 ? "+" : ""}{s.returns?.mean?.toFixed(1) ?? "—"}%
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 패턴 매칭 */}
      {pattern && pattern.length > 0 && (
        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">차트 패턴 매칭</h2>
          {pattern.map((p, i) => (
            <div key={i} className="bg-gray-900 rounded-lg p-3 mb-2">
              <div className="font-medium mb-2">{p.name} ({p.code})</div>
              {p.matches?.slice(0, 3).map((m: any, j: number) => (
                <div key={j} className="flex justify-between text-sm text-gray-400 mb-1">
                  <span>{m.date} (유사도 {(m.similarity * 100).toFixed(0)}%)</span>
                  <span className={m.future_return_d5 >= 0 ? "text-red-400" : "text-blue-400"}>
                    D+5: {m.future_return_d5 >= 0 ? "+" : ""}{m.future_return_d5?.toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          ))}
        </section>
      )}

      {/* 뉴스 임팩트 */}
      {newsImpact && Object.keys(newsImpact).length > 0 && (
        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">뉴스 임팩트</h2>
          {Object.entries(newsImpact).map(([category, data]: [string, any]) => (
            <div key={category} className="bg-gray-900 rounded-lg p-3 mb-2">
              <div className="flex justify-between items-center mb-2">
                <span className="font-medium text-purple-400">{category}</span>
                <span className="text-gray-500 text-sm">{data.count}건</span>
              </div>
              {data.titles?.slice(0, 3).map((t: any, i: number) => (
                <div key={i} className="text-sm text-gray-400 mb-1 flex justify-between">
                  <span className="truncate mr-2">{t.title}</span>
                  <span className={`shrink-0 ${
                    t.signal?.includes("매수") ? "text-red-400" :
                    t.signal?.includes("매도") ? "text-blue-400" : "text-gray-500"
                  }`}>{t.stock}</span>
                </div>
              ))}
            </div>
          ))}
        </section>
      )}

      {/* 테마별 자금 흐름 */}
      {sectors && Object.keys(sectors).length > 0 && (
        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">테마별 자금 흐름</h2>
          {Object.entries(sectors)
            .sort(([, a]: any, [, b]: any) => (b.total_foreign_net || 0) - (a.total_foreign_net || 0))
            .map(([name, data]: [string, any]) => (
              <div key={name} className="flex justify-between bg-gray-900 rounded-lg p-3 mb-1">
                <span>{name} <span className="text-gray-500 text-sm">[{data.stock_count}종목]</span></span>
                <span className={data.total_foreign_net >= 0 ? "text-red-400" : "text-blue-400"}>
                  외국인 {data.total_foreign_net >= 0 ? "+" : ""}{(data.total_foreign_net / 1000).toFixed(0)}천주
                </span>
              </div>
            ))}
        </section>
      )}
    </div>
  );
}
