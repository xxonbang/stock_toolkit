# 모의투자 자동매매 시스템 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GCP e2-micro 데몬에 모의투자 자동매매 기능 추가 — 고확신 종목 자동 매수, +2% 익절 / -3% 손절 자동 매도

**Architecture:** 기존 WebSocket 데몬에 3개 모듈 추가: (1) GitHub API로 theme-analysis 워크플로우 완료 감지 → (2) cross_signal.json에서 고확신 종목 추출 + Supabase로 중복 체크 후 KIS 모의투자 API 매수 → (3) WebSocket 체결가로 보유 종목 수익률 실시간 감시, ±조건 시 자동 매도

**Tech Stack:** KIS 모의투자 REST API (VTTC0802U/VTTC0801U), Supabase (포지션 DB), GitHub REST API, asyncio

---

## 파일 구조 (신규 3개 + 수정 3개)

```
daemon/
├── trader.py            # [신규] KIS 모의투자 매수/매도 주문 + 수익률 감시
├── github_monitor.py    # [신규] GitHub 워크플로우 완료 감지
├── position_db.py       # [신규] Supabase 포지션 CRUD
├── config.py            # [수정] 매매 설정 + GitHub/Supabase 환경변수 추가
├── main.py              # [수정] 자동매매 컴포넌트 통합
├── notifier.py          # [수정] 매매 알림 포맷 추가
└── tests/
    ├── test_trader.py        # [신규]
    ├── test_github_monitor.py # [신규]
    └── test_position_db.py   # [신규]
```

---

### Task 1: config.py 매매 설정 추가

**Files:**
- Modify: `daemon/config.py`
- Modify: `daemon/.env.example`

- [ ] **Step 1: .env.example에 신규 환경변수 추가**

daemon/.env.example에 추가:
```
# GitHub API (워크플로우 감시용)
GITHUB_TOKEN=
GITHUB_REPO=xxonbang/theme_analysis
GITHUB_WORKFLOW=daily-theme-analysis.yml

# Supabase (포지션 DB)
SUPABASE_URL=
SUPABASE_SECRET_KEY=

# KIS 모의투자 계좌
KIS_MOCK_ACCOUNT_NO=
```

- [ ] **Step 2: config.py에 매매 설정 추가**

```python
# 자동매매 설정
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "xxonbang/theme_analysis")
GITHUB_WORKFLOW = os.getenv("GITHUB_WORKFLOW", "daily-theme-analysis.yml")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "")

KIS_MOCK_ACCOUNT_NO = os.getenv("KIS_MOCK_ACCOUNT_NO", "")
KIS_MOCK_BASE_URL = "https://openapivts.koreainvestment.com:29443"

TRADE_AMOUNT_PER_STOCK = 10_000_000  # 종목당 투자금액 (원)
TRADE_TAKE_PROFIT_PCT = 2.0          # 익절 기준 (%)
TRADE_STOP_LOSS_PCT = -3.0           # 손절 기준 (%)
```

- [ ] **Step 3: 커밋**

---

### Task 2: position_db.py — Supabase 포지션 관리

**Files:**
- Create: `daemon/position_db.py`
- Create: `daemon/tests/test_position_db.py`

Supabase 테이블 `auto_trades`:
```sql
create table auto_trades (
  id uuid default gen_random_uuid() primary key,
  code text not null,
  name text not null,
  side text not null,           -- 'buy' or 'sell'
  order_price int not null,     -- 주문 가격
  filled_price int,             -- 체결 가격
  quantity int not null,         -- 수량
  status text not null,          -- 'pending', 'filled', 'sold', 'cancelled'
  pnl_pct float,                -- 수익률 (매도 시)
  sell_reason text,             -- 'take_profit', 'stop_loss'
  created_at timestamptz default now(),
  filled_at timestamptz,
  sold_at timestamptz
);
```

- [ ] **Step 1: 테스트 작성**

