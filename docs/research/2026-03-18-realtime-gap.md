# 실시간 데이터 격차 분석 및 장중 활용 방안 연구

> 2026-03-18 — stock_toolkit이 시장보다 ~1일 뒤처지는 원인 분석 및 개선 방안
> **2차 연구 반영** (2026-03-18): 1차 누락 사항 5건 추가, 파일별 갱신 분류, Intraday Overlay 전략 추가
> **3차 연구 반영** (2026-03-18): 실측 데이터 검증 (놓친 급등 85.7%, 수급 반전 0% 반영, overlay 유효성 100%)
> **4차 연구 반영** (2026-03-18): 엣지케이스/리스크, 대체 접근법 5종, signal-pulse KIS-only 분리 실행 가능성
> **5차 연구 반영** (2026-03-18): UX 영향도, 미활용 데이터 8건 추가, 솔루션 통합 검증
> **6차 연구 반영** (2026-03-18): 이전 연구 오류 정정, 미해결 질문 4건 해결, 최종 확정
> **7차 연구 반영** (2026-03-18): 블라인드스팟 10건, 구현 리스크 4건, GitHub Pages fetch 최적화, signal-pulse→stock_toolkit 자동 트리거
> **8차 연구 반영** (2026-03-18): 최종 전략 평가 — 8가지 중 3가지만 실행, 5가지 폐기, ~135줄로 확정
> **9차 연구 반영** (2026-03-18): Devil's Advocate — 08:00 cron이 핵심 해결, 3가지 솔루션은 "필수→선택적"으로 하향
> **10차 연구 반영** (2026-03-18): 9차 오류 정정 — 08:00 cron은 신호 0% 개선 (국내 데이터는 전일 그대로), Overlay/Decay 다시 "필수"로 상향

---

## 1. 현재 데이터 지연 구조

### 1.1 핵심 병목: signal-pulse 하루 2회 실행

| 실행 시점 (KST) | 데이터 기준 | stock_toolkit 반영 시점 |
|:---:|---|:---:|
| **07:00** | 전일 장마감 데이터 기반 분석 | 08:00 (다음 배포) |
| **19:00** | 당일 장마감 데이터 기반 분석 | 19:30 (다음 배포) |

- `combined_analysis.json` (vision_signal, api_signal, confidence) = **장중 0회 업데이트**
- **12시간 갭**: 07:00 분석 → 19:00까지 동일 데이터 유지
- cross_signal, smart_money, risk_monitor 등 핵심 섹션이 모두 signal-pulse 의존

### 1.2 데이터 소스별 갱신 빈도

| 데이터 | 소스 | 장중 갱신 | stock_toolkit 활용 |
|---|---|:---:|:---:|
| 등락률/거래량/거래대금 TOP | theme-analyzer latest.json | **7회/일** | ✅ 사용 |
| 외국인/기관 수급 (종목별) | investor-intraday.json | **5회/일** | ⚠️ 히트맵만 |
| 30분/60분 봉 OHLCV | intraday-history.json | **7회/일** | ⚠️ 패턴만 |
| KOSPI/KOSDAQ 지수 | latest.json | **7회/일** | ✅ 사용 |
| 환율/선물/VIX | macro-indicators.json | **7회/일** | ✅ 사용 |
| 매물대 Volume Profile | volume-profile.json | **1회/일** (11:30) | ✅ 사용 |
| **종목 신호 (매수/매도)** | **combined_analysis.json** | **0회/일** ❌ | **핵심 의존** |
| **AI 재료분석** | **combined_analysis.json** | **0회/일** ❌ | **핵심 의존** |

### 1.3 사용자 체감 지연

**예시: 오전 10시에 대시보드를 볼 때**

| 섹션 | 데이터 시점 | 지연 |
|---|---|---|
| 프리마켓 (선물/환율) | 오늘 09:31 | 30분 |
| 시장 현황 (지수/투자자동향) | 오늘 09:31 | 30분 |
| **AI 주목 종목** | **어제 19:00** | **15시간** |
| **크로스 시그널** | **어제 19:00 신호 + 오늘 09:05 테마** | **혼합** |
| **리스크 모니터** | **어제 19:00** | **15시간** |
| 갭 분석 / 등락률 | 오늘 09:05 | 1시간 |
| 장중 수급 히트맵 | 오늘 09:31 | 30분 |

**→ 핵심 투자 판단 섹션(신호/리스크)이 ~15시간 전 데이터**

---

## 2. theme-analyzer 장중 실시간 데이터 상세

### 2.1 장중 수집 타임라인

```
07:00  ─── macro-premarket (선물/환율/매크로)
07:30  ─── theme-forecast (AI 테마 예측)
09:05  ─── daily-theme-analysis (전체 수집 1차 + AI 테마)
09:28  ─── daily-theme-analysis (전체 수집 2차)
09:30  ─── intraday-history (30분봉)
09:31  ─── investor-data (수급 + 랭킹)
10:00  ─── intraday-history + theme-forecast-intraday
10:01  ─── investor-data
11:00  ─── intraday-history
11:30  ─── refresh-data (종합 갱신, AI 없이)
11:31  ─── investor-data
12:00  ─── intraday-history
13:00  ─── intraday-history + theme-forecast-intraday
13:21  ─── investor-data
14:00  ─── intraday-history
14:31  ─── investor-data
15:00  ─── intraday-history
15:40  ─── paper-trading
15:45  ─── investor-data (장마감 확정)
18:05  ─── investor-data (pykrx 검증)
```

### 2.2 장중에 변하는 핵심 데이터

**① investor-intraday.json — 종목별 실시간 수급 (5회/일)**
```json
snapshots[].data["003280"] = {
  "f": -175363,   // 외국인 순매수 (주)
  "i": 733705,    // 기관 순매수 (주)
  "pg": -214665,  // 프로그램 순매수 (주)
  "cp": 3520,     // 현재가
  "cr": 2.15      // 등락률 (%)
}
```
- 150~160종목, 5시점
- **외국인/기관 수급 방향 전환을 실시간 포착 가능**

**② latest.json — 등락률/거래량/거래대금 TOP (7회/일)**
```
rising[kospi/kosdaq]     → 상승률 TOP 10
falling[kospi/kosdaq]    → 하락률 TOP 10
volume[kospi/kosdaq]     → 거래량 TOP 30
trading_value[kospi/kosdaq] → 거래대금 TOP 30
fluctuation_direct       → 연속 상승/하락일수
investor_data            → 종목별 수급 확정치
kospi_index / kosdaq_index → 지수 현재값
```

**③ intraday-history.json — 554종목 30분봉 (7회/일)**
```json
stocks["002140"][].intervals_30m = [
  { time: "09:30", close: 2830, high: 3040, low: 2740, volume: 2256889 },
  { time: "10:00", close: 2790, ... },
  ...
]
```

**④ volume-profile.json — 장중 매물대 (today 필드)**
```json
profiles["003280"].today = {
  poc_price: 3553,      // 당일 최대 거래량 가격대
  poc_volume: 44532138,
  bins: [{ price: 2951, volume: 4850577 }, ...]
}
```

---

## 3. signal-pulse 추가 실행 가능성 분석

### 3.1 현재 제약

| 제약 요소 | 현황 | 영향 |
|---|---|---|
| KIS API 토큰 | 1일 1회 발급, 24시간 유효, Supabase 캐시 | 2회까지 안전, 3회 이상 위험 |
| Gemini API | 5개 키, RPM 제한, 429 시 최대 5분 쿨다운 | 처리 시간 40~80분 |
| 처리 시간 | Vision + KIS 병렬 실행 40~80분 | 1시간 미만 배치 소요 |
| 데이터 신뢰도 | 아침(07:00) confidence 0.49, 저녁(19:00) 0.69 | 장중 데이터 신뢰도 불확실 |

### 3.2 추가 실행 가능 시점

```
가능 ✅ 하루 3회: 07:00, 13:00(장중), 19:00
        - KIS 토큰 캐시 범위 내
        - Gemini 일일 한도 내
        - 장중 13:00 실행 시 5시간분 장중 데이터 반영

불확실 ⚠️ 하루 4회: 07:00, 11:00, 15:30, 19:00
        - KIS 토큰 재발급 위험
        - Gemini 일일 한도 근접

불가 ❌ 매시간 실행
        - Gemini 429 에러 빈발
        - 처리 시간(40~80분) > 실행 간격(60분)
```

---

## 4. 제안: signal-pulse 없이 장중 실시간 분석

### 핵심 아이디어

signal-pulse의 AI 신호(vision_signal)를 기다리지 않고, **theme-analyzer의 장중 데이터만으로 독립적인 장중 분석**을 생성한다.

### 4.1 방안 A: 장중 수급 반전 감지 (즉시 구현 가능)

**데이터:** investor-intraday.json (5회/일, 150+종목)

**로직:**
```
각 스냅샷 간 외국인 순매수 변화 추적:
- 09:31 → 10:01: 외국인 -50만주 → +30만주 = "매수 전환" 🔴
- 10:01 → 11:31: 외국인 +30만주 → +80만주 = "매수 가속" 🔴🔴
- 11:31 → 13:21: 외국인 +80만주 → +20만주 = "매수 둔화" ⚠️
```

**출력:** 장중 수급 반전 종목 실시간 리스트
- 현재 `intraday_stock_tracker.json`으로 이미 기본 구현되어 있음
- **개선 필요:** 시점 간 변화 추세(가속/둔화/반전)를 명시적으로 계산

**가치:** 외국인/기관 수급 전환은 단기 매매의 핵심 지표

