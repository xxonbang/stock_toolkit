"""KIS 모의투자 자동매매 — 매수/매도 주문 + 수익률 감시"""
import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from daemon.config import (
    KIS_MOCK_APP_KEY, KIS_MOCK_APP_SECRET, KIS_MOCK_ACCOUNT_NO, KIS_MOCK_BASE_URL,
    TRADE_TAKE_PROFIT_PCT, TRADE_STOP_LOSS_PCT, TRADE_TRAILING_STOP_PCT, TRADE_MIN_AMOUNT_PER_STOCK,
    DATA_BASE_URL, SUPABASE_URL, SUPABASE_SECRET_KEY,
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
_token_last_refresh: float = 0  # 마지막 발급 시도 시각 (쿨다운용)
_TOKEN_TTL = 3500  # KIS 토큰 유효기간 ~1시간, 여유 두고 58분
_TOKEN_COOLDOWN = 65  # 재발급 쿨다운 (KIS 1분 제한 대비 65초)
_TOKEN_ACTIVATE_WAIT = 10  # 발급 후 활성화 대기 (초, KIS 모의투자 토큰 활성화 지연 대비)
_RATE_LIMIT_RETRIES = 3  # rate limit 재시도 횟수
_RATE_LIMIT_BASE_SEC = 2  # 재시도 기본 대기 (2, 4, 6초)


async def _load_token_from_supabase() -> str | None:
    """Supabase api_credentials에서 모의투자 토큰 로드 (유효 시에만 반환)"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/api_credentials?service_name=eq.kis_mock&credential_type=eq.access_token&is_active=eq.true&select=credential_value,expires_at"
        headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}
        session = await get_session()
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return None
            rows = await resp.json()
            if not rows:
                return None
            row = rows[0]
            expires_at = row.get("expires_at", "")
            if not expires_at:
                return None
            # 만료 체크 (UTC 기준)
            from datetime import datetime as _dt, timezone as _tz
            exp = _dt.fromisoformat(expires_at.replace("Z", "+00:00"))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=_tz.utc)
            remaining = (exp - _dt.now(_tz.utc)).total_seconds()
            if remaining < 120:  # 2분 미만이면 만료 임박 → 재발급
                return None
            import json as _json
            token_data = _json.loads(row["credential_value"])
            token = token_data.get("access_token", "")
            if not token:
                return None
            logger.info(f"Supabase에서 모의투자 토큰 로드 (잔여 {remaining/60:.0f}분)")
            return token
    except Exception as e:
        logger.debug(f"Supabase 토큰 로드 실패 (fallback): {e}")
        return None


async def _save_token_to_supabase(token: str, issued_at: float) -> None:
    """모의투자 토큰을 Supabase api_credentials에 저장 (upsert)"""
    try:
        import json as _json
        from datetime import datetime as _dt, timezone as _tz
        issued = _dt.fromtimestamp(issued_at, tz=_tz.utc)
        expires = _dt.fromtimestamp(issued_at + _TOKEN_TTL, tz=_tz.utc)
        token_data = _json.dumps({"access_token": token, "issued_at": issued.isoformat(), "expires_at": expires.isoformat()})
        headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}
        session = await get_session()
        # 기존 레코드 확인
        check_url = f"{SUPABASE_URL}/rest/v1/api_credentials?service_name=eq.kis_mock&credential_type=eq.access_token&select=id"
        async with session.get(check_url, headers=headers) as resp:
            existing = await resp.json() if resp.status == 200 else []
        if existing:
            # 업데이트
            url = f"{SUPABASE_URL}/rest/v1/api_credentials?service_name=eq.kis_mock&credential_type=eq.access_token"
            body = {"credential_value": token_data, "expires_at": expires.isoformat(), "is_active": True}
            async with session.patch(url, json=body, headers=headers) as resp:
                if resp.status in (200, 204):
                    logger.info("Supabase에 모의투자 토큰 저장 완료")
        else:
            # 신규 삽입
            url = f"{SUPABASE_URL}/rest/v1/api_credentials"
            body = {"service_name": "kis_mock", "credential_type": "access_token", "credential_value": token_data, "expires_at": expires.isoformat(), "is_active": True, "description": "KIS 모의투자 토큰 (daemon 자동 갱신)"}
            async with session.post(url, json=body, headers=headers) as resp:
                if resp.status in (200, 201):
                    logger.info("Supabase에 모의투자 토큰 신규 저장")
    except Exception as e:
        logger.debug(f"Supabase 토큰 저장 실패 (무시): {e}")


async def _ensure_mock_token() -> str | None:
    """모의투자 토큰 발급 — Supabase 공유 + 메모리 캐시 + 쿨다운"""
    global _access_token, _token_issued_at, _token_last_refresh
    now = time.time()

    # 1. 메모리 캐시에 유효한 토큰이 있으면 그대로 사용
    if _access_token and (now - _token_issued_at) < _TOKEN_TTL:
        return _access_token

    # 2. Supabase에서 공유 토큰 로드 시도
    shared = await _load_token_from_supabase()
    if shared:
        _access_token = shared
        _token_issued_at = now  # 메모리 TTL 리셋
        return _access_token

    # 3. 쿨다운: 마지막 발급 시도로부터 65초 미경과 시 대기
    since_last = now - _token_last_refresh
    if _token_last_refresh > 0 and since_last < _TOKEN_COOLDOWN:
        wait = _TOKEN_COOLDOWN - since_last
        logger.info(f"토큰 쿨다운 대기: {wait:.0f}초")
        await asyncio.sleep(wait)

    # 4. KIS API로 재발급
    _access_token = ""
    _token_last_refresh = time.time()
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
                if "error_code" in data:
                    logger.warning(f"토큰 발급 제한: {data.get('error_description', '')}")
                    return None
                _access_token = data.get("access_token", "")
                if not _access_token:
                    return None
                _token_issued_at = time.time()
                # 활성화 대기: KIS 모의투자 토큰은 발급 직후 비활성 상태일 수 있음
                logger.info(f"토큰 발급 완료, {_TOKEN_ACTIVATE_WAIT}초 활성화 대기")
                await asyncio.sleep(_TOKEN_ACTIVATE_WAIT)
                # 5. Supabase에 저장 (다른 프로세스와 공유)
                await _save_token_to_supabase(_access_token, _token_issued_at)
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


def _load_ma20_cache() -> dict[str, float]:
    """종목별 MA20 캐시 로드"""
    import json
    from pathlib import Path
    cache_attr = "_ma20_cache"
    if hasattr(_load_ma20_cache, cache_attr):
        return getattr(_load_ma20_cache, cache_attr)
    result = {}
    cache_path = Path(__file__).parent / "ma20_cache.json"
    if cache_path.exists():
        try:
            with open(cache_path, encoding="utf-8") as f:
                result = json.load(f)
        except Exception:
            pass
    setattr(_load_ma20_cache, cache_attr, result)
    return result


def select_gapup_momentum(signals: list | None, top_n: int = 1) -> list[dict]:
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

        # MA200 필터 (값 없으면 판단 불가 → 제외)
        ma200 = ma200_map.get(code, 0)
        if ma200 <= 0 or current <= ma200:
            continue

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
    # fallback: 잔고 조회 API의 매수 평균단가 (매수 시에만 — 매도 시 매수가가 반환되므로 부정확)
    if not is_sell:
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
    """KIS 잔고 조회 API로 특정 종목 보유 수량 확인.
    반환: 보유 수량 (0 이상) 또는 -1 (조회 실패)."""
    try:
        token = await _ensure_mock_token()
        if not token:
            return -1  # 조회 실패
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
                return 0  # 종목이 잔고에 없음 = 보유 0주
    except Exception as e:
        logger.warning(f"잔고 조회 실패: {code} {e}")
    return -1  # 조회 실패


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


async def place_buy_order_with_qty(code: str, name: str, price: int, quantity: int, skip_sim: bool = False) -> bool:
    """수량을 직접 지정하여 시장가 매수 (미체결 방지)"""
    if await is_upper_limit(code, price):
        logger.info(f"상한가 종목 스킵 — {name}({code}) {price:,}원")
        return False
    position = await insert_buy_order(code, name, price, quantity)
    if not position:
        return False

    # 매수 전 기존 잔고 기록 (추가 매수 시 기존 보유분 차감용)
    pre_balance = await _check_balance_qty(code)
    if pre_balance < 0:
        pre_balance = 0  # 조회 실패 시 0으로 간주 (매수 방향이므로 안전)

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
        # 부분체결 잔량 재주문 (최대 2회 추가 시도)
        if 0 < filled_qty < quantity:
            remaining = quantity - filled_qty
            for retry in range(1, 3):
                logger.info(f"부분체결 잔량 재주문 ({retry}/2): {name}({code}) {remaining}주")
                await asyncio.sleep(2)
                retry_result = await _kis_order_market("VTTC0802U", code, remaining)
                if not retry_result:
                    logger.warning(f"잔량 재주문 실패: {name}({code}) {remaining}주")
                    break
                await asyncio.sleep(1)
                post_bal = await _check_balance_qty(code)
                if post_bal < 0:
                    logger.warning(f"잔량 재주문 후 잔고 조회 실패: {name}({code})")
                    break
                new_filled = post_bal - pre_balance
                if new_filled > filled_qty:
                    added = new_filled - filled_qty
                    filled_qty = min(new_filled, quantity)
                    remaining = quantity - filled_qty
                    logger.info(f"잔량 추가 체결: {name}({code}) +{added}주 → 총 {filled_qty}주")
                if remaining <= 0:
                    break
            if remaining > 0:
                logger.warning(f"부분체결 최종: {name}({code}) {filled_qty}/{quantity}주 (잔량 {remaining}주 미체결)")

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
        # 비선택 전략 가상 시뮬레이션 생성 (갭업 매수에서는 스킵 — 당일 청산이므로 시뮬 무의미)
        if not skip_sim:
            try:
                config = await _get_trade_config()
                active_strategy = config.get("strategy_type", "fixed")
                sim_strategy = "stepped" if active_strategy == "fixed" else "fixed"
                trade_id = position["id"]
                user_id = config.get("user_id") or ""
                if not user_id:
                    logger.warning(f"가상 시뮬레이션 스킵: user_id 없음 (config)")
                else:
                    await _create_simulation(
                        trade_id=trade_id,
                        strategy_type=sim_strategy,
                        entry_price=fill_price,
                        user_id=user_id,
                    )
                    # 시간전략(11:00 매도) 시뮬레이션 — 11:00 이전 매수에서만 생성
                    if datetime.now(_KST).hour < 11:
                        await _create_simulation(
                            trade_id=trade_id,
                            strategy_type="time_exit",
                            entry_price=fill_price,
                            user_id=user_id,
                        )
            except Exception as e:
                logger.warning(f"가상 시뮬레이션 생성 오류: {e}")
        return True
    # KIS 주문 실패 → DB pending 정리
    from daemon.position_db import delete_position
    try:
        await delete_position(position["id"])
    except Exception as e:
        logger.error(f"매수 실패 pending 삭제 오류 (orphan 가능): {name}({code}) {e}")
    logger.warning(f"매수 실패 → pending 삭제: {name}({code})")
    return False


async def place_sell_order(code: str, name: str, price: int, quantity: int, position_id: str, reason: str, buy_price: int) -> bool:
    try:
        result = await _kis_order_market("VTTC0801U", code, quantity)
        if not result:
            # KIS 주문 실패 → DB 미변경 (KIS/DB 불일치 방지)
            logger.error(f"KIS 매도 주문 실패 — DB 미변경: {name}({code})")
            unmark_selling(position_id)
            await send_telegram(
                f"<b>⚠️ KIS 매도 주문 실패</b>\n{name} ({code})\n"
                f"사유: {reason}\nDB 상태 유지 (filled) — 다음 체크에서 재시도"
            )
            return False
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
        # 예외 발생 시 DB 미변경 (KIS/DB 불일치 방지)
        logger.error(f"매도 처리 오류 — DB 미변경: {name}({code}) {e}")
        unmark_selling(position_id)
        return False


def _reset_token():
    global _access_token, _token_issued_at
    _access_token = ""
    _token_issued_at = 0
    # Supabase 구 토큰도 무효화 (비동기 불가 → is_active=false로 마킹)
    try:
        import asyncio
        asyncio.ensure_future(_invalidate_supabase_token())
    except Exception:
        pass  # best-effort


async def _invalidate_supabase_token():
    """Supabase의 kis_mock 토큰 비활성화 (구 토큰 재로드 방지)"""
    try:
        headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
                    "Content-Type": "application/json"}
        session = await get_session()
        url = f"{SUPABASE_URL}/rest/v1/api_credentials?service_name=eq.kis_mock&credential_type=eq.access_token"
        async with session.patch(url, json={"is_active": False}, headers=headers) as resp:
            if resp.status in (200, 204):
                logger.info("Supabase 모의투자 토큰 무효화 완료")
    except Exception:
        pass  # best-effort


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
        # 갭업 모멘텀 실제 매매는 schedule_gapup_open()에서 처리 (09:01/09:30)
        # 여기서는 5팩터 시뮬레이션만 생성하고 return
        use_criteria = config.get("criteria_filter", False)
        all_scored = select_research_optimal(cross_data, top_n=999, criteria_filter=use_criteria)
        if all_scored:
            try:
                await _create_stepped_simulations(all_scored[:2], config)
            except Exception as e:
                logger.warning(f"5팩터 시뮬 생성 오류: {e}")
        try:
            await _create_api_leader_simulations(cross_data, config)
        except Exception as e:
            logger.warning(f"API∧대장주 시뮬 생성 오류: {e}")
        logger.info(f"research_optimal: 5팩터 시뮬 {len(all_scored)}건 처리, 실매매는 갭업 스케줄에서")
        return
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

    # 시뮬레이션: research_optimal 모드에서는 위에서 이미 처리하고 return했으므로
    # 여기는 기타 모드(토글 기반)에서의 시뮬 생성
    try:
        await _create_api_leader_simulations(cross_data, config)
    except Exception as e:
        logger.warning(f"API∧대장주 시뮬 생성 오류: {e}")


async def _fetch_volume_rank(token: str) -> list[dict]:
    """KIS 거래량순위 API (실투자 도메인) — 상위 30종목 획득 후 시가/전일종가 추가 조회.
    순위분석 API는 모의투자 미지원 → 실투자 앱키+Supabase 토큰 사용.
    실패 시 빈 리스트 (fallback으로 기존 200종목 스캔)."""
    REAL_URL = "https://openapi.koreainvestment.com:9443"
    try:
        # 실투자 토큰 로드 (Supabase api_credentials service_name='kis')
        from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
        session = await get_session()
        sb_headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}
        sb_url = f"{SUPABASE_URL}/rest/v1/api_credentials?service_name=eq.kis&credential_type=eq.access_token&is_active=eq.true&select=credential_value"
        async with session.get(sb_url, headers=sb_headers) as sb_resp:
            sb_data = await sb_resp.json()
        if not sb_data or not isinstance(sb_data, list) or not sb_data[0].get("credential_value"):
            logger.debug("volume-rank: 실투자 토큰 없음 → fallback")
            return []
        import json as _json
        real_token = _json.loads(sb_data[0]["credential_value"]).get("access_token", "")
        if not real_token:
            return []

        from daemon.config import KIS_APP_KEY, KIS_APP_SECRET
        real_headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {real_token}",
            "appkey": KIS_APP_KEY, "appsecret": KIS_APP_SECRET,
            "tr_id": "FHPST01710000", "custtype": "P",
        }
        params = {
            "FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20171",
            "FID_INPUT_ISCD": "0000", "FID_DIV_CLS_CODE": "0", "FID_BLNG_CLS_CODE": "0",
            "FID_TRGT_CLS_CODE": "111111111", "FID_TRGT_EXLS_CLS_CODE": "0000101101",  # 우선주+ETF+ETN+SPAC 제외
            "FID_INPUT_PRICE_1": "0", "FID_INPUT_PRICE_2": "0",
            "FID_VOL_CNT": "0", "FID_INPUT_DATE_1": "",
        }
        items = None
        for _vr_attempt in range(1, 4):
            try:
                async with session.get(f"{REAL_URL}/uapi/domestic-stock/v1/quotations/volume-rank", params=params, headers=real_headers) as resp:
                    if resp.status != 200:
                        logger.warning(f"volume-rank HTTP {resp.status} (시도 {_vr_attempt}/3)")
                        await asyncio.sleep(_vr_attempt * 2)
                        continue
                    text = await resp.text()
                    if not text or not text.strip().startswith("{"):
                        logger.warning(f"volume-rank 빈/비정상 응답 (시도 {_vr_attempt}/3): {text[:100]}")
                        await asyncio.sleep(_vr_attempt * 2)
                        continue
                    import json as _json2
                    data = _json2.loads(text)
                    if data.get("rt_cd") != "0" or not data.get("output"):
                        logger.warning(f"volume-rank rt_cd={data.get('rt_cd')} msg={data.get('msg1','')} (시도 {_vr_attempt}/3)")
                        await asyncio.sleep(_vr_attempt * 2)
                        continue
                    items = data["output"]
                    break
            except Exception as ve:
                logger.warning(f"volume-rank 요청 오류 (시도 {_vr_attempt}/3): {ve}")
                await asyncio.sleep(_vr_attempt * 2)
        if not items:
            return []

        # 30종목의 시가/전일종가를 개별 inquire-price로 추가 조회 (모의투자 토큰 사용)
        result = []
        for item in items:
            code = item.get("mksc_shrn_iscd", "")
            if not code:
                continue
            result.append({
                "code": code,
                "name": item.get("hts_kor_isnm", code),
                "price": int(item.get("stck_prpr", "0") or "0"),
                "open_price": 0,  # 아래에서 채움
                "prev_close": 0,  # 아래에서 채움
                "vol_rate": float(item.get("vol_inrt", "0") or "0"),  # 거래량 증가율
                "change_rate": float(item.get("prdy_ctrt", "0") or "0"),
                "acml_vol": int(item.get("acml_vol", "0") or "0"),
                "acml_tr_pbmn": int(item.get("acml_tr_pbmn", "0") or "0"),
            })

        # 시가/전일종가 보충 (모의투자 inquire-price, 5건 배치)
        for i in range(0, len(result), 5):
            batch = result[i:i+5]
            tasks = []
            for r in batch:
                url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
                p = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": r["code"]}
                tasks.append(session.get(url, params=p, headers=_order_headers(token, "FHKST01010100")))
            resps = await asyncio.gather(*tasks, return_exceptions=True)
            for r, resp in zip(batch, resps):
                if isinstance(resp, Exception):
                    continue
                try:
                    d = await resp.json()
                    out = d.get("output", {})
                    r["open_price"] = int(out.get("stck_oprc", "0") or "0")
                    r["prev_close"] = int(out.get("stck_sdpr", "0") or "0")
                    r["vol_rate"] = float(out.get("prdy_vrss_vol_rate", "0") or "0")
                except Exception:
                    pass
            await asyncio.sleep(0.5)

        logger.info(f"volume-rank: {len(result)}종목 (실투자 API + 시가/종가 보충)")
        return result
    except Exception as e:
        logger.warning(f"volume-rank 조회 실패: {e}")
        return []


async def _fetch_asking_price(token: str, code: str) -> dict | None:
    """KIS 호가잔량 조회 — 매수/매도 잔량 합계 반환."""
    try:
        session = await get_session()
        url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
        params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
        async with session.get(url, params=params, headers=_order_headers(token, "FHKST01010200")) as resp:
            data = await resp.json()
            if data.get("rt_cd") != "0":
                return None
            out = data.get("output1", {})
            total_ask = int(out.get("total_askp_rsqn", "0") or "0")  # 매도 잔량 합계
            total_bid = int(out.get("total_bidp_rsqn", "0") or "0")  # 매수 잔량 합계
            return {"ask": total_ask, "bid": total_bid, "ratio": total_bid / total_ask if total_ask > 0 else 0}
    except Exception:
        return None


async def _get_yesterday_trade_codes() -> set[str]:
    """직전 거래일 매매 종목 코드 조회 (1일 쿨다운용). 주말/공휴일 대비 3일 lookback."""
    try:
        lookback_utc = (datetime.now(_KST).replace(hour=0, minute=0, second=0) - timedelta(days=3, hours=9)).strftime("%Y-%m-%dT%H:%M:%S")
        today_utc = (datetime.now(_KST).replace(hour=0, minute=0, second=0) - timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:%S")
        url = f"{SUPABASE_URL}/rest/v1/auto_trades?and=(created_at.gte.{lookback_utc},created_at.lt.{today_utc})&status=neq.sim_only&select=code"
        headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}
        session = await get_session()
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                rows = await resp.json()
                return {r["code"] for r in rows if r.get("code")}
    except Exception as e:
        logger.warning(f"전일 매매 종목 조회 실패: {e}")
    return set()


async def _has_tv_traded_today() -> bool:
    """당일 거래대금 전략 매수 이력 확인 (재시작 중복매수 방어)."""
    try:
        today_utc = (datetime.now(_KST).replace(hour=0, minute=0, second=0) - timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:%S")
        url = f"{SUPABASE_URL}/rest/v1/auto_trades?created_at=gte.{today_utc}&status=neq.sim_only&select=id&limit=1"
        headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}
        session = await get_session()
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                rows = await resp.json()
                return len(rows) > 0
    except Exception as e:
        logger.warning(f"당일 매수 이력 조회 실패: {e}")
    return False


async def run_tv_scan_and_buy() -> int:
    """거래대금 기반 종목 선정 — volume-rank API → 거래대금 순 → TOP2 매수.
    필터: 가격대 1천~20만, 상승 출발, 갭<15%, 전일 매매 종목 1일 쿨다운.
    Returns: 매수 종목 수."""
    # #2 재시작 중복매수 방어: 당일 이미 매수 이력 있으면 스킵
    if await _has_tv_traded_today():
        logger.info("거래대금 스캔 스킵 — 당일 이미 매수 완료")
        return 0

    logger.info("거래대금 스캔 시작 — volume-rank API")

    token = await _ensure_mock_token()
    if not token:
        logger.warning("토큰 없음 — 거래대금 스캔 중단")
        return 0

    # volume-rank API 조회 (실투자 도메인, 상위 30종목)
    vr_items = await _fetch_volume_rank(token)
    if not vr_items:
        await send_telegram("📭 거래대금 스캔: volume-rank API 조회 실패")
        return 0
    # #3 acml_tr_pbmn 필드 검증 로깅
    sample = vr_items[0] if vr_items else {}
    logger.info(f"volume-rank: {len(vr_items)}종목 (acml_tr_pbmn={sample.get('acml_tr_pbmn', 'N/A')}, acml_vol={sample.get('acml_vol', 'N/A')})")

    # 전일 매매 종목 (1일 쿨다운)
    yesterday_codes = await _get_yesterday_trade_codes()
    if yesterday_codes:
        logger.info(f"전일 매매 쿨다운: {len(yesterday_codes)}종목 제외")

    # 필터 + 거래대금 순 정렬
    candidates = []
    for item in vr_items:
        code = item["code"]
        cur_price = item["price"]
        open_price = item["open_price"]
        prev_close = item["prev_close"]
        change_rate = item.get("change_rate", 0)

        # ETF/ETN 제외
        item_name = item["name"]
        if any(kw in item_name for kw in ("KODEX", "TIGER", "KOSEF", "ACE", "SOL", "KBSTAR", "HANARO", "ETN", "선물")):
            continue
        if code.startswith("Q"):
            continue
        # 가격대 필터
        if cur_price < 1000 or cur_price >= 200000:
            continue
        # 상승 출발
        if change_rate <= 0:
            continue
        # 갭 < 15% (open/prev 없으면 등락률로 대체 — #5 장중 등락률은 갭보다 클 수 있음)
        if open_price > 0 and prev_close > 0:
            gap_pct = (open_price - prev_close) / prev_close * 100
        else:
            gap_pct = change_rate
        if gap_pct >= 15:
            continue
        # 1일 쿨다운
        if code in yesterday_codes:
            logger.info(f"쿨다운 제외: {item['name']}({code})")
            continue

        # 거래대금: API 필드 → fallback 현재가×누적거래량
        trading_value = item.get("acml_tr_pbmn", 0)
        if trading_value <= 0:
            trading_value = cur_price * item.get("acml_vol", 0)
        # #4 거래대금 0인 종목 제외 (장 초반 미집계 방어)
        if trading_value <= 0:
            continue

        candidates.append({
            "code": code, "name": item["name"], "price": cur_price,
            "gap_pct": round(gap_pct, 1), "change_rate": round(change_rate, 1),
            "vol_rate": round(item.get("vol_rate", 0), 0),
            "trading_value": trading_value,
        })

    # 거래대금 순 정렬
    candidates.sort(key=lambda x: -x["trading_value"])
    targets = candidates[:2]

    if not targets:
        await send_telegram("📭 거래대금 스캔: 조건 충족 종목 없음 (상승+갭<15%+가격1천~20만+쿨다운)")
        return 0

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
        await send_telegram("📭 거래대금 스캔: 후보 있으나 보유중/상한가로 매수 불가")
        return 0

    # 잔고 조회
    balance = await fetch_available_balance()
    if balance <= 0:
        names = ", ".join(t["name"] for t in buy_targets)
        await send_telegram(f"⚠️ 거래대금 매수 실패: 잔고 없음\n대상: {names}")
        return 0

    amount_per = balance // len(buy_targets)

    # 텔레그램 보고
    rpt = [f"<b>📊 거래대금 모멘텀 스캔</b>"]
    rpt.append(f"")
    rpt.append(f"<b>[스캔]</b> VR API | 필터 통과 {len(candidates)}종목")
    rpt.append(f"잔고: {balance:,}원 | 종목당: {amount_per:,}원")
    rpt.append(f"")
    rpt.append(f"<b>[매수 대상]</b>")
    for t in buy_targets:
        qty = calc_quantity(amount_per, t["price"])
        invest = t["price"] * qty
        rpt.append(f"  📥 <b>{t['name']}</b> ({t['code']})")
        rpt.append(f"     등락{t['change_rate']:+.1f}% | 갭{t['gap_pct']:+.1f}% | 거래량{t['vol_rate']:.0f}%")
        rpt.append(f"     {t['price']:,}원 × {qty}주 = {invest:,}원")
    await send_telegram("\n".join(rpt))

    # 매수 실행
    bought = 0
    remaining_buys = [(t, calc_quantity(amount_per, t["price"])) for t in buy_targets if calc_quantity(amount_per, t["price"]) > 0]
    for round_num in range(1, 4):
        if not remaining_buys:
            break
        if round_num > 1:
            logger.info(f"거래대금 매수 {round_num}라운드: {len(remaining_buys)}종목 재시도")
            await asyncio.sleep(round_num * 5)
        failed_buys = []
        for t, qty in remaining_buys:
            success = await place_buy_order_with_qty(t["code"], t["name"], t["price"], qty, skip_sim=True)
            if success:
                bought += 1
            else:
                failed_buys.append((t, qty))
        remaining_buys = failed_buys
    if remaining_buys:
        names = ", ".join(t["name"] for t, _ in remaining_buys)
        await send_telegram(f"<b>🚨 거래대금 매수 최종 실패</b>\n{names}\n3라운드 재시도 소진")

    if bought > 0:
        try:
            from daemon.main import trigger_subscription_refresh
            await trigger_subscription_refresh()
        except Exception as e:
            logger.warning(f"거래대금 매수 후 구독 갱신 실패: {e}")
    logger.info(f"거래대금 스캔 매수 완료: {bought}종목")
    return bought


async def run_gapup_scan_and_buy(require_volume: bool = False, sim_only: bool = False) -> int:
    """장 시작 갭업 스캔: volume-rank 우선 → fallback 200종목 개별 조회.
    require_volume=True: 거래량 2배 필터 추가 (09:10 보완 매수용).
    sim_only=True: 매수 없이 종목 선정 결과만 auto_trades에 sim_only로 기록.
    Returns: 매수(또는 기록) 종목 수.
    """
    import json
    from pathlib import Path

    vol_label = "+거래량2배" if require_volume else ""
    logger.info(f"갭업 스캔 시작{vol_label} — stock-master 상위 200종목 조회")

    # 1) stock-master에서 전종목 코드+이름 로드
    master_path = Path(__file__).parent.parent / "results" / "stock-master.json"
    if not master_path.exists():
        logger.warning("stock-master.json 없음 — 갭업 스캔 중단")
        return 0
    try:
        with open(master_path, encoding="utf-8") as f:
            master = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"stock-master.json 파싱 실패 — 갭업 스캔 중단: {e}")
        return 0
    all_stocks = master.get("stocks", [])
    if not all_stocks:
        logger.warning("stock-master 종목 0개 — 갭업 스캔 중단")
        return 0

    # MA 캐시 로드
    ma200_map = _load_ma200_cache()
    ma20_map = _load_ma20_cache()

    # 2) 상위 200종목 현재가 병렬 조회 (거래대금 상위는 사전 판별 불가 → 무작위 200 대신, MA200 보유 종목 우선)
    # MA200이 있는 종목 = daily_ohlcv에 수집된 종목 = 유동성 있는 종목
    scan_targets = [s for s in all_stocks if s["code"] in ma200_map][:200]
    if not scan_targets:
        scan_targets = all_stocks[:200]
    logger.info(f"갭업 스캔 대상: {len(scan_targets)}종목")

    token = await _ensure_mock_token()
    if not token:
        logger.warning("토큰 없음 — 갭업 스캔 중단")
        return 0

    # === 우선 경로: volume-rank API (1회 호출, 상위 30종목) ===
    vr_candidates = []
    vr_items = await _fetch_volume_rank(token)
    if vr_items:
        logger.info(f"volume-rank: {len(vr_items)}종목 조회 완료")
        for item in vr_items:
            code = item["code"]
            cur_price = item["price"]
            open_price = item["open_price"]
            prev_close = item["prev_close"]
            if cur_price < 1000 or cur_price >= 200000:
                continue
            if open_price <= 0 or prev_close <= 0:
                continue
            gap_pct = (open_price - prev_close) / prev_close * 100
            ma200 = ma200_map.get(code, 0)
            if ma200 <= 0 or cur_price <= ma200:
                continue
            ma20 = ma20_map.get(code, 0)
            if ma20 <= 0 or cur_price <= ma20:
                continue
            if 0 <= gap_pct < 5:
                vol_rate = item["vol_rate"]
                if require_volume and vol_rate < 200:
                    continue
                # 전일 거래대금 (과열 필터 일봉에서 보충)
                prev_tv = 0
                vr_candidates.append({
                    "code": code, "name": item["name"], "price": cur_price,
                    "gap_pct": round(gap_pct, 2), "vol_rate": round(vol_rate, 0),
                    "prev_tv": prev_tv,
                })
        # 과열 필터 (기존과 동일 — 일봉 조회)
        if vr_candidates:
            vr_filtered = []
            for c in vr_candidates:
                try:
                    session = await get_session()
                    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-price"
                    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": c["code"],
                              "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "0"}
                    async with session.get(url, params=params, headers=_order_headers(token, "FHKST01010400")) as resp:
                        data = await resp.json()
                        bars = data.get("output", [])[:21]
                        if len(bars) < 4:
                            continue
                        ranges = []
                        for b in bars[1:4]:
                            bh = int(b.get("stck_hgpr", "0"))
                            blo = int(b.get("stck_lwpr", "0"))
                            if blo > 0:
                                ranges.append((bh - blo) / blo * 100)
                        avg_range_3 = sum(ranges) / len(ranges) if ranges else 0
                        prev_cl = int(bars[1].get("stck_clpr", "0"))
                        close_3d = int(bars[3].get("stck_clpr", "0"))
                        cum_3d = (prev_cl - close_3d) / close_3d * 100 if close_3d > 0 else 0
                        if avg_range_3 >= 13 or cum_3d >= 20:
                            logger.info(f"VR 과열 제외: {c['name']}({c['code']})")
                            continue
                        # 전일 거래대금 보충 + TV≥3억 필터
                        prev_tv_raw = int(bars[1].get("acml_vol", "0") or "0") * int(bars[1].get("stck_clpr", "0") or "0")
                        c["prev_tv"] = prev_tv_raw / 1e8  # 억원
                        if c["prev_tv"] < 3:
                            logger.info(f"VR 거래대금 제외: {c['name']}({c['code']}) TV={c['prev_tv']:.1f}억")
                            continue
                        # 20일 평균 거래대금(avgTV) ≥ 10억 필터
                        tv_list = []
                        for b in bars[1:21]:
                            bv = int(b.get("acml_vol", "0") or "0")
                            bc = int(b.get("stck_clpr", "0") or "0")
                            if bv > 0 and bc > 0:
                                tv_list.append(bv * bc)
                        avg_tv = (sum(tv_list) / len(tv_list) / 1e8) if tv_list else 0
                        c["avg_tv"] = round(avg_tv, 1)
                        if avg_tv < 10:
                            logger.info(f"VR avgTV 제외: {c['name']}({c['code']}) avgTV={avg_tv:.1f}억")
                            continue
                        vr_filtered.append(c)
                except Exception as e:
                    logger.warning(f"VR 과열 제외: {c['name']}({c['code']}) 오류 — {e}")
                await asyncio.sleep(0.3)
            vr_candidates = vr_filtered

        # volume-rank에서 2종목 이상 확보 시 → 호가잔량으로 최종 선정
        if len(vr_candidates) >= 2:
            import math as _math
            # 비율×log(전일TV) 스코어로 정렬
            for c in vr_candidates:
                log_tv = _math.log(max(c["prev_tv"] * 1e8, 1))
                c["_score"] = c["vol_rate"] * log_tv
            vr_candidates.sort(key=lambda x: -x["_score"])
            top5 = vr_candidates[:5]
            # TOP5에 대해 호가잔량 조회 → 매수잔량/매도잔량 비율 부여
            for t in top5:
                asking = await _fetch_asking_price(token, t["code"])
                t["bid_ask_ratio"] = asking["ratio"] if asking else 0
                await asyncio.sleep(0.3)
            # 매수잔량 > 매도잔량 종목 우선, 이후 스코어 순
            top5.sort(key=lambda x: (-1 if x["bid_ask_ratio"] > 1 else 0, -x.get("_score", 0)))
            candidates = top5
            logger.info(f"volume-rank 경로: {len(vr_candidates)}종목 → TOP{min(5, len(top5))} 호가 확인")
            # 아래 기존 스캔 건너뛰고 매수 단계로 이동
        else:
            if vr_items:
                logger.info(f"volume-rank {len(vr_items)}종목 중 갭업 조건 {len(vr_candidates)}종목 → fallback")
            vr_candidates = []  # fallback으로 진행

    # === fallback 경로: 기존 200종목 개별 조회 ===
    if len(vr_candidates) < 2:
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

        logger.info(f"fallback: 200종목 개별 조회 시작")
        candidates = []
        for batch_start in range(0, len(scan_targets), 5):
            batch = scan_targets[batch_start:batch_start + 5]
            results = await asyncio.gather(*[_fetch_detail(s["code"]) for s in batch])
            for stock, out in zip(batch, results):
                if not out:
                    continue
                code = stock["code"]
                name = stock.get("name", code)
                cur_price = int(out.get("stck_prpr", "0"))
                open_price = int(out.get("stck_oprc", "0"))
                prev_close = int(out.get("stck_sdpr", "0"))
                if cur_price < 1000 or cur_price >= 200000:
                    continue
                if open_price <= 0 or prev_close <= 0:
                    continue
                gap_pct = (open_price - prev_close) / prev_close * 100
                ma200 = ma200_map.get(code, 0)
                if ma200 <= 0 or cur_price <= ma200:
                    continue
                ma20 = ma20_map.get(code, 0)
                if ma20 <= 0 or cur_price <= ma20:
                    continue
                if 0 <= gap_pct < 5:
                    vol_rate = float(out.get("prdy_vrss_vol_rate", "0") or "0")
                    if require_volume and vol_rate < 200:
                        continue
                    candidates.append({
                        "code": code, "name": name, "price": cur_price,
                        "gap_pct": round(gap_pct, 2), "vol_rate": round(vol_rate, 0),
                    })
            await asyncio.sleep(0.5)
        logger.info(f"갭업 스캔 결과: {len(candidates)}종목 기본 조건 충족")
        # 과열 필터
        if candidates:
            filtered = []
            for c in candidates:
                try:
                    session = await get_session()
                    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-price"
                    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": c["code"],
                              "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "0"}
                    async with session.get(url, params=params, headers=_order_headers(token, "FHKST01010400")) as resp:
                        data = await resp.json()
                        bars = data.get("output", [])[:21]
                        if len(bars) < 4:
                            logger.info(f"과열 제외: {c['name']}({c['code']}) 일봉 부족")
                            continue
                        ranges = []
                        for b in bars[1:4]:
                            bh = int(b.get("stck_hgpr", "0"))
                            blo = int(b.get("stck_lwpr", "0"))
                            if blo > 0:
                                ranges.append((bh - blo) / blo * 100)
                        avg_range_3 = sum(ranges) / len(ranges) if ranges else 0
                        prev_cl = int(bars[1].get("stck_clpr", "0"))
                        close_3d = int(bars[3].get("stck_clpr", "0"))
                        cum_3d = (prev_cl - close_3d) / close_3d * 100 if close_3d > 0 else 0
                        if avg_range_3 >= 13 or cum_3d >= 20:
                            logger.info(f"과열 제외: {c['name']}({c['code']})")
                            continue
                        # 전일 거래대금 보충 + TV≥3억 필터
                        prev_tv_raw = int(bars[1].get("acml_vol", "0") or "0") * int(bars[1].get("stck_clpr", "0") or "0")
                        c["prev_tv"] = prev_tv_raw / 1e8  # 억원
                        if c["prev_tv"] < 3:
                            logger.info(f"거래대금 제외: {c['name']}({c['code']}) TV={c['prev_tv']:.1f}억")
                            continue
                        # 20일 평균 거래대금(avgTV) ≥ 10억 필터
                        tv_list = []
                        for b in bars[1:21]:
                            bv = int(b.get("acml_vol", "0") or "0")
                            bc = int(b.get("stck_clpr", "0") or "0")
                            if bv > 0 and bc > 0:
                                tv_list.append(bv * bc)
                        avg_tv = (sum(tv_list) / len(tv_list) / 1e8) if tv_list else 0
                        c["avg_tv"] = round(avg_tv, 1)
                        if avg_tv < 10:
                            logger.info(f"avgTV 제외: {c['name']}({c['code']}) avgTV={avg_tv:.1f}억")
                            continue
                        filtered.append(c)
                except Exception as e:
                    logger.warning(f"과열 제외: {c['name']}({c['code']}) 오류 — {e}")
                await asyncio.sleep(0.3)
            logger.info(f"과열 필터 후: {len(filtered)}종목 (제외 {len(candidates) - len(filtered)}종목)")
            candidates = filtered

    if not candidates:
        cond = "갭0~5% + MA200↑ + 과열필터 + TV≥3억 + avgTV≥10억" + ("+거래량2배" if require_volume else "")
        await send_telegram(f"📭 갭업 스캔: 조건 충족 종목 없음 ({cond})")
        return 0

    # 비율×log(전일TV) 스코어 정렬 (VR 경로에서는 이미 호가 기반 정렬 완료)
    if not any("bid_ask_ratio" in c for c in candidates):
        import math as _math
        for c in candidates:
            if "_score" not in c:
                log_tv = _math.log(max(c.get("prev_tv", 0) * 1e8, 1))
                c["_score"] = c.get("vol_rate", 0) * log_tv
        candidates.sort(key=lambda x: -x.get("_score", 0))
    targets = candidates[:2]

    # 보유/주문 중 필터 (sim_only에서는 건너뜀 — 전략 비교를 위해 동일 종목 기록 허용)
    if sim_only:
        buy_targets = targets[:2]
    else:
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
        return 0

    # === sim_only 모드: 매수 없이 auto_trades에 sim_only로 기록 ===
    if sim_only:
        recorded = 0
        rpt = [f"<b>📈 갭업 시뮬 기록</b> (sim_only)"]
        for t in buy_targets[:2]:
            try:
                session = await get_session()
                url = f"{SUPABASE_URL}/rest/v1/auto_trades"
                headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
                           "Content-Type": "application/json", "Prefer": "return=representation"}
                body = {"code": t["code"], "name": t["name"], "side": "buy",
                        "order_price": t["price"], "quantity": 0, "status": "sim_only",
                        "sell_reason": "gapup_sim"}
                async with session.post(url, json=body, headers=headers) as resp:
                    if resp.status in (200, 201):
                        recorded += 1
                        rpt.append(f"  {t['name']}({t['code']}) {t['price']:,}원 갭{t['gap_pct']:+.1f}%")
            except Exception as e:
                logger.warning(f"갭업 시뮬 기록 실패: {t['name']} — {e}")
        await send_telegram("\n".join(rpt))
        logger.info(f"갭업 시뮬 기록 완료: {recorded}종목")
        return recorded

    # === 실전 매수 ===
    balance = await fetch_available_balance()
    if balance <= 0:
        names = ", ".join(t["name"] for t in buy_targets)
        await send_telegram(f"⚠️ 갭업 매수 실패: 잔고 없음\n대상: {names}")
        return 0

    amount_per = balance // len(buy_targets)

    scan_label = "📈 갭업 모멘텀 09:10 보완" if require_volume else "📈 갭업 모멘텀 스캔"
    scan_path = "VR" if any("bid_ask_ratio" in c for c in candidates) else "개별조회"
    rpt = [f"<b>{scan_label}</b>"]
    rpt.append(f"")
    rpt.append(f"<b>[스캔]</b> {scan_path} | 대상 {len(scan_targets)}종목")
    rpt.append(f"갭0~5%+MA200↑+MA20↑: {len(candidates)}종목")
    rpt.append(f"잔고: {balance:,}원 | 종목당: {amount_per:,}원")
    rpt.append(f"")
    rpt.append(f"<b>[매수 대상]</b>")
    for t in buy_targets:
        qty = calc_quantity(amount_per, t["price"])
        ma200_val = ma200_map.get(t["code"], 0)
        ma20_val = ma20_map.get(t["code"], 0)
        bid_ratio = t.get("bid_ask_ratio", 0)
        bid_info = f" 호가{bid_ratio:.1f}" if bid_ratio > 0 else ""
        invest = t["price"] * qty
        rpt.append(f"  📥 <b>{t['name']}</b> ({t['code']})")
        score_info = f" 스코어{t.get('_score', 0):.0f}" if t.get("_score") else ""
        tv_info = f" TV{t.get('prev_tv', 0):.0f}억" if t.get("prev_tv") else ""
        avg_tv_info = f" avgTV{t.get('avg_tv', 0):.0f}억" if t.get("avg_tv") else ""
        rpt.append(f"     갭+{t['gap_pct']:.1f}% | 거래량 {t['vol_rate']:.0f}%{bid_info}{tv_info}{avg_tv_info}{score_info}")
        rpt.append(f"     {t['price']:,}원 × {qty}주 = {invest:,}원")
        rpt.append(f"     MA200 {ma200_val:,.0f} | MA20 {ma20_val:,.0f}")
    await send_telegram("\n".join(rpt))

    bought = 0
    remaining_buys = [(t, calc_quantity(amount_per, t["price"])) for t in buy_targets if calc_quantity(amount_per, t["price"]) > 0]
    for round_num in range(1, 4):
        if not remaining_buys:
            break
        if round_num > 1:
            logger.info(f"갭업 매수 {round_num}라운드: {len(remaining_buys)}종목 재시도 ({round_num * 5}초 대기)")
            await asyncio.sleep(round_num * 5)
        failed_buys = []
        for t, qty in remaining_buys:
            success = await place_buy_order_with_qty(t["code"], t["name"], t["price"], qty, skip_sim=True)
            if success:
                bought += 1
            else:
                failed_buys.append((t, qty))
        remaining_buys = failed_buys
    if remaining_buys:
        names = ", ".join(t["name"] for t, _ in remaining_buys)
        await send_telegram(f"<b>🚨 갭업 매수 최종 실패</b>\n{names}\n3라운드 재시도 소진")

    if bought > 0:
        try:
            from daemon.main import trigger_subscription_refresh
            await trigger_subscription_refresh()
        except Exception as e:
            logger.warning(f"갭업 매수 후 구독 갱신 실패: {e}")
    logger.info(f"갭업 스캔 매수 완료: {bought}종목")
    return bought


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
        buy_mode = config.get("buy_signal_mode", "and")
        reason = None

        # 거래대금 모멘텀: 장중 TP/SL 미적용 (15:15 전량 청산), 비상 손절만 적용
        if buy_mode == "research_optimal":
            pnl = calc_pnl_pct(buy_price, current_price)
            if pnl <= -15:
                reason = "stop_loss"
                logger.warning(f"비상 손절 발동: {pos['name']}({code}) {pnl:.1f}%")
            else:
                continue

        elif strategy_type == "stepped":
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
    """KIS 미체결 주문 전체 취소 + DB pending 정리.
    KIS 모의투자는 inquire-nccs API 미지원(404)이므로 DB 정리만 수행."""
    from daemon.position_db import invalidate_cache, delete_position
    # KIS 모의투자는 미체결 조회 API 미지원 → 시장가 즉시체결이므로 스킵
    logger.info("모의투자: 미체결 API 스킵 (시장가 즉시체결 간주), DB pending 정리")

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

async def close_gapup_sim_records():
    """당일 gapup_sim 레코드에 종가 P&L 기록 (#7 sim P&L 추적)."""
    try:
        today_utc = (datetime.now(_KST).replace(hour=0, minute=0, second=0) - timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:%S")
        url = f"{SUPABASE_URL}/rest/v1/auto_trades?created_at=gte.{today_utc}&sell_reason=eq.gapup_sim&status=eq.sim_only&select=id,code,order_price"
        headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}
        session = await get_session()
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200: return
            sims = await resp.json()
        if not sims: return
        token = await _ensure_mock_token()
        for sim in sims:
            cp = await _get_current_price(sim["code"]) if token else 0
            bp = sim.get("order_price", 0)
            pnl = round((cp - bp) / bp * 100, 2) if cp > 0 and bp > 0 else 0
            patch_url = f"{SUPABASE_URL}/rest/v1/auto_trades?id=eq.{sim['id']}"
            patch_headers = {**headers, "Content-Type": "application/json", "Prefer": "return=minimal"}
            async with session.patch(patch_url, json={"sell_price": cp, "pnl_pct": pnl, "sold_at": datetime.now(_KST).isoformat()}, headers=patch_headers) as _:
                pass
            await asyncio.sleep(0.3)
        logger.info(f"gapup_sim P&L 기록: {len(sims)}건")
    except Exception as e:
        logger.warning(f"gapup_sim P&L 기록 실패: {e}")


async def sell_all_positions_force():
    """전량 강제 매도 — 갭업 당일청산용. 수익/손실 불문 전 포지션 시장가 매도."""
    from daemon.position_db import invalidate_cache
    await cancel_all_pending_orders()
    positions = await get_active_positions(force_refresh=True)
    filled = [p for p in positions if p["status"] in ("filled", "sell_requested")]
    if not filled:
        logger.info("강제 매도: 보유 포지션 없음")
        return
    logger.info(f"강제 매도: {len(filled)}종목 전량 매도 시작")
    remaining = list(filled)
    for round_num in range(1, 4):  # 최대 3라운드 재시도
        if not remaining:
            break
        if round_num > 1:
            logger.info(f"강제 매도 {round_num}라운드: {len(remaining)}종목 재시도 ({round_num * 5}초 대기)")
            await asyncio.sleep(round_num * 5)
        failed = []
        for pos in remaining:
            position_id = pos["id"]
            if is_selling(position_id):
                # 다른 경로에서 매도 진행 중 → 이번 라운드 스킵, 다음 라운드에서 재확인
                failed.append(pos)
                continue
            mark_selling(position_id)
            buy_price = pos.get("filled_price") or pos.get("order_price", 0)
            # 중복 매도 방어: KIS 잔고 확인 (OOM 재시작 시 이전 매도 이미 체결 가능)
            bal = await _check_balance_qty(pos["code"])
            if bal == 0:  # 잔고 0 = 이미 체결 확인 (bal=-1은 조회 실패 → 정상 매도 진행)
                logger.info(f"강제 매도 스킵 (잔고 0 — 이미 체결): {pos['name']}({pos['code']})")
                # 실체결가 우선 조회, 없으면 현재가, 최종 fallback은 매수가
                sell_price = await _get_actual_fill_price(pos["code"], is_sell=True)
                if sell_price <= 0:
                    sell_price = await _get_current_price(pos["code"]) or buy_price
                pnl = calc_pnl_pct(buy_price, sell_price)
                pos["_current_price"] = sell_price  # 텔레그램 보고용
                await update_position_sold(position_id, sell_price, pnl, "eod_close")
                _peak_prices.pop(position_id, None)
                unmark_selling(position_id)
                continue
            current_price = await _get_current_price(pos["code"])
            pos["_current_price"] = current_price
            pnl = calc_pnl_pct(buy_price, current_price) if buy_price > 0 and current_price > 0 else 0
            try:
                result = await _kis_order_market("VTTC0801U", pos["code"], pos["quantity"])
                if not result:
                    logger.error(f"강제 매도 실패 ({round_num}R): {pos['name']}({pos['code']})")
                    unmark_selling(position_id)
                    failed.append(pos)
                    continue
                # 체결 확인
                filled_qty = await _verify_sell_fill(pos["code"], pos["quantity"])
                if filled_qty <= 0:
                    # 미체결 조회 실패 → 모의투자 시장가 즉시체결 간주
                    filled_qty = pos["quantity"]
                    logger.warning(f"강제 매도 체결 조회 실패 → 즉시체결 간주: {pos['name']}({pos['code']})")
                sell_price = current_price
                actual = await _get_actual_fill_price(pos["code"], is_sell=True)
                if actual > 0:
                    sell_price = actual
                if sell_price <= 0:
                    sell_price = buy_price  # 최종 fallback: 매수가 (0 저장 방지)
                    logger.warning(f"강제 매도 체결가 조회 실패 → 매수가 fallback: {pos['name']}({pos['code']})")
                pnl = calc_pnl_pct(buy_price, sell_price)
                if filled_qty < pos["quantity"]:
                    # 부분체결: 잔여 수량 DB 업데이트, 다음 라운드에서 재시도
                    await update_position_quantity(position_id, pos["quantity"] - filled_qty)
                    unmark_selling(position_id)
                    pos["quantity"] = pos["quantity"] - filled_qty
                    failed.append(pos)
                    logger.warning(f"강제 매도 부분체결: {pos['name']}({pos['code']}) {filled_qty}/{pos['quantity']+filled_qty}주")
                else:
                    await update_position_sold(position_id, sell_price, pnl, "eod_close")
                    _peak_prices.pop(position_id, None)
                logger.info(f"강제 매도: {pos['name']}({pos['code']}) {pnl:+.1f}% ({filled_qty}주)")
            except Exception as e:
                logger.error(f"강제 매도 오류: {pos['name']}({pos['code']}) {e}")
                unmark_selling(position_id)
                failed.append(pos)
            await asyncio.sleep(0.3)
        remaining = failed
    if remaining:
        names = ", ".join(p["name"] for p in remaining)
        logger.error(f"강제 매도 최종 실패: {names}")
        await send_telegram(f"<b>🚨 강제 매도 실패 ({len(remaining)}종목)</b>\n{names}\n3라운드 재시도 소진")
    # 텔레그램 보고
    if filled:
        lines = []
        total_pnl_amt = 0
        for pos in filled:
            bp = pos.get("filled_price") or pos.get("order_price", 0)
            cp = pos.get("_current_price", 0)
            qty = pos.get("quantity", 0)
            if bp > 0 and cp > 0:
                pnl_val = calc_pnl_pct(bp, cp)
                pnl_amt = (cp - bp) * qty
                total_pnl_amt += pnl_amt
                lines.append(f"  {pos['name']}({pos['code']}) {pnl_val:+.1f}%")
                lines.append(f"     {bp:,} → {cp:,}원 × {qty}주 ({pnl_amt:+,}원)")
            else:
                lines.append(f"  {pos['name']}({pos['code']})")
        rpt_lines = [
            f"<b>🔄 전량 강제 매도 완료</b>",
            f"{len(filled)}종목 매도",
        ] + lines + [
            f"",
            f"<b>당일 합계: {total_pnl_amt:+,}원</b>",
        ]
        await send_telegram("\n".join(rpt_lines))
    _orphan_sim_codes.clear()
    invalidate_cache()


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
                actual = await _get_actual_fill_price(pos["code"], is_sell=True)
                if actual > 0:
                    sell_price = actual
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
                    actual = await _get_actual_fill_price(pos_now["code"], is_sell=True)
                    if actual > 0:
                        sp = actual
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
    """15초마다 보유종목 현재가 REST API 조회 → 익절/손절/수동매도 + 시뮬 체크"""
    from daemon import main as _main
    from daemon.main import is_market_hours, is_market_day
    while not _main._shutdown:
        for _ in range(15):
            if _main._shutdown:
                return
            await asyncio.sleep(1)
        if not is_market_day() or not is_market_hours():
            continue
        try:
            positions = await get_active_positions(force_refresh=True)
            targets = [p for p in positions if p["status"] in ("filled", "sell_requested")]
            if targets:
                for pos in targets:
                    code = pos["code"]
                    price = await _get_current_price(code)
                    if price <= 0:
                        continue
                    await check_positions_for_sell({"code": code, "price": price})
                    await asyncio.sleep(0.3)  # API 호출 간격
                # 시뮬레이션 미생성 종목 자동 보완 (수동 매수 등 daemon 외부 경로 대응)
                await _ensure_simulations_for_filled(targets)
            # 시뮬레이션 독립 체크 — 실전 보유 0건이어도 실행
            await _check_orphan_simulations()
            # 5분마다 KIS 평단가 sync (분할 매수 시 DB 평단가 불일치 보정)
            await _sync_avg_prices(targets)
        except Exception as e:
            logger.error(f"매도 폴링 체크 오류: {e}")


_last_price_sync: float = 0


async def _sync_avg_prices(positions: list):
    """KIS 잔고 API의 실제 평단가(pchs_avg_pric)로 DB filled_price 갱신 (5분마다)"""
    global _last_price_sync
    now = time.time()
    if now - _last_price_sync < 300:  # 5분 쿨다운
        return
    _last_price_sync = now

    token = await _ensure_mock_token()
    if not token:
        return
    cano, acnt_cd = _parse_account()
    try:
        session = await get_session()
        url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance"
        params = {
            "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
            "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02",
            "UNPR_DVSN": "01", "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "00",
            "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
        }
        async with session.get(url, params=params, headers=_order_headers(token, "VTTC8434R")) as resp:
            data = await resp.json()
            if data.get("rt_cd") != "0":
                return
            kis_holdings = {s.get("pdno", ""): int(float(s.get("pchs_avg_pric", "0")))
                           for s in data.get("output1", []) if s.get("pdno")}
        # DB와 비교하여 차이 있으면 갱신
        for pos in positions:
            if pos["status"] != "filled":
                continue
            code = pos.get("code", "")
            db_price = pos.get("filled_price") or 0
            kis_price = kis_holdings.get(code, 0)
            if kis_price > 0 and db_price > 0 and abs(kis_price - db_price) > 1:
                await update_position_filled(pos["id"], kis_price)
                logger.info(f"평단가 sync: {pos.get('name','')}({code}) {db_price:,}→{kis_price:,}원")
    except Exception as e:
        logger.warning(f"평단가 sync 오류: {e}")


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


async def _create_stepped_simulations(scored_top2: list, config: dict):
    """기존 5팩터 스코어링 종목을 시뮬레이션으로 추적 (strategy_type=stepped).
    가상 auto_trades(sim_only) 레코드를 먼저 생성하여 UUID를 확보한 뒤 시뮬 생성.
    """
    from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
    from daemon.position_db import _supabase_request
    user_id = config.get("user_id", "")
    if not user_id or not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return
    today = datetime.now(_KST).strftime("%Y%m%d")
    # 중복 방지: ① open stepped 시뮬 종목 + ② 오늘 생성된 sim_only 종목
    existing_open = await _supabase_request(
        "GET",
        f"{SUPABASE_URL}/rest/v1/strategy_simulations?status=eq.open&strategy_type=eq.stepped&select=trade_id",
    )
    open_trade_ids = {r.get("trade_id") for r in (existing_open or [])}
    existing_trades = []
    if open_trade_ids:
        tid_filter = ",".join(open_trade_ids)
        existing_trades = await _supabase_request(
            "GET",
            f"{SUPABASE_URL}/rest/v1/auto_trades?id=in.({tid_filter})&select=code",
        ) or []
    existing_codes = {r.get("code") for r in existing_trades}
    # 오늘 생성된 sim_only도 중복 체크
    today_utc = (datetime.now(_KST).replace(hour=0, minute=0, second=0) - timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:%S")
    today_sim_only = await _supabase_request(
        "GET",
        f"{SUPABASE_URL}/rest/v1/auto_trades?status=eq.sim_only&created_at=gte.{today_utc}&select=code",
    )
    existing_codes |= {r.get("code") for r in (today_sim_only or [])}
    for item in scored_top2:
        code = item.get("code", "")
        name = item.get("name", code)
        # 실시간 현재가로 entry_price 설정 (cross_signal은 이전 시점 가격이므로)
        price = await _get_current_price(code)
        if price <= 0:
            price = (item.get("api_data") or {}).get("price", {}).get("current", 0)
        if price <= 0 or code in existing_codes:
            continue
        # 상한가 종목은 시뮬 생성 제외 (실제 매수 불가능)
        if await is_upper_limit(code, price):
            logger.info(f"Stepped 시뮬 스킵 (상한가): {name}({code}) {price:,}원")
            continue
        # 가상 auto_trades 레코드 생성 (trade_id UUID 확보용)
        virtual_trade = await _supabase_request("POST",
            f"{SUPABASE_URL}/rest/v1/auto_trades",
            json={"code": code, "name": name, "side": "buy",
                  "order_price": price, "quantity": 0, "status": "sim_only"},
            retries=0)
        if not virtual_trade:
            logger.warning(f"Stepped 시뮬 가상 trade 생성 실패: {name}")
            continue
        vt = virtual_trade[0] if isinstance(virtual_trade, list) else virtual_trade
        body = {
            "trade_id": vt["id"],
            "strategy_type": "stepped",
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
                    logger.info(f"Stepped 시뮬 생성: {name}({code}) {price:,}원 score={item.get('_score',0)}")
                else:
                    # 시뮬 생성 실패 → orphan sim_only 삭제
                    logger.warning(f"Stepped 시뮬 INSERT 실패 → sim_only 삭제: {name}({code})")
                    from daemon.position_db import delete_position
                    try:
                        await delete_position(vt["id"])
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"5팩터 시뮬 생성 오류 → sim_only 삭제: {code} {e}")
            from daemon.position_db import delete_position
            try:
                await delete_position(vt["id"])
            except Exception:
                pass


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
        # 실시간 현재가로 entry_price 설정 (cross_signal은 이전 시점 가격)
        real_price = await _get_current_price(item["code"])
        entry_price = real_price if real_price > 0 else item["price"]
        # 상한가 종목은 시뮬 생성 제외 (실제 매수 불가능)
        if await is_upper_limit(item["code"], entry_price):
            logger.info(f"API∧대장주 시뮬 스킵 (상한가): {item['name']}({item['code']}) {entry_price:,}원")
            continue
        # api_leader용 가상 auto_trades 레코드 생성 (trade_id UUID 필수)
        virtual_trade = await _supabase_request("POST",
            f"{SUPABASE_URL}/rest/v1/auto_trades",
            json={"code": item["code"], "name": item["name"], "side": "buy",
                  "order_price": entry_price, "quantity": 0, "status": "sim_only"},
            retries=0)
        if not virtual_trade:
            logger.warning(f"API∧대장주 가상 trade 생성 실패: {item['name']}")
            continue
        vt = virtual_trade[0] if isinstance(virtual_trade, list) else virtual_trade
        body = {
            "trade_id": vt["id"],
            "strategy_type": "api_leader",
            "entry_price": entry_price,
            "status": "open",
            "peak_price": entry_price,
            "stepped_stop_pct": -2.0,
            "user_id": user_id,
        }
        try:
            url = f"{SUPABASE_URL}/rest/v1/strategy_simulations"
            async with session.post(url, json=body, headers=headers) as resp:
                if resp.status in (200, 201):
                    logger.info(f"API∧대장주 시뮬 생성: {item['name']}({item['code']}) {entry_price:,}원 {item['score']}점")
                else:
                    err = await resp.text()
                    logger.warning(f"API∧대장주 시뮬 생성 실패 → sim_only 삭제: {resp.status} {err[:100]}")
                    from daemon.position_db import delete_position
                    try:
                        await delete_position(vt["id"])
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"API∧대장주 시뮬 생성 오류 → sim_only 삭제: {e}")
            from daemon.position_db import delete_position
            try:
                await delete_position(vt["id"])
            except Exception:
                pass


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


async def _check_stepped():
    """stepped 시뮬레이션 독립 체크 — Stepped 기본형 조건으로 매도"""
    from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        return
    now_kst = datetime.now(_KST)
    try:
        session = await get_session()
        headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}
        url = f"{SUPABASE_URL}/rest/v1/strategy_simulations?status=eq.open&strategy_type=eq.stepped&select=id,entry_price,peak_price,trade_id"
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return
            sims = await resp.json()
        if not sims:
            return

        config = await _get_trade_config()
        sl = config.get("stop_loss_pct", TRADE_STOP_LOSS_PCT)
        ts_pct = config.get("trailing_stop_pct", TRADE_TRAILING_STOP_PCT)
        preset = config.get("stepped_preset", "default")
        patch_headers = {**headers, "Content-Type": "application/json", "Prefer": "return=minimal"}

        # trade_id → code 매핑 (auto_trades 조인)
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

            # Stepped 기본형 조건 적용
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
                logger.info(f"5팩터 시뮬 close: {code} {exit_reason} pnl={pnl:+.1f}%")
            patch_url = f"{SUPABASE_URL}/rest/v1/strategy_simulations?id=eq.{sim['id']}"
            async with session.patch(patch_url, json=update_body, headers=patch_headers) as resp:
                pass
            await asyncio.sleep(0.2)
    except Exception as e:
        logger.warning(f"5팩터 시뮬 체크 오류: {e}")


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
    # api_leader + stepped 시뮬 독립 체크 (orphan_sim_codes 없어도 실행)
    await _check_api_leader_simulations()
    await _check_stepped()
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


_ORDER_MAX_RETRIES = 5  # 주문 최대 재시도 횟수
_ORDER_BASE_WAIT = 3    # 재시도 기본 대기 (초)


async def _kis_order_market(tr_id: str, code: str, quantity: int, _pre_balance: int | None = None) -> dict | None:
    """KIS 모의투자 시장가 주문 — 실패 시 토큰 재발급 + 최대 5회 재시도"""
    is_buy = tr_id == "VTTC0802U"
    if _pre_balance is None and is_buy:
        _pre_balance = await _check_balance_qty(code)
        if _pre_balance < 0:
            _pre_balance = None  # 조회 실패 시 잔고 비교 비활성화

    for attempt in range(1, _ORDER_MAX_RETRIES + 1):
        token = await _ensure_mock_token()
        if not token:
            # 토큰 발급 실패 → _ensure_mock_token 내부에서 쿨다운 처리됨
            logger.warning(f"토큰 없음 ({attempt}/{_ORDER_MAX_RETRIES}): {code}")
            continue

        # 매수 재시도 전 — 이전 주문이 이미 체결됐는지 잔고 확인
        if attempt > 1 and is_buy:
            cur_bal = await _check_balance_qty(code)
            if _pre_balance is not None and cur_bal >= 0 and cur_bal > _pre_balance:
                logger.warning(f"재시도 중단 — 이미 체결 감지: {code} 잔고 {_pre_balance}→{cur_bal}")
                return {"rt_cd": "0", "msg1": "이미 체결 (잔고 확인)"}

        url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/order-cash"
        cano, acnt_cd = _parse_account()
        body = {
            "CANO": cano, "ACNT_PRDT_CD": acnt_cd,
            "PDNO": code, "ORD_DVSN": "01", "ORD_QTY": str(quantity), "ORD_UNPR": "0",
        }
        try:
            session = await get_session()
            async with session.post(url, json=body, headers=_order_headers(token, tr_id)) as resp:
                if resp.status != 200:
                    logger.error(f"주문 HTTP {resp.status} ({attempt}/{_ORDER_MAX_RETRIES}): {code} {tr_id}")
                    if resp.status in (401, 403):
                        _reset_token()  # 인증 오류만 토큰 리셋
                    await asyncio.sleep(_ORDER_BASE_WAIT * attempt)
                    continue
                data = await resp.json()
                if data.get("rt_cd") == "0":
                    return data
                msg = data.get("msg1", "")
                if "만료" in msg or "token" in msg.lower() or "유효하지" in msg:
                    logger.warning(f"토큰 오류 ({attempt}/{_ORDER_MAX_RETRIES}): {msg}")
                    _reset_token()  # 토큰 관련 오류만 리셋
                    continue  # _ensure_mock_token에서 쿨다운 처리
                if "초과" in msg:
                    logger.warning(f"rate limit ({attempt}/{_ORDER_MAX_RETRIES}): {code}")
                    await asyncio.sleep(_ORDER_BASE_WAIT * attempt)
                    continue
                logger.error(f"주문 실패 ({attempt}/{_ORDER_MAX_RETRIES}) {code}: {msg}")
                await asyncio.sleep(_ORDER_BASE_WAIT)
                continue
        except Exception as e:
            logger.error(f"주문 오류 ({attempt}/{_ORDER_MAX_RETRIES}) {code}: {e}")
            await asyncio.sleep(_ORDER_BASE_WAIT * attempt)
            continue

    logger.error(f"주문 최종 실패 ({_ORDER_MAX_RETRIES}회 재시도 소진): {code} {tr_id}")
    return None