```python
# daemon/tests/test_position_db.py
import pytest
from daemon.position_db import (
    is_already_held_or_ordered,
    calc_quantity,
    calc_pnl_pct,
)


def test_calc_quantity():
    # 1000만원 / 68500원 = 145주 (내림)
    assert calc_quantity(10_000_000, 68500) == 145


def test_calc_quantity_zero_price():
    assert calc_quantity(10_000_000, 0) == 0


def test_calc_pnl_pct():
    # (70000 - 68500) / 68500 * 100 = 2.19%
    result = calc_pnl_pct(68500, 70000)
    assert round(result, 2) == 2.19


def test_calc_pnl_pct_loss():
    result = calc_pnl_pct(68500, 66000)
    assert result < 0
```

- [ ] **Step 2: position_db.py 구현**

```python
"""포지션 DB — Supabase CRUD"""
import logging
import aiohttp
from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY

logger = logging.getLogger("daemon.position")


def calc_quantity(amount: int, price: int) -> int:
    if price <= 0:
        return 0
    return amount // price


def calc_pnl_pct(buy_price: int, current_price: int) -> float:
    if buy_price <= 0:
        return 0.0
    return (current_price - buy_price) / buy_price * 100


def _headers() -> dict:
    return {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


async def get_active_positions() -> list[dict]:
    """보유중(filled) + 주문중(pending) 포지션 조회"""
    url = f"{SUPABASE_URL}/rest/v1/auto_trades"
    params = "status=in.(pending,filled)&select=*"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{url}?{params}", headers=_headers(), timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        logger.error(f"포지션 조회 실패: {e}")
    return []


async def is_already_held_or_ordered(code: str) -> bool:
    """해당 종목이 보유중/주문중인지 확인"""
    positions = await get_active_positions()
    return any(p["code"] == code for p in positions)


async def insert_buy_order(code: str, name: str, price: int, quantity: int) -> dict | None:
    """매수 주문 기록"""
    url = f"{SUPABASE_URL}/rest/v1/auto_trades"
    body = {
        "code": code,
        "name": name,
        "side": "buy",
        "order_price": price,
        "quantity": quantity,
        "status": "pending",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=_headers(), timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 201:
                    data = await resp.json()
                    return data[0] if data else None
                else:
                    text = await resp.text()
                    logger.error(f"매수 주문 기록 실패 ({resp.status}): {text}")
    except Exception as e:
        logger.error(f"매수 주문 기록 오류: {e}")
    return None


async def update_position_filled(position_id: str, filled_price: int):
    """체결 완료 업데이트"""
    url = f"{SUPABASE_URL}/rest/v1/auto_trades?id=eq.{position_id}"
    body = {
        "status": "filled",
        "filled_price": filled_price,
        "filled_at": "now()",
    }
    try:
        async with aiohttp.ClientSession() as session:
            await session.patch(url, json=body, headers=_headers(), timeout=aiohttp.ClientTimeout(total=10))
    except Exception as e:
        logger.error(f"체결 업데이트 실패: {e}")


async def update_position_sold(position_id: str, sell_price: int, pnl_pct: float, reason: str):
    """매도 완료 업데이트"""
    url = f"{SUPABASE_URL}/rest/v1/auto_trades?id=eq.{position_id}"
    body = {
        "status": "sold",
        "pnl_pct": round(pnl_pct, 2),
        "sell_reason": reason,
        "sold_at": "now()",
    }
    try:
        async with aiohttp.ClientSession() as session:
            await session.patch(url, json=body, headers=_headers(), timeout=aiohttp.ClientTimeout(total=10))
    except Exception as e:
        logger.error(f"매도 업데이트 실패: {e}")
```

- [ ] **Step 3: 테스트 실행 확인**
- [ ] **Step 4: 커밋**

---

### Task 3: github_monitor.py — 워크플로우 완료 감지

