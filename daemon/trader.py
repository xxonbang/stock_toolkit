"""KIS 모의투자 자동매매 — 매수/매도 주문 + 수익률 감시"""
import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from daemon.config import (
    KIS_MOCK_APP_KEY, KIS_MOCK_APP_SECRET, KIS_MOCK_ACCOUNT_NO, KIS_MOCK_BASE_URL,
    TRADE_TAKE_PROFIT_PCT, TRADE_STOP_LOSS_PCT, TRADE_TRAILING_STOP_PCT, TRADE_MIN_AMOUNT_PER_STOCK,
    DATA_BASE_URL,
)
from daemon.position_db import (
    is_already_held_or_ordered, insert_buy_order, update_position_filled,
    update_position_sold, update_position_quantity, get_active_positions,
    calc_quantity, calc_pnl_pct,
    is_selling, mark_selling, unmark_selling, try_mark_selling,
)
from daemon.notifier import send_telegram
from daemon.stock_manager import fetch_json, fetch_alert_config
from daemon.http_session import get_session

logger = logging.getLogger("daemon.trader")

BUY_SIGNALS = {"적극매수", "매수"}

# 종목별 고점 추적 (trailing stop용)
_peak_prices: dict[str, int] = {}

_access_token = ""
_token_issued_at: float = 0
_TOKEN_TTL = 3500  # KIS 토큰 유효기간 ~1시간, 여유 두고 58분
_RATE_LIMIT_RETRIES = 3  # rate limit 재시도 횟수
_RATE_LIMIT_BASE_SEC = 2  # 재시도 기본 대기 (2, 4, 6초)


async def _ensure_mock_token() -> str | None:
    """모의투자 토큰 발급 — 만료 시 자동 재발급"""
    global _access_token, _token_issued_at
    now = time.time()
    if _access_token and (now - _token_issued_at) < _TOKEN_TTL:
        return _access_token
    # 재발급
    _access_token = ""
    url = f"{KIS_MOCK_BASE_URL}/oauth2/tokenP"
    body = {
        "grant_type": "client_credentials",
        "appkey": KIS_MOCK_APP_KEY,
        "appsecret": KIS_MOCK_APP_SECRET,
    }
    try:
        session = await get_session()
        async with session.post(url, json=body) as resp:
            if resp.status == 200:
                data = await resp.json()
                _access_token = data.get("access_token", "")
                _token_issued_at = now
                logger.info("모의투자 토큰 발급 완료")
                return _access_token
    except Exception as e:
        logger.error(f"모의투자 토큰 발급 실패: {e}")
    return None


def _order_headers(token: str, tr_id: str) -> dict:
    return {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": KIS_MOCK_APP_KEY,
        "appsecret": KIS_MOCK_APP_SECRET,
        "tr_id": tr_id,
        "custtype": "P",
    }


_KST = timezone(timedelta(hours=9))


def _calc_hold_days(pos: dict) -> int:
    """포지션의 보유 거래일수 계산 (주말/공휴일 제외, KST 기준)"""
    created = pos.get("filled_at") or pos.get("created_at", "")
    if not created:
        return 0
    try:
        from daemon.main import _get_holidays
        created_date = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(_KST).date()
        today = datetime.now(_KST).date()
        if created_date >= today:
            return 0
        count = 0
        d = created_date + timedelta(days=1)
        while d <= today:
            if d.weekday() < 5 and d.strftime("%m-%d") not in _get_holidays(d.year):
                count += 1
            d += timedelta(days=1)
        return count
    except Exception:
        return 0


def _parse_account() -> tuple[str, str]:
    """KIS_MOCK_ACCOUNT_NO를 (CANO, ACNT_PRDT_CD) 튜플로 파싱"""
    parts = KIS_MOCK_ACCOUNT_NO.split("-") if "-" in KIS_MOCK_ACCOUNT_NO else [KIS_MOCK_ACCOUNT_NO[:8], KIS_MOCK_ACCOUNT_NO[8:]]
    return parts[0], parts[1] if len(parts) > 1 else "01"


def filter_high_confidence(signals: list | None, mode: str = "and") -> list[dict]:
    """매수 종목 필터. mode: 콤마 구분 토글 ('chart,indicator,top_leader') 또는 레거시."""
    if not signals or mode == "none":
        return []
    # 레거시 모드 → 토글 플래그 변환
    if mode == "and":
        flags = {"chart", "indicator"}
    elif mode == "or":
        return [s for s in signals if s.get("vision_signal") in BUY_SIGNALS or s.get("api_signal") in BUY_SIGNALS]
    elif mode == "leader":
        flags = {"all_leaders"}
    else:
        flags = set(mode.split(","))
    # top_leader: 대장주(theme 보유) 중 테마별 거래대금 1위 코드 집합 산출
    top_codes: set[str] | None = None
    if "top_leader" in flags:
        theme_best: dict[str, tuple[str, int]] = {}  # theme → (code, volume)
        for s in signals:
            theme = s.get("theme")
            if not theme:
                continue  # 대장주가 아닌 종목은 top_leader 대상 아님
            vol = (s.get("api_data") or {}).get("ranking", {}).get("volume", 0)
            if theme not in theme_best or vol > theme_best[theme][1]:
                theme_best[theme] = (s.get("code", ""), vol)
        top_codes = {code for code, _ in theme_best.values()}
    # all_leaders: theme 필드가 있는 종목만 (대장주)
    need_all_leaders = "all_leaders" in flags
    # 시그널 + 대장주 조건 AND 필터
    need_chart = "chart" in flags
    need_indicator = "indicator" in flags
    return [
        s for s in signals
        if (not need_chart or s.get("vision_signal") in BUY_SIGNALS)
        and (not need_indicator or s.get("api_signal") in BUY_SIGNALS)
        and (top_codes is None or s.get("code", "") in top_codes)
        and (not need_all_leaders or s.get("theme"))
    ]


def _load_ma200_cache() -> dict[str, float]:
    """종목별 MA200 캐시 로드 (ma200_cache.json 우선, 없으면 daily_ohlcv_all.json에서 계산)"""
    import json
    from pathlib import Path
    cache_attr = "_ma200_cache"
    if hasattr(_load_ma200_cache, cache_attr):
        return getattr(_load_ma200_cache, cache_attr)
    result = {}
    # 1순위: 가벼운 캐시 파일 (48KB)
    cache_path = Path(__file__).parent / "ma200_cache.json"
    if cache_path.exists():
        try:
            with open(cache_path, encoding="utf-8") as f:
                result = json.load(f)
            setattr(_load_ma200_cache, cache_attr, result)
            return result
        except Exception:
            pass
    # 2순위: 전체 데이터에서 계산 (353MB)
    path = Path(__file__).parent.parent / "results" / "daily_ohlcv_all.json"
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for code, info in data.items():
                bars = info.get("bars", [])
                if len(bars) < 200:
                    continue
                closes = [int(b.get("stck_clpr", "0")) for b in bars[-200:]]
                closes = [c for c in closes if c > 0]
                if len(closes) >= 200:
                    result[code] = sum(closes) / len(closes)
        except Exception:
            pass
    setattr(_load_ma200_cache, cache_attr, result)
    return result


def select_gapup_momentum(signals: list | None, top_n: int = 2) -> list[dict]:
    """갭업 모멘텀 전략: 갭업 2~5% + MA200 위 + 거래량 2배 종목 선정.
    시가 매수 → 당일 종가 매도 (schedule_eod_close에서 처리).
    """
    if not signals:
        return []
    ma200_map = _load_ma200_cache()
    candidates = []
    for s in signals:
        code = s.get("code", "")
        api_data = s.get("api_data") or {}
        price_data = api_data.get("price", {})
        ranking = api_data.get("ranking", {})

        current = price_data.get("current", 0)
        prev_close = price_data.get("prev_close", 0)
        open_price = price_data.get("open", 0) or current
        volume = ranking.get("volume", 0)
        volume_rate = ranking.get("volume_rate_vs_prev", 0)

        if current <= 0 or prev_close <= 0:
            continue
        if current < 1000 or current >= 200000:
            continue

        # 갭업 계산: 시가 대비 전일종가
        gap_pct = (open_price - prev_close) / prev_close * 100 if prev_close > 0 and open_price > 0 else 0

        # MA200 필터: daily_ohlcv_all.json에서 계산된 값 사용
        ma200 = ma200_map.get(code, 0)
        if ma200 > 0 and current <= ma200:
            continue  # MA200 아래면 제외

        # 거래량 조건: volume_rate_vs_prev >= 200 (전일 대비 2배)
        vol_ok = volume_rate >= 200 or volume > 500000

        if 2 <= gap_pct < 5 and vol_ok:
            candidates.append({
                **s,
                "_gap_pct": round(gap_pct, 2),
                "_score": round(gap_pct * 10, 1),
                "_score_detail": [f"갭업+{gap_pct:.1f}%", f"거래량{volume_rate:.0f}%", f"MA200>{ma200:,.0f}" if ma200 > 0 else "MA200?"],
            })

    # 거래량 순 정렬
    candidates.sort(key=lambda x: -(x.get("api_data") or {}).get("ranking", {}).get("volume", 0))
    return candidates[:top_n]


def select_research_optimal(signals: list | None, max_price: int = 50000, top_n: int = 2, min_score: int = 20, criteria_filter: bool = False) -> list[dict]:
    """연구 최적 전략: 5팩터 스코어링으로 Top-N 종목 선정.
    팩터: api매수(30) + api적극매수(+10) + vision매수(20) + vision적극매수(+5)
          + 대장주1등(25)/전체(15) + 저가주<2만(5)
          + 급락반등(≤-10%&외국인50만주+)(+35)
    criteria_filter=True: 수급+10, 골든크로스+5, 저항돌파+5 가점 적용
    가격 < max_price 필터, 최소 min_score점, 상위 top_n개 반환.
    """
    if not signals:
        return []

    # 대장주 1등 코드 집합 산출 (theme별 거래대금 1위)
    theme_best: dict[str, tuple[str, int]] = {}
    for s in signals:
        theme = s.get("theme")
        if not theme:
            continue
        vol = (s.get("api_data") or {}).get("ranking", {}).get("volume", 0)
        if theme not in theme_best or vol > theme_best[theme][1]:
            theme_best[theme] = (s.get("code", ""), vol)
    top1_codes = {code for code, _ in theme_best.values()}

    scored = []
    for s in signals:
        code = s.get("code", "")
        price = (s.get("api_data") or {}).get("price", {}).get("current", 0)
        if price <= 0 or price >= max_price or price < 1000:
            continue

        score = 0
        details = []
        # 팩터 1: api 매수 신호
        api_sig = s.get("api_signal", "")
        if api_sig in BUY_SIGNALS:
            score += 30
            details.append(f"API매수+30")
            if api_sig == "적극매수":
                score += 10
                details.append(f"적극매수+10")
        # 팩터 2: vision 매수 신호
        vis_sig = s.get("vision_signal", "")
        if vis_sig in BUY_SIGNALS:
            score += 20
            details.append(f"Vision매수+20")
            if vis_sig == "적극매수":
                score += 5
                details.append(f"적극매수+5")
        # 팩터 3: 대장주
        if code in top1_codes:
            score += 25
            details.append(f"대장주1등+25")
        elif s.get("theme"):
            score += 15
            details.append(f"테마소속+15")
        # 팩터 4: 저가주
        if price < 20000:
            score += 5
            details.append(f"저가주+5")
        # 팩터 5: 급락반등 (≤-10% 급락 + 외국인 50만주+ 매집)
        change_rate = (s.get("api_data") or {}).get("price", {}).get("change_rate_pct", 0)
        foreign_net = (s.get("intraday") or {}).get("foreign_net", 0)
        if change_rate <= -10 and foreign_net >= 500_000:
            score += 35
            details.append(f"급락반등+35({change_rate:+.1f}%,외인{foreign_net/10000:.0f}만주)")

        if score >= min_score:
            scored.append({**s, "_score": score, "_score_detail": details})

    # criteria_filter 적용: 가점만 (감점은 백테스트 v2에서 일관 역효과 확인 → 제거)
    if criteria_filter:
        for item in scored:
            if item.get("_supply_demand"):
                item["_score"] += 10
                item.setdefault("_score_detail", []).append("수급양호+10")
            if item.get("_golden_cross"):
                item["_score"] += 5
                item.setdefault("_score_detail", []).append("골든크로스+5")
            if item.get("_resistance_breakout"):
                item["_score"] += 5
                item.setdefault("_score_detail", []).append("저항돌파+5")

    def _sort_key(x):
        ad = x.get("api_data") or {}
        return (
            -x["_score"],
            -(ad.get("ranking") or {}).get("volume", 0),
            -(ad.get("price") or {}).get("change_rate_pct", 0),
            (ad.get("price") or {}).get("current", 0),
        )
    scored.sort(key=_sort_key)
    return scored[:top_n]


