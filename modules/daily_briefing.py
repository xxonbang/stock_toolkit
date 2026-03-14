import json
from datetime import datetime
import pytz

KST = pytz.timezone("Asia/Seoul")

def build_morning_context(macro: dict, forecast: dict, cross_signals: list) -> dict:
    return {
        "type": "morning",
        "date": datetime.now(KST).strftime("%Y-%m-%d (%a)"),
        "fear_greed": macro.get("fear_greed", {}),
        "vix": macro.get("vix", {}),
        "indicators": macro.get("indicators", {}),
        "themes": forecast.get("today", []),
        "cross_signals": cross_signals,
    }


def build_evening_context(macro: dict, performance: dict) -> dict:
    return {
        "type": "evening",
        "date": datetime.now(KST).strftime("%Y-%m-%d (%a)"),
        "market": macro,
        "performance": performance,
    }


MORNING_PROMPT = """당신은 한국 주식 시장 전문 애널리스트입니다.
아래 데이터를 기반으로 오늘의 모닝 브리프를 작성하세요.

데이터:
{context}

출력 형식 (텔레그램 HTML):
1. 글로벌 환경 (F&G, VIX, 환율) — 2~3줄
2. 오늘의 주목 테마 (상위 3개) — 테마명 + 이유 1줄씩
3. 고확신 종목 (크로스 시그널) — 종목명 + 신호 + 핵심 근거
4. 주의 종목 — 리스크 요인이 있는 종목
5. 전략 제안 — 2~3줄 핵심 전략

간결하게, HTML 태그(<b>, <i>) 사용. 전체 30줄 이내."""

EVENING_PROMPT = """당신은 한국 주식 시장 전문 애널리스트입니다.
아래 데이터를 기반으로 오늘의 이브닝 리뷰를 작성하세요.

데이터:
{context}

출력 형식 (텔레그램 HTML):
1. 오늘의 시장 요약 — KOSPI/KOSDAQ 지수 + 특징 2줄
2. 시스템 성과 — 적극매수 적중률, 평균 수익률
3. 테마 변동 — 신규 부상/약화 테마
4. 내일 관전 포인트 — 2~3줄

간결하게, HTML 태그(<b>, <i>) 사용. 전체 25줄 이내."""


def generate_morning_brief(gemini_client, data_loader) -> str:
    from modules.cross_signal import find_cross_signals

    macro = data_loader.get_macro()
    forecast = data_loader.get_theme_forecast()
    themes = data_loader.get_themes()
    signals = data_loader.get_combined_signals()
    cross = find_cross_signals(themes, signals)
    ctx = build_morning_context(macro, forecast, cross)
    prompt = MORNING_PROMPT.format(context=json.dumps(ctx, ensure_ascii=False, indent=2))
    return gemini_client.generate(prompt)


def generate_evening_review(gemini_client, data_loader) -> str:
    from modules.system_performance import build_performance_report

    macro = data_loader.get_macro()
    perf = build_performance_report(data_loader)
    ctx = build_evening_context(macro, perf)
    prompt = EVENING_PROMPT.format(context=json.dumps(ctx, ensure_ascii=False, indent=2))
    return gemini_client.generate(prompt)
