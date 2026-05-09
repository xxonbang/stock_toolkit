"""셀트리온(068270) 횡보 매매 가상 시뮬 백테스트

매매 룰:
- 매수: 저가 <= 199,000원 (지정가 가정)
- 매도: 고가 >= 205,000원 (지정가 가정)
- 무한 사이클, 무손절, 1000만원 자본 시작
- 같은 1분봉에서 low<=199k AND high>=205k 동시 → 매수+매도 동시 처리

데이터:
- 분봉: KIS FHKST03010200 직접 fetch (최근 2거래일 — API 과거 날짜 지정 불가)
- 일봉: KIS FHKST03010100 (분봉 커버 이전 60일)

KIS 분봉 API 제약:
- inquire-time-itemchartprice (FHKST03010200)
- FID_INPUT_HOUR_1 = 시각(HHMMSS) 기준, 날짜 직접 지정 파라미터 없음
- 반환: 해당 시각 이전 최대 30건 (최근 거래일 기준)
- 과거 날짜 직접 지정 불가 → 최근 2거래일만 수집 가능

DB 적재:
- auto_trades: sim_only 상태로 각 사이클 1건
- strategy_simulations: strategy_type=celltrion_band, 각 사이클 1건
"""
import os
import sys
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "daemon" / ".env")

# ── 상수 ──────────────────────────────────────────────────────────────────
STOCK_CODE = "068270"
STOCK_NAME = "셀트리온"
BUY_PRICE = 199_000
SELL_PRICE = 205_000
SIM_START_CAPITAL = 10_000_000
STRATEGY_TYPE = "celltrion_band"
KST = timezone(timedelta(hours=9))
REAL_URL = "https://openapi.koreainvestment.com:9443"
MINUTE_API_SLEEP = 0.4  # 분봉 API 호출 간격(초)

SB_URL = os.getenv("SUPABASE_URL", "")
SB_KEY = os.getenv("SUPABASE_SECRET_KEY", "")
KIS_APP_KEY = os.getenv("KIS_APP_KEY", "")
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", "")

