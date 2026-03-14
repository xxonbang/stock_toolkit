def find_cross_signals(themes: list, combined_signals: list) -> list:
    leader_map = {}
    for theme in themes:
        for leader in theme.get("leaders", []):
            code = leader.get("code")
            if code:
                leader_map[code] = {
                    "theme": theme.get("name"),
                    "theme_rank": theme.get("rank"),
                }
    matches = []
    buy_signals = {"적극매수", "매수"}
    for sig in combined_signals:
        code = sig.get("code")
        if code in leader_map and sig.get("signal") in buy_signals:
            matches.append({**sig, **leader_map[code]})
    matches.sort(key=lambda x: x.get("score", 0), reverse=True)
    return matches


def format_cross_signal_alert(matches: list) -> str:
    if not matches:
        return ""
    lines = ["<b>[고확신 매매 후보] 크로스 시그널</b>", "━" * 20]
    for m in matches:
        lines.append(
            f"\n<b>{m['name']} ({m['code']})</b>\n"
            f"테마: {m['theme']} (#{m.get('theme_rank', '-')})\n"
            f"신호: {m['signal']} (점수: {m.get('score', '-')})"
        )
    lines.append("━" * 20)
    return "\n".join(lines)


def run(data_loader, send_fn=None):
    themes = data_loader.get_themes()
    signals = data_loader.get_combined_signals()
    matches = find_cross_signals(themes, signals)
    if matches and send_fn:
        send_fn(format_cross_signal_alert(matches))
    return matches
