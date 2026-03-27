const BASE_URL = import.meta.env.BASE_URL + "data/";

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(BASE_URL + path, { cache: "no-cache" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export const dataService = {
  getPerformance: () => fetchJson<any>("performance.json"),
  getAnomalies: () => fetchJson<any[]>("anomalies.json"),
  getSmartMoney: () => fetchJson<any[]>("smart_money.json"),
  getSectorFlow: () => fetchJson<Record<string, any>>("sector_flow.json"),
  getNewsImpact: () => fetchJson<Record<string, any>>("news_impact.json"),
  getCrossSignal: () => fetchJson<any[]>("cross_signal.json"),
  getLifecycle: () => fetchJson<any[]>("lifecycle.json"),
  getRiskMonitor: () => fetchJson<any[]>("risk_monitor.json"),
  getBriefing: () => fetchJson<any>("briefing.json"),
  getSimulation: () => fetchJson<any[]>("simulation.json"),
  getPattern: () => fetchJson<any[]>("pattern.json"),
  getScannerStocks: () => fetchJson<any[]>("scanner_stocks.json"),
  getSentiment: () => fetchJson<any>("sentiment.json"),
  getShortSqueeze: () => fetchJson<any[]>("short_squeeze.json"),
  getGapAnalysis: () => fetchJson<any[]>("gap_analysis.json"),
  getValuation: () => fetchJson<any[]>("valuation.json"),
  getVolumeDivergence: () => fetchJson<any[]>("volume_divergence.json"),
  getPremarket: () => fetchJson<any>("premarket.json"),
  getPortfolio: () => fetchJson<any>("portfolio.json"),
  getSupplyCluster: () => fetchJson<any>("supply_cluster.json"),
  getExitOptimizer: () => fetchJson<any[]>("exit_optimizer.json"),
  getEventCalendar: () => fetchJson<any>("event_calendar.json"),
  getThemePropagation: () => fetchJson<any[]>("theme_propagation.json"),
  getProgramTrading: () => fetchJson<any>("program_trading.json"),
  getIntradayHeatmap: () => fetchJson<any>("intraday_heatmap.json"),
  getInsiderTrades: () => fetchJson<any[]>("insider_trades.json"),
  getConsensus: () => fetchJson<any[]>("consensus.json"),
  getAuction: () => fetchJson<any[]>("auction.json"),
  getOrderbook: () => fetchJson<any[]>("orderbook.json"),
  getCorrelation: () => fetchJson<any>("correlation.json"),
  getTradingJournal: () => fetchJson<any>("trading_journal.json"),
  getTradingValue: () => fetchJson<any[]>("trading_value.json"),
  getPaperTrading: () => fetchJson<any>("paper_trading_latest.json"),
  getForecastAccuracy: () => fetchJson<any>("forecast_accuracy.json"),
  getVolumeProfile: () => fetchJson<any[]>("volume_profile.json"),
  getSignalConsistency: () => fetchJson<any[]>("signal_consistency.json"),
  getSimulationHistory: () => fetchJson<any[]>("simulation_history.json"),
  getIntradayStockFlow: () => fetchJson<any[]>("intraday_stock_flow.json"),
  getIndicatorHistory: () => fetchJson<any>("indicator_history.json"),
  getStockMaster: () => fetchJson<any>("stock-master.json"),
  getConsecutiveSignals: () => fetchJson<any>("consecutive_signals.json"),
};
