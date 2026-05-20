#!/usr/bin/env python3
"""SK하이닉스 4지표 실측 검증 — MTS 이미지(2026-05-20 11:24)와 KIS 응답 비교.

목적:
1. acml_tr_pbmn / acml_vol 단위·공식 정확성 확인 (VWAP)
2. UN vs J 거래량 차이 → NXT 상장 여부 확인
3. 5/19 일봉을 UN/J 양쪽 조회해서 history(volume_30d_history.json) 마지막값이 어느 쪽인지 식별
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, ".")

from daemon.trader import _ensure_mock_token, KIS_MOCK_BASE_URL, _order_headers, get_session

KST = ZoneInfo("Asia/Seoul")
CODE = "000660"


async def _get(url: str, params: dict, token: str, tr_id: str) -> dict | None:
    session = await get_session()
    for attempt in range(3):
        async with session.get(url, params=params, headers=_order_headers(token, tr_id)) as resp:
            data = await resp.json()
            if data.get("rt_cd") == "0":
                return data
            if "초과" in (data.get("msg1") or "") and attempt < 2:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            print(f"  [{tr_id} {params.get('FID_COND_MRKT_DIV_CODE')}] rt_cd={data.get('rt_cd')} msg={data.get('msg1')}")
            return None
    return None


async def fetch_price(token: str, code: str, market_div: str) -> dict | None:
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    params = {"FID_COND_MRKT_DIV_CODE": market_div, "FID_INPUT_ISCD": code}
    d = await _get(url, params, token, "FHKST01010100")
    return d.get("output") if d else None


async def fetch_daily(token: str, code: str, market_div: str) -> list[dict]:
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-price"
    params = {
        "FID_COND_MRKT_DIV_CODE": market_div, "FID_INPUT_ISCD": code,
        "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "0",
    }
    d = await _get(url, params, token, "FHKST01010400")
    return d.get("output", []) if d else []


async def main():
    token = await _ensure_mock_token()
    if not token:
        sys.exit("KIS 모의투자 토큰 획득 실패")

    # 1) 현재가 — UN
    out_un = await fetch_price(token, CODE, "UN")
    out_j = await fetch_price(token, CODE, "J")
    if not out_un:
        sys.exit("UN inquire-price 실패")

    name = out_un.get("hts_kor_isnm", "") or "(미정)"
    price = int(out_un.get("stck_prpr", "0") or "0")
    vol_un = int(out_un.get("acml_vol", "0") or "0")
    tv_un = int(out_un.get("acml_tr_pbmn", "0") or "0")
    vol_j = int(out_j.get("acml_vol", "0") or "0") if out_j else 0

    now = datetime.now(KST)
    elapsed = max(1, min(390, now.hour * 60 + now.minute - 540))

    # 2) 일봉 — UN/J 양쪽
    daily_un = await fetch_daily(token, CODE, "UN")
    daily_j = await fetch_daily(token, CODE, "J")

    def vol_for_date(bars: list[dict], yyyymmdd: str) -> int:
        for b in bars:
            if b.get("stck_bsop_date") == yyyymmdd:
                return int(b.get("acml_vol", 0) or 0)
        return 0

    HIST_LAST = 7_805_248  # volume_30d_history['000660'][-1] (5/19)
    AVG20D = 9_007_560

    v_un_519 = vol_for_date(daily_un, "20260519")
    v_j_519 = vol_for_date(daily_j, "20260519")

    # 4지표 산출
    vwap = tv_un / vol_un if vol_un > 0 else 0

    print(f"\n=== KIS 실측 (시각 {now.strftime('%H:%M:%S')} KST, elapsed={elapsed}분) ===")
    print(f"종목: {name} ({CODE}) / 현재가: {price:,}원")
    print(f"거래량 UN={vol_un:,} / J={vol_j:,} / UN-J={vol_un - vol_j:,} ({(vol_un - vol_j) / max(vol_j, 1) * 100:.1f}% NXT 비중 추정)")
    print(f"거래대금 (UN): {tv_un:,}원 = {tv_un/1e12:.4f}조원")
    print(f"VWAP = {vwap:,.2f}원 (단위: 원/주)")

    print(f"\n=== 5/19 일봉 — history 마지막값 출처 식별 ===")
    print(f"history 마지막값 (5/19): {HIST_LAST:,} 주")
    print(f"KIS 5/19 일봉 UN: {v_un_519:,} 주  → history와 일치: {v_un_519 == HIST_LAST}")
    print(f"KIS 5/19 일봉 J:  {v_j_519:,} 주   → history와 일치: {v_j_519 == HIST_LAST}")
    if v_un_519 == HIST_LAST:
        print("  → history는 UN 기반 ✓ (분자=UN과 일치)")
    elif v_j_519 == HIST_LAST:
        print("  → history는 J 기반 ✗ (분자=UN과 불일치, RVOL/30일순위 과대평가 가능)")
    else:
        print("  → history는 둘 다 불일치 (다른 출처? 추가 조사 필요)")

    # avg20d 분석
    if daily_un:
        un_20 = [int(b.get("acml_vol", 0) or 0) for b in daily_un[:20]]
        un_20 = [v for v in un_20 if v > 0]
        avg_un = sum(un_20) // len(un_20) if un_20 else 0
    else:
        avg_un = 0
    if daily_j:
        j_20 = [int(b.get("acml_vol", 0) or 0) for b in daily_j[:20]]
        j_20 = [v for v in j_20 if v > 0]
        avg_j = sum(j_20) // len(j_20) if j_20 else 0
    else:
        avg_j = 0
    print(f"\nKIS 직접산출 avg20d UN={avg_un:,} / J={avg_j:,}")
    print(f"저장된 avg20d = {AVG20D:,}")
    print(f"  UN avg 매치: {abs(avg_un - AVG20D) < AVG20D * 0.03}")
    print(f"  J avg 매치:  {abs(avg_j - AVG20D) < AVG20D * 0.03}")

    snapshot = {
        "timestamp": now.isoformat(), "code": CODE, "name": name,
        "kis_now": {"price": price, "vol_un": vol_un, "vol_j": vol_j, "trading_value": tv_un, "vwap": vwap},
        "daily_519": {"un": v_un_519, "j": v_j_519, "history_value": HIST_LAST},
        "avg20d_check": {"saved": AVG20D, "kis_un": avg_un, "kis_j": avg_j},
    }
    out_path = "docs/research/2026-05-20-sk-verification.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {out_path}")


asyncio.run(main())
