def find_cross_signals(themes: list, combined_signals: list) -> list:
    """signal-pulse 매수 시그널 종목 + theme-analyzer 대장주 전체를 필터 없이 수집"""
    buy_signals = {"적극매수", "매수"}

    # 1) 대장주 맵 구축
    leader_map = {}
    leader_names = {}
    for idx, theme in enumerate(themes):
        for leader in theme.get("leader_stocks", theme.get("leaders", [])):
            code = leader.get("code")
            if code:
                leader_map[code] = {
                    "theme": theme.get("theme_name", theme.get("name")),
                    "theme_rank": theme.get("rank") or (idx + 1),
                }
                leader_names[code] = leader.get("name", "")

    # 2) combined_signals를 코드 기준 맵으로
    sig_map = {}
    for sig in combined_signals:
        code = sig.get("code")
        if code:
            sig_map[code] = sig

    # 3) 수집: 매수 시그널 종목 + 대장주 (UNION)
    result_map = {}

    # 3a) 매수 시그널 종목 (signal-pulse)
    for code, sig in sig_map.items():
        vs = sig.get("vision_signal", sig.get("signal", ""))
        as_ = sig.get("api_signal", "")
        if vs in buy_signals or as_ in buy_signals:
            entry = {**sig}
            if code in leader_map:
                entry.update(leader_map[code])
            if vs in buy_signals and as_ in buy_signals:
                entry["dual_signal"] = "고확신"
            elif vs in buy_signals:
                entry["dual_signal"] = "확인필요"
            elif as_ in buy_signals:
                entry["dual_signal"] = "KIS매수"
            result_map[code] = entry

    # 3b) 대장주 중 아직 수집되지 않은 종목 추가
    for code, leader_info in leader_map.items():
        if code in result_map:
            continue
        # combined_signals에 데이터가 있으면 병합
        if code in sig_map:
            entry = {**sig_map[code], **leader_info}
        else:
            entry = {"code": code, "name": leader_names.get(code, ""), **leader_info}
        entry["dual_signal"] = "대장주"
        result_map[code] = entry

    result = list(result_map.values())
    result.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    return result


def format_cross_signal_alert(matches: list) -> str:
    if not matches:
        return ""
    lines = ["<b>[고확신 매매 후보] 크로스 시그널</b>", "━" * 20]
    for m in matches:
        sig = m.get('vision_signal', m.get('signal', '-'))
        dual = f" [{m['dual_signal']}]" if m.get('dual_signal') else ""
        lines.append(
            f"\n<b>{m.get('name', '')} ({m.get('code', '')})</b>\n"
            f"테마: {m.get('theme', '')} (#{m.get('theme_rank', '-')})\n"
            f"신호: {sig}{dual} (신뢰도: {round(m.get('confidence', 0) * 100)}%)"
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