**Files:**
- Create: `daemon/github_monitor.py`
- Create: `daemon/tests/test_github_monitor.py`

- [ ] **Step 1: 테스트 작성**

```python
# daemon/tests/test_github_monitor.py
import pytest
from daemon.github_monitor import parse_workflow_runs, is_new_completion


def test_parse_workflow_runs_success():
    data = {
        "workflow_runs": [
            {"id": 123, "status": "completed", "conclusion": "success", "updated_at": "2026-03-21T09:10:00Z"},
            {"id": 122, "status": "completed", "conclusion": "success", "updated_at": "2026-03-21T07:30:00Z"},
        ]
    }
    runs = parse_workflow_runs(data)
    assert len(runs) == 2
    assert runs[0]["id"] == 123


def test_parse_workflow_runs_empty():
    assert parse_workflow_runs({}) == []
    assert parse_workflow_runs(None) == []


def test_is_new_completion():
    assert is_new_completion("2026-03-21T09:10:00Z", "2026-03-21T07:30:00Z") is True
    assert is_new_completion("2026-03-21T09:10:00Z", "2026-03-21T09:10:00Z") is False
    assert is_new_completion("2026-03-21T09:10:00Z", None) is True
```

- [ ] **Step 2: github_monitor.py 구현**

```python
"""GitHub 워크플로우 완료 감지"""
import logging
import aiohttp
from daemon.config import GITHUB_TOKEN, GITHUB_REPO, GITHUB_WORKFLOW

logger = logging.getLogger("daemon.github")


def parse_workflow_runs(data: dict | None) -> list[dict]:
    if not data:
        return []
    runs = data.get("workflow_runs", [])
    return [
        {
            "id": r["id"],
            "status": r["status"],
            "conclusion": r.get("conclusion"),
            "updated_at": r["updated_at"],
        }
        for r in runs
        if r.get("status") == "completed" and r.get("conclusion") == "success"
    ]


def is_new_completion(latest_time: str, last_seen_time: str | None) -> bool:
    if last_seen_time is None:
        return True
    return latest_time > last_seen_time


async def check_workflow_completion(last_seen_time: str | None) -> tuple[bool, str | None]:
    """워크플로우 완료 여부 확인. (새 완료 여부, 최신 완료 시각) 반환."""
    if not GITHUB_TOKEN:
        return False, last_seen_time

    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW}/runs"
    params = {"status": "completed", "per_page": 1}
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    runs = parse_workflow_runs(data)
                    if runs:
                        latest_time = runs[0]["updated_at"]
                        if is_new_completion(latest_time, last_seen_time):
                            logger.info(f"워크플로우 완료 감지: {latest_time}")
                            return True, latest_time
                        return False, last_seen_time
                else:
                    logger.warning(f"GitHub API 오류 ({resp.status})")
    except Exception as e:
        logger.error(f"GitHub API 호출 실패: {e}")
    return False, last_seen_time
```

- [ ] **Step 3: 테스트 실행 확인**
- [ ] **Step 4: 커밋**

---

### Task 4: trader.py — KIS 모의투자 매수/매도 + 수익률 감시

**Files:**
- Create: `daemon/trader.py`
- Create: `daemon/tests/test_trader.py`

- [ ] **Step 1: 테스트 작성**

