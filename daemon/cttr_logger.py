"""09:05 매수 후보의 매수/매도 압력 지표 로깅 — 2주 누적 후 cttr 필터 실효성 검증용.

수집 지표 (학술적 OFI 등가물):
- ofi_ratio: 매수호가잔량 / 매도호가잔량 (>1 매수우세, <1 매도우세)
- ntby_aspr: 순매수호가잔량 (음수면 매도우세)
- vol_tnrt: 거래량회전율
- price/change_rate/tv: 가격 + 등락률 + 거래대금

3시점 스냅샷 (09:05/09:10/09:15) → EOD에 final_pnl 추가
저장: results/cttr_log/YYYY-MM-DD.json
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))
LOG_DIR = Path(__file__).parent.parent / "results" / "cttr_log"


async def _fetch_pressure_snapshot(token: str, code: str) -> dict | None:
    """호가잔량 + 현재가 정보 조회 → 매수/매도 압력 지표 반환."""
    from daemon.trader import get_session, _order_headers
    from daemon.config import KIS_MOCK_BASE_URL
    try:
        session = await get_session()
        url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
        params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
        async with session.get(url, params=params, headers=_order_headers(token, "FHKST01010200")) as resp:
            data = await resp.json()
            if data.get("rt_cd") != "0":
                return None
            o1 = data.get("output1", {})
            o2 = data.get("output2", {})

            ask = int(o1.get("total_askp_rsqn", "0") or "0")
            bid = int(o1.get("total_bidp_rsqn", "0") or "0")
            ntby = int(o1.get("ntby_aspr_rsqn", "0") or "0")
            ratio = round(bid / ask, 3) if ask > 0 else 0
            return {
                "price": int(o2.get("stck_prpr", "0") or "0"),
                "change_rate": float(o2.get("antc_cntg_prdy_ctrt", "0") or "0"),
                "ask_qty": ask,
                "bid_qty": bid,
                "ntby_aspr": ntby,
                "ofi_ratio": ratio,  # >1: 매수우세, <1: 매도우세
            }
    except Exception as e:
        logger.warning(f"압력 조회 오류 ({code}): {e}")
        return None


async def log_snapshot(candidates: list[dict], snapshot_time: str) -> None:
    """후보 종목들의 압력 스냅샷 기록.
    candidates: [{"code", "name", "selected" (bool)}, ...]
    snapshot_time: "0905" | "0910" | "0915"
    """
    from daemon.trader import _ensure_mock_token
    if not candidates:
        return
    token = await _ensure_mock_token()
    if not token:
        logger.warning(f"cttr_log [{snapshot_time}] 토큰 없음")
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(_KST).strftime("%Y-%m-%d")
    log_path = LOG_DIR / f"{today}.json"

    # 기존 데이터 로드 (없으면 신규)
    if log_path.exists():
        with open(log_path, encoding="utf-8") as f:
            log_data = json.load(f)
    else:
        log_data = {"date": today, "candidates": {}}

    # 각 후보별 스냅샷
    for c in candidates:
        code = c["code"]
        if code not in log_data["candidates"]:
            log_data["candidates"][code] = {
                "name": c.get("name", code),
                "selected": c.get("selected", False),
                "snapshots": {},
                "final_pnl_pct": None,
            }
        snap = await _fetch_pressure_snapshot(token, code)
        if snap:
            log_data["candidates"][code]["snapshots"][snapshot_time] = snap
        await asyncio.sleep(0.15)

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

    logger.info(f"cttr_log [{snapshot_time}] {len(candidates)}종목 기록 ({log_path.name})")


async def update_final_pnl() -> None:
    """EOD에 호출 — 당일 로그의 final_pnl_pct를 채움."""
    from daemon.trader import _ensure_mock_token, get_session, _order_headers
    from daemon.config import KIS_MOCK_BASE_URL
    today = datetime.now(_KST).strftime("%Y-%m-%d")
    log_path = LOG_DIR / f"{today}.json"
    if not log_path.exists():
        return

    token = await _ensure_mock_token()
    if not token:
        return

    with open(log_path, encoding="utf-8") as f:
        log_data = json.load(f)

    session = await get_session()
    for code, info in log_data.get("candidates", {}).items():
        # 09:05 시점 가격 기준 → 현재 종가 수익률 계산
        snaps = info.get("snapshots", {})
        entry = snaps.get("0905", {}).get("price", 0) if snaps else 0
        if entry <= 0:
            continue
        try:
            url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
            params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
            async with session.get(url, params=params, headers=_order_headers(token, "FHKST01010100")) as resp:
                d = await resp.json()
                if d.get("rt_cd") == "0":
                    cl = int(d.get("output", {}).get("stck_prpr", "0") or "0")
                    if cl > 0:
                        info["final_pnl_pct"] = round((cl - entry) / entry * 100, 2)
        except Exception as e:
            logger.warning(f"final_pnl 조회 오류 ({code}): {e}")
        await asyncio.sleep(0.15)

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

    logger.info(f"cttr_log final_pnl 업데이트: {log_path.name}")
