from collections import defaultdict


def aggregate_by_sector(stocks: list) -> dict:
    sectors = defaultdict(lambda: {"total_foreign_net": 0, "total_change": 0, "trading_value": 0, "stock_count": 0, "stocks": []})
    for s in stocks:
        theme = s.get("theme")
        if not theme:
            continue
        sec = sectors[theme]
        sec["total_foreign_net"] += s.get("foreign_net", 0)
        sec["total_change"] += s.get("change_rate", 0)
        sec["trading_value"] += s.get("trading_value", 0)
        sec["stock_count"] += 1
        sec["stocks"].append(s)
    for sec in sectors.values():
        if sec["stock_count"] > 0:
            sec["avg_change"] = round(sec["total_change"] / sec["stock_count"], 1)
    return dict(sectors)


def detect_rotation(today: dict, yesterday: dict) -> list:
    rotations = []
    for sector in set(list(today.keys()) + list(yesterday.keys())):
        today_net = today.get(sector, {}).get("total_foreign_net", 0)
        yest_net = yesterday.get(sector, {}).get("total_foreign_net", 0)
        if yest_net > 0 and today_net < 0:
            rotations.append({"sector": sector, "direction": "유출 전환", "yesterday": yest_net, "today": today_net})
        elif yest_net < 0 and today_net > 0:
            rotations.append({"sector": sector, "direction": "유입 전환", "yesterday": yest_net, "today": today_net})
    return rotations


def format_sector_flow(sectors: dict) -> str:
    sorted_sectors = sorted(sectors.items(), key=lambda x: x[1]["total_foreign_net"], reverse=True)
    lines = ["<b>[섹터 자금 흐름]</b>", "━" * 20]
    for name, data in sorted_sectors[:10]:
        net = data["total_foreign_net"]
        arrow = "+" if net >= 0 else ""
        emoji = "📈" if net >= 0 else "📉"
        lines.append(f"{emoji} {name}: {arrow}{net}억 ({data.get('avg_change', 0):+.1f}%) [{data['stock_count']}종목]")
    return "\n".join(lines)
