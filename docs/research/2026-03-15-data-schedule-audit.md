# 데이터 수집 스케줄 대비 활용 검증 보고서

> 2026-03-15 — theme-analyzer 데이터 수집 스케줄 기반 교차 검증
> v2 보고서 보완: 누락 항목 및 추가 발견 사항

---

## 1. 스케줄별 데이터 수집 → 파일 → 활용 매핑

### 1.1 장전 (07:00~08:45)

| 시간 | 수집 내용 | 저장 파일 | stock_toolkit 활용 |
|:---:|------|------|:---:|
| 07:00 | 나스닥100선물(NQ=F), MU, SOXX, EWY, KORU, KOSPI200F | `macro-indicators.json` → indicators[] | ❌ 미활용 |
| 07:00 | 환율 USD/JPY/EUR/CNY | `macro-indicators.json` → exchange + `latest.json` → exchange | ❌ 미활용 |
| 07:30 | AI 유망 테마 예측 (1차) | `theme-forecast.json` + `forecast-history/` | ❌ 미활용 |
| 08:45 | KOSPI200 선물 + 전체 거시지표 갱신 | `macro-indicators.json` + `indicator-history.json` | ❌ 미활용 |

**장전 데이터 활용률: 0%** — 4개 수집 시점의 데이터가 전부 미활용

### 1.2 장중 전체 수집 (09:05, 09:28)

| 시간 | 수집 내용 | 저장 파일 | stock_toolkit 활용 |
|:---:|------|------|:---:|
| 09:05 | KIS 등락률 TOP | `latest.json` → rising/falling | ✅ 사용 |
| 09:05 | KIS 거래량 TOP | `latest.json` → volume | ✅ 사용 |
| 09:05 | KIS 거래대금 TOP | `latest.json` → trading_value | ❌ 미활용 |
| 09:05 | 뉴스 수집 | `latest.json` → news | ❌ 미활용 |
| 09:05 | AI 테마 분석 | `latest.json` → theme_analysis | ✅ 사용 |
| 09:05 | 환율 | `latest.json` → exchange | ❌ 미활용 |
| 09:28 | 2차 동일 수집 | `latest.json` 갱신 | - |

**장중 전체 수집 활용률: 50%** (3/6 카테고리)

### 1.3 장중 수급 가집계 (5회)

| 시간 | 수집 내용 | 저장 파일 | stock_toolkit 활용 |
|:---:|------|------|:---:|
| 09:31 | 외국인 1차 | `investor-intraday.json` → snapshots[0] | ❌ 미활용 |
| 10:01 | 기관 1차 | `investor-intraday.json` → snapshots[1] | ❌ 미활용 |
| 11:31 | 외국인+기관 2차 | `investor-intraday.json` → snapshots[2] | ❌ 미활용 |
| 13:21 | 외국인+기관 3차 | `investor-intraday.json` → snapshots[3] | ❌ 미활용 |
| 14:31 | 외국인+기관 최종 | `investor-intraday.json` → snapshots[4] | ❌ 미활용 |
| 15:45 | 장후 수급 | `latest.json` → investor_data | ✅ 사용 (장마감 확정치만) |
| 18:05 | 확정치 + pykrx 검증 | `latest.json` → investor_data 갱신 | ✅ 사용 |

**장중 수급 활용률: 28%** — 5개 가집계 데이터 전부 미활용, 장마감 확정치만 사용

### 1.4 장중 등락 히스토리 (매시간)

| 시간 | 수집 내용 | 저장 파일 | stock_toolkit 활용 |
|:---:|------|------|:---:|
| 09:30~15:00 | 1분봉 → 30분/60분 집계 | `intraday-history.json` → stocks{} | ⚠️ 시도했으나 구조 불일치 |
| 11:30, 15:40 | 보충 수집 | `intraday-history.json` 갱신 | ⚠️ 동일 |

**장중 등락 활용률: ~5%** — 패턴 매칭에 시도했으나 실패, 실질 미활용

### 1.5 장중 AI 테마 재예측 (2회)

