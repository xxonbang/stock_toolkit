def format_stock_card(stock: dict) -> str:
    signal = stock.get("signal", {})
    lines = [
        f"<b>{stock.get('name', '')} ({stock.get('code', '')})</b>",
    ]
    if signal:
        lines.append(f"신호: {signal.get('signal', '-')} (점수: {signal.get('score', '-')})")
    if stock.get("theme"):
        lines.append(f"테마: {stock['theme']} (#{stock.get('theme_rank', '-')})")
    if stock.get("change_rate") is not None:
        lines.append(f"등락률: {stock['change_rate']:+.1f}%")
    return "\n".join(lines)


def format_section(title: str, content: str) -> str:
    return f"{'━' * 20}\n<b>{title}</b>\n{'━' * 20}\n{content}"