### 4.2 방안 B: 장중 모멘텀 스코어 (즉시 구현 가능)

**데이터:** latest.json (등락률/거래량 7회/일) + investor-intraday.json

**로직:**
```
종목별 장중 모멘텀 점수 =
  등락률 가중치(40%) + 거래량 변화율(20%) + 외국인 순매수 방향(20%) + 기관 순매수 방향(20%)

점수 > 70: "장중 강세"
점수 < 30: "장중 약세"
이전 배포 대비 점수 변화 > 20: "모멘텀 전환"
```

**출력:** 새 JSON `intraday_momentum.json`
```json
[
  {
    "code": "090710", "name": "휴림로봇",
    "momentum_score": 85,
    "prev_score": 60,
    "change": "+25 (모멘텀 가속)",
    "factors": {
      "change_rate": 15.3,
      "volume_surge": 230,
      "foreign_flow": "매수전환",
      "institution_flow": "매수유지"
    }
  }
]
```

**가치:** signal-pulse 신호 없이도 장중 강세/약세 종목 실시간 파악

### 4.3 방안 C: 장중 테마 온도 변화 (즉시 구현 가능)

**데이터:** latest.json의 theme_analysis + rising/volume 데이터

**로직:**
```
테마별 대장주들의 장중 평균 등락률 변화:
- 09:05 AI/반도체 대장주 평균 +2.3%
- 11:30 AI/반도체 대장주 평균 +5.1% → "테마 가열 중" 🔥
- 14:00 AI/반도체 대장주 평균 +3.2% → "테마 냉각" ❄️
```

**출력:** `theme_temperature.json`
```json
[
  {
    "theme": "AI/반도체",
    "current_avg_change": 5.1,
    "prev_avg_change": 2.3,
    "trend": "가열",
    "leaders": [
      { "name": "SK하이닉스", "change": 3.2, "prev": 1.5 },
      { "name": "삼성전자", "change": 1.8, "prev": 0.8 }
    ]
  }
]
```

**가치:** 테마 모멘텀의 장중 변화를 실시간 추적

### 4.4 방안 D: 30분봉 패턴 실시간 경보 (중기 구현)

**데이터:** intraday-history.json (554종목, 30분봉 7회/일)

**로직:**
```
554종목의 30분봉 패턴 실시간 감시:
- 거래량 3배 급증 + 양봉 = "돌파 시도"
- 3연속 음봉 + 거래량 감소 = "하락 추세"
- POC 가격 돌파 (volume-profile) = "매물대 돌파"
```

**출력:** `intraday_alerts.json`
```json
[
  {
    "code": "090710", "name": "휴림로봇",
    "alert_type": "volume_breakout",
    "description": "10:00~10:30 거래량 320% 급증 + 양봉",
    "price": 14500, "time": "10:30"
  }
]
```

**가치:** 실시간 기술적 이벤트 감지 (signal-pulse 완전 독립)

### 4.5 방안 E: signal-pulse 장중 1회 추가 실행 (signal-pulse 변경 필요)

**변경 대상:** signal-pulse의 cron-job.org 스케줄

**현재:** 07:00, 19:00 (2회)
**변경:** 07:00, **13:00**, 19:00 (3회)

**효과:**
- 장중 13:00에 최신 시장 데이터 기반으로 신호 재분석
- 07:00 대비 6시간분 장중 데이터 반영
- cross_signal, smart_money, risk_monitor 6시간 단축

**제약:**
- KIS 토큰 캐시 범위 내 (24시간 유효, Supabase 캐시)
- Gemini API 일일 한도 내 (5키 × RPM)
- 처리 시간 40~80분 → 13:00 시작, 14:00~14:20 완료 예상

---

## 5. 구현 우선순위

### Tier 1: 즉시 구현 가능 (stock_toolkit만 수정)

| # | 방안 | 데이터 소스 | 효과 | 난이도 |
|---|---|---|---|:---:|
| 1 | **장중 수급 반전 감지 강화** (A) | investor-intraday.json | 외국인/기관 수급 전환 실시간 포착 | 낮음 |
| 2 | **장중 모멘텀 스코어** (B) | latest.json + investor-intraday | signal-pulse 없이 장중 강세/약세 판별 | 중간 |
| 3 | **장중 테마 온도 변화** (C) | latest.json theme_analysis | 테마 가열/냉각 실시간 추적 | 낮음 |

### Tier 2: 중기 구현 (stock_toolkit 수정)

| # | 방안 | 데이터 소스 | 효과 | 난이도 |
|---|---|---|---|:---:|
| 4 | **30분봉 패턴 경보** (D) | intraday-history.json | 기술적 이벤트 실시간 감지 | 중간 |
| 5 | **매물대 돌파/이탈 실시간 감지** | volume-profile.json (today) | 지지/저항 돌파 경보 | 중간 |

### Tier 3: signal-pulse 변경 필요

| # | 방안 | 변경 대상 | 효과 | 난이도 |
|---|---|---|---|:---:|
| 6 | **signal-pulse 장중 1회 추가** (E) | cron-job.org 스케줄 | AI 신호 6시간 단축 | 낮음 |

---

## 6. 기대 효과 요약

| 지표 | 현재 | Tier 1 완료 후 | Tier 1+2 완료 후 | 전체 완료 후 |
|---|:---:|:---:|:---:|:---:|
| AI 신호 지연 | ~15시간 | ~15시간 (불변) | ~15시간 | **~6시간** |
| 수급 반전 감지 | 없음 | **30분 내** | **30분 내** | **30분 내** |
| 장중 모멘텀 | 없음 | **30분 내** | **30분 내** | **30분 내** |
| 테마 온도 변화 | 없음 | **30분 내** | **30분 내** | **30분 내** |
| 기술적 경보 | 없음 | 없음 | **30분 내** | **30분 내** |
| 매물대 경보 | 없음 | 없음 | **30분 내** | **30분 내** |
| 체감 실시간성 | 약 1일 지연 | **장중 데이터 반영** | **장중 경보 가능** | **종합 실시간** |

### 핵심 결론

**signal-pulse의 AI 신호(vision_signal)는 장중 갱신이 불가능하지만, theme-analyzer의 장중 데이터(수급 5회, 랭킹 7회, 30분봉 7회)를 독립적으로 분석하면 "장중 실시간 보조 지표"를 생성할 수 있다.**

Tier 1만으로도 수급 반전, 모멘텀 변화, 테마 온도를 30분 이내로 반영하여 **체감 실시간성을 크게 개선**할 수 있으며, AI 신호 자체의 지연은 signal-pulse 장중 추가 실행(Tier 3)으로 해결 가능하다.

---

## 7. 2차 연구: 1차에서 놓친 핵심 발견사항

### 7.1 출력 파일 46개의 갱신 분류 (실측 기반)

**매 30분 배포 시 46개 파일 중 실제 변경되는 비율:**

| 분류 | 파일 수 | 비율 | 갱신 드라이버 |
|---|:---:|:---:|---|
| **Tier 1**: 매 30분 변경 | 9개 | 20% | latest.json + investor-intraday |
| **Tier 2**: 2x/day만 변경 | 12개 | 26% | signal-pulse combined_analysis |
| **Tier 3**: 5x/day 변경 | 4개 | 9% | investor-intraday 스냅샷 |
| **Tier 4**: 정적/일일 | ~21개 | 45% | hardcoded 또는 일일 1회 |

**→ 매 30분 배포 중 실질적으로 변하는 파일은 ~48% (Tier 1+3)**

#### Tier 1 상세 (매 30분, latest.json 기반)

| 파일 | 변경 드라이버 |
|---|---|
| gap_analysis.json | rising_stocks의 change_rate |
| volume_divergence.json | volume_rate vs change_rate |
| lifecycle.json | 테마별 평균 등락률 |
| sector_flow.json | 외국인 순매수 합산 |
| intraday_stock_flow.json | investor-intraday 마지막 스냅샷 |
| intraday_stock_tracker.json | 수급 시점 간 변화 추적 |
| intraday_heatmap.json | 시간대별 프로그램매매 |
| sentiment.json | F&G, VIX, 지수 |
| premarket.json | 선물/환율/매크로 |

#### Tier 2 상세 (2x/day, signal-pulse 의존)

| 파일 | signal-pulse 의존 필드 | 실시간 가능 필드 |
|---|---|---|
| cross_signal.json | vision_signal, api_signal | ❌ 없음 |
| smart_money.json | vision_signal, confidence | foreign_net (실시간) |
| risk_monitor.json | vision_signal, RSI | foreign_net (실시간) |
| scanner_stocks.json | vision_signal, api_signal | criteria_data (부분 실시간) |
| news_impact.json | vision_news | ❌ 없음 |
| pattern.json | kis_gemini RSI | 30분봉 (실시간) |
| signal_consistency.json | 5일 신호 히스토리 | ❌ 없음 |
| simulation.json | signal_history | ❌ 없음 |
| simulation_history.json | simulation_index | ❌ 없음 |
| short_squeeze.json | criteria_data | foreign_net (실시간) |
| valuation.json | kis_gemini PER/PBR | fundamental_data (부분) |
| portfolio.json | vision_signal | foreign_net (실시간) |

### 7.2 1차 연구 누락 사항 5건

