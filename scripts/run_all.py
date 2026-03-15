"""전체 모듈 실행 (Phase 1~4)"""
import sys
import json
import shutil
import argparse
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
from modules.pattern_matcher import find_similar_patterns
from modules.scenario_simulator import parse_strategy, simulate_strategy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full", "data-only"], default="full",
                        help="full: Gemini+텔레그램 포함, data-only: 데이터 갱신만")
    args = parser.parse_args()

    use_ai = args.mode == "full"

    loader = DataLoader(THEME_DATA_PATH, SIGNAL_DATA_PATH)
    results_dir = Path(__file__).parent.parent / "results"
    results_dir.mkdir(exist_ok=True)

    # Phase 1
    print("=== Phase 1: 알림 & 브리핑 ===")
    if use_ai:
        cross_matches = run_cross_signal(loader, send_message)
    else:
        themes = loader.get_themes()
        signals = loader.get_combined_signals()
        cross_matches = find_cross_signals(themes, signals)
    with open(results_dir / "cross_signal.json", "w", encoding="utf-8") as f:
        json.dump(cross_matches or [], f, ensure_ascii=False, indent=2)

    report = build_performance_report(loader)
    with open(results_dir / "performance.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 모닝 브리프 생성 (Gemini — full 모드만)
    if use_ai:
        try:
            gemini = GeminiClient()
            brief = generate_morning_brief(gemini, loader)
            with open(results_dir / "briefing.json", "w", encoding="utf-8") as f:
                json.dump({"morning": brief}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  브리핑 생성 실패: {e}")

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

    # 위험 종목 평가 + 스캐너 데이터
    risk_results = []
    scanner_stocks = []
    combined = loader.get_combined_signals()
    themes = loader.get_themes()
    leader_theme = {}
    for theme in themes:
        for leader in theme.get("leaders", []):
            if leader.get("code"):
                leader_theme[leader["code"]] = theme.get("name", "")

    for sig in combined:
        result = evaluate_risk(sig)
        if result["level"] != "낮음":
            risk_results.append(result)
        code = sig.get("code", "")
        signal = sig.get("signal", sig.get("combined_signal", sig.get("vision_signal", "")))
        foreign_net = sig.get("foreign_net", 0)
        scanner_stocks.append({
            "code": code,
            "name": sig.get("name", ""),
            "signal": signal,
            "confidence": round(sig.get("vision_confidence", 0) or 0, 2),
            "foreign_net": foreign_net,
            "foreign_flow": "순매수" if isinstance(foreign_net, (int, float)) and foreign_net > 0 else "순매도",
            "risk_level": result["level"],
            "warnings": result["warnings"],
            "theme": leader_theme.get(code, ""),
            "market": sig.get("market", ""),
        })

    risk_results.sort(key=lambda x: len(x.get("warnings", [])), reverse=True)
    with open(results_dir / "risk_monitor.json", "w", encoding="utf-8") as f:
        json.dump(risk_results, f, ensure_ascii=False, indent=2)
    with open(results_dir / "scanner_stocks.json", "w", encoding="utf-8") as f:
        json.dump(scanner_stocks, f, ensure_ascii=False, indent=2)

    # Phase 3
    print("=== Phase 3: 분석 ===")
    history = loader.get_theme_history()
    db = build_impact_database(history)
    stats = {k: calculate_impact_stats(v) for k, v in db.items()}
    with open(results_dir / "news_impact.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    # 시나리오 시뮬레이션 (기본 전략)
    print("  시나리오 시뮬레이션...")
    signal_history = loader.get_signal_history("vision")
    default_strategies = [
        "signal=매수 hold=5",
        "signal=적극매수 hold=5",
        "signal=매수 hold=5 stop=-3",
    ]
    sim_results = []
    for strat_str in default_strategies:
        strat = parse_strategy(strat_str)
        result = simulate_strategy(signal_history, strat)
        sim_results.append(result)
    with open(results_dir / "simulation.json", "w", encoding="utf-8") as f:
        json.dump(sim_results, f, ensure_ascii=False, indent=2)

    # 패턴 매칭 (교차 신호 상위 종목 대상)
    print("  패턴 매칭...")
    pattern_results = []
    intraday = loader.get_intraday_history()
    if intraday and cross_matches:
        for match in (cross_matches or [])[:5]:
            code = match.get("code", "")
            prices = intraday.get(code, {}).get("prices", [])
            if prices and len(prices) >= 5:
                similar = find_similar_patterns(prices[-20:], signal_history)
                if similar:
                    pattern_results.append({
                        "code": code,
                        "name": match.get("name", ""),
                        "matches": similar,
                    })
    with open(results_dir / "pattern.json", "w", encoding="utf-8") as f:
        json.dump(pattern_results, f, ensure_ascii=False, indent=2)

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

    # Phase 5: 신규 모듈
    print("=== Phase 5: 신규 분석 ===")
    from modules.sentiment_index import calculate_sentiment, classify_sentiment
    from modules.gap_analyzer import detect_gaps
    from modules.valuation_screener import calculate_value_score
    from modules.volume_price_divergence import detect_divergence
    from modules.premarket_monitor import build_premarket_report
    from modules.short_squeeze import calculate_squeeze_score

    # 시장 심리 온도계
    macro = loader.get_macro()
    fg = macro.get("fear_greed", {})
    vix_data = macro.get("vix", {})
    kospi_data = latest.get("kospi_index", loader.get_market_status() if hasattr(loader, 'get_market_status') else {})
    sentiment_score = calculate_sentiment(
        fg.get("score", 50), vix_data.get("current", 20), kospi_data, 0, 50, 0, 0
    )
    sentiment_label, sentiment_strategy = classify_sentiment(sentiment_score)
    sentiment_result = {
        "score": sentiment_score,
        "label": sentiment_label,
        "strategy": sentiment_strategy,
        "components": {
            "fear_greed": {"value": round(fg.get("score", 0), 1)},
            "vix": {"value": vix_data.get("current", 0)},
        }
    }
    with open(results_dir / "sentiment.json", "w", encoding="utf-8") as f:
        json.dump(sentiment_result, f, ensure_ascii=False, indent=2)

    # 갭 분석
    all_rising = latest.get("rising_stocks", [])
    gaps = detect_gaps(all_rising)
    with open(results_dir / "gap_analysis.json", "w", encoding="utf-8") as f:
        json.dump(gaps[:10], f, ensure_ascii=False, indent=2)

    # 밸류에이션
    val_results = []
    for sig in combined:
        score = calculate_value_score(sig)
        if score > 40:
            val_results.append({**sig, "value_score": score})
    val_results.sort(key=lambda x: x.get("value_score", 0), reverse=True)
    with open(results_dir / "valuation.json", "w", encoding="utf-8") as f:
        json.dump(val_results[:15], f, ensure_ascii=False, indent=2)

    # 거래량-가격 괴리
    div_results = []
    for s in all_rising:
        d = detect_divergence(s)
        if d.get("has_divergence"):
            div_results.append(d)
    with open(results_dir / "volume_divergence.json", "w", encoding="utf-8") as f:
        json.dump(div_results[:10], f, ensure_ascii=False, indent=2)

    # 프리마켓
    premarket_report = build_premarket_report(macro, {}, [])
    with open(results_dir / "premarket.json", "w", encoding="utf-8") as f:
        json.dump(premarket_report, f, ensure_ascii=False, indent=2)

    # 역발상 시그널
    squeeze_results = []
    for sig in combined:
        score = calculate_squeeze_score(sig)
        if score > 30:
            squeeze_results.append({
                "code": sig.get("code", ""),
                "name": sig.get("name", ""),
                "signal": sig.get("vision_signal", ""),
                "squeeze_score": score,
            })
    squeeze_results.sort(key=lambda x: x.get("squeeze_score", 0), reverse=True)
    with open(results_dir / "short_squeeze.json", "w", encoding="utf-8") as f:
        json.dump(squeeze_results[:10], f, ensure_ascii=False, indent=2)

    # 프론트엔드 데이터 복사
    frontend_data = Path(__file__).parent.parent / "frontend" / "public" / "data"
    frontend_data.mkdir(parents=True, exist_ok=True)
    for json_file in results_dir.glob("*.json"):
        shutil.copy2(json_file, frontend_data / json_file.name)

    print(f"=== 전체 완료 (mode={args.mode}) ===")


if __name__ == "__main__":
    main()
