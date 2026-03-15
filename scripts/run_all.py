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
    # 시장 지표 추가
    macro = loader.get_macro()
    perf_latest = loader.get_latest()
    fg = macro.get("fear_greed", {})
    vix_d = macro.get("vix", {})
    fg_score = fg.get("score", 50)
    regime = "극단적 공포" if fg_score < 25 else "공포" if fg_score < 45 else "중립" if fg_score < 55 else "탐욕" if fg_score < 75 else "극단적 탐욕"
    report["current_regime"] = regime
    report["fear_greed"] = {"score": round(fg_score, 1), "rating": fg.get("rating", "")}
    report["vix"] = {"current": vix_d.get("current", 0), "rating": vix_d.get("rating", "")}
    report["kospi"] = perf_latest.get("kospi_index", {})
    report["kosdaq"] = perf_latest.get("kosdaq_index", {})
    # 신호 분포
    combined_data = loader.get_combined_signals()
    if isinstance(combined_data, list):
        signal_counts = {}
        for s in combined_data:
            sig = s.get("signal", s.get("combined_signal", s.get("vision_signal", "중립")))
            signal_counts[sig] = signal_counts.get(sig, 0) + 1
        signal_counts["total"] = len(combined_data)
        report["by_source"]["combined"] = signal_counts
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
    # 실제 데이터 구조: rising.kospi/kosdaq, volume.kospi/kosdaq, falling.kospi/kosdaq
    rising = latest.get("rising", {})
    rising_stocks = rising.get("kospi", []) + rising.get("kosdaq", [])
    volume_data = latest.get("volume", {})
    volume_stocks = volume_data.get("kospi", []) + volume_data.get("kosdaq", [])
    falling = latest.get("falling", {})
    falling_stocks = falling.get("kospi", []) + falling.get("kosdaq", [])

    stocks = rising_stocks + volume_stocks
    anomalies = run_anomaly_scan(stocks)
    with open(results_dir / "anomalies.json", "w", encoding="utf-8") as f:
        json.dump(anomalies, f, ensure_ascii=False, indent=2)

    all_stocks = rising_stocks
    smart_money_results = []
    for stock in all_stocks:
        score = calculate_smart_money_score(stock)
        if score >= 70:
            smart_money_results.append({**stock, "smart_money_score": score})
    smart_money_results.sort(key=lambda x: x["smart_money_score"], reverse=True)
    with open(results_dir / "smart_money.json", "w", encoding="utf-8") as f:
        json.dump(smart_money_results, f, ensure_ascii=False, indent=2)

    all_flow_stocks = rising_stocks + falling_stocks
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
        for leader in theme.get("leader_stocks", theme.get("leaders", [])):
            if leader.get("code"):
                leader_theme[leader["code"]] = theme.get("theme_name", theme.get("name", ""))

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
        name = theme.get("theme_name", theme.get("name", ""))
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

    # criteria_data 로드 (combined_analysis.json 원본에서)
    combined_raw = loader._load_json(loader.signal_path / "combined" / "combined_analysis.json")
    criteria_map = combined_raw.get("criteria_data", {}) if isinstance(combined_raw, dict) else {}
    investor_data = latest.get("investor_data", {})

    # 시장 심리 온도계
    macro = loader.get_macro()
    fg = macro.get("fear_greed", {})
    vix_data = macro.get("vix", {})
    kospi_data = latest.get("kospi_index", loader.get_market_status() if hasattr(loader, 'get_market_status') else {})
    sentiment_score = calculate_sentiment(
        fg.get("score", 50), vix_data.get("current", 20), kospi_data, 0, 50, 0, 0
    )
    sentiment_info = classify_sentiment(sentiment_score)
    sentiment_result = {
        "score": sentiment_score,
        "label": sentiment_info["label"],
        "strategy": sentiment_info["strategy"],
        "components": {
            "fear_greed": {"value": round(fg.get("score", 0), 1)},
            "vix": {"value": vix_data.get("current", 0)},
        }
    }
    with open(results_dir / "sentiment.json", "w", encoding="utf-8") as f:
        json.dump(sentiment_result, f, ensure_ascii=False, indent=2)

    # 갭 분석 — change_rate > 5%를 갭으로 처리
    all_rising = rising_stocks
    gap_results = []
    for s in all_rising:
        change = s.get("change_rate", 0)
        if abs(change) >= 5:
            gap_results.append({
                "code": s.get("code", ""),
                "name": s.get("name", ""),
                "gap_pct": round(change, 2),
                "direction": "상승 갭" if change > 0 else "하락 갭",
                "volume_rate": s.get("volume_rate", 100),
                "fill_probability": round(max(30, min(85, 70 - abs(change) * 2)), 0),
            })
    gap_results.sort(key=lambda x: abs(x["gap_pct"]), reverse=True)
    with open(results_dir / "gap_analysis.json", "w", encoding="utf-8") as f:
        json.dump(gap_results[:10], f, ensure_ascii=False, indent=2)

    # 밸류에이션 — criteria_data 기반
    val_results = []
    for sig in combined:
        code = sig.get("code", "")
        crit = criteria_map.get(code, {}) if criteria_map else {}
        mc = crit.get("market_cap_range", {}) if isinstance(crit, dict) else {}
        ma = crit.get("ma_alignment", {}) if isinstance(crit, dict) else {}
        mc_met = mc.get("met", False) if isinstance(mc, dict) else False
        ma_met = ma.get("met", False) if isinstance(ma, dict) else False
        if not mc_met:
            continue
        score = 50
        if ma_met:
            score += 25
        signal = sig.get("vision_signal", "")
        if signal in ("매수", "적극매수"):
            score += 15
        inv = investor_data.get(code, {})
        fn = inv.get("foreign_net", 0) if isinstance(inv, dict) else 0
        if fn > 0:
            score += 10
        val_results.append({
            "code": code, "name": sig.get("name", ""),
            "signal": signal, "ma_aligned": ma_met,
            "market_cap_ok": True, "foreign_net": fn,
            "value_score": min(score, 99),
        })
    val_results.sort(key=lambda x: x.get("value_score", 0), reverse=True)
    with open(results_dir / "valuation.json", "w", encoding="utf-8") as f:
        json.dump(val_results[:15], f, ensure_ascii=False, indent=2)

    # 거래량-가격 괴리 — volume_rate vs change_rate 매핑
    div_results = []
    all_vol = volume_stocks + rising_stocks
    for s in all_vol:
        vol_rate = s.get("volume_rate", 100)
        change = s.get("change_rate", 0)
        # 거래량 급증 + 가격 부진 or 거래량 없는 급등
        if vol_rate > 300 and change < 3:
            div_results.append({
                "code": s.get("code", ""), "name": s.get("name", ""),
                "volume_change": round(vol_rate, 1), "price_change": round(change, 1),
                "type": "거래량 급증 · 가격 부진", "interpretation": "매도 압력 또는 세력 매집",
            })
        elif vol_rate < 80 and change > 8:
            div_results.append({
                "code": s.get("code", ""), "name": s.get("name", ""),
                "volume_change": round(vol_rate, 1), "price_change": round(change, 1),
                "type": "거래량 없는 급등", "interpretation": "매도 물량 고갈 주의",
            })
    with open(results_dir / "volume_divergence.json", "w", encoding="utf-8") as f:
        json.dump(div_results[:10], f, ensure_ascii=False, indent=2)

    # 프리마켓
    premarket_report = build_premarket_report(macro, {}, [])
    with open(results_dir / "premarket.json", "w", encoding="utf-8") as f:
        json.dump(premarket_report, f, ensure_ascii=False, indent=2)

    # 역발상 시그널 — criteria_data 기반
    squeeze_results = []
    for sig in combined:
        code = sig.get("code", "")
        crit = criteria_map.get(code, {})
        inv = investor_data.get(code, {})
        foreign_net = inv.get("foreign_net", 0) if isinstance(inv, dict) else 0
        overheating = crit.get("overheating_alert", {}) if isinstance(crit, dict) else {}
        supply = crit.get("supply_demand", {}) if isinstance(crit, dict) else {}
        is_oh = overheating.get("met", False) if isinstance(overheating, dict) else False
        has_supply = supply.get("met", False) if isinstance(supply, dict) else False

        score = 0
        if is_oh and foreign_net > 0:
            score = min(95, 50 + int(foreign_net / 50000))
        elif has_supply and foreign_net > 100000:
            score = min(90, 40 + int(foreign_net / 80000))

        if score > 30:
            squeeze_results.append({
                "code": code, "name": sig.get("name", ""),
                "signal": sig.get("vision_signal", ""),
                "foreign_net": foreign_net,
                "overheating": overheating.get("reason", "")[:50] if isinstance(overheating, dict) else "",
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
