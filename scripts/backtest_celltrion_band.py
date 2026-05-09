"""셀트리온(068270) 횡보 매매 가상 시뮬 백테스트

매매 룰:
- 매수: 저가 <= 199,000원 (지정가 가정)
- 매도: 고가 >= 205,000원 (지정가 가정)
- 무한 사이클, 무손절, 1000만원 자본 시작
- 같은 일봉에서 low<=199k AND high>=205k 동시 → 매수+매도 동시 처리

데이터:
- 일봉만 사용: KIS FHKST03010100 최근 100일

DB 적재:
- closed 사이클: auto_trades(sim_only) + strategy_simulations(closed)
- 미청산 보유: auto_trades(sim_only, sell_price=NULL) + strategy_simulations(open)
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


# ── 일봉 데이터 로드 ──────────────────────────────────────────────────────

def load_daily_bars(token: str, days: int = 100) -> list[dict]:
    """KIS FHKST03010100으로 최근 N일 일봉 조회.
    반환: [{time: datetime(KST 15:30), open, high, low, close}, ...] 오름차순
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
        })

    bars.sort(key=lambda x: x["time"])
    return bars


# ── 백테스트 ──────────────────────────────────────────────────────────────

def run_backtest(bars: list[dict]) -> tuple[list[dict], dict]:
    """bars: time-sorted list of {time, high, low, ...}
    반환: (cycles, final_state)

    같은 일봉에서 low<=BUY_PRICE AND high>=SELL_PRICE 동시 조건:
    → 매수 즉시 매도로 처리
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
    """closed 사이클마다 auto_trades + strategy_simulations 1건씩 insert.
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


def insert_open_holding(buy_dt: datetime, qty: int, user_id: str) -> bool:
    """미청산 보유 1건 — auto_trades(open) + strategy_simulations(open) insert.
    entry 일자 15:30 KST 기준, sell_price/exit_price/pnl_pct=NULL.
    반환: 성공 여부
    """
    # entry_dt는 이미 15:30 KST (일봉 time 기준)
    entry_dt_utc = buy_dt.astimezone(timezone.utc).isoformat()

    trade_body = {
        "code": STOCK_CODE,
        "name": STOCK_NAME,
        "side": "buy",
        "order_price": BUY_PRICE,
        "filled_price": BUY_PRICE,
        "sell_price": None,
        "quantity": qty,
        "status": "sim_only",
        "pnl_pct": None,
        "sell_reason": STRATEGY_TYPE,
        "created_at": entry_dt_utc,
        "filled_at": entry_dt_utc,
        "sold_at": None,
    }
    trade_row = sb_post("auto_trades", trade_body)
    trade_id = trade_row.get("id", "")
    if not trade_id:
        print("  WARNING: 미청산 auto_trades insert 실패")
        return False

    sim_body = {
        "trade_id": trade_id,
        "strategy_type": STRATEGY_TYPE,
        "entry_price": BUY_PRICE,
        "exit_price": None,
        "pnl_pct": None,
        "status": "open",
        "exit_reason": None,
        "peak_price": BUY_PRICE,
        "stepped_stop_pct": 0.0,
        "created_at": entry_dt_utc,
        "exited_at": None,
        **({"user_id": user_id} if user_id else {}),
    }
    sb_post("strategy_simulations", sim_body)
    return True


# ── 보고 출력 ─────────────────────────────────────────────────────────────

