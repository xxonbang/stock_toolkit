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

function Empty({ text = "현재 해당 데이터 없음" }: { text?: string }) {
  return <div className="text-center py-4 text-xs text-gray-400">{text}</div>;
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
  const [supplyCluster, setSupplyCluster] = useState<any>(null);
  const [exitOptimizer, setExitOptimizer] = useState<any[] | null>(null);
  const [eventCalendar, setEventCalendar] = useState<any>(null);
  const [propagation, setPropagation] = useState<any[] | null>(null);
  const [programTrading, setProgramTrading] = useState<any>(null);
  const [heatmap, setHeatmap] = useState<any>(null);
  const [insiderTrades, setInsiderTrades] = useState<any[] | null>(null);
  const [consensus, setConsensus] = useState<any[] | null>(null);
  const [auction, setAuction] = useState<any[] | null>(null);
  const [orderbook, setOrderbook] = useState<any[] | null>(null);
  const [correlationData, setCorrelationData] = useState<any>(null);
  const [earningsCalendar, setEarningsCalendar] = useState<any>(null);
  const [aiMentor, setAiMentor] = useState<any>(null);
  const [tradingJournal, setTradingJournal] = useState<any>(null);
  const [memberTrading, setMemberTrading] = useState<any[] | null>(null);
  const [tradingValue, setTradingValue] = useState<any[] | null>(null);
  const [paperTrading, setPaperTrading] = useState<any>(null);
  const [forecastAccuracy, setForecastAccuracy] = useState<any>(null);
  const [volumeProfile, setVolumeProfile] = useState<any[] | null>(null);
  const [signalConsistency, setSignalConsistency] = useState<any[] | null>(null);
  const [simulationHistory, setSimulationHistory] = useState<any[] | null>(null);
  const [intradayStockFlow, setIntradayStockFlow] = useState<any[] | null>(null);
  const [indicatorHistory, setIndicatorHistory] = useState<any>(null);

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
    dataService.getSupplyCluster().then(setSupplyCluster);
    dataService.getExitOptimizer().then(setExitOptimizer);
    dataService.getEventCalendar().then(setEventCalendar);
    dataService.getThemePropagation().then(setPropagation);
    dataService.getProgramTrading().then(setProgramTrading);
    dataService.getIntradayHeatmap().then(setHeatmap);
    dataService.getInsiderTrades().then(setInsiderTrades);
    dataService.getConsensus().then(setConsensus);
    dataService.getAuction().then(setAuction);
    dataService.getOrderbook().then(setOrderbook);
    dataService.getCorrelation().then(setCorrelationData);
    dataService.getEarningsCalendar().then(setEarningsCalendar);
    dataService.getAiMentor().then(setAiMentor);
    dataService.getTradingJournal().then(setTradingJournal);
    dataService.getMemberTrading().then(setMemberTrading);
    dataService.getTradingValue().then(setTradingValue);
    dataService.getPaperTrading().then(setPaperTrading);
    dataService.getForecastAccuracy().then(setForecastAccuracy);
    dataService.getVolumeProfile().then(setVolumeProfile);
    dataService.getSignalConsistency().then(setSignalConsistency);
    dataService.getSimulationHistory().then(setSimulationHistory);
    dataService.getIntradayStockFlow().then(setIntradayStockFlow);
    dataService.getIndicatorHistory().then(setIndicatorHistory);
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
            <div className="text-3xl font-bold text-gray-900">{sentiment.score}<span className="text-sm font-normal text-gray-400">/100</span></div>
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
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(sentiment.components)
                  .filter(([key]) => ["fear_greed", "vix", "kospi_deviation", "foreign_flow"].includes(key))
                  .map(([key, comp]: [string, any]) => (
                  <div key={key} className="text-xs bg-gray-50 rounded p-2">
                    <div className="text-gray-500">{key === "fear_greed" ? "F&G" : key === "vix" ? "VIX" : key === "kospi_deviation" ? "KOSPI 이격도" : "외국인 수급"}</div>
                    <div className="font-medium">{typeof comp.value === 'number' ? (Number.isInteger(comp.value) ? comp.value.toLocaleString() : comp.value) : comp.value}</div>
                  </div>
                ))}
              </div>
              {/* 매크로 지표 */}
              {sentiment.components.macro?.length > 0 && (
                <div className="pt-2 border-t border-gray-100">
                  <div className="text-xs text-gray-400 mb-1">글로벌 지표</div>
                  <div className="grid grid-cols-2 gap-1">
                    {sentiment.components.macro.slice(0, 6).map((ind: any, i: number) => (
                      <div key={i} className="flex justify-between text-[10px] bg-gray-50 rounded px-1.5 py-1">
                        <span className="text-gray-500 truncate">{ind.name || ind.symbol}</span>
                        <span className={`font-medium ${(ind.change_pct || 0) >= 0 ? "text-red-500" : "text-blue-500"}`}>
                          {ind.change_pct != null ? `${ind.change_pct >= 0 ? "+" : ""}${ind.change_pct}%` : "-"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {/* 투자자 동향 */}
              {sentiment.components.investor_trend?.length > 0 && (
                <div className="pt-2 border-t border-gray-100">
                  <div className="text-xs text-gray-400 mb-1">투자자 동향</div>
                  <div className="grid grid-cols-1 gap-1">
                    {sentiment.components.investor_trend.slice(0, 3).map((inv: any, i: number) => (
                      <div key={i} className="flex justify-between text-[10px] bg-gray-50 rounded px-1.5 py-1">
                        <span className="text-gray-500">{inv.investor || inv.name}</span>
                        <span className={`font-medium ${(inv.net_buy || inv.amount || 0) >= 0 ? "text-red-500" : "text-blue-500"}`}>
                          {(inv.net_buy || inv.amount || 0) >= 0 ? "+" : ""}{((inv.net_buy || inv.amount || 0) / 100000000).toFixed(1)}억
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
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
                {(performance.kospi.change || 0) >= 0
                  ? <TrendingUp size={14} className="text-red-400 shrink-0" />
                  : <TrendingDown size={14} className="text-blue-400 shrink-0" />}
                <div className="min-w-0">
                  <div className="text-sm font-medium">{performance.kospi.current?.toLocaleString()}</div>
                  <div className="text-xs text-gray-500">KOSPI {performance.kospi.change != null && <span className={`${(performance.kospi.change || 0) >= 0 ? "text-red-500" : "text-blue-500"}`}>{performance.kospi.change >= 0 ? "▲" : "▼"}{Math.abs(performance.kospi.change || 0).toFixed(2)}</span>}</div>
                </div>
              </div>
            )}
            {performance.kosdaq && (
              <div className="flex items-center gap-2 min-w-0">
                {(performance.kosdaq.change || 0) >= 0
                  ? <TrendingUp size={14} className="text-red-400 shrink-0" />
                  : <TrendingDown size={14} className="text-blue-400 shrink-0" />}
                <div className="min-w-0">
                  <div className="text-sm font-medium">{performance.kosdaq.current?.toLocaleString()}</div>
                  <div className="text-xs text-gray-500">KOSDAQ {performance.kosdaq.change != null && <span className={`${(performance.kosdaq.change || 0) >= 0 ? "text-red-500" : "text-blue-500"}`}>{performance.kosdaq.change >= 0 ? "▲" : "▼"}{Math.abs(performance.kosdaq.change || 0).toFixed(2)}</span>}</div>
                </div>
              </div>
            )}
          </div>
          {/* 환율 */}
          {performance.exchange?.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <div className="text-xs text-gray-500 mb-1.5">환율</div>
              <div className="grid grid-cols-2 gap-2">
                {performance.exchange.slice(0, 4).map((r: any, i: number) => {
                  const label: Record<string, string> = { USD: "원/달러", JPY: "원/엔(100)", EUR: "원/유로", CNY: "원/위안" };
                  const cur = r.currency || r.name || "";
                  return (
                    <div key={i} className="text-xs bg-gray-50 rounded p-1.5 flex justify-between">
                      <span className="text-gray-500">{label[cur] || cur}</span>
                      <span>
                        <span className="font-medium">{r.rate?.toLocaleString()}원</span>
                        {r.change_rate != null && (
                          <span className={`ml-1 ${r.change_rate >= 0 ? "text-red-500" : "text-blue-500"}`}>
                            {r.change_rate >= 0 ? "▲" : "▼"}{Math.abs(r.change_rate)}%
                          </span>
                        )}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {/* F&G 추세 */}
          {(performance.fear_greed?.previous_1_week != null || performance.fear_greed?.previous_1_month != null) && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <div className="text-xs text-gray-500 mb-1.5">공포·탐욕 추세</div>
              <div className="flex gap-3 text-xs">
                {[
                  { label: "1주 전", val: performance.fear_greed.previous_1_week },
                  { label: "1달 전", val: performance.fear_greed.previous_1_month },
                  { label: "1년 전", val: performance.fear_greed.previous_1_year },
                ].map((item, idx) => {
                  const diff = item.val != null ? fgScore - item.val : null;
                  return (
                    <div key={idx} className="bg-gray-50 rounded p-1.5 flex-1 text-center">
                      <div className="text-gray-400">{item.label}</div>
                      <div className="font-medium">{item.val ?? "-"}</div>
                      {diff != null && <div className={`text-[10px] ${diff >= 0 ? "text-red-500" : "text-blue-500"}`}>{diff >= 0 ? "▲" : "▼"}{Math.abs(diff).toFixed(1)}p</div>}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {/* 매크로 지표 */}
          {performance.macro_indicators?.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <div className="text-xs text-gray-500 mb-1.5">글로벌 매크로</div>
              <div className="grid grid-cols-2 gap-1.5">
                {performance.macro_indicators.slice(0, 8).map((ind: any, i: number) => (
                  <div key={i} className="flex justify-between text-xs bg-gray-50 rounded p-1.5">
                    <span className="text-gray-500 truncate">{ind.name || ind.symbol}</span>
                    <span className={`font-medium ${(ind.change_pct || 0) >= 0 ? "text-red-600" : "text-blue-600"}`}>
                      {ind.price?.toLocaleString()} {ind.change_pct != null ? `(${ind.change_pct >= 0 ? "+" : ""}${ind.change_pct}%)` : ""}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {/* 테마 예측 */}
          {performance.theme_forecast?.themes?.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <div className="text-xs text-gray-500 mb-1.5">오늘의 테마 예측</div>
              {performance.theme_forecast.market_context && (
                <div className="text-xs text-gray-600 mb-1">{performance.theme_forecast.market_context}</div>
              )}
              <div className="flex flex-wrap gap-1">
                {performance.theme_forecast.themes.slice(0, 5).map((t: any, i: number) => (
                  <Badge key={i} variant="purple">{t.theme_name || t.name} {t.confidence ? `${t.confidence}%` : ""}</Badge>
                ))}
              </div>
            </div>
          )}
          {/* 매크로 추세 (indicator-history) */}
          {indicatorHistory && Object.keys(indicatorHistory).length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <div className="text-xs text-gray-500 mb-1.5">매크로 추세</div>
              <div className="grid grid-cols-2 gap-1.5">
                {Object.entries(indicatorHistory).slice(0, 6).map(([key, val]: [string, any]) => (
                  <div key={key} className="flex justify-between text-xs bg-gray-50 rounded p-1.5">
                    <span className="text-gray-500 truncate">{key}</span>
                    <span className="font-medium">{typeof val === "number" ? val.toLocaleString() : typeof val === "object" && val?.value != null ? val.value : "-"}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {/* 수급 클러스터 */}
      {supplyCluster && (
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="supply_cluster">수급 클러스터</SectionHeader>
          <div className="flex items-center gap-3 mb-3">
            <div className="text-sm font-bold text-gray-900 bg-purple-50 border border-purple-200 rounded-lg px-3 py-1.5">
              {supplyCluster.regime}
            </div>
          </div>
          <div className="text-xs text-gray-600 mb-3">{supplyCluster.strategy}</div>
          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <div className="bg-gray-50 rounded-lg p-2">
              <div className="text-gray-500">외국인</div>
              <div className={`font-semibold ${supplyCluster.foreign_net >= 0 ? "text-red-600" : "text-blue-600"}`}>
                {supplyCluster.foreign_net >= 0 ? "+" : ""}{Math.abs(supplyCluster.foreign_net) >= 1000000 ? `${(supplyCluster.foreign_net / 1000000).toFixed(1)}백만주` : `${(supplyCluster.foreign_net / 1000).toFixed(0)}천주`}
              </div>
              <div className="text-[9px] text-gray-400 mt-0.5">순매수</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-2">
              <div className="text-gray-500">기관</div>
              <div className={`font-semibold ${supplyCluster.institution_net >= 0 ? "text-red-600" : "text-blue-600"}`}>
                {supplyCluster.institution_net >= 0 ? "+" : ""}{Math.abs(supplyCluster.institution_net) >= 1000000 ? `${(supplyCluster.institution_net / 1000000).toFixed(1)}백만주` : `${(supplyCluster.institution_net / 1000).toFixed(0)}천주`}
              </div>
              <div className="text-[9px] text-gray-400 mt-0.5">순매수</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-2">
              <div className="text-gray-500">개인</div>
              <div className={`font-semibold ${supplyCluster.individual_net >= 0 ? "text-red-600" : "text-blue-600"}`}>
                {supplyCluster.individual_net >= 0 ? "+" : ""}{Math.abs(supplyCluster.individual_net) >= 1000000 ? `${(supplyCluster.individual_net / 1000000).toFixed(1)}백만주` : `${(supplyCluster.individual_net / 1000).toFixed(0)}천주`}
              </div>
              <div className="text-[9px] text-gray-400 mt-0.5">순매수</div>
            </div>
          </div>
        </section>
      )}

      {/* 내 포트폴리오 */}
      {portfolio && (
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="portfolio" count={portfolio.holdings?.length}>내 포트폴리오</SectionHeader>
          <div className="flex items-center gap-3 mb-3">
            <div className="text-2xl font-bold text-gray-900">{portfolio.health_score}<span className="text-sm font-normal text-gray-400">/100</span></div>
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
      {(
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="cross" count={crossSignal?.length ?? 0}>교차 신호</SectionHeader>
          <div className="space-y-2">
            {(crossSignal || []).map((s, i) => (
              <div key={i} className="p-2.5 bg-green-50 border border-green-100 rounded-lg">
                <div className="flex items-center justify-between">
                  <div className="min-w-0 mr-2">
                    <span className="font-medium text-sm">{s.name}</span>
                    <span className="text-xs text-gray-400 ml-1">{s.code}</span>
                  </div>
                  <div className="shrink-0">{signalBadge(s.signal)}</div>
                </div>
                <div className="text-xs text-gray-500 mt-1 flex items-center gap-1.5">
                  <span>{s.theme} · AI 신뢰도 {((s.confidence || 0) * 100).toFixed(0)}%</span>
                  {s.dual_signal && (
                    <Badge variant={s.dual_signal === "고확신" ? "success" : s.dual_signal === "혼조" ? "warning" : "default"}>
                      {s.dual_signal}
                    </Badge>
                  )}
                </div>
              </div>
            ))}
          </div>
            {!crossSignal?.length && <Empty />}
        </section>
      )}

      {/* 테마 라이프사이클 */}
      {(
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="lifecycle" count={lifecycle?.length ?? 0}>테마 라이프사이클</SectionHeader>
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
                <Scatter data={lifecycle || []}>{(lifecycle || []).map((l: any, i: number) => (<Cell key={i} fill={STAGE_FILL[l.stage] || "#6b7280"} r={Math.max(6, l.stock_count * 3)} />))}</Scatter>
              </ScatterChart>
            </ResponsiveContainer>
            <div className="flex justify-center gap-3 text-xs text-gray-400">
              {Object.entries(STAGE_DOT).map(([s, c]) => (
                <span key={s} className="flex items-center gap-1"><span className={`w-2 h-2 rounded-full ${c}`} />{s}</span>
              ))}
            </div>
          </div>
          <div className="space-y-1.5">
            {(lifecycle || []).map((l: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
                <span className="text-sm font-medium truncate min-w-0">{l.theme}</span>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs text-gray-500">{l.avg_change >= 0 ? "+" : ""}{l.avg_change}%</span>
                  <Badge variant={l.stage === "과열" ? "danger" : l.stage === "성장" ? "warning" : l.stage === "탄생" ? "success" : "default"}>{l.stage}</Badge>
                </div>
              </div>
            ))}
          </div>
            {!lifecycle?.length && <Empty />}
        </section>
      )}

      {/* 이상 거래 감지 */}
      {(
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="anomaly" count={anomalies?.length ?? 0}>이상 거래 감지</SectionHeader>
          <div className="space-y-1.5">
            {(anomalies || []).slice(0, 6).map((a, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-red-50 border border-red-100 rounded-lg gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <Zap size={14} className="text-red-400 shrink-0" />
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{a.name}</div>
                    <div className="text-xs text-gray-500">{a.type}</div>
                  </div>
                </div>
                <div className="text-right text-xs shrink-0">
                  {a.ratio && <div className="text-amber-600 font-medium">거래량 x{a.ratio}</div>}
                  {a.rsi && <div className="text-purple-600 font-medium">RSI {a.rsi}</div>}
                  {a.change_rate != null && (
                    <div className={a.change_rate >= 0 ? "text-red-600" : "text-blue-600"}>
                      등락 {a.change_rate >= 0 ? "+" : ""}{a.change_rate}%
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
            {!anomalies?.length && <Empty />}
        </section>
      )}

      {/* 위험 종목 모니터 */}
      {(
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="risk" count={riskMonitor?.length ?? 0}>위험 종목 모니터</SectionHeader>
          <div className="space-y-1.5">
            {(riskMonitor || []).slice(0, 6).map((r, i) => (
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
            {!riskMonitor?.length && <Empty />}
        </section>
      )}

      {/* 스마트 머니 TOP */}
      {(
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="smartmoney" count={smartMoney?.length ?? 0}>스마트 머니 TOP</SectionHeader>
          <div className="space-y-1.5">
            {(smartMoney || []).slice(0, 8).map((s, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 text-[10px] font-bold flex items-center justify-center shrink-0">
                    {i + 1}
                  </div>
                  <div className="min-w-0">
                    <span className="text-sm font-medium truncate block">{s.name}</span>
                    {s.dual_signal && (
                      <span className={`text-[10px] ${s.dual_signal === "고확신" ? "text-green-600" : "text-gray-400"}`}>
                        {s.dual_signal}{s.total_score != null ? ` · 종합 ${s.total_score}점` : ""}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {signalBadge(s.signal)}
                  <div className="text-right shrink-0">
                    <div className="text-sm font-bold text-blue-700">{s.smart_money_score}</div>
                    <div className="text-[9px] text-gray-400">스코어</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
            {!smartMoney?.length && <Empty />}
        </section>
      )}

      {/* 전략 시뮬레이션 */}
      {(
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="simulation">전략 시뮬레이션</SectionHeader>
          <div className="space-y-2">
            {(simulation || []).map((s, i) => {
              const strategyLabel = (s.strategy || "")
                .replace("signal=적극매수", "적극매수 신호")
                .replace("signal=매수", "매수 신호")
                .replace(/hold=(\d+)/, "→ $1일 보유")
                .replace(/stop=(-?\d+)/, "· 손절 $1%");
              return (
                <div key={i} className="p-3 bg-gray-50 rounded-lg">
                  <div className="text-xs text-blue-600 font-medium mb-2 flex items-center gap-1">
                    <Activity size={12} className="shrink-0" />
                    <span className="truncate">{strategyLabel || s.strategy}</span>
                  </div>
                  {s.total_trades > 0 ? (
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
                  ) : (
                    <div className="text-xs text-gray-400 text-center py-1">거래 데이터 축적 중</div>
                  )}
                </div>
              );
            })}
          </div>
            {!simulation?.length && <Empty />}
        </section>
      )}

      {/* 차트 패턴 매칭 */}
      {(
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="pattern">차트 패턴 매칭</SectionHeader>
          <div className="space-y-3">
            {(pattern || []).map((p, i) => (
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
            {!pattern?.length && <Empty />}
        </section>
      )}

      {/* 뉴스 임팩트 */}
      {(
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="news">뉴스 임팩트</SectionHeader>
          <div className="space-y-3">
            {Object.entries(newsImpact || {}).map(([cat, data]: [string, any]) => (
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
            {!Object.keys(newsImpact || {}).length && <Empty />}
        </section>
      )}

      {/* 갭 분석 */}
      {(
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="gap" count={gapAnalysis?.length ?? 0}>갭 분석</SectionHeader>
          <div className="space-y-1.5">
            {(gapAnalysis || []).slice(0, 6).map((g, i) => (
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
            {!gapAnalysis?.length && <Empty />}
        </section>
      )}

      {/* 공매도 역발상 */}
      {(
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="squeeze" count={shortSqueeze?.length ?? 0}>역발상 시그널</SectionHeader>
          <div className="space-y-1.5">
            {(shortSqueeze || []).slice(0, 6).map((s, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-orange-50 border border-orange-100 rounded-lg gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{s.name}</div>
                  <div className="text-xs text-gray-500 truncate">{s.overheating}</div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {signalBadge(s.signal)}
                  <div className="text-right shrink-0">
                    <div className="text-sm font-bold text-orange-600">{s.squeeze_score}</div>
                    <div className="text-[9px] text-gray-400">역발상</div>
                  </div>
                </div>
              </div>
            ))}
            <p className="text-[10px] text-gray-400">과열 경고 + 외국인 매수 전환 = 역발상 매수 기회</p>
          </div>
            {!shortSqueeze?.length && <Empty />}
        </section>
      )}

      {/* 밸류에이션 */}
      {(
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="valuation" count={valuation?.length ?? 0}>밸류에이션 스크리너</SectionHeader>
          <div className="space-y-1.5">
            {(valuation || []).slice(0, 6).map((v, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{v.name}</div>
                  <div className="text-xs text-gray-500">
                    {v.per ? `PER ${v.per}` : v.ma_aligned ? "MA정배열" : "MA비정배열"}
                    {v.pbr ? ` · PBR ${v.pbr}` : ""}
                    {v.roe ? ` · ROE ${v.roe}%` : ""}
                    {v.opm ? ` · 영업이익률 ${v.opm}%` : ""}
                    {v.debt_ratio ? ` · 부채 ${v.debt_ratio}%` : ""}
                    {!v.per && v.foreign_net > 0 ? " · 외국인 매수" : ""}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {signalBadge(v.signal)}
                  <div className="text-right shrink-0">
                    <div className="text-sm font-bold text-green-700">{v.value_score}</div>
                    <div className="text-[9px] text-gray-400">밸류</div>
                  </div>
                </div>
              </div>
            ))}
            <p className="text-[10px] text-gray-400">PER · PBR · ROE + 매매신호 종합 밸류 스코어</p>
          </div>
            {!valuation?.length && <Empty />}
        </section>
      )}

      {/* 거래량-가격 괴리 */}
      {(
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="divergence" count={divergence?.length ?? 0}>거래량-가격 괴리</SectionHeader>
          <div className="space-y-1.5">
            {(divergence || []).slice(0, 6).map((d, i) => (
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
            {!divergence?.length && <Empty />}
        </section>
      )}

      {/* 테마별 자금 흐름 */}
      {(
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="sector">테마별 자금 흐름</SectionHeader>
          <div className="space-y-1.5">
            {Object.entries(sectors || {})
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
            {!Object.keys(sectors || {}).length && <Empty />}
        </section>
      )}

      {/* 테마 전이 예측 */}
      {(
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="propagation" count={propagation?.length ?? 0}>테마 전이 예측</SectionHeader>
          <div className="space-y-2">
            {(propagation || []).map((p, i) => (
              <div key={i} className="p-2.5 bg-violet-50 border border-violet-100 rounded-lg">
                <div className="text-sm font-medium text-gray-900 mb-1">{p.theme}</div>
                <div className="text-xs text-gray-600">
                  <span className="text-violet-600 font-medium">{p.leader}</span>
                  <span className="text-gray-400 mx-1">→</span>
                  {p.followers?.join(", ")}
                </div>
                <div className="text-[10px] text-gray-400 mt-1">예상 전이 시간: ~{p.lag_minutes}분</div>
              </div>
            ))}
          </div>
            {!propagation?.length && <Empty />}
        </section>
      )}

      {/* 손절/익절 최적화 */}
      {(
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="exit" count={exitOptimizer?.length ?? 0}>손절/익절 최적화</SectionHeader>
          <div className="space-y-1.5">
            {(exitOptimizer || []).slice(0, 6).map((e, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{e.name}</div>
                  <div className="text-xs text-gray-500">{e.signal}</div>
                </div>
                <div className="flex gap-3 shrink-0 text-xs">
                  <div className="text-center">
                    <div className="text-blue-600 font-medium">{e.stop_loss}%</div>
                    <div className="text-[10px] text-gray-400">손절</div>
                  </div>
                  <div className="text-center">
                    <div className="text-red-600 font-medium">+{e.take_profit}%</div>
                    <div className="text-[10px] text-gray-400">익절</div>
                  </div>
                  <div className="text-center">
                    <div className="text-amber-600 font-medium">{e.trailing_stop}%</div>
                    <div className="text-[10px] text-gray-400">추적</div>
                  </div>
                </div>
              </div>
            ))}
            <p className="text-[10px] text-gray-400">추적 = 최고점 대비 하락 시 자동 매도 기준</p>
          </div>
            {!exitOptimizer?.length && <Empty />}
        </section>
      )}

      {/* 이벤트 캘린더 */}
      {(
        <section className="bg-white border border-gray-200 rounded-xl p-4">
          <SectionHeader id="events" count={eventCalendar?.events?.length ?? 0}>이벤트 캘린더</SectionHeader>
          <div className="space-y-1.5">
            {(eventCalendar?.events || []).map((ev: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
                <div className="min-w-0">
                  <div className="text-sm font-medium">{ev.name}</div>
                  <div className="text-xs text-gray-500">{ev.date}</div>
                </div>
                <Badge variant={ev.impact === "high" ? "danger" : ev.impact === "medium" ? "warning" : "default"}>
                  {ev.impact === "high" ? "고영향" : ev.impact === "medium" ? "중영향" : "저영향"}
                </Badge>
              </div>
            ))}
          </div>
            {!(eventCalendar?.events || []).length && <Empty />}
        </section>
      )}

      {/* 프로그램 매매 */}
      <section className="bg-white border border-gray-200 rounded-xl p-4">
        <SectionHeader id="program">프로그램 매매</SectionHeader>
        {programTrading?.data ? (
          <div className="space-y-1.5">
            {(programTrading.data.kospi || []).slice(0, 5).map((p: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
                <span className="text-sm text-gray-700">{p.investor}</span>
                <div className="flex gap-3 text-xs shrink-0">
                  <span className={`font-medium ${p.all_ntby_amt >= 0 ? "text-red-600" : "text-blue-600"}`}>
                    {p.all_ntby_amt >= 0 ? "+" : ""}{(p.all_ntby_amt / 100).toFixed(0)}억
                  </span>
                </div>
              </div>
            ))}
            {/* 종목별 프로그램 매매 */}
            {programTrading.by_stock?.length > 0 && (
              <div className="mt-2 pt-2 border-t border-gray-100">
                <div className="text-xs text-gray-500 mb-1">종목별 프로그램 순매수</div>
                {programTrading.by_stock.slice(0, 5).map((ps: any, i: number) => (
                  <div key={i} className="flex items-center justify-between text-xs py-1">
                    <span className="text-gray-700 truncate">{ps.name}</span>
                    <span className={`font-medium ${ps.program_net >= 0 ? "text-red-600" : "text-blue-600"}`}>
                      {ps.program_net >= 0 ? "+" : ""}{(ps.program_net / 1000).toFixed(0)}천주
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : <Empty />}
      </section>

      {/* 시간대별 수익률 */}
      <section className="bg-white border border-gray-200 rounded-xl p-4">
        <SectionHeader id="heatmap">시간대별 수익률</SectionHeader>
        {heatmap?.snapshots?.length ? (
          <div className="space-y-1.5">
            {heatmap.snapshots.map((snap: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
                <div className="text-xs text-gray-500">{snap.time}</div>
                <div className="flex gap-3 text-xs">
                  <span className={`font-medium ${(snap.foreign || 0) >= 0 ? "text-red-600" : "text-blue-600"}`}>
                    외국인 {snap.foreign >= 0 ? "+" : ""}{(snap.foreign / 100000000).toFixed(1)}억
                  </span>
                  <span className={`font-medium ${(snap.institution || 0) >= 0 ? "text-red-600" : "text-blue-600"}`}>
                    기관 {snap.institution >= 0 ? "+" : ""}{(snap.institution / 100000000).toFixed(1)}억
                  </span>
                </div>
              </div>
            ))}
            <p className="text-[10px] text-gray-400">장중 시간대별 외국인·기관 순매매 추이</p>
          </div>
        ) : heatmap?.hours ? (
          <div className="grid grid-cols-7 gap-1">
            {Object.entries(heatmap.hours).map(([hour, ret]: [string, any]) => (
              <div key={hour} className={`text-center p-2 rounded-lg ${ret >= 0.5 ? "bg-red-50" : ret >= 0 ? "bg-gray-50" : "bg-blue-50"}`}>
                <div className="text-[10px] text-gray-500">{hour}시</div>
                <div className={`text-xs font-medium ${ret >= 0.5 ? "text-red-600" : ret >= 0 ? "text-gray-600" : "text-blue-600"}`}>
                  {ret >= 0 ? "+" : ""}{ret}%
                </div>
              </div>
            ))}
          </div>
        ) : <Empty />}
        {!heatmap?.snapshots?.length && <p className="text-[10px] text-gray-400 mt-2">시간대별 평균 수익률 (양수=상승 경향, 음수=하락 경향)</p>}
      </section>

      {/* 내부자 거래 */}
      <section className="bg-white border border-gray-200 rounded-xl p-4">
        <SectionHeader id="insider" count={insiderTrades?.length ?? 0}>내부자 거래</SectionHeader>
        <div className="space-y-1.5">
          {(insiderTrades || []).map((t, i) => (
            <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{t.name || t.corp_name}</div>
                <div className="text-xs text-gray-500">{t.executive} · {t.position}</div>
              </div>
              <div className="text-right shrink-0">
                <div className={`text-xs font-medium ${t.type === "매수" ? "text-red-600" : "text-blue-600"}`}>{t.type} {t.shares?.toLocaleString()}주</div>
                <div className="text-[10px] text-gray-400">{t.date}</div>
              </div>
            </div>
          ))}
        </div>
        {!insiderTrades?.length && <Empty />}
      </section>

      {/* 컨센서스 괴리 */}
      <section className="bg-white border border-gray-200 rounded-xl p-4">
        <SectionHeader id="consensus" count={consensus?.length ?? 0}>컨센서스 괴리</SectionHeader>
        <div className="space-y-1.5">
          {(consensus || []).map((c, i) => (
            <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{c.name}</div>
                <div className="text-xs text-gray-500">
                  {c.current_price > 0 ? `현재가 ${c.current_price?.toLocaleString()}원` : "매수 신호 종목"}
                </div>
              </div>
              <div className="text-right shrink-0">
                {c.target_price > 0 ? (
                  <>
                    <div className="text-xs font-medium text-amber-600">목표 {c.target_price?.toLocaleString()}원</div>
                    <div className={`text-[10px] ${c.gap_pct >= 0 ? "text-red-500" : "text-blue-500"}`}>
                      괴리 {c.gap_pct >= 0 ? "+" : ""}{c.gap_pct}%
                    </div>
                  </>
                ) : (
                  <div className="text-xs text-gray-400">목표가 수집 중</div>
                )}
              </div>
            </div>
          ))}
        </div>
        {!consensus?.length && <Empty />}
      </section>

      {/* 동시호가 분석 */}
      <section className="bg-white border border-gray-200 rounded-xl p-4">
        <SectionHeader id="auction" count={auction?.length ?? 0}>동시호가 분석</SectionHeader>
        <div className="space-y-1.5">
          {(auction || []).map((a, i) => (
            <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{a.name}</div>
                <div className="text-xs text-gray-500">{a.session === "opening" ? "시가" : "종가"} 동시호가</div>
              </div>
              <div className="text-right shrink-0">
                <div className={`text-xs font-medium ${a.pressure === "매수우위" ? "text-red-600" : "text-blue-600"}`}>{a.pressure}</div>
                <div className="text-[10px] text-gray-400">비율 {a.ratio}</div>
              </div>
            </div>
          ))}
        </div>
        {!auction?.length && <Empty />}
        <p className="text-[10px] text-gray-400 mt-1">장중 실시간 호가 기반 · 휴장 시 최근 데이터</p>
      </section>

      {/* 호가창 압력 */}
      <section className="bg-white border border-gray-200 rounded-xl p-4">
        <SectionHeader id="orderbook" count={orderbook?.length ?? 0}>호가창 압력</SectionHeader>
        <div className="space-y-1.5">
          {(orderbook || []).map((o, i) => (
            <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{o.name}</div>
                {o.bid_ask_ratio != null && (
                  <div className="text-xs text-gray-500">
                    매수잔량 {o.bid_volume?.toLocaleString()} · 매도잔량 {o.ask_volume?.toLocaleString()}
                    {o.bid_ask_ratio ? ` · 비율 ${o.bid_ask_ratio}` : ""}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <div className="w-16 h-2 bg-gray-100 rounded-full overflow-hidden flex">
                  {(() => {
                    const pct = o.bid_volume && o.ask_volume ? Math.round(o.bid_volume / (o.bid_volume + o.ask_volume) * 100) : (o.buy_pct || 50);
                    return (<><div className="bg-red-400 h-full" style={{width: `${pct}%`}} /><div className="bg-blue-400 h-full" style={{width: `${100 - pct}%`}} /></>);
                  })()}
                </div>
                <span className={`text-xs font-medium ${(() => {
                  const pct = o.bid_volume && o.ask_volume ? Math.round(o.bid_volume / (o.bid_volume + o.ask_volume) * 100) : (o.buy_pct || 50);
                  return pct > 50 ? "text-red-600" : "text-blue-600";
                })()}`}>
                  {(() => {
                    const pct = o.bid_volume && o.ask_volume ? Math.round(o.bid_volume / (o.bid_volume + o.ask_volume) * 100) : (o.buy_pct || 50);
                    return `${pct > 50 ? "매수" : "매도"}우위 ${pct}%`;
                  })()}
                </span>
              </div>
            </div>
          ))}
        </div>
        {!orderbook?.length && <Empty />}
      </section>

      {/* 상관관계 네트워크 */}
      <section className="bg-white border border-gray-200 rounded-xl p-4">
        <SectionHeader id="correlation">상관관계 네트워크</SectionHeader>
        {correlationData?.pairs?.length ? (
          <div className="space-y-1.5">
            {correlationData.pairs.map((p: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
                <div className="text-sm min-w-0">
                  <span className="font-medium">{p.stock_a}</span>
                  <span className="text-gray-400 mx-1">↔</span>
                  <span className="font-medium">{p.stock_b}</span>
                </div>
                <div className="shrink-0">
                  <div className={`w-12 h-2 bg-gray-100 rounded-full overflow-hidden`}>
                    <div className={`h-full rounded-full ${p.correlation > 0.7 ? "bg-red-400" : p.correlation > 0.3 ? "bg-amber-400" : "bg-green-400"}`} style={{width: `${Math.abs(p.correlation) * 100}%`}} />
                  </div>
                  <div className="text-[10px] text-gray-500 text-right">{p.correlation?.toFixed(2)} {Math.abs(p.correlation) > 0.7 ? "높음" : Math.abs(p.correlation) > 0.3 ? "보통" : "낮음"}</div>
                </div>
              </div>
            ))}
            <p className="text-[10px] text-gray-400">0.7 이상 = 높은 상관 (분산 효과 낮음)</p>
          </div>
        ) : <Empty />}
      </section>

      {/* 실적 프리뷰 */}
      <section className="bg-white border border-gray-200 rounded-xl p-4">
        <SectionHeader id="earnings" count={earningsCalendar?.items?.length ?? 0}>실적 프리뷰</SectionHeader>
        <div className="space-y-1.5">
          {(earningsCalendar?.items || []).slice(0, 6).map((e: any, i: number) => (
            <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{e.corp_name || e.name}</div>
                <div className="text-xs text-gray-500">{e.report_type || "실적 공시"}</div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-xs text-gray-700">{e.date}</div>
              </div>
            </div>
          ))}
        </div>
        {!(earningsCalendar?.items || []).length && <Empty />}
      </section>

      {/* AI 투자 멘토 */}
      <section className="bg-white border border-gray-200 rounded-xl p-4">
        <SectionHeader id="mentor">AI 투자 멘토</SectionHeader>
        {aiMentor?.advice?.length ? (
          <div className="space-y-2">
            {aiMentor.advice.map((a: any, i: number) => (
              <div key={i} className="p-2.5 bg-indigo-50 border border-indigo-100 rounded-lg">
                <div className="text-xs font-medium text-indigo-700 mb-1">{a.category}</div>
                <div className="text-sm text-gray-700">{a.message}</div>
              </div>
            ))}
          </div>
        ) : <Empty />}
      </section>

      {/* 증권사 매매 동향 */}
      <section className="bg-white border border-gray-200 rounded-xl p-4">
        <SectionHeader id="member" count={memberTrading?.length ?? 0}>증권사 매매 동향</SectionHeader>
        <div className="space-y-1.5">
          {(memberTrading || []).slice(0, 6).map((m, i) => (
            <div key={i} className="p-2 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium truncate">{m.name}</span>
                <span className={`text-xs font-medium ${(m.foreign_net || 0) >= 0 ? "text-red-600" : "text-blue-600"}`}>
                  외국인 {m.foreign_net >= 0 ? "+" : ""}{(m.foreign_net / 1000).toFixed(0)}천주
                </span>
              </div>
              <div className="flex gap-2 text-xs text-gray-500">
                <span>매수: {m.buy_top5?.map((b: any) => b.name || b).join(", ")}</span>
              </div>
            </div>
          ))}
        </div>
        {!memberTrading?.length && <Empty />}
      </section>

      {/* 거래대금 TOP */}
      <section className="bg-white border border-gray-200 rounded-xl p-4">
        <SectionHeader id="trading_value" count={tradingValue?.length ?? 0}>거래대금 TOP</SectionHeader>
        <div className="space-y-1.5">
          {(tradingValue || []).slice(0, 10).map((tv, i) => (
            <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-5 h-5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-bold flex items-center justify-center shrink-0">
                  {i + 1}
                </div>
                <span className="text-sm font-medium truncate">{tv.name}</span>
              </div>
              <div className="text-right shrink-0 text-xs">
                <div className={`font-medium ${(tv.change_rate || 0) >= 0 ? "text-red-600" : "text-blue-600"}`}>
                  {(tv.change_rate || 0) >= 0 ? "+" : ""}{tv.change_rate}%
                </div>
                {tv.trading_value && <div className="text-gray-400">{(tv.trading_value / 100000000).toFixed(0)}억</div>}
              </div>
            </div>
          ))}
        </div>
        {!tradingValue?.length && <Empty />}
      </section>

      {/* 모의투자 현황 */}
      <section className="bg-white border border-gray-200 rounded-xl p-4">
        <SectionHeader id="paper_trading">모의투자 현황</SectionHeader>
        {paperTrading?.stocks?.length ? (
          <div className="space-y-1.5">
            <div className="text-xs text-gray-500 mb-2">날짜: {paperTrading.date}</div>
            {paperTrading.stocks.slice(0, 6).map((s: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
                <span className="text-sm font-medium truncate">{s.name || s.code}</span>
                <div className="text-right shrink-0 text-xs">
                  {s.return_pct != null && (
                    <span className={`font-medium ${s.return_pct >= 0 ? "text-red-600" : "text-blue-600"}`}>
                      {s.return_pct >= 0 ? "+" : ""}{s.return_pct}%
                    </span>
                  )}
                </div>
              </div>
            ))}
            {paperTrading.summary && (
              <div className="text-xs text-gray-500 mt-2 bg-blue-50 rounded p-2">
                총 수익률: {paperTrading.summary.total_return ?? "-"}%
              </div>
            )}
          </div>
        ) : <Empty />}
      </section>

      {/* 예측 적중률 */}
      <section className="bg-white border border-gray-200 rounded-xl p-4">
        <SectionHeader id="forecast">예측 적중률</SectionHeader>
        {forecastAccuracy?.overall_accuracy != null && (
          <div className="flex items-center gap-3 mb-3">
            <div className="text-2xl font-bold text-gray-900">{forecastAccuracy.overall_accuracy}%</div>
            <div className="text-xs text-gray-500">
              전체 적중률 ({forecastAccuracy.total_hits}/{forecastAccuracy.total_predictions})
            </div>
          </div>
        )}
        <div className="space-y-1.5">
          {(forecastAccuracy?.predictions || []).map((fc: any, i: number) => (
            <div key={i} className="p-2 bg-gray-50 rounded-lg">
              <div className="flex justify-between text-xs text-gray-500 mb-1">
                <span>{fc.date}</span>
                <span>{fc.hit_count}/{fc.total} 적중</span>
              </div>
              <div className="flex flex-wrap gap-1">
                {(fc.themes || []).map((t: string, j: number) => (
                  <Badge key={j} variant={fc.hits?.[j] ? "success" : "default"}>
                    {fc.hits?.[j] ? "✓ " : ""}{t}
                  </Badge>
                ))}
              </div>
            </div>
          ))}
        </div>
        {!(forecastAccuracy?.predictions || []).length && <Empty />}
      </section>

      {/* Volume Profile 지지/저항 */}
      <section className="bg-white border border-gray-200 rounded-xl p-4">
        <SectionHeader id="volume_profile" count={volumeProfile?.length ?? 0}>매물대 지지/저항</SectionHeader>
        <div className="space-y-1.5">
          {(volumeProfile || []).slice(0, 8).map((vp, i) => (
            <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{vp.name}</div>
              </div>
              <div className="flex gap-2 text-xs shrink-0">
                {vp.poc_1week ? <div className="text-center"><div className="text-gray-400">1주 POC</div><div className="font-medium">{vp.poc_1week?.toLocaleString()}원</div></div> : null}
                {vp.poc_1month ? <div className="text-center"><div className="text-gray-400">1개월 POC</div><div className="font-medium">{vp.poc_1month?.toLocaleString()}원</div></div> : null}
                {vp.poc_3month ? <div className="text-center"><div className="text-gray-400">3개월 POC</div><div className="font-medium">{vp.poc_3month?.toLocaleString()}원</div></div> : null}
              </div>
            </div>
          ))}
          <p className="text-[10px] text-gray-400">POC = 가장 많이 거래된 핵심 가격대 (지지/저항선)</p>
        </div>
        {!volumeProfile?.length && <Empty />}
      </section>

      {/* 신호 일관성 추적 */}
      <section className="bg-white border border-gray-200 rounded-xl p-4">
        <SectionHeader id="consistency" count={signalConsistency?.length ?? 0}>신호 일관성</SectionHeader>
        <div className="space-y-1.5">
          {(signalConsistency || []).slice(0, 8).map((sc, i) => (
            <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{sc.name}</div>
                <div className="text-xs text-gray-500">
                  {sc.signals?.join(" → ")} ({sc.days}일)
                </div>
              </div>
              <Badge variant={sc.consistency === "일관" ? "success" : sc.consistency === "변동" ? "danger" : "warning"}>
                {sc.consistency === "일관" ? `${sc.days}일 연속` : sc.consistency === "변동" ? "신호 불안정" : "부분 일치"}
              </Badge>
            </div>
          ))}
          <p className="text-[10px] text-gray-400">연속 동일 신호 = 높은 신뢰도 · 잦은 변동 = 주의</p>
        </div>
        {!signalConsistency?.length && <Empty />}
      </section>

      {/* 시뮬레이션 히스토리 */}
      <section className="bg-white border border-gray-200 rounded-xl p-4">
        <SectionHeader id="sim_history" count={simulationHistory?.length ?? 0}>시뮬레이션 히스토리</SectionHeader>
        <div className="space-y-1.5">
          {(simulationHistory || []).map((sh, i) => (
            <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
              <div className="text-xs text-gray-500">{sh.date}</div>
              <div className="flex gap-3 text-xs shrink-0">
                <div className="text-center">
                  <div className="text-gray-400">거래수</div>
                  <div className="font-medium">{sh.total_trades}</div>
                </div>
                <div className="text-center">
                  <div className="text-gray-400">승률</div>
                  <div className={`font-medium ${(sh.win_rate || 0) >= 50 ? "text-red-600" : "text-blue-600"}`}>{sh.win_rate}%</div>
                </div>
                <div className="text-center">
                  <div className="text-gray-400">수익</div>
                  <div className={`font-medium ${(sh.avg_return || 0) >= 0 ? "text-red-600" : "text-blue-600"}`}>
                    {(sh.avg_return || 0) >= 0 ? "+" : ""}{sh.avg_return?.toFixed(1)}%
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
        {!simulationHistory?.length && <Empty />}
      </section>

      {/* 장중 종목별 수급 */}
      <section className="bg-white border border-gray-200 rounded-xl p-4">
        <SectionHeader id="intraday_flow" count={intradayStockFlow?.length ?? 0}>장중 종목별 수급</SectionHeader>
        <div className="space-y-1.5">
          {(intradayStockFlow || []).slice(0, 10).map((isf, i) => (
            <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg gap-2">
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{isf.name || isf.code}</div>
                <div className="text-xs text-gray-500">
                  {isf.name ? isf.code : ""}
                  {isf.current_price > 0 && <span className="ml-1">{isf.current_price?.toLocaleString()}원</span>}
                  {isf.change_rate != null && (
                    <span className={`ml-1 ${(isf.change_rate || 0) >= 0 ? "text-red-500" : "text-blue-500"}`}>
                      {isf.change_rate >= 0 ? "+" : ""}{isf.change_rate}%
                    </span>
                  )}
                </div>
              </div>
              <div className="flex gap-2 text-xs shrink-0">
                <div className={`text-center ${(isf.foreign || 0) >= 0 ? "text-red-600" : "text-blue-600"}`}>
                  <div className="text-gray-400">외국인</div>
                  <div className="font-medium">{isf.foreign >= 0 ? "+" : ""}{Math.abs(isf.foreign) >= 10000 ? `${(isf.foreign / 10000).toFixed(0)}만주` : `${isf.foreign?.toLocaleString()}주`}</div>
                </div>
                <div className={`text-center ${(isf.institution || 0) >= 0 ? "text-red-600" : "text-blue-600"}`}>
                  <div className="text-gray-400">기관</div>
                  <div className="font-medium">{isf.institution >= 0 ? "+" : ""}{Math.abs(isf.institution) >= 10000 ? `${(isf.institution / 10000).toFixed(0)}만주` : `${isf.institution?.toLocaleString()}주`}</div>
                </div>
              </div>
            </div>
          ))}
          <p className="text-[10px] text-gray-400">최근 장중 가집계 시점 기준 종목별 투자자 동향</p>
        </div>
        {!intradayStockFlow?.length && <Empty />}
      </section>

      {/* 매매 일지 */}
      <section className="bg-white border border-gray-200 rounded-xl p-4">
        <SectionHeader id="journal" count={tradingJournal?.entries?.length ?? 0}>매매 일지</SectionHeader>
        <div className="space-y-1.5">
          {(tradingJournal?.entries || []).map((e: any, i: number) => (
            <div key={i} className="p-2.5 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium">{e.name}</span>
                <Badge variant={e.action === "매수" ? "danger" : "blue"}>{e.action}</Badge>
              </div>
              <div className="text-xs text-gray-500">{e.date} · {e.reason}</div>
            </div>
          ))}
        </div>
        {!(tradingJournal?.entries || []).length && <Empty />}
      </section>
    </div>
  );
}