SB_HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
}
SB_WRITE_HEADERS = {
    **SB_HEADERS,
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


# ── Supabase 헬퍼 ─────────────────────────────────────────────────────────

def sb_get(path: str) -> list:
    url = f"{SB_URL}/rest/v1/{path}"
    req = urllib.request.Request(url, headers=SB_HEADERS)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def sb_post(path: str, body: dict) -> dict:
    url = f"{SB_URL}/rest/v1/{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=SB_WRITE_HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
    return result[0] if isinstance(result, list) and result else result


def sb_delete(path: str):
    url = f"{SB_URL}/rest/v1/{path}"
    req = urllib.request.Request(url, headers=SB_WRITE_HEADERS, method="DELETE")
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()


# ── KIS 토큰 ──────────────────────────────────────────────────────────────

def get_kis_token() -> str:
    rows = sb_get(
        "api_credentials?service_name=eq.kis&credential_type=eq.access_token"
        "&is_active=eq.true&select=credential_value,expires_at"
    )
    if not rows:
        raise RuntimeError("KIS 실전 토큰이 Supabase에 없습니다.")
    cv = rows[0]["credential_value"]
    token = cv if cv.startswith("eyJ") else json.loads(cv)["access_token"]
    expires_at = rows[0].get("expires_at", "")
    if expires_at:
        exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        remaining = (exp - datetime.now(timezone.utc)).total_seconds()
        if remaining < 300:
            raise RuntimeError(f"KIS 토큰 만료 임박 ({remaining:.0f}초 남음). 토큰 재발급 후 재실행.")
        print(f"  KIS 토큰 유효 (잔여 {remaining/3600:.1f}h)")
    return token


# ── 분봉 데이터 로드 (KIS FHKST03010200) ──────────────────────────────────

def load_minute_bars(token: str) -> list[dict]:
    """KIS inquire-time-itemchartprice로 최근 2거래일 1분봉 수집.

    API 제약:
    - FID_INPUT_HOUR_1 기반 (날짜 직접 지정 불가)
    - 1회 호출 = 최대 30건, 과거 방향 페이지 순회
    - 날짜 경계를 넘으면 전일 데이터가 섞이므로 최근 2거래일(약 780건)만 안정적으로 수집 가능

    반환: [{time: datetime(KST), open, high, low, close, source: 'minute'}, ...] 오름차순
    """
    kis_headers = {
        "authorization": f"Bearer {token}",
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_APP_SECRET,
        "tr_id": "FHKST03010200",
        "custtype": "P",
    }

    now_kst = datetime.now(KST)
    # 장 마감 기준: 오늘이 거래일이면 당일 15:30, 아니면 가장 최근 거래일 15:30
    # 간단 처리: 현재 시각이 09:00 이전이면 전 거래일 15:30부터 시작
    if now_kst.hour < 9:
        start_dt = (now_kst - timedelta(days=1)).replace(hour=15, minute=30, second=0, microsecond=0)
    else:
        start_dt = now_kst.replace(hour=15, minute=30, second=0, microsecond=0)
        if now_kst < start_dt:
            start_dt = start_dt  # 아직 장 중이면 현재 시각 기준

    # 2거래일(약 780분) 커버: cutoff = start_dt 기준일로부터 2 영업일 전 09:00
    # 단순하게 달력 기준 3일 전 09:00 (주말 포함)
    cutoff_dt = (start_dt - timedelta(days=3)).replace(hour=9, minute=0, second=0, microsecond=0)

    current_dt = start_dt
    seen: set[str] = set()
    bars: list[dict] = []
    call_count = 0
    max_calls = 60  # 2거래일 × 13회/일 ≒ 26회, 여유 2배

    while call_count < max_calls:
        hour_str = current_dt.strftime("%H%M%S")
        params = {
            "FID_ETC_CLS_CODE": "",
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": STOCK_CODE,
            "FID_INPUT_HOUR_1": hour_str,
            "FID_PW_DATA_INCU_YN": "Y",
        }
        query = urllib.parse.urlencode(params)
        url = f"{REAL_URL}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice?{query}"
        req = urllib.request.Request(url, headers=kis_headers)

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
        except Exception as e:
            print(f"  분봉 API 오류 ({hour_str}): {e}, skip")
            call_count += 1
            time.sleep(1.0)
            continue

        if result.get("rt_cd") != "0":
            print(f"  분봉 API 비정상: {result.get('msg1')}")
            break

        output2 = result.get("output2", [])
        call_count += 1

        if not output2:
            break

        reached_cutoff = False
        for b in output2:
            dt_str = b["stck_bsop_date"] + b["stck_cntg_hour"]
            bar_dt = datetime.strptime(dt_str, "%Y%m%d%H%M%S").replace(tzinfo=KST)
            key = bar_dt.isoformat()
            if key not in seen:
                seen.add(key)
                bars.append({
                    "time": bar_dt,
                    "open": int(b.get("stck_oprc", 0)),
                    "high": int(b.get("stck_hgpr", 0)),
                    "low": int(b.get("stck_lwpr", 0)),
                    "close": int(b.get("stck_prpr", 0)),
                    "source": "minute",
                })
            if bar_dt <= cutoff_dt:
                reached_cutoff = True

        if reached_cutoff:
            break

        last = output2[-1]
        last_dt = datetime.strptime(
            last["stck_bsop_date"] + last["stck_cntg_hour"], "%Y%m%d%H%M%S"
        ).replace(tzinfo=KST)
        if last_dt <= cutoff_dt:
            break
        current_dt = last_dt - timedelta(minutes=1)
        time.sleep(MINUTE_API_SLEEP)

    bars.sort(key=lambda x: x["time"])
    print(f"  분봉 API 호출: {call_count}회, 수집: {len(bars)}건")
    return bars


# ── 일봉 데이터 로드 ──────────────────────────────────────────────────────

def load_daily_bars(token: str, days: int = 100) -> list[dict]:
    """KIS FHKST03010100으로 최근 N일 일봉 조회.
    반환: [{time: datetime, open, high, low, close, source: 'daily'}, ...] 오름차순
    """
    end_date = datetime.now(KST).strftime("%Y%m%d")
    start_date = (datetime.now(KST) - timedelta(days=int(days * 1.5))).strftime("%Y%m%d")

    headers = {
        "authorization": f"Bearer {token}",
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_APP_SECRET,
        "tr_id": "FHKST03010100",
        "custtype": "P",
    }
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": STOCK_CODE,
        "FID_INPUT_DATE_1": start_date,
        "FID_INPUT_DATE_2": end_date,
        "FID_PERIOD_DIV_CODE": "D",
        "FID_ORG_ADJ_PRC": "1",
    }
    query = urllib.parse.urlencode(params)
    url = f"{REAL_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice?{query}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())

    if result.get("rt_cd") != "0":
        raise RuntimeError(f"KIS API 오류: {result.get('msg1')}")

    raw = result.get("output2", [])
    bars = []
    for b in raw:
        date_str = b.get("stck_bsop_date", "")
        if not date_str:
            continue
        dt = datetime.strptime(date_str, "%Y%m%d").replace(
            hour=15, minute=30, tzinfo=KST
        )
        bars.append({
            "time": dt,
            "open": int(b.get("stck_oprc", "0")),
            "high": int(b.get("stck_hgpr", "0")),
            "low": int(b.get("stck_lwpr", "0")),
            "close": int(b.get("stck_clpr", "0")),
            "source": "daily",
        })

    bars.sort(key=lambda x: x["time"])
    return bars