| 시간 | 수집 내용 | 저장 파일 | stock_toolkit 활용 |
|:---:|------|------|:---:|
| 10:00 | 조기 재예측 | `forecast-history/YYYY-MM-DD_1000.json` | ❌ 미활용 |
| 13:00 | 오후 재예측 | `forecast-history/YYYY-MM-DD_1300.json` | ❌ 미활용 |

**테마 재예측 활용률: 0%** — 하루 3회 AI 예측이 모두 미활용

### 1.6 매물대 Volume Profile (3회)

| 시간 | 수집 내용 | 저장 파일 | stock_toolkit 활용 |
|:---:|------|------|:---:|
| 10:00 | 장중 매물대 1차 (80종목) | `volume-profile.json` | ❌ 미활용 |
| 13:00 | 장중 매물대 2차 (80종목) | `volume-profile.json` 갱신 | ❌ 미활용 |
| 15:40 | 장후 매물대 전체 (165종목) | `volume-profile.json` 최종 | ❌ 미활용 |

**매물대 활용률: 0%** — 165종목 × 6기간 × POC 전체 미활용

### 1.7 장후 (15:40~18:00)

| 시간 | 수집 내용 | 저장 파일 | stock_toolkit 활용 |
|:---:|------|------|:---:|
| 15:40 | 모의투자 시뮬레이션 | `paper-trading/YYYY-MM-DD.json` (24일분) | ❌ 미활용 |
| 18:00 | 백테스트 (적중률) | `forecast-history/`에서 비교 가능 | ❌ 미활용 |

**장후 활용률: 0%** — 24일분 모의투자 결과 + 백테스트 전체 미활용

---

## 2. 이전 보고서(v2)에서 누락된 발견 사항

### 2.1 criteria_data 추가 필드 (v2에서 미발견)

| 필드 | 설명 | v2 보고서 | 활용 |
|------|------|:---:|:---:|
| `golden_cross` | 골든크로스 발생 여부 | ❌ 미언급 | ❌ 미활용 |
| `bnf` | BNF(Buy and Forget) 적합 종목 | ❌ 미언급 | ❌ 미활용 |
| `short_selling` | 공매도 비율 + 경고 수준 | ❌ 미언급 | ❌ 미활용 |
| `reverse_alignment` | 역배열 (하락 추세) | ❌ 미언급 | ❌ 미활용 |
| `market_cap` | 시가총액 상세 | ❌ 미언급 | ❌ 미활용 |

**v2에서 criteria_data를 11개로 기재했으나 실제 14개 필드 존재. 3개 추가 발견.**

### 2.2 investor-intraday.json 상세 구조 (v2에서 불충분)

v2 보고서: "5개 시점 투자자 동향"으로만 기재

**실제 구조:**
```json
snapshots[]: [{
  time: "09:31",
  round: 1,
  is_estimated: true/false,
  data: {
    "005930": { f: 외국인, i: 기관, p: 프로그램, pg: 개인, cp: 현재가, cr: 등락률 },
    "000660": { ... },
    // 200+ 종목별 실시간 수급
  },
  pt: {
    kospi: [{ investor: "외국인", all_ntby_amt: ... }],
    kosdaq: [...]
  }
}]
```

**발견:** 단순 시장 전체 합계가 아닌, **종목별(200+종목) 시간대별 외국인/기관/개인/프로그램 수급 + 현재가 + 등락률**이 포함되어 있음. 이는 v2에서 "5개 시점 투자자 동향"으로 축소 기재되었으나, 실제로는 **200종목 × 5시점 × 6필드 = 6,000개 데이터포인트**의 장중 실시간 수급 데이터.

### 2.3 paper-trading 상세 구조 (v2에서 불충분)

v2 보고서: "22일분 모의투자 결과"로만 기재

**실제 구조:**
```json
{
  trade_date: "2026-03-13",
  price_snapshots: [
    { timestamp: "09:24", prices: { "005930": 59100, ... }, leader_stocks: [...] },
    { timestamp: "09:32", prices: { ... }, leader_stocks: [...] },
    { timestamp: "10:02", prices: { ... } },
    { timestamp: "11:32", prices: { ... } },
    { timestamp: "13:22", prices: { ... } },
    { timestamp: "14:32", prices: { ... } },
  ],
  stocks: [
    { name: "한일사료", code: "005860", theme: "사료/비료/곡물",
      buy_price: 4530, close_price: 4530, profit_rate: 0.0,
      high_price: 4530, high_profit_rate: 0.0 },
    // 10개 AI 선정 대장주
  ],
  summary: { total_stocks: 10, profit_stocks: 5, loss_stocks: 3, ... }
}
```