| # | 누락 사항 | 1차 연구 | 2차 발견 |
|---|---|---|---|
| 1 | **criteria_data 대체 한계** | "대체 가능" | boolean 필터만 → 신호 강도(적극매수/매수) 구분 불가 |
| 2 | **Tier 2 파일의 혼합 구조** | 미분석 | 신호는 stale하지만 foreign_net 등은 실시간 갱신 → "Intraday Overlay" 전략 필요 |
| 3 | **fundamental_data 갱신 불확실** | 미언급 | PER은 주가 연동이지만, theme-analyzer에서 장중 재계산하는지 미확인 |
| 4 | **46개 파일 분류** | "대부분 갱신" 추측 | 실측: 48%만 의미있게 변경 |
| 5 | **criteria_data의 golden_cross 구조** | 단순 boolean | 실제로 7개 하위 지표 (ema_5_20, macd, stochastic, rsi, bollinger, dmi, obv) 포함 → 점수화 가능 |

### 7.3 핵심 전략: Intraday Overlay

**문제:** Tier 2 파일(cross_signal, smart_money 등)의 AI 신호는 2x/day이지만, 주변 데이터는 매 30분 갱신됨

**해결: 신호는 캐시하되, 장중 실시간 데이터를 "오버레이"로 추가**

#### 현재 smart_money.json 구조:
```json
{
  "code": "000660", "name": "SK하이닉스",
  "signal": "매수",              ← 07:00 고정 (stale)
  "foreign_net": 212397,         ← 실시간 (latest.json)
  "smart_money_score": 99        ← 신호 기반 점수 (stale)
}
```

#### 개선안 — Intraday Overlay 추가:
```json
{
  "code": "000660", "name": "SK하이닉스",
  "signal": "매수",
  "signal_age_hours": 5,                    ← 신호 경과 시간
  "foreign_net": 212397,
  "smart_money_score": 99,
  "intraday": {                             ← 장중 실시간 오버레이
    "current_change_rate": 3.2,             ← latest.json rising/volume
    "current_volume_rate": 245,             ← latest.json
    "foreign_flow_direction": "매수가속",    ← investor-intraday 시점 간 비교
    "momentum_30m": 2.1,                    ← intraday-history 최근 봉
    "criteria_met": 6,                      ← criteria_data all_met 수
    "intraday_score": 78                    ← 장중 독립 점수 (신호 없이 계산)
  }
}
```

**intraday_score 계산식 (signal-pulse 비의존):**
```
기본 50점
+ 등락률 > 5%        → +15
+ 거래량비 > 200%     → +10
+ 외국인 순매수 > 0   → +10
+ 기관 순매수 > 0     → +5
+ 외국인 매수 가속    → +10 (이전 스냅샷 대비 증가)
+ criteria_data 충족 3개+ → +10
+ golden_cross.met   → +5
```

**효과:** 07:00 AI 신호 "매수"가 유효한지를 장중 데이터로 **실시간 검증/보강**

### 7.4 cross_signal.json Intraday Overlay

#### 현재:
```json
{
  "name": "휴림로봇", "vision_signal": "매수",
  "dual_signal": "고확신", "confidence": 0.81
}
```

#### 개선안:
```json
{
  "name": "휴림로봇", "vision_signal": "매수",
  "dual_signal": "고확신", "confidence": 0.81,
  "signal_timestamp": "2026-03-18 07:00",
  "intraday": {
    "current_price": 14500,
    "change_rate": 18.56,
    "volume_rate": 352,
    "foreign_buying": true,
    "institution_selling": true,
    "momentum": "상승가속",
    "validation": "신호 유효"    ← 장중 데이터가 AI 신호를 뒷받침하는지
  }
}
```

**validation 판정 로직:**
```
AI 신호 = "매수" + 장중 등락률 > 0 + 외국인 순매수 → "신호 유효" ✅
AI 신호 = "매수" + 장중 등락률 < -3% + 외국인 순매도 → "신호 약화" ⚠️
AI 신호 = "매수" + 장중 등락률 < -5% → "신호 무효화" ❌
```

### 7.5 theme-analyzer criteria_data의 프록시 신호 가능성

**golden_cross 상세 구조 (7개 하위 지표):**
```json
"golden_cross": {
  "met": true,
  "signals": {
    "ema_5_20": true,
    "macd": true,
    "stochastic": false,
    "rsi": true,
    "bollinger": false,
    "dmi": true,
    "obv": true
  },
  "count": 5,
  "reason": "7개 중 5개 골든크로스 신호"
}
```

**프록시 신호 점수화:**
```
golden_cross 5/7 충족 = +25점
ma_alignment.met = +15점
supply_demand.met = +10점
high_breakout.met = +10점
momentum_history.met = +10점
overheating.met = -15점 (과열 경고)
reverse_alignment.met = -20점 (역배열)
short_selling.met = -10점
```

→ 합산 점수 > 40: "기술적 매수 신호"
→ 합산 점수 < -10: "기술적 매도 신호"

**이 점수는 AI 없이도 theme-analyzer 데이터만으로 매 30분 재계산 가능**

### 7.6 장중 급등/급락 실시간 감지 (1차 미포함)

**latest.json에서 즉시 추출 가능:**
```
등락률 > 15% AND 거래량비 > 200% → "급등 경보"
등락률 < -10% AND 거래량비 > 300% → "급락 경보"
```

**2차 조사에서 실측한 현재 데이터 (2026-03-17):**

| 종목 | 등락률 | 거래량비 | 상태 |
|---|---|---|---|
| 신성이엔지 | +29.91% | 1434% | 급등 |
| 휴림에이텍 | +30.00% | 352% | 급등 |
| 해성옵틱스 | +28.74% | 709% | 급등 |
| 와이제이링크 | +22.88% | 2332% | 급등 |
| 비엘팜텍 | +22.54% | 273% | 급등 |

**→ 5종목이 장중 급등 기준 충족, AI 신호 없이도 즉시 감지 가능**

---

## 8. 수정된 구현 우선순위 (2차 연구 반영)

### Tier 1: 즉시 구현 — Intraday Overlay (가장 효과적)

| # | 방안 | 대상 파일 | 효과 |
|---|---|---|---|
| **1** | **cross_signal/smart_money에 intraday 오버레이 추가** | cross_signal.json, smart_money.json | AI 신호 유효성을 장중 데이터로 실시간 검증 |
| **2** | **장중 급등/급락 경보** | 신규 intraday_alerts.json | AI 없이 등락률+거래량으로 즉시 감지 |
| **3** | **criteria_data 점수화** | scanner_stocks.json 보강 | golden_cross 7개 하위지표 → 기술적 프록시 신호 |

### Tier 2: 장중 독립 분석

| # | 방안 | 대상 파일 | 효과 |
|---|---|---|---|
| 4 | 장중 모멘텀 스코어 (방안 B) | 신규 intraday_momentum.json | signal-pulse 비의존 강세/약세 판별 |
| 5 | 장중 테마 온도 (방안 C) | 신규 theme_temperature.json | 테마 가열/냉각 추적 |
| 6 | 장중 수급 반전 강화 (방안 A) | intraday_stock_tracker.json 개선 | 시점 간 가속/둔화/반전 명시 |

### Tier 3: signal-pulse 변경

| # | 방안 | 효과 |
|---|---|---|
| 7 | signal-pulse 13:00 추가 실행 | AI 신호 지연 15시간 → 6시간 |

### 핵심 변경: Intraday Overlay가 가장 효과적인 이유

1차 연구는 "새로운 독립 분석 파일 추가"에 집중했으나, 2차 연구 결과 **기존 핵심 파일(cross_signal, smart_money)에 장중 데이터를 오버레이**하는 것이 가장 효과적:

- 사용자가 이미 보는 섹션에서 바로 실시간 정보 제공
- 새 섹션 추가 없이 기존 UI에 자연스럽게 통합
- "신호는 아침 기준이지만, 현재 시장이 뒷받침하고 있는지" 즉시 확인 가능
- AI 신호 + 장중 검증 = 신뢰도 향상

---

## 9. 3차 연구: 실측 데이터 기반 검증

### 9.1 Intraday Overlay 유효성 검증 (실제 cross_signal 종목)

**검증 방법:** 현재 cross_signal 4종목의 AI 신호(07:00 기준)가 장중 실제 데이터와 일치하는지 확인

| 종목 | AI 신호 | 등락률 | 외국인 | 거래량비 | 검증 결과 |
|---|---|---|---|---|---|
| 휴림로봇 | 매수 (0.66) | +12.37% | +212,397 | 1033% | ✅ 신호 유효 — 강화 |
| 아주IB투자 | 매수 (0.70) | +18.17% | +87,968 | 217% | ✅ 신호 유효 |
| 보성파워텍 | 매수 (0.65) | +4.71% | +1,014,931 | — | ✅ 신호 유효 — 외국인 강매수 |
| HD현대에너지솔루션 | KIS매수 (0.64) | +5.53% | — | 604x | ✅ 신호 유효 |

**결론:** 4/4 종목 모두 장중 데이터가 AI 신호를 뒷받침. **Overlay 전략은 실제 데이터에서 유효.**

### 9.2 놓친 기회 정량화 (핵심 발견)

**테스트:** 당일 15% 이상 급등한 종목 중 AI 신호가 "매수"가 아닌 종목

| 종목 | 등락률 | 거래량비 | AI 신호 | 상태 |
|---|---|---|---|---|
| 와이제이링크 | **+30.00%** | 2332% | **중립** | ❌ 놓침 |
| 휴림에이텍 | **+30.00%** | 352% | **중립** | ❌ 놓침 |
| 신성이엔지 | **+29.91%** | 1434% | **매도** | ❌ 놓침 |
| 해성옵틱스 | **+28.56%** | 709% | **중립** | ❌ 놓침 |
| 비엘팜텍 | +20.57% | — | 매수 | ✅ 포착 |
| 아이엘 | **+15.37%** | — | **중립** | ❌ 놓침 |
| 서울전자통신 | **+15.14%** | — | **중립** | ❌ 놓침 |

