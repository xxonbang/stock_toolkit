"""텔레그램 봇 명령어 핸들러"""
from config.settings import THEME_DATA_PATH, SIGNAL_DATA_PATH
from core.data_loader import DataLoader
from modules.stock_scanner import scan_stocks, format_scan_result
from modules.cross_signal import find_cross_signals, format_cross_signal_alert
from bot.formatters import format_stock_card

loader = DataLoader(THEME_DATA_PATH, SIGNAL_DATA_PATH)


def handle_scan(query: str) -> str:
    latest = loader.get_latest()
    combined = loader.get_combined_signals()
    # 종목 데이터에 신호 병합
    stocks = latest.get("rising_stocks", [])
    signal_map = {s["code"]: s for s in combined}
    for stock in stocks:
        sig = signal_map.get(stock.get("code"))
        if sig:
            stock.update(sig)
    results = scan_stocks(stocks, query)
    return format_scan_result(results, query)


def handle_top() -> str:
    themes = loader.get_themes()
    signals = loader.get_combined_signals()
    matches = find_cross_signals(themes, signals)
    if not matches:
        return "현재 고확신 종목이 없습니다."
    return format_cross_signal_alert(matches)


def handle_stock(code: str) -> str:
    stock = loader.get_stock(code)
    if not stock:
        return f"종목 {code}을 찾을 수 없습니다."
    return format_stock_card(stock)


def handle_market() -> str:
    macro = loader.get_macro()
    fg = macro.get("fear_greed", {})
    vix = macro.get("vix", {})
    indicators = macro.get("indicators", {})
    lines = [
        "<b>[시장 현황]</b>",
        f"Fear & Greed: {fg.get('score', '—')} ({fg.get('label', '—')})",
        f"VIX: {vix.get('current', '—')}",
    ]
    if indicators:
        for k, v in indicators.items():
            lines.append(f"{k}: {v}")
    return "\n".join(lines)
