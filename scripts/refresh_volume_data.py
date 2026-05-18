#!/usr/bin/env python3
"""volume_avg_20d.json + volume_30d_history.json 직접 생성 (daily_ohlcv 의존성 X).

GitHub Actions cron에서 매일 실행. daemon hang 문제 완전 우회.

데이터 소스:
- Supabase portfolio_holdings: 보유 종목 unique code (모든 사용자)
- KIS volume-rank API: TOP 200 종목 (보조)
- KIS inquire-daily-price: 종목별 30일 일봉

출력:
- results/volume_avg_20d.json
- results/volume_30d_history.json
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiohttp

KST = timezone(timedelta(hours=9))
KIS_BASE = "https://openapi.koreainvestment.com:9443"

KIS_APP_KEY = os.environ.get("KIS_APP_KEY", "")
KIS_APP_SECRET = os.environ.get("KIS_APP_SECRET", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_SECRET_KEY", "")

OUT_AVG = Path(__file__).parent.parent / "results" / "volume_avg_20d.json"
OUT_HIST = Path(__file__).parent.parent / "results" / "volume_30d_history.json"


async def get_kis_token(session: aiohttp.ClientSession) -> str:
    body = {"grant_type": "client_credentials", "appkey": KIS_APP_KEY, "appsecret": KIS_APP_SECRET}
    async with session.post(f"{KIS_BASE}/oauth2/tokenP", json=body, timeout=aiohttp.ClientTimeout(total=15)) as r:
        d = await r.json()
        tok = d.get("access_token")
        if not tok:
            raise RuntimeError(f"KIS token 발급 실패: {d}")
        return tok


def fetch_holdings_codes() -> list[str]:
    """Supabase portfolio_holdings에서 unique code 추출 (service_role로 RLS bypass)."""
    if not (SUPABASE_URL and SUPABASE_KEY):
        return []
    import urllib.request
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/portfolio_holdings?select=code",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            return list({row.get("code", "") for row in data if row.get("code")})
    except Exception as e:
        print(f"Supabase holdings 조회 실패: {e}", flush=True)
        return []


async def _fetch_daily_mkt(session: aiohttp.ClientSession, token: str, code: str, mkt: str) -> list[dict]:
    url = f"{KIS_BASE}/uapi/domestic-stock/v1/quotations/inquire-daily-price"
    params = {
        "FID_COND_MRKT_DIV_CODE": mkt, "FID_INPUT_ISCD": code,
        "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "0",
    }
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}", "appkey": KIS_APP_KEY, "appsecret": KIS_APP_SECRET,
        "tr_id": "FHKST01010400", "custtype": "P",
    }
    async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r:
        d = await r.json()
        if d.get("rt_cd") != "0":
            return []
        return d.get("output", [])


async def fetch_daily(session: aiohttp.ClientSession, token: str, code: str) -> list[dict]:
    """UN(통합) 우선 + NXT 미상장 종목 자동 J fallback (KIS API 버그 회피)."""
    threshold = (datetime.now(KST) - timedelta(days=10)).strftime("%Y%m%d")
    bars = await _fetch_daily_mkt(session, token, code, "UN")
    if not bars:
        return await _fetch_daily_mkt(session, token, code, "J")
    first_date = bars[0].get("stck_bsop_date", "")
    if first_date and first_date < threshold:
        return await _fetch_daily_mkt(session, token, code, "J")
    return bars


async def main() -> None:
    if not (KIS_APP_KEY and KIS_APP_SECRET):
        sys.exit("KIS_APP_KEY/SECRET 미설정")

    print("=== refresh_volume_data 시작 ===", flush=True)
    holdings = fetch_holdings_codes()
    print(f"보유 종목 (Supabase): {len(holdings)}건", flush=True)

    async with aiohttp.ClientSession() as session:
        token = await get_kis_token(session)
        print(f"KIS token OK", flush=True)

        # 보유 종목만 fetch — volume-rank API는 권한 문제로 미사용.
        # 새 종목 추가 시 다음 cron(24h 이내)에서 자동 포함됨.
        target_codes = list(dict.fromkeys(holdings))
        if not target_codes:
            print("보유 종목 없음 — skip", flush=True)
            return
        print(f"갱신 대상: {len(target_codes)}종목 (보유)", flush=True)

        # 종목별 일봉 fetch
        hist_data: dict[str, list[int]] = {}
        errors = 0
        for i, code in enumerate(target_codes):
            try:
                bars = await fetch_daily(session, token, code)
                if not bars:
                    errors += 1
                    continue
                # output은 최근 → 과거 역순. 오래된 → 최근으로 뒤집어 저장
                vols = []
                for b in reversed(bars[:30]):
                    try:
                        vols.append(int(b.get("acml_vol", 0)))
                    except (TypeError, ValueError):
                        vols.append(0)
                if any(v > 0 for v in vols):
                    hist_data[code] = vols
                await asyncio.sleep(0.06)
                if (i + 1) % 30 == 0:
                    print(f"  진행: {i+1}/{len(target_codes)} (수집 {len(hist_data)}, 에러 {errors})", flush=True)
            except Exception as e:
                errors += 1
                print(f"  {code} error: {type(e).__name__}: {e}", flush=True)

    print(f"fetch 완료: {len(hist_data)}종목 수집, {errors} 에러", flush=True)

    # 20일 평균 거래량 계산 (마지막 20일)
    avg_data: dict[str, int] = {}
    for code, vols in hist_data.items():
        recent = vols[-20:]
        pos = [v for v in recent if v > 0]
        if pos:
            avg_data[code] = int(sum(pos) / len(pos))

    # 기존 데이터 merge — 보유 외 종목 데이터 유지 (다른 사용자 종목 또는 이전 신규 데이터)
    def load_existing(p: Path) -> dict:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}
    existing_avg = {k: v for k, v in load_existing(OUT_AVG).items() if not k.startswith("_")}
    existing_hist = {k: v for k, v in load_existing(OUT_HIST).items() if not k.startswith("_")}
    merged_avg = {**existing_avg, **avg_data}    # 신규가 기존을 덮어씀
    merged_hist = {**existing_hist, **hist_data}

    # 메타데이터 추가
    kst_now = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    src_last_date = datetime.now(KST).strftime("%Y%m%d")
    avg_with_meta = {"_generated_at": kst_now, "_source_last_date": src_last_date, **merged_avg}
    hist_with_meta = {"_generated_at": kst_now, "_source_last_date": src_last_date, **merged_hist}
    print(f"merge: 기존 {len(existing_avg)}건 + 신규 {len(avg_data)}건 → 최종 {len(merged_avg)}건", flush=True)

    OUT_AVG.parent.mkdir(parents=True, exist_ok=True)
    OUT_AVG.write_text(json.dumps(avg_with_meta, ensure_ascii=False), encoding="utf-8")
    OUT_HIST.write_text(json.dumps(hist_with_meta, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT_AVG.name}: {len(avg_data)} codes, {OUT_AVG.stat().st_size/1024:.1f}KB", flush=True)
    print(f"wrote {OUT_HIST.name}: {len(hist_data)} codes, {OUT_HIST.stat().st_size/1024:.1f}KB", flush=True)
    print("=== 완료 ===", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
