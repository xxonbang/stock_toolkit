def calculate_correlations(price_histories: dict, threshold: float = 0.7) -> list:
    codes = list(price_histories.keys())
    pairs = []
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            a, b = codes[i], codes[j]
            pa = price_histories[a]
            pb = price_histories[b]
            n = min(len(pa), len(pb))
            if n < 5:
                continue
            pa, pb = pa[-n:], pb[-n:]
            mean_a = sum(pa) / n
            mean_b = sum(pb) / n
            cov = sum((pa[k] - mean_a) * (pb[k] - mean_b) for k in range(n)) / n
            std_a = (sum((x - mean_a) ** 2 for x in pa) / n) ** 0.5
            std_b = (sum((x - mean_b) ** 2 for x in pb) / n) ** 0.5
            if std_a == 0 or std_b == 0:
                continue
            corr = round(cov / (std_a * std_b), 3)
            if corr >= threshold:
                pairs.append({"code_a": a, "code_b": b, "correlation": corr})
    return sorted(pairs, key=lambda x: x["correlation"], reverse=True)


def find_clusters(correlations: list) -> list:
    groups: list[set] = []
    for pair in correlations:
        a, b = pair["code_a"], pair["code_b"]
        merged = None
        for g in groups:
            if a in g or b in g:
                g.add(a)
                g.add(b)
                merged = g
                break
        if merged is None:
            groups.append({a, b})
    return [sorted(g) for g in groups]


def format_correlation_alert(clusters: list) -> str:
    if not clusters:
        return "<b>[상관관계] 고상관 클러스터 없음</b>"
    lines = ["<b>[상관관계] 종목 클러스터</b>", "━" * 20]
    for i, cluster in enumerate(clusters, 1):
        lines.append(f"\n클러스터 {i}: {', '.join(cluster)}")
        lines.append(f"  → 동반 움직임 주의 — 분산 효과 제한적")
    lines.append("━" * 20)
    return "\n".join(lines)