```python
# daemon/tests/test_trader.py
import pytest
from daemon.trader import filter_high_confidence, should_sell


def test_filter_high_confidence():
    signals = [
        {"code": "005930", "name": "삼성전자", "vision_signal": "매수", "api_signal": "매수", "theme": "반도체", "theme_rank": 1},
        {"code": "000660", "name": "SK하이닉스", "vision_signal": "매수", "api_signal": "중립", "theme": "반도체", "theme_rank": 2},
        {"code": "047040", "name": "대우건설", "vision_signal": "적극매수", "api_signal": "매수", "theme": "건설", "theme_rank": 1},
    ]
    result = filter_high_confidence(signals)
    codes = [r["code"] for r in result]
    assert "005930" in codes    # 양쪽 매수 → 포함
    assert "000660" not in codes # api 중립 → 제외
    assert "047040" in codes    # 양쪽 매수 이상 → 포함


def test_filter_high_confidence_empty():
    assert filter_high_confidence([]) == []
    assert filter_high_confidence(None) == []


def test_should_sell_take_profit():
    reason = should_sell(buy_price=68500, current_price=69870, take_profit=2.0, stop_loss=-3.0)
    assert reason == "take_profit"  # +2.0%


def test_should_sell_stop_loss():
    reason = should_sell(buy_price=68500, current_price=66445, take_profit=2.0, stop_loss=-3.0)
    assert reason == "stop_loss"  # -3.0%


def test_should_sell_hold():
    reason = should_sell(buy_price=68500, current_price=69000, take_profit=2.0, stop_loss=-3.0)
    assert reason is None  # +0.73% → 홀드
```

- [ ] **Step 2: trader.py 구현**

