# KIS API 확장 — 호가/투자자동향 추가 + Code Assistant MCP 연결

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** KIS API 활용을 현재가 1개에서 호가+투자자동향으로 확장하고, KIS Code Assistant MCP를 개발 도구로 연결한다.

**Architecture:** `kis_client.py`에 2개 메서드 추가 (기존 패턴 유지). `generate_missing_data.py`의 `gen_orderbook()`에서 KIS 실데이터 시도 → 실패 시 기존 mock 폴백. MCP는 Claude Code 설정 파일에 추가.

**Tech Stack:** Python requests, KIS REST API (FHKST01010200, FHKST01010900), MCP (uv + stdio)

**Side-effect 방지 원칙:**
- 기존 메서드/함수 시그니처 변경 없음
- `gen_orderbook()`은 KIS 실패 시 기존 mock 로직 그대로 폴백
- 투자자동향은 새 메서드 추가만 (기존 호출자 변경 없음)
- MCP는 별도 설정 파일만 수정

---

## File Structure

| 파일 | 변경 | 역할 |
|------|------|------|
| `core/kis_client.py` | Modify | `get_asking_price()`, `get_investor()` 메서드 추가 |
| `scripts/generate_missing_data.py` | Modify | `gen_orderbook()`에서 KIS 호가 API 호출 시도 + mock 폴백 |
| `tests/test_kis_client.py` | Create | KIS 클라이언트 단위 테스트 |
| `~/.claude/settings.local.json` | Modify | KIS Code Assistant MCP 서버 등록 |

---

## Task 1: kis_client.py에 호가 조회 메서드 추가

**Files:**
- Modify: `core/kis_client.py:128` (get_current_price 뒤에 추가)
- Test: `tests/test_kis_client.py`

- [ ] **Step 1: 호가 조회 테스트 작성**

```python
# tests/test_kis_client.py
from unittest.mock import patch, MagicMock
from core.kis_client import KISClient


def test_get_asking_price_parses_response():
    """KIS 호가 API 응답을 올바르게 파싱하는지 검증"""
    mock_response = {
        "rt_cd": "0",
        "output1": {
            "askp1": "184000", "askp2": "184500", "askp3": "185000",
            "askp4": "185500", "askp5": "186000",
            "bidp1": "183500", "bidp2": "183000", "bidp3": "182500",
            "bidp4": "182000", "bidp5": "181500",
            "askp_rsqn1": "1000", "askp_rsqn2": "2000", "askp_rsqn3": "1500",
            "askp_rsqn4": "800", "askp_rsqn5": "600",
            "bidp_rsqn1": "1200", "bidp_rsqn2": "1800", "bidp_rsqn3": "900",
            "bidp_rsqn4": "700", "bidp_rsqn5": "500",
            "total_askp_rsqn": "5900",
            "total_bidp_rsqn": "5100",
        },
    }
    client = KISClient()
    client.access_token = "fake_token"
    client._token_expires_at = None

    with patch.object(client, "ensure_token", return_value=True), \
         patch("core.kis_client.requests.get") as mock_get:
        mock_get.return_value = MagicMock(json=lambda: mock_response)
        result = client.get_asking_price("005930")

    assert result is not None
    assert len(result["ask_levels"]) == 5
    assert len(result["bid_levels"]) == 5
    assert result["ask_levels"][0]["price"] == 184000
    assert result["ask_levels"][0]["qty"] == 1000
    assert result["bid_levels"][0]["price"] == 183500
    assert result["total_ask_qty"] == 5900
    assert result["total_bid_qty"] == 5100


def test_get_asking_price_returns_none_on_failure():
    """API 실패 시 None 반환"""
    client = KISClient()
    with patch.object(client, "ensure_token", return_value=False):
        assert client.get_asking_price("005930") is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd /Users/sonbyeongcheol/DEV/stock_toolkit && python -m pytest tests/test_kis_client.py -v`
Expected: FAIL — `AttributeError: 'KISClient' object has no attribute 'get_asking_price'`

- [ ] **Step 3: get_asking_price 메서드 구현**

`core/kis_client.py`의 `get_current_price` 메서드 뒤 (L175 이후)에 추가:

