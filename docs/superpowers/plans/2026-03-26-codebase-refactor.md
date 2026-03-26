# 코드베이스 리팩토링 & 성능 개선 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 진단 보고서(P1-P2) 기반 daemon/trader.py 중복 제거, 성능 병목 해소, Dashboard 폴링 버그 수정

**Architecture:** daemon/trader.py의 6곳 계정 파싱·2곳 미체결 취소·2곳 보유일 계산·2곳 토큰 재시도를 유틸리티로 추출. 당일 매도 중복 쿼리를 단일 함수로 통합. Dashboard 폴링 간격을 동적으로 재판단하도록 수정.

**Tech Stack:** Python 3.12 (asyncio, aiohttp), React 18, TypeScript

**순서 원칙:** 순수 리팩토링(동작 변경 없음) → 로직 통합(1개 함수 제거) → 버그 수정. 각 Task는 독립적으로 커밋 가능하며 이전 Task에 의존하지 않음(Task 1-4). Task 5는 Task 1-4 결과에 의존.

---

### Task 1: 계정번호 파싱 유틸리티 추출

**Files:**
- Modify: `daemon/trader.py` (라인 126, 181, 234, 441, 700, 986)

**위험도:** 없음 — 순수 리팩토링, 동작 변경 없음

- [ ] **Step 1: 유틸리티 함수 추가**

`daemon/trader.py` 상단(`_order_headers` 함수 뒤, 라인 70 부근)에 추가:

```python
def _parse_account() -> tuple[str, str]:
    """KIS_MOCK_ACCOUNT_NO를 (CANO, ACNT_PRDT_CD) 튜플로 파싱"""
    parts = KIS_MOCK_ACCOUNT_NO.split("-") if "-" in KIS_MOCK_ACCOUNT_NO else [KIS_MOCK_ACCOUNT_NO[:8], KIS_MOCK_ACCOUNT_NO[8:]]
    return parts[0], parts[1] if len(parts) > 1 else "01"
```

- [ ] **Step 2: 6곳의 인라인 파싱을 유틸리티 호출로 교체**

각 위치에서 기존 2-3줄을 1줄로 교체:

**라인 126-129 (`_kis_order`):**
```python
# 기존
account_parts = KIS_MOCK_ACCOUNT_NO.split("-") if "-" in KIS_MOCK_ACCOUNT_NO else [KIS_MOCK_ACCOUNT_NO[:8], KIS_MOCK_ACCOUNT_NO[8:]]
body = {
    "CANO": account_parts[0],
    "ACNT_PRDT_CD": account_parts[1] if len(account_parts) > 1 else "01",
# 교체
cano, acnt_cd = _parse_account()
body = {
    "CANO": cano,
    "ACNT_PRDT_CD": acnt_cd,
```

동일 패턴을 아래 5곳에도 적용:
- 라인 181-182 (`_cancel_unfilled`)
- 라인 234-235 (`_cancel_unfilled_sell`)
- 라인 441 (`fetch_available_balance`)
- 라인 700-702 (`cancel_all_pending_orders`)
- 라인 986-989 (`_kis_order_market`)

- [ ] **Step 3: 동작 확인**

```bash
cd /Users/sonbyeongcheol/DEV/stock_toolkit && python -c "from daemon.trader import _parse_account; print(_parse_account())"
```

Expected: 계정번호 튜플 출력 (에러 없음)

- [ ] **Step 4: 커밋**

```bash
git add daemon/trader.py
git commit -m "refactor: 계정번호 파싱 유틸리티 _parse_account() 추출 — 6곳 중복 제거"
```

---

### Task 2: 당일 매도 조회 중복 쿼리 통합

**Files:**
- Modify: `daemon/trader.py` (라인 479, 500, 556-590)

**위험도:** 낮음 — 동일 데이터를 1회만 조회, 반환 형식만 변경

- [ ] **Step 1: `_get_sold_today_trades()`를 확장하여 코드 세트도 반환**

기존 `_get_sold_today_trades()` (라인 556-571)를 수정:

```python
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
```

(함수 자체는 변경 없음 — SELECT에 이미 `code` 포함)

- [ ] **Step 2: `_get_sold_today_codes()` 삭제**

라인 574-590 전체 삭제.

- [ ] **Step 3: `run_buy_process()`에서 단일 호출로 통합**

기존 (라인 479-508):
```python
# 기존: 2회 호출
sold_today = await _get_sold_today_trades()
if sold_today:
    total_loss = sum(t.get("pnl_pct", 0) for t in sold_today)
    if total_loss <= MAX_DAILY_LOSS_PCT:
        ...
        return
...
sold_today = await _get_sold_today_codes()
...
    if code in sold_today:
```

