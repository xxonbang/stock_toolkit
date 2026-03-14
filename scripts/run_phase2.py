"""Phase 2 실행: 이상 거래 탐지 + 스마트 머니 + 섹터 흐름"""
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import THEME_DATA_PATH, SIGNAL_DATA_PATH
from core.data_loader import DataLoader
from core.telegram_bot import send_message
from modules.anomaly_detector import run_anomaly_scan, format_anomaly_alert
from modules.smart_money import calculate_smart_money_score, format_smart_money_alert
from modules.sector_flow import aggregate_by_sector, format_sector_flow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["anomaly", "smart_money", "sector", "all"], default="all")
    args = parser.parse_args()

    loader = DataLoader(THEME_DATA_PATH, SIGNAL_DATA_PATH)
    results_dir = Path(__file__).parent.parent / "results"
    results_dir.mkdir(exist_ok=True)

    if args.mode in ("anomaly", "all"):
        print("[1/3] 이상 거래 탐지...")
        latest = loader.get_latest()
        stocks = latest.get("rising_stocks", []) + latest.get("volume_top", [])
        anomalies = run_anomaly_scan(stocks)
        for a in anomalies:
            send_message(format_anomaly_alert(a))
        with open(results_dir / "anomalies.json", "w", encoding="utf-8") as f:
            json.dump(anomalies, f, ensure_ascii=False, indent=2)

    if args.mode in ("smart_money", "all"):
        print("[2/3] 스마트 머니 분석...")
        latest = loader.get_latest()
        all_stocks = latest.get("rising_stocks", [])
        smart_money_results = []
        for stock in all_stocks:
            score = calculate_smart_money_score(stock)
            if score >= 70:
                smart_money_results.append({**stock, "smart_money_score": score})
        smart_money_results.sort(key=lambda x: x["smart_money_score"], reverse=True)
        with open(results_dir / "smart_money.json", "w", encoding="utf-8") as f:
            json.dump(smart_money_results, f, ensure_ascii=False, indent=2)

    if args.mode in ("sector", "all"):
        print("[3/3] 섹터 자금 흐름...")
        latest = loader.get_latest()
        stocks = latest.get("rising_stocks", []) + latest.get("falling_stocks", [])
        sectors = aggregate_by_sector(stocks)
        send_message(format_sector_flow(sectors))
        with open(results_dir / "sector_flow.json", "w", encoding="utf-8") as f:
            json.dump(sectors, f, ensure_ascii=False, indent=2)

    print("Phase 2 완료.")


if __name__ == "__main__":
    main()
