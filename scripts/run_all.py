"""전체 모듈 실행 (Phase 1~4)"""
import sys
import json
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import THEME_DATA_PATH, SIGNAL_DATA_PATH
from core.data_loader import DataLoader
from core.telegram_bot import send_message
from core.gemini_client import GeminiClient

from modules.cross_signal import run as run_cross_signal, find_cross_signals
from modules.daily_briefing import generate_morning_brief, generate_evening_review
from modules.system_performance import build_performance_report
from modules.anomaly_detector import run_anomaly_scan, format_anomaly_alert
from modules.smart_money import calculate_smart_money_score
from modules.sector_flow import aggregate_by_sector, format_sector_flow
from modules.news_impact import build_impact_database, calculate_impact_stats
from modules.theme_lifecycle import track_theme_lifecycle, format_lifecycle_alert
from modules.risk_monitor import evaluate_risk


def main():
    loader = DataLoader(THEME_DATA_PATH, SIGNAL_DATA_PATH)
    gemini = GeminiClient()
    results_dir = Path(__file__).parent.parent / "results"
    results_dir.mkdir(exist_ok=True)

    # Phase 1
    print("=== Phase 1: 알림 & 브리핑 ===")
    cross_matches = run_cross_signal(loader, send_message)
    with open(results_dir / "cross_signal.json", "w", encoding="utf-8") as f:
        json.dump(cross_matches or [], f, ensure_ascii=False, indent=2)

    report = build_performance_report(loader)
    with open(results_dir / "performance.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Phase 2
    print("=== Phase 2: 모니터링 ===")
    latest = loader.get_latest()
    stocks = latest.get("rising_stocks", []) + latest.get("volume_top", [])
    anomalies = run_anomaly_scan(stocks)
    with open(results_dir / "anomalies.json", "w", encoding="utf-8") as f:
        json.dump(anomalies, f, ensure_ascii=False, indent=2)

    all_stocks = latest.get("rising_stocks", [])
    smart_money_results = []
    for stock in all_stocks:
        score = calculate_smart_money_score(stock)
        if score >= 70:
            smart_money_results.append({**stock, "smart_money_score": score})
    smart_money_results.sort(key=lambda x: x["smart_money_score"], reverse=True)
    with open(results_dir / "smart_money.json", "w", encoding="utf-8") as f:
        json.dump(smart_money_results, f, ensure_ascii=False, indent=2)

    all_flow_stocks = latest.get("rising_stocks", []) + latest.get("falling_stocks", [])
    sectors = aggregate_by_sector(all_flow_stocks)
    with open(results_dir / "sector_flow.json", "w", encoding="utf-8") as f:
        json.dump(sectors, f, ensure_ascii=False, indent=2)

    # 위험 종목 평가
    risk_results = []
    combined = loader.get_combined_signals()
    for sig in combined:
        result = evaluate_risk(sig)
        if result["level"] != "낮음":
            risk_results.append(result)
    risk_results.sort(key=lambda x: len(x.get("warnings", [])), reverse=True)
    with open(results_dir / "risk_monitor.json", "w", encoding="utf-8") as f:
        json.dump(risk_results, f, ensure_ascii=False, indent=2)

    # Phase 3
    print("=== Phase 3: 분석 ===")
    history = loader.get_theme_history()
    db = build_impact_database(history)
    stats = {k: calculate_impact_stats(v) for k, v in db.items()}
    with open(results_dir / "news_impact.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    # Phase 4
    print("=== Phase 4: 라이프사이클 ===")
    themes = loader.get_themes()
    lifecycle_results = []
    for theme in themes:
        name = theme.get("name", "")
        if name:
            result = track_theme_lifecycle(name, [{"themes": h.get("data", {}).get("themes", [])} for h in history])
            lifecycle_results.append(result)
    with open(results_dir / "lifecycle.json", "w", encoding="utf-8") as f:
        json.dump(lifecycle_results, f, ensure_ascii=False, indent=2)

    # 프론트엔드 데이터 복사
    frontend_data = Path(__file__).parent.parent / "frontend" / "public" / "data"
    frontend_data.mkdir(parents=True, exist_ok=True)
    for json_file in results_dir.glob("*.json"):
        shutil.copy2(json_file, frontend_data / json_file.name)

    print("=== 전체 완료 ===")


if __name__ == "__main__":
    main()