# ── 백테스트 ──────────────────────────────────────────────────────────────

def run_backtest(bars: list[dict]) -> tuple[list[dict], dict]:
    """bars: time-sorted list of {time, high, low, source, ...}
    반환: (cycles, final_state)

    같은 bar에서 low<=BUY_PRICE AND high>=SELL_PRICE 동시 조건:
    → 매수 즉시 매도로 처리 (분봉 단위 불확실성 보수적 가정)
    """
    cap = SIM_START_CAPITAL
    holding = False
    buy_dt = None
    qty = 0
    cycles = []

    for bar in bars:
        low = bar["low"]
        high = bar["high"]

        if not holding and low <= BUY_PRICE:
            qty = cap // BUY_PRICE
            invested = qty * BUY_PRICE
            if qty > 0 and invested <= cap:
                cap -= invested
                holding = True
                buy_dt = bar["time"]

        if holding and high >= SELL_PRICE:
            proceeds = qty * SELL_PRICE
            cap += proceeds
            pnl_pct = (SELL_PRICE - BUY_PRICE) / BUY_PRICE * 100
            cycles.append({
                "entry_dt": buy_dt,
                "exit_dt": bar["time"],
                "entry_price": BUY_PRICE,
                "exit_price": SELL_PRICE,
                "qty": qty,
                "pnl_pct": round(pnl_pct, 4),
                "bar_source": bar["source"],
            })
            holding = False
            qty = 0

    final_state = {
        "cap": cap,
        "still_holding": holding,
        "unrealized_qty": qty,
        "unrealized_buy_dt": buy_dt,
    }
    return cycles, final_state


# ── DB 적재 ───────────────────────────────────────────────────────────────

def get_user_id() -> str:
    rows = sb_get("strategy_simulations?select=user_id&limit=1")
    if rows:
        return rows[0].get("user_id", "")
    return ""


def clear_existing():
    """기존 celltrion_band 시뮬 + 연결 auto_trades 삭제 (idempotent)."""
    sims = sb_get(f"strategy_simulations?strategy_type=eq.{STRATEGY_TYPE}&select=id,trade_id")
    trade_ids = [s["trade_id"] for s in sims if s.get("trade_id")]
    sim_ids = [s["id"] for s in sims]

    if sim_ids:
        ids_filter = ",".join(sim_ids)
        sb_delete(f"strategy_simulations?id=in.({ids_filter})")
        print(f"  strategy_simulations 삭제: {len(sim_ids)}건")

    if trade_ids:
        ids_filter = ",".join(trade_ids)
        sb_delete(f"auto_trades?id=in.({ids_filter})")
        print(f"  auto_trades 삭제: {len(trade_ids)}건")