def should_sell(buy_price: int, current_price: int, take_profit: float = TRADE_TAKE_PROFIT_PCT, stop_loss: float = TRADE_STOP_LOSS_PCT) -> str | None:
    pnl = calc_pnl_pct(buy_price, current_price)
    if pnl >= take_profit:
        return "take_profit"
    if pnl <= stop_loss:
        return "stop_loss"
    return None


# Stepped Trailing 프리셋
_STEPPED_PRESETS = {
    "default": [
        (25.0, None),   # +25%+ → peak - trailing_pct (동적)
        (20.0, 15.0),   # +20% 도달 → stop +15%
        (15.0, 10.0),   # +15% 도달 → stop +10%
        (10.0, 5.0),    # +10% 도달 → stop +5%
        (5.0, 0.0),     # +5% 도달 → stop 0% (본전)
    ],
    "aggressive": [
        (30.0, None),   # +30%+ → peak - trailing_pct (동적)
        (25.0, 20.0),   # +25% 도달 → stop +20%
        (20.0, 15.0),   # +20% 도달 → stop +15%
        (15.0, 7.0),    # +15% 도달 → stop +7%
        (7.0, 0.0),     # +7% 도달 → stop 0% (본전)
    ],
}


def calc_stepped_stop_pct(peak_pnl_pct: float, trailing_pct: float, preset: str = "default") -> float:
    """Stepped Trailing: 고점 수익률 기반 stop 위치 계산.
    peak_pnl_pct: 매수가 대비 고점 수익률 (%)
    trailing_pct: trailing stop % (음수, 기본 -3.0)
    preset: "default" 또는 "aggressive"
    Returns: stop 수익률 (%, 이 아래로 내려가면 매도)
    """
    levels = _STEPPED_PRESETS.get(preset, _STEPPED_PRESETS["default"])
    for level, stop in levels:
        if peak_pnl_pct >= level:
            if stop is None:
                return peak_pnl_pct + trailing_pct
            return stop
    return -999.0  # step 미도달 → stepped stop 미작동, 기본 SL만 적용


async def _kis_order(tr_id: str, code: str, quantity: int, price: int, retry: bool = True) -> dict | None:
    """KIS 모의투자 주문 공통 — 토큰 만료 시 1회 재시도"""
    token = await _ensure_mock_token()
    if not token:
        return None
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/order-cash"
    cano, acnt_cd = _parse_account()
    body = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_cd,
        "PDNO": code,
        "ORD_DVSN": "00",
        "ORD_QTY": str(quantity),
        "ORD_UNPR": str(price),
    }
    try:
        session = await get_session()
        async with session.post(url, json=body, headers=_order_headers(token, tr_id)) as resp:
            data = await resp.json()
            if data.get("rt_cd") == "0":
                return data
            msg = data.get("msg1", "")
            if retry and ("만료" in msg or "token" in msg.lower()):
                logger.warning(f"KIS 토큰 만료 — 재발급 후 재시도")
                _reset_token()
                await asyncio.sleep(1)
                return await _kis_order(tr_id, code, quantity, price, retry=False)
            logger.error(f"KIS 주문 실패 ({tr_id}): {msg}")
    except Exception as e:
        logger.error(f"KIS 주문 오류 ({tr_id}): {e}")
    return None


async def is_upper_limit(code: str, price: int) -> bool:
    """현재가가 상한가인지 확인 (rate limit 시 재시도)"""
    token = await _ensure_mock_token()
    if not token:
        return False
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    for attempt in range(1, _RATE_LIMIT_RETRIES + 1):
        try:
            session = await get_session()
            async with session.get(url, params=params, headers=_order_headers(token, "FHKST01010100")) as resp:
                data = await resp.json()
                if data.get("rt_cd") == "0":
                    upper = int(data.get("output", {}).get("stck_mxpr", "0"))
                    if upper > 0 and price >= upper:
                        return True
                    return False
                msg = data.get("msg1", "")
                if "초과" in msg and attempt < _RATE_LIMIT_RETRIES:
                    await asyncio.sleep(attempt * _RATE_LIMIT_BASE_SEC)
                    continue
        except Exception as e:
            if attempt < _RATE_LIMIT_RETRIES:
                await asyncio.sleep(attempt * _RATE_LIMIT_BASE_SEC)
                continue
            logger.warning(f"상한가 조회 오류 ({code}): {e}")
    return False


_MAX_FILL_RETRIES = 3


async def _get_actual_fill_price(code: str, is_sell: bool = False) -> int:
    """KIS 일별주문체결조회로 실제 체결 단가 조회. 실패 시 0 반환."""
    token = await _ensure_mock_token()
    if not token:
        return 0
    cano, acnt_cd = _parse_account()
    today = datetime.now(_KST).strftime("%Y%m%d")
    sll_buy = "01" if is_sell else "02"
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
    params = {
        "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
        "INQR_STRT_DT": today, "INQR_END_DT": today,
        "SLL_BUY_DVSN_CD": sll_buy, "INQR_DVSN": "00",
        "PDNO": "", "CCLD_DVSN": "00",
        "ORD_GNO_BRNO": "", "ODNO": "",
        "INQR_DVSN_3": "00", "INQR_DVSN_1": "",
        "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
    }
    try:
        session = await get_session()
        async with session.get(url, params=params, headers=_order_headers(token, "VTTC8001R")) as resp:
            data = await resp.json()
            if data.get("rt_cd") != "0":
                logger.debug(f"체결가 조회 실패: {code} rt_cd={data.get('rt_cd')} {data.get('msg1', '')}")
                return 0
            for order in data.get("output1", []):
                if order.get("pdno") != code:
                    continue
                avg_price = int(order.get("avg_prvs", "0") or "0")
                if avg_price > 0:
                    return avg_price
                fill_price = int(order.get("ccld_prc", "0") or "0")
                if fill_price > 0:
                    return fill_price
    except Exception as e:
        logger.debug(f"체결가 조회 오류: {code} {e}")
    # fallback: 잔고 조회 API의 매수 평균단가
    try:
        balance_price = await _get_balance_avg_price(code)
        if balance_price > 0:
            logger.info(f"체결가 잔고 fallback: {code} {balance_price:,}원")
            return balance_price
    except Exception:
        pass
    return 0


async def _get_balance_avg_price(code: str) -> int:
    """잔고 조회 API에서 특정 종목의 매수 평균단가 조회"""
    try:
        token = await _ensure_mock_token()
        if not token:
            return 0
        session = await get_session()
        acnt = KIS_MOCK_ACCOUNT_NO.split("-")
        url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance"
        headers = {
            "authorization": f"Bearer {token}",
            "appkey": KIS_MOCK_APP_KEY, "appsecret": KIS_MOCK_APP_SECRET,
            "tr_id": "VTTC8434R", "content-type": "application/json; charset=utf-8",
        }
        params = {
            "CANO": acnt[0], "ACNT_PRDT_CD": acnt[1] if len(acnt) > 1 else "01",
            "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02", "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N", "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "00",
            "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
        }
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                for item in data.get("output1", []):
                    if item.get("pdno") == code:
                        avg = item.get("pchs_avg_pric", "0")
                        return int(float(avg))
    except Exception as e:
        logger.warning(f"잔고 평단가 조회 실패: {code} {e}")
    return 0


async def _cancel_unfilled(code: str, is_sell: bool = False) -> int | None:
    """KIS 미체결 조회 → 해당 종목 미체결분 취소, 미체결 수량 반환. 조회 실패 시 None."""
    sll_buy = "01" if is_sell else "02"
    label = "매도 " if is_sell else ""
    token = await _ensure_mock_token()
    if not token:
        return None
    cano, acnt_cd = _parse_account()
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-nccs"
    params = {
        "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
        "INQR_STRT_DT": "", "INQR_END_DT": "",
        "SLL_BUY_DVSN_CD": sll_buy, "INQR_DVSN": "00",
        "PDNO": "", "CCLD_DVSN": "01",
        "ORD_GNO_BRNO": "", "ODNO": "",
        "INQR_DVSN_3": "00", "INQR_DVSN_1": "",
        "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
    }
    unfilled_qty = 0
    try:
        session = await get_session()
        async with session.get(url, params=params, headers=_order_headers(token, "VTTC8001R")) as resp:
            data = await resp.json()
            if data.get("rt_cd") != "0":
                return None
            for order in data.get("output", []):
                if order.get("pdno") != code:
                    continue
                rmn = int(order.get("rmn_qty", "0") or "0")
                if rmn <= 0:
                    continue
                unfilled_qty += rmn
                odno = order.get("odno", "")
                if odno:
                    cancel_url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/order-rvsecncl"
                    cancel_body = {
                        "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
                        "KRX_FWDG_ORD_ORGNO": "", "ORGN_ODNO": odno,
                        "ORD_DVSN": "00", "RVSE_CNCL_DVSN_CD": "02",
                        "ORD_QTY": str(rmn), "ORD_UNPR": "0", "QTY_ALL_ORD_YN": "Y",
                    }
                    async with session.post(cancel_url, json=cancel_body, headers=_order_headers(token, "VTTC0803U")) as cresp:
                        cdata = await cresp.json()
                        if cdata.get("rt_cd") == "0":
                            logger.info(f"{label}미체결 취소: {code} 잔여 {rmn}주")
                        else:
                            logger.warning(f"{label}미체결 취소 실패: {code} {cdata.get('msg1', '')}")
                    await asyncio.sleep(0.3)
    except Exception as e:
        logger.error(f"{label}미체결 조회/취소 오류: {e}")
        return None
    return unfilled_qty


async def _verify_sell_fill(code: str, ordered_qty: int) -> int:
    """매도 주문 후 체결 확인 → 미체결분 취소 후 재주문, 최대 3회 retry.
    API 조회 실패 시 체결 0주로 보수적 간주 (실투자 대비)."""
    total_filled = 0
    remaining = ordered_qty
    api_fail_count = 0
    for attempt in range(1, _MAX_FILL_RETRIES + 1):
        await asyncio.sleep(1)
        unfilled = await _cancel_unfilled(code, is_sell=True)
        if unfilled is None:
            api_fail_count += 1
            logger.warning(f"매도 미체결 조회 실패 ({api_fail_count}회): {code} — 재시도")
            if attempt < _MAX_FILL_RETRIES:
                continue  # API 실패 시 재시도
            else:
                # 최종 실패: 보수적으로 체결 0주 간주 (호출자가 재처리)
                logger.warning(f"매도 미체결 조회 {_MAX_FILL_RETRIES}회 연속 실패: {code} — 체결 0주 간주")
                return total_filled
        filled_this_round = remaining - unfilled
        total_filled += filled_this_round
        if unfilled == 0:
            break  # 전량 체결
        remaining = unfilled
        if attempt < _MAX_FILL_RETRIES:
            logger.info(f"매도 미체결 재주문 ({attempt}/{_MAX_FILL_RETRIES}): {code} {remaining}주")
            result = await _kis_order_market("VTTC0801U", code, remaining)
            if not result:
                logger.warning(f"매도 재주문 실패: {code} {remaining}주")
                break
        else:
            logger.info(f"매도 최대 재시도 도달: {code} 최종 체결 {total_filled}주 / 주문 {ordered_qty}주")
    if total_filled != ordered_qty:
        logger.warning(f"매도 부분체결: {code} 주문 {ordered_qty}주 → 체결 {total_filled}주")
    return total_filled