**놓친 비율: 6/7 = 85.7%**

**특히 신성이엔지(+29.91%):** criteria_data에서 golden_cross✅, ma_alignment✅, supply_demand✅, high_breakout✅ 모두 충족했으나 AI 신호는 "매도" → **criteria 프록시가 AI보다 정확했던 사례**

### 9.3 외국인 수급 반전 감지 (investor-intraday 실측)

**당일 수급 반전이 발생한 종목: 8건**

| 종목 | 반전 내용 | 등락률 | cross_signal 포함 |
|---|---|---|---|
| 006490 | 매수→매도 (-185만주) | -26.50% | ❌ 미포함 |
| 017040 | 매수→매도 (-65만주) | -20.44% | ❌ 미포함 |
| 003280 흥아해운 | 매수→매도 (-137만주) | +13.01% | ❌ 미포함 |
| 외 5종목 | — | — | ❌ 미포함 |

**→ 수급 반전 8건 중 0건이 현재 시그널 시스템에 반영됨**

### 9.4 Vision vs KIS 신호 불일치 검증

| 종목 | Vision | KIS | 실제 등락률 | 정답 |
|---|---|---|---|---|
| 아주IB투자 | **매수** | 중립 | +18.17% | **Vision 정답** |
| 보성파워텍 | **매수** | 중립 | +4.71% | **Vision 정답** |
| HD현대에너지솔루션 | 중립 | **매수** | +5.53% (604x vol) | **KIS 정답** |

**→ Vision이 2/3, KIS가 1/3 정답. 양쪽 통합이 단독보다 유효함을 실증**

### 9.5 AI 신호 경과 시간 (Staleness) 실측

**combined_analysis.json 생성 시각:** 2026-03-18 00:11 KST

| 시점 (KST) | 신호 경과 시간 | 시장 상태 |
|---|---|---|
| 09:00 장 시작 | **8시간 49분** | 오전 모멘텀 서지 시작 |
| 11:00 오전 | **10시간 49분** | 추세 확인 구간 |
| 13:00 점심 | **12시간 49분** | 오후 반전 가능 구간 |
| 15:30 장 마감 | **15시간 19분** | 마감 직전 |

**→ 장 시작 시점에 이미 9시간 전 데이터. 오전 모멘텀 서지(거래량 2~3배)를 놓침.**

### 9.6 구현 타당성 검증

**run_all.py에서 Intraday Overlay 삽입 지점:**

| 항목 | 검증 결과 |
|---|---|
| 삽입 위치 | Phase 2 (line 180) — anomalies 이후, cross_signal 재가공 |
| 필요 데이터 | investor_data ✅ (line 147), rising_stocks ✅ (line 142), cross_matches ✅ (line 43) |
| 추가 데이터 로딩 | **불필요** — 모든 데이터 이미 로드됨 |
| 코드 변경량 | run_all.py ~50줄 + Dashboard.tsx ~20줄 |
| 성능 영향 | 무시 가능 (4종목 × dict lookup) |
| 기존 코드 영향 | 없음 (기존 필드 유지, 새 필드 추가만) |

### 9.7 criteria_data 프록시 점수 상관관계

**검증:** 제안된 점수 공식 vs 실제 confidence

| 종목 | 프록시 점수 | AI confidence | 상관 |
|---|---|---|---|
| 삼성전자우 | 15 | 0.69 | ❌ 불일치 |
| 삼성전기 | 25 | 0.67 | ⚠️ 약한 일치 |
| 신성이엔지 | 40 | 0.24 | ❌ 심각 불일치 |

**상관률: ~40% — 약함**

**원인:** 프록시 점수는 기술적 필터만, AI confidence는 뉴스/수급/재료 종합 판단
**결론:** criteria 프록시는 AI 대체가 아닌 **보조 지표**로만 활용. 다만 신성이엔지 사례처럼 **AI가 틀리고 criteria가 맞는 경우도 존재** → 상호 보완 관계

---

## 10. 3차 연구 종합 결론

### 실측으로 확인된 사실

| 항목 | 수치 |
|---|---|
| AI 신호 경과 시간 (장 시작 시) | **8시간 49분** |
| 15%+ 급등 종목 포착률 | **14.3%** (7개 중 1개만 포착) |
| 수급 반전 종목 시그널 반영률 | **0%** (8건 중 0건) |
| Intraday Overlay 유효성 | **100%** (4/4 종목 장중 데이터가 신호 뒷받침) |
| criteria 프록시-AI 상관률 | **~40%** (보조 지표로만 유효) |
| 구현 코드 변경량 | **~70줄** (run_all.py 50줄 + Dashboard.tsx 20줄) |

### 최종 구현 권고

**1순위 (즉시):** Intraday Overlay — cross_signal/smart_money에 장중 실시간 필드 추가
- 실측 유효성 100% 확인
- 코드 변경 ~70줄, 추가 데이터 로딩 불필요
- 놓친 85.7%의 급등 종목을 "장중 급등 경보"로 보완

**2순위 (단기):** 장중 급등/급락 경보 신설
- 등락률 >15% + 거래량비 >200% 자동 감지
- 현재 6/7 급등 종목을 놓치고 있음 → 즉시 포착

**3순위 (중기):** signal-pulse 13:00 추가 실행
- AI 신호 경과 시간 8.8시간 → 4시간으로 단축
- KIS 토큰/Gemini API 범위 내 실행 가능

---

## 11. 4차 연구: 엣지케이스·리스크·대체 접근법·KIS 분리 실행

### 11.1 엣지케이스 및 리스크

#### A. theme-analyzer 데이터 공백 검증

2026-03-17 git 커밋 로그 기준, 장중(09:00~15:30) 최대 업데이트 간격은 **~40분**.
다만 **모든 investor-intraday 스냅샷이 `is_estimated: true`** (KIS API 추정값, 공식 확정 아님).

| 리스크 | 심각도 | 대응 |
|---|---|---|
| 장중 40분 이상 데이터 공백 | 낮음 | 30분 배포 주기로 자연 보완 |
| 모든 수급 데이터가 추정값 | 중간 | UI에 "추정" 라벨 표시 권장 |
| 비거래일 빈 스냅샷 | 낮음 | 코드에서 이미 graceful fallback 처리됨 |

#### B. V자형 급락 후 회복 시 오버레이 오판

```
07:00 AI 신호: "매수"
10:00 장중: -3.0% → 오버레이 "신호 약화" 표시
14:00 장중: +4.8% → 실제로는 회복
```

**해결 방안:**
- ±2% 이내 변동은 "중립"으로 처리 (hysteresis)
- 최근 30분 추세만 반영 (전체 일중 변화가 아닌)
- 2시간 rolling 표준편차가 2% 미만이면 "변동성 정상"으로 무시

#### C. intraday_stock_tracker price=0 문제

실측 확인: 일부 종목에서 `price: 0, change_rate: 0` 발생 → Division by Zero 위험.
**→ null check 필수 (overlay 구현 시 반드시 처리)**

#### D. 데이터 타이밍 불일치

stock_toolkit 배포 시 `actions/checkout@v4`로 theme-analyzer **최신 main**을 가져오므로 캐시 문제는 없음.
다만 theme-analyzer의 마지막 커밋과 stock_toolkit 배포 사이에 **최대 30분 지연** 존재.

### 11.2 대체 접근법 분석

#### 접근법 A: 독립 기술적 신호 생성 ❌

criteria_data에 golden_cross 하위 지표(ema_5_20, macd 등 7개)가 있지만, **combined_analysis.json의 api_data에는 세부 기술적 지표가 포함되지 않음**. 개별 종목의 RSI, MACD 등을 직접 계산하려면 별도 데이터 수집 필요.

**실행 가능성: 낮음** — 데이터 확보 후에만 가능

#### 접근법 B: 연속 배포 간 Delta 분석 ⚠️

현재 deploy-pages.yml에서 briefing.json만 이전 버전 보존. 다른 JSON은 매 배포 시 전체 덮어쓰기.

**구현 시 필요 작업:**
```yaml
# deploy-pages.yml에 추가
- name: Backup previous data
  run: |
    curl -sf "$PAGES_URL/data/cross_signal.json" -o /tmp/prev_cross.json || true
    curl -sf "$PAGES_URL/data/smart_money.json" -o /tmp/prev_smart.json || true
```
이전 데이터와 비교하여 "외국인 매수 가속/둔화" 등 변화 신호 생성 가능.

**실행 가능성: 중간** — 워크플로우 + run_all.py 소폭 수정 필요

#### 접근법 C: forecast-history 장중 예측 변화 추적 ✅ (신규 발견)

**핵심 발견:** forecast-history에 이미 **하루 3회 예측(07:35, 10:02, 13:02)**이 저장되어 있으나 완전 미활용.

2026-03-17 실측 비교:

| 시점 | AI/반도체 리더 | 변화 |
|---|---|---|
| 07:35 | SK하이닉스(1위), 삼성전자(2위), 나무기술(3위) | 초기 예측 |
| 10:02 | 삼성전자(1위), SK하이닉스(2위), HPSP(3위) | **리더주 순위 변경** |
| 13:02 | 삼성전자(1위), SK하이닉스(2위), HPSP(3위) + **로봇 테마 신규 부상** | **신규 테마 발굴** |