```python
def get_asking_price(self, stock_code: str, _retry: bool = False) -> dict | None:
    """주식현재가 호가/예상체결 조회 (tr_id: FHKST01010200)"""
    if not self.ensure_token():
        return None
    try:
        url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST01010200",
            "custtype": "P",
        }
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
        }
        res = requests.get(url, headers=headers, params=params, timeout=15)
        data = res.json()
        if data.get("rt_cd") == "0":
            o = data.get("output1", {})
            ask_levels = []
            bid_levels = []
            for i in range(1, 6):
                ask_levels.append({
                    "price": int(o.get(f"askp{i}", 0)),
                    "qty": int(o.get(f"askp_rsqn{i}", 0)),
                    "level": i,
                })
                bid_levels.append({
                    "price": int(o.get(f"bidp{i}", 0)),
                    "qty": int(o.get(f"bidp_rsqn{i}", 0)),
                    "level": i,
                })
            return {
                "ask_levels": ask_levels,
                "bid_levels": bid_levels,
                "total_ask_qty": int(o.get("total_askp_rsqn", 0)),
                "total_bid_qty": int(o.get("total_bidp_rsqn", 0)),
            }
        else:
            msg = data.get("msg1", "")
            if "만료" in msg and not _retry:
                self.access_token = ""
                self._token_expires_at = None
                token = self._issue_new_token()
                if token:
                    self.access_token = token
                    return self.get_asking_price(stock_code, _retry=True)
            print(f"  [KIS] {stock_code} 호가 조회 실패: {msg}")
    except Exception as e:
        print(f"  [KIS] {stock_code} 호가 API 오류: {e}")
    return None
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd /Users/sonbyeongcheol/DEV/stock_toolkit && python -m pytest tests/test_kis_client.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: 커밋**

```bash
git add core/kis_client.py tests/test_kis_client.py
git commit -m "feat: KIS 호가 조회 API 추가 (get_asking_price)"
```

---

## Task 2: kis_client.py에 투자자동향 조회 메서드 추가

**Files:**
- Modify: `core/kis_client.py` (get_asking_price 뒤에 추가)
- Modify: `tests/test_kis_client.py`

- [ ] **Step 1: 투자자동향 테스트 작성**

`tests/test_kis_client.py`에 추가:

```python
def test_get_investor_parses_response():
    """KIS 투자자동향 API 응답을 올바르게 파싱하는지 검증"""
    mock_response = {
        "rt_cd": "0",
        "output": [
            {
                "stck_bsop_date": "20260320",
                "prsn_ntby_qty": "-5000",
                "frgn_ntby_qty": "3000",
                "orgn_ntby_qty": "2000",
                "prsn_ntby_tr_pbmn": "-915000000",
                "frgn_ntby_tr_pbmn": "549000000",
                "orgn_ntby_tr_pbmn": "366000000",
            }
        ],
    }
    client = KISClient()
    client.access_token = "fake_token"
    client._token_expires_at = None

    with patch.object(client, "ensure_token", return_value=True), \
         patch("core.kis_client.requests.get") as mock_get:
        mock_get.return_value = MagicMock(json=lambda: mock_response)
        result = client.get_investor("005930")

    assert result is not None
    assert len(result) >= 1
    assert result[0]["date"] == "20260320"
    assert result[0]["individual_net_qty"] == -5000
    assert result[0]["foreign_net_qty"] == 3000
    assert result[0]["institution_net_qty"] == 2000


def test_get_investor_returns_none_on_failure():
    """API 실패 시 None 반환"""
    client = KISClient()
    with patch.object(client, "ensure_token", return_value=False):
        assert client.get_investor("005930") is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd /Users/sonbyeongcheol/DEV/stock_toolkit && python -m pytest tests/test_kis_client.py::test_get_investor_parses_response -v`
Expected: FAIL — `AttributeError: 'KISClient' object has no attribute 'get_investor'`

- [ ] **Step 3: get_investor 메서드 구현**

`core/kis_client.py`의 `get_asking_price` 뒤에 추가:

```python
def get_investor(self, stock_code: str, _retry: bool = False) -> list[dict] | None:
    """주식현재가 투자자 조회 (tr_id: FHKST01010900)"""
    if not self.ensure_token():
        return None
    try:
        url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-investor"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST01010900",
            "custtype": "P",
        }
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
        }
        res = requests.get(url, headers=headers, params=params, timeout=15)
        data = res.json()
        if data.get("rt_cd") == "0":
            rows = data.get("output", [])
            result = []
            for row in rows:
                result.append({
                    "date": row.get("stck_bsop_date", ""),
                    "individual_net_qty": int(row.get("prsn_ntby_qty", 0)),
                    "foreign_net_qty": int(row.get("frgn_ntby_qty", 0)),
                    "institution_net_qty": int(row.get("orgn_ntby_qty", 0)),
                    "individual_net_amount": int(row.get("prsn_ntby_tr_pbmn", 0)),
                    "foreign_net_amount": int(row.get("frgn_ntby_tr_pbmn", 0)),
                    "institution_net_amount": int(row.get("orgn_ntby_tr_pbmn", 0)),
                })
            return result
        else:
            msg = data.get("msg1", "")
            if "만료" in msg and not _retry:
                self.access_token = ""
                self._token_expires_at = None
                token = self._issue_new_token()
                if token:
                    self.access_token = token
                    return self.get_investor(stock_code, _retry=True)
            print(f"  [KIS] {stock_code} 투자자 조회 실패: {msg}")
    except Exception as e:
        print(f"  [KIS] {stock_code} 투자자 API 오류: {e}")
    return None
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd /Users/sonbyeongcheol/DEV/stock_toolkit && python -m pytest tests/test_kis_client.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: 커밋**