async def _check_balance_qty(code: str) -> int:
    """KIS 잔고 조회 API로 특정 종목 보유 수량 확인 (미체결 조회 실패 시 fallback)"""
    try:
        token = await _ensure_mock_token()
        if not token:
            return 0
        session = await get_session()
        acnt = KIS_MOCK_ACCOUNT_NO.split("-")
        url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance"
        headers = {
            "authorization": f"Bearer {token}",
            "appkey": KIS_MOCK_APP_KEY, "appsecret": KIS_MOCK_APP_SECRET,
            "tr_id": "VTTC8434R", "content-type": "application/json; charset=utf-8",
        }
        params = {
            "CANO": acnt[0], "ACNT_PRDT_CD": acnt[1] if len(acnt) > 1 else "01",
            "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02", "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N", "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "00",
            "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
        }
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                for item in data.get("output1", []):
                    if item.get("pdno") == code:
                        return int(item.get("hldg_qty", 0))
    except Exception as e:
        logger.warning(f"잔고 조회 실패: {code} {e}")
    return 0


async def _verify_fill_with_retry(code: str, ordered_qty: int) -> int:
    """주문 후 체결 확인 → 미체결분 취소 후 재주문, 최대 3회 retry.
    API 조회 실패 시 체결 0주로 보수적 간주 (실투자 대비)."""
    total_filled = 0
    remaining = ordered_qty
    api_fail_count = 0
    for attempt in range(1, _MAX_FILL_RETRIES + 1):
        await asyncio.sleep(1)
        unfilled = await _cancel_unfilled(code)
        if unfilled is None:
            api_fail_count += 1
            logger.warning(f"미체결 조회 실패 ({api_fail_count}회): {code} — 재시도")
            if attempt < _MAX_FILL_RETRIES:
                continue
            else:
                logger.warning(f"미체결 조회 {_MAX_FILL_RETRIES}회 연속 실패: {code} — 체결 0주 간주")
                return total_filled
        filled_this_round = remaining - unfilled
        total_filled += filled_this_round
        if unfilled == 0:
            break  # 전량 체결
        remaining = unfilled
        if attempt < _MAX_FILL_RETRIES:
            logger.info(f"미체결 재주문 ({attempt}/{_MAX_FILL_RETRIES}): {code} {remaining}주")
            result = await _kis_order_market("VTTC0802U", code, remaining)
            if not result:
                logger.warning(f"재주문 실패: {code} {remaining}주")
                break
        else:
            logger.info(f"최대 재시도 도달: {code} 최종 체결 {total_filled}주 / 주문 {ordered_qty}주")
    if total_filled != ordered_qty:
        logger.info(f"체결 결과: {code} 주문 {ordered_qty}주 → 체결 {total_filled}주")
    return total_filled


async def place_buy_order_with_qty(code: str, name: str, price: int, quantity: int) -> bool:
    """수량을 직접 지정하여 시장가 매수 (미체결 방지)"""
    if await is_upper_limit(code, price):
        logger.info(f"상한가 종목 스킵 — {name}({code}) {price:,}원")
        return False
    position = await insert_buy_order(code, name, price, quantity)
    if not position:
        return False

    # 매수 전 기존 잔고 기록 (추가 매수 시 기존 보유분 차감용)
    pre_balance = await _check_balance_qty(code)

    # 시장가 매수 (지정가 미체결 방지)
    result = await _kis_order_market("VTTC0802U", code, quantity)
    if result:
        filled_qty = await _verify_fill_with_retry(code, quantity)
        if filled_qty <= 0:
            # 미체결 조회 실패 → 잔고 API로 실제 체결분 확인
            post_balance = await _check_balance_qty(code)
            if post_balance > pre_balance:
                filled_qty = post_balance - pre_balance
                logger.info(f"잔고 차분으로 체결 검증: {name}({code}) {filled_qty}주 (잔고 {pre_balance}→{post_balance})")
            elif post_balance > 0 and pre_balance == 0:
                filled_qty = min(post_balance, quantity)
                logger.info(f"잔고 확인으로 체결 검증: {name}({code}) {filled_qty}주")
            else:
                # 잔고에도 변화 없으면 시장가 즉시체결 간주 (최후 수단)
                filled_qty = quantity
                logger.warning(f"미체결+잔고 조회 모두 실패 → 즉시체결 간주: {name}({code}) {quantity}주")
        actual_price = await _get_actual_fill_price(code, is_sell=False)
        if actual_price <= 0:
            # 체결가 조회 실패 → 현재가를 fallback (주문가는 전일종가라 부정확)
            actual_price = await _get_current_price(code)
            if actual_price > 0:
                logger.info(f"체결가 조회 실패, 현재가 fallback: {name}({code}) {actual_price:,}원")
        fill_price = actual_price if actual_price > 0 else price
        await update_position_filled(position["id"], fill_price)
        if filled_qty != quantity:
            await update_position_quantity(position["id"], filled_qty)
        logger.info(f"매수 체결: {name}({code}) {fill_price:,}원 × {filled_qty}주 (시장가)")
        await send_telegram(
            f"<b>📥 자동 매수 체결</b>\n"
            f"<b>{name} ({code})</b>\n"
            f"가격: {fill_price:,}원 × {filled_qty}주\n"
            f"금액: {fill_price * filled_qty:,}원"
            + (f"\n⚠️ 부분체결 ({quantity}주 중 {filled_qty}주)" if filled_qty != quantity else "")
        )
        # 매수 직후 즉시 손절 체크 (WebSocket 구독 전 공백 제거)
        try:
            cur_price = await _get_current_price(code)
            if cur_price > 0:
                await check_positions_for_sell({"code": code, "price": cur_price})
        except Exception as e:
            logger.warning(f"매수 직후 손절 체크 오류: {e}")
        # 구독 갱신 (WebSocket 실시간 감시 시작)
        try:
            from daemon.main import trigger_subscription_refresh
            await trigger_subscription_refresh()
        except Exception as e:
            logger.warning(f"구독 갱신 실패: {e}")
        # 비선택 전략 가상 시뮬레이션 생성
        try:
            config = await _get_trade_config()
            active_strategy = config.get("strategy_type", "fixed")
            sim_strategy = "stepped" if active_strategy == "fixed" else "fixed"
            trade_id = position["id"]
            user_id = config.get("user_id") or ""
            if not user_id:
                logger.warning(f"가상 시뮬레이션 스킵: user_id 없음 (config)")
            else:
                asyncio.ensure_future(_create_simulation(
                    trade_id=trade_id,
                    strategy_type=sim_strategy,
                    entry_price=fill_price,
                    user_id=user_id,
                ))
                # 시간전략(11:00 매도) 시뮬레이션 — 11:00 이전 매수에서만 생성
                if datetime.now(_KST).hour < 11:
                    asyncio.ensure_future(_create_simulation(
                        trade_id=trade_id,
                        strategy_type="time_exit",
                        entry_price=fill_price,
                        user_id=user_id,
                    ))
        except Exception as e:
            logger.warning(f"가상 시뮬레이션 생성 호출 오류: {e}")
        return True
    # KIS 주문 실패 → DB pending 정리
    from daemon.position_db import delete_position
    await delete_position(position["id"])
    logger.warning(f"매수 실패 → pending 삭제: {name}({code})")
    return False


async def place_sell_order(code: str, name: str, price: int, quantity: int, position_id: str, reason: str, buy_price: int) -> bool:
    try:
        result = await _kis_order_market("VTTC0801U", code, quantity)
        if not result:
            # KIS 주문 자체 실패 (잔고 없음 등) → 현재가 기반으로 DB 정리
            sell_price = await _get_current_price(code) or price
            pnl = calc_pnl_pct(buy_price, sell_price)
            await update_position_sold(position_id, sell_price, pnl, reason)
            _peak_prices.pop(position_id, None)
            logger.warning(f"KIS 매도 주문 실패 → 현재가 기반 정리: {name}({code}) {pnl:+.1f}%")
            await send_telegram(
                f"<b>⚠️ KIS 매도 주문 실패 — DB 정리</b>\n{name} ({code})\n"
                f"사유: {reason}\n매도가(현재가): {sell_price:,}원 ({pnl:+.2f}%)"
            )
            return True
        if result:
            filled_qty = await _verify_sell_fill(code, quantity)
            if filled_qty <= 0:
                # 미체결 조회 실패 → 모의투자 시장가는 즉시체결이므로 체결된 것으로 간주
                sell_price = await _get_current_price(code) or price
                pnl = calc_pnl_pct(buy_price, sell_price)
                await update_position_sold(position_id, sell_price, pnl, reason)
                _peak_prices.pop(position_id, None)
                logger.warning(f"매도 미체결 조회 실패 → 즉시체결 간주: {name}({code}) {pnl:+.1f}%")
                await send_telegram(
                    f"<b>📊 매도 체결 (즉시체결 간주)</b>\n{name} ({code})\n"
                    f"사유: {reason}\n매도가(현재가): {sell_price:,}원 ({pnl:+.2f}%)"
                )
                return True
            actual_price = await _get_actual_fill_price(code, is_sell=True)
            if actual_price <= 0:
                actual_price = await _get_current_price(code)
                if actual_price > 0:
                    logger.info(f"매도 체결가 조회 실패, 현재가 fallback: {name}({code}) {actual_price:,}원")
            sell_price = actual_price if actual_price > 0 else price
            pnl = calc_pnl_pct(buy_price, sell_price)
            reason_labels = {"take_profit": "익절", "stop_loss": "손절", "trailing_stop": "급락 손절", "stepped_trailing": "Stepped 청산", "manual_sell": "수동 매도", "eod_close": "장 마감 청산"}
            reason_label = reason_labels.get(reason, reason)
            emoji = {"take_profit": "💰", "stop_loss": "🛑", "trailing_stop": "📉", "stepped_trailing": "📊", "manual_sell": "✋", "eod_close": "🔔"}.get(reason, "📊")
            _peak_prices.pop(position_id, None)
            if filled_qty < quantity:
                # NOTE: update_position_quantity()가 unmark_selling() 전에 실행되므로
                # 재매도 시 줄어든 잔여 수량으로만 주문됨 (이중 매도 아님)
                await update_position_quantity(position_id, quantity - filled_qty)
                unmark_selling(position_id)
                logger.warning(f"매도 부분체결: {name}({code}) {filled_qty}/{quantity}주, 잔여 {quantity - filled_qty}주")
            else:
                await update_position_sold(position_id, sell_price, pnl, reason)
            logger.info(f"매도 체결: {name}({code}) {reason_label} ({pnl:+.1f}%) {filled_qty}주")
            await send_telegram(
                f"<b>{emoji} 자동 매도 ({reason_label})</b>\n"
                f"<b>{name} ({code})</b>\n"
                f"매수가: {buy_price:,}원 → 매도가: {sell_price:,}원\n"
                f"수익률: {pnl:+.2f}% ({filled_qty}주)"
                + (f"\n⚠️ 부분체결 ({quantity}주 중 {filled_qty}주)" if filled_qty != quantity else "")
            )
            # 실전 매도 시 남아있는 open 시뮬레이션 close (time_exit 포함)
            asyncio.ensure_future(_close_open_simulations(position_id, sell_price, buy_price, code=code))
            try:
                from daemon.main import trigger_subscription_refresh
                task = asyncio.ensure_future(trigger_subscription_refresh())
                task.add_done_callback(lambda t: logger.warning(f"구독 갱신 실패: {t.exception()}") if not t.cancelled() and t.exception() else None)
            except Exception:
                pass
            return True
    except Exception as e:
        # 예외 발생 시에도 현재가 기반 DB 정리 (무한 재시도 방지)
        sell_price = await _get_current_price(code) or price
        pnl = calc_pnl_pct(buy_price, sell_price)
        await update_position_sold(position_id, sell_price, pnl, reason)
        _peak_prices.pop(position_id, None)
        logger.error(f"매도 처리 오류 → DB 정리: {name}({code}) {e}")
        return False


def _reset_token():
    global _access_token, _token_issued_at
    _access_token = ""
    _token_issued_at = 0