교체:
```python
# 개선: 1회 호출, 2가지 용도로 활용
sold_today_rows = await _get_sold_today_trades()
if sold_today_rows:
    total_loss = sum(t.get("pnl_pct", 0) for t in sold_today_rows)
    if total_loss <= MAX_DAILY_LOSS_PCT:
        logger.warning(f"당일 누적 손실 {total_loss:.1f}% — 매수 중단 (한도 {MAX_DAILY_LOSS_PCT}%)")
        return
sold_today_codes = {r["code"] for r in sold_today_rows if r.get("code")}
...
    if code in sold_today_codes:
```

- [ ] **Step 4: 동작 확인**

```bash
python -c "import asyncio; from daemon.trader import _get_sold_today_trades; print(asyncio.run(_get_sold_today_trades()))"
```

Expected: 리스트 반환 (빈 리스트 또는 매도 내역)

- [ ] **Step 5: 커밋**

```bash
git add daemon/trader.py
git commit -m "perf: 당일 매도 조회 중복 쿼리 통합 — _get_sold_today_codes 제거, 1회 조회로 통합"
```

---

### Task 3: 미체결 취소 함수 통합

**Files:**
- Modify: `daemon/trader.py` (라인 176-279)

**위험도:** 중간 — 두 함수의 유일한 차이점(`SLL_BUY_DVSN_CD`: "02" 매수 / "01" 매도)을 파라미터화. 호출부도 함께 수정 필수.

- [ ] **Step 1: `_cancel_unfilled`에 `is_sell` 파라미터 추가**

기존 `_cancel_unfilled` (라인 176-226)을 수정:

```python
async def _cancel_unfilled(code: str, is_sell: bool = False) -> int | None:
    """KIS 미체결 조회 → 해당 종목 미체결분 취소, 미체결 수량 반환. 조회 실패 시 None."""
    token = await _ensure_mock_token()
    if not token:
        return None
    cano, acnt_cd = _parse_account()
    url = f"{KIS_MOCK_BASE_URL}/uapi/domestic-stock/v1/trading/inquire-nccs"
    sll_buy = "01" if is_sell else "02"
    label = "매도 " if is_sell else ""
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
```

- [ ] **Step 2: `_cancel_unfilled_sell` 삭제**

라인 229-279 전체 삭제.

- [ ] **Step 3: `_cancel_unfilled_sell` 호출부를 `_cancel_unfilled(code, is_sell=True)`로 교체**

`_verify_sell_fill` 함수 (라인 288):
```python
# 기존
unfilled = await _cancel_unfilled_sell(code)
# 교체
unfilled = await _cancel_unfilled(code, is_sell=True)
```

파일 내에서 `_cancel_unfilled_sell`을 호출하는 모든 곳을 검색하여 동일하게 교체.

- [ ] **Step 4: import 확인 및 동작 테스트**

```bash
python -c "from daemon.trader import _cancel_unfilled; print('OK')"
```

Expected: `OK` (import 에러 없음)

- [ ] **Step 5: 커밋**

```bash
git add daemon/trader.py
git commit -m "refactor: _cancel_unfilled + _cancel_unfilled_sell 통합 — is_sell 파라미터로 매수/매도 구분"
```

---

### Task 4: 보유일 계산 유틸리티 추출

**Files:**
- Modify: `daemon/trader.py` (라인 656-666, 805-813)

**위험도:** 없음 — 순수 리팩토링

- [ ] **Step 1: 유틸리티 함수 추가**

`daemon/trader.py` 상단(`_parse_account` 함수 근처)에 추가:

```python
_KST = timezone(timedelta(hours=9))

def _calc_hold_days(pos: dict) -> int:
    """포지션의 보유일수 계산 (KST 기준)"""
    created = pos.get("filled_at") or pos.get("created_at", "")
    if not created:
        return 0
    try:
        created_date = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(_KST).date()
        return (datetime.now(_KST).date() - created_date).days
    except Exception:
        return 0
```

- [ ] **Step 2: check_positions_for_sell의 보유일 계산 교체 (라인 656-666)**

```python
# 기존 (라인 656-666)
_KST = timezone(timedelta(hours=9))
hold_days = 0
created = pos.get("filled_at") or pos.get("created_at", "")
if created:
    try:
        created_date = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(_KST).date()
        today = datetime.now(_KST).date()
        hold_days = (today - created_date).days
    except Exception:
        pass

# 교체
hold_days = _calc_hold_days(pos)
```

- [ ] **Step 3: close_all_positions_eod의 보유일 계산 교체 (라인 805-813)**