**활용 방안:**
- 시점 간 leader_stocks 비교 → "리더주 재평가" 신호
- 신규 부상 테마 탐지: `13:02 테마 - 10:02 테마`
- 테마 안정성 지표: 3회 예측에서 일관되면 "안정", 변동되면 "유동적"

**실행 가능성: 높음, 구현 난이도: 낮음**

#### 접근법 D: 신뢰도 Decay 모델 ✅

현재 신호에 생성 시각 정보가 없어 "경과 시간"을 알 수 없음.

**구현:**
```
effective_confidence = original_confidence × 0.95^(hours_elapsed)
예: 07:00 신뢰도 0.85 → 10:00 = 0.85 × 0.95³ = 0.73
```

cross_signal.json과 performance.json에 `generated_at` 필드 추가 후, 프론트엔드에서 decay 적용.

**실행 가능성: 높음, 구현 난이도: 매우 낮음**

#### 접근법 E: WebSocket / 실시간 폴링 ❌

GitHub Pages는 정적 호스팅 → WebSocket 불가. Supabase Real-time 미설정.
프론트엔드에서 setInterval 폴링은 가능하나, 배포 주기(30분)보다 자주 폴링해도 데이터 불변.

**실행 가능성: 낮음** — 아키텍처 변경 필요

### 11.3 signal-pulse KIS-only 분리 실행 (핵심 발견)

#### 현재 아키텍처

analyze.yml에 이미 `skip_vision`/`skip_kis` 플래그가 존재하며, **Vision과 KIS 분석이 완전 독립**.

| 실행 유형 | 소요 시간 | Gemini 호출 | 포함 내용 |
|---|---|---|---|
| Full (Vision + KIS) | **~120분** | ~20회 | 차트 분석 + API 분석 |
| **KIS-only** | **~20분** | ~2회 | API 분석 + criteria 평가 |
| Vision-only | ~40분 | ~10회 | 차트/뉴스 분석 |

#### KIS 토큰 제약 확인 (실제 코드 검증)

**kis_client.py line 181-183:**
```python
return time_since_issue.total_seconds() >= 23 * 3600
```
- KIS API가 **하루 1회 토큰 발급**을 강제 (자체 제한 아님)
- 단, 발급된 토큰은 **24시간 유효** → 같은 토큰으로 여러 번 실행 가능
- GitHub Actions에서 **날짜별 캐시** (line 248)로 당일 재사용

#### Gemini API 여유 확인

- 현재 일일 사용: ~220K 토큰 (용량의 2.2%)
- KIS-only 6회 추가: ~576K 토큰 (5.76%)
- **45배 여유 공간** → 제약 없음

#### 제안: KIS-Fast 스케줄

```
07:00  Full (Vision + KIS)     ← 기존 유지
09:00  KIS-only (top 20)       ← 신규 (장 시작 직후)
11:00  KIS-only (top 20)       ← 신규
13:00  KIS-only (top 20)       ← 신규 (장중)
15:30  KIS-only (top 20)       ← 신규 (장 마감)
19:00  Full (Vision + KIS)     ← 기존 유지
```

**효과:**
- AI 신호 갱신: 2회/일 → **6회/일**
- 최대 신호 경과 시간: 15시간 → **2시간**
- 추가 비용: Gemini 토큰 ~576K (여유 범위)
- KIS 토큰: 추가 발급 불필요 (당일 캐시 재사용)

**트레이드오프:**
- KIS-only는 top 20 종목만 분석 (Full의 100종목 대비)
- Vision 차트 분석 없음 → 기술적 패턴 인식 약화
- 하지만 criteria_data(규칙 기반)는 포함되므로 기본 필터 유지

---

## 12. 최종 종합 구현 권고 (4차 연구 반영)

### 즉시 구현 (stock_toolkit만 수정)

| 순위 | 방안 | 난이도 | 효과 |
|:---:|---|:---:|---|
| **1** | **Intraday Overlay** — cross_signal/smart_money에 장중 데이터 추가 | 낮음 (~70줄) | 기존 AI 신호의 현재 유효성 실시간 검증 |
| **2** | **신뢰도 Decay** — 신호 경과 시간에 따라 confidence 감소 | 매우 낮음 (~20줄) | 사용자에게 신호 신선도 투명 공개 |
| **3** | **forecast-history 활용** — 3시점 예측 변화 추적 | 낮음 (~40줄) | 장중 테마/리더주 재평가 포착 |
| **4** | **장중 급등 경보** — 등락률 >15% + 거래량 >200% 자동 감지 | 낮음 (~30줄) | 놓친 85.7% 급등 종목 보완 |

### 중기 구현 (signal-pulse 변경)

| 순위 | 방안 | 난이도 | 효과 |
|:---:|---|:---:|---|
| **5** | **KIS-only 분리 실행 4회 추가** | 중간 | AI 신호 갱신 2→6회/일, 최대 경과 2시간 |
| **6** | **Delta 분석** — 이전 배포 데이터와 비교 | 중간 | 수급 가속/둔화 트렌드 감지 |

### 장기 계획

| 순위 | 방안 | 난이도 | 효과 |
|:---:|---|:---:|---|
| **7** | Supabase Real-time 마이그레이션 | 높음 | 실시간 데이터 푸시 |
| **8** | 독립 기술적 신호 생성 (RSI/MACD 자체 계산) | 높음 | signal-pulse 완전 독립 |

---

## 13. 5차 연구: UX 영향도·미활용 데이터 감사·솔루션 통합 검증

### 13.1 UX 영향도 — 사용자가 실제로 겪는 문제

#### 데이터 신선도 표시 현황

**현재 타임스탬프 렌더링 (SectionHeader):**
```
폰트: text-[10px] (극히 작음)
색상: t-text-dim (흐린 색상)
위치: 섹션 헤더 우측 끝
```

**39개 섹션 중 데이터 신선도 설명이 있는 섹션: 1개 (장중 종목별 수급만)**
나머지 38개 섹션: 신선도 언급 없음.

#### 사용자 의사결정 위험 시나리오

**시나리오 1: 추격매수 위험**
```
09:00  AI 신호 생성: "삼성전자 적극매수"
14:00  투자자 페이지 로드 → 같은 "적극매수" 표시
       → 7시간 전 신호임을 모르고 매수 → 장중 약세로 손실
```

**시나리오 2: 위험 모니터링 실패**
```
09:15  "SK하이닉스 위험 주의"
12:00  새로운 악재 → 급락 10%
15:00  대시보드: 여전히 "주의" → 사용자 "아직 괜찮네" 판단 → 손실 확대
```

#### 한국 증권사 MTS 대비 부재 사항

| 기능 | 증권사 MTS | stock_toolkit |
|---|---|---|
| 실시간/지연 데이터 표시 | ✅ "실시간" / "15분 지연" | ❌ 없음 |
| 자동 갱신 | ✅ 5~10초 주기 | ❌ 없음 (수동만) |
| "최근 갱신" 배너 | ✅ 항상 표시 | ❌ 없음 |
| 신호 나이 표시 | ✅ "5분 전" | ❌ 없음 |

### 13.2 미활용 실시간 데이터 감사 (신규 발견 8건)

#### 발견 1: KOSPI/KOSDAQ MA 추세 신호 — 표시만 하고 분석 안 함

```
KOSPI 현재: 5702.39
  > MA5 (5586.54) ✅ 단기 상승
  < MA20 (5686.87) → 가까움
  > MA60 (5026.09) ✅ 장기 상승
```
현재: kospi_index를 performance.json에 넣지만 **MA 대비 위치 분석 없음**
활용: "지수 단기 상승 추세" / "MA20 저항 접근" 등 자동 판정 가능

#### 발견 2: program_net (종목별 프로그램매매) — 완전 미사용

```
152/155 종목에 program_net 필드 존재
예: 흥아해운 program_net: 190,713 (프로그램 순매수)
```
현재: foreign_net, institution_net, individual_net만 사용, **program_net 무시**

#### 발견 3: investor_data 10일 히스토리 — 완전 미사용

```
각 종목 10일 rolling history 존재
예: 흥아해운 foreign_net 10일 전 -290,781 → 현재 +256,317 (누적 +547,098 전환)
```
현재: 당일 foreign_net만 사용, **추세 분석 없음**

#### 발견 4: program_trade 11개 투자자 유형 — 합산만 사용

```
금융투자: +117,390 (매수)   외국인: -655,197 (매도)
```
현재: 11개 유형을 하나로 합산. **투자자 유형별 분석 없음**

#### 발견 5: 시장 breadth (investor-intraday) — 미사용

```
09:31: 151종목 중 92종목 외국인 순매수 (60.9%)
14:31: 157종목 중 76종목 외국인 순매수 (48.4%)
→ 장중 12.5%p 악화 (외국인 이탈 진행)
```
현재: 합산 수치만 사용, **breadth 비율 미계산**

#### 발견 6: paper-trading 8시점 가격 스냅샷 — 완전 미사용

```
AI 선정 종목의 장중 8시점(09:22~14:32) 가격 추적 데이터 존재
예: 나무기술 — 09:22 7,280원 → 09:50 7,595원(+4.3%) → 14:32 7,220원(-0.8%)
```
현재: stocks(매매결과)와 summary만 사용, **price_snapshots 필드 무시**

#### 발견 7: member_data 증권사 매수/매도 편중 — 미분석

```
48종목에 buy_top5/sell_top5 존재
특정 증권사 집중도(concentration) 분석 가능
```
현재: member_trading.json에 단순 복사만, **편중도 분석 없음**

