from modules.stock_scanner import scan_stocks
from modules.system_performance import calculate_avg_return


def parse_strategy(strategy_str: str) -> dict:
    parts = strategy_str.split()
    result = {"filters": "", "hold_days": 5, "stop_loss": None, "take_profit": None}
    filter_parts = []
    for part in parts:
        if part.startswith("hold="):
            result["hold_days"] = int(part.split("=")[1])
        elif part.startswith("stop="):
            result["stop_loss"] = float(part.split("=")[1])
        elif part.startswith("tp="):
            result["take_profit"] = float(part.split("=")[1])
        else:
            filter_parts.append(part)
    result["filters"] = " ".join(filter_parts)
    result["raw"] = strategy_str
    return result


def simulate_strategy(history: list, strategy: dict) -> dict:
    trades = []
    hold = strategy["hold_days"]
    stop = strategy.get("stop_loss")

    for snapshot in history:
        stocks = snapshot.get("stocks", [])
        if strategy["filters"]:
            matched = scan_stocks(stocks, strategy["filters"])
        else:
            matched = stocks

        for stock in matched:
            price_key = f"price_d{hold}"
            entry = stock.get("price_d0", 0)
            exit_price = stock.get(price_key, 0)
            if entry <= 0 or exit_price <= 0:
                continue
            ret = round((exit_price - entry) / entry * 100, 2)

            if stop is not None:
                for d in range(1, hold + 1):
                    day_price = stock.get(f"price_d{d}", 0)
                    if day_price > 0:
                        day_ret = (day_price - entry) / entry * 100
                        if day_ret <= stop:
                            ret = round(stop, 2)
                            break

            trades.append({"code": stock.get("code"), "name": stock.get("name"), "return": ret, "date": snapshot.get("date")})

    returns = [t["return"] for t in trades]
    wins = sum(1 for r in returns if r > 0)
    return {
        "strategy": strategy["raw"],
        "total_trades": len(trades),
        "win_rate": round(wins / len(trades) * 100, 1) if trades else 0,
        "returns": calculate_avg_return(returns),
        "trades": trades,
    }


def compare_strategies(history: list, strategies: list) -> list:
    return [simulate_strategy(history, s) for s in strategies]


def format_simulation_result(result: dict) -> str:
    r = result["returns"]
    return (
        f"<b>[시뮬레이션] {result['strategy']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"총 매매: {result['total_trades']}건\n"
        f"승률: {result['win_rate']}%\n"
        f"평균 수익: {r['mean']:+.1f}%\n"
        f"최대 수익: {r['max']:+.1f}% | 최대 손실: {r['min']:+.1f}%\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