async def fetch_available_balance() -> int:
    """KIS 모의투자 계좌 예수금 조회 (rate limit 시 재시도)"""
    token = await _ensure_mock_token()
    if not token:
        return 0
    cano, acnt_cd = _parse_account()
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-psbl-order"
    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_cd,
        "PDNO": "005930",
        "ORD_UNPR": "0",
        "ORD_DVSN": "00",
        "CMA_EVLU_AMT_ICLD_YN": "Y",
        "OVRS_ICLD_YN": "N",
    }
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": KIS_MOCK_APP_KEY,
        "appsecret": KIS_MOCK_APP_SECRET,
        "tr_id": "VTTC8908R",
        "custtype": "P",
    }
    for attempt in range(1, _RATE_LIMIT_RETRIES + 1):
        try:
            session = await get_session()
            async with session.get(url, params=params, headers=headers) as resp:
                data = await resp.json()
                if data.get("rt_cd") == "0":
                    output = data.get("output", {})
                    balance = int(output.get("ord_psbl_cash", "0"))
                    logger.info(f"가용 잔고: {balance:,}원")
                    return balance
                msg = data.get("msg1", "")
                if "초과" in msg and attempt < _RATE_LIMIT_RETRIES:
                    logger.warning(f"잔고 조회 rate limit ({attempt}/{_RATE_LIMIT_RETRIES}) — {attempt * _RATE_LIMIT_BASE_SEC}초 후 재시도")
                    await asyncio.sleep(attempt * _RATE_LIMIT_BASE_SEC)
                    continue
                logger.warning(f"잔고 조회 실패: {msg}")
        except Exception as e:
            logger.error(f"잔고 조회 오류: {e}")
            if attempt < _RATE_LIMIT_RETRIES:
                await asyncio.sleep(attempt * _RATE_LIMIT_BASE_SEC)
                continue
    return 0


MAX_HOLDING_STOCKS = 18     # 최대 보유 종목 수 (WebSocket 40슬롯 중 알림용 2슬롯 확보)

async def run_buy_process():
    # 보유 종목 수 체크 — WebSocket 슬롯 한도 초과 방지
    from daemon.position_db import get_active_positions
    positions = await get_active_positions(force_refresh=True)
    held = [p for p in positions if p.get("status") in ("filled", "sell_requested")]
    if len(held) >= MAX_HOLDING_STOCKS:
        logger.warning(f"보유 종목 {len(held)}개 — WebSocket 한도({MAX_HOLDING_STOCKS}) 도달, 매수 중단")
        await send_telegram(f"⚠️ 매수 차단: 보유 {len(held)}종목 (한도 {MAX_HOLDING_STOCKS})\nWebSocket 슬롯 부족으로 손절 감시 불가 방지")
        return

    sold_today_rows = await _get_sold_today_trades()
    sold_today_codes = {r["code"] for r in sold_today_rows if r.get("code")}

    cross_data = await fetch_json(f"{DATA_BASE_URL}/cross_signal.json")
    if not isinstance(cross_data, list):
        logger.warning("cross_signal.json 로드 실패")
        return

    config = await fetch_alert_config()
    buy_mode = config.get("buy_signal_mode", "and")

    all_scored = []  # 스코어 충족 전체 (research_optimal용)
    if buy_mode == "research_optimal":
        # 실제 매매: 갭업 모멘텀 전략 (갭업 2~5% + 거래량 2배)
        targets = select_gapup_momentum(cross_data, top_n=2)
        if targets:
            names = ", ".join(f"{t.get('name','')}(갭업{t.get('_gap_pct',0):+.1f}%)" for t in targets)
            logger.info(f"갭업 모멘텀 전략: {len(targets)}종목 선정 — {names}")
        else:
            logger.info("갭업 모멘텀 전략: 조건 충족 종목 없음 (갭업2~5% + 거래량2배)")
        # 시뮬레이션: 기존 5팩터 스코어링 (가상 포지션으로 성과 추적)
        use_criteria = config.get("criteria_filter", False)
        all_scored = select_research_optimal(cross_data, top_n=999, criteria_filter=use_criteria)
    else:
        # 기존 로직: 토글 기반 필터
        has_fallback = "fallback_top_leader" in buy_mode
        primary_mode = buy_mode.replace(",fallback_top_leader", "").replace("fallback_top_leader,", "").replace("fallback_top_leader", "") or "none"
        targets = filter_high_confidence(cross_data, mode=primary_mode)
        if not targets and has_fallback:
            logger.info(f"1차 조건({primary_mode}) 매칭 0건 — fallback 대장주 1위로 전환")
            targets = filter_high_confidence(cross_data, mode="top_leader")

    if not targets:
        logger.info(f"매수 대상 없음 (모드: {buy_mode})")
        await send_telegram(f"📭 매수 대상 없음 (모드: {buy_mode})")
        return

    # Pass 1: 보유/주문/당일매도 필터링 (현재가 API 호출 없음)
    need_price = []
    skipped_held = []
    skipped_sold_today = []
    for t in targets:
        code = t["code"]
        name = t.get("name", "")
        if await is_already_held_or_ordered(code):
            logger.info(f"이미 보유/주문중 — {name}({code}) 스킵")
            skipped_held.append(name)
            continue
        if code in sold_today_codes:
            logger.info(f"당일 매도 종목 — {name}({code}) 재매수 방지 스킵")
            skipped_sold_today.append(name)
            continue
        price = 0
        api_data = t.get("api_data", {})
        if api_data:
            price = api_data.get("price", {}).get("current", 0)
        need_price.append({"code": code, "name": name, "price": price, "_need_fetch": price <= 0})

    if not need_price:
        logger.info("매수 가능 종목 없음")
        return

    # Pass 2: 현재가 병렬 조회
    fetch_targets = [c for c in need_price if c["_need_fetch"]]
    if fetch_targets:
        prices = await asyncio.gather(*[_get_current_price(c["code"]) for c in fetch_targets])
        for c, p in zip(fetch_targets, prices):
            c["price"] = p

    # Pass 3: 가격 없는 종목 제거 + 상한가 체크
    buy_candidates = []
    for c in need_price:
        if c["price"] <= 0:
            logger.warning(f"현재가 없음 — {c['name']}({c['code']}) 스킵")
            continue
        # 상한가 사전 체크 (분배 전에 걸러냄)
        if await is_upper_limit(c["code"], c["price"]):
            logger.info(f"상한가 종목 스킵 — {c['name']}({c['code']}) {c['price']:,}원")
            continue
        buy_candidates.append({"code": c["code"], "name": c["name"], "price": c["price"]})

    if not buy_candidates:
        logger.info("매수 가능 종목 없음")
        return

    # 가용 잔고 조회 → 균등 분배
    balance = await fetch_available_balance()
    if balance <= 0:
        logger.warning("가용 잔고 없음 — 매수 중단")
        names = ", ".join(c["name"] for c in buy_candidates[:5])
        await send_telegram(f"⚠️ 매수 실패: 가용 잔고 없음\n대상 종목: {names}\n잔고: {balance:,}원")
        return

    if buy_mode == "research_optimal":
        # 연구 최적: 100% 자본을 최대 2종목에 균등 배분
        actual_candidates = buy_candidates[:2]
        amount_per_stock = balance // max(len(actual_candidates), 1)
    elif balance <= TRADE_MIN_AMOUNT_PER_STOCK:
        actual_candidates = buy_candidates[:1]
        amount_per_stock = balance
    else:
        max_stocks = balance // TRADE_MIN_AMOUNT_PER_STOCK
        actual_candidates = buy_candidates[:max_stocks]
        amount_per_stock = balance // len(actual_candidates)
    logger.info(f"매수 대상 {len(buy_candidates)}종목 중 {len(actual_candidates)}종목 매수, 잔고 {balance:,}원, 종목당 {amount_per_stock:,}원")

    # 종합 보고 텔레그램 발송
    rpt = [f"<b>📋 매수 프로세스 보고 ({buy_mode})</b>"]
    rpt.append(f"")
    rpt.append(f"<b>[1단계] 종목 선정</b>")
    rpt.append(f"전체 후보: {len(cross_data)}종목")
    if buy_mode == "research_optimal":
        # 갭업 모멘텀 실제 매매 보고
        for t in targets:
            detail = " / ".join(t.get("_score_detail", []))
            rpt.append(f"  📈 {t.get('name','')} ({detail})")
        # 5팩터 시뮬 보고
        if all_scored:
            rpt.append(f"[시뮬] 5팩터 충족: {len(all_scored)}종목")
            for i, s in enumerate(all_scored[:5], 1):
                detail = " / ".join(s.get("_score_detail", []))
                rpt.append(f"  {i}. {s.get('name','')} {s.get('_score',0)}점 ({detail})")
    rpt.append(f"선정: {len(targets)}종목")
    rpt.append(f"")
    rpt.append(f"<b>[2단계] 필터링</b>")
    if skipped_held:
        rpt.append(f"보유중 스킵: {', '.join(skipped_held)}")
    if skipped_sold_today:
        rpt.append(f"당일매도 스킵: {', '.join(skipped_sold_today[:10])}")
        if len(skipped_sold_today) > 10:
            rpt.append(f"  ... 외 {len(skipped_sold_today) - 10}종목")
    rpt.append(f"매수 가능: {len(buy_candidates)}종목")
    rpt.append(f"")
    rpt.append(f"<b>[3단계] 매수 실행</b>")
    rpt.append(f"잔고: {balance:,}원 | 종목당: {amount_per_stock:,}원")
    for c in actual_candidates:
        qty = calc_quantity(amount_per_stock, c["price"])
        rpt.append(f"  📥 {c['name']} ({c['code']}) {c['price']:,}원 × {qty}주")
    if len(buy_candidates) > len(actual_candidates):
        rpt.append(f"  ⏭ 잔고 한도 초과 {len(buy_candidates) - len(actual_candidates)}종목 제외")
    await send_telegram("\n".join(rpt))

    bought = 0
    for c in actual_candidates:
        quantity = calc_quantity(amount_per_stock, c["price"])
        if quantity <= 0:
            logger.info(f"잔고 부족으로 매수 불가 — {c['name']}({c['code']}) {c['price']:,}원, 종목당 {amount_per_stock:,}원")
            continue
        await place_buy_order_with_qty(c["code"], c["name"], c["price"], quantity)
        bought += 1
    if bought > 0:
        # 매수 직후 WebSocket 구독 즉시 갱신 — 손절 감시 지연 방지
        try:
            from daemon.main import trigger_subscription_refresh
            await trigger_subscription_refresh()
            logger.info(f"매수 후 구독 즉시 갱신 완료 ({bought}종목)")
        except Exception as e:
            logger.warning(f"매수 후 구독 갱신 실패: {e}")
    if bought == 0 and actual_candidates:
        names = ", ".join(c["name"] for c in actual_candidates)
        await send_telegram(f"⚠️ 매수 실패: 잔고 부족\n대상: {names}\n잔고: {balance:,}원, 종목당 {amount_per_stock:,}원")

    # 시뮬레이션 생성: 5팩터 스코어 종목 (기존 전략을 가상으로 추적)
    if buy_mode == "research_optimal" and all_scored:
        try:
            await _create_5factor_simulations(all_scored[:2], config)
        except Exception as e:
            logger.warning(f"5팩터 시뮬 생성 오류: {e}")

    # 연구 시뮬: "API∧대장주" 종목 선정 가상 포지션 생성
    try:
        await _create_api_leader_simulations(cross_data, config)
    except Exception as e:
        logger.warning(f"API∧대장주 시뮬 생성 오류: {e}")


