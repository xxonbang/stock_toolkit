"""셀트리온(068270) 횡보 매매 가상 시뮬 백테스트

매매 룰:
- 매수: 저가 <= 199,000원 (지정가 가정)
- 매도: 고가 >= 205,000원 (지정가 가정)
- 무한 사이클, 무손절, 1000만원 자본 시작

데이터:
- 분봉: intraday-history.json (068270 없으면 일봉만 사용)
- 일봉: KIS FHKST03010100 (최대 100일 일봉)

DB 적재:
- auto_trades: sim_only 상태로 각 사이클 1건
- strategy_simulations: strategy_type=celltrion_band, 각 사이클 1건
"""
import os
import sys
import json
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
INTRADAY_URL = "https://xxonbang.github.io/theme-analyzer/data/intraday-history.json"

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


# ── 분봉 데이터 로드 ──────────────────────────────────────────────────────

def load_intraday_bars() -> list[dict]:
    """intraday-history.json에서 068270 30분봉 추출.
    반환: [{time: datetime, open, high, low, close, source: 'intraday'}, ...]
    없으면 빈 리스트.
    """
    # 로컬 캐시 우선
    local = Path(__file__).parent.parent / "results" / "intraday-history.json"
    try:
        if local.exists():
            with open(local, encoding="utf-8") as f:
                data = json.load(f)
        else:
            print("  로컬 intraday-history.json 없음, 원격 다운로드 시도...")
            req = urllib.request.Request(INTRADAY_URL)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
    except Exception as e:
        print(f"  intraday 로드 실패: {e}")
        return []

    stocks = data.get("stocks", {})
    if STOCK_CODE not in stocks:
        return []

    raw_days = stocks[STOCK_CODE]  # list of day objects
    bars = []
    for day_obj in raw_days:
        date_str = day_obj.get("date", "")  # "YYYY-MM-DD"
        for interval in day_obj.get("intervals_30m", []):
            time_str = interval.get("time", "")  # "HH:MM"
            if not date_str or not time_str:
                continue
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=KST)
            bars.append({
                "time": dt,
                "open": day_obj.get("open", interval.get("close", 0)),
                "high": interval["high"],
                "low": interval["low"],
                "close": interval["close"],
                "source": "intraday",
            })
    bars.sort(key=lambda x: x["time"])
    return bars


# ── 일봉 데이터 로드 ──────────────────────────────────────────────────────

def load_daily_bars(token: str, days: int = 100) -> list[dict]:
    """KIS FHKST03010100으로 최근 N일 일봉 조회.
    반환: [{time: datetime, open, high, low, close, source: 'daily'}, ...] 오름차순
    """
    end_date = datetime.now(KST).strftime("%Y%m%d")
    # 영업일 days개 확보를 위해 calendar days = days * 1.5
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
            hour=15, minute=30, tzinfo=KST  # 일봉은 종가 시점(15:30) 대표
        )
        bars.append({
            "time": dt,
            "open": int(b.get("stck_oprc", "0")),
            "high": int(b.get("stck_hgpr", "0")),
            "low": int(b.get("stck_lwpr", "0")),
            "close": int(b.get("stck_clpr", "0")),
            "source": "daily",
        })

    # API는 최신 → 과거 순으로 반환 → 오름차순 정렬
    bars.sort(key=lambda x: x["time"])
    return bars


# ── 백테스트 ──────────────────────────────────────────────────────────────

def run_backtest(bars: list[dict]) -> tuple[list[dict], dict]:
    """bars: time-sorted list of {time, high, low, ...}
    반환: (cycles, final_state)
    """
    cap = SIM_START_CAPITAL
    holding = False
    buy_dt = None
    qty = 0
    cycles = []

    for bar in bars:
        low = bar["low"]
        high = bar["high"]

        if not holding:
            if low <= BUY_PRICE:
                qty = cap // BUY_PRICE
                invested = qty * BUY_PRICE
                if qty > 0 and invested <= cap:
                    cap -= invested
                    holding = True
                    buy_dt = bar["time"]

        if holding:
            if high >= SELL_PRICE:
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
    """기존 strategy_simulations에서 user_id 추출."""
    rows = sb_get("strategy_simulations?select=user_id&limit=1")
    if rows:
        return rows[0].get("user_id", "")
    return ""


