#!/bin/bash
# 원격 최신 데이터 다운로드 — results/ + frontend/public/data/ 양쪽 저장
cd "$(dirname "$0")/.."

BASE="https://xxonbang.github.io/stock_toolkit/data"
THEME="https://xxonbang.github.io/theme-analyzer/data"

FILES=(
  stock-master.json
  cross_signal.json
  portfolio.json
  performance.json
  source_performance.json
  briefing.json
  premarket.json
  ai_mentor.json
  consecutive_monitor.json
  consecutive_signals.json
  forecast_accuracy.json
  gap_analysis.json
  indicator_history.json
  intraday_heatmap.json
  intraday_stock_flow.json
  intraday_stock_tracker.json
  lifecycle.json
  news_impact.json
  orderbook.json
  paper_trading_latest.json
  pattern.json
  program_trading.json
  risk_monitor.json
  scanner_stocks.json
  sector_flow.json
  sentiment.json
  short_squeeze.json
  signal_consistency.json
  simulation.json
  simulation_history.json
  smart_money.json
  supply_cluster.json
  trading_journal.json
  trading_value.json
  valuation.json
  volume_divergence.json
  volume_profile.json
  anomalies.json
  auction.json
)

for f in "${FILES[@]}"; do
  curl -s -o "results/$f" "$BASE/$f"
  cp "results/$f" "frontend/public/data/$f"
done

# theme-analyzer
curl -s -o "results/intraday-history.json" "$THEME/intraday-history.json"
cp "results/intraday-history.json" "frontend/public/data/intraday-history.json"

echo "완료 (${#FILES[@]} + intraday-history)"
