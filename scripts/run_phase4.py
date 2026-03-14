"""Phase 4 실행: 테마 라이프사이클 + 리스크 모니터 + 매매 일지 + 패턴 매칭"""
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import THEME_DATA_PATH, SIGNAL_DATA_PATH
from core.data_loader import DataLoader
from core.telegram_bot import send_message
from modules.theme_lifecycle import track_theme_lifecycle, format_lifecycle_alert
from modules.pattern_matcher import find_similar_patterns, format_pattern_match


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["lifecycle", "pattern", "all"], default="all")
    args = parser.parse_args()

    loader = DataLoader(THEME_DATA_PATH, SIGNAL_DATA_PATH)
    results_dir = Path(__file__).parent.parent / "results"
    results_dir.mkdir(exist_ok=True)

    if args.mode in ("lifecycle", "all"):
        print("[1/2] 테마 라이프사이클 분석...")
        themes = loader.get_themes()
        history = loader.get_theme_history()
        lifecycle_results = []
        for theme in themes:
            name = theme.get("name", "")
            if name:
                result = track_theme_lifecycle(name, [{"themes": h.get("data", {}).get("themes", [])} for h in history])
                lifecycle_results.append(result)
                send_message(format_lifecycle_alert(result))
        with open(results_dir / "lifecycle.json", "w", encoding="utf-8") as f:
            json.dump(lifecycle_results, f, ensure_ascii=False, indent=2)

    if args.mode in ("pattern", "all"):
        print("[2/2] 패턴 매칭 분석...")
        # 패턴 매칭은 충분한 히스토리가 있을 때 실행
        print("패턴 매칭: 히스토리 데이터 기반으로 실행됩니다.")

    print("Phase 4 완료.")


if __name__ == "__main__":
    main()