def print_report(daily_bars, cycles, final_state, inserted_closed, inserted_open):
    print()
    print("=" * 60)
    print("셀트리온(068270) 횡보 매매 백테스트 결과 (일봉 100일)")
    print("=" * 60)

    print("\n[데이터 현황]")
    if daily_bars:
        print(f"  일봉: {len(daily_bars)}건 "
              f"({daily_bars[0]['time'].date()} ~ {daily_bars[-1]['time'].date()})")
    else:
        print("  일봉: 없음")

    print("\n[백테스트 결과]")
    print(f"  사이클 수: {len(cycles)}회 (closed) + {'1' if final_state['still_holding'] else '0'}회 (open)")

    if cycles or final_state["still_holding"]:
        unrealized_val = final_state["unrealized_qty"] * BUY_PRICE if final_state["still_holding"] else 0
        total_val = final_state["cap"] + unrealized_val
        total_return = (total_val - SIM_START_CAPITAL) / SIM_START_CAPITAL * 100
        print(f"  시작 자본: {SIM_START_CAPITAL:,}원")
        print(f"  현금 잔고: {final_state['cap']:,}원")
        if final_state["still_holding"]:
            print(f"  미청산 평가(매수가): {unrealized_val:,}원 ({final_state['unrealized_qty']}주)")
        print(f"  총 평가자산: {total_val:,}원")
        print(f"  누적 수익률: {total_return:.2f}%")

        if cycles:
            hold_secs = [(c["exit_dt"] - c["entry_dt"]).total_seconds() for c in cycles]
            avg_hold_days = sum(hold_secs) / len(hold_secs) / 86400
            print(f"  평균 보유기간: {avg_hold_days:.2f}일")

        print("\n  [사이클 상세]")
        for i, c in enumerate(cycles, 1):
            hold_days = (c["exit_dt"] - c["entry_dt"]).total_seconds() / 86400
            print(f"    {i:2d}. 매수 {c['entry_dt'].strftime('%Y-%m-%d')} → "
                  f"매도 {c['exit_dt'].strftime('%Y-%m-%d')} "
                  f"({hold_days:.1f}일) qty={c['qty']:,}")
        if final_state["still_holding"]:
            print(f"  미청산: {final_state['unrealized_buy_dt'].strftime('%Y-%m-%d')} 매수 "
                  f"{final_state['unrealized_qty']}주 (보유 중)")
    else:
        print("  사이클 없음 (매매 조건 미충족)")

    print(f"\n[DB 적재]")
    print(f"  closed: auto_trades + strategy_simulations 각 {inserted_closed}건")
    print(f"  open:   auto_trades + strategy_simulations 각 {inserted_open}건")
    print()

    # 검증 표
    print("[검증]")
    qty_seq = [str(c["qty"]) for c in cycles]
    if final_state["still_holding"]:
        qty_seq.append(f"{final_state['unrealized_qty']}(보유)")
    print(f"  qty 시퀀스: {' → '.join(qty_seq)}")
    print(f"  종료 cap: {final_state['cap']:,}원")


# ── 메인 ──────────────────────────────────────────────────────────────────

def main():
    print("셀트리온(068270) 횡보 매매 백테스트 시작 (일봉 100일)")
    print(f"  매수: <= {BUY_PRICE:,}원 / 매도: >= {SELL_PRICE:,}원")
    print(f"  시작 자본: {SIM_START_CAPITAL:,}원")

    # 1. 토큰
    print("\n[1] KIS 토큰 확보")
    token = get_kis_token()

    # 2. 일봉
    print("\n[2] 일봉 데이터 로드 (KIS FHKST03010100 — 100일)")
    daily_bars = load_daily_bars(token, days=100)
    if not daily_bars:
        print("  일봉 데이터 없음 — 종료")
        return
    print(f"  {len(daily_bars)}건 "
          f"({daily_bars[0]['time'].date()} ~ {daily_bars[-1]['time'].date()})")

    # 3. 백테스트
    print("\n[3] 백테스트 실행")
    cycles, final_state = run_backtest(daily_bars)
    print(f"  closed 사이클: {len(cycles)}회")
    if final_state["still_holding"]:
        print(f"  미청산 보유: {final_state['unrealized_qty']}주 "
              f"(매수일 {final_state['unrealized_buy_dt'].strftime('%Y-%m-%d')})")

    # 4. DB 적재
    print("\n[4] DB 적재")
    print("  기존 데이터 삭제 중...")
    clear_existing()

    user_id = get_user_id()
    if not user_id:
        print("  WARNING: user_id 미확인 → strategy_simulations에 user_id 없이 insert")

    inserted_closed = insert_cycles(cycles, user_id)
    print(f"  closed insert: {inserted_closed}건")

    inserted_open = 0
    if final_state["still_holding"]:
        ok = insert_open_holding(
            final_state["unrealized_buy_dt"],
            final_state["unrealized_qty"],
            user_id,
        )
        inserted_open = 1 if ok else 0
        print(f"  open insert: {inserted_open}건")

    # 5. 보고
    print_report(daily_bars, cycles, final_state, inserted_closed, inserted_open)


if __name__ == "__main__":
    main()