async def run_gapup_scan_and_buy():
    """장 시작 갭업 스캔: stock-master 상위 200종목 현재가 조회 → 갭업 2~5% + MA200 + 거래량2배 → 즉시 매수.
    09:01 KST에 호출됨 (schedule_gapup_open에서).
    """
    import json
    from pathlib import Path

    logger.info("갭업 스캔 시작 — stock-master 상위 200종목 조회")

    # 1) stock-master에서 전종목 코드+이름 로드
    master_path = Path(__file__).parent.parent / "results" / "stock-master.json"
    if not master_path.exists():
        logger.warning("stock-master.json 없음 — 갭업 스캔 중단")
        return
    with open(master_path, encoding="utf-8") as f:
        master = json.load(f)
    all_stocks = master.get("stocks", [])
    if not all_stocks:
        logger.warning("stock-master 종목 0개 — 갭업 스캔 중단")
        return

    # MA200 캐시 로드
    ma200_map = _load_ma200_cache()

    # 2) 상위 200종목 현재가 병렬 조회 (거래대금 상위는 사전 판별 불가 → 무작위 200 대신, MA200 보유 종목 우선)
    # MA200이 있는 종목 = daily_ohlcv에 수집된 종목 = 유동성 있는 종목
    scan_targets = [s for s in all_stocks if s["code"] in ma200_map][:200]
    if not scan_targets:
        scan_targets = all_stocks[:200]
    logger.info(f"갭업 스캔 대상: {len(scan_targets)}종목")

    # 배치 상세 조회 (시가, 전일종가, 거래량 포함)
    token = await _ensure_mock_token()
    if not token:
        logger.warning("토큰 없음 — 갭업 스캔 중단")
        return

    async def _fetch_detail(code: str) -> dict | None:
        try:
            session = await get_session()
            url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
            params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
            async with session.get(url, params=params, headers=_order_headers(token, "FHKST01010100")) as resp:
                data = await resp.json()
                if data.get("rt_cd") != "0":
                    return None
                return data.get("output", {})
        except Exception:
            return None

    # 50건씩 배치 조회 (rate limit 준수)
    candidates = []
    for batch_start in range(0, len(scan_targets), 50):
        batch = scan_targets[batch_start:batch_start + 50]
        results = await asyncio.gather(*[_fetch_detail(s["code"]) for s in batch])
        for stock, out in zip(batch, results):
            if not out:
                continue
            code = stock["code"]
            name = stock.get("name", code)
            cur_price = int(out.get("stck_prpr", "0"))
            open_price = int(out.get("stck_oprc", "0"))
            prev_close = int(out.get("stck_sdpr", "0"))
            acml_vol = int(out.get("acml_vol", "0"))

            if cur_price < 1000 or cur_price >= 200000:
                continue
            if open_price <= 0 or prev_close <= 0:
                continue

            gap_pct = (open_price - prev_close) / prev_close * 100

            # MA200 필터
            ma200 = ma200_map.get(code, 0)
            if ma200 > 0 and cur_price <= ma200:
                continue

            # 거래량 조건: 50만주+ (전일거래량 비교 불가하므로 절대 거래량 기준)
            vol_ok = acml_vol > 500000

            if 2 <= gap_pct < 5 and vol_ok:
                candidates.append({
                    "code": code, "name": name, "price": cur_price,
                    "gap_pct": round(gap_pct, 2), "vol_rate": acml_vol,
                })
        await asyncio.sleep(0.1)  # 배치 간 여유

    logger.info(f"갭업 스캔 결과: {len(candidates)}종목 조건 충족")

    if not candidates:
        await send_telegram("📭 갭업 스캔: 조건 충족 종목 없음 (갭업2~5% + MA200↑ + 거래량2배)")
        return

    # 거래량 순 정렬, 상위 2종목
    candidates.sort(key=lambda x: -x["vol_rate"])
    targets = candidates[:2]

    # 보유/주문 중 필터
    buy_targets = []
    for t in targets:
        if await is_already_held_or_ordered(t["code"]):
            logger.info(f"이미 보유/주문중 — {t['name']}({t['code']}) 스킵")
            continue
        if await is_upper_limit(t["code"], t["price"]):
            logger.info(f"상한가 스킵 — {t['name']}({t['code']})")
            continue
        buy_targets.append(t)

    if not buy_targets:
        await send_telegram("📭 갭업 스캔: 후보 있으나 보유중/상한가로 매수 불가")
        return

    # 잔고 조회 + 매수
    balance = await fetch_available_balance()
    if balance <= 0:
        names = ", ".join(t["name"] for t in buy_targets)
        await send_telegram(f"⚠️ 갭업 매수 실패: 잔고 없음\n대상: {names}")
        return

    amount_per = balance // len(buy_targets)

    # 텔레그램 보고
    rpt = [f"<b>📈 갭업 모멘텀 스캔 매수</b>"]
    rpt.append(f"스캔: {len(scan_targets)}종목 → 조건충족: {len(candidates)}종목")
    rpt.append(f"잔고: {balance:,}원 | 종목당: {amount_per:,}원")
    for t in buy_targets:
        qty = calc_quantity(amount_per, t["price"])
        rpt.append(f"  📥 {t['name']} ({t['code']}) 갭업+{t['gap_pct']:.1f}% 거래량{t['vol_rate']:.0f}% {t['price']:,}원 × {qty}주")
    await send_telegram("\n".join(rpt))

    bought = 0
    for t in buy_targets:
        qty = calc_quantity(amount_per, t["price"])
        if qty <= 0:
            continue
        await place_buy_order_with_qty(t["code"], t["name"], t["price"], qty)
        bought += 1

    if bought > 0:
        try:
            from daemon.main import trigger_subscription_refresh
            await trigger_subscription_refresh()
        except Exception as e:
            logger.warning(f"갭업 매수 후 구독 갱신 실패: {e}")
    logger.info(f"갭업 스캔 매수 완료: {bought}종목")