```python
"""KIS 모의투자 자동매매 — 매수/매도 주문 + 수익률 감시"""
import logging
import aiohttp
from daemon.config import (
    KIS_APP_KEY, KIS_APP_SECRET, KIS_MOCK_ACCOUNT_NO, KIS_MOCK_BASE_URL,
    TRADE_AMOUNT_PER_STOCK, TRADE_TAKE_PROFIT_PCT, TRADE_STOP_LOSS_PCT,
    DATA_BASE_URL,
)
from daemon.position_db import (
    is_already_held_or_ordered, insert_buy_order, update_position_filled,
    update_position_sold, get_active_positions, calc_quantity, calc_pnl_pct,
)
from daemon.notifier import format_alert, send_telegram
from daemon.stock_manager import fetch_json, get_stock_name

logger = logging.getLogger("daemon.trader")

BUY_SIGNALS = {"적극매수", "매수"}

# 토큰 캐시
_access_token = ""


async def _ensure_mock_token() -> str | None:
    """모의투자 토큰 발급"""
    global _access_token
    if _access_token:
        return _access_token
    url = f"{KIS_MOCK_BASE_URL}/oauth2/tokenP"
    body = {
        "grant_type": "client_credentials",
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_APP_SECRET,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    _access_token = data.get("access_token", "")
                    return _access_token
    except Exception as e:
        logger.error(f"모의투자 토큰 발급 실패: {e}")
    return None


def _order_headers(token: str, tr_id: str) -> dict:
    return {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_APP_SECRET,
        "tr_id": tr_id,
        "custtype": "P",
    }


def filter_high_confidence(signals: list | None) -> list[dict]:
    """고확신 종목 필터: 대장주 AND vision 매수 AND api 매수"""
    if not signals:
        return []
    return [
        s for s in signals
        if s.get("vision_signal") in BUY_SIGNALS
        and s.get("api_signal") in BUY_SIGNALS
    ]


def should_sell(buy_price: int, current_price: int, take_profit: float = TRADE_TAKE_PROFIT_PCT, stop_loss: float = TRADE_STOP_LOSS_PCT) -> str | None:
    """매도 판정: 'take_profit', 'stop_loss', 또는 None(홀드)"""
    pnl = calc_pnl_pct(buy_price, current_price)
    if pnl >= take_profit:
        return "take_profit"
    if pnl <= stop_loss:
        return "stop_loss"
    return None


async def place_buy_order(code: str, name: str, price: int) -> bool:
    """KIS 모의투자 지정가 매수 주문"""
    token = await _ensure_mock_token()
    if not token:
        return False

    quantity = calc_quantity(TRADE_AMOUNT_PER_STOCK, price)
    if quantity <= 0:
        logger.warning(f"매수 수량 0 — {name}({code}) 가격 {price}원")
        return False

    # Supabase에 주문 기록
    position = await insert_buy_order(code, name, price, quantity)
    if not position:
        return False

    # KIS 모의투자 매수 주문
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/order-cash"
    account_parts = KIS_MOCK_ACCOUNT_NO.split("-") if "-" in KIS_MOCK_ACCOUNT_NO else [KIS_MOCK_ACCOUNT_NO[:8], KIS_MOCK_ACCOUNT_NO[8:]]
    body = {
        "CANO": account_parts[0],
        "ACNT_PRDT_CD": account_parts[1] if len(account_parts) > 1 else "01",
        "PDNO": code,
        "ORD_DVSN": "00",   # 지정가
        "ORD_QTY": str(quantity),
        "ORD_UNPR": str(price),
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=_order_headers(token, "VTTC0802U"), timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("rt_cd") == "0":
                    await update_position_filled(position["id"], price)
                    logger.info(f"매수 체결: {name}({code}) {price:,}원 × {quantity}주")
                    await send_telegram(
                        f"<b>📥 자동 매수 체결</b>\n"
                        f"<b>{name} ({code})</b>\n"
                        f"가격: {price:,}원 × {quantity}주\n"
                        f"금액: {price * quantity:,}원"
                    )
                    return True
                else:
                    msg = data.get("msg1", "")
                    logger.error(f"매수 주문 실패: {name}({code}) — {msg}")
    except Exception as e:
        logger.error(f"매수 주문 오류: {e}")
    return False


async def place_sell_order(code: str, name: str, price: int, quantity: int, position_id: str, reason: str, buy_price: int) -> bool:
    """KIS 모의투자 지정가 매도 주문"""
    token = await _ensure_mock_token()
    if not token:
        return False

    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/order-cash"
    account_parts = KIS_MOCK_ACCOUNT_NO.split("-") if "-" in KIS_MOCK_ACCOUNT_NO else [KIS_MOCK_ACCOUNT_NO[:8], KIS_MOCK_ACCOUNT_NO[8:]]
    body = {
        "CANO": account_parts[0],
        "ACNT_PRDT_CD": account_parts[1] if len(account_parts) > 1 else "01",
        "PDNO": code,
        "ORD_DVSN": "00",
        "ORD_QTY": str(quantity),
        "ORD_UNPR": str(price),
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=_order_headers(token, "VTTC0801U"), timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("rt_cd") == "0":
                    pnl = calc_pnl_pct(buy_price, price)
                    await update_position_sold(position_id, price, pnl, reason)
                    reason_label = "익절 +2%" if reason == "take_profit" else "손절 -3%"
                    emoji = "💰" if reason == "take_profit" else "🛑"
                    logger.info(f"매도 체결: {name}({code}) {reason_label} ({pnl:+.1f}%)")
                    await send_telegram(
                        f"<b>{emoji} 자동 매도 ({reason_label})</b>\n"
                        f"<b>{name} ({code})</b>\n"
                        f"매수가: {buy_price:,}원 → 매도가: {price:,}원\n"
                        f"수익률: {pnl:+.2f}% ({quantity}주)"
                    )
                    return True
                else:
                    msg = data.get("msg1", "")
                    logger.error(f"매도 주문 실패: {name}({code}) — {msg}")
    except Exception as e:
        logger.error(f"매도 주문 오류: {e}")
    return False


async def run_buy_process():
    """매수 프로세스: cross_signal에서 고확신 종목 추출 → 중복 체크 → 매수"""
    cross_data = await fetch_json(f"{DATA_BASE_URL}/cross_signal.json")
    if not isinstance(cross_data, list):
        logger.warning("cross_signal.json 로드 실패")
        return

    targets = filter_high_confidence(cross_data)
    if not targets:
        logger.info("고확신 매수 대상 없음")
        return

    logger.info(f"고확신 종목 {len(targets)}개 발견")
    for t in targets:
        code = t["code"]
        name = t.get("name", "")

        # 중복 체크
        if await is_already_held_or_ordered(code):
            logger.info(f"이미 보유/주문중 — {name}({code}) 스킵")
            continue

        # 현재가 조회 (api_data에서)
        price = 0
        api_data = t.get("api_data", {})
        if api_data:
            price = api_data.get("price", {}).get("current", 0)

        if price <= 0:
            logger.warning(f"현재가 없음 — {name}({code}) 스킵")
            continue

        await place_buy_order(code, name, price)


async def check_positions_for_sell(current_price_data: dict):
    """보유 포지션 수익률 체크 → 익절/손절"""
    code = current_price_data["code"]
    current_price = current_price_data["price"]

    positions = await get_active_positions()
    for pos in positions:
        if pos["code"] != code or pos["status"] != "filled":
            continue

        buy_price = pos.get("filled_price") or pos.get("order_price", 0)
        if buy_price <= 0:
            continue

        reason = should_sell(buy_price, current_price)
        if reason:
            await place_sell_order(
                code=code,
                name=pos["name"],
                price=current_price,
                quantity=pos["quantity"],
                position_id=pos["id"],
                reason=reason,
                buy_price=buy_price,
            )
```

