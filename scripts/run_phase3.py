"""Phase 3 실행: 뉴스 임팩트 + 시나리오 시뮬레이터"""
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import THEME_DATA_PATH, SIGNAL_DATA_PATH
from core.data_loader import DataLoader
from modules.news_impact import build_impact_database, calculate_impact_stats
from modules.scenario_simulator import parse_strategy, simulate_strategy, format_simulation_result
from core.telegram_bot import send_message


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["news", "simulate", "all"], default="all")
    parser.add_argument("--strategy", type=str, default=None, help="시뮬레이션 전략 (예: 'signal=적극매수 hold=5')")
    args = parser.parse_args()

    loader = DataLoader(THEME_DATA_PATH, SIGNAL_DATA_PATH)
    results_dir = Path(__file__).parent.parent / "results"
    results_dir.mkdir(exist_ok=True)

    if args.mode in ("news", "all"):
        print("[1/2] 뉴스 임팩트 DB 구축...")
        history = loader.get_theme_history()
        db = build_impact_database(history)
        stats = {}
        for news_type, impacts in db.items():
            stats[news_type] = calculate_impact_stats(impacts)
        with open(results_dir / "news_impact.json", "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        print(f"뉴스 임팩트 DB 저장: {len(stats)}개 유형")

    if args.mode in ("simulate", "all"):
        print("[2/2] 시나리오 시뮬레이션...")
        history = loader.get_theme_history()
        strategies = [
            "signal=적극매수 hold=5",
            "signal=적극매수 hold=5 stop=-5",
            "signal=매수 hold=5",
        ]
        if args.strategy:
            strategies = [args.strategy]
        results = []
        for s_str in strategies:
            s = parse_strategy(s_str)
            result = simulate_strategy(history, s)
            results.append(result)
            print(f"  {s_str}: {result['total_trades']}건, 승률 {result['win_rate']}%")
        with open(results_dir / "simulation.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    print("Phase 3 완료.")


if __name__ == "__main__":
    main()
