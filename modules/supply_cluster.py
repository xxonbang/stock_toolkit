_REGIMES = {
    "외국인 주도 매수": {"foreign": 1, "institution": 0, "individual": -1},
    "기관 주도 매수": {"foreign": 0, "institution": 1, "individual": -1},
    "외국인+기관 동반 매수": {"foreign": 1, "institution": 1, "individual": -1},
    "개인 주도 매수": {"foreign": -1, "institution": -1, "individual": 1},
    "외국인+개인 매수": {"foreign": 1, "institution": -1, "individual": 1},
    "기관+개인 매수": {"foreign": -1, "institution": 1, "individual": 1},
    "혼조": {"foreign": 0, "institution": 0, "individual": 0},
}

_STRATEGIES = {
    "외국인 주도 매수": "추세 추종 — 외국인 매수 지속 여부 모니터링",
    "기관 주도 매수": "중장기 편입 고려 — 실적 모멘텀 확인",
    "외국인+기관 동반 매수": "강한 매수 신호 — 포지션 확대 검토",
    "개인 주도 매수": "단기 급등 주의 — 차익 실현 구간",
    "외국인+개인 매수": "기관 부재 구간 — 변동성 유의",
    "기관+개인 매수": "외국인 이탈 구간 — 추가 상승 제한 가능",
    "혼조": "뚜렷한 수급 주체 없음 — 관망 권고",
}


def classify_supply_regime(
    foreign_net: float,
    institution_net: float,
    individual_net: float,
) -> str:
    def sign(v: float) -> int:
        return 1 if v > 0 else (-1 if v < 0 else 0)

    f, i, p = sign(foreign_net), sign(institution_net), sign(individual_net)
    for regime, pattern in _REGIMES.items():
        if pattern["foreign"] == f and pattern["institution"] == i and pattern["individual"] == p:
            return regime
    return "혼조"


def get_regime_strategy(regime: str) -> str:
    return _STRATEGIES.get(regime, "전략 정보 없음")


def format_cluster_alert(regime: str, stats: dict) -> str:
    strategy = get_regime_strategy(regime)
    lines = [
        "<b>[수급 클러스터 분석]</b>",
        "━" * 20,
        f"수급 유형: <b>{regime}</b>",
        f"전략: {strategy}",
        "",
        f"외국인: {stats.get('foreign_net', 0):+,}억원",
        f"기관:   {stats.get('institution_net', 0):+,}억원",
        f"개인:   {stats.get('individual_net', 0):+,}억원",
        "━" * 20,
    ]
    return "\n".join(lines)
