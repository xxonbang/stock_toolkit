"""Phase 1 실행: 크로스 시그널 + 모닝/이브닝 브리핑 + 성과 리포트"""
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import THEME_DATA_PATH, SIGNAL_DATA_PATH
from core.data_loader import DataLoader
from core.gemini_client import GeminiClient
from core.telegram_bot import send_message
from modules.cross_signal import run as run_cross_signal
from modules.daily_briefing import generate_morning_brief, generate_evening_review
from modules.system_performance import build_performance_report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["morning", "evening", "cross", "performance", "all"], default="all")
    args = parser.parse_args()

    loader = DataLoader(THEME_DATA_PATH, SIGNAL_DATA_PATH)
    gemini = GeminiClient()

    if args.mode in ("cross", "all"):
        print("[1/4] 크로스 시그널 분석...")
        run_cross_signal(loader, send_message)

    if args.mode in ("morning", "all"):
        print("[2/4] 모닝 브리프 생성...")
        brief = generate_morning_brief(gemini, loader)
        send_message(brief)

    if args.mode in ("evening", "all"):
        print("[3/4] 이브닝 리뷰 생성...")
        review = generate_evening_review(gemini, loader)
        send_message(review)

    if args.mode in ("performance", "all"):
        print("[4/4] 시스템 성과 리포트...")
        report = build_performance_report(loader)
        results_dir = Path(__file__).parent.parent / "results"
        results_dir.mkdir(exist_ok=True)
        with open(results_dir / "performance.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("성과 리포트 저장: results/performance.json")

    print("Phase 1 완료.")


if __name__ == "__main__":
    main()