def clear_existing():
    """기존 celltrion_band 시뮬 + 연결 auto_trades 삭제 (idempotent)."""
    # strategy_simulations에서 trade_id 목록 수집
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

        # 1. auto_trades insert
        trade_body = {
            "code": STOCK_CODE,
            "name": STOCK_NAME,
            "side": "buy",
            "order_price": BUY_PRICE,
            "filled_price": BUY_PRICE,
            "sell_price": SELL_PRICE,
            "quantity": c["qty"],
            "status": "sold",
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

        # 2. strategy_simulations insert
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

def print_report(intraday_bars, daily_bars, all_bars, cycles, final_state, inserted):
    print()
    print("=" * 60)
    print("셀트리온(068270) 횡보 매매 백테스트 결과")
    print("=" * 60)

    # 데이터 현황
    print("\n[데이터 현황]")
    if intraday_bars:
        print(f"  분봉 (30m): {len(intraday_bars)}건 "
              f"({intraday_bars[0]['time'].date()} ~ {intraday_bars[-1]['time'].date()})")
    else:
        print(f"  분봉: 없음 (intraday-history.json에 {STOCK_CODE} 미포함)")
    print(f"  일봉: {len(daily_bars)}건 "
          f"({daily_bars[0]['time'].date()} ~ {daily_bars[-1]['time'].date()})" if daily_bars else "  일봉: 없음")
    print(f"  백테스트 사용 bars: {len(all_bars)}건")

    # 백테스트 결과
    print("\n[백테스트 결과]")
    print(f"  사이클 수: {len(cycles)}회")

    if cycles:
        hold_days = []
        for c in cycles:
            delta = c["exit_dt"] - c["entry_dt"]
            hold_days.append(delta.total_seconds() / 86400)
        avg_hold = sum(hold_days) / len(hold_days)
        print(f"  평균 보유기간: {avg_hold:.1f}일")

        pnl_per_cycle = round((SELL_PRICE - BUY_PRICE) / BUY_PRICE * 100, 4)
        # 미청산 포지션을 BUY_PRICE로 평가 (보수적 기준)
        unrealized_val = final_state["unrealized_qty"] * BUY_PRICE if final_state["still_holding"] else 0
        total_val = final_state["cap"] + unrealized_val
        total_return = (total_val - SIM_START_CAPITAL) / SIM_START_CAPITAL * 100
        realized_return = (final_state["cap"] - SIM_START_CAPITAL + sum(
            c["qty"] * (SELL_PRICE - BUY_PRICE) for c in cycles
        )) / SIM_START_CAPITAL * 100
        print(f"  사이클당 수익률: {pnl_per_cycle:.2f}%")
        print(f"  시작 자본: {SIM_START_CAPITAL:,}원")
        print(f"  현금 잔고: {final_state['cap']:,}원")
        print(f"  미청산 포지션 평가(매수가 기준): {unrealized_val:,}원")
        print(f"  총 평가자산: {total_val:,}원")
        print(f"  누적 수익률 (총 평가자산 기준): {total_return:.2f}%")

        if final_state["still_holding"]:
            print(f"  미청산 포지션: {final_state['unrealized_qty']}주 (매수일: {final_state['unrealized_buy_dt'].date()})")

        print("\n  [일자별 사이클]")
        for i, c in enumerate(cycles, 1):
            hold = (c["exit_dt"] - c["entry_dt"]).total_seconds() / 86400
            print(f"    {i:2d}. 매수 {c['entry_dt'].strftime('%Y-%m-%d')} "
                  f"→ 매도 {c['exit_dt'].strftime('%Y-%m-%d')} "
                  f"({hold:.0f}일) qty={c['qty']:,} pnl={c['pnl_pct']:.2f}% [{c['bar_source']}]")
    else:
        print("  사이클 없음 (매매 조건 미충족)")

    # DB 적재
    print(f"\n[DB 적재]")
    print(f"  auto_trades + strategy_simulations 각 {inserted}건 insert")

    print()


# ── 메인 ──────────────────────────────────────────────────────────────────

def main():
    print("셀트리온(068270) 횡보 매매 백테스트 시작")
    print(f"  매수: <= {BUY_PRICE:,}원 / 매도: >= {SELL_PRICE:,}원")
    print(f"  시작 자본: {SIM_START_CAPITAL:,}원")

    # 1. 토큰
    print("\n[1] KIS 토큰 확보")
    token = get_kis_token()

    # 2. 분봉
    print("\n[2] 분봉 데이터 로드 (intraday-history.json)")
    intraday_bars = load_intraday_bars()
    if intraday_bars:
        print(f"  {STOCK_CODE} {len(intraday_bars)}건 ({intraday_bars[0]['time'].date()} ~ {intraday_bars[-1]['time'].date()})")
        intraday_cutoff = intraday_bars[0]["time"].date()
    else:
        print(f"  {STOCK_CODE} 분봉 없음 → 일봉만 사용")
        intraday_cutoff = None

    # 3. 일봉
    print("\n[3] 일봉 데이터 로드 (KIS FHKST03010100)")
    daily_bars = load_daily_bars(token, days=100)
    print(f"  {len(daily_bars)}건 ({daily_bars[0]['time'].date()} ~ {daily_bars[-1]['time'].date()})" if daily_bars else "  없음")

    # 4. 결합 — 분봉 시작일 이전 일봉만 사용
    if intraday_cutoff:
        daily_filtered = [b for b in daily_bars if b["time"].date() < intraday_cutoff]
    else:
        daily_filtered = daily_bars

    all_bars = daily_filtered + intraday_bars
    all_bars.sort(key=lambda x: x["time"])
    print(f"\n[4] 결합 bars: 일봉 {len(daily_filtered)}건 + 분봉 {len(intraday_bars)}건 = {len(all_bars)}건")

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
    print_report(intraday_bars, daily_bars, all_bars, cycles, final_state, inserted)


if __name__ == "__main__":
    main()
