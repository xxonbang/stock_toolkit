# 외부 데이터 활용 방안 종합 연구 보고서

> 2026-03-17 — theme-analyzer / signal-pulse 전체 데이터 재조사 + stock_toolkit 활용 방안 연구
> 이전 보고서: `2026-03-15-data-schedule-audit.md` (스케줄 대비 활용률 18.5%)
>
> **구현 완료** (2026-03-17): Tier 1~3 전체 18건 적용, 활용률 18.5% → ~80% 향상

---

## 목차

1. [데이터 소스 전체 목록](#1-데이터-소스-전체-목록)
2. [현재 활용 현황 (42개 프론트엔드 파일 기준)](#2-현재-활용-현황)
3. [1순위: 기존 기능 개선 방안](#3-1순위-기존-기능-개선-방안)
4. [2순위: 신규 기능 활용 방안](#4-2순위-신규-기능-활용-방안)
5. [데이터 필드별 활용 매핑 상세](#5-데이터-필드별-활용-매핑-상세)
6. [구현 우선순위 종합](#6-구현-우선순위-종합)

---

## 1. 데이터 소스 전체 목록

### 1.1 theme-analyzer (10개 파일/디렉토리)

| # | 파일 | 크기 | 갱신 주기 | 핵심 내용 |
|---|------|------|----------|----------|
| T1 | `latest.json` | 20.4MB | 장중 2회 (09:05, 09:28) + 장후 | 19개 최상위 키: 등락률/거래량/거래대금TOP, 테마분석, 수급, 뉴스, 펀더멘털, 호가, 프로그램매매 등 |
| T2 | `macro-indicators.json` | ~5KB | 07:00, 08:45, 장중 | 8개 지표(NQ=F, VIX, FNG, MU, SOXX 등), 환율 4종, 선물 6종, 투자자동향 20일 |
| T3 | `theme-forecast.json` | ~15KB | 07:30, 10:00, 13:00 | AI 테마 예측 (today/short_term/long_term), 촉매/리스크/대장주/신뢰도 |
| T4 | `investor-intraday.json` | 67KB | 장중 5회 (09:31~14:31) | 150+종목 × 5시점 × 6필드 (외국인/기관/프로그램/현재가/등락률) |
| T5 | `intraday-history.json` | 2.4MB | 매 30분 (09:30~15:30) | 504종목 × 일별 30분봉(13개)/60분봉(7개) OHLCV |
| T6 | `volume-profile.json` | 828KB | 10:00, 13:00, 15:40 | 200+종목 × 6기간(1y/6m/3m/1m/1w/today) 매물대(POC, bins) |
| T7 | `indicator-history.json` | 11KB | 15:46 | 10개 매크로 지표 + 환율 + 선물 히스토리 |
| T8 | `paper-trading/` | 25파일 | 장후 15:40 | 일별 AI 모의투자: 9~10종목 매매, 8시점 가격 스냅샷, P&L 요약 |
| T9 | `forecast-history/` | 21파일 | 07:30, 10:00, 13:00 | 일별 3회 AI 예측 아카이브: 테마/촉매/리스크/대장주/신뢰도 |
| T10 | `history/` | 90파일 | 장중 3~4회 | latest.json 시점별 스냅샷 (등락률/거래량/뉴스/환율) |

### 1.2 signal-pulse (8개 파일/디렉토리)

| # | 파일 | 크기 | 핵심 내용 |
|---|------|------|----------|
| S1 | `combined/combined_analysis.json` | 19,272줄 | 105종목 Vision+KIS 통합 시그널: 신호/이유/신뢰도/뉴스분석/매치상태 |
| S2 | `vision/vision_analysis.json` | 5,784줄 | 97종목 Vision 분석: 4차원 점수(기술/수급/밸류/재료), 뉴스센티먼트 |
| S3 | `kis/kis_analysis.json` | 5,593줄 | 100종목 KIS API 분석: 시그널/점수/리스크/뉴스 |
| S4 | `kis/kis_gemini.json` | 대용량 | 100종목 상세: 가격(OHLC+52주), 거래, 시총, 밸류에이션, 호가, 투자자동향 |
| S5 | `kis/fear_greed.json` | ~200B | F&G 지수: 현재/전일/1주전/1월전/1년전 |
| S6 | `kis/vix.json` | ~150B | VIX: 현재/전일/변화/점수/등급 |
| S7 | `kis/market_status.json` | ~500B | KOSPI/KOSDAQ: 현재가, MA5/10/20/60/120, 배열상태 |
| S8 | `simulation/` | 48파일 | 일별 시뮬레이션: vision/kis/combined 카테고리별 매매결과, 전종목 시가/종가/고가 |

### 1.3 latest.json 상세 구조 (19개 최상위 키)

```
timestamp          → 마지막 갱신 시각
exchange           → 환율 4종 (USD/JPY/EUR/CNY)
rising             → KOSPI/KOSDAQ 등락률 TOP 10
falling            → 하락률 TOP 3
volume             → 거래량 TOP 30
trading_value      → 거래대금 TOP 30
fluctuation        → 방향별 등락 (UP/DOWN)
fluctuation_direct → 연속 상승/하락일수 포함
history            → 218종목 3일 OHLCV 일봉
news               → 100+종목 × 3~5건 네이버 뉴스
investor_data      → 189종목 외국인/기관/개인 순매수 + 히스토리
investor_estimated → 가집계 여부 boolean
theme_analysis     → 테마 30+ (순위/등락률/시총/대장주)
criteria_data      → 257종목 14개 기술적 필터 (boolean)
kospi_index        → KOSPI 현재 + MA5/10/20/60/120 + 상태
kosdaq_index       → KOSDAQ 동일 구조
member_data        → 47종목 증권사 매수/매도 TOP5
fundamental_data   → 79종목 PER/PBR/EPS/BPS/ROE/부채비율/OPM/PEG/RSI
program_trade      → KOSPI/KOSDAQ 프로그램매매 (11개 투자자유형)
```

### 1.4 kis_gemini.json 상세 구조 (종목별)

```
code, name, market
ranking            → volume_rank, volume, volume_rate_vs_prev, trading_value
price              → current, change, change_rate_pct, open, high, low, prev_close, high_52week, low_52week
trading            → volume, trading_value, volume_turnover_pct
market_info        → market_cap_billion, shares_outstanding, foreign_holding_pct
valuation          → per, pbr, eps, bps, peg
order_book         → total_ask/bid_volume, bid_ask_ratio, best_ask/bid
investor_flow      → today(f/i/ind), sum_5_days, daily_trend[]
```

---

## 2. 현재 활용 현황

### 2.1 프론트엔드 42개 JSON 파일 상태

| 상태 | 파일 수 | 비율 |
|------|:---:|:---:|
| ✅ 정상 작동 (실데이터) | 33 | 79% |
| ⚠️ 파싱 오류 / 0값 | 3 | 7% |
| ❌ 비어있음 (2B~235B) | 6 | 14% |

### 2.2 비어있거나 문제 있는 파일 상세

| 파일 | 크기 | 상태 | 원인 |
|------|------|------|------|
| `pattern.json` | 2B | ❌ 빈 배열 | kis_gemini price_history 부재 시 intraday-history 폴백 미작동 |
| `volume_profile.json` | 2B | ❌ 빈 배열 | 828KB 데이터 로드되나 필드명 불일치로 빈 출력 |
| `simulation_history.json` | 2B | ❌ 빈 배열 | simulation index 로드 실패 |
| `supply_cluster.json` | 235B | ⚠️ 최소 데이터 | investor_trend만 사용, 종목별 수급 미활용 |
| `intraday_heatmap.json` | 682B | ⚠️ 전체 0값 | investor-intraday 파싱 시 투자자 필드명 매칭 실패 |
| `theme_propagation.json` | 290B | ⚠️ 최소 데이터 | 테마 히스토리 데이터 부족 |

### 2.3 외부 데이터 활용률 요약

| 데이터 소스 | 전체 필드 수 | 활용 필드 수 | 활용률 |
|------------|:---:|:---:|:---:|
| latest.json (19키) | 19 | 14 | 74% |
| macro-indicators.json | 4섹션 | 4 | 100% |
| theme-forecast.json | 8키 | 3 | 38% |
| investor-intraday.json | 3섹션 | 1 (파싱 실패) | ~0% |
| intraday-history.json | 2섹션 | ~0% (폴백만) | ~0% |
| volume-profile.json | 3섹션 | 0% (로드 실패) | 0% |
| paper-trading/ (25파일) | 6키 | 1파일만 | 4% |
| forecast-history/ (21파일) | 8키 | 부분 사용 | 30% |
| history/ (90파일) | 10키 | lifecycle만 | 10% |
| combined_analysis.json | 풀 | 대부분 | 80% |
| kis_gemini.json | 풀 | 부분 | 60% |
| simulation/ (48파일) | 풀 | 0% | 0% |

---

## 3. 1순위: 기존 기능 개선 방안

> 이미 구현된 기능의 빈 데이터, 파싱 오류, 불완전 데이터를 수정하여 즉시 품질 향상

### 3.1 [버그] volume_profile.json — 매물대 분석 복구

**현재 상태:** 빈 배열 `[]` (2B)
**원인:** theme-analyzer의 `volume-profile.json` (828KB) 로드 성공하나 필드명 불일치
- 코드가 `vp_data.get("1month")` 접근하나 실제 키는 `"1m"`, `"6m"`, `"3m"`, `"1w"`, `"1y"`, `"today"`

**활용 데이터:**
```
volume-profile.json → profiles[code] → {
  "1y":    { price_low, price_high, bin_size, bins[{price, volume}] },
  "6m":    { ... },
  "3m":    { ... },
  "1m":    { ... },  ← 코드는 "1month"를 찾음
  "1w":    { ... },
  "today": { ... }
}
```

**개선안:**
- 키 매핑 수정: `"1month"` → `"1m"`, `"3month"` → `"3m"` 등
- POC(Point of Control) 계산: 각 기간별 최대 거래량 가격대 추출
- 프론트엔드에 지지/저항 가격대 표시

**효과:** 200+종목의 매물대 지지/저항 분석 즉시 활성화

---

### 3.2 [버그] intraday_heatmap.json — 장중 수급 히트맵 복구

**현재 상태:** 5개 시점 존재하나 모든 값 = 0
**원인:** `investor-intraday.json`의 `pt` 필드 파싱 시 투자자 유형 매칭 실패

**실제 데이터 구조:**
```json
snapshots[].pt = {
  kospi: { all: -305363, arbt: -55524, nabt: -249842 },
  kosdaq: { all: -155356, arbt: -1420, nabt: -153934 }
}
```
코드는 `pt.kospi`에서 `"외국인"` 문자열을 찾으나, 실제 구조는 `all/arbt/nabt` 키 사용

**활용 데이터 (추가):**
```json
snapshots[].data[code] = {
  f: -563000,   // 외국인 순매수
  i: 0,         // 기관 순매수
  p: null,      // 프로그램
  pg: -991427,  // 프로그램 순
  cp: 2875,     // 현재가
  cr: 23.13     // 등락률
}
```

**개선안:**
- pt 구조에 맞게 파싱 수정 (all/arbt/nabt 키 직접 사용)
- 종목별 수급(data[code]) 활용: 시간대별 TOP 외국인 순매수 종목 추출
- 프로그램 매매 장중 추이 추가

**효과:** 5시점 장중 수급 흐름 + 종목별 외국인/기관 실시간 추적

---

### 3.3 [버그] pattern.json — 패턴 매칭 복구

**현재 상태:** 빈 배열 `[]` (2B)
**원인:** kis_gemini의 price_history 부재 시 intraday-history 폴백이 실질적으로 작동하지 않음

**활용 데이터:**
```
intraday-history.json → stocks[code][] = {
  date, open,
  intervals_30m: [{ time, close, high, low, change_rate, volume }] × 13,
  intervals_60m: [{ time, close, high, low, change_rate, volume }] × 7
}
```
504종목 × 수일분 30분봉 데이터 존재

**개선안:**
- intraday-history.json을 주 데이터 소스로 전환 (kis_gemini 보조)
- 30분봉 종가 배열로 패턴 벡터 생성 → 코사인 유사도 매칭
- latest.json의 history[code].changes (3일 일봉) 보조 활용

**효과:** 504종목 기반 실제 장중 패턴 매칭 기능 복구

---

### 3.4 [개선] paper_trading — 모의투자 히스토리 추가

**현재 상태:** 최신 1일분만 표시 (paper_trading_latest.json, 3.6KB)
**미활용 데이터:** 25일분 paper-trading/*.json (2026-02-10 ~ 2026-03-16)

**각 파일 구조:**
```json
{
  trade_date, morning_timestamp, collected_at,
  price_snapshots: [{ timestamp, prices: {code: price}, leader_stocks }] × 8,
  stocks: [{ code, name, theme, buy_price, close_price, profit_rate,
             high_price, high_time, high_profit_rate }] × 9~10,
  summary: { total_stocks, profit_stocks, loss_stocks,
             total_profit_rate, high_total_profit_rate }
}
```

**개선안:**
- 25일 롤링 수익률 추이 차트 데이터 생성
- 일별 승률(profit_stocks/total_stocks) 트렌드
- 테마별 성공률 집계 (theme 필드 기준)
- 최고 수익 시점 분석 (high_time 분포)

**효과:** 모의투자 전략의 시계열 성과 분석 (단일 스냅샷 → 25일 트렌드)

---

### 3.5 [개선] forecast_accuracy — 예측 적중률 정밀화

**현재 상태:** 10일 예측 추적하나 적중률 0% (테마명 불일치)
**원인:** 예측 테마명("반도체/IT 부품 (AI & HBM 포함)")과 실제 테마명("AI 반도체") 부분 일치 실패

**활용 데이터:**
```
forecast-history/*.json → today[].{
  theme_name, description, catalyst, confidence,
  leader_stocks[].{ code, name, reason, data_verified }
}
```

**개선안:**
- 테마명 대신 **대장주 코드(leader_stocks[].code)** 기준 매칭
  - 예측 대장주가 실제 등락률 TOP에 포함되면 적중
- 신뢰도(confidence: 높음/보통/낮음)별 적중률 분리 집계
- short_term/long_term 예측도 추적 (현재 today만)

**효과:** 실질적 예측 적중률 측정 + AI 예측 신뢰도 검증

---

### 3.6 [개선] simulation_history — 시뮬레이션 히스토리 복구

**현재 상태:** 빈 배열 (2B)
**미활용 데이터:** signal-pulse의 `simulation/` 48파일

**각 파일 구조:**
```json
{
  date, collected_at,
  categories: {
    vision: [{ code, name, signal, buy_price, close_price, profit_rate }],
    kis: [...],
    combined: [...]
  },
  all_prices: { code: { open_price, close_price, high_price, high_price_time } },
  all_signals: { code: { name, vision_signal } }
}
```

**개선안:**
- 48일분 시뮬레이션 결과 집계: vision/kis/combined 카테고리별 승률·수익률
- 일별 성과 트렌드 차트 데이터
- 카테고리별 비교 (어느 소스가 더 정확한지)

**효과:** 시그널 소스별 백테스트 성과 시각화

---

### 3.7 [개선] news_impact — 뉴스 소스 이중화

**현재 상태:** combined_analysis의 vision_news만 사용
**미활용 데이터:** latest.json → news (100+종목 × 3~5건 네이버 뉴스)

**latest.json news 구조:**
```json
news[code] = {
  name: "삼성전자",
  news: [{ date, title, link, source }] × 3~5
}
```

**개선안:**
- vision_news (signal-pulse) + latest.news (theme-analyzer) 병합
- 중복 제거 후 종목별 뉴스 카운트 증가
- 뉴스 소스 다양화 라벨 표시

**효과:** 뉴스 커버리지 확대 (종목당 3~5건 → 6~10건)

---

### 3.8 [개선] valuation — 밸류에이션 데이터 보강

**현재 상태:** kis_gemini 또는 criteria_data에서 PER/PBR/ROE 추출
**미활용 데이터:** latest.json → fundamental_data (79종목)

**fundamental_data 구조:**
```json
fundamental_data[code] = {
  per, pbr, eps, bps, market_cap, roe,
  debt_ratio, eps_growth, opm, peg, rsi,
  w52_hgpr, w52_lwpr, stck_prpr
}
```

**개선안:**
- 기존 밸류에이션에 추가 지표 반영: debt_ratio(부채비율), eps_growth(EPS성장률), opm(영업이익률)
- 52주 고/저 대비 현재가 위치 시각화 (w52_hgpr, w52_lwpr, stck_prpr)
- PEG 비율 활용 (성장 대비 밸류 판단)

**효과:** 밸류에이션 섹션 지표 3개 → 8개로 확대

---

### 3.9 [개선] premarket — 장전 데이터 강화

**현재 상태:** 선물 5종 + F&G + VIX (macro-indicators 기반)
**미활용 데이터:**
- `theme-forecast.json` → `market_context`, `us_market_summary`
- `macro-indicators.json` → `investor_trend` (20일 투자자동향)

**개선안:**
- AI가 생성한 market_context(시황 요약)를 프리마켓 섹션에 추가
- 전일 미국 시장 요약(us_market_summary) 표시
- 최근 5일 외국인/기관 순매수 추이 (investor_trend에서 추출)

**효과:** 장전 브리핑의 맥락 정보 대폭 강화

---

### 3.10 [개선] short_squeeze — 공매도 스퀴즈 정밀화

**현재 상태:** criteria_data의 overheating + 외국인 순매수 > 10만주로 판별
**미활용 데이터:** criteria_data의 `short_selling` 필드 (공매도 비율 + 경고 수준)

**개선안:**
- `short_selling: true` 종목 직접 필터링
- 공매도 과열 + 외국인 매수 전환 = 스퀴즈 후보
- `golden_cross: true` 종목과 교차 필터링 (기술적 반등 확인)

**효과:** 공매도 스퀴즈 탐지 정확도 향상

---

### 3.11 [개선] smart_money — 스마트머니 데이터 보강

**현재 상태:** combined_analysis에서 고신뢰 시그널(score≥70) TOP 20 추출
**미활용 데이터:** latest.json → member_data (47종목 증권사별 매수/매도 TOP5)

**member_data 구조:**
```json
member_data[code] = {
  name, buy_top5: [{ member, quantity, amount }],
  sell_top5: [...], total_sell_qty, total_buy_qty,
  foreign_buy, foreign_sell, foreign_net
}
```

**개선안:**
- 고신뢰 시그널 종목에 증권사 매매 데이터 추가
- "특정 대형 증권사가 집중 매수" 패턴 표시
- foreign_net과 institution 시그널 교차 검증

**효과:** 스마트머니 근거에 증권사 수급 데이터 추가

---

### 3.12 [개선] orderbook — 호가창 실제 데이터 적용

**현재 상태:** kis_gemini 또는 investor_data 폴백으로 호가 구성
**미활용 데이터:** kis_gemini의 order_book 상세

**kis_gemini order_book 구조:**
```json
order_book = {
  total_ask_volume, total_bid_volume,
  bid_ask_ratio: 179.85,
  best_ask: { price, volume },
  best_bid: { price, volume }
}
```

**개선안:**
- bid_ask_ratio 직접 활용 (현재 자체 계산)
- 매도 잔량 vs 매수 잔량 비율을 매수 압력 지표로 표시
- best_ask/best_bid 스프레드 분석

**효과:** 호가 분석의 정확도 향상

---

## 4. 2순위: 신규 기능 활용 방안

> 현재 미구현이나 기존 데이터로 즉시 구현 가능한 기능

### 4.1 [신규] 장중 종목별 수급 추적기

**데이터 소스:** `investor-intraday.json` → data[code]
**현재 미활용도:** 150+종목 × 5시점 × 6필드 = **4,500+ 데이터포인트 완전 미활용**

**구현 내용:**
- 개별 종목의 시간대별 외국인(f)/기관(i) 순매수 추이 라인차트
- "장 초반 외국인 매수 → 장 후반 매도 전환" 패턴 자동 감지
- 등락률(cr) 대비 수급 방향 일치/불일치 표시

**데이터 구조:**
```json
// 종목 코드별 5시점 수급 데이터
data["003280"] = {
  f: -563000,   // 09:31 외국인
  i: 0,         // 09:31 기관
  cp: 2875,     // 09:31 현재가
  cr: 23.13     // 09:31 등락률
}
// → 10:01, 11:31, 13:21, 14:31 반복
```

**기대 효과:** 장중 수급 반전 종목 조기 포착

---

### 4.2 [신규] AI 예측 백테스트 대시보드

**데이터 소스:** `forecast-history/` (21파일) + `history/` (90파일)
**현재 미활용도:** AI 예측 3회/일 × 7일 = 21개 예측 전량 미분석

**구현 내용:**
- 일별 예측 테마 vs 실제 상승 테마 비교 매트릭스
- 대장주 코드 기준 적중 판정 (테마명 불일치 우회)
- 시간대별(07:30/10:00/13:00) 예측 정확도 비교
- 신뢰도(높음/보통/낮음)별 적중률 통계
- 최근 7일 적중률 트렌드

**데이터 매핑:**
```
forecast-history/YYYY-MM-DD_0730.json → today[].leader_stocks[].code
    vs.
history/YYYY-MM-DD_1143.json → rising.kospi/kosdaq[].code
```

**기대 효과:** AI 예측의 실질 성과 투명화, 예측 모델 개선 근거 확보

---

### 4.3 [신규] 매물대 지지/저항 경보

**데이터 소스:** `volume-profile.json` (828KB, 200+종목)
**현재 미활용도:** 6기간 매물대 데이터 전량 미활용

**구현 내용:**
- POC(최대 거래량 가격) 계산: `max(bins, key=volume).price`
- 현재가 대비 POC 위치: "지지대 근접" / "저항대 근접" / "돌파" 판정
- 1주/1월/3월 POC 수렴 시 "강한 지지/저항" 신호
- 스캐너 필터 추가: "지지대 근접 종목", "저항 돌파 종목"

**데이터 예시:**
```json
profiles["003280"]["1m"] = {
  price_low: 1414, price_high: 3290, bin_size: 93,
  bins: [
    { price: 1460, volume: 4805915 },
    { price: 2340, volume: 12300000 },  // ← POC (최대 거래량)
    { price: 3100, volume: 890000 }
  ]
}
```

**기대 효과:** 기술적 매매 의사결정 근거 제공 (매물대 기반 진입/이탈 판단)

---

### 4.4 [신규] 시그널 소스 성과 비교

**데이터 소스:** `simulation/` (48파일, signal-pulse)
**현재 미활용도:** 48일 × 3카테고리(vision/kis/combined) 시뮬레이션 전량 미사용

**구현 내용:**
- vision vs kis vs combined 시그널의 일별 수익률 비교 차트
- 카테고리별 누적 수익률, 승률, 최대 손실
- "이번 달 가장 정확한 시그널 소스" 자동 판정
- 종목별 "vision이 맞고 kis가 틀린" / "둘 다 맞은" 분석

**데이터 구조:**
```json
categories.vision = [{
  code, name, signal, buy_price, close_price,
  profit_rate, high_price, high_price_time
}]
```

**기대 효과:** 시그널 소스 선택의 데이터 기반 의사결정

---

### 4.5 [신규] 연속 상승/하락 모니터

**데이터 소스:** latest.json → `fluctuation_direct`
**현재 미활용도:** consecutive_up_days / consecutive_down_days 필드 미사용

**구현 내용:**
- 3일 이상 연속 상승 종목 리스트 (모멘텀 후보)
- 3일 이상 연속 하락 종목 리스트 (반등 후보)
- 수급 데이터와 교차: "연속 하락 + 외국인 매수 전환" = 반등 시그널

**기대 효과:** 모멘텀/반등 종목 자동 스크리닝

---

### 4.6 [신규] 매크로 지표 트렌드 분석

**데이터 소스:** `indicator-history.json` + `macro-indicators.json`
**현재 미활용도:** 히스토리 데이터는 복사만 하고 트렌드 분석 미실시

**구현 내용:**
- VIX 5일 추세 (상승=리스크 증가, 하락=안정)
- F&G 주간 변화량 표시 (이전 보고서의 previous_1_week 활용)
- 선물 6종의 3일 추세 방향 (화살표 or 미니 스파크라인)
- 환율 추이 (USD/KRW 5일 변화)

**기대 효과:** 매크로 환경 변화 추세 한눈에 파악

---

### 4.7 [신규] 증권사 수급 집중도 분석

**데이터 소스:** latest.json → member_data (47종목)
**현재 상태:** member_trading.json으로 단순 복사만

**구현 내용:**
- 특정 증권사의 다종목 동시 매수 패턴 감지 ("외국계 A증권 5종목 집중 매수")
- 매수/매도 편중 비율(buy_qty/total_vol) 분석
- 기존 시그널과 교차: "적극매수 시그널 + 대형 증권사 매수" = 고확신 종목

**기대 효과:** 기관 수급 기반 종목 선별 근거 추가

---

### 4.8 [신규] 테마 예측 vs 실현 캘린더

**데이터 소스:**
- `theme-forecast.json` → short_term, long_term 예측
- `forecast-history/` → 과거 예측 기록

**현재 미활용도:** short_term(1주)/long_term(1개월) 예측 전량 미사용

**구현 내용:**
- 캘린더 뷰: 예측 시점 → 실현 예정일 표시
- short_term 예측의 "이번 주 말까지" 추적
- long_term 예측의 "1개월 후" 추적
- 만기 도래 시 자동 적중/실패 판정

**기대 효과:** 중장기 예측의 추적 관리

---

## 5. 데이터 필드별 활용 매핑 상세

### 5.1 theme-analyzer 미활용 필드 → 활용 매핑

| 파일 | 미활용 필드 | 활용 대상 기능 | 우선순위 |
|------|-----------|-------------|:---:|
| latest.json | `trading_value` (거래대금 TOP30) | trading_value.json 보강 | 3.12과 통합 |
| latest.json | `fluctuation_direct.consecutive_*` | 4.5 연속 상승/하락 모니터 | 2순위 |
| latest.json | `history[code].raw_daily_prices` | 3.3 패턴매칭 보조 | 1순위 |
| latest.json | `news[code]` | 3.7 뉴스 소스 이중화 | 1순위 |
| latest.json | `fundamental_data` | 3.8 밸류에이션 보강 | 1순위 |
| latest.json | `program_trade` 상세 (11유형) | program_trading.json 보강 | 2순위 |
| investor-intraday | `data[code].{f,i,p,pg,cp,cr}` | 3.2 히트맵 + 4.1 수급 추적기 | 1순위 |
| investor-intraday | `pt.{kospi,kosdaq}` | 3.2 히트맵 복구 | 1순위 |
| intraday-history | `intervals_30m/60m` | 3.3 패턴매칭 복구 | 1순위 |
| volume-profile | `profiles[code].{1y~today}.bins` | 3.1 매물대 복구 + 4.3 경보 | 1순위 |
| paper-trading/ | 24일분 히스토리 | 3.4 모의투자 히스토리 | 1순위 |
| forecast-history/ | `today/short_term/long_term` | 3.5 적중률 + 4.2 백테스트 | 1순위 |
| theme-forecast | `market_context`, `us_market_summary` | 3.9 프리마켓 강화 | 1순위 |
| theme-forecast | `short_term`, `long_term` | 4.8 예측 캘린더 | 2순위 |
| macro-indicators | `investor_trend` (20일) | 3.9 프리마켓 + 4.6 트렌드 | 2순위 |
| macro-indicators | `futures` (6종) | 3.9 프리마켓 강화 | 2순위 |

### 5.2 signal-pulse 미활용 필드 → 활용 매핑

| 파일 | 미활용 필드 | 활용 대상 기능 | 우선순위 |
|------|-----------|-------------|:---:|
| kis_gemini | `order_book.bid_ask_ratio` | 3.12 호가창 개선 | 1순위 |
| kis_gemini | `investor_flow.daily_trend` | smart_money 보강 | 2순위 |
| kis_gemini | `market_info.foreign_holding_pct` | 외국인 지분율 표시 | 2순위 |
| simulation/ | 48파일 전체 | 3.6 히스토리 + 4.4 소스 비교 | 1순위 |
| criteria_data | `short_selling_alert` 상세 | 3.10 공매도 스퀴즈 | 1순위 |
| criteria_data | `golden_cross` 상세 | 스캐너 필터 보강 | 2순위 |
| fear_greed | `previous_1_week/month/year` | 4.6 트렌드 분석 | 2순위 |
| vix | `score`, `rating` | sentiment.json 보강 | 2순위 |
| vision_analysis | `scores.{technical,supply_demand,valuation,material}` | 스캐너 점수 표시 | 2순위 |

---

## 6. 구현 우선순위 종합

### Tier 1: 즉시 수정 (버그 — 데이터는 있으나 파싱/매핑 오류)

| # | 항목 | 영향 | 난이도 | 참조 |
|---|------|------|:---:|------|
| 1 | volume_profile.json 키 매핑 수정 | 200+종목 매물대 활성화 | 낮음 | §3.1 |
| 2 | intraday_heatmap.json 파싱 수정 | 장중 수급 히트맵 활성화 | 낮음 | §3.2 |
| 3 | pattern.json intraday 폴백 수정 | 패턴 매칭 활성화 | 중간 | §3.3 |

### Tier 2: 단기 개선 (기존 기능 데이터 보강)

| # | 항목 | 영향 | 난이도 | 참조 |
|---|------|------|:---:|------|
| 4 | paper_trading 25일 히스토리 | 모의투자 트렌드 분석 | 낮음 | §3.4 |
| 5 | forecast_accuracy 대장주 기준 매칭 | 예측 적중률 실측 | 중간 | §3.5 |
| 6 | simulation_history 48일 집계 | 시그널 백테스트 시각화 | 낮음 | §3.6 |
| 7 | news_impact 뉴스 이중화 | 뉴스 커버리지 2배 | 낮음 | §3.7 |
| 8 | valuation 지표 확대 | 밸류에이션 3→8개 지표 | 낮음 | §3.8 |
| 9 | premarket 시황/미국시장 추가 | 장전 브리핑 맥락 강화 | 낮음 | §3.9 |
| 10 | short_squeeze 공매도 필드 활용 | 스퀴즈 탐지 정확도 | 낮음 | §3.10 |

### Tier 3: 신규 기능 (미구현 → 구현)

| # | 항목 | 영향 | 난이도 | 참조 |
|---|------|------|:---:|------|
| 11 | 장중 종목별 수급 추적기 | 실시간 수급 반전 포착 | 중간 | §4.1 |
| 12 | AI 예측 백테스트 대시보드 | 예측 성과 투명화 | 높음 | §4.2 |
| 13 | 매물대 지지/저항 경보 | 기술적 매매 근거 | 중간 | §4.3 |
| 14 | 시그널 소스 성과 비교 | 시그널 선택 근거 | 중간 | §4.4 |
| 15 | 연속 상승/하락 모니터 | 모멘텀/반등 스크리닝 | 낮음 | §4.5 |
| 16 | 매크로 트렌드 분석 | 시황 변화 추세 파악 | 낮음 | §4.6 |
| 17 | 증권사 수급 집중도 | 기관 수급 패턴 감지 | 중간 | §4.7 |
| 18 | 테마 예측 vs 실현 캘린더 | 중장기 예측 추적 | 높음 | §4.8 |

---

### 기대 효과 요약

| 지표 | 현재 | Tier 1 완료 후 | Tier 2 완료 후 | Tier 3 완료 후 |
|------|:---:|:---:|:---:|:---:|
| 프론트엔드 정상 파일 비율 | 79% | **93%** | **98%** | 100% |
| theme-analyzer 데이터 활용률 | 18.5% | **35%** | **60%** | **85%** |
| signal-pulse 데이터 활용률 | 60% | 65% | **80%** | **95%** |
| 빈 JSON 파일 수 | 6개 | **3개** | **0개** | 0개 |