**발견:** 단순 수익률이 아닌, **장중 6개 시점의 전 종목 가격 스냅샷 + AI 선정 대장주별 매수가/종가/최고가/수익률**이 포함. 24일 × 6시점 × 100+종목 = **14,400+ 가격 데이터포인트**의 장중 가격 히스토리.

### 2.4 forecast-history 상세 구조 (v2에서 불충분)

**실제 구조:**
```json
{
  forecast_date: "2026-03-13",
  generated_at: "2026-03-13T07:33:00+09:00",
  market_context: "미국 증시 하락, VIX 상승...",
  us_market_summary: "S&P500 -0.5%, 나스닥 -0.8%...",
  news_sources: [{ title: "...", url: "...", grounding: true }],
  today: [
    { theme_name: "사료/비료/곡물 관련주",
      theme_description: "호르무즈 해협 봉쇄 우려...",
      confidence: "높음",
      catalyst: "중동 긴장 고조",
      risk: "지정학적 리스크 해소 시 급락",
      leader_stocks: [
        { name: "한일사료", code: "005860", reason: "...",
          data_verified: true, news_evidence: ["..."] }
      ]
    }
  ]
}
```

**발견:** 20개 파일(하루 3회 × ~7일). 각 예측에 **테마명, 설명, 신뢰도(높음/중간/낮음), 촉매, 리스크, 대장주, 뉴스 근거**가 포함. 이 데이터로 예측 적중률 자동 계산이 가능하나 완전 미활용.

### 2.5 latest.json → history 필드 (v2에서 누락)

**실제 구조:**
```json
history: {
  "005930": {  // 삼성전자
    code: "005930",
    changes: [
      { date: "2026-03-13", change_pct: -0.5, volume: 12500000, close: 59100 },
      { date: "2026-03-12", change_pct: +1.2, volume: 15800000, close: 59400 },
      { date: "2026-03-11", change_pct: -0.8, volume: 11200000, close: 58700 },
    ],
    total_change_rate: -0.1,
    raw_daily_prices: [
      { stck_bsop_date: "20260313", stck_clpr: "59100", stck_oprc: "59500",
        stck_hgpr: "59800", stck_lwpr: "58900", acml_vol: "12500000" },
      // 3일분 OHLCV
    ]
  },
  // 200+ 종목
}
```

**발견:** 200+ 종목의 **3일분 일봉 OHLCV(시가/고가/저가/종가/거래량)**가 포함. `intraday-history.json`과 별개로 일봉 데이터가 존재하며, 이전 보고서에서 "미사용"으로만 표기했으나 **단기 추세 분석, 3일 모멘텀, 가격 패턴**에 즉시 활용 가능.

### 2.6 latest.json → news 필드 (v2에서 상세 미확인)

**실제 구조:**
```json
news: {
  "005930": {
    name: "삼성전자",
    news: [
      { title: "삼성전자 주가 30만원 찍을까",
        link: "https://...",
        description: "...",
        pubDate: "2026-03-13T10:30:00",
        originallink: "https://..." },
      // 3~5개 뉴스
    ]
  },
  // 100+ 종목
}
```

**발견:** 100+ 종목별 최신 뉴스 3~5건이 포함. `combined_analysis`의 `vision_news`와 별개의 독립 뉴스 소스. theme-analyzer가 Naver News API로 직접 수집한 것으로, **뉴스 임팩트 분석에 추가 소스로 활용 가능**.

---

## 3. 종합: 스케줄 대비 활용률

