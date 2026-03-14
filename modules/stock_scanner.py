import re


def parse_condition(condition_str: str) -> dict:
    pattern = r"(\w+)\s*(>=|<=|!=|>|<|=)\s*(.+)"
    match = re.match(pattern, condition_str.strip())
    if not match:
        return None
    field, op, value = match.groups()
    if value.lower() in ("true", "false"):
        value = value.lower() == "true"
    else:
        try:
            value = float(value)
        except ValueError:
            pass
    return {"field": field, "op": op, "value": value}


def evaluate_condition(stock: dict, cond: dict) -> bool:
    val = stock.get(cond["field"])
    if val is None:
        return False
    target = cond["value"]
    op = cond["op"]
    if op == "=":
        return str(val) == str(target)
    elif op == "!=":
        return str(val) != str(target)
    elif op == ">":
        return float(val) > float(target)
    elif op == ">=":
        return float(val) >= float(target)
    elif op == "<":
        return float(val) < float(target)
    elif op == "<=":
        return float(val) <= float(target)
    return False


def scan_stocks(stocks: list, query: str) -> list:
    parts = [p.strip() for p in query.split("AND")]
    conditions = [parse_condition(p) for p in parts]
    conditions = [c for c in conditions if c is not None]
    if not conditions:
        return stocks
    return [s for s in stocks if all(evaluate_condition(s, c) for c in conditions)]


def format_scan_result(results: list, query: str) -> str:
    if not results:
        return f"조건 일치 종목 없음\n조건: {query}"
    lines = [f"<b>[스캔 결과]</b> {len(results)}건 일치", f"조건: {query}", "━" * 20]
    for r in results:
        lines.append(f"{r.get('name', '')} ({r.get('code', '')}) — {r.get('signal', '-')} | 점수 {r.get('score', '-')}")
    return "\n".join(lines)
