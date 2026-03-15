def build_event_calendar(macro_events: list, earnings_dates: list) -> list:
    """
    macro_events: [{"date": str, "name": str, "impact": str}]
    earnings_dates: [{"date": str, "code": str, "name": str}]
    Returns unified, date-sorted event list.
    """
    calendar = []
    for e in macro_events:
        calendar.append({
            "date": e.get("date", ""),
            "type": "매크로",
            "name": e.get("name", ""),
            "impact": e.get("impact", "중"),
            "code": None,
        })
    for e in earnings_dates:
        calendar.append({
            "date": e.get("date", ""),
            "type": "실적",
            "name": e.get("name", ""),
            "impact": "중",
            "code": e.get("code"),
        })
    return sorted(calendar, key=lambda x: x.get("date", ""))


def analyze_event_overlap(calendar: list) -> list:
    """
    Finds dates with multiple events and assesses combined impact.
    """
    from collections import defaultdict
    by_date: dict = defaultdict(list)
    for event in calendar:
        by_date[event["date"]].append(event)
    overlaps = []
    for date, events in sorted(by_date.items()):
        if len(events) < 2:
            continue
        high_impact = sum(1 for e in events if e.get("impact") == "상")
        combined = "고위험" if high_impact >= 2 else ("주의" if len(events) >= 3 else "모니터링")
        overlaps.append({
            "date": date,
            "events": events,
            "event_count": len(events),
            "combined_impact": combined,
        })
    return overlaps


def format_calendar_alert(analysis: list) -> str:
    if not analysis:
        return "<b>[이벤트 캘린더] 중복 이벤트 없음</b>"
    lines = ["<b>[이벤트 캘린더 복합 분석]</b>", "━" * 20]
    for overlap in analysis[:5]:
        lines.append(
            f"\n<b>{overlap['date']}</b> — {overlap['combined_impact']} "
            f"({overlap['event_count']}건 중복)"
        )
        for e in overlap["events"]:
            tag = f"[{e['type']}]"
            lines.append(f"  {tag} {e['name']}")
    lines.append("━" * 20)
    return "\n".join(lines)