def _today_utc_start() -> str:
    """KST 0시를 UTC로 변환한 타임스탬프"""
    return (datetime.now(_KST).replace(hour=0, minute=0, second=0) - timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:%S")


async def _get_sold_today_trades() -> list[dict]:
    """당일 매도된 종목 전체 조회 (pnl_pct 포함)"""
    from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return []
    try:
        session = await get_session()
        today_utc = _today_utc_start()
        url = f"{SUPABASE_URL}/rest/v1/auto_trades?status=eq.sold&sold_at=gte.{today_utc}&select=code,pnl_pct"
        headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
    except Exception as e:
        logger.warning(f"당일 매도 종목 조회 실패: {e}")
    return []



_trade_config_cache: dict | None = None
_trade_config_time: float = 0
_TRADE_CONFIG_TTL = 5  # seconds (전략 변경 즉시 반영 위해 5초로 단축)


def invalidate_trade_config_cache():
    """전략 변경 시 외부에서 호출하여 즉시 캐시 무효화"""
    global _trade_config_cache, _trade_config_time
    _trade_config_cache = None
    _trade_config_time = 0


async def _get_trade_config() -> dict:
    """익절/손절 설정 조회 (30초 캐시)"""
    global _trade_config_cache, _trade_config_time
    now = time.time()
    if _trade_config_cache and (now - _trade_config_time) < _TRADE_CONFIG_TTL:
        return _trade_config_cache
    _trade_config_cache = await fetch_alert_config()
    _trade_config_time = now
    return _trade_config_cache


async def check_positions_for_sell(current_price_data: dict):
    """보유 포지션 수익률 체크 → 익절/손절/수동매도 (캐시 + 중복 매도 방지)"""
    code = current_price_data.get("code", "")
    current_price = current_price_data.get("price", 0)
    if not code or current_price <= 0:
        return

    config = await _get_trade_config()
    tp = config.get("take_profit_pct", TRADE_TAKE_PROFIT_PCT)
    sl = config.get("stop_loss_pct", TRADE_STOP_LOSS_PCT)

    positions = await get_active_positions()  # 5초 캐시 사용
    for pos in positions:
        if pos["code"] != code:
            continue
        # 수동 매도 요청 처리 (프론트엔드에서 status='sell_requested'로 변경)
        if pos["status"] == "sell_requested":
            position_id = pos["id"]
            if is_selling(position_id):
                continue
            mark_selling(position_id)
            buy_price = pos.get("filled_price") or pos.get("order_price", 0)
            await place_sell_order(
                code=code, name=pos["name"], price=current_price,
                quantity=pos["quantity"], position_id=position_id,
                reason="manual_sell", buy_price=buy_price,
            )
            continue
        if pos["status"] != "filled":
            continue

        position_id = pos["id"]
        # 중복 매도 방지: 이미 매도 진행 중이면 스킵
        if is_selling(position_id):
            continue

        buy_price = pos.get("filled_price") or pos.get("order_price", 0)
        if buy_price <= 0:
            continue

        # 고점 추적 (trailing stop용, flash spike 방지)
        peak_key = position_id
        prev_peak = _peak_prices.get(peak_key, 0)
        flash_spike_pct = config.get("flash_spike_pct", 5.0) / 100
        if current_price > prev_peak:
            if prev_peak > 0 and (current_price - prev_peak) / prev_peak > flash_spike_pct:
                pass  # flash spike — peak 갱신 안 함
            else:
                _peak_prices[peak_key] = current_price

        # 보유일수 계산 → 익절 기준 연동
        hold_days = _calc_hold_days(pos)
        effective_tp = get_tiered_tp(tp, hold_days)

        strategy_type = config.get("strategy_type", "fixed")
        reason = None

        if strategy_type == "stepped":
            # Stepped Trailing: 고정 TP 없음, stepped stop만 적용
            pnl = calc_pnl_pct(buy_price, current_price)

            # 기본 손절 체크
            if pnl <= sl:
                reason = "stop_loss"
            else:
                # 고점 수익률 기준 stepped stop 계산
                peak = _peak_prices.get(peak_key, current_price)
                peak_pnl = calc_pnl_pct(buy_price, peak)
                ts_pct = config.get("trailing_stop_pct", TRADE_TRAILING_STOP_PCT)
                stepped_preset = config.get("stepped_preset", "default")
                stepped_stop = calc_stepped_stop_pct(peak_pnl, ts_pct, preset=stepped_preset)
                if stepped_stop > -999.0 and pnl <= stepped_stop:
                    reason = "stepped_trailing"
        else:
            # Fixed: 현행 로직 그대로
            reason = should_sell(buy_price, current_price, take_profit=effective_tp, stop_loss=sl)

            # trailing stop: 수익 중(pnl > 0)이고 고점 대비 c% 하락
            if not reason:
                pnl = calc_pnl_pct(buy_price, current_price)
                peak = _peak_prices.get(peak_key, current_price)
                if pnl > 0 and peak > 0:
                    drop = (current_price - peak) / peak * 100
                    ts_pct = config.get("trailing_stop_pct", TRADE_TRAILING_STOP_PCT)
                    if drop <= ts_pct:
                        reason = "trailing_stop"

        if reason:
            if not try_mark_selling(position_id):
                continue  # 다른 태스크가 먼저 mark함
            await place_sell_order(
                code=code,
                name=pos["name"],
                price=current_price,
                quantity=pos["quantity"],
                position_id=position_id,
                reason=reason,
                buy_price=buy_price,
            )

    # 가상 시뮬레이션 체크
    await _check_simulations(current_price_data)


async def cancel_all_pending_orders():
    """KIS 미체결 주문 전체 취소 + DB pending 정리"""
    from daemon.position_db import invalidate_cache, delete_position
    token = await _ensure_mock_token()
    if not token:
        return
    cano, acnt_cd = _parse_account()

    # KIS 모의투자 미체결 조회
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-nccs"
    params = {
        "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
        "INQR_STRT_DT": "", "INQR_END_DT": "",
        "SLL_BUY_DVSN_CD": "00", "INQR_DVSN": "00",
        "PDNO": "", "CCLD_DVSN": "01",
        "ORD_GNO_BRNO": "", "ODNO": "",
        "INQR_DVSN_3": "00", "INQR_DVSN_1": "",
        "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
    }
    session = await get_session()
    try:
        async with session.get(url, params=params, headers=_order_headers(token, "VTTC8001R")) as resp:
            data = await resp.json()
            if data.get("rt_cd") != "0":
                logger.warning(f"미체결 조회 실패: {data.get('msg1', '')}")
                return
            orders = data.get("output", [])
            if not orders:
                logger.info("미체결 주문 없음")
                return
            logger.info(f"미체결 {len(orders)}건 취소 시작")
            for order in orders:
                odno = order.get("odno", "")
                code = order.get("pdno", "")
                qty = order.get("psbl_qty", order.get("ord_qty", "0"))
                # 주문 취소
                cancel_url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/order-rvsecncl"
                cancel_body = {
                    "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
                    "KRX_FWDG_ORD_ORGNO": "",
                    "ORGN_ODNO": odno,
                    "ORD_DVSN": "00",
                    "RVSE_CNCL_DVSN_CD": "02",  # 취소
                    "ORD_QTY": str(qty),
                    "ORD_UNPR": "0",
                    "QTY_ALL_ORD_YN": "Y",
                }
                async with session.post(cancel_url, json=cancel_body, headers=_order_headers(token, "VTTC0803U")) as cresp:
                    cdata = await cresp.json()
                    if cdata.get("rt_cd") == "0":
                        logger.info(f"미체결 취소: {code} 주문번호={odno}")
                    else:
                        logger.warning(f"미체결 취소 실패: {code} {cdata.get('msg1', '')}")
                await asyncio.sleep(0.3)
    except Exception as e:
        logger.error(f"미체결 취소 오류: {e}")

    # DB pending 정리
    positions = await get_active_positions(force_refresh=True)
    pending = [p for p in positions if p["status"] == "pending"]
    for p in pending:
        await delete_position(p["id"])
        logger.info(f"DB pending 삭제: {p.get('name', '')}({p.get('code', '')})")
    invalidate_cache()


# 보유일별 익절 기준 / 장 마감 보유 기준 (매수가 대비 %, 누적)
# base_tp는 사용자 설정값 (기본 7%), 나머지는 base_tp 기준 오프셋
_TP_OFFSETS = [0, 3, 8, 13, 18]      # D+0: +0, D+1: +3, D+2: +8, D+3: +13, D+4+: +18
_CARRY_THRESHOLDS = [3, 5, 8, 12, 15]  # D+0: 3%, D+1: 5%, D+2: 8%, D+3: 12%, D+4+: 15%


def get_tiered_tp(base_tp: float, hold_days: int) -> float:
    """보유일수 연동 익절 기준 반환"""
    idx = min(max(hold_days, 0), len(_TP_OFFSETS) - 1)
    return base_tp + _TP_OFFSETS[idx]


def get_carry_threshold(hold_days: int) -> float:
    """보유일수 연동 장 마감 보유 기준 반환"""
    idx = min(max(hold_days, 0), len(_CARRY_THRESHOLDS) - 1)
    return _CARRY_THRESHOLDS[idx]

async def sell_all_positions_market():
    """장 마감 청산 — 손절 미도달 종목은 익일 보유, 수동매도 요청 및 매수가 불명 종목만 매도"""
    from daemon.position_db import invalidate_cache

    config = await _get_trade_config()
    sl = config.get("stop_loss_pct", TRADE_STOP_LOSS_PCT)

    # 1) 미체결 주문 취소
    await cancel_all_pending_orders()

    # 2) 보유 포지션 분류
    positions = await get_active_positions(force_refresh=True)
    filled = [p for p in positions if p["status"] in ("filled", "sell_requested")]
    if not filled:
        logger.info("장 마감 청산: 보유 포지션 없음")
        return

    to_sell = []
    to_carry = []

    today = datetime.now(_KST).date()

    for pos in filled:
        buy_price = pos.get("filled_price") or pos.get("order_price", 0)

        # 수동 매도 요청(sell_requested)은 무조건 매도
        if pos["status"] == "sell_requested":
            to_sell.append(pos)
            pos["_current_price"] = await _get_current_price(pos["code"])
            pos["_pnl"] = calc_pnl_pct(buy_price, pos["_current_price"]) if buy_price > 0 and pos["_current_price"] > 0 else 0
            continue

        if buy_price <= 0:
            to_sell.append(pos)
            continue

        hold_days = _calc_hold_days(pos)

        current_price = await _get_current_price(pos["code"])
        pnl = calc_pnl_pct(buy_price, current_price) if current_price > 0 else 0
        pos["_current_price"] = current_price
        pos["_pnl"] = pnl
        pos["_hold_days"] = hold_days

        # 판정: 손절 기준 이하 → 매도, 그 외 → 익일 보유
        # (장중에 -2%에서 이미 손절되므로 여기 도달하는 경우는 드묾)
        if pnl <= sl:
            to_sell.append(pos)
        else:
            to_carry.append(pos)
        await asyncio.sleep(0.2)

    # 익일 보유 종목: peak을 당일 종가로 리셋 (stepped 구간 보호 유지 + 전날 장중 고점 제거)
    for pos in to_carry:
        cp = pos.get("_current_price", 0)
        if cp > 0:
            _peak_prices[pos.get("id", "")] = cp
        else:
            _peak_prices.pop(pos.get("id", ""), None)

    # 익일 보유 종목 알림
    if to_carry:
        carry_lines = []
        for pos in to_carry:
            d = pos.get("_hold_days", 0)
            carry_lines.append(f"  {pos['name']}({pos['code']}) {pos['_pnl']:+.2f}% (D+{d})")
        logger.info(f"익일 보유: {len(to_carry)}종목")
        await send_telegram(
            f"<b>📌 익일 보유 ({len(to_carry)}종목)</b>\n"
            f"손절 미도달 → 보유 유지 (익일 -2% 손절 적용)\n\n"
            + "\n".join(carry_lines)
        )

    # 매도 대상
    if not to_sell:
        logger.info("장 마감 청산: 매도 대상 없음 (전종목 익일 보유)")
        invalidate_cache()
        return

    logger.info(f"장 마감 청산: {len(to_sell)}종목 매도, {len(to_carry)}종목 익일 보유")
    failed_positions = []
    for pos in to_sell:
        position_id = pos["id"]
        if is_selling(position_id):
            continue
        mark_selling(position_id)
        buy_price = pos.get("filled_price") or pos.get("order_price", 0)
        current_price = pos.get("_current_price") or await _get_current_price(pos["code"])
        try:
            result = await _kis_order_market("VTTC0801U", pos["code"], pos["quantity"])
            if result:
                filled_qty = await _verify_sell_fill(pos["code"], pos["quantity"])
                if current_price <= 0:
                    current_price = await _get_current_price(pos["code"])
                sell_price = current_price if current_price > 0 else buy_price
                pnl = calc_pnl_pct(buy_price, sell_price)
                _peak_prices.pop(position_id, None)
                if filled_qty >= pos["quantity"]:
                    await update_position_sold(position_id, sell_price, pnl, "eod_close")
                    logger.info(f"장 마감 매도: {pos['name']}({pos['code']}) {pnl:+.2f}%")
                elif filled_qty > 0:
                    await update_position_quantity(position_id, pos["quantity"] - filled_qty)
                    unmark_selling(position_id)
                    failed_positions.append(pos)
                    logger.warning(f"장 마감 부분체결: {pos['name']}({pos['code']}) {filled_qty}/{pos['quantity']}주")
                else:
                    unmark_selling(position_id)
                    failed_positions.append(pos)
                    logger.warning(f"장 마감 미체결: {pos['name']}({pos['code']})")
                await send_telegram(
                    f"<b>🔔 장 마감 청산</b>\n"
                    f"<b>{pos['name']} ({pos['code']})</b>\n"
                    f"매수가: {buy_price:,}원 → 매도가: {sell_price:,}원\n"
                    f"수익률: {pnl:+.2f}% ({filled_qty}주)"
                    + (f"\n⚠️ 부분체결 ({pos['quantity']}주 중 {filled_qty}주)" if filled_qty < pos["quantity"] else "")
                )
            else:
                unmark_selling(position_id)
                failed_positions.append(pos)
        except Exception as e:
            unmark_selling(position_id)
            _peak_prices.pop(position_id, None)
            failed_positions.append(pos)
            logger.error(f"장 마감 매도 오류: {pos['name']}({pos['code']}) {e}")
        await asyncio.sleep(0.3)
    # 실패 종목 1회 재시도
    if failed_positions:
        logger.info(f"장 마감 미체결 {len(failed_positions)}종목 재시도")
        await asyncio.sleep(3)
        for pos in failed_positions:
            position_id = pos["id"]
            if is_selling(position_id):
                continue
            try:
                remaining = (await get_active_positions(force_refresh=True))
                pos_now = next((p for p in remaining if p["id"] == position_id and p["status"] == "filled"), None)
                if not pos_now:
                    continue
                mark_selling(position_id)
                result = await _kis_order_market("VTTC0801U", pos_now["code"], pos_now["quantity"])
                if result:
                    filled_qty = await _verify_sell_fill(pos_now["code"], pos_now["quantity"])
                    retry_buy_price = pos_now.get("filled_price") or pos_now.get("order_price", 0)
                    cp = await _get_current_price(pos_now["code"])
                    sp = cp if cp > 0 else retry_buy_price
                    pnl = calc_pnl_pct(retry_buy_price, sp)
                    if filled_qty >= pos_now["quantity"]:
                        await update_position_sold(position_id, sp, pnl, "eod_close")
                        logger.info(f"장 마감 재시도 성공: {pos_now['name']}({pos_now['code']})")
                    else:
                        unmark_selling(position_id)
                        logger.warning(f"장 마감 재시도 실패: {pos_now['name']}({pos_now['code']}) 체결 {filled_qty}주")
                else:
                    unmark_selling(position_id)
            except Exception as e:
                unmark_selling(position_id)
                logger.error(f"장 마감 재시도 오류: {pos.get('name')} {e}")
    invalidate_cache()

    # EOD: 모든 open 시뮬레이션 개별 close (exit_price/pnl_pct 포함)
    try:
        session = await get_session()
        headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}", "Content-Type": "application/json", "Prefer": "return=minimal"}
        eod_url = f"{SUPABASE_URL}/rest/v1/strategy_simulations?status=eq.open&select=id,trade_id,entry_price"
        async with session.get(eod_url, headers={k: v for k, v in headers.items() if k != "Prefer"}) as resp:
            if resp.status != 200:
                logger.warning("EOD 시뮬 조회 실패")
            else:
                open_sims = await resp.json()
                if open_sims:
                    # trade_id → code 매핑
                    tids = list(set(s["trade_id"] for s in open_sims))
                    tid_filter = ",".join(tids)
                    tr_url = f"{SUPABASE_URL}/rest/v1/auto_trades?id=in.({tid_filter})&select=id,code"
                    async with session.get(tr_url, headers={k: v for k, v in headers.items() if k != "Prefer"}) as tr_resp:
                        trades_map = {t["id"]: t["code"] for t in (await tr_resp.json() if tr_resp.status == 200 else [])}
                    now_iso = datetime.now(_KST).isoformat()
                    closed_count = 0
                    for sim in open_sims:
                        code = trades_map.get(sim["trade_id"], "")
                        entry = sim["entry_price"]
                        price = await _get_current_price(code) if code else 0
                        pnl = calc_pnl_pct(entry, price) if price > 0 and entry > 0 else 0
                        body = {"status": "closed", "exit_reason": "eod_close", "exit_price": price or entry, "pnl_pct": round(pnl, 2), "exited_at": now_iso}
                        patch_url = f"{SUPABASE_URL}/rest/v1/strategy_simulations?id=eq.{sim['id']}"
                        async with session.patch(patch_url, json=body, headers=headers) as pr:
                            if pr.status in (200, 204):
                                closed_count += 1
                        await asyncio.sleep(0.1)
                    logger.info(f"EOD: {closed_count}/{len(open_sims)}건 시뮬레이션 개별 close")
                else:
                    logger.info("EOD: open 시뮬레이션 없음")
        _orphan_sim_codes.clear()
    except Exception as e:
        logger.warning(f"EOD 시뮬레이션 close 오류: {e}")


async def schedule_sell_check():
    """30초마다 보유종목 현재가 REST API 조회 → 익절/손절/수동매도 체크 (WebSocket 백업)"""
    from daemon import main as _main
    from daemon.main import is_market_hours, is_market_day
    while not _main._shutdown:
        # 30초 대기 (shutdown 시 즉시 탈출)
        for _ in range(30):
            if _main._shutdown:
                return
            await asyncio.sleep(1)
        if not is_market_day() or not is_market_hours():
            continue
        try:
            positions = await get_active_positions(force_refresh=True)
            targets = [p for p in positions if p["status"] in ("filled", "sell_requested")]
            if not targets:
                continue
            for pos in targets:
                code = pos["code"]
                price = await _get_current_price(code)
                if price <= 0:
                    continue
                await check_positions_for_sell({"code": code, "price": price})
                await asyncio.sleep(0.3)  # API 호출 간격
            # 시뮬레이션 미생성 종목 자동 보완 (수동 매수 등 daemon 외부 경로 대응)
            await _ensure_simulations_for_filled(targets)
            # 실전 매도 후 남은 시뮬레이션 독립 체크
            await _check_orphan_simulations()
        except Exception as e:
            logger.error(f"매도 폴링 체크 오류: {e}")


async def _create_simulation(trade_id: str, strategy_type: str, entry_price: int, user_id: str):
    """비선택 전략의 가상 포지션 생성"""
    from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return
    if not user_id:
        logger.warning("가상 시뮬레이션 생성 스킵: user_id 없음")
        return
    try:
        session = await get_session()
        url = f"{SUPABASE_URL}/rest/v1/strategy_simulations"
        headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}", "Content-Type": "application/json", "Prefer": "return=minimal"}
        body = {
            "trade_id": trade_id,
            "strategy_type": strategy_type,
            "entry_price": entry_price,
            "status": "open",
            "peak_price": entry_price,
            "stepped_stop_pct": -2.0,
            "user_id": user_id,
        }
        async with session.post(url, json=body, headers=headers) as resp:
            if resp.status in (200, 201):
                logger.info(f"가상 시뮬레이션 생성: {strategy_type} entry={entry_price}")
            else:
                err_body = await resp.text()
                logger.warning(f"가상 시뮬레이션 생성 실패: {resp.status} {err_body[:200]}")
    except Exception as e:
        logger.warning(f"가상 시뮬레이션 생성 오류: {e}")