def insert_cycles(cycles: list[dict], user_id: str) -> int:
    """사이클마다 auto_trades + strategy_simulations 1건씩 insert.
    반환: 성공한 사이클 수
    """
    inserted = 0
    for c in cycles:
        entry_dt_utc = c["entry_dt"].astimezone(timezone.utc).isoformat()
        exit_dt_utc = c["exit_dt"].astimezone(timezone.utc).isoformat()

        trade_body = {
            "code": STOCK_CODE,
            "name": STOCK_NAME,
            "side": "buy",
            "order_price": BUY_PRICE,
            "filled_price": BUY_PRICE,
            "sell_price": SELL_PRICE,
            "quantity": c["qty"],
            "status": "sim_only",
            "pnl_pct": round(c["pnl_pct"], 2),
            "sell_reason": STRATEGY_TYPE,
            "created_at": entry_dt_utc,
            "filled_at": entry_dt_utc,
            "sold_at": exit_dt_utc,
        }
        trade_row = sb_post("auto_trades", trade_body)
        trade_id = trade_row.get("id", "")
        if not trade_id:
            print(f"  WARNING: auto_trades insert 실패 (entry {c['entry_dt'].date()})")
            continue

        sim_body = {
            "trade_id": trade_id,
            "strategy_type": STRATEGY_TYPE,
            "entry_price": BUY_PRICE,
            "exit_price": SELL_PRICE,
            "pnl_pct": round(c["pnl_pct"], 2),
            "status": "closed",
            "exit_reason": STRATEGY_TYPE,
            "peak_price": SELL_PRICE,
            "stepped_stop_pct": 0.0,
            "created_at": entry_dt_utc,
            "exited_at": exit_dt_utc,
            **({"user_id": user_id} if user_id else {}),
        }
        sb_post("strategy_simulations", sim_body)
        inserted += 1

    return inserted


# ── 보고 출력 ─────────────────────────────────────────────────────────────

def print_report(minute_bars, daily_bars, all_bars, cycles, final_state, inserted):
    print()
    print("=" * 60)
    print("셀트리온(068270) 횡보 매매 백테스트 결과")
    print("=" * 60)

    print("\n[데이터 현황]")
    if minute_bars:
        dates = sorted(set(b["time"].date() for b in minute_bars))
        print(f"  분봉 (1m): {len(minute_bars)}건 ({dates[0]} ~ {dates[-1]}, {len(dates)}거래일)")
        print(f"  ※ KIS API 제약: 과거 30일 분봉 직접 지정 불가 → 최근 2거래일만 수집")
    else:
        print("  분봉: 없음 (API 실패)")
    print(f"  일봉: {len(daily_bars)}건 "
          f"({daily_bars[0]['time'].date()} ~ {daily_bars[-1]['time'].date()})" if daily_bars else "  일봉: 없음")
    print(f"  백테스트 사용 bars: {len(all_bars)}건")

    print("\n[백테스트 결과]")
    print(f"  사이클 수: {len(cycles)}회")

    if cycles:
        hold_secs = [(c["exit_dt"] - c["entry_dt"]).total_seconds() for c in cycles]
        avg_hold_days = sum(hold_secs) / len(hold_secs) / 86400
        avg_hold_min = sum(hold_secs) / len(hold_secs) / 60
        print(f"  평균 보유기간: {avg_hold_days:.2f}일 ({avg_hold_min:.0f}분)")

        unrealized_val = final_state["unrealized_qty"] * BUY_PRICE if final_state["still_holding"] else 0
        total_val = final_state["cap"] + unrealized_val
        total_return = (total_val - SIM_START_CAPITAL) / SIM_START_CAPITAL * 100
        print(f"  시작 자본: {SIM_START_CAPITAL:,}원")
        print(f"  현금 잔고: {final_state['cap']:,}원")
        if final_state["still_holding"]:
            print(f"  미청산 평가(매수가): {unrealized_val:,}원 ({final_state['unrealized_qty']}주)")
        print(f"  총 평가자산: {total_val:,}원")
        print(f"  누적 수익률: {total_return:.2f}%")

        print("\n  [사이클 상세]")
        for i, c in enumerate(cycles, 1):
            hold = (c["exit_dt"] - c["entry_dt"]).total_seconds()
            hold_str = f"{hold/60:.0f}분" if hold < 86400 else f"{hold/86400:.1f}일"
            # 분봉이면 HH:MM 표시, 일봉이면 날짜만
            entry_str = c["entry_dt"].strftime("%Y-%m-%d %H:%M") if c["bar_source"] == "minute" else c["entry_dt"].strftime("%Y-%m-%d")
            exit_str = c["exit_dt"].strftime("%Y-%m-%d %H:%M") if c["bar_source"] == "minute" else c["exit_dt"].strftime("%Y-%m-%d")
            print(f"    {i:2d}. 매수 {entry_str} → 매도 {exit_str} "
                  f"({hold_str}) qty={c['qty']:,} [{c['bar_source']}]")
    else:
        print("  사이클 없음 (매매 조건 미충족)")

    print(f"\n[DB 적재]")
    print(f"  auto_trades + strategy_simulations 각 {inserted}건 insert")
    print()


