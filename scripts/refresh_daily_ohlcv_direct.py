#!/usr/bin/env python3
"""KIS API 직접 호출로 daily_ohlcv_all.json 갱신 (daemon 의존성 X).

옵션 B 구현: GCP daemon이 hang되는 상황 우회. 로컬에서 직접 KIS API 호출.
- 실투자 base URL 사용 (시세 조회는 실투자/모의 동일)
- 전일 거래대금 TOP 500 종목 + 보유 종목 우선
- 최근 5거래일 일봉 fetch + 기존 bars에 append
- 종목당 timeout 10초, 진행 로그 10종목마다

실행:
  python3 scripts/refresh_daily_ohlcv_direct.py
"""
from __future__ import annotations
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiohttp
from dotenv import dotenv_values

KST = timezone(timedelta(hours=9))
ENV = dotenv_values(Path(__file__).parent.parent / "daemon" / ".env")
APP_KEY = ENV.get("KIS_APP_KEY", "")
APP_SECRET = ENV.get("KIS_APP_SECRET", "")
BASE = "https://openapi.koreainvestment.com:9443"  # 실투자 (시세 조회용)
OHLCV_PATH = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"


async def get_token(session: aiohttp.ClientSession) -> str:
    body = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    async with session.post(f"{BASE}/oauth2/tokenP", json=body,
                            timeout=aiohttp.ClientTimeout(total=15)) as r:
        d = await r.json()
        tok = d.get("access_token")
        if not tok:
            raise RuntimeError(f"token 발급 실패: {d}")
        return tok


async def _fetch_daily_with_mkt(session: aiohttp.ClientSession, token: str, code: str, mkt: str) -> list[dict]:
    url = f"{BASE}/uapi/domestic-stock/v1/quotations/inquire-daily-price"
    params = {
        "FID_COND_MRKT_DIV_CODE": mkt,
        "FID_INPUT_ISCD": code,
        "FID_PERIOD_DIV_CODE": "D",
        "FID_ORG_ADJ_PRC": "0",
    }
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHKST01010400",
        "custtype": "P",
    }
    async with session.get(url, params=params, headers=headers,
                           timeout=aiohttp.ClientTimeout(total=10)) as r:
        d = await r.json()
        if d.get("rt_cd") != "0":
            return []
        return d.get("output", [])


async def fetch_daily(session: aiohttp.ClientSession, token: str, code: str) -> list[dict]:
    """UN(통합) 우선 + NXT 미상장 종목 자동 J fallback.
    KIS API 버그: NXT 미상장 종목 UN 호출 시 ~2개월 옛 데이터 반환 → 응답 first_date가
    10일 이상 stale이면 J로 재시도 (이때만 KRX 단독 데이터 사용)."""
    threshold = (datetime.now(KST) - timedelta(days=10)).strftime("%Y%m%d")
    bars = await _fetch_daily_with_mkt(session, token, code, "UN")
    # 응답이 비었거나 stale이면 J로 재시도
    if not bars:
        return await _fetch_daily_with_mkt(session, token, code, "J")
    first_date = bars[0].get("stck_bsop_date", "")
    if first_date and first_date < threshold:
        # NXT 미상장 종목 추정 (UN 응답이 옛 데이터) → J로 재시도
        return await _fetch_daily_with_mkt(session, token, code, "J")
    return bars


async def main() -> None:
    if not (APP_KEY and APP_SECRET):
        sys.exit("KIS_APP_KEY/SECRET 미설정")
    if not OHLCV_PATH.exists():
        sys.exit(f"{OHLCV_PATH} 없음")

    print(f"daily_ohlcv 로드 ({OHLCV_PATH.stat().st_size/1e6:.0f}MB)", flush=True)
    ohlcv = json.loads(OHLCV_PATH.read_text(encoding="utf-8"))

    # 전일 거래대금 TOP 500
    candidates = []
    for code, info in ohlcv.items():
        if len(code) != 6 or not code.isdigit():
            continue
        bars = info.get("bars", [])
        if not bars:
            continue
        tv = int(bars[-1].get("acml_tr_pbmn", 0))
        last = bars[-1].get("stck_bsop_date", "")
        if tv > 0:
            candidates.append({"code": code, "tv": tv, "last_date": last})
    candidates.sort(key=lambda x: -x["tv"])
    targets = candidates[:500]
    print(f"대상: {len(targets)}종목 (전일 TV TOP 500)", flush=True)

    today = datetime.now(KST).strftime("%Y%m%d")
    updated = errors = skipped = 0

    async with aiohttp.ClientSession() as session:
        token = await get_token(session)
        print(f"token 발급 OK", flush=True)

        for i, t in enumerate(targets):
            code = t["code"]
            if t["last_date"] >= today:
                skipped += 1
                continue
            try:
                bars = await fetch_daily(session, token, code)
                if not bars:
                    errors += 1
                    continue
                existing = {b["stck_bsop_date"] for b in ohlcv[code]["bars"]}
                added = 0
                for b in bars:
                    d = b.get("stck_bsop_date", "")
                    if d and d not in existing:
                        ohlcv[code]["bars"].append(b)
                        existing.add(d)
                        added += 1
                if added > 0:
                    ohlcv[code]["bars"].sort(key=lambda x: x.get("stck_bsop_date", ""))
                    updated += 1
                # rate limit (실투자 초당 20건)
                await asyncio.sleep(0.06)
                if (i + 1) % 50 == 0:
                    print(f"진행 {i+1}/{len(targets)} (갱신 {updated}, 에러 {errors}, skip {skipped})", flush=True)
                # 100종목마다 중간 저장
                if updated > 0 and (i + 1) % 100 == 0:
                    OHLCV_PATH.write_text(json.dumps(ohlcv, ensure_ascii=False), encoding="utf-8")
                    print(f"  중간 저장: {i+1}/{len(targets)}", flush=True)
            except asyncio.TimeoutError:
                errors += 1
                print(f"  {code} timeout (10s)", flush=True)
            except Exception as e:
                errors += 1
                print(f"  {code} error: {type(e).__name__}: {e}", flush=True)

    OHLCV_PATH.write_text(json.dumps(ohlcv, ensure_ascii=False), encoding="utf-8")
    print(f"완료: 갱신 {updated}, 에러 {errors}, skip {skipped}, 파일 {OHLCV_PATH.stat().st_size/1e6:.0f}MB", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
