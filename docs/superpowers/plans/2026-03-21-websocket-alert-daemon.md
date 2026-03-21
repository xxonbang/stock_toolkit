# WebSocket 알림 데몬 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GCP e2-micro에서 독립 실행되는 KIS WebSocket 실시간 알림 데몬 구현 — 기존 코드 변경 제로

**Architecture:** Python asyncio 기반 단일 프로세스. KIS WebSocket(ws://)으로 체결가 수신 → 인메모리에서 조건 판정 → Telegram Bot API로 즉시 알림. 기존 stock_toolkit 코드와 완전 독립된 별도 디렉토리(`daemon/`)에 구성.

**Tech Stack:** Python 3.11, websockets, asyncio, aiohttp (Telegram/HTTP), APScheduler (종목 갱신)

**참고 문서:** `docs/research/2026-03-21-gcp-migration.md` 섹션 9

**의도적 제외 (후속 태스크로 별도 구현):**
- 수급 반전 알림 — H0STCNT0 체결가만으로는 외국인/기관 순매수 판단 불가, REST API 주기 호출 또는 H0STASP0 호가 구독 필요
- 호가 매수벽/매도벽 감지 — H0STASP0 구독 + 호가 분석 로직 필요, 구독 슬롯 소모(종목당 2슬롯)

---

## 파일 구조

```
daemon/
├── main.py                  # 엔트리포인트 — asyncio 이벤트루프, 컴포넌트 조합
├── ws_client.py             # KIS WebSocket 연결/수신/PINGPONG/재연결
├── alert_rules.py           # 알림 판정 규칙 (급등/급락/거래량/수급/목표가)
├── notifier.py              # Telegram 알림 발송 (쓰로틀링, 포맷팅)
├── stock_manager.py         # 구독 종목 관리 (자동 갱신 + 수동)
├── config.py                # 환경변수 로드 (.env)
├── requirements.txt         # 데몬 전용 의존성
├── .env.example             # 필요한 환경변수 목록
└── tests/
    ├── test_alert_rules.py  # 알림 판정 유닛 테스트
    ├── test_ws_client.py    # WebSocket 파싱 유닛 테스트
    ├── test_notifier.py     # 알림 포맷팅/쓰로틀 테스트
    └── test_stock_manager.py # 종목 관리 테스트
```

**설계 원칙:**
- `daemon/` 디렉토리는 기존 stock_toolkit과 **완전 독립** — import 없음, 의존 없음
- 각 파일은 하나의 책임만 담당
- 기존 `core/`, `modules/`, `scripts/` 일체 변경 없음

---

### Task 1: 프로젝트 스캐폴딩 + 설정

**Files:**
- Create: `daemon/__init__.py`
- Create: `daemon/tests/__init__.py`
- Create: `daemon/config.py`
- Create: `daemon/requirements.txt`
- Create: `daemon/.env.example`

- [ ] **Step 0: __init__.py 생성 (패키지 인식용)**

```python
# daemon/__init__.py — 빈 파일
```

```python
# daemon/tests/__init__.py — 빈 파일
```

- [ ] **Step 1: requirements.txt 작성**

```
websockets>=12.0
aiohttp>=3.9.0
APScheduler>=3.10.0
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 2: .env.example 작성**

```
KIS_APP_KEY=
KIS_APP_SECRET=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
# GitHub Pages 데이터 URL (종목 자동 갱신용)
DATA_BASE_URL=https://xxonbang.github.io/stock_toolkit/data
```

- [ ] **Step 3: config.py 작성**

```python
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

KIS_APP_KEY = os.getenv("KIS_APP_KEY", "")
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DATA_BASE_URL = os.getenv("DATA_BASE_URL", "https://xxonbang.github.io/stock_toolkit/data")

# KIS WebSocket
WS_URL_REAL = "ws://ops.koreainvestment.com:21000"
WS_URL_MOCK = "ws://ops.koreainvestment.com:31000"
WS_URL = os.getenv("KIS_WS_URL", WS_URL_REAL)

# 알림 임계값
ALERT_SURGE_LEVELS = [5.0, 10.0, 15.0]   # 급등 단계별 (%)
ALERT_DROP_LEVELS = [-3.0, -5.0]          # 급락 단계별 (%)
ALERT_VOLUME_RATIO = 3.0                  # 거래량 폭증 배수
ALERT_COOLDOWN_SEC = 300                  # 동일 종목 동일 이벤트 재알림 방지 (초)
```

- [ ] **Step 4: pip install 확인**

Run: `cd /Users/sonbyeongcheol/DEV/stock_toolkit && pip install websockets aiohttp APScheduler python-dotenv pytest pytest-asyncio`
Expected: 정상 설치

- [ ] **Step 5: 커밋**

```bash
git add daemon/__init__.py daemon/tests/__init__.py daemon/config.py daemon/requirements.txt daemon/.env.example
git commit -m "feat(daemon): 프로젝트 스캐폴딩 — config, requirements, .env.example"
```

---

### Task 2: KIS WebSocket 클라이언트

**Files:**
- Create: `daemon/ws_client.py`
- Create: `daemon/tests/test_ws_client.py`

- [ ] **Step 1: 테스트 작성 — 체결가 메시지 파싱**

KIS WebSocket 체결가(H0STCNT0) 메시지는 `|`로 구분된 헤더 + `^`로 구분된 데이터 필드.
메시지 포맷: `{암호화여부}|{TR ID}|{데이터건수}|{데이터}`

```python
# daemon/tests/test_ws_client.py
import pytest
from daemon.ws_client import parse_stock_execution

# KIS H0STCNT0 체결가 메시지의 데이터 부분 (^로 구분, 45개 필드)
# 주요 필드 인덱스: 0=종목코드, 2=체결시간, 3=현재가, 4=전일대비부호,
# 5=전일대비, 8=등락률, 11=단일체결수량, 12=누적거래량, 13=누적거래대금
SAMPLE_DATA = "005930^0^153000^68500^2^500^0^68800^0.74^68200^0^250^12345678^890000000^68000^69000^68500^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0^0"


def test_parse_stock_execution_basic():
    result = parse_stock_execution(SAMPLE_DATA)
    assert result["code"] == "005930"
    assert result["price"] == 68500
    assert result["change_rate"] == 0.74
    assert result["tick_volume"] == 250
    assert result["volume"] == 12345678


def test_parse_stock_execution_invalid():
    result = parse_stock_execution("invalid^data")
    assert result is None


def test_parse_stock_execution_empty():
    result = parse_stock_execution("")
    assert result is None
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `cd /Users/sonbyeongcheol/DEV/stock_toolkit && python -m pytest daemon/tests/test_ws_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'daemon.ws_client'`

- [ ] **Step 3: ws_client.py 구현**

```python
"""KIS WebSocket 클라이언트 — 체결가/호가 실시간 수신"""
import asyncio
import json
import logging
import time
import aiohttp
import websockets
from daemon.config import KIS_APP_KEY, KIS_APP_SECRET, WS_URL

logger = logging.getLogger("daemon.ws")

# KIS H0STCNT0 필드 인덱스
IDX_CODE = 0
IDX_TIME = 2
IDX_PRICE = 3
IDX_SIGN = 4
IDX_CHANGE = 5
IDX_CHANGE_RATE = 8
IDX_TICK_VOLUME = 11  # 단일 체결 수량
IDX_VOLUME = 12       # 누적 거래량
IDX_TRADE_AMOUNT = 13


def parse_stock_execution(data_str: str) -> dict | None:
    """H0STCNT0 체결가 데이터 문자열을 파싱"""
    if not data_str:
        return None
    fields = data_str.split("^")
    if len(fields) < 14:
        return None
    try:
        return {
            "code": fields[IDX_CODE],
            "time": fields[IDX_TIME],
            "price": int(fields[IDX_PRICE]),
            "change_sign": fields[IDX_SIGN],
            "change": int(fields[IDX_CHANGE]),
            "change_rate": float(fields[IDX_CHANGE_RATE]),
            "tick_volume": int(fields[IDX_TICK_VOLUME]),
            "volume": int(fields[IDX_VOLUME]),
            "trade_amount": int(fields[IDX_TRADE_AMOUNT]),
        }
    except (ValueError, IndexError):
        return None


async def get_approval_key() -> str | None:
    """KIS WebSocket 접속키 발급 (REST API)"""
    url = "https://openapi.koreainvestment.com:9443/oauth2/Approval"
    body = {
        "grant_type": "client_credentials",
        "appkey": KIS_APP_KEY,
        "secretkey": KIS_APP_SECRET,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("approval_key")
    except Exception as e:
        logger.error(f"approval_key 발급 실패: {e}")
    return None


def build_subscribe_message(approval_key: str, tr_id: str, stock_code: str, subscribe: bool = True) -> str:
    """WebSocket 구독/해제 메시지 생성"""
    return json.dumps({
        "header": {
            "approval_key": approval_key,
            "custtype": "P",
            "tr_type": "1" if subscribe else "2",
            "content-type": "utf-8",
        },
        "body": {
            "input": {
                "tr_id": tr_id,
                "tr_key": stock_code,
            }
        }
    })


class KISWebSocketClient:
    def __init__(self, on_execution=None):
        """
        on_execution: 체결 데이터 수신 시 호출할 콜백 (async callable)
            signature: async def callback(data: dict) -> None
        """
        self._on_execution = on_execution
        self._ws = None
        self._approval_key = None
        self._subscribed_codes: set[str] = set()
        self._running = False

    async def connect(self):
        """WebSocket 연결 + 메시지 수신 루프"""
        self._running = True
        retry_count = 0
        max_retries = 5

        while self._running and retry_count < max_retries:
            # 매 연결 시 approval_key 재발급 (24시간 만료 대비)
            self._approval_key = await get_approval_key()
            if not self._approval_key:
                logger.error("approval_key 없음 — 2초 후 재시도")
                retry_count += 1
                await asyncio.sleep(2)
                continue

            try:
                async with websockets.connect(WS_URL, ping_interval=None) as ws:
                    self._ws = ws
                    retry_count = 0
                    logger.info(f"KIS WebSocket 연결 성공: {WS_URL}")

                    # 기존 구독 복원
                    for code in list(self._subscribed_codes):
                        await ws.send(build_subscribe_message(
                            self._approval_key, "H0STCNT0", code, True
                        ))

                    async for raw_msg in ws:
                        await self._handle_message(raw_msg)

            except Exception as e:
                retry_count += 1
                logger.warning(f"WebSocket 끊김 ({retry_count}/{max_retries}): {e}")
                if self._running and retry_count < max_retries:
                    await asyncio.sleep(2)

        logger.info("WebSocket 클라이언트 종료")

    async def _handle_message(self, raw_msg: str):
        """수신 메시지 분류 처리"""
        # PINGPONG 응답 — KIS는 서버가 보낸 메시지를 그대로 echo
        if "PINGPONG" in raw_msg:
            if self._ws:
                await self._ws.send(raw_msg)
            return

        # 구독 응답 (JSON)
        if raw_msg.startswith("{"):
            return

        # 체결 데이터: 암호화여부|TR_ID|건수|데이터
        parts = raw_msg.split("|", 3)
        if len(parts) < 4:
            return

        tr_id = parts[1]
        data_str = parts[3]

        if tr_id == "H0STCNT0" and self._on_execution:
            parsed = parse_stock_execution(data_str)
            if parsed:
                await self._on_execution(parsed)

    async def subscribe(self, stock_code: str):
        """종목 체결가 구독 추가"""
        self._subscribed_codes.add(stock_code)
        if self._ws and self._approval_key:
            await self._ws.send(build_subscribe_message(
                self._approval_key, "H0STCNT0", stock_code, True
            ))
            logger.info(f"구독 추가: {stock_code} (총 {len(self._subscribed_codes)}개)")

    async def unsubscribe(self, stock_code: str):
        """종목 구독 해제"""
        self._subscribed_codes.discard(stock_code)
        if self._ws and self._approval_key:
            await self._ws.send(build_subscribe_message(
                self._approval_key, "H0STCNT0", stock_code, False
            ))

    async def update_subscriptions(self, new_codes: set[str]):
        """구독 목록 전체 교체 (diff 기반)"""
        to_remove = self._subscribed_codes - new_codes
        to_add = new_codes - self._subscribed_codes
        for code in to_remove:
            await self.unsubscribe(code)
        for code in to_add:
            await self.subscribe(code)

    def stop(self):
        self._running = False

    @property
    def subscribed_count(self) -> int:
        return len(self._subscribed_codes)
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

Run: `cd /Users/sonbyeongcheol/DEV/stock_toolkit && python -m pytest daemon/tests/test_ws_client.py -v`
Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git add daemon/ws_client.py daemon/tests/test_ws_client.py
git commit -m "feat(daemon): KIS WebSocket 클라이언트 — 연결/수신/파싱/재연결"
```

---

### Task 3: 알림 판정 규칙

**Files:**
- Create: `daemon/alert_rules.py`
- Create: `daemon/tests/test_alert_rules.py`

- [ ] **Step 1: 테스트 작성**

```python
# daemon/tests/test_alert_rules.py
import pytest
from daemon.alert_rules import AlertEngine


@pytest.fixture
def engine():
    return AlertEngine(
        surge_levels=[5.0, 10.0, 15.0],
        drop_levels=[-3.0, -5.0],
        volume_ratio=3.0,
        cooldown_sec=300,
    )


# === 급등 ===
def test_surge_5pct(engine):
    alerts = engine.check({"code": "005930", "price": 105000, "change_rate": 5.5, "volume": 1000})
    types = [a["type"] for a in alerts]
    assert "surge_5" in types


def test_surge_15pct(engine):
    alerts = engine.check({"code": "005930", "price": 115000, "change_rate": 15.5, "volume": 1000})
    types = [a["type"] for a in alerts]
    assert "surge_5" in types
    assert "surge_10" in types
    assert "surge_15" in types


def test_no_surge_below_threshold(engine):
    alerts = engine.check({"code": "005930", "price": 100000, "change_rate": 3.0, "volume": 1000})
    surge_alerts = [a for a in alerts if a["type"].startswith("surge")]
    assert len(surge_alerts) == 0


# === 급락 ===
def test_drop_3pct(engine):
    alerts = engine.check({"code": "005930", "price": 97000, "change_rate": -3.5, "volume": 1000})
    types = [a["type"] for a in alerts]
    assert "drop_3" in types


def test_drop_5pct(engine):
    alerts = engine.check({"code": "005930", "price": 95000, "change_rate": -5.5, "volume": 1000})
    types = [a["type"] for a in alerts]
    assert "drop_3" in types
    assert "drop_5" in types


# === 거래량 폭증 ===
def test_volume_surge(engine):
    # 5분 윈도우에 평균 100 → 현재 체결 후 평균 400
    for _ in range(10):
        engine.record_volume("005930", 100)
    alerts = engine.check({"code": "005930", "price": 100000, "change_rate": 0.5, "volume": 1000}, tick_volume=400)
    types = [a["type"] for a in alerts]
    assert "volume_surge" in types


def test_no_volume_surge_below_ratio(engine):
    for _ in range(10):
        engine.record_volume("005930", 100)
    alerts = engine.check({"code": "005930", "price": 100000, "change_rate": 0.5, "volume": 1000}, tick_volume=200)
    volume_alerts = [a for a in alerts if a["type"] == "volume_surge"]
    assert len(volume_alerts) == 0


# === 쿨다운 ===
def test_cooldown_prevents_duplicate(engine):
    alerts1 = engine.check({"code": "005930", "price": 105000, "change_rate": 5.5, "volume": 1000})
    assert len(alerts1) > 0
    alerts2 = engine.check({"code": "005930", "price": 106000, "change_rate": 6.0, "volume": 1000})
    surge5 = [a for a in alerts2 if a["type"] == "surge_5"]
    assert len(surge5) == 0  # 쿨다운 중이므로 재알림 없음


# === 목표가 ===
def test_target_price_reached(engine):
    engine.set_target("005930", 70000)
    alerts = engine.check({"code": "005930", "price": 70500, "change_rate": 2.0, "volume": 1000})
    types = [a["type"] for a in alerts]
    assert "target_reached" in types


def test_target_price_not_reached(engine):
    engine.set_target("005930", 70000)
    alerts = engine.check({"code": "005930", "price": 69000, "change_rate": 1.0, "volume": 1000})
    target_alerts = [a for a in alerts if a["type"] == "target_reached"]
    assert len(target_alerts) == 0
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `cd /Users/sonbyeongcheol/DEV/stock_toolkit && python -m pytest daemon/tests/test_alert_rules.py -v`
Expected: FAIL

- [ ] **Step 3: alert_rules.py 구현**

```python
"""알림 판정 엔진 — 급등/급락/거래량/목표가"""
import time
from collections import deque


class AlertEngine:
    def __init__(self, surge_levels: list[float], drop_levels: list[float],
                 volume_ratio: float, cooldown_sec: int):
        self._surge_levels = sorted(surge_levels)
        self._drop_levels = sorted(drop_levels, reverse=True)  # -3, -5 순
        self._volume_ratio = volume_ratio
        self._cooldown_sec = cooldown_sec
        # 쿨다운: {(code, alert_type): last_alert_time}
        self._cooldowns: dict[tuple[str, str], float] = {}
        # 거래량 윈도우: {code: deque of (timestamp, tick_volume)}
        self._volume_window: dict[str, deque] = {}
        # 목표가: {code: target_price}
        self._targets: dict[str, float] = {}

    def check(self, data: dict, tick_volume: int | None = None) -> list[dict]:
        """체결 데이터에 대해 모든 알림 규칙 검사. 발생한 알림 리스트 반환."""
        code = data["code"]
        change_rate = data["change_rate"]
        price = data["price"]
        alerts = []

        # 급등 단계별
        for level in self._surge_levels:
            if change_rate >= level:
                alert_type = f"surge_{int(level)}"
                if self._can_alert(code, alert_type):
                    alerts.append({
                        "type": alert_type,
                        "code": code,
                        "price": price,
                        "change_rate": change_rate,
                        "level": level,
                    })
                    self._mark_alerted(code, alert_type)

        # 급락 단계별
        for level in self._drop_levels:
            if change_rate <= level:
                alert_type = f"drop_{abs(int(level))}"
                if self._can_alert(code, alert_type):
                    alerts.append({
                        "type": alert_type,
                        "code": code,
                        "price": price,
                        "change_rate": change_rate,
                        "level": level,
                    })
                    self._mark_alerted(code, alert_type)

        # 거래량 폭증
        if tick_volume is not None:
            self.record_volume(code, tick_volume)
            avg = self._avg_volume(code)
            if avg > 0 and tick_volume >= avg * self._volume_ratio:
                alert_type = "volume_surge"
                if self._can_alert(code, alert_type):
                    alerts.append({
                        "type": alert_type,
                        "code": code,
                        "price": price,
                        "tick_volume": tick_volume,
                        "avg_volume": round(avg, 1),
                        "ratio": round(tick_volume / avg, 1),
                    })
                    self._mark_alerted(code, alert_type)

        # 목표가 도달
        if code in self._targets:
            target = self._targets[code]
            if price >= target:
                alert_type = "target_reached"
                if self._can_alert(code, alert_type):
                    alerts.append({
                        "type": alert_type,
                        "code": code,
                        "price": price,
                        "target": target,
                    })
                    self._mark_alerted(code, alert_type)
                    del self._targets[code]  # 1회 알림 후 제거

        return alerts

    def record_volume(self, code: str, tick_volume: int):
        """거래량 윈도우에 기록 (최근 5분)"""
        now = time.time()
        if code not in self._volume_window:
            self._volume_window[code] = deque()
        window = self._volume_window[code]
        window.append((now, tick_volume))
        # 5분 초과 데이터 제거
        cutoff = now - 300
        while window and window[0][0] < cutoff:
            window.popleft()

    def set_target(self, code: str, price: float):
        self._targets[code] = price

    def remove_target(self, code: str):
        self._targets.pop(code, None)

    def _avg_volume(self, code: str) -> float:
        window = self._volume_window.get(code)
        if not window or len(window) < 2:
            return 0.0
        # 마지막 항목 제외한 평균 (현재 틱과 비교하기 위해)
        items = list(window)[:-1]
        if not items:
            return 0.0
        return sum(v for _, v in items) / len(items)

    def _can_alert(self, code: str, alert_type: str) -> bool:
        key = (code, alert_type)
        last = self._cooldowns.get(key, 0)
        return (time.time() - last) >= self._cooldown_sec

    def _mark_alerted(self, code: str, alert_type: str):
        self._cooldowns[(code, alert_type)] = time.time()
        # 오래된 쿨다운 항목 정리 (메모리 누수 방지)
        if len(self._cooldowns) > 1000:
            now = time.time()
            expired = [k for k, v in self._cooldowns.items() if now - v > self._cooldown_sec * 2]
            for k in expired:
                del self._cooldowns[k]
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

Run: `cd /Users/sonbyeongcheol/DEV/stock_toolkit && python -m pytest daemon/tests/test_alert_rules.py -v`
Expected: 10 passed

- [ ] **Step 5: 커밋**

```bash
git add daemon/alert_rules.py daemon/tests/test_alert_rules.py
git commit -m "feat(daemon): 알림 판정 엔진 — 급등/급락/거래량/목표가 + 쿨다운"
```

---

### Task 4: Telegram 알림 발송기

**Files:**
- Create: `daemon/notifier.py`
- Create: `daemon/tests/test_notifier.py`

- [ ] **Step 1: 테스트 작성**

```python
# daemon/tests/test_notifier.py
import pytest
from daemon.notifier import format_alert


def test_format_surge():
    alert = {"type": "surge_5", "code": "005930", "price": 70000, "change_rate": 5.5, "level": 5.0}
    msg = format_alert(alert, stock_name="삼성전자")
    assert "삼성전자" in msg
    assert "005930" in msg
    assert "+5.5%" in msg
    assert "급등" in msg


def test_format_drop():
    alert = {"type": "drop_3", "code": "005930", "price": 65000, "change_rate": -3.2, "level": -3.0}
    msg = format_alert(alert, stock_name="삼성전자")
    assert "급락" in msg
    assert "-3.2%" in msg


def test_format_volume_surge():
    alert = {"type": "volume_surge", "code": "005930", "price": 68000, "tick_volume": 500, "avg_volume": 100.0, "ratio": 5.0}
    msg = format_alert(alert, stock_name="삼성전자")
    assert "거래량" in msg
    assert "5.0배" in msg


def test_format_target_reached():
    alert = {"type": "target_reached", "code": "005930", "price": 71000, "target": 70000}
    msg = format_alert(alert, stock_name="삼성전자")
    assert "목표가" in msg
    assert "70,000" in msg
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `cd /Users/sonbyeongcheol/DEV/stock_toolkit && python -m pytest daemon/tests/test_notifier.py -v`
Expected: FAIL

- [ ] **Step 3: notifier.py 구현**

```python
"""Telegram 알림 발송 — 포맷팅 + 비동기 전송"""
import logging
import aiohttp
from daemon.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger("daemon.notify")

ALERT_LABELS = {
    "surge_5": ("📈 급등 +5%", "warning"),
    "surge_10": ("🔥 급등 +10%", "danger"),
    "surge_15": ("🚀 급등 +15%", "critical"),
    "drop_3": ("📉 급락 -3%", "warning"),
    "drop_5": ("💥 급락 -5%", "danger"),
    "volume_surge": ("📊 거래량 폭증", "info"),
    "target_reached": ("🎯 목표가 도달", "success"),
}


def format_alert(alert: dict, stock_name: str = "") -> str:
    """알림 딕셔너리를 Telegram HTML 메시지로 포맷"""
    alert_type = alert["type"]
    label, _ = ALERT_LABELS.get(alert_type, (alert_type, "info"))
    code = alert["code"]
    price = alert["price"]
    name_str = f"{stock_name} " if stock_name else ""

    lines = [f"<b>[ST] {label}</b>"]
    lines.append(f"<b>{name_str}({code})</b>")
    lines.append(f"현재가: {price:,}원")

    if alert_type.startswith("surge_") or alert_type.startswith("drop_"):
        rate = alert["change_rate"]
        lines.append(f"등락률: {rate:+.1f}%")
    elif alert_type == "volume_surge":
        lines.append(f"체결량: 평균 대비 {alert['ratio']}배")
    elif alert_type == "target_reached":
        lines.append(f"목표가: {alert['target']:,.0f}원")

    return "\n".join(lines)


async def send_telegram(text: str):
    """Telegram Bot API로 메시지 발송"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram 설정 누락 — 알림 미발송")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error(f"Telegram 발송 실패 ({resp.status}): {body}")
    except Exception as e:
        logger.error(f"Telegram 발송 오류: {e}")
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

Run: `cd /Users/sonbyeongcheol/DEV/stock_toolkit && python -m pytest daemon/tests/test_notifier.py -v`
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add daemon/notifier.py daemon/tests/test_notifier.py
git commit -m "feat(daemon): Telegram 알림 포맷터 + 비동기 발송"
```

---

### Task 5: 구독 종목 관리자

**Files:**
- Create: `daemon/stock_manager.py`
- Create: `daemon/tests/test_stock_manager.py`

- [ ] **Step 1: 테스트 작성**

```python
# daemon/tests/test_stock_manager.py
import pytest
from daemon.stock_manager import parse_cross_signal_codes, parse_portfolio_codes


def test_parse_cross_signal_codes():
    data = [
        {"code": "005930", "name": "삼성전자", "confidence": 0.8},
        {"code": "000660", "name": "SK하이닉스", "confidence": 0.6},
    ]
    codes = parse_cross_signal_codes(data, limit=20)
    assert codes == {"005930", "000660"}


def test_parse_cross_signal_empty():
    assert parse_cross_signal_codes([], limit=20) == set()
    assert parse_cross_signal_codes(None, limit=20) == set()


def test_parse_cross_signal_limit():
    data = [{"code": f"{i:06d}", "confidence": 0.5} for i in range(30)]
    codes = parse_cross_signal_codes(data, limit=10)
    assert len(codes) == 10


def test_parse_portfolio_codes():
    data = [
        {"code": "005930", "name": "삼성전자", "avg_price": 60000, "quantity": 10},
        {"code": "000660", "name": "SK하이닉스", "avg_price": 120000, "quantity": 5},
    ]
    codes = parse_portfolio_codes(data)
    assert codes == {"005930", "000660"}
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `cd /Users/sonbyeongcheol/DEV/stock_toolkit && python -m pytest daemon/tests/test_stock_manager.py -v`
Expected: FAIL

- [ ] **Step 3: stock_manager.py 구현**

```python
"""구독 종목 관리 — GitHub Pages JSON 폴링 + 수동 종목"""
import logging
import aiohttp
from daemon.config import DATA_BASE_URL

logger = logging.getLogger("daemon.stocks")

# 종목명 캐시: {code: name}
stock_names: dict[str, str] = {}


def parse_cross_signal_codes(data: list | None, limit: int = 20) -> set[str]:
    """cross_signal.json에서 매수 시그널 종목 코드 추출"""
    if not data:
        return set()
    codes = set()
    for item in data[:limit]:
        code = item.get("code")
        if code:
            codes.add(code)
            name = item.get("name", "")
            if name:
                stock_names[code] = name
    return codes


def parse_portfolio_codes(data: list | None) -> set[str]:
    """포트폴리오 보유 종목 코드 추출"""
    if not data:
        return set()
    codes = set()
    for item in data:
        code = item.get("code")
        if code:
            codes.add(code)
            name = item.get("name", "")
            if name:
                stock_names[code] = name
    return codes


async def fetch_json(url: str) -> list | dict | None:
    """HTTP GET으로 JSON 가져오기"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    return await resp.json(content_type=None)
    except Exception as e:
        logger.warning(f"JSON fetch 실패 ({url}): {e}")
    return None


async def fetch_subscription_codes(manual_codes: set[str] | None = None) -> set[str]:
    """GitHub Pages에서 cross_signal + portfolio 종목을 가져와 합산"""
    codes: set[str] = set()

    # 매수 시그널 종목
    cross_data = await fetch_json(f"{DATA_BASE_URL}/cross_signal.json")
    if isinstance(cross_data, list):
        codes |= parse_cross_signal_codes(cross_data, limit=20)

    # 포트폴리오 (portfolio.json에 holdings가 있으면)
    portfolio_data = await fetch_json(f"{DATA_BASE_URL}/portfolio.json")
    if isinstance(portfolio_data, dict):
        holdings = portfolio_data.get("holdings", [])
        codes |= parse_portfolio_codes(holdings)

    # 수동 지정 종목
    if manual_codes:
        codes |= manual_codes

    # 40개 한도
    if len(codes) > 40:
        codes = set(list(codes)[:40])
        logger.warning(f"구독 한도 40개 초과 — {len(codes)}개로 제한")

    return codes


def get_stock_name(code: str) -> str:
    return stock_names.get(code, "")
```

- [ ] **Step 4: 테스트 실행 — 통과 확인**

Run: `cd /Users/sonbyeongcheol/DEV/stock_toolkit && python -m pytest daemon/tests/test_stock_manager.py -v`
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add daemon/stock_manager.py daemon/tests/test_stock_manager.py
git commit -m "feat(daemon): 구독 종목 관리자 — cross_signal/portfolio 파싱 + 40개 한도"
```

---

### Task 6: 메인 엔트리포인트

**Files:**
- Create: `daemon/main.py`

- [ ] **Step 1: main.py 구현**

```python
"""WebSocket 알림 데몬 — 엔트리포인트"""
import asyncio
import logging
import signal
from daemon.config import (
    ALERT_SURGE_LEVELS, ALERT_DROP_LEVELS,
    ALERT_VOLUME_RATIO, ALERT_COOLDOWN_SEC,
)
from daemon.ws_client import KISWebSocketClient
from daemon.alert_rules import AlertEngine
from daemon.notifier import format_alert, send_telegram
from daemon.stock_manager import fetch_subscription_codes, get_stock_name

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("daemon.main")

# 전역 상태
alert_engine = AlertEngine(
    surge_levels=ALERT_SURGE_LEVELS,
    drop_levels=ALERT_DROP_LEVELS,
    volume_ratio=ALERT_VOLUME_RATIO,
    cooldown_sec=ALERT_COOLDOWN_SEC,
)
ws_client: KISWebSocketClient | None = None


async def on_execution(data: dict):
    """체결 데이터 수신 콜백 — 알림 규칙 검사 + 발송"""
    alerts = alert_engine.check(data, tick_volume=data.get("tick_volume"))
    for alert in alerts:
        name = get_stock_name(alert["code"])
        msg = format_alert(alert, stock_name=name)
        logger.info(f"알림 발송: {alert['type']} {alert['code']}")
        await send_telegram(msg)


async def refresh_subscriptions():
    """구독 종목 갱신 (GitHub Pages 폴링)"""
    if not ws_client:
        return
    codes = await fetch_subscription_codes()
    if codes:
        await ws_client.update_subscriptions(codes)
        logger.info(f"구독 갱신 완료: {len(codes)}종목")


async def schedule_refresh():
    """10분마다 구독 종목 갱신"""
    while True:
        await asyncio.sleep(600)
        try:
            await refresh_subscriptions()
        except Exception as e:
            logger.error(f"구독 갱신 실패: {e}")


async def main():
    global ws_client

    logger.info("WebSocket 알림 데몬 시작")

    # 초기 구독 종목 로드
    codes = await fetch_subscription_codes()
    logger.info(f"초기 구독 종목: {len(codes)}개")

    # WebSocket 클라이언트 생성
    ws_client = KISWebSocketClient(on_execution=on_execution)
    for code in codes:
        ws_client._subscribed_codes.add(code)

    # 종료 핸들러
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, ws_client.stop)

    # 동시 실행: WebSocket + 종목 갱신 스케줄러
    await asyncio.gather(
        ws_client.connect(),
        schedule_refresh(),
    )

    logger.info("WebSocket 알림 데몬 종료")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: 로컬 드라이런 확인**

Run: `cd /Users/sonbyeongcheol/DEV/stock_toolkit && python -m daemon.main --help 2>&1 || echo "드라이런 완료"`
Expected: 환경변수 없이 시작 시도 → approval_key 실패 로그 → 정상 종료 (크래시 없음 확인)

- [ ] **Step 3: 전체 테스트 실행**

Run: `cd /Users/sonbyeongcheol/DEV/stock_toolkit && python -m pytest daemon/tests/ -v`
Expected: 21 passed (ws_client 3 + alert_rules 10 + notifier 4 + stock_manager 4)

- [ ] **Step 4: 커밋**

```bash
git add daemon/main.py
git commit -m "feat(daemon): 메인 엔트리포인트 — WebSocket + 알림 + 종목 갱신 통합"
```

---

### Task 7: GCP 배포 설정

**Files:**
- Create: `daemon/Dockerfile`
- Create: `daemon/README.md` (운영 가이드)

- [ ] **Step 1: Dockerfile 작성**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "daemon.main"]
```

- [ ] **Step 2: 최종 전체 테스트**

Run: `cd /Users/sonbyeongcheol/DEV/stock_toolkit && python -m pytest daemon/tests/ -v && python -m pytest tests/ -v`
Expected: daemon 테스트 21건 + 기존 테스트 55건 전부 PASS (기존 테스트 영향 없음 확인)

- [ ] **Step 3: 커밋**

```bash
git add daemon/Dockerfile
git commit -m "feat(daemon): Dockerfile + GCP 배포 준비"
```
