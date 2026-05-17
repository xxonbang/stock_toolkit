#!/usr/bin/env python3
"""results/daily_ohlcv_all.json에서 종목별 거래량 지표 추출 → 소형 JSON 생성.

용도: frontend RVOL(상대 거래량) + 30일 거래량 순위 계산.
     전체 일봉(353MB)은 frontend가 fetch 불가하므로 필요 부분만 소형 파일로 분리.

출력:
  results/volume_avg_20d.json   — {"<code>": <avg_vol_20d_int>}
  results/volume_30d_history.json — {"<code>": [vol_d0, vol_d1, ...]}  (오래된→최근)
"""
from __future__ import annotations
import json
from pathlib import Path

AVG_DAYS = 20
HISTORY_DAYS = 30
SRC = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"
DST_AVG = Path(__file__).parent.parent / "results" / "volume_avg_20d.json"
DST_HIST = Path(__file__).parent.parent / "results" / "volume_30d_history.json"


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"input not found: {SRC}")
    data = json.loads(SRC.read_text(encoding="utf-8"))
    avg_out: dict[str, int] = {}
    hist_out: dict[str, list[int]] = {}
    for code, info in data.items():
        if not isinstance(code, str) or len(code) != 6 or not code.isdigit():
            continue
        bars = info.get("bars") if isinstance(info, dict) else None
        if not isinstance(bars, list) or not bars:
            continue
        # bars는 오래된 → 최근 정렬. 마지막 N개의 acml_vol 추출
        def to_int(b: dict) -> int:
            try:
                return int(b.get("acml_vol", 0))
            except (TypeError, ValueError):
                return 0

        recent_avg = bars[-AVG_DAYS:]
        vols_avg = [v for v in (to_int(b) for b in recent_avg) if v > 0]
        if vols_avg:
            avg_out[code] = int(sum(vols_avg) / len(vols_avg))

        recent_hist = bars[-HISTORY_DAYS:]
        vols_hist = [to_int(b) for b in recent_hist]
        if any(v > 0 for v in vols_hist):
            hist_out[code] = vols_hist

    DST_AVG.write_text(json.dumps(avg_out, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {DST_AVG.name}: {len(avg_out)} codes, {DST_AVG.stat().st_size / 1024:.1f}KB")
    DST_HIST.write_text(json.dumps(hist_out, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {DST_HIST.name}: {len(hist_out)} codes, {DST_HIST.stat().st_size / 1024:.1f}KB")


if __name__ == "__main__":
    main()
