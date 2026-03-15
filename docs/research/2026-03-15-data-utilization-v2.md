# 데이터 활용 심층 재조사 보고서 (v2)

> 2026-03-15 기준 — 전수 조사 결과
> 이전 보고서(v1) 대비 필드 레벨까지 완전 분석

---

## 요약

| 지표 | 수치 |
|------|------|
| 전체 JSON 파일 | **482개** (Signal-Pulse 349 + Theme-Analyzer 133) |
| 전체 데이터 필드 | **~180개+** |
| 실제 사용 필드 | **~35개 (19%)** |
| 미사용 필드 | **~145개+ (81%)** |
| 미사용 파일 용량 | **~11MB** |

**핵심 발견:** `kis_gemini.json`(1.7MB)이 가장 풍부한 데이터 소스(60일 가격, 펀더멘탈, 호가잔량, RSI, PER/PBR/PEG, ROE)이지만 **완전히 미사용**.

---

## 1. Signal-Pulse 전체 파일 인벤토리

### 1A. KIS 디렉토리 (7파일 + 74 히스토리)

| 파일 | 크기 | 종목 수 | 주요 필드 | 사용 |
|------|------|:---:|------|:---:|
| `kis_latest.json` | 6.1MB | 100 | 현재가, OHLC, 거래량, 거래대금, 시가총액 | ❌ |
| `kis_analysis.json` | 333KB | 100 | 4차원 점수(기술/수급/밸류/재료), 종합점수, 신호, 근거, 리스크 | ❌ |
| `kis_gemini.json` | 1.7MB | 100 | **PER/PBR/EPS/BPS/PEG, ROE/OPM/부채비율, 호가잔량, 60일 OHLCV+RSI14, 외국인보유비율, 52주고저** | ❌ |
| `criteria_data.json` | 148KB | 100 | MA정배열, 신고가, 저항돌파, 공매도, 과열경고, 골든크로스 등 11개 | ⚠️ 3개만 |
| `fear_greed.json` | 249B | - | 점수, 등급, 1주/1달/1년 전 점수 | ⚠️ 점수만 |
| `vix.json` | 180B | - | 현재값, 변화율, 점수, 등급 | ⚠️ 현재값만 |
| `market_status.json` | 752B | 2 | KOSPI/KOSDAQ MA5~120, 상태, 신호조정 | ⚠️ 일부만 |
| `history/` | 74파일 | - | kis_analysis 일별 스냅샷 | ❌ |

### 1B. Vision 디렉토리 (1파일 + 77 히스토리)

| 파일 | 크기 | 종목 수 | 주요 필드 | 사용 |
|------|------|:---:|------|:---:|
| `vision_analysis.json` | 336KB | 98 | 4차원 점수, 신호, 뉴스분석, 신뢰도 | ❌ (combined 경유) |
| `history/` | 77파일 | - | vision 일별 스냅샷 | ❌ |

### 1C. Combined 디렉토리 (1파일 + 74 히스토리)

| 파일 | 크기 | 종목 수 | 주요 필드 | 사용 |
|------|------|:---:|------|:---:|
| `combined_analysis.json` | 880KB | 105 | 아래 상세 참조 | ⚠️ 6/18 필드 |
| `history/` | 74파일 | - | combined 일별 스냅샷 | ❌ |

#### combined_analysis.json 필드별 사용 현황

