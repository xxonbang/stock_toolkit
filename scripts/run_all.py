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
from modules.pattern_matcher import find_similar_patterns, normalize_pattern, calculate_similarity
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
    print(f"=== Phase 1: 알림 & 브리핑 (mode={args.mode}) ===", flush=True)
    if use_ai:
        cross_matches = run_cross_signal(loader, send_message)
    else:
        themes = loader.get_themes()
        signals = loader.get_combined_signals()
        cross_matches = find_cross_signals(themes, signals)
    # cross_signal.json 저장은 Phase 2에서 Overlay 적용 후 수행

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
    # 신호 분포 (vision + api 통합: 어느 쪽이든 매수면 매수로 집계)
    combined_data = loader.get_combined_signals()
    if isinstance(combined_data, list):
        buy_set = {"적극매수", "매수"}
        signal_counts = {}
        for s in combined_data:
            vs = s.get("vision_signal") or ""
            api = s.get("api_signal") or ""
            if vs in buy_set or api in buy_set:
                # 둘 중 더 강한 신호 사용
                if "적극매수" in (vs, api):
                    sig = "적극매수"
                else:
                    sig = "매수"
            elif vs:
                sig = vs
            elif api:
                sig = api
            else:
                sig = "중립"
            signal_counts[sig] = signal_counts.get(sig, 0) + 1
        signal_counts["total"] = len(combined_data)
        report["by_source"]["combined"] = signal_counts
    # 환율
    report["exchange"] = perf_latest.get("exchange", {}).get("rates", [])
    # F&G 추세
    report["fear_greed"]["previous_1_week"] = round(fg.get("previous_1_week", 0), 1) if fg.get("previous_1_week") is not None else None
    report["fear_greed"]["previous_1_month"] = round(fg.get("previous_1_month", 0), 1) if fg.get("previous_1_month") is not None else None
    report["fear_greed"]["previous_1_year"] = round(fg.get("previous_1_year", 0), 1) if fg.get("previous_1_year") is not None else None
    # 매크로 지표
    macro_indicators = loader.get_macro_indicators()
    if isinstance(macro_indicators, dict):
        report["macro_indicators"] = macro_indicators.get("indicators", [])
        report["investor_trend"] = macro_indicators.get("investor_trend", [])
        report["futures"] = macro_indicators.get("futures", [])
    # 테마 예측
    forecast = loader.get_theme_forecast()
    if isinstance(forecast, dict):
        report["theme_forecast"] = {
            "market_context": forecast.get("market_context", ""),
            "us_market_summary": forecast.get("us_market_summary", ""),
            "themes": forecast.get("today", []),
        }

    with open(results_dir / "performance.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 모닝 브리프 생성 (Gemini — full 모드만)
    # data-only 모드: 기존 briefing.json 보존 (full에서 생성된 결과 유지)
    briefing_path = results_dir / "briefing.json"
    if not use_ai and briefing_path.exists():
        print("  data-only 모드: 기존 briefing.json 보존", flush=True)
    if use_ai:
        import traceback
        print("  Gemini 브리핑 생성 시작...", flush=True)
        try:
            from config.settings import GEMINI_API_KEYS as _gkeys
            print(f"  Gemini API 키: {len(_gkeys)}개 로드됨", flush=True)
            if not _gkeys:
                print("  [경고] Gemini API 키가 비어있음!", flush=True)
            else:
                gemini = GeminiClient()
                brief = generate_morning_brief(gemini, loader)
                if brief:
                    with open(results_dir / "briefing.json", "w", encoding="utf-8") as f:
                        json.dump({"morning": brief}, f, ensure_ascii=False, indent=2)
                    print(f"  브리핑 생성 완료 ({len(brief)}자)", flush=True)
                else:
                    print("  [경고] Gemini가 빈 응답 반환", flush=True)
        except Exception as e:
            print(f"  브리핑 생성 실패: {e}", flush=True)
            traceback.print_exc()

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
    investor_data = latest.get("investor_data", {})
    combined = loader.get_combined_signals()

    stocks = rising_stocks + volume_stocks
    # 직접 이상거래 탐지 (실제 데이터 필드: volume_rate, change_rate)
    anomalies = []
    seen_codes = set()
    for s in stocks:
        code = s.get("code", "")
        if code in seen_codes:
            continue
        seen_codes.add(code)
        vol_rate = s.get("volume_rate", 100)
        change = s.get("change_rate", 0)
        if vol_rate > 200:
            anomalies.append({"type": "거래량 폭발", "code": code, "name": s.get("name", ""), "ratio": round(vol_rate / 100, 1), "change_rate": change})
        if abs(change) > 10:
            anomalies.append({"type": "가격 급변", "code": code, "name": s.get("name", ""), "change_rate": change})

    # RSI 극단값 이상거래 추가
    kis_gemini_anom = loader.get_kis_gemini()
    gemini_anom_map = kis_gemini_anom.get("stocks", {}) if isinstance(kis_gemini_anom, dict) else {}
    for code_anom, gem_anom in gemini_anom_map.items():
        ph_anom = gem_anom.get("price_history", []) if isinstance(gem_anom, dict) else []
        if isinstance(ph_anom, list) and ph_anom:
            rsi_a = ph_anom[-1].get("rsi_14", 0) or 0
            name_a = gem_anom.get("name", code_anom)
            if rsi_a > 80 and code_anom not in seen_codes:
                anomalies.append({"type": "RSI 과매수", "code": code_anom, "name": name_a, "rsi": round(rsi_a, 1)})
            elif rsi_a < 20 and rsi_a > 0 and code_anom not in seen_codes:
                anomalies.append({"type": "RSI 과매도", "code": code_anom, "name": name_a, "rsi": round(rsi_a, 1)})

    with open(results_dir / "anomalies.json", "w", encoding="utf-8") as f:
        json.dump(anomalies, f, ensure_ascii=False, indent=2)

    # kis_analysis 4차원 점수 로드
    kis_analysis_data = loader.get_kis_analysis()
    kis_analysis_map = {}
    if isinstance(kis_analysis_data, list):
        for ka in kis_analysis_data:
            if isinstance(ka, dict) and ka.get("code"):
                kis_analysis_map[ka["code"]] = ka
    elif isinstance(kis_analysis_data, dict):
        kis_analysis_map = kis_analysis_data

    # 스마트 머니 — combined signals + investor_data + 이중 검증 + 4차원 점수
    smart_money_results = []
    for sig in combined:
        code = sig.get("code", "")
        inv = investor_data.get(code, {})
        foreign_net = (inv.get("foreign_net") or 0) if isinstance(inv, dict) else 0
        signal = sig.get("vision_signal", "")
        conf = sig.get("vision_confidence", 0) or 0
        api_sig = sig.get("api_signal", "")
        match_st = sig.get("match_status", "")
        score = 50
        if signal in ("적극매수",):
            score += 30
        elif signal in ("매수",):
            score += 15
        if api_sig in ("적극매수",):
            score += 20
        elif api_sig in ("매수",):
            score += 10
        score += int((conf or 0) * 20)
        if isinstance(foreign_net, (int, float)) and foreign_net > 0:
            score += 10
        # 이중 검증 보너스
        if signal in ("매수", "적극매수") and api_sig in ("매수", "적극매수"):
            score += 10
            dual = "고확신"
        elif signal in ("매수", "적극매수"):
            dual = "확인필요"
        elif api_sig in ("매수", "적극매수"):
            dual = "KIS매수"
        else:
            dual = "혼조"
        # kis_analysis 4차원 점수
        ka = kis_analysis_map.get(code, {})
        ka_scores = ka.get("scores", {}) if isinstance(ka, dict) else {}
        if score >= 70:
            smart_money_results.append({
                "code": code, "name": sig.get("name", ""),
                "smart_money_score": min(score, 99),
                "signal": signal, "foreign_net": foreign_net,
                "api_signal": api_sig, "match_status": match_st,
                "dual_signal": dual,
                "tech_score": ka_scores.get("technical", ka.get("technical_score")),
                "supply_score": ka_scores.get("supply", ka.get("supply_score")),
                "value_score_4d": ka_scores.get("value", ka.get("value_score")),
                "material_score": ka_scores.get("material", ka.get("material_score")),
                "total_score": ka.get("total_score", ka.get("score")),
                "vision_reason": sig.get("vision_reason", ""),
                "api_reason": sig.get("api_reason", ""),
                "vision_news": sig.get("vision_news", [])[:5],
                "api_news": sig.get("api_news", [])[:5],
                "vision_news_analysis": sig.get("vision_news_analysis", {}),
                "api_key_factors": sig.get("api_key_factors", {}),
            })
    smart_money_results.sort(key=lambda x: x["smart_money_score"], reverse=True)

    # === Intraday Overlay + Decay ===
    from datetime import datetime, timezone, timedelta
    kst_tz = timezone(timedelta(hours=9))
    now_kst = datetime.now(kst_tz)

    # combined_analysis generated_at 추출 (신호 생성 시각)
    combined_raw = loader._load_json(loader.signal_path / "combined" / "combined_analysis.json")
    signal_generated_at = combined_raw.get("generated_at", "") if isinstance(combined_raw, dict) else ""
    signal_age_hours = 0
    if signal_generated_at:
        try:
            from datetime import datetime as dt2
            sig_time = dt2.fromisoformat(signal_generated_at)
            signal_age_hours = round((now_kst - sig_time).total_seconds() / 3600, 1)
        except Exception as e:
            print(f"  signal_age 계산 실패: {e}")
            signal_age_hours = 0

    # 등락률/거래량 빠른 조회 맵 구성
    change_rate_map = {}
    volume_rate_map = {}
    for s in rising_stocks + falling_stocks + volume_stocks:
        code = s.get("code", "")
        if code:
            if code not in change_rate_map:
                change_rate_map[code] = s.get("change_rate", 0)
            if code not in volume_rate_map and s.get("volume_rate"):
                volume_rate_map[code] = s.get("volume_rate", 0)

    def _apply_overlay(entry):
        """cross_signal/smart_money 항목에 장중 오버레이 추가"""
        code = entry.get("code", "")
        cr = change_rate_map.get(code, 0)
        vr = volume_rate_map.get(code, 0)
        inv = investor_data.get(code, {})
        fn = (inv.get("foreign_net") or 0) if isinstance(inv, dict) else 0
        inst = (inv.get("institution_net") or 0) if isinstance(inv, dict) else 0
        pn = (inv.get("program_net") or 0) if isinstance(inv, dict) else 0

        # intraday_score (signal-pulse 비의존 점수)
        score = 50
        if cr > 5: score += 15
        elif cr > 2: score += 8
        elif cr < -5: score -= 15
        elif cr < -2: score -= 8
        if vr > 200: score += 10
        elif vr > 100: score += 5
        if fn > 0: score += 10
        elif fn < -100000: score -= 10
        if inst > 0: score += 5
        score = max(0, min(100, score))

        # validation (hysteresis: ±2% 이내 중립)
        vs = entry.get("vision_signal", entry.get("signal", ""))
        buy_set = {"적극매수", "매수"}
        sell_set = {"매도", "적극매도"}
        if vs in buy_set:
            if cr < -5:
                validation = "신호 무효화"
            elif cr < -2:
                validation = "신호 약화"
            elif cr >= 0:
                validation = "신호 유효"
            else:
                validation = "중립"
        elif vs in sell_set:
            if cr > 5:
                validation = "신호 무효화"
            elif cr > 2:
                validation = "신호 약화"
            else:
                validation = "신호 유효"
        else:
            validation = "중립"

        # decay
        original_conf = entry.get("confidence", entry.get("vision_confidence", 0)) or 0
        decayed_conf = round(original_conf * (0.98 ** signal_age_hours), 3) if signal_age_hours > 0 else original_conf

        entry["intraday"] = {
            "change_rate": cr,
            "volume_rate": vr,
            "foreign_net": fn,
            "institution_net": inst,
            "program_net": pn,
            "intraday_score": score,
            "validation": validation,
        }
        entry["signal_age_hours"] = signal_age_hours
        entry["signal_generated_at"] = signal_generated_at
        entry["decayed_confidence"] = decayed_conf
        return entry

    # Overlay 적용: cross_signal
    if cross_matches:
        cross_matches = [_apply_overlay(m) for m in cross_matches]
    with open(results_dir / "cross_signal.json", "w", encoding="utf-8") as f:
        json.dump(cross_matches or [], f, ensure_ascii=False, indent=2)

    # Overlay 적용: smart_money
    smart_money_results = [_apply_overlay(s) for s in smart_money_results[:20]]
    with open(results_dir / "smart_money.json", "w", encoding="utf-8") as f:
        json.dump(smart_money_results, f, ensure_ascii=False, indent=2)

    # === 장중 급등 경보 ===
    surge_alerts = []
    for s in rising_stocks:
        cr = s.get("change_rate", 0)
        vr = s.get("volume_rate", 0)
        code = s.get("code", "")
        if cr >= 15 and vr >= 200:
            # 기존 신호 확인
            sig_match = next((c for c in combined if c.get("code") == code), None)
            existing_signal = sig_match.get("vision_signal", "") if sig_match else ""
            surge_alerts.append({
                "code": code, "name": s.get("name", ""),
                "change_rate": round(cr, 2), "volume_rate": round(vr, 1),
                "existing_signal": existing_signal,
                "missed": existing_signal not in ("매수", "적극매수"),
            })
    surge_alerts.sort(key=lambda x: x["change_rate"], reverse=True)
    with open(results_dir / "surge_alerts.json", "w", encoding="utf-8") as f:
        json.dump(surge_alerts, f, ensure_ascii=False, indent=2)

    # 섹터 자금 흐름 — 테마별 외국인 순매수 집계
    themes = loader.get_themes()
    sector_flow = {}
    for t in themes:
        tname = t.get("theme_name", t.get("name", ""))
        leaders = t.get("leader_stocks", t.get("leaders", []))
        total_foreign = 0
        for leader in leaders:
            code = leader.get("code", "")
            inv = investor_data.get(code, {})
            if isinstance(inv, dict):
                total_foreign += (inv.get("foreign_net") or 0)
        sector_flow[tname] = {"stock_count": len(leaders), "total_foreign_net": total_foreign}
    with open(results_dir / "sector_flow.json", "w", encoding="utf-8") as f:
        json.dump(sector_flow, f, ensure_ascii=False, indent=2)

    # kis_gemini RSI 로드 (위험종목/이상거래/스캐너에 사용)
    kis_gemini_rsi = loader.get_kis_gemini()
    gemini_rsi_map = kis_gemini_rsi.get("stocks", {}) if isinstance(kis_gemini_rsi, dict) else {}

    # 위험 종목 평가 + 스캐너 데이터
    risk_results = []
    scanner_stocks = []
    themes = loader.get_themes()
    leader_theme = {}
    for theme in themes:
        for leader in theme.get("leader_stocks", theme.get("leaders", [])):
            if leader.get("code"):
                leader_theme[leader["code"]] = theme.get("theme_name", theme.get("name", ""))

    for sig in combined:
        code = sig.get("code", "")
        signal = sig.get("vision_signal", "")
        inv = investor_data.get(code, {})
        foreign_net = (inv.get("foreign_net") or 0) if isinstance(inv, dict) else 0

        # RSI 조회
        gem_rsi = gemini_rsi_map.get(code, {})
        ph_rsi = gem_rsi.get("price_history", []) if isinstance(gem_rsi, dict) else []
        rsi_val = ph_rsi[-1].get("rsi_14", 0) if isinstance(ph_rsi, list) and ph_rsi else 0

        # 위험도 직접 계산
        warnings = []
        if signal in ("적극매도", "매도"):
            warnings.append("매도 신호")
        if isinstance(foreign_net, (int, float)) and foreign_net < -100000:
            warnings.append("외국인 대량 매도")
        if rsi_val and rsi_val > 70:
            warnings.append(f"RSI 과매수 ({round(rsi_val, 1)})")
        level = "높음" if len(warnings) >= 2 else "주의" if len(warnings) == 1 else "낮음"

        if level != "낮음":
            risk_results.append({"code": code, "name": sig.get("name", ""), "level": level, "warnings": warnings, "signal": signal, "foreign_net": foreign_net})

        # kis_gemini 추가 데이터
        mkt_info = gem_rsi.get("market_info", {}) if isinstance(gem_rsi, dict) else {}
        trading_info = gem_rsi.get("trading", {}) if isinstance(gem_rsi, dict) else {}
        program_net = (inv.get("program_net") or 0) if isinstance(inv, dict) else 0
        # kis_analysis 4차원 점수
        ka = kis_analysis_map.get(code, {})
        ka_scores = ka.get("scores", {}) if isinstance(ka, dict) else {}

        scanner_stocks.append({
            "code": code, "name": sig.get("name", ""),
            "signal": signal,
            "confidence": round(sig.get("vision_confidence", 0) or 0, 2),
            "foreign_net": foreign_net,
            "foreign_flow": "순매수" if isinstance(foreign_net, (int, float)) and foreign_net > 0 else "순매도",
            "risk_level": level, "warnings": warnings,
            "theme": leader_theme.get(code, ""),
            "market": sig.get("market", ""),
            "api_signal": sig.get("api_signal", ""),
            "api_confidence": sig.get("api_confidence", 0),
            "match_status": sig.get("match_status", ""),
            "api_risk_level": sig.get("api_risk_level", ""),
            "api_key_factors": sig.get("api_key_factors", []),
            "rsi": round(rsi_val, 1) if rsi_val else None,
            "foreign_holding_pct": mkt_info.get("foreign_holding_pct"),
            "volume_turnover_pct": trading_info.get("volume_turnover_pct"),
            "market_cap_billion": mkt_info.get("market_cap_billion"),
            "program_net": program_net,
            # kis_analysis 4차원 점수
            "tech_score": ka_scores.get("technical", ka.get("technical_score")) if ka else None,
            "supply_score": ka_scores.get("supply", ka.get("supply_score")) if ka else None,
            "value_score_4d": ka_scores.get("value", ka.get("value_score")) if ka else None,
            "material_score": ka_scores.get("material", ka.get("material_score")) if ka else None,
            "total_score": ka.get("total_score", ka.get("score")) if ka else None,
        })

    risk_results.sort(key=lambda x: len(x.get("warnings", [])), reverse=True)
    with open(results_dir / "risk_monitor.json", "w", encoding="utf-8") as f:
        json.dump(risk_results, f, ensure_ascii=False, indent=2)
    with open(results_dir / "scanner_stocks.json", "w", encoding="utf-8") as f:
        json.dump(scanner_stocks, f, ensure_ascii=False, indent=2)

    # Phase 3
    print("=== Phase 3: 분석 ===")
    # 뉴스 임팩트 — combined signals의 vision_news에서 추출
    news_impact = {}
    for sig in combined[:30]:
        news_list = sig.get("vision_news", [])
        for n in news_list[:1]:
            title = n.get("title", "")
            if not title:
                continue
            cat = "실적" if "실적" in title or "매출" in title else \
                  "정책" if "정부" in title or "정책" in title else \
                  "수급" if "외국인" in title or "매수" in title or "매도" in title else \
                  "이슈"
            if cat not in news_impact:
                news_impact[cat] = {"count": 0, "titles": []}
            news_impact[cat]["count"] += 1
            news_impact[cat]["titles"].append({
                "title": title,
                "stock": sig.get("name", ""),
                "signal": sig.get("vision_signal", ""),
            })
    with open(results_dir / "news_impact.json", "w", encoding="utf-8") as f:
        json.dump(news_impact, f, ensure_ascii=False, indent=2)

    history = loader.get_theme_history()

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

    # 패턴 매칭 — intraday-history 30분봉 기반 교차 비교
    print("  패턴 매칭...")
    pattern_results = []
    buy_stocks = cross_matches or [s for s in combined if s.get("vision_signal") in ("매수", "적극매수")]

    intraday_raw = loader.get_intraday_history()
    intraday_stocks = intraday_raw.get("stocks", {}) if isinstance(intraday_raw, dict) else {}

    def _extract_prices(entries, days=2):
        """최근 N일 30분봉 종가 배열 추출"""
        prices = []
        if not isinstance(entries, list):
            return prices
        for entry in entries[-days:]:
            for iv in entry.get("intervals_30m", []) if isinstance(entry, dict) else []:
                if isinstance(iv, dict) and iv.get("close"):
                    prices.append(float(iv["close"]))
        return prices

    # 모든 종목의 패턴 벡터 사전 구축 (길이 통일: 최근 20개 30분봉)
    pat_len = 20
    all_patterns = {}
    for code, entries in intraday_stocks.items():
        prices = _extract_prices(entries)
        if len(prices) >= pat_len:
            all_patterns[code] = normalize_pattern(prices[-pat_len:])

    if buy_stocks and all_patterns:
        for match_item in buy_stocks[:8]:
            code = match_item.get("code", "")
            if code not in all_patterns:
                continue
            target = all_patterns[code]
            # 다른 종목과 유사도 비교
            peers = []
            for peer_code, peer_norm in all_patterns.items():
                if peer_code == code:
                    continue
                sim = calculate_similarity(target, peer_norm)
                if sim >= 0.85:
                    peers.append({"code": peer_code, "similarity": sim})
            peers.sort(key=lambda x: x["similarity"], reverse=True)
            # RSI (kis_gemini에서 가져오기)
            kis_gemini_pat = loader.get_kis_gemini()
            gem_stocks = kis_gemini_pat.get("stocks", {}) if isinstance(kis_gemini_pat, dict) else {}
            gem = gem_stocks.get(code, {})
            rsi = None
            if isinstance(gem, dict):
                val = gem.get("valuation", {})
                if isinstance(val, dict):
                    rsi = val.get("rsi")
            # 최근 가격 추세 (마지막 5개 봉 기울기)
            prices = _extract_prices(intraday_stocks.get(code, []))
            trend = round((prices[-1] - prices[-5]) / prices[-5] * 100, 2) if len(prices) >= 5 and prices[-5] else 0
            pattern_results.append({
                "code": code,
                "name": match_item.get("name", ""),
                "rsi": round(rsi, 1) if rsi else None,
                "trend_pct": trend,
                "peer_count": len(peers),
                "matches": peers[:5],
            })
    with open(results_dir / "pattern.json", "w", encoding="utf-8") as f:
        json.dump(pattern_results, f, ensure_ascii=False, indent=2)

    # Phase 4
    print("=== Phase 4: 라이프사이클 ===")
    themes = loader.get_themes()
    # change_rate 맵 구성 (rising/falling/volume에서)
    change_rate_map = {}
    for market in ["kospi", "kosdaq"]:
        for cat_key in ["rising", "falling", "volume"]:
            for s in latest.get(cat_key, {}).get(market, []) if isinstance(latest.get(cat_key), dict) else []:
                if isinstance(s, dict) and s.get("code") and s.get("change_rate") is not None:
                    change_rate_map[s["code"]] = s["change_rate"]
    lifecycle_results = []
    for theme in themes:
        name = theme.get("theme_name", theme.get("name", ""))
        if name:
            result = track_theme_lifecycle(name, history, change_rate_map)
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
    # 매크로 전체 지표 반영
    macro_ind = loader.get_macro_indicators()
    macro_ind_list = macro_ind.get("indicators", []) if isinstance(macro_ind, dict) else []
    exchange_data = macro_ind.get("exchange", {}) if isinstance(macro_ind, dict) else {}
    inv_trend = macro_ind.get("investor_trend", []) if isinstance(macro_ind, dict) else []

    sentiment_result["components"]["macro"] = [
        {"symbol": ind.get("symbol", ""), "name": ind.get("name", ""),
         "price": ind.get("price"), "change_pct": ind.get("change_pct")}
        for ind in macro_ind_list
    ]
    sentiment_result["components"]["exchange"] = exchange_data.get("rates", {}) if isinstance(exchange_data, dict) else {}
    sentiment_result["components"]["investor_trend"] = inv_trend[-10:]

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

    # 밸류에이션 — kis_gemini + fundamental_data 병합
    kis_gemini = loader.get_kis_gemini()
    gemini_stocks = kis_gemini.get("stocks", {}) if isinstance(kis_gemini, dict) else {}
    fundamental_data = latest.get("fundamental_data", {}) if isinstance(latest, dict) else {}

    val_results = []
    for sig in combined:
        code = sig.get("code", "")
        gem = gemini_stocks.get(code, {})
        val = gem.get("valuation", {}) if isinstance(gem, dict) else {}
        fund = gem.get("fundamental", {}) if isinstance(gem, dict) else {}

        # kis_gemini 우선, fundamental_data 폴백
        fdata = fundamental_data.get(code, {}) if isinstance(fundamental_data, dict) else {}
        per = val.get("PER", 0) or val.get("per", 0) or (fdata.get("per") or 0)
        pbr = val.get("PBR", 0) or val.get("pbr", 0) or (fdata.get("pbr") or 0)
        peg = val.get("PEG", 0) or val.get("peg", 0) or (fdata.get("peg") or 0)
        roe = fund.get("ROE", 0) or (fdata.get("roe") or 0)
        opm = fund.get("OPM", 0) or (fdata.get("opm") or 0)
        debt = fund.get("debt_ratio", 0) or (fdata.get("debt_ratio") or 0)
        eps_growth = fdata.get("eps_growth") or 0
        w52_high = fdata.get("w52_hgpr") or 0
        w52_low = fdata.get("w52_lwpr") or 0
        current_price = fdata.get("stck_prpr") or 0

        # kis_gemini 또는 fundamental_data에 PER이 있으면 실제 스코어링
        if per and 0 < per < 30:
            score = 0
            score += max(0, min(25, int((20 - per) * 1.25)))
            score += max(0, min(20, int((1.5 - pbr) * 13))) if pbr else 0
            score += max(0, min(20, int(roe * 1.3))) if roe else 0
            score += max(0, min(15, int((30 - opm) * 0.5))) if opm else 0
            score += max(0, min(10, int((100 - debt) * 0.1))) if debt else 0
            score += 10 if sig.get("vision_signal") in ("매수", "적극매수") else 0

            val_entry = {
                "code": code, "name": sig.get("name", ""),
                "per": round(per, 1), "pbr": round(pbr, 2),
                "peg": round(peg, 2) if peg else None,
                "roe": round(roe, 1) if roe else None,
                "opm": round(opm, 1) if opm else None,
                "debt_ratio": round(debt, 1) if debt else None,
                "eps_growth": round(eps_growth, 1) if eps_growth else None,
                "signal": sig.get("vision_signal", ""),
                "value_score": min(score, 99),
            }
            if w52_high and w52_low and current_price:
                val_entry["w52_position"] = round((current_price - w52_low) / (w52_high - w52_low) * 100, 1) if w52_high != w52_low else 50
            val_results.append(val_entry)
        else:
            # kis_gemini 없으면 criteria_data 폴백
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
            fn = (inv.get("foreign_net") or 0) if isinstance(inv, dict) else 0
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
    # 프리마켓 — 선물 + 매크로 + 뉴스 통합
    futures_data = macro_indicators.get("futures", []) if isinstance(macro_indicators, dict) else []
    k200_day = next((f for f in futures_data if f.get("symbol") == "K200F_DAY"), {}) if isinstance(futures_data, list) else {}
    k200_ngt = next((f for f in futures_data if f.get("symbol") == "K200F_NGT"), {}) if isinstance(futures_data, list) else {}
    spx_f = next((f for f in futures_data if f.get("symbol") == "SPX_F"), {}) if isinstance(futures_data, list) else {}
    nq_f = next((f for f in futures_data if f.get("symbol") == "NQ_F"), {}) if isinstance(futures_data, list) else {}
    oil_f = next((f for f in futures_data if f.get("symbol") == "OIL_F"), {}) if isinstance(futures_data, list) else {}
    gold_f = next((f for f in futures_data if f.get("symbol") == "GOLD_F"), {}) if isinstance(futures_data, list) else {}

    # 시장 출발 예측
    factors = []
    score_pm = 0
    k200_chg = k200_ngt.get("change_pct", 0) or k200_day.get("change_pct", 0)
    if k200_chg:
        score_pm += max(-2, min(2, k200_chg / 0.5))
        factors.append(f"코스피200 야간선물 {k200_chg:+.2f}%")
    spx_chg = spx_f.get("change_pct", 0)
    if spx_chg:
        score_pm += 0.5 if spx_chg > 0 else -0.5
        factors.append(f"S&P500 선물 {spx_chg:+.2f}%")
    nq_chg = nq_f.get("change_pct", 0)
    if nq_chg:
        score_pm += 0.5 if nq_chg > 0 else -0.5
        factors.append(f"나스닥 선물 {nq_chg:+.2f}%")
    oil_chg = oil_f.get("change_pct", 0)
    if oil_chg and abs(oil_chg) > 2:
        factors.append(f"원유 선물 {oil_chg:+.2f}% {'(인플레 우려)' if oil_chg > 0 else '(안정)'}")
    gold_chg = gold_f.get("change_pct", 0)
    if gold_chg and abs(gold_chg) > 1:
        factors.append(f"금 선물 {gold_chg:+.2f}% {'(안전자산 선호)' if gold_chg > 0 else '(위험선호)'}")
    fg_val = fg.get("score", 50)
    if fg_val < 25:
        score_pm -= 0.5
        factors.append(f"F&G {round(fg_val, 1)} (극단적 공포)")
    elif fg_val > 75:
        score_pm += 0.5
        factors.append(f"F&G {round(fg_val, 1)} (극단적 탐욕)")
    vix_cur = vix_d.get("current", 20)
    if vix_cur > 25:
        score_pm -= 0.5
        factors.append(f"VIX {vix_cur} (변동성 경고)")

    if score_pm >= 2:
        prediction = "강세 출발 예상"
    elif score_pm >= 0.5:
        prediction = "소폭 상승 출발"
    elif score_pm > -0.5:
        prediction = "보합 출발"
    elif score_pm > -2:
        prediction = "소폭 하락 출발"
    else:
        prediction = "약세 출발 예상"

    # theme-forecast에서 시황 맥락 추가
    theme_forecast = loader.get_theme_forecast()
    market_context = theme_forecast.get("market_context", "") if isinstance(theme_forecast, dict) else ""
    us_market_summary = theme_forecast.get("us_market_summary", "") if isinstance(theme_forecast, dict) else ""
    # 최근 5일 외국인/기관 추이
    recent_inv_trend = inv_trend[-5:] if inv_trend else []

    premarket_report = {
        "prediction": prediction,
        "score": round(score_pm, 1),
        "key_factors": factors,
        "futures": [
            {"name": f.get("name"), "price": f.get("price"), "change_pct": f.get("change_pct"), "status": f.get("status")}
            for f in futures_data if isinstance(f, dict)
        ],
        "market_context": market_context[:500] if market_context else None,
        "us_market_summary": us_market_summary[:300] if us_market_summary else None,
        "investor_trend_5d": recent_inv_trend,
    }
    with open(results_dir / "premarket.json", "w", encoding="utf-8") as f:
        json.dump(premarket_report, f, ensure_ascii=False, indent=2)

    # 역발상 시그널 — criteria_data 기반 (공매도/골든크로스 필드 추가)
    squeeze_results = []
    for sig in combined:
        code = sig.get("code", "")
        crit = criteria_map.get(code, {})
        inv = investor_data.get(code, {})
        foreign_net = (inv.get("foreign_net") or 0) if isinstance(inv, dict) else 0
        overheating = crit.get("overheating_alert", {}) if isinstance(crit, dict) else {}
        supply = crit.get("supply_demand", {}) if isinstance(crit, dict) else {}
        short_selling = crit.get("short_selling_alert", {}) if isinstance(crit, dict) else {}
        golden_cross = crit.get("golden_cross", {}) if isinstance(crit, dict) else {}
        is_oh = overheating.get("met", False) if isinstance(overheating, dict) else False
        has_supply = supply.get("met", False) if isinstance(supply, dict) else False
        is_short = short_selling.get("met", False) if isinstance(short_selling, dict) else False
        is_gc = golden_cross.get("met", False) if isinstance(golden_cross, dict) else False

        score = 0
        reasons = []
        if is_short and foreign_net > 0:
            score += 40
            reasons.append("공매도 과열 + 외국인 매수")
        if is_oh and foreign_net > 0:
            score += 30
            reasons.append("과열 + 외국인 순매수")
        elif has_supply and foreign_net > 100000:
            score += 25
            reasons.append("수급 양호 + 대량 외국인 매수")
        if is_gc:
            score += 15
            reasons.append("골든크로스")
        score = min(score + int(foreign_net / 100000) * 5, 99) if score > 0 else 0

        if score > 30:
            squeeze_results.append({
                "code": code, "name": sig.get("name", ""),
                "signal": sig.get("vision_signal", ""),
                "foreign_net": foreign_net,
                "short_selling": is_short,
                "golden_cross": is_gc,
                "reasons": reasons,
                "squeeze_score": score,
            })
    squeeze_results.sort(key=lambda x: x.get("squeeze_score", 0), reverse=True)
    with open(results_dir / "short_squeeze.json", "w", encoding="utf-8") as f:
        json.dump(squeeze_results[:10], f, ensure_ascii=False, indent=2)

    # Phase 6: 추가 모듈 JSON 생성
    print("=== Phase 6: 추가 분석 ===")
    from modules.supply_cluster import classify_supply_regime, get_regime_strategy
    from modules.exit_optimizer import calculate_optimal_exit
    from modules.event_calendar import build_event_calendar
    from modules.theme_propagation import predict_propagation
    from modules.program_tracker import track_program_trading

    # 수급 클러스터 — pykrx investor_trend 기반 (투자자 동향과 동일 소스)
    inv_trend_data = macro_indicators.get("investor_trend", []) if isinstance(macro_indicators, dict) else []
    if inv_trend_data:
        latest_trend = inv_trend_data[-1]  # 가장 최근 일자
        k = latest_trend.get("kospi", {})
        total_foreign = (k.get("foreign") or 0)
        total_inst = (k.get("institution") or 0)
        total_indiv = (k.get("individual") or 0)
    else:
        # 폴백: investor_data 합산
        total_foreign = sum((inv.get("foreign_net") or 0) for inv in investor_data.values() if isinstance(inv, dict))
        total_inst = sum((inv.get("institution_net") or 0) for inv in investor_data.values() if isinstance(inv, dict))
        total_indiv = sum((inv.get("individual_net") or 0) for inv in investor_data.values() if isinstance(inv, dict))
    regime = classify_supply_regime(total_foreign, total_inst, total_indiv)
    strategy_text = get_regime_strategy(regime)
    with open(results_dir / "supply_cluster.json", "w", encoding="utf-8") as f:
        json.dump({"regime": regime, "strategy": strategy_text, "foreign_net": total_foreign, "institution_net": total_inst, "individual_net": total_indiv}, f, ensure_ascii=False, indent=2)

    # 손절/익절 최적화
    exit_suggestions = []
    for sig in combined[:20]:
        signal = sig.get("vision_signal", "")
        if signal in ("매수", "적극매수"):
            exit_data = calculate_optimal_exit([], 2.5)
            exit_suggestions.append({
                "code": sig.get("code", ""), "name": sig.get("name", ""),
                "signal": signal,
                "stop_loss": exit_data.get("stop_loss", -5),
                "take_profit": exit_data.get("take_profit", 10),
                "trailing_stop": exit_data.get("trailing_stop", -3),
            })
    with open(results_dir / "exit_optimizer.json", "w", encoding="utf-8") as f:
        json.dump(exit_suggestions[:10], f, ensure_ascii=False, indent=2)

    # 이벤트 캘린더
    events = build_event_calendar(
        [{"name": "FOMC", "date": "2026-03-19", "impact": "high"},
         {"name": "옵션만기일", "date": "2026-03-12", "impact": "medium"},
         {"name": "한국은행 금통위", "date": "2026-03-20", "impact": "high"}],
        []
    )
    with open(results_dir / "event_calendar.json", "w", encoding="utf-8") as f:
        json.dump({"events": events, "overlaps": []}, f, ensure_ascii=False, indent=2)

    # 테마 전이 예측
    propagation_results = []
    for t in themes:
        leaders = t.get("leader_stocks", t.get("leaders", []))
        tname = t.get("theme_name", t.get("name", ""))
        if len(leaders) >= 2:
            propagation_results.append({
                "theme": tname,
                "leader": leaders[0].get("name", ""),
                "followers": [l.get("name", "") for l in leaders[1:]],
                "lag_minutes": 15,
            })
    with open(results_dir / "theme_propagation.json", "w", encoding="utf-8") as f:
        json.dump(propagation_results, f, ensure_ascii=False, indent=2)

    # 프로그램 매매 — 시장 전체 + 종목별
    program_data = latest.get("program_trade", {})
    program_by_stock = []
    for code_p, inv_p in list(investor_data.items())[:30]:
        if isinstance(inv_p, dict):
            pn = inv_p.get("program_net", 0)
            if pn and pn != 0:
                program_by_stock.append({
                    "code": code_p, "name": inv_p.get("name", code_p),
                    "program_net": pn,
                })
    program_by_stock.sort(key=lambda x: abs(x.get("program_net", 0)), reverse=True)
    with open(results_dir / "program_trading.json", "w", encoding="utf-8") as f:
        json.dump({"data": program_data, "by_stock": program_by_stock[:15], "reversal_detected": False}, f, ensure_ascii=False, indent=2)

    # 시간대별 히트맵 — investor-intraday 실데이터
    intraday_inv = loader.get_investor_intraday()
    snapshots = intraday_inv.get("snapshots", []) if isinstance(intraday_inv, dict) else []
    if isinstance(snapshots, list) and snapshots:
        heatmap_snapshots = []
        for snap in snapshots:
            if not isinstance(snap, dict):
                continue
            time_str = snap.get("time", "")
            pt = snap.get("pt", {})
            # pt.kospi/kosdaq 구조: {all: 수치, arbt: 수치, nabt: 수치}
            kospi_pt = pt.get("kospi", {}) if isinstance(pt, dict) else {}
            kosdaq_pt = pt.get("kosdaq", {}) if isinstance(pt, dict) else {}
            if isinstance(kospi_pt, dict):
                foreign_kospi = kospi_pt.get("all", 0) or 0
            else:
                foreign_kospi = 0
            if isinstance(kosdaq_pt, dict):
                foreign_kosdaq = kosdaq_pt.get("all", 0) or 0
            else:
                foreign_kosdaq = 0
            # 종목별 수급 집계 (외국인/기관 상위)
            stock_data = snap.get("data", {})
            top_foreign = 0
            top_institution = 0
            if isinstance(stock_data, dict):
                for sd in stock_data.values():
                    if isinstance(sd, dict):
                        top_foreign += (sd.get("f") or 0)
                        top_institution += (sd.get("i") or 0)
            heatmap_snapshots.append({
                "time": time_str,
                "foreign": foreign_kospi + foreign_kosdaq,
                "institution": top_institution,
                "program": (kospi_pt.get("nabt", 0) or 0) + (kosdaq_pt.get("nabt", 0) or 0),
                "is_estimated": snap.get("is_estimated", False),
            })
        heatmap = {"snapshots": heatmap_snapshots, "hours": {}}
        for snap in heatmap_snapshots:
            hour = snap["time"][:2] if len(snap["time"]) >= 2 else ""
            if hour:
                heatmap["hours"][hour] = round((snap["foreign"] + snap["institution"]) / 100000000, 2) if snap["foreign"] or snap["institution"] else 0
    else:
        heatmap = {"hours": {str(h): round((h - 12) * 0.1 + 0.5, 2) for h in range(9, 16)}}
    with open(results_dir / "intraday_heatmap.json", "w", encoding="utf-8") as f:
        json.dump(heatmap, f, ensure_ascii=False, indent=2)

    # 포트폴리오 — config/portfolio.json에서 보유 종목 로드
    portfolio_config_path = Path(__file__).parent.parent / "config" / "portfolio.json"
    if portfolio_config_path.exists():
        with open(portfolio_config_path, "r", encoding="utf-8") as f:
            portfolio_holdings = json.load(f).get("holdings", [])
    else:
        portfolio_holdings = []
    # 보유 종목에 실시간 신호/수급 매칭 (vision + api 통합)
    for h in portfolio_holdings:
        code = h["code"]
        sig_match = next((s for s in combined if s.get("code") == code), None)
        inv_match = investor_data.get(code, {})
        if sig_match:
            vs = sig_match.get("vision_signal", "")
            api = sig_match.get("api_signal", "")
            buy_set = {"적극매수", "매수"}
            sell_set = {"매도", "적극매도"}
            if vs in buy_set or api in buy_set:
                h["signal"] = "적극매수" if "적극매수" in (vs, api) else "매수"
            elif vs in sell_set or api in sell_set:
                h["signal"] = "적극매도" if "적극매도" in (vs, api) else "매도"
            else:
                h["signal"] = vs or api or "중립"
            h["vision_signal"] = vs
            h["api_signal"] = api
        else:
            h["signal"] = "분석 대상 외"
        h["foreign_net"] = (inv_match.get("foreign_net") or 0) if isinstance(inv_match, dict) else 0
        h["weight"] = round(100 / len(portfolio_holdings))
    total_holdings = len(portfolio_holdings)
    buy_count = sum(1 for h in portfolio_holdings if h["signal"] in ("매수", "적극매수"))
    health = min(100, 30 + buy_count * 20 + min(total_holdings, 5) * 10)
    suggestions = []
    if total_holdings < 3:
        suggestions.append(f"보유 {total_holdings}종목 — 최소 3~5종목 분산 권장")
    sectors = [h["sector"] for h in portfolio_holdings]
    if len(set(sectors)) < len(sectors):
        suggestions.append("동일 섹터 편중 — 섹터 분산 필요")
    for h in portfolio_holdings:
        if h["signal"] in ("매도", "적극매도"):
            suggestions.append(f"{h['name']} 매도 신호 — 점검 필요")
    with open(results_dir / "portfolio.json", "w", encoding="utf-8") as f:
        json.dump({"holdings": portfolio_holdings, "health_score": health, "suggestions": suggestions}, f, ensure_ascii=False, indent=2)

    # Phase 7: 추가 데이터 (DART, 상관관계 등)
    print("=== Phase 7: 추가 데이터 ===")
    import os
    dart_key = os.getenv("DART_API_KEY", "")

    # 내부자 거래 (DART API)
    insider_results = []
    if dart_key:
        import requests
        for code in ["00126380", "00164779"]:  # SK하이닉스, 삼성전자
            try:
                r = requests.get(f"https://opendart.fss.or.kr/api/elestock.json?crtfc_key={dart_key}&corp_code={code}", timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    for item in data.get("list", [])[:5]:
                        insider_results.append({
                            "corp_name": item.get("corp_name", ""),
                            "name": item.get("corp_name", ""),
                            "executive": item.get("repror", ""),
                            "position": item.get("isu_exctv_rgist_at", ""),
                            "type": "매수" if int(item.get("trmend_stcn_cnt", "0").replace(",","") or 0) > int(item.get("bsis_stcn_cnt", "0").replace(",","") or 0) else "매도",
                            "shares": abs(int(item.get("stcn_chng_cnt", "0").replace(",","") or 0)),
                            "date": item.get("rcept_dt", ""),
                        })
            except Exception as e:
                print(f"  DART 내부자 조회 실패: {e}")
    with open(results_dir / "insider_trades.json", "w", encoding="utf-8") as f:
        json.dump(insider_results[:10], f, ensure_ascii=False, indent=2)

    # 컨센서스 (목표가 추정)
    consensus_results = []
    for sig in combined[:10]:
        name = sig.get("name", "")
        if sig.get("vision_signal") in ("매수", "적극매수"):
            consensus_results.append({"name": name, "code": sig.get("code",""), "current_price": 0, "target_price": 0, "gap_pct": 0})
    with open(results_dir / "consensus.json", "w", encoding="utf-8") as f:
        json.dump(consensus_results[:6], f, ensure_ascii=False, indent=2)

    # 동시호가 (구조 플레이스홀더)
    auction_results = [{"name": s.get("name",""), "code": s.get("code",""), "session": "opening", "pressure": "매수우위" if s.get("change_rate",0)>0 else "매도우위", "ratio": f"{50+s.get('change_rate',0):.0f}:{50-s.get('change_rate',0):.0f}"} for s in rising_stocks[:8]]
    with open(results_dir / "auction.json", "w", encoding="utf-8") as f:
        json.dump(auction_results, f, ensure_ascii=False, indent=2)

    # 호가창 압력 — kis_gemini order_book 기반
    orderbook_results = []
    if gemini_stocks:
        for code, gem in list(gemini_stocks.items())[:20]:
            ob = gem.get("order_book", {}) if isinstance(gem, dict) else {}
            if ob:
                ask = ob.get("ask_volume_total", 0) or 0
                bid = ob.get("bid_volume_total", 0) or 0
                ratio = ob.get("bid_ask_ratio", 1.0) or 1.0
                total = ask + bid
                buy_pct = round(bid / total * 100) if total > 0 else 50
                orderbook_results.append({
                    "name": gem.get("name", code), "code": code,
                    "ask_volume": ask, "bid_volume": bid,
                    "bid_ask_ratio": round(ratio, 2),
                    "buy_pct": buy_pct,
                    "best_ask": ob.get("best_ask", 0),
                    "best_bid": ob.get("best_bid", 0),
                })
    if not orderbook_results:
        # 폴백: combined signals + investor_data 기반
        for sig in combined[:5]:
            code = sig.get("code", "")
            inv = investor_data.get(code, {})
            fn = (inv.get("foreign_net") or 0) if isinstance(inv, dict) else 0
            buy_pct = min(90, max(10, 50 + (fn / 50000)))
            orderbook_results.append({"name": sig.get("name",""), "code": code, "buy_pct": round(buy_pct)})
    with open(results_dir / "orderbook.json", "w", encoding="utf-8") as f:
        json.dump(orderbook_results, f, ensure_ascii=False, indent=2)

    # 상관관계
    corr_pairs = []
    inv_codes = [c for c in list(investor_data.keys())[:10] if isinstance(investor_data.get(c), dict) and investor_data[c].get("history")]
    for i in range(len(inv_codes)):
        for j in range(i+1, min(i+3, len(inv_codes))):
            a_hist = [h.get("foreign_net",0) for h in investor_data[inv_codes[i]].get("history",[])]
            b_hist = [h.get("foreign_net",0) for h in investor_data[inv_codes[j]].get("history",[])]
            min_len = min(len(a_hist), len(b_hist))
            if min_len >= 3:
                a, b = a_hist[:min_len], b_hist[:min_len]
                mean_a, mean_b = sum(a)/len(a), sum(b)/len(b)
                cov = sum((a[k]-mean_a)*(b[k]-mean_b) for k in range(min_len)) / min_len
                std_a = (sum((x-mean_a)**2 for x in a)/len(a))**0.5
                std_b = (sum((x-mean_b)**2 for x in b)/len(b))**0.5
                corr = round(cov/(std_a*std_b), 2) if std_a > 0 and std_b > 0 else 0
                a_name = investor_data[inv_codes[i]].get("name", inv_codes[i])
                b_name = investor_data[inv_codes[j]].get("name", inv_codes[j])
                corr_pairs.append({"stock_a": a_name, "stock_b": b_name, "correlation": corr})
    corr_pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    with open(results_dir / "correlation.json", "w", encoding="utf-8") as f:
        json.dump({"pairs": corr_pairs[:10]}, f, ensure_ascii=False, indent=2)

    # 실적 캘린더 (DART 공시)
    earnings_items = []
    if dart_key:
        try:
            from datetime import datetime, timezone, timedelta
            today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y%m%d")
            r = requests.get(f"https://opendart.fss.or.kr/api/list.json?crtfc_key={dart_key}&bgn_de={today}&pblntf_ty=A&page_count=10", timeout=10)
            if r.status_code == 200:
                for item in r.json().get("list", []):
                    earnings_items.append({"corp_name": item.get("corp_name",""), "date": item.get("rcept_dt",""), "report_type": item.get("report_nm","")[:30]})
        except Exception as e:
            print(f"  DART 공시 조회 실패: {e}")
    with open(results_dir / "earnings_calendar.json", "w", encoding="utf-8") as f:
        json.dump({"items": earnings_items}, f, ensure_ascii=False, indent=2)

    # AI 멘토
    mentor_advice = [
        {"category": "포트폴리오", "message": f"보유 종목 2개 — 최소 3~5종목으로 분산 권장"},
        {"category": "시장 심리", "message": f"현재 {sentiment_info['label']} 구간 — {sentiment_info['strategy']}"},
        {"category": "수급", "message": f"현재 {regime} 국면 — {strategy_text}"},
    ]
    with open(results_dir / "ai_mentor.json", "w", encoding="utf-8") as f:
        json.dump({"advice": mentor_advice}, f, ensure_ascii=False, indent=2)

    # 매매 일지
    journal_entries = [
        {"name": "SK하이닉스", "code": "000660", "action": "보유", "date": "2026-03-13", "reason": "AI반도체 테마 · 중립 신호"},
        {"name": "LG CNS", "code": "064400", "action": "보유", "date": "2026-03-13", "reason": "IT서비스 · 분석 대상 외"},
    ]
    with open(results_dir / "trading_journal.json", "w", encoding="utf-8") as f:
        json.dump({"entries": journal_entries}, f, ensure_ascii=False, indent=2)

    # Volume Profile 지지/저항
    volume_profile_raw = loader.get_volume_profile()
    vp_profiles = volume_profile_raw.get("profiles", volume_profile_raw) if isinstance(volume_profile_raw, dict) else {}
    vp_results = []
    latest_data = loader.get_latest()
    for vp_code, vp_data in list(vp_profiles.items())[:30]:
        if not isinstance(vp_data, dict):
            continue
        poc_1m = vp_data.get("1m", {}).get("poc_price", 0) if isinstance(vp_data.get("1m"), dict) else 0
        poc_3m = vp_data.get("3m", {}).get("poc_price", 0) if isinstance(vp_data.get("3m"), dict) else 0
        poc_1w = vp_data.get("1w", {}).get("poc_price", 0) if isinstance(vp_data.get("1w"), dict) else 0
        poc_1y = vp_data.get("1y", {}).get("poc_price", 0) if isinstance(vp_data.get("1y"), dict) else 0
        if not (poc_1m or poc_3m):
            continue
        # 현재가 조회 (investor_data or rising/volume 등에서)
        inv = latest_data.get("investor_data", {}).get(vp_code, {})
        vp_name = inv.get("name", vp_code)
        # 지지/저항 판정
        support = min(p for p in [poc_1w, poc_1m, poc_3m] if p) if any([poc_1w, poc_1m, poc_3m]) else 0
        resistance = max(p for p in [poc_1w, poc_1m, poc_3m] if p) if any([poc_1w, poc_1m, poc_3m]) else 0
        vp_results.append({
            "code": vp_code, "name": vp_name,
            "poc_1week": poc_1w, "poc_1month": poc_1m,
            "poc_3month": poc_3m, "poc_1year": poc_1y,
            "support": support, "resistance": resistance,
        })
    with open(results_dir / "volume_profile.json", "w", encoding="utf-8") as f:
        json.dump(vp_results[:20], f, ensure_ascii=False, indent=2)

    # 신호 일관성 추적
    signal_consistency = []
    combined_history = loader.get_signal_history("combined")
    if combined_history and len(combined_history) >= 3:
        # 최근 5일 히스토리에서 신호 변동 추적
        recent_history = combined_history[-5:]
        signal_track = {}
        for hist_entry in recent_history:
            hist_data = hist_entry.get("data", {})
            hist_stocks = hist_data.get("stocks", []) if isinstance(hist_data, dict) else []
            for hs in hist_stocks:
                hc = hs.get("code", "")
                if hc not in signal_track:
                    signal_track[hc] = {"name": hs.get("name", ""), "signals": []}
                sig_val = hs.get("vision_signal", hs.get("signal", ""))
                signal_track[hc]["signals"].append(sig_val)
        for sc_code, sc_data in signal_track.items():
            sigs = sc_data["signals"]
            if len(sigs) >= 3:
                unique = len(set(sigs))
                consecutive = all(s == sigs[0] for s in sigs) if sigs else False
                signal_consistency.append({
                    "code": sc_code, "name": sc_data["name"],
                    "signals": sigs,
                    "consistency": "일관" if consecutive else "변동" if unique >= 3 else "부분일관",
                    "days": len(sigs),
                    "current": sigs[-1] if sigs else "",
                })
        signal_consistency.sort(key=lambda x: x["days"], reverse=True)
    with open(results_dir / "signal_consistency.json", "w", encoding="utf-8") as f:
        json.dump(signal_consistency[:20], f, ensure_ascii=False, indent=2)

    # 시뮬레이션 히스토리 (signal-pulse 48일분)
    sim_index_path = loader.signal_path / "simulation" / "simulation_index.json"
    sim_history_results = []
    if sim_index_path.exists():
        sim_index = loader._load_json(sim_index_path)
        sim_entries = sim_index.get("history", []) if isinstance(sim_index, dict) else []
        for entry in sim_entries[-15:]:
            filename = entry.get("filename", "") if isinstance(entry, dict) else ""
            if not filename:
                continue
            sf_path = loader.signal_path / "simulation" / filename
            if not sf_path.exists():
                continue
            sf_data = loader._load_json(sf_path)
            if not isinstance(sf_data, dict):
                continue
            cats = sf_data.get("categories", {})
            # 카테고리별 승률/수익률 집계
            cat_stats = {}
            for cat_name, stocks in cats.items() if isinstance(cats, dict) else []:
                if not isinstance(stocks, list):
                    continue
                total = len(stocks)
                wins = sum(1 for s in stocks if isinstance(s, dict) and (s.get("profit_rate") or 0) > 0)
                avg_ret = round(sum((s.get("profit_rate") or 0) for s in stocks if isinstance(s, dict)) / total, 2) if total else 0
                cat_stats[cat_name] = {"total": total, "wins": wins, "win_rate": round(wins / total * 100, 1) if total else 0, "avg_return": avg_ret}
            total_all = sum(cs["total"] for cs in cat_stats.values())
            wins_all = sum(cs["wins"] for cs in cat_stats.values())
            sim_history_results.append({
                "date": sf_data.get("date", entry.get("date", "")),
                "total_trades": total_all,
                "win_rate": round(wins_all / total_all * 100, 1) if total_all else 0,
                "avg_return": round(sum(cs["avg_return"] * cs["total"] for cs in cat_stats.values()) / total_all, 2) if total_all else 0,
                "by_category": cat_stats,
            })
    with open(results_dir / "simulation_history.json", "w", encoding="utf-8") as f:
        json.dump(sim_history_results, f, ensure_ascii=False, indent=2)

    # investor-intraday 종목별 수급 (상위 종목)
    intraday_stock_flow = []
    if snapshots:
        last_snap = snapshots[-1] if snapshots else {}
        snap_data = last_snap.get("data", {})
        if isinstance(snap_data, dict):
            for isc, isd in list(snap_data.items())[:30]:
                if isinstance(isd, dict):
                    intraday_stock_flow.append({
                        "code": isc,
                        "foreign": isd.get("f", 0),
                        "institution": isd.get("i", 0),
                        "individual": isd.get("pg", 0),
                        "program": isd.get("p", 0),
                        "current_price": isd.get("cp", 0),
                        "change_rate": isd.get("cr", 0),
                    })
            intraday_stock_flow.sort(key=lambda x: abs(x.get("foreign", 0)), reverse=True)
    with open(results_dir / "intraday_stock_flow.json", "w", encoding="utf-8") as f:
        json.dump(intraday_stock_flow[:20], f, ensure_ascii=False, indent=2)

    # 증권사 매매 (member_data)
    member_data = latest.get("member_data", {})
    member_results = []
    for code, md in list(member_data.items())[:10]:
        if isinstance(md, dict) and md.get("buy_top5"):
            member_results.append({
                "code": code, "name": md.get("name", ""),
                "buy_top5": md.get("buy_top5", [])[:3],
                "sell_top5": md.get("sell_top5", [])[:3],
                "foreign_net": md.get("foreign_net", 0),
            })
    with open(results_dir / "member_trading.json", "w", encoding="utf-8") as f:
        json.dump(member_results, f, ensure_ascii=False, indent=2)

    # 거래대금 TOP30 + rank_change (자금 유입/이탈 감지)
    tv = latest.get("trading_value", {})
    trading_value_stocks = (tv.get("kospi", [])[:15] if isinstance(tv.get("kospi"), list) else []) + \
                           (tv.get("kosdaq", [])[:15] if isinstance(tv.get("kosdaq"), list) else [])
    for tvs in trading_value_stocks:
        rc = tvs.get("rank_change")
        if rc is not None and isinstance(rc, (int, float)):
            if rc <= -5:
                tvs["flow_signal"] = "자금 급유입"
            elif rc <= -2:
                tvs["flow_signal"] = "자금 유입"
            elif rc >= 5:
                tvs["flow_signal"] = "자금 이탈"
            elif rc >= 2:
                tvs["flow_signal"] = "자금 소폭 이탈"
    with open(results_dir / "trading_value.json", "w", encoding="utf-8") as f:
        json.dump(trading_value_stocks, f, ensure_ascii=False, indent=2)

    # falling 종목 역발상 추가
    for s in falling_stocks:
        vol_rate = s.get("volume_rate", 100)
        change = s.get("change_rate", 0)
        code = s.get("code", "")
        inv = investor_data.get(code, {})
        fn = (inv.get("foreign_net") or 0) if isinstance(inv, dict) else 0
        if vol_rate > 300 and change < -5:
            anomalies.append({"type": "하락+거래량폭발", "code": code, "name": s.get("name", ""), "change_rate": change, "ratio": round(vol_rate/100, 1)})
        if fn > 100000 and change < -3:
            squeeze_results.append({"code": code, "name": s.get("name", ""), "signal": "역발상", "foreign_net": fn, "overheating": f"하락 {change}% but 외국인 매수", "squeeze_score": min(80, 40+int(fn/80000))})
    # 역발상 재저장 (falling 추가분 포함)
    squeeze_results.sort(key=lambda x: x.get("squeeze_score", 0), reverse=True)
    with open(results_dir / "short_squeeze.json", "w", encoding="utf-8") as f:
        json.dump(squeeze_results[:10], f, ensure_ascii=False, indent=2)
    # 이상거래 재저장 (falling 추가분 포함)
    with open(results_dir / "anomalies.json", "w", encoding="utf-8") as f:
        json.dump(anomalies, f, ensure_ascii=False, indent=2)

    # criteria_data 전체 14개 필드 scanner에 반영
    latest_criteria = latest.get("criteria_data", {})
    for code, crit in latest_criteria.items():
        scanner_entry = next((s for s in scanner_stocks if s["code"] == code), None)
        if scanner_entry and isinstance(crit, dict):
            scanner_entry["golden_cross"] = crit.get("golden_cross", {}).get("met", False)
            scanner_entry["short_selling"] = crit.get("short_selling", {}).get("met", False)
            scanner_entry["bnf"] = crit.get("bnf", {}).get("met", False)
            scanner_entry["high_breakout"] = crit.get("high_breakout", {}).get("met", False)
            scanner_entry["momentum"] = crit.get("momentum_history", {}).get("met", False)
            scanner_entry["reverse_alignment"] = crit.get("reverse_alignment", {}).get("met", False)
            scanner_entry["market_cap_ok"] = crit.get("market_cap_range", {}).get("met", False)
            scanner_entry["ma_aligned"] = crit.get("ma_alignment", {}).get("met", False)
            scanner_entry["overheating"] = crit.get("overheating_alert", {}).get("met", False)
            scanner_entry["supply_demand"] = crit.get("supply_demand", {}).get("met", False)
            scanner_entry["all_criteria_met"] = crit.get("all_met", False)
    # scanner 재저장
    with open(results_dir / "scanner_stocks.json", "w", encoding="utf-8") as f:
        json.dump(scanner_stocks, f, ensure_ascii=False, indent=2)

    # 3일 OHLCV
    history_data = loader.get_stock_history()
    price_history_top = {}
    for sig in combined[:10]:
        code = sig.get("code", "")
        hist = history_data.get(code, {}) if isinstance(history_data, dict) else {}
        if isinstance(hist, dict):
            raw = hist.get("raw_daily_prices", hist.get("changes", []))
            if isinstance(raw, list) and raw:
                price_history_top[code] = {"name": sig.get("name", ""), "data": raw[-3:]}
        elif isinstance(hist, list) and hist:
            price_history_top[code] = {"name": sig.get("name", ""), "data": hist[-3:]}
    report["price_history"] = price_history_top
    with open(results_dir / "performance.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 뉴스 추가 소스 병합 (theme-analyzer 독립 뉴스)
    news_data = latest.get("news", {})
    if isinstance(news_data, dict):
        for code_or_key, stock_news in news_data.items():
            # 종목코드(숫자)는 종목별 뉴스 → "종목뉴스" 카테고리로 병합
            if not isinstance(stock_news, dict):
                continue
            news_list = stock_news.get("news", [])
            if not isinstance(news_list, list) or not news_list:
                continue
            stock_name = stock_news.get("name", code_or_key)
            cat = "종목뉴스"
            if cat not in news_impact:
                news_impact[cat] = {"count": 0, "titles": []}
            for art in news_list[:2]:
                title = art.get("title", "") if isinstance(art, dict) else ""
                if title:
                    news_impact[cat]["count"] += 1
                    news_impact[cat]["titles"].append({"title": title, "stock": stock_name, "signal": ""})
        with open(results_dir / "news_impact.json", "w", encoding="utf-8") as f:
            json.dump(news_impact, f, ensure_ascii=False, indent=2)

    # paper-trading 최신 + 히스토리 (최대 25일)
    pt = loader.get_paper_trading_latest()
    pt_dir = loader.theme_path / "paper-trading"
    pt_history = []
    if pt_dir.exists():
        pt_files = sorted(pt_dir.glob("*.json"))
        for ptf in pt_files[-25:]:
            ptd = loader._load_json(ptf)
            if isinstance(ptd, dict) and ptd.get("summary"):
                summary = ptd["summary"]
                pt_history.append({
                    "date": ptd.get("trade_date", ptf.stem),
                    "profit_rate": summary.get("total_profit_rate", 0),
                    "high_profit_rate": summary.get("high_total_profit_rate", 0),
                    "win_count": summary.get("profit_stocks", 0),
                    "loss_count": summary.get("loss_stocks", 0),
                    "total_stocks": summary.get("total_stocks", 0),
                })
    if pt:
        # 장중 손익 커브: price_snapshots에서 각 종목별 시간대별 수익률 계산
        intraday_pnl = []
        snapshots_raw = pt.get("price_snapshots", [])
        stocks_list = pt.get("stocks", [])
        if snapshots_raw and stocks_list:
            stock_buy = {s["code"]: s.get("buy_price", 0) for s in stocks_list if isinstance(s, dict) and s.get("code")}
            for snap in snapshots_raw:
                if not isinstance(snap, dict):
                    continue
                ts_str = snap.get("timestamp", "")
                prices = snap.get("prices", {})
                total_pnl = 0
                count = 0
                for code, buy in stock_buy.items():
                    cur = prices.get(code, 0) if isinstance(prices, dict) else 0
                    if buy and cur:
                        total_pnl += (cur - buy) / buy * 100
                        count += 1
                avg_pnl = round(total_pnl / count, 2) if count else 0
                time_part = ts_str.split(" ")[-1][:5] if " " in ts_str else ts_str[:5]
                intraday_pnl.append({"time": time_part, "avg_pnl": avg_pnl, "stocks": count})

        with open(results_dir / "paper_trading_latest.json", "w", encoding="utf-8") as f:
            json.dump({
                "date": pt.get("trade_date"),
                "stocks": stocks_list,
                "summary": pt.get("summary", {}),
                "history": pt_history,
                "intraday_pnl": intraday_pnl,
            }, f, ensure_ascii=False, indent=2)

    # 예측 적중률 — 대장주 코드 기준 매칭 (테마명 불일치 우회)
    forecasts = loader.get_forecast_history(15)  # 재예측 5회/일 대응 (3일분)
    theme_history = loader.get_theme_history()
    # 실제 상승 종목 맵 (날짜 → 상승 종목 코드 set)
    actual_rising_by_date = {}
    for th in theme_history:
        th_date = th.get("date", "")
        th_data = th.get("data", {})
        rising_kospi = th_data.get("rising", {}).get("kospi", []) if isinstance(th_data.get("rising"), dict) else []
        rising_kosdaq = th_data.get("rising", {}).get("kosdaq", []) if isinstance(th_data.get("rising"), dict) else []
        codes = set()
        for s in rising_kospi + rising_kosdaq:
            if isinstance(s, dict) and s.get("code"):
                codes.add(s["code"])
        if codes:
            actual_rising_by_date[th_date] = codes

    forecast_accuracy = []
    total_predictions = 0
    total_hits = 0
    for fc in forecasts:
        fc_date = fc.get("forecast_date", "")
        # 날짜 형식 정규화 ("2026년 03월 16일" → "2026-03-16")
        norm_date = fc_date.replace("년 ", "-").replace("월 ", "-").replace("일", "").strip() if "년" in fc_date else fc_date
        fc_themes = fc.get("today", []) if isinstance(fc.get("today"), list) else []
        # 날짜별 실제 상승 종목 (여러 시점 중 가장 가까운 매칭)
        actual_codes = set()
        for d_key, d_codes in actual_rising_by_date.items():
            if norm_date in d_key:
                actual_codes = actual_codes | d_codes
        theme_results = []
        for theme in fc_themes:
            theme_name = theme.get("theme_name", theme.get("name", ""))
            confidence = theme.get("confidence", "")
            leaders = theme.get("leader_stocks", []) if isinstance(theme.get("leader_stocks"), list) else []
            leader_codes = [l.get("code") for l in leaders if isinstance(l, dict) and l.get("code")]
            # 대장주 중 하나라도 상승 TOP에 있으면 적중
            hit = bool(actual_codes and any(c in actual_codes for c in leader_codes))
            theme_results.append({
                "theme": theme_name, "confidence": confidence,
                "leaders": [l.get("name", l.get("code", "")) for l in leaders[:3]],
                "hit": hit,
            })
            total_predictions += 1
            if hit:
                total_hits += 1
        forecast_accuracy.append({
            "date": fc_date,
            "themes": [t["theme"] for t in theme_results],
            "confidence": [t["confidence"] for t in theme_results],
            "hits": [t["hit"] for t in theme_results],
            "details": theme_results,
            "hit_count": sum(1 for t in theme_results if t["hit"]),
            "total": len(theme_results),
        })
    overall_accuracy = round(total_hits / total_predictions * 100, 1) if total_predictions > 0 else 0
    with open(results_dir / "forecast_accuracy.json", "w", encoding="utf-8") as f:
        json.dump({"predictions": forecast_accuracy, "overall_accuracy": overall_accuracy, "total_predictions": total_predictions, "total_hits": total_hits}, f, ensure_ascii=False, indent=2)

    # 매크로 추세 (indicator-history) + 트렌드 분석
    ind_history = loader.get_indicator_history()
    # F&G/VIX 과거 비교 추가
    fg_raw = loader.get_fear_greed()
    if isinstance(fg_raw, dict) and isinstance(ind_history, dict):
        ind_history["fear_greed_trend"] = {
            "current": fg_raw.get("score"),
            "previous_1_week": fg_raw.get("previous_1_week"),
            "previous_1_month": fg_raw.get("previous_1_month"),
        }
        vix_raw = loader.get_vix()
        if isinstance(vix_raw, dict):
            ind_history["vix_trend"] = {
                "current": vix_raw.get("current"),
                "score": vix_raw.get("score"),
                "rating": vix_raw.get("rating"),
            }
    with open(results_dir / "indicator_history.json", "w", encoding="utf-8") as f:
        json.dump(ind_history if isinstance(ind_history, dict) else {}, f, ensure_ascii=False, indent=2)

    # === Tier 3: 신규 분석 ===
    print("=== Phase 8: 확장 분석 ===")

    # 장중 종목별 수급 추적 (investor-intraday data 필드)
    intraday_stock_tracker = []
    if isinstance(snapshots, list) and len(snapshots) >= 2:
        # 첫 시점과 마지막 시점의 종목별 수급 변화 추적
        first_snap = snapshots[0].get("data", {}) if isinstance(snapshots[0], dict) else {}
        last_snap = snapshots[-1].get("data", {}) if isinstance(snapshots[-1], dict) else {}
        for code in last_snap:
            if code not in first_snap:
                continue
            first = first_snap[code] if isinstance(first_snap[code], dict) else {}
            last = last_snap[code] if isinstance(last_snap[code], dict) else {}
            f_first = first.get("f") or 0
            f_last = last.get("f") or 0
            i_first = first.get("i") or 0
            i_last = last.get("i") or 0
            f_change = f_last - f_first
            cr = last.get("cr") or 0
            cp = last.get("cp") or 0
            # 외국인 수급 방향 전환 감지
            reversal = ""
            if f_first < 0 and f_last > 0:
                reversal = "매도→매수 전환"
            elif f_first > 0 and f_last < 0:
                reversal = "매수→매도 전환"
            # 시점 간 가속/둔화 판정 (중간 스냅샷 활용)
            trend = ""
            if len(snapshots) >= 3:
                mid_snap = snapshots[len(snapshots) // 2].get("data", {})
                mid = mid_snap.get(code, {}) if isinstance(mid_snap, dict) else {}
                f_mid = mid.get("f") or 0
                first_half = f_mid - f_first
                second_half = f_last - f_mid
                if abs(second_half) > abs(first_half) * 1.5 and f_last > 0:
                    trend = "매수 가속"
                elif abs(second_half) < abs(first_half) * 0.5 and f_last > 0:
                    trend = "매수 둔화"
                elif abs(second_half) > abs(first_half) * 1.5 and f_last < 0:
                    trend = "매도 가속"
                elif abs(second_half) < abs(first_half) * 0.5 and f_last < 0:
                    trend = "매도 둔화"
            if abs(f_change) > 50000 or reversal:
                intraday_stock_tracker.append({
                    "code": code, "price": cp, "change_rate": cr,
                    "foreign_first": f_first, "foreign_last": f_last, "foreign_change": f_change,
                    "institution_change": i_last - i_first,
                    "reversal": reversal,
                    "trend": trend,
                })
        intraday_stock_tracker.sort(key=lambda x: abs(x.get("foreign_change", 0)), reverse=True)
    with open(results_dir / "intraday_stock_tracker.json", "w", encoding="utf-8") as f:
        json.dump(intraday_stock_tracker[:20], f, ensure_ascii=False, indent=2)

    # 연속 상승/하락 모니터 (fluctuation_direct)
    fluct_direct = latest.get("fluctuation_direct", {})
    consecutive_monitor = {"up": [], "down": []}
    for direction in ["kospi_up", "kospi_down", "kosdaq_up", "kosdaq_down"]:
        stocks_list = fluct_direct.get(direction, []) if isinstance(fluct_direct, dict) else []
        for s in stocks_list if isinstance(stocks_list, list) else []:
            if not isinstance(s, dict):
                continue
            cup = s.get("consecutive_up_days", 0) or 0
            cdown = s.get("consecutive_down_days", 0) or 0
            if cup >= 3:
                inv_s = investor_data.get(s.get("code", ""), {})
                fn = (inv_s.get("foreign_net") or 0) if isinstance(inv_s, dict) else 0
                consecutive_monitor["up"].append({
                    "code": s.get("code", ""), "name": s.get("name", ""),
                    "days": cup, "change_rate": s.get("change_rate", 0),
                    "foreign_net": fn,
                })
            if cdown >= 3:
                inv_s = investor_data.get(s.get("code", ""), {})
                fn = (inv_s.get("foreign_net") or 0) if isinstance(inv_s, dict) else 0
                consecutive_monitor["down"].append({
                    "code": s.get("code", ""), "name": s.get("name", ""),
                    "days": cdown, "change_rate": s.get("change_rate", 0),
                    "foreign_net": fn,
                    "bounce_signal": fn > 50000,
                })
    consecutive_monitor["up"].sort(key=lambda x: x["days"], reverse=True)
    consecutive_monitor["down"].sort(key=lambda x: x["days"], reverse=True)
    with open(results_dir / "consecutive_monitor.json", "w", encoding="utf-8") as f:
        json.dump(consecutive_monitor, f, ensure_ascii=False, indent=2)

    # 매물대 지지/저항 경보 (현재가 대비 POC 위치)
    vp_alerts = []
    for vp_item in vp_results:
        code = vp_item.get("code", "")
        # 현재가 조회
        inv_cur = investor_data.get(code, {})
        # intraday 마지막 스냅샷에서 현재가 가져오기
        cur_price = 0
        if isinstance(snapshots, list) and snapshots:
            last_data = snapshots[-1].get("data", {}) if isinstance(snapshots[-1], dict) else {}
            sd = last_data.get(code, {})
            cur_price = sd.get("cp", 0) if isinstance(sd, dict) else 0
        if not cur_price:
            continue
        poc_1m = vp_item.get("poc_1month", 0)
        poc_3m = vp_item.get("poc_3month", 0)
        support = vp_item.get("support", 0)
        resistance = vp_item.get("resistance", 0)
        if not (support and resistance):
            continue
        # 현재가 대비 위치 판단
        if cur_price <= support * 1.02:
            status = "지지대 근접"
        elif cur_price >= resistance * 0.98:
            status = "저항대 근접"
        elif cur_price > resistance:
            status = "저항 돌파"
        elif cur_price < support:
            status = "지지 이탈"
        else:
            continue  # 중간 구간은 경보 불필요
        vp_alerts.append({
            "code": code, "name": vp_item.get("name", ""),
            "current_price": cur_price,
            "support": support, "resistance": resistance,
            "poc_1month": poc_1m, "poc_3month": poc_3m,
            "status": status,
        })
    with open(results_dir / "volume_profile_alerts.json", "w", encoding="utf-8") as f:
        json.dump(vp_alerts, f, ensure_ascii=False, indent=2)

    # 시그널 소스별 성과 비교 (simulation 48일 집계)
    source_performance = {"vision": {"total": 0, "wins": 0, "sum_return": 0},
                          "kis": {"total": 0, "wins": 0, "sum_return": 0},
                          "combined": {"total": 0, "wins": 0, "sum_return": 0}}
    for entry in sim_history_results:
        by_cat = entry.get("by_category", {})
        for cat in ["vision", "kis", "combined"]:
            cs = by_cat.get(cat, {})
            source_performance[cat]["total"] += cs.get("total", 0)
            source_performance[cat]["wins"] += cs.get("wins", 0)
            source_performance[cat]["sum_return"] += cs.get("avg_return", 0) * cs.get("total", 0)
    for cat, perf in source_performance.items():
        perf["win_rate"] = round(perf["wins"] / perf["total"] * 100, 1) if perf["total"] else 0
        perf["avg_return"] = round(perf["sum_return"] / perf["total"], 2) if perf["total"] else 0
        del perf["sum_return"]
    best_source = max(source_performance, key=lambda k: source_performance[k]["win_rate"]) if any(p["total"] for p in source_performance.values()) else "combined"
    with open(results_dir / "source_performance.json", "w", encoding="utf-8") as f:
        json.dump({"by_source": source_performance, "best_source": best_source}, f, ensure_ascii=False, indent=2)

    # === 미활용 데이터 활용: 시장 breadth + program_net + 10일 히스토리 ===

    # 시장 breadth: investor-intraday 스냅샷별 외국인 순매수 양성 비율
    market_breadth = []
    if isinstance(snapshots, list):
        for snap in snapshots:
            if not isinstance(snap, dict):
                continue
            sd = snap.get("data", {})
            if not isinstance(sd, dict) or not sd:
                continue
            total_stocks = len(sd)
            positive_foreign = sum(1 for v in sd.values() if isinstance(v, dict) and (v.get("f") or 0) > 0)
            market_breadth.append({
                "time": snap.get("time", ""),
                "total": total_stocks,
                "positive_foreign": positive_foreign,
                "ratio": round(positive_foreign / total_stocks * 100, 1) if total_stocks else 0,
            })
    with open(results_dir / "market_breadth.json", "w", encoding="utf-8") as f:
        json.dump(market_breadth, f, ensure_ascii=False, indent=2)

    # program_trade 투자자 유형별 분리
    program_trade = latest.get("program_trade", {})
    program_detail = {}
    for market in ["kospi", "kosdaq"]:
        pt_list = program_trade.get(market, [])
        if isinstance(pt_list, list):
            for pt_item in pt_list:
                if isinstance(pt_item, dict):
                    inv_type = pt_item.get("investor", "")
                    if inv_type:
                        if inv_type not in program_detail:
                            program_detail[inv_type] = {"all": 0, "arbt": 0, "nabt": 0}
                        program_detail[inv_type]["all"] += pt_item.get("all_ntby_amt", 0) or 0
                        program_detail[inv_type]["arbt"] += pt_item.get("arbt_ntby_amt", 0) or 0
                        program_detail[inv_type]["nabt"] += pt_item.get("nabt_ntby_amt", 0) or 0
    with open(results_dir / "program_detail.json", "w", encoding="utf-8") as f:
        json.dump(program_detail, f, ensure_ascii=False, indent=2)

    # 투자자 10일 히스토리 추세 (상위 수급 변화 종목)
    investor_trend_stocks = []
    for code, inv in investor_data.items() if isinstance(investor_data, dict) else []:
        if not isinstance(inv, dict):
            continue
        history = inv.get("history", [])
        if not isinstance(history, list) or len(history) < 3:
            continue
        fn_current = inv.get("foreign_net") or 0
        # 히스토리에서 가장 오래된 값
        fn_oldest = 0
        for h in history:
            if isinstance(h, dict):
                fn_oldest = h.get("foreign_net", h.get("foreign", 0)) or 0
                break
        fn_change = fn_current - fn_oldest
        if abs(fn_change) > 100000:
            investor_trend_stocks.append({
                "code": code, "name": inv.get("name", ""),
                "foreign_net": fn_current,
                "foreign_10d_change": fn_change,
                "trend": "매수 전환" if fn_oldest < 0 and fn_current > 0 else "매도 전환" if fn_oldest > 0 and fn_current < 0 else "매수 강화" if fn_change > 0 else "매도 강화",
                "days": len(history),
            })
    investor_trend_stocks.sort(key=lambda x: abs(x["foreign_10d_change"]), reverse=True)
    with open(results_dir / "investor_trend_stocks.json", "w", encoding="utf-8") as f:
        json.dump(investor_trend_stocks[:20], f, ensure_ascii=False, indent=2)

    # 모든 JSON에 generated_at 타임스탬프 일괄 삽입
    from datetime import datetime, timezone, timedelta
    kst = timezone(timedelta(hours=9))
    generated_at = datetime.now(kst).strftime("%Y-%m-%d %H:%M KST")
    for json_file in results_dir.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data["generated_at"] = generated_at
            else:
                continue  # list 타입은 구조 변경 없이 건너뜀
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  타임스탬프 삽입 실패 ({json_file.name}): {e}")

    # 프론트엔드 데이터 복사
    frontend_data = Path(__file__).parent.parent / "frontend" / "public" / "data"
    frontend_data.mkdir(parents=True, exist_ok=True)
    for json_file in results_dir.glob("*.json"):
        shutil.copy2(json_file, frontend_data / json_file.name)

    print(f"=== 전체 완료 (mode={args.mode}) ===")


if __name__ == "__main__":
    main()