#### 발견 8: consecutive_up_days / consecutive_down_days — 미추출

```
fluctuation_direct에 연속 상승/하락일수 필드 존재
```
현재: consecutive_monitor.json 생성 로직은 있으나, **실측 결과 데이터가 대부분 0** (추출 로직 검증 필요)

### 13.3 솔루션 통합 검증 — 4개 동시 구현 시

**충돌 여부: ❌ 없음** — 각 솔루션이 직교하는 데이터 소스 사용

| 솔루션 | 데이터 소스 | 출력 | 간섭 |
|---|---|---|---|
| Intraday Overlay | latest.json + investor-intraday | cross_signal/smart_money 필드 추가 | 없음 |
| 신뢰도 Decay | generated_at 타임스탬프 | 프론트엔드 계산 | 없음 |
| Forecast 추적 | forecast-history/*.json | 신규 JSON 또는 기존 lifecycle | 없음 |
| 장중 급등 경보 | latest.json rising/volume | 신규 JSON | 없음 |

**단독 80% 해결 가능 솔루션: 없음** — 4개 조합 시 70~80% 효과

**Decay 공식 수정 권고:**
```
기존 제안: 0.95^hours (8.5시간 후 -34%, 너무 급격)
수정 제안: 0.98^hours (8.5시간 후 -15%, 더 완만)
```

### 13.4 필수 UX 개선 사항 (Intraday Overlay 구현 시)

| # | 개선 | 현재 | 개선안 |
|---|---|---|---|
| 1 | **타임스탬프 가시성** | text-[10px] t-text-dim | text-xs + 색상 강조 |
| 2 | **신호 나이 표시** | 없음 | "5시간 전 분석" 뱃지 |
| 3 | **자동 갱신** | 수동만 | 장중 5분 / 장외 30분 폴링 |
| 4 | **"최근 갱신" 배너** | 없음 | 헤더 하단 고정 |
| 5 | **경고 배너** | 없음 | 신호 3시간+ 경과 시 "갱신 필요" 표시 |
| 6 | **HelpDialog 보강** | 1/39 섹션만 신선도 설명 | 핵심 섹션에 데이터 출처/시점 설명 추가 |

### 13.5 최종 구현 체크리스트

```
[ ] Intraday Overlay: run_all.py ~70줄 추가 (Phase 2)
[ ] Decay 모델: generated_at 추가 + 프론트 계산 ~25줄
[ ] Forecast 비교: get_forecast_history() 활용 ~40줄
[ ] 장중 급등 경보: latest.json 필터링 ~30줄
[ ] UX: 타임스탬프 가시성 개선 ~10줄
[ ] UX: 신호 나이 뱃지 ~15줄
[ ] UX: 자동 갱신 setInterval ~20줄
[ ] hysteresis 로직: ±2% 무시 ~10줄
[ ] price=0 null check ~5줄
[ ] is_estimated 라벨 표시 ~5줄
────────────────────────────────
총 ~250줄 추가, 기존 코드 수정 최소
```

---

## 14. 6차 연구: 이전 연구 검증·오류 정정·최종 확정

### 14.1 이전 연구 주장 검증 결과

| 주장 | 출처 | 검증 결과 | 정정 |
|---|---|---|---|
| "15%+ 급등 85.7% 놓침" | 3차 | **73.3%로 정정** (15종목 중 11종목 미포착) | 비율 하향 수정, 심각성은 유지 |
| "forecast-history 하루 3회 생성" | 4차 | **✅ 확인** (25파일, 일별 3회: 07:35/10:02/13:02) | 정확함 |
| "consecutive_monitor 데이터 0" | 5차 | **코드 정상** — 연속 3일+ 충족 종목이 현재 없음 | 버그 아님, 정상 동작 |
| "fundamental_data 장중 재계산" | 5차 | **미재계산 확인** — 일일 1회 갱신 (per/pbr/eps/bps 고정값) | 장중 활용 제한적 |
| "Decay 0.95^h vs 0.98^h" | 5차 | **0.98^h 확정** — 8.5시간 후 -16% (0.95는 -45%로 과도) | 0.98 채택 |
| "intraday-history가 Phase 2에서 로드됨" | 4차 | **❌ 미로드** — line 393(Phase 3)에서 최초 로드 | Overlay 삽입 시 추가 로딩 필요 |
| "KIS 토큰 하루 재사용 가능" | 4차 | **✅ 확인** — 23시간 유효, 6회/일 실행 가능 | 정확함 |

### 14.2 삽입 지점 데이터 가용성 정정

**Phase 2 (line ~180) 시점에서:**

| 데이터 | 가용 여부 | 로드 위치 |
|---|---|---|
| investor_data | ✅ | line 147 |
| rising_stocks | ✅ | line 142 |
| volume_stocks | ✅ | line 143 |
| cross_matches | ✅ | line 43 |
| combined (signal-pulse) | ✅ | line 65 |
| **intraday-history** | **❌ 미로드** | line 393 (Phase 3) |
| **investor-intraday** | **❌ 미로드** | line 842 (Phase 6) |

**정정:** Intraday Overlay 구현 시 Phase 2에서 추가 로딩 필요:
```python
intraday_raw = loader.get_intraday_history()  # 추가 필요
intraday_inv = loader.get_investor_intraday()  # 추가 필요
```

### 14.3 무효화된 제안

| 제안 | 무효화 이유 |
|---|---|
| "criteria_data로 AI 신호 대체" (2차) | 3차에서 상관률 ~40% 확인 → 보조 지표로만 유효 |
| "fundamental_data 장중 활용" (2차) | 6차에서 일일 1회 갱신 확인 → 장중 변화 없음 |
| "모든 데이터 이미 로드" (4차) | 6차에서 intraday-history/investor-intraday 미로드 확인 |

### 14.4 최종 확정 구현 계획 (NO AMBIGUITY)

#### 단일 최고 효과 변경 (30분 이내)

**Intraday Overlay on cross_signal.json + smart_money.json**

```
파일: scripts/run_all.py

변경 1: Phase 1 (line 49) 이후에 cross_signal 저장을 DEFER
변경 2: Phase 2 (line ~180) 에서:
  a) intraday-history 로드 추가
  b) investor-intraday 로드 추가
  c) cross_matches 각 종목에 오버레이 필드 추가:
     - current_change_rate (rising_stocks에서 매칭)
     - current_volume_rate (volume_stocks에서 매칭)
     - foreign_net (investor_data에서)
     - signal_age_hours (현재 KST - combined_analysis generated_at)
     - intraday_score (등락률+거래량+수급 복합 점수)
     - validation ("신호 유효"/"신호 약화"/"신호 무효화")
  d) smart_money도 동일 오버레이 추가
  e) 오버레이 완료 후 cross_signal.json, smart_money.json 저장

변경 3: 프론트엔드 Dashboard.tsx
  - cross_signal 섹션: intraday_score, validation 뱃지 표시
  - smart_money 섹션: 동일
  - 신호 나이 표시: "N시간 전 분석" 텍스트
```

#### Tier 1 전체 구현 (2~3시간)

| 순위 | 방안 | 파일 | 줄 수 | 의존성 |
|:---:|---|---|:---:|---|
| **1** | Intraday Overlay | run_all.py + Dashboard.tsx | ~80줄 | 없음 |
| **2** | 신뢰도 Decay (0.98^h) | run_all.py (generated_at 추가) + Dashboard.tsx | ~25줄 | Overlay와 동시 |
| **3** | 장중 급등 경보 | run_all.py | ~30줄 | 없음 |
| **4** | Forecast-history 추적 | run_all.py | ~40줄 | 없음 |

**총 ~175줄, 이전 추정 250줄에서 하향 조정 (중복 제거)**

### 14.5 Decay 공식 최종 확정

```
공식: effective_confidence = confidence × 0.98^(hours_elapsed)

적용 예 (07:00 생성, confidence = 0.85):
  09:00 (+2h):  0.85 × 0.96 = 0.82 (-3.5%)   → 거의 유지
  11:00 (+4h):  0.85 × 0.92 = 0.78 (-8.2%)    → 소폭 감소
  13:00 (+6h):  0.85 × 0.89 = 0.75 (-11.8%)   → 약간 감소
  15:30 (+8.5h): 0.85 × 0.84 = 0.72 (-15.3%)  → 적절한 감소
  19:00 (+12h): 0.85 × 0.78 = 0.67 (-21.2%)   → 의미있는 감소
```

**평가:** 장 마감(+8.5h)까지 -15% 감소 → 사용자에게 "아직 참고 가능하지만 주의 필요" 수준. 적절함.

### 14.6 6차 연구로 최종 확정된 사실

```
✅ 급등 미포착률: 73.3% (15종목 중 11종목)
✅ signal-pulse: 하루 정확히 2회 (UTC 10:00, 22:00 = KST 19:00, 07:00)
✅ stock_toolkit 배포: 대체로 30분 간격 (일부 60분 갭 존재)
✅ forecast-history: 하루 3회 확인 (07:35, 10:02, 13:02)
✅ consecutive_monitor: 코드 정상, 현재 해당 종목 없음
✅ fundamental_data: 일일 1회 갱신, 장중 변화 없음
✅ Decay 공식: 0.98^h 확정
✅ KIS 토큰: 23시간 유효, 6회/일 실행 가능
✅ Overlay 삽입 시 intraday-history/investor-intraday 추가 로딩 필요
✅ 총 구현량: ~175줄 (이전 250줄에서 하향 수정)
```

---

## 15. 7차 연구: 블라인드스팟·구현 리스크·신규 발견

### 15.1 이전 6차까지 놓친 블라인드스팟 (주요 10건)

| # | 블라인드스팟 | 영향도 | 발견 |
|---|---|---|---|
| 1 | **GitHub Pages에서 curl로 데이터 가져오기 가능** — briefing.json에 이미 적용, theme-analyzer/signal-pulse에는 미적용 | 높음 | git checkout 대신 HTTP fetch로 배포 시간 20~30% 단축 가능 |
| 2 | **deploy-pages.yml에 concurrency 제어 없음** — 동시 배포 시 Pages 충돌 가능 | 높음 | `concurrency: group` 설정 필수 |
| 3 | **briefing.json만 보존, 다른 AI 출력 유실** — data-only 모드에서 cross_signal/smart_money 등 이전 결과 덮어쓰기 | 중간 | API 실패 시 이전 데이터 소실 |
| 4 | **빈 data/로 배포 성공** — `cp results/*.json ... \|\| true`로 분석 전체 실패해도 배포됨 | 중간 | 빈 대시보드 노출 위험 |
| 5 | **30분마다 데이터 변경 여부 무관하게 전체 빌드+배포** — 불필요한 Actions 분 소모 | 낮음 | 데이터 변경 체크 추가 가능 |
| 6 | **RefreshButtons 다중 클릭 시 병렬 job 실행** — 중복 방지 없음 | 낮음 | debounce 또는 disabled 처리 필요 |
| 7 | **cron-job.org job ID 하드코딩** — 변경 시 프론트 무효화 | 낮음 | 환경변수 또는 설정 파일 분리 |
| 8 | **cross-repo 의존성 검증 없음** — theme-analyzer 구조 변경 시 silent fail | 중간 | 필수 파일 존재 체크 추가 |
| 9 | **git checkout 중 race condition** — theme-analyzer mid-push 시 partial JSON 가능 | 중간 | JSON 파싱 유효성 검사 추가 |
| 10 | **signal-pulse 내부에 workflow trigger 패턴 존재** — stock_toolkit에는 미적용 | 중간 | signal-pulse 완료 → stock_toolkit 자동 트리거 가능 |

### 15.2 구현 리스크 상세

#### A. Race Condition (동시 배포)

**현재:** deploy-pages.yml에 concurrency 설정 없음
**위험:** 수동 트리거 + cron + push 트리거가 동시 발생 가능

**필수 수정:**
```yaml
# deploy-pages.yml jobs 섹션에 추가
concurrency:
  group: stock-toolkit-pages
  cancel-in-progress: true
```

#### B. 빈 데이터 배포 방지

**현재:** `cp results/*.json frontend/dist/data/ 2>/dev/null || true`
**위험:** 분석 전체 실패 시 빈 data/ 폴더로 배포

**필수 수정:**
```yaml
- name: Validate results
  run: |
    REQUIRED="performance.json cross_signal.json smart_money.json scanner_stocks.json"
    for f in $REQUIRED; do
      [ -f "results/$f" ] || { echo "❌ $f 누락"; exit 1; }
    done
```

#### C. 데이터 파일 크기 영향

| 파일 | 현재 | Overlay 추가 후 | 증가율 |
|---|---|---|---|
| cross_signal.json | 15KB | ~16KB | +8% |
| smart_money.json | 7KB | ~17KB | +143% |
| 전체 data/ | 760KB | ~770KB | +1.3% |

**모바일 영향:** gzip 후 5~7KB 추가 → 무시 가능

#### D. 프론트엔드 null 처리

Overlay 필드 추가 시, 기존 캐시된 프론트엔드는 새 필드가 undefined.
**TypeScript optional chaining (`?.`) 필수:**
```tsx
stockDetail.intraday?.current_change_rate ?? 0
stockDetail.intraday?.validation ?? "미확인"
```

### 15.3 신규 최적화 기회 (7차 고유 발견)

#### GitHub Pages HTTP Fetch 전략

**현재:** git checkout (15~30초/레포)
**대안:** curl로 Pages URL에서 직접 다운로드 (1~3초/파일)

```yaml
# 현재 (느림)
- uses: actions/checkout@v4
  with:
    repository: xxonbang/theme-analyzer
    path: theme_analysis

# 대안 (빠름) - 필요한 파일만 다운로드
- name: Fetch theme-analyzer data
  run: |
    mkdir -p theme_analysis/frontend/public/data
    BASE="https://xxonbang.github.io/theme-analyzer/data"
    for f in latest.json macro-indicators.json investor-intraday.json intraday-history.json volume-profile.json theme-forecast.json indicator-history.json; do
      curl -sf "$BASE/$f" -o "theme_analysis/frontend/public/data/$f" &
    done
    wait
```

**효과:** 7개 파일 병렬 다운로드 = 2~3초 (git checkout 30초 대비 90% 단축)
**제약:** paper-trading/, forecast-history/, history/ 디렉토리는 Pages에 포함 여부 확인 필요

#### signal-pulse 완료 → stock_toolkit 자동 트리거

signal-pulse의 analyze.yml에 이미 `gh workflow run deploy-pages.yml` 패턴이 존재.
동일 패턴으로 stock_toolkit의 deploy를 트리거 가능:

```yaml
# signal-pulse analyze.yml에 추가
- name: Trigger stock_toolkit deploy
  run: |
    gh workflow run deploy-pages.yml --repo xxonbang/stock_toolkit --field mode=data-only
  env:
    GH_TOKEN: ${{ secrets.CROSS_REPO_TOKEN }}
```

**효과:** signal-pulse 분석 완료 즉시 stock_toolkit 갱신 → 데이터 지연 최소화

### 15.4 구현 전 필수 사전 작업 (7차 기준 추가)

```
기존 체크리스트에 추가:
[ ] deploy-pages.yml concurrency 설정 추가
[ ] 필수 JSON 존재 검증 스텝 추가
[ ] Dashboard.tsx 모든 overlay 필드에 optional chaining 적용
[ ] RefreshButtons 다중 클릭 방지 (loading 상태 중 disabled)
```

---

## 16. 8차 연구: 최종 전략 평가 — 실행 결정

### 16.1 연구 복잡도 자체 평가

| 지표 | 수치 |
|---|---|
| 문서 총 줄 수 | ~1,300줄 |
| 제안된 솔루션 총 수 | 8가지 |
| 구현 전 확인 사항 | 24개 |
| 식별된 리스크 | 14건 |

**판정: 과도하게 복잡해짐.** 8가지 솔루션 중 핵심 3가지만 실행하고 나머지는 폐기.

### 16.2 최종 결정: 실행할 3가지 (나머지 전부 폐기)

| 순위 | 변경 | 코드 | 효과 | 리스크 |
|:---:|---|:---:|---|:---:|
| **1** | **Intraday Overlay** | ~80줄 | AI 신호의 현재 유효성 실시간 검증 (3차 검증 4/4 통과) | 낮음 |
| **2** | **신뢰도 Decay (0.98^h)** | ~25줄 | 신호 나이 투명 공개 (8.5시간 -15%) | 없음 |
| **3** | **장중 급등 경보** | ~30줄 | 놓친 73.3% 급등 종목 즉시 감지 | 없음 |

**합계: ~135줄. 모두 역가능(필드 제거만으로 복구).**

### 16.3 폐기하는 솔루션 5가지

| 솔루션 | 폐기 이유 |
|---|---|
| Forecast-history 추적 | lifecycle.json과 중복, 효과 불명확 |
| Delta 분석 | 이전 데이터 보존 메커니즘 없음, 구현 복잡 |
| KIS-only 분리 4회 실행 | signal-pulse 범위, Decay로 사용자 인식 충분 |
| 30분봉 패턴 경보 | 554종목 성능 이슈, 급등 경보로 부분 해결 |
| Supabase Real-time | 아키텍처 변경 필요, 수개월 소요 |

### 16.4 원래 요청에 대한 정직한 평가

**요청:** "이 프로그램은 주식시장 상황과 추세를 약 하루정도 늦게 따라가고 있음"

| 항목 | 현재 | 솔루션 후 | 근본 해결? |
|---|---|---|---|
| AI 신호 지연 | 15시간 | 여전히 15시간 | ❌ (signal-pulse 범위) |
| 사용자 체감 | "1일 늦음" | "장중 검증 + 나이 표시" | ✅ 70~80% |
| 놓친 급등 | 73.3% | 즉시 감지 | ✅ |
| 잘못된 매매 결정 | 구 신호 추격매수 | 나이+유효성 표시 | ✅ |

**AI 신호 자체(15시간 지연)는 stock_toolkit 범위 내에서 해결 불가.
하지만 "사용자가 늦다고 느끼는 체감"은 3가지 변경으로 70~80% 개선.**

### 16.5 3문장 요약

1. **문제:** signal-pulse AI 신호가 하루 2회(07:00/19:00)만 갱신되어, 장중 핵심 섹션이 최대 15시간 전 데이터로 고정됨.
2. **해결:** 기존 신호를 유지하되, 장중 실시간 데이터를 오버레이(유효성 검증) + 신호 나이 표시(Decay) + 급등 경보(미포착 보완)를 추가.
3. **결과:** ~135줄 변경으로 체감 실시간성 70~80% 개선, 급등 미포착 73.3%→즉시 감지, 모든 변경 역가능.

---

## 17. 9차 연구: Devil's Advocate — 기존 결론에 대한 반론

### 17.1 핵심 반론: "08:00 배포 추가로 문제가 이미 해결되었을 가능성"

커밋 `2b05b22` (2026-03-17)에서 08:00 KST full 모드 cron을 추가함.

| 항목 | 이전 | 현재 (08:00 cron 추가 후) |
|---|---|---|
| signal-pulse 분석 | 07:00 KST 완료 | 동일 |
| stock_toolkit 최초 full 배포 | 09:30 KST | **08:00 KST** |
| 장 시작(09:00) 시점 신호 나이 | ~15시간 (전날 19:00 기준) | **~1시간** (당일 07:00 기준) |

**→ "약 하루 늦음" 문제의 대부분은 08:00 cron 추가만으로 이미 해결됨.**

### 17.2 3가지 솔루션 재평가 (반론 포함)

#### Overlay 반론

| 문제 | 상세 |
|---|---|
| UI 표시 공간 없음 | AI 주목 종목은 칩(pill)으로만 렌더링 → overlay 데이터가 보이려면 클릭 필요 |
| 패시브 사용자 무효 | 칩을 클릭하지 않는 사용자에게는 overlay가 전달되지 않음 |
| 정보 과부하 | 팝업에 기존 6~7필드 + overlay 6~7필드 = 사용자 혼란 |

#### Decay 반론

| 문제 | 상세 |
|---|---|
| 균일한 노화 표시 | 모든 신호가 동일하게 "N시간 전" → 차별화 정보 없음 |
| 타임스탬프 무시 현상 | 현재 text-[10px] t-text-dim 타임스탬프를 99% 사용자가 안 읽음 |
| 불안감 유발 | "이 신호는 오래됐습니다"를 보여주는 것 = 기능 부족 고백 |

#### 급등 경보 반론

| 문제 | 상세 |
|---|---|
| 30분 배포 사이클 지연 | 급등 발생 → 30분 후 경보 → 이미 반락 가능 |
| 거래량 조건 소멸 | 배포 시점에 거래량비 200% 미만으로 떨어져 있을 수 있음 |
| "너무 늦은 경보"는 경보가 아님 | 초 단위 감지가 필요한데 30분 주기는 본질적으로 부적합 |

### 17.3 반론에 대한 재반론 (균형 평가)

| 반론 | 재반론 | 최종 판단 |
|---|---|---|
| 08:00으로 이미 해결 | 08:00은 장 시작 전이고, 장중(09:30~15:30) 동안은 여전히 08:00 데이터 = 최대 7.5시간 지연 | **부분 유효** — 장 시작 직후는 해결, 장중 후반은 미해결 |
| Overlay UI 공간 없음 | 칩 외에 교차 신호 섹션(line 815-839)에는 카드형 UI가 있어 표시 가능 | **일부 유효** — 칩에는 불가, 카드에는 가능 |
| 급등 경보 30분 지연 | "30분 전 급등"이라도 아예 모르는 것보다는 나음. 추세 파악 용도 | **일부 유효** — 실시간 경보가 아닌 "추세 모니터링" |
| Decay 불안감 유발 | "모르고 구 신호 추격매수"보다 "알고 조심"이 나음 | **유효** — 투명성은 불안감보다 가치 있음 |

### 17.4 수정된 최종 결론

**8차 결론 "3가지 솔루션 필수"에서 수정:**

```
08:00 cron 추가로 장 시작 시점의 지연은 이미 해결됨 (15시간 → 1시간).
3가지 솔루션은 "필수"가 아닌 "장중 후반 지연(~7.5시간) 보완용 선택적 개선".
```

| 솔루션 | 8차 판정 | 9차 수정 판정 |
|---|---|---|
| Intraday Overlay | 필수, 최우선 | **선택적** — 교차 신호 카드에만 적용 시 유효 |
| 신뢰도 Decay | 필수 | **선택적** — 투명성 제공, 하지만 필수는 아님 |
| 장중 급등 경보 | 필수 | **선택적** — "추세 모니터링"으로 리포지셔닝 |
| **08:00 cron (이미 구현)** | 언급만 | **핵심 해결책** — 원래 문제의 80%+ 해결 |

### 17.5 ~~최종 3문장 요약 (9차 수정)~~ → 10차에서 정정됨

~~1. **문제:** signal-pulse AI 신호가 하루 2회(07:00/19:00)만 갱신되어 장중 데이터가 고정됨.~~
~~2. **이미 해결된 부분:** 08:00 full 모드 cron 추가(2b05b22)로 장 시작 시점 지연이 15시간→1시간으로 단축됨.~~
~~3. **추가 개선(선택적):** 장중 후반 지연(~7.5시간) 보완을 위해 Overlay/Decay/경보를 검토할 수 있으나, 필수는 아님.~~

**⚠️ 9차 결론은 10차에서 무효화됨 — 아래 섹션 18 참조**

---

## 18. 10차 연구: 9차 오류 정정 — 08:00 cron은 신호 신선도를 개선하지 않음

### 18.1 핵심 정정

**9차 주장:** "08:00 cron으로 장 시작 시 신호 나이가 15시간→1시간으로 단축"
**10차 정정:** **완전히 오류.** 08:00 cron이 사용하는 signal-pulse 07:00 분석은 **어제 15:30 장마감 데이터 기반**. 신호 나이는 여전히 16.5시간.

**근거:** 한국 주식시장은 15:30 마감 후 다음날 09:00까지 거래 없음. 07:00 분석이든 19:00 분석이든 마지막 거래 데이터는 동일한 전일 15:30 마감가.

### 18.2 정정된 신호 신선도 타임라인

| 시점 (KST) | 신호 기반 데이터 | 장마감 후 경과 | 비고 |
|:---:|---|:---:|---|
| 15:30 (전일 마감) | — | 0시간 | 데이터 확정 |
| 19:00 (전일 분석) | 전일 15:30 | 3.5시간 | signal-pulse 저녁 분석 |
| 07:00 (당일 분석) | **전일 15:30** | **15.5시간** | 같은 데이터로 재분석 |
| **08:00 (배포)** | **전일 15:30** | **16.5시간** | 08:00 cron → **0시간 개선** |
| 09:00 (장 개장) | 전일 15:30 | 17.5시간 | 장 시작, 신호 변함없음 |
| 10:00 | 전일 15:30 | 18.5시간 | |
| 14:00 | 전일 15:30 | **22.5시간** | 장중 후반, 최대 지연 |
| 15:30 (당일 마감) | 전일 15:30 | **24시간** | 정확히 1일 지연 |
| 19:00 (당일 분석) | **당일 15:30** | 3.5시간 | **드디어 당일 데이터 반영** |

### 18.3 08:00 cron이 실제로 개선한 것

| 데이터 | 08:00에 신선한가? | 신선도 |
|---|---|---|
| 선물/환율/F&G/VIX | ✅ 야간 글로벌 시장 | ~1시간 |
| AI 테마 예측 | ✅ 글로벌 야간 + 전일 국내 | ~30분 |
| **AI 매매 신호 (vision_signal)** | **❌ 전일 마감 데이터** | **16.5시간** |
| **등락률/거래량 TOP** | **❌ 전일 마감** | **16.5시간** |
| **투자자 수급** | **❌ 전일 마감** | **16.5시간** |

**08:00 cron은 글로벌 야간 데이터만 새로움. 국내 시장 데이터는 전일 그대로.**

### 18.4 장중 fresh 데이터 타임라인

```
08:00  모든 국내 데이터 = 어제 15:30 기준 (16.5시간 전)
       글로벌만 fresh: 선물, F&G, VIX, 환율

09:05  ★ theme-analyzer 첫 수집 → latest.json 갱신
       등락률/거래량/거래대금 TOP = 오늘 데이터 (첫 fresh!)

09:28  ★ theme-analyzer 2차 수집

09:31  ★ investor-intraday 첫 스냅샷
       종목별 외국인/기관 실시간 수급 (첫 fresh!)

10:01  investor-intraday 2차
11:31  investor-intraday 3차
13:21  investor-intraday 4차
14:31  investor-intraday 5차

09:30~15:00  intraday-history 30분봉 (7회)

이 시간 동안 cross_signal/smart_money/risk_monitor의 vision_signal은:
  → 여전히 전일 15:30 기반 = 18~24시간 전 데이터
  → theme-analyzer는 6시간분 fresh 데이터 보유
  → 이 격차가 "약 하루 늦게 따라감"의 정확한 원인
```

### 18.5 솔루션 재평가 (10차 정정)

9차에서 "선택적"으로 하향했던 솔루션을 **다시 "필수"로 상향**:

| 솔루션 | 9차 판정 | 10차 정정 판정 | 근거 |
|---|---|---|---|
| **Intraday Overlay** | 선택적 | **필수** | 장중 6시간 fresh 데이터 vs 24시간 stale 신호 — 격차가 매우 큼 |
| **신뢰도 Decay** | 선택적 | **필수** | 사용자가 24시간 전 신호를 최신으로 착각하는 것을 방지 |
| 장중 급등 경보 | 선택적 | **선택적 유지** | 30분 지연 한계는 변함없음 |

### 18.6 최종 3문장 요약 (10차 확정)

1. **문제:** signal-pulse AI 신호는 전일 15:30 마감 데이터 기반이며, 장중 갱신 0회 → 장중 최대 24시간 지연.
2. **08:00 cron의 한계:** 글로벌 야간 데이터만 새로움, **국내 시장 신호는 전일 그대로** (9차 "80% 해결" 주장은 오류).
3. **필수 해결:** Overlay(장중 fresh 데이터로 stale 신호 검증) + Decay(신호 나이 투명 공개)는 선택이 아닌 필수. 장중 급등 경보는 선택적.