# ── 메인 ──────────────────────────────────────────────────────────────────

def main():
    print("셀트리온(068270) 횡보 매매 백테스트 시작 (분봉+일봉 혼합)")
    print(f"  매수: <= {BUY_PRICE:,}원 / 매도: >= {SELL_PRICE:,}원")
    print(f"  시작 자본: {SIM_START_CAPITAL:,}원")

    # 1. 토큰
    print("\n[1] KIS 토큰 확보")
    token = get_kis_token()

    # 2. 분봉 (KIS API)
    print("\n[2] 분봉 데이터 로드 (KIS FHKST03010200 — 최근 2거래일)")
    minute_bars = load_minute_bars(token)
    if minute_bars:
        minute_cutoff_date = minute_bars[0]["time"].date()
        print(f"  분봉 {len(minute_bars)}건 "
              f"({minute_bars[0]['time'].strftime('%Y-%m-%d %H:%M')} ~ "
              f"{minute_bars[-1]['time'].strftime('%Y-%m-%d %H:%M')})")
    else:
        minute_cutoff_date = None
        print("  분봉 수집 실패 → 일봉만 사용")

    # 3. 일봉
    print("\n[3] 일봉 데이터 로드 (KIS FHKST03010100)")
    daily_bars = load_daily_bars(token, days=100)
    print(f"  {len(daily_bars)}건 "
          f"({daily_bars[0]['time'].date()} ~ {daily_bars[-1]['time'].date()})" if daily_bars else "  없음")

    # 4. 결합 — 분봉 커버 날짜 이전만 일봉 사용
    if minute_cutoff_date:
        daily_filtered = [b for b in daily_bars if b["time"].date() < minute_cutoff_date]
    else:
        daily_filtered = daily_bars

    all_bars = daily_filtered + minute_bars
    all_bars.sort(key=lambda x: x["time"])
    print(f"\n[4] 결합 bars: 일봉 {len(daily_filtered)}건 + 분봉 {len(minute_bars)}건 = {len(all_bars)}건")

    # 5. 백테스트
    print("\n[5] 백테스트 실행")
    cycles, final_state = run_backtest(all_bars)
    print(f"  사이클 {len(cycles)}회 완료")

    # 6. DB 적재
    print("\n[6] DB 적재")
    print("  기존 데이터 삭제 중...")
    clear_existing()

    user_id = get_user_id()
    if not user_id:
        print("  WARNING: user_id 미확인 → strategy_simulations에 user_id 없이 insert")

    inserted = 0
    if cycles:
        inserted = insert_cycles(cycles, user_id)
        print(f"  insert 완료: {inserted}건")
    else:
        print("  insert 없음 (사이클 0건)")

    # 7. 보고
    print_report(minute_bars, daily_bars, all_bars, cycles, final_state, inserted)


if __name__ == "__main__":
    main()