```python
# 기존 (라인 805-813)
hold_days = 0
created = pos.get("filled_at") or pos.get("created_at", "")
if created:
    try:
        created_date = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(_KST).date()
        hold_days = (today - created_date).days
    except Exception:
        pass

# 교체
hold_days = _calc_hold_days(pos)
```

주의: close_all_positions_eod 함수 상단의 `_KST = timezone(timedelta(hours=9))` 및 `today = datetime.now(_KST).date()`가 다른 곳에서도 사용되는지 확인. 사용되면 유지, 보유일 계산에만 쓰이면 제거.

- [ ] **Step 4: 동작 확인**

```bash
python -c "from daemon.trader import _calc_hold_days; print(_calc_hold_days({'created_at': '2026-03-25T00:00:00Z'}))"
```

Expected: 1 (또는 오늘 날짜 기준 일수)

- [ ] **Step 5: 커밋**

```bash
git add daemon/trader.py
git commit -m "refactor: 보유일 계산 유틸리티 _calc_hold_days() 추출 — 2곳 중복 제거"
```

---

### Task 5: 토큰 재시도 파라미터명 통일

**Files:**
- Modify: `daemon/trader.py` (라인 120, 980)

**위험도:** 없음 — 파라미터명만 통일, 동작 변경 없음

- [ ] **Step 1: `_kis_order_market`의 `_retry` → `retry`로 변경**

```python
# 기존 (라인 980)
async def _kis_order_market(tr_id: str, code: str, quantity: int, _retry: bool = True) -> dict | None:
# 교체
async def _kis_order_market(tr_id: str, code: str, quantity: int, retry: bool = True) -> dict | None:
```

함수 내부의 `_retry` 참조도 모두 `retry`로 변경 (라인 1005, 1009):
```python
# 기존
if _retry and ("만료" in msg or "token" in msg.lower()):
    return await _kis_order_market(tr_id, code, quantity, _retry=False)
# 교체
if retry and ("만료" in msg or "token" in msg.lower()):
    return await _kis_order_market(tr_id, code, quantity, retry=False)
```

- [ ] **Step 2: 동작 확인**

```bash
python -c "from daemon.trader import _kis_order_market; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add daemon/trader.py
git commit -m "refactor: _kis_order_market 파라미터명 _retry → retry 통일"
```

---

### Task 6: Dashboard 폴링 간격 버그 수정

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx` (라인 267-271)

**위험도:** 낮음 — 폴링 interval 로직만 변경, UI/데이터 영향 없음

- [ ] **Step 1: 정적 폴링 → 동적 폴링으로 변경**

기존 (라인 267-271):
```typescript
// 장중 5분, 장외 10분 자동 폴링
const now = new Date();
const h = now.getHours();
const isMarketHours = h >= 9 && h < 16;
const interval = setInterval(loadAllData, isMarketHours ? 5 * 60 * 1000 : 10 * 60 * 1000);
```

교체:
```typescript
// 장중 5분, 장외 10분 자동 폴링 (매 틱마다 장중/장외 재판단)
let pollTimer: ReturnType<typeof setTimeout> | null = null;
const schedulePoll = () => {
  const h = new Date().getHours();
  const delay = (h >= 9 && h < 16) ? 5 * 60 * 1000 : 10 * 60 * 1000;
  pollTimer = setTimeout(() => {
    if (document.visibilityState === "visible") loadAllData();
    schedulePoll();
  }, delay);
};
schedulePoll();
```

- [ ] **Step 2: cleanup 코드 업데이트 (라인 272)**

기존:
```typescript
return () => { clearInterval(interval); subscription.unsubscribe(); document.removeEventListener("visibilitychange", handleVisibility); };
```

교체:
```typescript
return () => { if (pollTimer) clearTimeout(pollTimer); subscription.unsubscribe(); document.removeEventListener("visibilitychange", handleVisibility); };
```

- [ ] **Step 3: 빌드 확인**

```bash
cd /Users/sonbyeongcheol/DEV/stock_toolkit/frontend && npx tsc --noEmit
```

Expected: 타입 에러 없음

- [ ] **Step 4: 커밋**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "fix: Dashboard 폴링 간격 버그 — 장중→장외 전환 시 동적 재판단 + 탭 비활성 시 폴링 스킵"
```

---

## 실행 전 체크리스트

- Task 1-5는 모두 `daemon/trader.py` 수정. **Task 1→2→3→4→5 순서로 실행** (라인 번호가 앞 Task 완료 후 이동하므로)
- Task 6은 frontend 독립 수정. Task 1-5와 병렬 실행 가능
- 각 Task 후 `python -c "from daemon.trader import ..."` 로 import 에러 확인
- 모든 커밋은 단일 파일 변경으로 rollback 용이