async def _create_5factor_simulations(scored_top2: list, config: dict):
    """기존 5팩터 스코어링 종목을 시뮬레이션으로 추적 (strategy_type=five_factor)"""
    from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
    from daemon.position_db import _supabase_request
    user_id = config.get("user_id", "")
    if not user_id or not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return
    today = datetime.now(_KST).strftime("%Y%m%d")
    # 이미 오늘 생성된 five_factor 시뮬이 있으면 스킵
    existing = await _supabase_request(
        "GET",
        f"{SUPABASE_URL}/rest/v1/strategy_simulations?strategy_type=eq.five_factor&status=eq.open&user_id=eq.{user_id}&select=trade_id",
    )
    existing_ids = {r.get("trade_id", "") for r in (existing or [])}
    for item in scored_top2:
        code = item.get("code", "")
        price = (item.get("api_data") or {}).get("price", {}).get("current", 0)
        if price <= 0:
            continue
        trade_id = f"five_factor_{code}_{today}"
        if trade_id in existing_ids:
            continue
        body = {
            "trade_id": trade_id,
            "strategy_type": "five_factor",
            "entry_price": price,
            "status": "open",
            "peak_price": price,
            "stepped_stop_pct": -2.0,
            "user_id": user_id,
        }
        try:
            session = await get_session()
            url = f"{SUPABASE_URL}/rest/v1/strategy_simulations"
            headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
                       "Content-Type": "application/json", "Prefer": "return=minimal"}
            async with session.post(url, json=body, headers=headers) as resp:
                if resp.status in (200, 201):
                    name = item.get("name", code)
                    logger.info(f"5팩터 시뮬 생성: {name}({code}) {price:,}원 score={item.get('_score',0)}")
        except Exception as e:
            logger.warning(f"5팩터 시뮬 생성 오류: {code} {e}")


async def _create_api_leader_simulations(cross_data: list, config: dict):
    """연구 시뮬: API매수∧대장주 Top-2를 별도 선정하여 가상 포지션 생성 (strategy_type=api_leader)"""
    from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
    from daemon.position_db import _supabase_request
    user_id = config.get("user_id", "")
    if not user_id or not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return

    # API매수 AND 대장주 조건으로 별도 선정
    top1_codes = set()
    for s in cross_data:
        theme = s.get("theme")
        if not theme:
            continue
        vol = (s.get("api_data") or {}).get("ranking", {}).get("volume", 0)
        existing = top1_codes  # 간단히 theme별 1위 산출은 select_research_optimal과 동일
    # select_research_optimal의 로직 재활용하되 API 필수 조건 추가
    scored = []
    theme_best: dict[str, tuple[str, int]] = {}
    for s in cross_data:
        theme = s.get("theme")
        if theme:
            vol = (s.get("api_data") or {}).get("ranking", {}).get("volume", 0)
            if theme not in theme_best or vol > theme_best[theme][1]:
                theme_best[theme] = (s.get("code", ""), vol)
    top1_codes = {code for code, _ in theme_best.values()}

    for s in cross_data:
        code = s.get("code", "")
        api_sig = s.get("api_signal", "")
        price = (s.get("api_data") or {}).get("price", {}).get("current", 0)
        if price < 1000 or price >= 50000:
            continue
        # API 매수 필수
        if api_sig not in ("매수", "적극매수"):
            continue
        # 대장주 Top5 필수 (테마별 거래대금 1위 또는 theme_rank 1~5)
        rank = s.get("theme_rank")
        is_top1 = code in top1_codes
        is_top5 = is_top1 or (rank is not None and rank <= 5)
        if not is_top5:
            continue
        score = 40 if api_sig == "적극매수" else 30
        if is_top1:
            score += 25
        else:
            score += 15
        if price < 20000:
            score += 5
        scored.append({"code": code, "name": s.get("name", ""), "price": price, "score": score})

    scored.sort(key=lambda x: -x["score"])
    top2 = scored[:2]
    if not top2:
        return

    session = await get_session()
    headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}", "Content-Type": "application/json", "Prefer": "return=minimal"}
    for item in top2:
        # api_leader용 가상 auto_trades 레코드 생성 (trade_id UUID 필수)
        virtual_trade = await _supabase_request("POST",
            f"{SUPABASE_URL}/rest/v1/auto_trades",
            json={"code": item["code"], "name": item["name"], "side": "buy",
                  "order_price": item["price"], "quantity": 0, "status": "sim_only"},
            retries=0)
        if not virtual_trade:
            logger.warning(f"API∧대장주 가상 trade 생성 실패: {item['name']}")
            continue
        vt = virtual_trade[0] if isinstance(virtual_trade, list) else virtual_trade
        body = {
            "trade_id": vt["id"],
            "strategy_type": "api_leader",
            "entry_price": item["price"],
            "status": "open",
            "peak_price": item["price"],
            "stepped_stop_pct": -2.0,
            "user_id": user_id,
        }
        try:
            url = f"{SUPABASE_URL}/rest/v1/strategy_simulations"
            async with session.post(url, json=body, headers=headers) as resp:
                if resp.status in (200, 201):
                    logger.info(f"API∧대장주 시뮬 생성: {item['name']}({item['code']}) {item['price']:,}원 {item['score']}점")
                else:
                    err = await resp.text()
                    logger.warning(f"API∧대장주 시뮬 생성 실패: {resp.status} {err[:100]}")
        except Exception as e:
            logger.warning(f"API∧대장주 시뮬 생성 오류: {e}")


async def _close_open_simulations(trade_id: str, sell_price: int, buy_price: int, code: str = ""):
    """실전 매도 시 해당 종목코드를 _orphan_sim_codes에 등록 (시뮬은 독립 체크로 유지)"""
    if code:
        _orphan_sim_codes.add(code)
        logger.info(f"실전 매도 → 시뮬 독립 체크 등록: {code}")
    else:
        logger.warning(f"_close_open_simulations: code 없음, trade_id={trade_id[:8]}")


# 실전 매도 후에도 시뮬레이션 체크가 필요한 종목 코드
_orphan_sim_codes: set[str] = set()


async def _check_simulations(current_price_data: dict):
    """open 상태의 가상 포지션 체크 → 가상 매도 조건 충족 시 업데이트"""
    from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return
    code = current_price_data.get("code", "")
    current_price = current_price_data.get("price", 0)
    if not code or current_price <= 0:
        return

    try:
        session = await get_session()
        headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}
        # 해당 code의 auto_trades id 목록 조회 (sold 포함 — 실전 매도 후에도 시뮬은 open일 수 있음)
        code_url = f"{SUPABASE_URL}/rest/v1/auto_trades?code=eq.{code}&select=id,created_at,status"
        async with session.get(code_url, headers=headers) as code_resp:
            if code_resp.status != 200:
                return
            code_rows = await code_resp.json()
        trade_ids_for_code = [r["id"] for r in (code_rows or [])]
        if not trade_ids_for_code:
            return

        # 해당 trade_id에 연결된 open 시뮬레이션만 조회
        trade_id_filter = ",".join(trade_ids_for_code)
        url = f"{SUPABASE_URL}/rest/v1/strategy_simulations?status=eq.open&trade_id=in.({trade_id_filter})&select=id,strategy_type,entry_price,peak_price,stepped_stop_pct,trade_id"
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return
            sims = await resp.json()

        if not sims:
            return

        config = await _get_trade_config()
        tp = config.get("take_profit_pct", TRADE_TAKE_PROFIT_PCT)
        sl = config.get("stop_loss_pct", TRADE_STOP_LOSS_PCT)
        ts_pct = config.get("trailing_stop_pct", TRADE_TRAILING_STOP_PCT)

        flash_spike_pct = config.get("flash_spike_pct", 5.0) / 100

        for sim in sims:
            entry_price = sim["entry_price"]
            peak_price = sim.get("peak_price", entry_price)
            sim_id = sim["id"]
            strategy = sim["strategy_type"]
            pnl = calc_pnl_pct(entry_price, current_price)

            # Update peak (flash spike 방지: 급등 시 peak 갱신 차단)
            new_peak = peak_price
            if current_price > peak_price:
                if peak_price > 0 and (current_price - peak_price) / peak_price > flash_spike_pct:
                    pass  # flash spike — peak 갱신 안 함
                else:
                    new_peak = current_price

            exit_reason = None
            exit_price = None

            if strategy == "fixed":
                # 고정 TP 전략 시뮬레이션 — 실제 포지션의 보유일수 참조
                matched_pos = next((r for r in code_rows if r["id"] == sim["trade_id"]), None)
                hold_days = _calc_hold_days(matched_pos) if matched_pos else 0
                effective_tp = get_tiered_tp(tp, hold_days)
                result = should_sell(entry_price, current_price, take_profit=effective_tp, stop_loss=sl)
                if result:
                    exit_reason = result
                    exit_price = current_price
                elif pnl > 0 and new_peak > 0:
                    drop = (current_price - new_peak) / new_peak * 100
                    if drop <= ts_pct:
                        exit_reason = "trailing_stop"
                        exit_price = current_price

            elif strategy == "stepped":
                # Stepped Trailing 시뮬레이션
                if pnl <= sl:
                    exit_reason = "stop_loss"
                    exit_price = current_price
                else:
                    peak_pnl = calc_pnl_pct(entry_price, new_peak)
                    stepped_preset = config.get("stepped_preset", "default")
                    stepped_stop = calc_stepped_stop_pct(peak_pnl, ts_pct, preset=stepped_preset)
                    if stepped_stop > -999.0 and pnl <= stepped_stop:
                        exit_reason = "stepped_trailing"
                        exit_price = current_price

            elif strategy == "time_exit":
                # 시간전략 시뮬레이션: SL=-2% + 11:00 KST 자동 매도
                if pnl <= sl:
                    exit_reason = "stop_loss"
                    exit_price = current_price
                else:
                    now_kst = datetime.now(_KST)
                    # 11:00 KST 이후면 현재가로 매도
                    if now_kst.hour >= 11:
                        exit_reason = "time_exit"
                        exit_price = current_price

            # Update simulation record
            update_body = {"peak_price": new_peak}
            if exit_reason:
                update_body.update({
                    "status": "closed",
                    "exit_price": exit_price,
                    "exit_reason": exit_reason,
                    "pnl_pct": round(pnl, 2),
                    "exited_at": datetime.now(_KST).isoformat(),
                })

            patch_url = f"{SUPABASE_URL}/rest/v1/strategy_simulations?id=eq.{sim_id}"
            patch_headers = {**headers, "Content-Type": "application/json", "Prefer": "return=minimal"}
            async with session.patch(patch_url, json=update_body, headers=patch_headers) as resp:
                pass  # best-effort update

    except Exception as e:
        logger.warning(f"가상 시뮬레이션 체크 오류: {e}")


