import { useEffect, useState } from "react";
import {
  ScatterChart, Scatter, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell,
} from "recharts";
import {
  TrendingUp, TrendingDown, Shield,
  Activity, BarChart3, Zap, LineChart,
} from "lucide-react";
import { dataService } from "../services/dataService";
import { SectionHeader } from "../components/HelpDialog";
import RefreshButtons from "../components/RefreshButtons";

const STAGE_FILL: Record<string, string> = {
  "탄생": "#22c55e", "성장": "#eab308", "과열": "#ef4444", "쇠퇴": "#9ca3af",
};
const STAGE_DOT: Record<string, string> = {
  "탄생": "bg-green-500", "성장": "bg-yellow-500", "과열": "bg-red-500", "쇠퇴": "bg-gray-400",
};

function Gauge({ value, max, label, color }: { value: number; max: number; label: string; color: string }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-500">{label}</span>
        <span className="font-medium">{value}</span>
      </div>
      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function Badge({ children, variant = "default" }: { children: React.ReactNode; variant?: string }) {
  const cls: Record<string, string> = {
    danger: "bg-red-50 text-red-700 border-red-200",
    warning: "bg-amber-50 text-amber-700 border-amber-200",
    success: "bg-green-50 text-green-700 border-green-200",
    blue: "bg-blue-50 text-blue-700 border-blue-200",
    purple: "bg-purple-50 text-purple-700 border-purple-200",
    default: "bg-gray-50 text-gray-600 border-gray-200",
  };
  return (
    <span className={`inline-flex items-center text-xs font-medium px-2 py-0.5 rounded-full border whitespace-nowrap ${cls[variant] || cls.default}`}>
      {children}
    </span>
  );
}

function signalBadge(signal: string) {
  if (signal?.includes("적극매수")) return <Badge variant="danger">적극매수</Badge>;
  if (signal?.includes("매수")) return <Badge variant="danger">매수</Badge>;
  if (signal?.includes("적극매도")) return <Badge variant="blue">적극매도</Badge>;
  if (signal?.includes("매도")) return <Badge variant="blue">매도</Badge>;
  return <Badge>중립</Badge>;
}

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
  const [sentiment, setSentiment] = useState<any>(null);
  const [shortSqueeze, setShortSqueeze] = useState<any[] | null>(null);
  const [gapAnalysis, setGapAnalysis] = useState<any[] | null>(null);
  const [valuation, setValuation] = useState<any[] | null>(null);
  const [divergence, setDivergence] = useState<any[] | null>(null);
  const [premarket, setPremarket] = useState<any>(null);
  const [portfolio, setPortfolio] = useState<any>(null);

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
    dataService.getSentiment().then(setSentiment);
    dataService.getShortSqueeze().then(setShortSqueeze);
    dataService.getGapAnalysis().then(setGapAnalysis);
    dataService.getValuation().then(setValuation);
    dataService.getVolumeDivergence().then(setDivergence);
    dataService.getPremarket().then(setPremarket);
    dataService.getPortfolio().then(setPortfolio);
  }, []);

  const fgScore = performance?.fear_greed?.score ?? 0;
  const fgLabel = fgScore < 25 ? "극단적 공포" : fgScore < 45 ? "공포" : fgScore < 55 ? "중립" : fgScore < 75 ? "탐욕" : "극단적 탐욕";
  const fgColor = fgScore < 25 ? "bg-red-500" : fgScore < 45 ? "bg-orange-400" : fgScore < 55 ? "bg-gray-400" : fgScore < 75 ? "bg-green-400" : "bg-green-600";
  const vixVal = performance?.vix?.current ?? 0;
  const vixLabel = vixVal < 15 ? "안정" : vixVal < 20 ? "보통" : vixVal < 30 ? "불안" : "공포";
  const vixColor = vixVal < 15 ? "bg-green-500" : vixVal < 20 ? "bg-yellow-500" : vixVal < 30 ? "bg-orange-500" : "bg-red-500";

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
          <BarChart3 size={22} className="text-blue-600" />
          Stock Toolkit
        </h1>
        <RefreshButtons />
      </div>

      {/* 장전 프리마켓 */}
      {premarket && (
        <section className="bg-amber-50 border border-amber-100 rounded-xl p-4">
          <SectionHeader id="premarket">장전 프리마켓</SectionHeader>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">시장 출발 예상</span>
            <span className={`text-sm font-bold ${premarket.prediction?.includes("상승") ? "text-red-600" : premarket.prediction?.includes("하락") ? "text-blue-600" : "text-gray-600"}`}>
              {premarket.prediction}
            </span>
          </div>
          <div className="space-y-1">
            {premarket.key_factors?.map((f: string, i: number) => (
              <div key={i} className="text-xs text-gray-500">· {f}</div>
            ))}
          </div>
        </section>
      )}

      {/* 시장 심리 온도계 */}
      {sentiment && (
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="sentiment">시장 심리 온도계</SectionHeader>
          <div className="flex items-center gap-4 mb-3">
            <div className="text-3xl font-bold text-gray-900">{sentiment.score}</div>
            <div>
              <div className={`text-sm font-semibold ${sentiment.score < 30 ? "text-blue-600" : sentiment.score < 60 ? "text-gray-600" : "text-red-600"}`}>
                {sentiment.label}
              </div>
              <div className="text-xs text-gray-500">{sentiment.strategy}</div>
            </div>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden mb-3">
            <div
              className={`h-full rounded-full ${sentiment.score < 30 ? "bg-blue-500" : sentiment.score < 60 ? "bg-gray-400" : "bg-red-500"}`}
              style={{ width: `${sentiment.score}%` }}
            />
          </div>
          <div className="flex justify-between text-[10px] text-gray-400 mb-3">
            <span>극단적 공포 0</span><span>중립 50</span><span>극단적 탐욕 100</span>
          </div>
          {sentiment.components && (
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(sentiment.components).map(([key, comp]: [string, any]) => (
                <div key={key} className="text-xs bg-gray-50 rounded p-2">
                  <div className="text-gray-500">{key === "fear_greed" ? "F&G" : key === "vix" ? "VIX" : key === "kospi_deviation" ? "KOSPI 이격도" : "외국인 수급"}</div>
                  <div className="font-medium">{typeof comp.value === 'number' ? (Number.isInteger(comp.value) ? comp.value.toLocaleString() : comp.value) : comp.value}</div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* AI 브리핑 */}
      {briefing?.morning && (
        <section className="bg-blue-50 border border-blue-100 rounded-xl p-4">
          <SectionHeader id="briefing">AI 모닝 브리프</SectionHeader>
          <div
            className="text-sm text-gray-700 leading-relaxed whitespace-pre-line [&_b]:text-gray-900 [&_b]:font-semibold"
            dangerouslySetInnerHTML={{ __html: briefing.morning }}
          />
        </section>
      )}

      {/* 시장 현황 */}
      {performance && (
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="market">시장 현황</SectionHeader>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Gauge value={fgScore} max={100} label="공포·탐욕 지수" color={fgColor} />
              <p className="text-xs text-gray-500">{fgLabel} 구간</p>
            </div>
            <div className="space-y-2">
              <Gauge value={vixVal} max={50} label="VIX 변동성" color={vixColor} />
              <p className="text-xs text-gray-500">{vixLabel}</p>
            </div>
            {performance.kospi && (
              <div className="flex items-center gap-2 min-w-0">
                <TrendingUp size={14} className="text-gray-400 shrink-0" />
                <div className="min-w-0">
                  <div className="text-sm font-medium">{performance.kospi.current?.toLocaleString()}</div>
                  <div className="text-xs text-gray-500">KOSPI</div>
                </div>
              </div>
            )}
            {performance.kosdaq && (
              <div className="flex items-center gap-2 min-w-0">
                <TrendingUp size={14} className="text-gray-400 shrink-0" />
                <div className="min-w-0">
                  <div className="text-sm font-medium">{performance.kosdaq.current?.toLocaleString()}</div>
                  <div className="text-xs text-gray-500">KOSDAQ</div>
                </div>
              </div>
            )}
          </div>
        </section>
      )}

      {/* 내 포트폴리오 */}
      {portfolio && (
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="portfolio" count={portfolio.holdings?.length}>내 포트폴리오</SectionHeader>
          <div className="flex items-center gap-3 mb-3">
            <div className="text-2xl font-bold text-gray-900">{portfolio.health_score}</div>
            <div>
              <div className={`text-sm font-semibold ${portfolio.health_score >= 70 ? "text-green-600" : portfolio.health_score >= 50 ? "text-amber-600" : "text-red-600"}`}>
                {portfolio.health_score >= 70 ? "양호" : portfolio.health_score >= 50 ? "보통" : "개선 필요"}
              </div>
              <div className="text-xs text-gray-500">건강도</div>
            </div>
          </div>
          <div className="space-y-1.5 mb-3">
            {portfolio.holdings?.map((h: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
                <div className="min-w-0">
                  <span className="text-sm font-medium">{h.name}</span>
                  <span className="text-xs text-gray-400 ml-1">{h.code}</span>
                  <div className="text-xs text-gray-500">{h.sector} · 비중 {h.weight}%</div>
                </div>
                <div className="shrink-0">{signalBadge(h.signal)}</div>
              </div>
            ))}
          </div>
          {portfolio.suggestions?.length > 0 && (
            <div className="bg-amber-50 border border-amber-100 rounded-lg p-2.5">
              <div className="text-xs font-medium text-amber-700 mb-1">리밸런싱 제안</div>
              {portfolio.suggestions.map((s: string, i: number) => (
                <div key={i} className="text-xs text-amber-600">· {s}</div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* 신호 분포 */}
      {performance?.by_source?.combined && (() => {
        const c = performance.by_source.combined;
        const total = c.total || 1;
        const bars = [
          { key: "적극매수", count: c["적극매수"] || 0, color: "bg-red-500" },
          { key: "매수", count: c["매수"] || 0, color: "bg-red-300" },
          { key: "중립", count: c["중립"] || 0, color: "bg-gray-300" },
          { key: "매도", count: c["매도"] || 0, color: "bg-blue-300" },
          { key: "적극매도", count: c["적극매도"] || 0, color: "bg-blue-500" },
        ];
        return (
          <section className="bg-white border border-gray-200 rounded-xl p-4">
            <SectionHeader id="signals" count={c.total}>신호 분포</SectionHeader>
            <div className="flex h-3 rounded-full overflow-hidden mb-3">
              {bars.map((b) => (
                <div key={b.key} className={b.color} style={{ width: `${(b.count / total) * 100}%` }} />
              ))}
            </div>
            <div className="flex justify-between text-xs">
              {bars.map((b) => (
                <div key={b.key} className="text-center flex-1">
                  <div className="font-semibold text-gray-900">{b.count}</div>
                  <div className="text-gray-500 text-[10px]">{b.key}</div>
                </div>
              ))}
            </div>
          </section>
        );
      })()}

      {/* 교차 신호 */}
      {crossSignal && crossSignal.length > 0 && (
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="cross" count={crossSignal.length}>교차 신호</SectionHeader>
          <div className="space-y-2">
            {crossSignal.map((s, i) => (
              <div key={i} className="p-2.5 bg-green-50 border border-green-100 rounded-lg">
                <div className="flex items-center justify-between">
                  <div className="min-w-0 mr-2">
                    <span className="font-medium text-sm">{s.name}</span>
                    <span className="text-xs text-gray-400 ml-1">{s.code}</span>
                  </div>
                  <div className="shrink-0">{signalBadge(s.signal)}</div>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {s.theme} · 신뢰도 {((s.confidence || 0) * 100).toFixed(0)}%
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 테마 라이프사이클 */}
      {lifecycle && lifecycle.length > 0 && (
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="lifecycle" count={lifecycle.length}>테마 라이프사이클</SectionHeader>
          <div className="bg-gray-50 rounded-lg p-2 mb-3">
            <ResponsiveContainer width="100%" height={160}>
              <ScatterChart margin={{ top: 5, right: 5, bottom: 20, left: 0 }}>
                <XAxis dataKey="stock_count" type="number" tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={{ stroke: '#e5e7eb' }} label={{ value: '종목수', position: 'bottom', fill: '#9ca3af', fontSize: 10, offset: -5 }} />
                <YAxis dataKey="avg_change" type="number" tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={{ stroke: '#e5e7eb' }} label={{ value: '%', position: 'top', fill: '#9ca3af', fontSize: 10, offset: -5 }} />
                <Tooltip content={({ payload }) => {
                  if (!payload?.length) return null;
                  const d = payload[0].payload;
                  return (<div className="bg-white border border-gray-200 rounded-lg shadow p-2 text-xs"><div className="font-semibold">{d.theme}</div><div className="text-gray-500">{d.stage} · {d.stock_count}종목 · {d.avg_change >= 0 ? "+" : ""}{d.avg_change}%</div></div>);
                }} />
                <Scatter data={lifecycle}>{lifecycle.map((l: any, i: number) => (<Cell key={i} fill={STAGE_FILL[l.stage] || "#6b7280"} r={Math.max(6, l.stock_count * 3)} />))}</Scatter>
              </ScatterChart>
            </ResponsiveContainer>
            <div className="flex justify-center gap-3 text-xs text-gray-400">
              {Object.entries(STAGE_DOT).map(([s, c]) => (
                <span key={s} className="flex items-center gap-1"><span className={`w-2 h-2 rounded-full ${c}`} />{s}</span>
              ))}
            </div>
          </div>
          <div className="space-y-1.5">
            {lifecycle.map((l: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
                <span className="text-sm font-medium truncate min-w-0">{l.theme}</span>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs text-gray-500">{l.avg_change >= 0 ? "+" : ""}{l.avg_change}%</span>
                  <Badge variant={l.stage === "과열" ? "danger" : l.stage === "성장" ? "warning" : l.stage === "탄생" ? "success" : "default"}>{l.stage}</Badge>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 이상 거래 감지 */}
      {anomalies && anomalies.length > 0 && (
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="anomaly" count={anomalies.length}>이상 거래 감지</SectionHeader>
          <div className="space-y-1.5">
            {anomalies.slice(0, 6).map((a, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-red-50 border border-red-100 rounded-lg gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <Zap size={14} className="text-red-400 shrink-0" />
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{a.name}</div>
                    <div className="text-xs text-gray-500">{a.type}</div>
                  </div>
                </div>
                <div className="text-right text-xs shrink-0">
                  {a.ratio && <div className="text-amber-600 font-medium">x{a.ratio}</div>}
                  {a.change_rate != null && (
                    <div className={a.change_rate >= 0 ? "text-red-600" : "text-blue-600"}>
                      {a.change_rate >= 0 ? "+" : ""}{a.change_rate}%
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 위험 종목 모니터 */}
      {riskMonitor && riskMonitor.length > 0 && (
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="risk" count={riskMonitor.length}>위험 종목 모니터</SectionHeader>
          <div className="space-y-1.5">
            {riskMonitor.slice(0, 6).map((r, i) => (
              <div key={i} className="p-2 bg-gray-50 rounded-lg">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Shield size={14} className={`shrink-0 ${r.level === "높음" ? "text-red-500" : "text-amber-500"}`} />
                    <span className="text-sm font-medium truncate">{r.name}</span>
                    <span className="text-xs text-gray-400 shrink-0">{r.code}</span>
                  </div>
                </div>
                <div className="flex gap-1 mt-1.5 ml-6">
                  {r.warnings?.map((w: string, j: number) => (
                    <Badge key={j} variant={r.level === "높음" ? "danger" : "warning"}>{w}</Badge>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 스마트 머니 TOP */}
      {smartMoney && smartMoney.length > 0 && (
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="smartmoney" count={smartMoney.length}>스마트 머니 TOP</SectionHeader>
          <div className="space-y-1.5">
            {smartMoney.slice(0, 8).map((s, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 text-[10px] font-bold flex items-center justify-center shrink-0">
                    {i + 1}
                  </div>
                  <span className="text-sm font-medium truncate">{s.name}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {signalBadge(s.signal)}
                  <span className="text-sm font-bold text-blue-700 w-7 text-right">{s.smart_money_score}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 전략 시뮬레이션 */}
      {simulation && simulation.length > 0 && (
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="simulation">전략 시뮬레이션</SectionHeader>
          <div className="space-y-2">
            {simulation.map((s, i) => (
              <div key={i} className="p-3 bg-gray-50 rounded-lg">
                <div className="text-xs text-blue-600 font-medium mb-2 flex items-center gap-1">
                  <Activity size={12} className="shrink-0" />
                  <span className="truncate">{s.strategy}</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div>
                    <div className="text-[10px] text-gray-500">총 거래</div>
                    <div className="text-sm font-semibold">{s.total_trades}건</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-gray-500">승률</div>
                    <div className={`text-sm font-semibold ${s.win_rate >= 50 ? "text-red-600" : "text-blue-600"}`}>{s.win_rate}%</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-gray-500">평균수익</div>
                    <div className={`text-sm font-semibold ${(s.returns?.mean || 0) >= 0 ? "text-red-600" : "text-blue-600"}`}>
                      {s.returns?.mean >= 0 ? "+" : ""}{s.returns?.mean?.toFixed(1)}%
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 차트 패턴 매칭 */}
      {pattern && pattern.length > 0 && (
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="pattern">차트 패턴 매칭</SectionHeader>
          <div className="space-y-3">
            {pattern.map((p, i) => (
              <div key={i}>
                <div className="font-medium text-sm flex items-center gap-1 mb-1.5">
                  <LineChart size={14} className="text-gray-400 shrink-0" />
                  <span className="truncate">{p.name}</span>
                  <span className="text-xs text-gray-400 shrink-0">{p.code}</span>
                </div>
                {p.matches?.slice(0, 3).map((m: any, j: number) => (
                  <div key={j} className="flex justify-between text-xs py-1 border-b border-gray-100 last:border-0 gap-2">
                    <span className="text-gray-500 truncate">{m.date} · 유사도 {(m.similarity * 100).toFixed(0)}%</span>
                    <span className={`shrink-0 ${m.future_return_d5 >= 0 ? "text-red-600 font-medium" : "text-blue-600 font-medium"}`}>
                      D+5 {m.future_return_d5 >= 0 ? "+" : ""}{m.future_return_d5?.toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            ))}
            <p className="text-[10px] text-gray-400">D+5 = 패턴 발생 후 5거래일 뒤 수익률</p>
          </div>
        </section>
      )}

      {/* 뉴스 임팩트 */}
      {newsImpact && Object.keys(newsImpact).length > 0 && (
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="news">뉴스 임팩트</SectionHeader>
          <div className="space-y-3">
            {Object.entries(newsImpact).map(([cat, data]: [string, any]) => (
              <div key={cat} className="p-3 bg-gray-50 rounded-lg">
                <div className="flex justify-between items-center mb-2">
                  <Badge variant="purple">{cat}</Badge>
                  <span className="text-xs text-gray-400">{data.count}건</span>
                </div>
                {data.titles?.slice(0, 2).map((t: any, i: number) => (
                  <div key={i} className="text-xs text-gray-600 mb-1 flex justify-between gap-2">
                    <span className="truncate min-w-0">{t.title}</span>
                    <span className="shrink-0 text-gray-400">{t.stock}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 갭 분석 */}
      {gapAnalysis && gapAnalysis.length > 0 && (
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="gap" count={gapAnalysis.length}>갭 분석</SectionHeader>
          <div className="space-y-1.5">
            {gapAnalysis.slice(0, 6).map((g, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{g.name}</div>
                  <div className="text-xs text-gray-500">{g.direction}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className={`text-sm font-bold ${g.gap_pct >= 0 ? "text-red-600" : "text-blue-600"}`}>
                    {g.gap_pct >= 0 ? "+" : ""}{g.gap_pct}%
                  </div>
                  <div className="text-[10px] text-gray-400">메꿈 확률 {g.fill_probability}%</div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 공매도 역발상 */}
      {shortSqueeze && shortSqueeze.length > 0 && (
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="squeeze" count={shortSqueeze.length}>역발상 시그널</SectionHeader>
          <div className="space-y-1.5">
            {shortSqueeze.slice(0, 6).map((s, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-orange-50 border border-orange-100 rounded-lg gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{s.name}</div>
                  <div className="text-xs text-gray-500 truncate">{s.overheating}</div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {signalBadge(s.signal)}
                  <span className="text-sm font-bold text-orange-600 w-7 text-right">{s.squeeze_score}</span>
                </div>
              </div>
            ))}
            <p className="text-[10px] text-gray-400">과열 경고 + 외국인 매수 전환 = 역발상 매수 기회</p>
          </div>
        </section>
      )}

      {/* 밸류에이션 */}
      {valuation && valuation.length > 0 && (
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="valuation" count={valuation.length}>밸류에이션 스크리너</SectionHeader>
          <div className="space-y-1.5">
            {valuation.slice(0, 6).map((v, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{v.name}</div>
                  <div className="text-xs text-gray-500">
                    {v.ma_aligned ? "MA정배열" : "MA비정배열"}
                    {v.foreign_net > 0 ? " · 외국인 매수" : ""}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {signalBadge(v.signal)}
                  <span className="text-sm font-bold text-green-700 w-7 text-right">{v.value_score}</span>
                </div>
              </div>
            ))}
            <p className="text-[10px] text-gray-400">시가총액 적정 + MA정배열 + 매수신호 + 외국인 매수 종합</p>
          </div>
        </section>
      )}

      {/* 거래량-가격 괴리 */}
      {divergence && divergence.length > 0 && (
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="divergence" count={divergence.length}>거래량-가격 괴리</SectionHeader>
          <div className="space-y-1.5">
            {divergence.slice(0, 6).map((d, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{d.name}</div>
                  <div className="text-xs text-gray-500">{d.type}</div>
                </div>
                <div className="text-right shrink-0 text-xs">
                  <div className="text-amber-600">거래량 x{(d.volume_change / 100).toFixed(1)}</div>
                  <div className={d.price_change >= 0 ? "text-red-600" : "text-blue-600"}>
                    가격 {d.price_change >= 0 ? "+" : ""}{d.price_change}%
                  </div>
                </div>
              </div>
            ))}
            <p className="text-[10px] text-gray-400">거래량과 가격의 방향이 다르면 추세 전환 가능성</p>
          </div>
        </section>
      )}

      {/* 테마별 자금 흐름 */}
      {sectors && Object.keys(sectors).length > 0 && (
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="sector">테마별 자금 흐름</SectionHeader>
          <div className="space-y-1.5">
            {Object.entries(sectors)
              .sort(([, a]: any, [, b]: any) => (b.total_foreign_net || 0) - (a.total_foreign_net || 0))
              .map(([name, data]: [string, any]) => {
                const net = data.total_foreign_net || 0;
                const isPos = net >= 0;
                return (
                  <div key={name} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
                    <div className="min-w-0">
                      <span className="text-sm font-medium truncate block">{name}</span>
                      <span className="text-xs text-gray-400">{data.stock_count}종목</span>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      {isPos ? <TrendingUp size={14} className="text-red-500" /> : <TrendingDown size={14} className="text-blue-500" />}
                      <span className={`text-sm font-medium ${isPos ? "text-red-600" : "text-blue-600"}`}>
                        {isPos ? "+" : ""}{(net / 1000).toFixed(0)}천주
                      </span>
                    </div>
                  </div>
                );
              })}
          </div>
        </section>
      )}
    </div>
  );
}