| 필드 | 사용 | 설명 |
|------|:---:|------|
| code, name, market | ✅ | 종목 식별 |
| vision_signal | ✅ | 매매 신호 |
| vision_confidence | ✅ | AI 신뢰도 |
| vision_news | ✅ | 뉴스 임팩트에 사용 |
| vision_reason | ❌ | 신호 판단 근거 |
| vision_news_analysis (sentiment, sentiment_score, key_news, catalyst) | ❌ | 뉴스 감성 점수 |
| **api_signal** | ❌ | **KIS 독립 신호 — 완전 무시** |
| **api_confidence** | ❌ | **KIS 신뢰도 — 완전 무시** |
| api_reason | ❌ | KIS 신호 근거 |
| api_news, api_news_analysis | ❌ | KIS 뉴스 분석 |
| **api_key_factors** (price_trend, volume_signal, foreign_flow 등) | ❌ | **사전 계산된 핵심 요인 — 완전 무시** |
| **api_risk_level** | ❌ | **사전 계산된 리스크 — 완전 무시** |
| **api_data** (price, ranking, valuation, recent_changes) | ❌ | **KIS 상세 데이터 — 완전 무시** |
| **match_status** (match/partial/mismatch) | ❌ | **Vision-KIS 일치 여부 — 완전 무시** |
| **confidence** (종합) | ❌ | **종합 신뢰도 — 완전 무시** |
| stats (match/mismatch 집계) | ❌ | 시장 전체 신호 일치도 |
| signal_counts | ❌ | 사전 집계 (재계산하고 있음) |

### 1D. Simulation 디렉토리 (41파일)

| 파일 | 내용 | 사용 |
|------|------|:---:|
| `simulation_index.json` | 41일분 시뮬레이션 목록 | ❌ |
| 41개 일별 파일 | return_pct, high_return_pct, stop_result 등 | ❌ |

### 1E. System 디렉토리

| 파일 | 내용 | 사용 |
|------|------|:---:|
| `key_alerts.json` | 알림 이력 (현재 비어있음) | ❌ |

---

## 2. Theme-Analyzer 전체 파일 인벤토리

### 2A. latest.json 19개 키별 사용 현황

| 키 | 타입 | 규모 | 사용 | 미사용 필드 |
|------|------|------|:---:|------|
| timestamp | str | 1 | ❌ | |
| **exchange** | dict | USD/JPY/EUR/CNY (rate, ttb, tts, change, change_rate) | ❌ | **환율 전체** |
| rising | dict | kospi 10 + kosdaq 10 | ✅ | current_price, change_price, volume, trading_value, market, is_etf, rank |
| falling | dict | kospi 2 + kosdaq 8 | ❌ | **로드만 하고 미사용** |
| volume | dict | kospi 30 + kosdaq 30 | ✅ | 동일 미사용 필드 |
| **trading_value** | dict | kospi 30 + kosdaq 30 | ❌ | **거래대금 TOP30 전체** |
| **fluctuation** | dict | 상승30+하락30 × 2시장 | ❌ | **등락률 분포 전체** |
| **fluctuation_direct** | dict | 직접 등락 | ❌ | **전체** |
| **history** | dict | 종목별 3일 시세 (OHLCV) | ❌ | **일별 시가/고가/저가/종가** |
| **news** | dict | 종목별 뉴스 목록 | ❌ | **theme-analyzer 뉴스 전체** |
| investor_data | dict | 165종목 | ✅ | program_net, name |
| investor_estimated | bool | 1 | ❌ | |
| theme_analysis | dict | 3개 테마 | ✅ | market_summary, analyzed_at, theme_description, leader valuation/news_evidence |
| **criteria_data** | dict | 종목별 14개 기준 | ❌ | **latest 내 criteria는 미사용 (combined 내 것만 사용)** |
| kospi_index | dict | 지수+MA | ✅ | |
| kosdaq_index | dict | 지수+MA | ⚠️ | 성능 리포트에만 사용, 대시보드 직접 표시 |
| **member_data** | dict | 종목별 증권사 매매 TOP5 (is_foreign 포함) | ❌ | **증권사별 순매수 전체** |
| investor_updated_at | str | 1 | ❌ | |
| program_trade | dict | 투자자별 차익/비차익 | ✅ | 패스스루 |

### 2B. 별도 파일

