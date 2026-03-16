def classify_lifecycle_stage(appeared_days: int, rank_trend: str, volume_trend: str, leader_change: float, spread_count: int) -> str:
    if appeared_days <= 3:
        return "탄생"
    if rank_trend == "falling" or (volume_trend == "falling" and leader_change < 0):
        return "쇠퇴"
    if volume_trend == "peak" or spread_count >= 12 or leader_change >= 7.0:
        return "과열"
    if rank_trend in ("stable_high", "rising") and volume_trend in ("rising", "stable"):
        return "성장"
    return "성장"


def _calculate_trend(values: list) -> str:
    if len(values) < 2:
        return "stable"
    recent = values[-3:] if len(values) >= 3 else values
    if all(recent[i] <= recent[i+1] for i in range(len(recent)-1)):
        return "rising"
    if all(recent[i] >= recent[i+1] for i in range(len(recent)-1)):
        return "falling"
    if values[-1] == max(values):
        return "peak"
    avg = sum(values) / len(values)
    if values[-1] >= avg:
        return "stable_high"
    return "stable"


def track_theme_lifecycle(theme_name: str, history: list, change_rate_map: dict = None) -> dict:
    appearances = []
    for snapshot in history:
        themes = snapshot.get("themes", [])
        # theme_analysis 구조 대응
        if not themes:
            ta = snapshot.get("data", {})
            if isinstance(ta, dict):
                themes = ta.get("theme_analysis", {}).get("themes", []) if isinstance(ta.get("theme_analysis"), dict) else ta.get("themes", [])
        for theme in themes:
            name = theme.get("theme_name", theme.get("name", ""))
            if name == theme_name:
                leaders = theme.get("leader_stocks", theme.get("leaders", []))
                stock_count = len(leaders)
                # leader_change: 리더 종목 평균 등락률
                avg_change = 0
                if leaders and change_rate_map:
                    changes = [change_rate_map.get(l.get("code"), 0) for l in leaders if isinstance(l, dict)]
                    avg_change = round(sum(changes) / len(changes), 2) if changes else 0
                appearances.append({
                    "date": snapshot.get("date", ""),
                    "rank": theme.get("rank", len(themes)),
                    "leader_change": avg_change,
                    "stock_count": stock_count,
                })
    if not appearances:
        return {"theme": theme_name, "stage": "미확인", "appeared_days": 0}
    ranks = [a["rank"] for a in appearances]
    changes = [a["leader_change"] for a in appearances]
    counts = [a["stock_count"] for a in appearances]
    stage = classify_lifecycle_stage(appeared_days=len(appearances), rank_trend=_calculate_trend([99 - r for r in ranks]), volume_trend=_calculate_trend(counts), leader_change=changes[-1] if changes else 0, spread_count=counts[-1] if counts else 0)
    strategy_map = {"탄생": "초기 진입 기회 — 대장주 중심 소량 매수", "성장": "추세 추종 — 눌림목 매수 유효", "과열": "신규 진입 자제 — 보유분 분할 매도", "쇠퇴": "잔여분 정리 — 다음 테마 탐색"}
    avg_change_latest = changes[-1] if changes else 0
    return {"theme": theme_name, "stage": stage, "appeared_days": len(appearances), "avg_change": avg_change_latest, "stock_count": counts[-1] if counts else 0, "strategy": strategy_map.get(stage, "")}


def format_lifecycle_alert(result: dict) -> str:
    stage_emoji = {"탄생": "🌱", "성장": "📈", "과열": "🔥", "쇠퇴": "📉"}
    emoji = stage_emoji.get(result["stage"], "❓")
    return f"<b>[테마 라이프사이클] {emoji} {result['theme']}</b>\n단계: {result['stage']} ({result['appeared_days']}일차)\n현재 순위: #{result['current_rank']}\n전략: {result['strategy']}"