async def _check_api_leader_simulations():
    """api_leader 시뮬레이션 독립 체크 — Stepped 공격형 조건으로 매도"""
    from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return
    now_kst = datetime.now(_KST)
    try:
        session = await get_session()
        headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}
        url = f"{SUPABASE_URL}/rest/v1/strategy_simulations?status=eq.open&strategy_type=eq.api_leader&select=id,entry_price,peak_price,trade_id"
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return
            sims = await resp.json()
        if not sims:
            return

        config = await _get_trade_config()
        sl = config.get("stop_loss_pct", TRADE_STOP_LOSS_PCT)
        ts_pct = config.get("trailing_stop_pct", TRADE_TRAILING_STOP_PCT)
        preset = "aggressive"  # api_leader는 항상 Stepped 공격형
        patch_headers = {**headers, "Content-Type": "application/json", "Prefer": "return=minimal"}

        # trade_id → code 매핑 일괄 조회
        trade_ids = list(set(s["trade_id"] for s in sims))
        tid_filter = ",".join(trade_ids)
        trades_url = f"{SUPABASE_URL}/rest/v1/auto_trades?id=in.({tid_filter})&select=id,code"
        async with session.get(trades_url, headers=headers) as tresp:
            if tresp.status != 200:
                return
            trades_data = await tresp.json()
        tid_to_code = {t["id"]: t["code"] for t in (trades_data or [])}

        for sim in sims:
            code = tid_to_code.get(sim["trade_id"], "")
            if not code:
                continue
            price = await _get_current_price(code)
            if price <= 0:
                continue
            entry = sim["entry_price"]
            prev_peak = sim.get("peak_price", entry)
            flash_spike_pct = config.get("flash_spike_pct", 5.0) / 100
            if price > prev_peak:
                if prev_peak > 0 and (price - prev_peak) / prev_peak > flash_spike_pct:
                    peak = prev_peak
                else:
                    peak = price
            else:
                peak = prev_peak
            pnl = calc_pnl_pct(entry, price)
            exit_reason = None

            # Stepped 공격형 조건 적용
            if pnl <= sl:
                exit_reason = "stop_loss"
            else:
                peak_pnl = calc_pnl_pct(entry, peak)
                ss = calc_stepped_stop_pct(peak_pnl, ts_pct, preset=preset)
                if ss > -999.0 and pnl <= ss:
                    exit_reason = "stepped_trailing"

            update_body: dict = {"peak_price": peak}
            if exit_reason:
                update_body.update({
                    "status": "closed", "exit_price": price,
                    "exit_reason": exit_reason, "pnl_pct": round(pnl, 2),
                    "exited_at": now_kst.isoformat(),
                })
                logger.info(f"API∧대장주 시뮬 close: {code} {exit_reason} pnl={pnl:+.1f}%")
            patch_url = f"{SUPABASE_URL}/rest/v1/strategy_simulations?id=eq.{sim['id']}"
            async with session.patch(patch_url, json=update_body, headers=patch_headers) as resp:
                pass
            await asyncio.sleep(0.2)
    except Exception as e:
        logger.warning(f"API∧대장주 시뮬 체크 오류: {e}")


async def _ensure_simulations_for_filled(positions: list[dict]):
    """filled 종목 중 시뮬레이션이 없는 것을 자동 생성 (수동 매수 등 daemon 외부 경로 대응)"""
    from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return
    filled = [p for p in positions if p.get("status") == "filled"]
    if not filled:
        return
    try:
        session = await get_session()
        headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}
        # 현재 open/closed 시뮬이 있는 trade_id 조회
        tids = ",".join(p["id"] for p in filled)
        url = f"{SUPABASE_URL}/rest/v1/strategy_simulations?trade_id=in.({tids})&select=trade_id,strategy_type"
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return
            existing = await resp.json()
        existing_set = set((e["trade_id"], e["strategy_type"]) for e in (existing or []))

        config = await _get_trade_config()
        active_strategy = config.get("strategy_type", "fixed")
        sim_strategy = "stepped" if active_strategy == "fixed" else "fixed"
        user_id = config.get("user_id") or ""
        if not user_id:
            return

        # trade_id별 시뮬 존재 여부
        tids_with_sim = set(e["trade_id"] for e in (existing or []))

        for pos in filled:
            tid = pos["id"]
            if tid in tids_with_sim:
                continue  # 이미 시뮬이 하나라도 있으면 스킵 (daemon 매수 종목)
            entry = pos.get("filled_price") or pos.get("order_price", 0)
            if entry <= 0:
                continue
            # 시뮬이 전혀 없는 종목 = daemon 외부 경로 매수 → 반대 전략 + time_exit 생성
            await _create_simulation(tid, sim_strategy, entry, user_id)
            logger.info(f"시뮬 자동 보완: {pos.get('name','')}({pos.get('code','')}) {sim_strategy} entry={entry}")
            if datetime.now(_KST).hour < 11:
                await _create_simulation(tid, "time_exit", entry, user_id)
                logger.info(f"시뮬 자동 보완: {pos.get('name','')}({pos.get('code','')}) time_exit entry={entry}")
    except Exception as e:
        logger.warning(f"시뮬 자동 보완 오류: {e}")


async def _check_orphan_simulations():
    """실전 매도 후 남아있는 시뮬 + api_leader 시뮬을 독립적으로 체크"""
    from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return
    # api_leader 시뮬도 체크 (orphan_sim_codes 없어도 실행)
    await _check_api_leader_simulations()
    if not _orphan_sim_codes:
        return
    now_kst = datetime.now(_KST)
    try:
        session = await get_session()
        headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}
        # open 상태 시뮬 전체 조회
        url = f"{SUPABASE_URL}/rest/v1/strategy_simulations?status=eq.open&select=id,strategy_type,entry_price,peak_price,trade_id"
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return
            sims = await resp.json()
        if not sims:
            _orphan_sim_codes.clear()
            return
        # trade_id → code 매핑
        trade_ids = list(set(s["trade_id"] for s in sims))
        tid_filter = ",".join(trade_ids)
        trades_url = f"{SUPABASE_URL}/rest/v1/auto_trades?id=in.({tid_filter})&select=id,code,filled_price,created_at"
        async with session.get(trades_url, headers=headers) as resp:
            if resp.status != 200:
                return
            trades_data = await resp.json()
        tid_map = {t["id"]: t for t in (trades_data or [])}

        config = await _get_trade_config()
        tp = config.get("take_profit_pct", TRADE_TAKE_PROFIT_PCT)
        sl = config.get("stop_loss_pct", TRADE_STOP_LOSS_PCT)
        ts_pct = config.get("trailing_stop_pct", TRADE_TRAILING_STOP_PCT)

        patch_headers = {**headers, "Content-Type": "application/json", "Prefer": "return=minimal"}
        closed_codes = set()
        for sim in sims:
            trade = tid_map.get(sim["trade_id"])
            if not trade:
                continue
            code = trade["code"]
            if code not in _orphan_sim_codes:
                continue  # 실전 매도 안 된 종목은 _check_simulations에서 처리
            price = await _get_current_price(code)
            if price <= 0:
                continue
            entry = sim["entry_price"]
            prev_peak = sim.get("peak_price", entry)
            # flash spike 방지: 급등 시 peak 갱신 차단
            flash_spike_pct = config.get("flash_spike_pct", 5.0) / 100
            if price > prev_peak:
                if prev_peak > 0 and (price - prev_peak) / prev_peak > flash_spike_pct:
                    peak = prev_peak  # flash spike — peak 유지
                else:
                    peak = price
            else:
                peak = prev_peak
            pnl = calc_pnl_pct(entry, price)
            strategy = sim["strategy_type"]
            exit_reason = None

            if strategy == "fixed":
                hold_days = _calc_hold_days(trade) if trade else 0
                effective_tp = get_tiered_tp(tp, hold_days)
                result = should_sell(entry, price, take_profit=effective_tp, stop_loss=sl)
                if result:
                    exit_reason = result
                elif pnl > 0 and peak > 0:
                    drop = (price - peak) / peak * 100
                    if drop <= ts_pct:
                        exit_reason = "trailing_stop"
            elif strategy == "stepped":
                if pnl <= sl:
                    exit_reason = "stop_loss"
                else:
                    peak_pnl = calc_pnl_pct(entry, peak)
                    preset = config.get("stepped_preset", "default")
                    ss = calc_stepped_stop_pct(peak_pnl, ts_pct, preset=preset)
                    if ss > -999.0 and pnl <= ss:
                        exit_reason = "stepped_trailing"
            elif strategy == "time_exit":
                if pnl <= sl:
                    exit_reason = "stop_loss"
                elif now_kst.hour >= 11:
                    exit_reason = "time_exit"

            update_body: dict = {"peak_price": peak}
            if exit_reason:
                update_body.update({
                    "status": "closed", "exit_price": price,
                    "exit_reason": exit_reason, "pnl_pct": round(pnl, 2),
                    "exited_at": now_kst.isoformat(),
                })
                closed_codes.add(code)
                logger.info(f"고아 시뮬 close: {code} {strategy} {exit_reason} pnl={pnl:+.1f}%")
            patch_url = f"{SUPABASE_URL}/rest/v1/strategy_simulations?id=eq.{sim['id']}"
            async with session.patch(patch_url, json=update_body, headers=patch_headers) as resp:
                pass
            await asyncio.sleep(0.2)

        # close된 코드의 open 시뮬이 남아있는지 재조회 → 없으면 orphan 제거
        if closed_codes:
            check_url = f"{SUPABASE_URL}/rest/v1/strategy_simulations?status=eq.open&select=trade_id"
            async with session.get(check_url, headers=headers) as resp:
                if resp.status == 200:
                    remaining = await resp.json()
                    remaining_codes = set()
                    for r in (remaining or []):
                        t = tid_map.get(r.get("trade_id"))
                        if t:
                            remaining_codes.add(t["code"])
                    for code in list(_orphan_sim_codes):
                        if code not in remaining_codes:
                            _orphan_sim_codes.discard(code)
    except Exception as e:
        logger.warning(f"고아 시뮬 체크 오류: {e}")


async def _get_current_price(code: str) -> int:
    """KIS API로 현재가 조회 (rate limit 시 재시도)"""
    token = await _ensure_mock_token()
    if not token:
        return 0
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    for attempt in range(1, _RATE_LIMIT_RETRIES + 1):
        try:
            session = await get_session()
            async with session.get(url, params=params, headers=_order_headers(token, "FHKST01010100")) as resp:
                data = await resp.json()
                if data.get("rt_cd") == "0":
                    return int(data.get("output", {}).get("stck_prpr", "0"))
                msg = data.get("msg1", "")
                if "초과" in msg and attempt < _RATE_LIMIT_RETRIES:
                    await asyncio.sleep(attempt * _RATE_LIMIT_BASE_SEC)
                    continue
        except Exception as e:
            if attempt < _RATE_LIMIT_RETRIES:
                await asyncio.sleep(attempt * _RATE_LIMIT_BASE_SEC)
                continue
            logger.warning(f"현재가 조회 실패 ({code}): {e}")
    return 0


async def _kis_order_market(tr_id: str, code: str, quantity: int, retry: bool = True, _pre_balance: int | None = None) -> dict | None:
    """KIS 모의투자 시장가 주문 (토큰 만료/rate limit 시 재시도, 중복 체결 방지)"""
    token = await _ensure_mock_token()
    if not token:
        return None
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/order-cash"
    cano, acnt_cd = _parse_account()
    body = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_cd,
        "PDNO": code,
        "ORD_DVSN": "01",  # 시장가
        "ORD_QTY": str(quantity),
        "ORD_UNPR": "0",
    }
    # 매수 주문 시 재시도 전 잔고 비교용 기록
    is_buy = tr_id == "VTTC0802U"
    if _pre_balance is None and is_buy:
        _pre_balance = await _check_balance_qty(code)
    for attempt in range(1, _RATE_LIMIT_RETRIES + 1):
        try:
            # rate limit 재시도 전 — 이전 주문이 이미 체결됐는지 잔고 확인
            if attempt > 1 and is_buy:
                cur_bal = await _check_balance_qty(code)
                if _pre_balance is not None and cur_bal > _pre_balance:
                    logger.warning(f"rate limit 재시도 중단 — 이미 체결 감지: {code} 잔고 {_pre_balance}→{cur_bal}")
                    return {"rt_cd": "0", "msg1": "이미 체결 (잔고 확인)"}
            session = await get_session()
            async with session.post(url, json=body, headers=_order_headers(token, tr_id)) as resp:
                if resp.status != 200:
                    logger.error(f"시장가 주문 HTTP {resp.status}: {code} {tr_id}")
                    return None
                data = await resp.json()
                if data.get("rt_cd") == "0":
                    return data
                msg = data.get("msg1", "")
                if retry and ("만료" in msg or "token" in msg.lower()):
                    logger.warning("시장가 주문 토큰 만료 — 재발급 후 재시도")
                    _reset_token()
                    await asyncio.sleep(1)
                    return await _kis_order_market(tr_id, code, quantity, retry=False, _pre_balance=_pre_balance)
                if "초과" in msg and attempt < _RATE_LIMIT_RETRIES:
                    logger.warning(f"시장가 주문 rate limit ({attempt}/{_RATE_LIMIT_RETRIES}): {code} — {attempt * _RATE_LIMIT_BASE_SEC}초 후 재시도")
                    await asyncio.sleep(attempt * _RATE_LIMIT_BASE_SEC)
                    continue
                logger.error(f"시장가 주문 실패 ({code}): {msg}")
                return None
        except Exception as e:
            if attempt < _RATE_LIMIT_RETRIES:
                await asyncio.sleep(attempt * _RATE_LIMIT_BASE_SEC)
                continue
            logger.error(f"시장가 주문 오류: {e}")
    return None
