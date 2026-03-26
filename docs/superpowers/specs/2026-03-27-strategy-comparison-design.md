# 전략 비교 모의투자 설계

## 개요
모의투자 화면에 Stepped Trailing / 고정 7% 익절 두 전략 중 선택 가능. 선택한 전략으로 실제 매매, 비선택 전략은 가상 시뮬레이션으로 병행하여 누적 성과 비교.

## DB 변경

### alert_config — 컬럼 추가
```sql
ALTER TABLE alert_config ADD COLUMN strategy_type TEXT DEFAULT 'fixed';
-- 값: 'fixed' (고정 TP) | 'stepped' (Stepped Trailing)
```

### strategy_simulations — 신규 테이블
```sql
CREATE TABLE strategy_simulations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  trade_id UUID REFERENCES auto_trades(id) ON DELETE CASCADE,
  strategy_type TEXT NOT NULL,
  entry_price INTEGER NOT NULL,
  exit_price INTEGER,
  exit_reason TEXT,
  pnl_pct NUMERIC,
  status TEXT DEFAULT 'open',
  peak_price INTEGER,
  stepped_stop INTEGER,
  created_at TIMESTAMPTZ DEFAULT now(),
  exited_at TIMESTAMPTZ,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE
);

ALTER TABLE strategy_simulations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users read own" ON strategy_simulations FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Service insert" ON strategy_simulations FOR INSERT WITH CHECK (true);
CREATE POLICY "Service update" ON strategy_simulations FOR UPDATE USING (true);
```

## Daemon 변경

### trader.py — 전략별 매도 분기

`check_positions_for_sell()`에서:

```
if strategy_type == "fixed":
    현행 로직 그대로 (고정 TP, SL -2%, trailing -3%)

elif strategy_type == "stepped":
    SL -2% 유지
    고정 TP 제거
    stepped_stop 계산:
      pnl >= +25% → stop = peak - 3%
      pnl >= +20% → stop = +15%
      pnl >= +15% → stop = +10%
      pnl >= +10% → stop = +5%
      pnl >= +5%  → stop = 0% (breakeven)
      pnl < +5%   → stop = -2% (기본 SL)
    current_price <= stepped_stop_price이면 매도
```

### trader.py — 가상 시뮬레이션 기록

`place_buy_order_with_qty()` 성공 시:
1. 실제 거래 기록 (auto_trades — 기존)
2. 비선택 전략의 가상 포지션 생성 (strategy_simulations)

`check_positions_for_sell()` 호출 시:
1. 실제 포지션 체크 (기존)
2. open 상태의 가상 포지션도 체크하여 가상 매도 조건 충족 시 업데이트

### stock_manager.py — fetch_alert_config 확장

`strategy_type` 컬럼 추가 조회. 기본값 'fixed'.

## Frontend 변경

### AutoTrader.tsx — 전략 선택 UI (최상단)

```
[투자 전략]
● Stepped Trailing    ○ 고정 7% 익절
📋 전략 비교 성과 ▶ (접힘, 클릭 시 펼침)
```

### 전략별 설정 연동

- Stepped 선택 시: 익절 입력 비활성화, "Stepped Trailing 적용 중" + step 구간 표시, 손절(-2%)만 편집 가능
- 고정 7% 선택 시: 기존 UI 그대로 (익절/손절/급락 편집)

### 전략 비교 펼침 UI

- 두 전략의 누적 수익률 비교 카드
- 날짜별 상세 비교 리스트 (최신순)
- 데이터 소스: strategy_simulations + auto_trades 조인

### supabase.ts — 함수 추가

- `setStrategyType(type)` — alert_config.strategy_type 업데이트
- `getStrategySimulations()` — 비교 데이터 조회
- `getStrategyComparison()` — 날짜별 실제 vs 가상 성과 집계

## Stepped Trailing 파라미터 (고정값)

| 도달 수익 | Stop 위치 |
|----------|----------|
| +5% | 0% (본전) |
| +10% | +5% |
| +15% | +10% |
| +20% | +15% |
| +25%+ | peak - 3% |
| +5% 미만 | -2% (고정 SL) |