| 파일 | 크기 | 사용 | 활용 가능 데이터 |
|------|------|:---:|------|
| **theme-forecast.json** | 13KB | ❌ | AI 테마 예측(당일/단기/장기), 시장 컨텍스트, 미국 증시 요약, 촉매/리스크 |
| **macro-indicators.json** | 6.1KB | ❌ | 나스닥선물, KOSPI200선물, MU, SOXX, EWY, KORU, VIX, F&G + 환율 + **20일 투자자 동향** |
| **volume-profile.json** | 832KB | ❌ | 165종목 × 6개 기간(1년/6개월/3개월/1개월/1주/당일) × 가격대별 거래량 분포 + POC(핵심가격) |
| **investor-intraday.json** | 65KB | ❌ | 09:31~14:31 **5개 시점** 투자자별(외국인/기관/개인) 실시간 매매 |
| **indicator-history.json** | 4.7KB | ❌ | 매크로/환율 일별 히스토리 |
| intraday-history.json | 1.6MB | ⚠️ | 종목별 30분/60분봉 (패턴 매칭 시도했으나 구조 불일치) |
| history/ | 87파일 | ⚠️ | 라이프사이클에만 일부 사용 |
| **forecast-history/** | 18파일 | ❌ | **예측 적중률 검증 가능** |
| **paper-trading/** | 22파일 | ❌ | **모의투자 결과 (장중 가격 스냅샷 포함)** |

---

## 3. 미활용 데이터로 개선 가능한 기존 기능

### 3A. 즉시 개선 가능 (Tier 1)

| # | 개선 항목 | 미활용 데이터 | 영향 섹션 | 기대 효과 |
|---|----------|-------------|----------|----------|
| 1 | api_signal + vision_signal 이중 검증 | combined.api_signal, api_confidence, match_status | 교차 신호, 스마트 머니, 위험 종목 | 신호 신뢰도 +20% |
| 2 | 실제 PER/PBR/PEG 밸류에이션 | kis_gemini.valuation | 밸류에이션 스크리너 | 프록시 → 실데이터 |
| 3 | 실제 호가잔량 | kis_gemini.order_book | 호가창 압력 | 추정치 → 실데이터 |
| 4 | 매크로 8개 지표 전체 반영 | macro-indicators.json | 시장 심리 온도계, 프리마켓 | 2개 → 8개 지표 |
| 5 | 환율 데이터 | latest.exchange + macro-indicators.exchange | 시장 현황, 프리마켓 | 원/달러 등 표시 |
| 6 | Fear & Greed 추세 | fear_greed.previous_1_week/month/year | 시장 현황 | 현재값 → 추세 표시 |
| 7 | 테마 예측 표시 | theme-forecast.json | AI 브리핑 보강 | 당일/단기/장기 예측 |
| 8 | 실제 장중 투자자 동향 | investor-intraday.json | 시간대별 히트맵 | 합성 → 실데이터 |

### 3B. 중간 난이도 (Tier 2)

| # | 개선 항목 | 미활용 데이터 | 영향 섹션 |
|---|----------|-------------|----------|
| 9 | 펀더멘탈 분석 (ROE/OPM/부채/성장률) | kis_gemini.fundamental | 밸류에이션, 스캐너 |
| 10 | RSI 과매수/과매도 | kis_gemini.price_history.rsi_14 | 이상 거래, 위험 종목 |
| 11 | 60일 캔들 데이터 패턴 매칭 | kis_gemini.price_history (60일 OHLCV) | 차트 패턴 매칭 |
| 12 | 증권사 매매 동향 | member_data (buy/sell top5 + is_foreign) | 스마트 머니 |
| 13 | 거래대금 TOP30 | trading_value | 스캐너, 이상 거래 |
| 14 | 하락 종목 분석 | falling (로드만 하고 미사용) | 역발상, 위험 종목 |
| 15 | 종목별 프로그램 매매 | investor_data.program_net + criteria_data.program_trading | 프로그램 매매 |
| 16 | volume-profile 지지/저항 | volume-profile.json POC | 손절/익절 정밀화 |
| 17 | 신호 일관성 추적 | kis/vision/combined history (225파일) | 교차 신호 신뢰도 |

### 3C. 장기 개선 (Tier 3)

| # | 개선 항목 | 미활용 데이터 | 영향 섹션 |
|---|----------|-------------|----------|
| 18 | 시뮬레이션 히스토리 | simulation/ 41일분 | 시스템 성과 |
| 19 | 예측 적중률 검증 | forecast-history/ 18파일 | 시스템 성과 |
| 20 | 모의투자 성과 | paper-trading/ 22파일 | 전략 시뮬레이션 |
| 21 | criteria 전체 11개 항목 | criteria_data (8개 미사용) | 스캐너 필터 확장 |
| 22 | 52주 신고가 돌파 | criteria_data.high_breakout | 스캐너, 이상 거래 |
| 23 | 외국인 보유비율 | kis_gemini.market_info.foreign_holding_pct | 스마트 머니 |
| 24 | 거래회전율 | kis_gemini.trading.volume_turnover_pct | 이상 거래 |
| 25 | 시가총액 세그먼트 | kis_gemini.market_info.market_cap_billion | 밸류에이션 |

---

## 4. kis_gemini.json 상세 구조 (가장 풍부한 미활용 소스)

100종목 × 아래 필드:

```
ranking: volume_rank, volume_rate_vs_prev, trading_value
price: open, high, low, close, week_52_high, week_52_low
trading: volume, trading_value, volume_turnover_pct
market_info: market_cap_billion, shares_outstanding, foreign_holding_pct
valuation: PER, PBR, EPS, BPS, PEG
order_book: ask_volume_total, bid_volume_total, bid_ask_ratio, best_ask, best_bid
investor_flow: today {foreign, institution, individual}, 5_day {same}, daily_trend [{date, foreign, inst, indiv}]
foreign_institution: today/5d/20d {foreign_net, institution_net}
price_history: [{date, open, high, low, close, volume, rsi_14}] × 60일
recent_changes: [{date, change_rate}] × 6일
fundamental: ROE, OPM, debt_ratio, eps_growth, sales_growth, profit_growth
```

**이 파일 하나만 활용해도 밸류에이션, 호가창, 패턴매칭, 스마트머니가 대폭 개선됨.**

---

## 5. 결론

### 이전 보고서(v1) 대비 추가 발견

| 항목 | v1 | v2 |
|------|------|------|
| 전체 파일 수 | 24개로 추정 | **482개** 정확 집계 |
| 활용률 | 30% | **19%** (필드 레벨) |
| kis_gemini 분석 | "호가잔량 미사용" 1줄 | **13개 카테고리 × 100종목** 상세 매핑 |
| combined 내부 필드 | api_signal 미사용 언급 | **18개 필드 중 6개만 사용** 정확 집계 |
| 히스토리 파일 | "히스토리 있음" | **225개 히스토리 스냅샷** 정확 집계 |
| paper-trading | 미언급 | **22일분 장중 가격 스냅샷** 발견 |
| member_data | "증권사 매매" 1줄 | **is_foreign 포함 TOP5 매매** 구체화 |
| latest.json 키 | "7개 미사용" | **10개 미사용** (criteria_data, history, news 추가 발견) |
| macro-indicators | "8개 지표" | **8개 지표 + 환율 4개 + 투자자동향 20일** |
| volume-profile | "165종목" | **165종목 × 6개 기간 × POC가격** |

### 활용률을 19% → 80%+로 올리기 위한 핵심 3개

1. **kis_gemini.json 연동** — PER/PBR/ROE/호가잔량/RSI/60일가격 → 밸류에이션, 호가창, 패턴매칭, 스캐너 5개 섹션 대폭 개선
2. **api_signal + match_status 활용** — Vision 단독 → 이중 검증 → 교차신호, 스마트머니, 위험종목 3개 섹션 신뢰도 향상
3. **macro-indicators + theme-forecast 연동** — 글로벌 매크로 + AI 예측 → 심리온도계, 프리마켓, AI브리핑 3개 섹션 고도화