| 시간대 | 수집 횟수 | 활용 횟수 | 활용률 |
|--------|:---:|:---:|:---:|
| 장전 (07:00~08:45) | 4회 | 0회 | **0%** |
| 장중 전체 (09:05, 09:28) | 2회 (6카테고리) | 3카테고리 | **50%** |
| 장중 수급 (09:31~14:31) | 5회 | 0회 | **0%** |
| 장중 등락 (09:30~15:00) | 7회 | ~0회 | **~0%** |
| 장중 AI 재예측 (10:00, 13:00) | 2회 | 0회 | **0%** |
| 매물대 (10:00, 13:00, 15:40) | 3회 | 0회 | **0%** |
| 장후 수급 (15:45, 18:05) | 2회 | 2회 | **100%** |
| 모의투자/백테스트 (15:40, 18:00) | 2회 | 0회 | **0%** |
| **합계** | **27회** | **5회** | **18.5%** |

**theme-analyzer가 하루 27회 데이터를 수집하지만, stock_toolkit은 그 중 5회분(장후 확정 수급 + 전체 수집 일부)만 활용.**

---

## 4. v2 보고서 수정/보완 사항

### 4.1 추가해야 할 Tier 1 항목

| # | 항목 | 미활용 데이터 | 이전 보고서 |
|---|------|-------------|:---:|
| T1-9 | latest.json → history (3일 OHLCV) | 200종목 3일 일봉 | v2 미언급 |
| T1-10 | latest.json → news (Naver 뉴스) | 100+종목 뉴스 3~5건 | v2 미언급 |

### 4.2 추가해야 할 Tier 2 항목

| # | 항목 | 미활용 데이터 | 이전 보고서 |
|---|------|-------------|:---:|
| T2-18 | criteria_data → golden_cross | 골든크로스 발생 종목 | v2 미발견 |
| T2-19 | criteria_data → short_selling | 공매도 비율 + 경고 | v2 미발견 |
| T2-20 | criteria_data → bnf | 장기 보유 적합 종목 | v2 미발견 |
| T2-21 | investor-intraday 종목별 수급 | 200종목 × 5시점 × 6필드 | v2 불충분 |

### 4.3 추가해야 할 Tier 3 항목

| # | 항목 | 미활용 데이터 | 이전 보고서 |
|---|------|-------------|:---:|
| T3-26 | paper-trading 장중 가격 스냅샷 | 24일 × 6시점 × 100+종목 가격 | v2 불충분 |
| T3-27 | forecast-history 예측 적중률 | 20개 예측 × 테마/촉매/리스크/신뢰도 | v2 불충분 |
| T3-28 | indicator-history 매크로 추세 | 일별 8개 지표 히스토리 | v2 미언급 |

---

## 5. 최종 결론

### 이전 보고서(v2) 대비 추가 발견

| 항목 | v2 | 본 보고서 |
|------|------|------|
| criteria_data 필드 | 11개 | **14개** (+3: golden_cross, bnf, short_selling) |
| investor-intraday | "5개 시점 투자자 동향" | **200종목 × 5시점 × 6필드 = 6,000 데이터포인트** |
| paper-trading | "22일분 모의투자" | **24일 × 6시점 × 100+종목 = 14,400+ 가격 스냅샷** |
| latest.json → history | "미사용" 1줄 | **200+종목 3일 OHLCV (일봉 데이터)** |
| latest.json → news | "미사용" 1줄 | **100+종목 × 3~5건 = 300+개 뉴스** |
| 수집 스케줄 활용률 | 미측정 | **27회 중 5회만 활용 (18.5%)** |
| 추가 개선 항목 | 25개 | **+8개 = 총 33개** |

### 핵심 메시지

theme-analyzer는 **하루 27회, 장전부터 장후까지 빈틈없이** 데이터를 수집하고 있으나, stock_toolkit은 그 중 **장후 확정 데이터만 주로 활용**하고 있어 장전 예측, 장중 실시간 수급, 매물대, 모의투자, 백테스트 데이터가 완전히 사장되고 있다.

특히 `investor-intraday.json`의 **종목별 실시간 수급 6,000 데이터포인트**와 `paper-trading/`의 **장중 가격 14,400+ 스냅샷**은 시간대별 히트맵, 패턴 매칭, 전략 검증에 즉시 활용 가능한 고가치 데이터임에도 전혀 연결되지 않고 있다.
