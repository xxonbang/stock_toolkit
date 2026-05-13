def _get_recently_auto_bought_codes(hours: int = 24) -> set:
    """최근 N시간 이내 자동매수된 종목 코드 set 반환 (Supabase auto_trades 조회).
    환경변수 누락 또는 조회 실패 시 빈 set 반환 (fail-safe).
    """
    import os
    import json
    import urllib.request
    from datetime import datetime, timezone, timedelta

    sb_url = os.getenv("SUPABASE_URL", "")
    sb_key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not sb_url or not sb_key:
        return set()

    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        statuses = "filled,sell_requested,sold"
        path = (
            f"/rest/v1/auto_trades"
            f"?select=code"
            f"&created_at=gte.{since}"
            f"&status=in.({statuses})"
        )
        req = urllib.request.Request(
            sb_url + path,
            headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            rows = json.loads(resp.read())
        return {r["code"] for r in rows if r.get("code")}
    except Exception as e:
        print(f"cross_signal: 자동매수 종목 조회 실패 (skip 필터) — {e}")
        return set()


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
                entry["dual_signal"] = "쌍방매수"
            elif vs in buy_signals:
                entry["dual_signal"] = "Vision매수"
            elif as_ in buy_signals:
                entry["dual_signal"] = "API매수"
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
    lines = ["<b>[매매 후보] 크로스 시그널</b>", "━" * 20]
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
    # 텔레그램 발송만 자동매수 종목 제외 (JSON 저장은 전체 보존)
    if matches and send_fn:
        excluded = _get_recently_auto_bought_codes(hours=24)
        to_send = [m for m in matches if m.get("code") not in excluded] if excluded else matches
        if excluded and len(to_send) != len(matches):
            removed = excluded & {m.get("code") for m in matches}
            print(f"cross_signal: 자동매수 종목 {len(matches) - len(to_send)}건 텔레그램 제외 {removed}")
        if to_send:
            send_fn(format_cross_signal_alert(to_send))
    return matches