```bash
git add core/kis_client.py tests/test_kis_client.py
git commit -m "feat: KIS 투자자동향 조회 API 추가 (get_investor)"
```

---

## Task 3: gen_orderbook()에 KIS 실데이터 연동 (mock 폴백 유지)

**Files:**
- Modify: `scripts/generate_missing_data.py:321-389` (`gen_orderbook` 함수)

**Side-effect 방지:** KIS API 실패 시 기존 mock 로직 100% 유지. 성공 시에만 실데이터로 대체.

- [ ] **Step 1: gen_orderbook() 수정 — KIS 호가 시도 + mock 폴백**

`scripts/generate_missing_data.py`의 `gen_orderbook()` 함수 내부, L338 `orderbook_items = []` 바로 위에 KIS 클라이언트 초기화 추가. 각 종목 루프 내부에서 KIS 호출 시도:

```python
def gen_orderbook():
    print("\n[4] orderbook.json — 호가창 압력 분석")

    latest = load_json(SOURCE_LATEST)
    investor_data = latest.get("investor_data", {})

    target_codes = ["000660", "064550", "005930", "086520", "000270"]
    target_names = {
        "000660": "SK하이닉스", "064550": "LG CNS", "005930": "삼성전자",
        "086520": "에코프로비엠", "000270": "기아",
    }
    prices = {
        "000660": 910000, "064550": 78500, "005930": 183500,
        "086520": 82000, "000270": 105000,
    }

    # KIS API 클라이언트 (실패해도 mock 폴백)
    kis = None
    try:
        from core.kis_client import KISClient
        kis = KISClient()
        if not kis.ensure_token():
            kis = None
    except Exception:
        kis = None

    orderbook_items = []
    kis_count = 0
    for code in target_codes:
        price = prices.get(code, 100000)
        name = target_names.get(code, code)
        inv = investor_data.get(code, {})
        foreign_net = inv.get("foreign_net", 0)

        # KIS 실데이터 시도
        kis_data = None
        if kis:
            try:
                kis_data = kis.get_asking_price(code)
                time.sleep(0.05)  # API 호출 후 항상 sleep (성공/실패 무관)
            except Exception:
                kis_data = None

        if kis_data:
            # KIS 실데이터 사용
            ask_levels = kis_data["ask_levels"]
            bid_levels = kis_data["bid_levels"]
            total_ask = kis_data["total_ask_qty"]
            total_bid = kis_data["total_bid_qty"]
            # 현재가도 1호가 기준으로 갱신
            if bid_levels and bid_levels[0]["price"] > 0:
                price = bid_levels[0]["price"]
            kis_count += 1
        else:
            # 기존 mock 로직 (폴백)
            ask_levels = []
            bid_levels = []
            for lvl in range(1, 6):
                ask_price = int(price * (1 + lvl * 0.002))
                bid_price = int(price * (1 - lvl * 0.002))
                ask_qty = max(100, 500 - lvl * 60 + (200 if foreign_net < 0 else 0))
                bid_qty = max(100, 500 - lvl * 60 + (200 if foreign_net > 0 else 0))
                ask_levels.append({"price": ask_price, "qty": ask_qty, "level": lvl})
                bid_levels.append({"price": bid_price, "qty": bid_qty, "level": lvl})
            total_ask = sum(l["qty"] for l in ask_levels)
            total_bid = sum(l["qty"] for l in bid_levels)

        pressure = round((total_bid - total_ask) / max(total_bid + total_ask, 1) * 100, 1)

        orderbook_items.append({
            "code": code,
            "name": name,
            "current_price": price,
            "ask_levels": ask_levels,
            "bid_levels": bid_levels,
            "total_ask_qty": total_ask,
            "total_bid_qty": total_bid,
            "bid_ask_ratio": round(total_bid / max(total_ask, 1), 2),
            "pressure_pct": pressure,
            "pressure_signal": "매수우위" if pressure > 10 else ("매도우위" if pressure < -10 else "균형"),
            "foreign_net_today": foreign_net,
            "updated_at": latest.get("timestamp", ""),
        })

    data_source = f"KIS API {kis_count}종목" if kis_count > 0 else "mock (KIS 미연결)"
    result = {
        "generated_at": datetime.now(KST).isoformat(),
        "data_source": data_source,
        "note": "5단계 매도/매수 호가. KIS API 연결 시 실데이터, 미연결 시 mock",
        "items": orderbook_items,
        "summary": {
            "total": len(orderbook_items),
            "buy_dominant": sum(1 for o in orderbook_items if o["pressure_signal"] == "매수우위"),
            "sell_dominant": sum(1 for o in orderbook_items if o["pressure_signal"] == "매도우위"),
        },
    }
    save_json("orderbook.json", result)
    print(f"  저장 완료 — {len(orderbook_items)}종목 (KIS: {kis_count}, mock: {len(orderbook_items) - kis_count})")
    return len(orderbook_items)
```

