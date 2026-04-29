---
name: query-trades
description: Supabase의 auto_trades + strategy_simulations DB를 직접 조회하여 오늘/특정일/누적 매매·시뮬 성과를 산출. Use when 사용자가 "오늘 모의투자/시뮬 성과", "특정 종목 추적", "전략별 누적 성과", "DB로 검증" 등을 요청할 때.
allowed-tools: Bash(python3 *), Read
---

# Query Trades (Supabase DB 직접 조회)

stock_toolkit의 auto_trades(실전+sim_only) + strategy_simulations(7전략)를 KST 기준으로 정확히 분리해서 조회한다.

## 환경 준비
- Working dir: `/Users/sonbyeongcheol/DEV/stock_toolkit`
- 인증: `daemon/.env`의 `SUPABASE_URL` + `SUPABASE_SECRET_KEY`
- 의존: `python-dotenv`, urllib

## 표준 조회 템플릿

```python
import os, json, urllib.request
from collections import defaultdict, Counter
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta

load_dotenv('daemon/.env')
URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SECRET_KEY")
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
KST = timezone(timedelta(hours=9))
today = datetime.now(KST).strftime("%Y-%m-%d")
```

## 자주 쓰는 쿼리

### 1. 오늘 created auto_trades (KST 기준)
```python
q = f"created_at=gte.{today}T00:00:00%2B09:00&created_at=lt.{today}T23:59:59%2B09:00&order=created_at.asc"
req = urllib.request.Request(f"{URL}/rest/v1/auto_trades?{q}", headers=HEADERS)
with urllib.request.urlopen(req, timeout=10) as r:
    today_trades = json.loads(r.read())
```

### 2. 오늘 sold (실전 청산)
```python
q = f"sold_at=gte.{today}T00:00:00%2B09:00&sold_at=lt.{today}T23:59:59%2B09:00&status=eq.sold"
```

### 3. 모든 strategy_simulations (페이지네이션)
```python
all_sims = []
offset = 0
while True:
    req = urllib.request.Request(f"{URL}/rest/v1/strategy_simulations?order=created_at.asc&limit=1000&offset={offset}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        page = json.loads(r.read())
    if not page: break
    all_sims.extend(page)
    if len(page) < 1000: break
    offset += 1000
```

### 4. trade_id → 종목명 매핑
```python
ids_str = ",".join(f'"{i}"' for i in trade_ids[:50])
req = urllib.request.Request(f"{URL}/rest/v1/auto_trades?id=in.({ids_str})&select=id,code,name", headers=HEADERS)
```

## 보고 시 분리 원칙 (필수 — 메모리 lessons)

오늘 청산을 단순 합산하면 misleading. **반드시 분리**:

1. **오늘 매수 + 오늘 청산** ← 오늘의 시그널 결과 (실질)
2. **이전 매수 + 오늘 청산** ← 장기 보유분 만기/trailing 청산
3. **현재 OPEN** ← 미실현 손익 **산정 금지** (peak 사용 금지 원칙)

## OPEN 포지션 보고 규칙
- entry_price만 표시. **peak_price로 미실현 PnL 계산 금지** (메모리 26번)
- "보유 중" 명시
- 현재가 API 접근이 가능하면 현재가 기준으로만 미실현 산정

## 알려진 함정
- 모의투자 inquire-nccs 미지원(404) → 시장가 즉시체결 간주
- gapup_sim은 `auto_trades.status=sim_only` + `sell_reason=gapup_sim`로만 기록 (strategy_simulations 미사용)
- DB timestamp는 UTC 저장 → KST 변환 시 +9h
- alert_config의 `emergency_sl` 컬럼은 레거시 (커밋 245e8a6 이후 미사용)

## 보고 형식
- 실전 청산: 표(종목/매수/매도/PnL/사유) + 매수금/손익금/평균
- 시뮬: 그룹별(오늘 매수+오늘청산 / 이전매수+오늘청산) 평균/승패
- 누적: 전략별 closed/open/win%/avg/sum
- OPEN: entry만 (미실현 PnL 미산정)