- [ ] **Step 3: 테스트 실행 확인**
- [ ] **Step 4: 커밋**

---

### Task 5: main.py 통합 — 자동매매 루프 추가

**Files:**
- Modify: `daemon/main.py`

- [ ] **Step 1: main.py에 자동매매 컴포넌트 통합**

on_execution 콜백에 수익률 감시 추가:
```python
from daemon.trader import check_positions_for_sell, run_buy_process
from daemon.github_monitor import check_workflow_completion

# on_execution에 추가:
async def on_execution(data: dict):
    # 기존 알림 로직 유지
    alerts = alert_engine.check(data, tick_volume=data.get("tick_volume"))
    for alert in alerts:
        name = get_stock_name(alert["code"])
        msg = format_alert(alert, stock_name=name)
        logger.info(f"알림 발송: {alert['type']} {alert['code']}")
        await send_telegram(msg)
    # 보유 포지션 수익률 체크
    await check_positions_for_sell(data)
```

워크플로우 감시 루프 추가:
```python
_last_workflow_time: str | None = None

async def schedule_auto_trade():
    """5분마다 theme-analysis 워크플로우 완료 확인 → 매수 프로세스"""
    global _last_workflow_time
    while True:
        await asyncio.sleep(300)
        try:
            completed, new_time = await check_workflow_completion(_last_workflow_time)
            if completed:
                _last_workflow_time = new_time
                logger.info("theme-analysis 완료 감지 — 매수 프로세스 시작")
                await run_buy_process()
        except Exception as e:
            logger.error(f"자동매매 루프 오류: {e}")
```

main() 함수의 asyncio.gather에 추가:
```python
await asyncio.gather(
    ws_client.connect(),
    schedule_refresh(),
    schedule_auto_trade(),  # 추가
)
```

- [ ] **Step 2: 전체 테스트 실행**

Run: `python -m pytest daemon/tests/ -v`
Expected: 기존 30건 + 신규 ~10건 = ~40건 PASS

- [ ] **Step 3: 커밋**

---

### Task 6: Supabase 테이블 생성 + .env 설정 + GCP 배포

- [ ] **Step 1: Supabase에 auto_trades 테이블 생성** (SQL 에디터에서 실행)
- [ ] **Step 2: .env에 GITHUB_TOKEN, SUPABASE_URL, SUPABASE_SECRET_KEY, KIS_MOCK_ACCOUNT_NO 추가**
- [ ] **Step 3: GCP VM에 코드 배포 + 데몬 재시작**
- [ ] **Step 4: 동작 확인 — 로그에서 워크플로우 감시/매수 프로세스 로그 확인**