- [ ] **Step 2: import time 추가**

`generate_missing_data.py` 상단 (L7 `import os` 뒤)에 `import time` 추가. 현재 import 목록에 없음.

- [ ] **Step 3: 기존 테스트 통과 확인**

Run: `cd /Users/sonbyeongcheol/DEV/stock_toolkit && python -m pytest tests/ -v --tb=short`
Expected: 기존 테스트 전부 PASS (side-effect 없음)

- [ ] **Step 4: 수동 검증 — KIS 없이 mock 폴백 동작 확인**

Run: `cd /Users/sonbyeongcheol/DEV/stock_toolkit && python -c "from scripts.generate_missing_data import gen_orderbook; gen_orderbook()"`
Expected: `저장 완료 — 5종목 (KIS: 0, mock: 5)` (KIS 토큰 없는 환경에서)

- [ ] **Step 5: 커밋**

```bash
git add scripts/generate_missing_data.py
git commit -m "feat: gen_orderbook에 KIS 호가 실데이터 연동 (mock 폴백 유지)"
```

---

## Task 4: KIS Code Assistant MCP 설정 (Phase 2)

**Files:**
- 신규 설정: `~/.claude/settings.local.json` (MCP 서버 등록)

**사전 조건:** open-trading-api 저장소 클론 + uv 설치

- [ ] **Step 1: open-trading-api 저장소 클론**

```bash
cd ~/DEV && git clone https://github.com/koreainvestment/open-trading-api.git
```

- [ ] **Step 2: uv 설치 확인**

```bash
which uv || curl -LsSf https://astral.sh/uv/install.sh | sh
```

- [ ] **Step 3: KIS Code Assistant MCP 의존성 설치**

```bash
cd ~/DEV/open-trading-api/MCP/KIS\ Code\ Assistant\ MCP && uv sync
```

- [ ] **Step 4: Claude Code 설정에 MCP 서버 등록**

`~/.claude/settings.local.json`에 추가:

```json
{
  "mcpServers": {
    "kis-code-assistant-mcp": {
      "command": "uv",
      "args": ["--directory", "/Users/sonbyeongcheol/DEV/open-trading-api/MCP/KIS Code Assistant MCP", "run", "server.py", "--stdio"]
    }
  }
}
```

- [ ] **Step 5: MCP 연결 테스트**

Claude Code 재시작 후, 대화에서 KIS Code Assistant 도구가 사용 가능한지 확인.

- [ ] **Step 6: 커밋 (해당 없음 — 프로젝트 외부 설정)**

MCP 설정은 `~/.claude/` 경로이므로 stock_toolkit 저장소에 커밋하지 않음.

---

## 검증 체크리스트

- [ ] `python -m pytest tests/test_kis_client.py -v` → 4 tests PASS
- [ ] `python -m pytest tests/ -v` → 기존 전체 테스트 PASS (side-effect 없음)
- [ ] `gen_orderbook()` KIS 미연결 시 → mock 폴백 정상 동작
- [ ] `kis_client.py` 기존 `get_current_price`, `get_prices_batch` 메서드 변경 없음
- [ ] `run_all.py` 변경 없음
- [ ] Claude Code에서 KIS Code Assistant MCP 도구 사용 가능
