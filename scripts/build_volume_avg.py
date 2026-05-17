#!/usr/bin/env python3
"""results/daily_ohlcv_all.json에서 종목별 20일 평균 거래량을 추출 → 소형 JSON 생성.

용도: frontend RVOL(상대 거래량) 계산 — 전체 일봉(353MB)은 frontend가 fetch 불가.
출력: results/volume_avg_20d.json = {"<code>": <avg_vol_20d_int>, ...}  (~100KB 예상)
"""
from __future__ import annotations
import json
from pathlib import Path

DAYS = 20
SRC = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"
DST = Path(__file__).parent.parent / "results" / "volume_avg_20d.json"


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"input not found: {SRC}")
    data = json.loads(SRC.read_text(encoding="utf-8"))
    out: dict[str, int] = {}
    for code, info in data.items():
        if not isinstance(code, str) or len(code) != 6 or not code.isdigit():
            continue
        bars = info.get("bars") if isinstance(info, dict) else None
        if not isinstance(bars, list) or not bars:
            continue
        # bars는 오래된 → 최근 정렬. 마지막 DAYS개의 acml_vol 평균
        recent = bars[-DAYS:]
        vols: list[int] = []
        for b in recent:
            try:
                v = int(b.get("acml_vol", 0))
            except (TypeError, ValueError):
                v = 0
            if v > 0:
                vols.append(v)
        if not vols:
            continue
        out[code] = int(sum(vols) / len(vols))
    DST.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {DST.name}: {len(out)} codes, {DST.stat().st_size / 1024:.1f}KB")


if __name__ == "__main__":
    main()
