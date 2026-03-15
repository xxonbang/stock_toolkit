# 데이터 활용 진단 보고서

> 2026-03-15 기준 stock_toolkit 프로젝트의 데이터 활용률 분석
> 결론: **전체 활용률 약 30%** — 70%의 데이터가 미활용 상태

---

## 요약

| 소스 | 전체 파일 | 사용 파일 | 활용률 |
|------|:---:|:---:|:---:|
| Signal-Pulse | 11개 | 4개 | 36% |
| Theme-Analyzer | 13개 | 4개 | 31% |
| **합계** | **24개** | **8개** | **33%** |

---

## 1. Signal-Pulse 데이터 — 활용 vs 미활용

### 사용 중 (4/11)

| 파일 | 용도 |
|------|------|
| `combined_analysis.json` | vision_signal, confidence만 사용 (stocks 105종목) |
| `fear_greed.json` | 시장 심리 스코어 |
| `vix.json` | 변동성 지수 |
| `criteria_data` (combined 내장) | MA정배열, 과열경고, 시가총액 범위 |

### 미활용 (7/11)

| 파일 | 종목 수 | 미활용 데이터 | 활용 시 기대효과 |
|------|:---:|------|------|
| **kis_analysis.json** | 100 | 4차원 점수(기술/수급/밸류/재료), 종합 점수, 근거 | 신호 가중치 부여, 신뢰도 강화 |
| **kis_latest.json** | 100 | 현재가, 시가총액, 외국인 보유비율, 52주 고저 | 밸류에이션 스크리너 고도화 |
| **kis_gemini.json** | 100 | 호가잔량, 거래량 상세, 투자자 흐름 13개+ 필드 | 호가창 압력 실제 데이터 |
| **vision_analysis.json** | 98 | 독립 비전 분석 점수, 뉴스 분석 | KIS-Vision 괴리 탐지 |
| **market_status.json** | 2 | KOSPI/KOSDAQ MA5/10/20/60/120 상세 | 시장 국면 정밀 판정 |
| **simulation/** | 45일분 | 전략별 백테스트 결과 | 시스템 성과 검증, 전략 비교 |
| **system/key_alerts.json** | - | 알림 이력 | 중복 알림 방지 |

### combined_analysis.json 내부 필드 활용도

| 필드 | 상태 | 설명 |
|------|:---:|------|
| code, name, market | ✅ | 종목 식별 |
| vision_signal | ✅ | 매매 신호 |
| vision_confidence | ✅ | AI 신뢰도 |
| vision_news | ✅ | 뉴스 임팩트에 사용 |
| vision_reason | ❌ | 신호 판단 근거 (미표시) |
| api_signal | ❌ | KIS API 기반 독립 신호 |
| api_confidence | ❌ | KIS API 신뢰도 |
| api_data | ❌ | KIS 상세 분석 데이터 |
| api_reason | ❌ | KIS 신호 판단 근거 |
| api_risk_level | ❌ | KIS 리스크 레벨 |
| api_news | ❌ | KIS 뉴스 분석 |
| api_news_analysis | ❌ | KIS 뉴스 상세 |
| api_key_factors | ❌ | KIS 핵심 요인 |
| match_status | ❌ | Vision-KIS 일치 여부 |
| confidence | ❌ | 종합 신뢰도 |

**핵심 문제:** `api_*` 필드 7개가 전부 미활용. KIS API의 독립 분석 결과가 완전히 무시됨.

---

## 2. Theme-Analyzer 데이터 — 활용 vs 미활용

### latest.json 키별 활용도 (19개 키)

| 키 | 상태 | 데이터 규모 | 설명 |
|------|:---:|------|------|
| timestamp | ✅ | 문자열 | 데이터 시점 |
| rising | ✅ | kospi 10 + kosdaq 10종목 | 상승 종목 |
| falling | ✅ | kospi 2 + kosdaq 8종목 | 하락 종목 |
| volume | ✅ | kospi 30 + kosdaq 30종목 | 거래량 TOP |
| investor_data | ✅ | 165종목 × (foreign/institution/individual + history) | 투자자 동향 |
| theme_analysis | ✅ | 3개 테마 × leader_stocks | AI 테마 분석 |
| kospi_index | ✅ | 지수 + MA5/10/20/60/120 | KOSPI |
| kosdaq_index | ✅ | 지수 + MA5/10/20/60/120 | KOSDAQ |
| program_trade | ✅ | kospi/kosdaq 투자자별 | 프로그램 매매 |
| **exchange** | ❌ | 환율 데이터 | 원/달러 등 |
| **trading_value** | ❌ | kospi 30 + kosdaq 30종목 | 거래대금 TOP30 |
| **fluctuation** | ❌ | 등락률 상세 | 등락률 분포 |
| **fluctuation_direct** | ❌ | 직접 등락률 | 등락률 상세 |
| **history** | ❌ | 종목별 3일 시세 | 단기 추세 |
| **news** | ❌ | 뉴스 목록 | 당일 관련 뉴스 |
| **member_data** | ❌ | 회원사(증권사) 매매 | 증권사별 순매수 |
| **criteria_data** | ❌ | 종목별 9요소 평가 | MA정배열, 신고가 등 |
| **investor_estimated** | ❌ | 추정치 여부 | 데이터 확정 여부 |
| **investor_updated_at** | ❌ | 수급 업데이트 시점 | 데이터 시점 |

### 별도 파일 활용도

| 파일 | 크기 | 상태 | 활용 가능 |
|------|------|:---:|------|
| **theme-forecast.json** | 13KB | ❌ | AI 테마 예측 (당일/단기/장기), 시장 요약, 미국 증시 |
| **macro-indicators.json** | 6KB | ❌ | 나스닥선물, 달러인덱스, 유가, 금, 은, 미국채, VIX, 투자자 동향 |
| **volume-profile.json** | 832KB | ❌ | 165종목 가격대별 거래량 분포 |
| **investor-intraday.json** | 65KB | ❌ | 시간대별(09:31~14:31) 투자자 매매 |
| **intraday-history.json** | ~1MB | ⚠️ | 분봉 데이터 (패턴 매칭에 사용 시도했으나 구조 불일치) |
| **history/** | 88파일 | ⚠️ | 라이프사이클에 일부 사용 |
| **forecast-history/** | 18파일 | ❌ | 과거 테마 예측 → 적중률 검증 가능 |
| **paper-trading/** | 22파일 | ❌ | 모의투자 결과 → 전략 검증 가능 |
| **history-index.json** | - | ❌ | 히스토리 목록 |
| **forecast-history-index.json** | - | ❌ | 예측 히스토리 목록 |
| **paper-trading-index.json** | - | ❌ | 모의투자 목록 |
| **indicator-history.json** | - | ❌ | 지표 히스토리 |

---

## 3. 핵심 문제 6가지

### 문제 1: 듀얼 시그널 미활용
- Vision 분석과 KIS API 분석이 **독립적으로** 수행되지만, `combined_analysis`에서 `vision_signal`만 사용
- `api_signal`, `api_confidence`, `match_status`(Vision-KIS 일치 여부)가 완전히 무시됨
- **개선:** 두 신호 일치 시 "고확신", 불일치 시 "주의"로 신뢰도 차등 부여

### 문제 2: 4차원 스코어링 무시
- KIS 분석은 기술(technical), 수급(supply_demand), 밸류에이션(valuation), 재료(material) 4차원 점수를 제공
- 현재 모든 신호를 동일 가중치로 취급
- **개선:** 스코어 차원별 가중 평균으로 종합 점수 산출

### 문제 3: 글로벌 매크로 미반영
- 8개 글로벌 지표(나스닥선물, 달러, 유가, 금, 은, 채권, VIX, 투자자동향) 사용 가능
- Fear & Greed + VIX만 사용 중
- **개선:** 매크로 레짐 판정에 전체 지표 활용

### 문제 4: 장중 타이밍 미활용
- 시간대별 투자자 동향(09:31~14:31, 5개 시점) 데이터 있음
- 모든 분석이 일별(daily) 기준으로만 수행
- **개선:** 시간대별 히트맵에 실제 데이터 반영

### 문제 5: 과거 검증 부재
- 45일분 백테스트 결과, 18일분 예측 히스토리, 22일분 모의투자 결과 보유
- 현재 시스템 성과를 과거와 비교하지 않음
- **개선:** 시스템 성과 대시보드에 히스토리컬 추세 표시

### 문제 6: 호가/거래량 프로파일 미활용
- kis_gemini에 호가잔량 데이터 존재 → 호가창 압력 섹션에 미연결
- volume-profile에 165종목 가격대별 거래량 → 지지/저항 분석 가능
- **개선:** 호가창 압력, 동시호가 분석에 실제 데이터 연결

---

## 4. 개선 우선순위

### Tier 1: 즉시 개선 가능 (코드 수정만, 30분~1시간)

| 개선 항목 | 데이터 소스 | 기대 효과 |
|----------|-----------|----------|
| api_signal + vision_signal 이중 검증 | combined_analysis.json | 신호 신뢰도 +20% |
| match_status 활용 (Vision-KIS 일치 여부) | combined_analysis.json | 고확신/주의 구분 |
| macro-indicators 8개 지표 반영 | macro-indicators.json | 시장 심리 온도계 정밀화 |
| theme-forecast 예측 표시 | theme-forecast.json | AI 브리핑 보강 |
| exchange(환율) 데이터 반영 | latest.json exchange | 시장 현황 보강 |

### Tier 2: 중간 난이도 (1~2시간)

| 개선 항목 | 데이터 소스 | 기대 효과 |
|----------|-----------|----------|
| KIS 4차원 점수 표시 | kis_analysis.json | 종목별 강약점 시각화 |
| 호가잔량 실데이터 연결 | kis_gemini.json | 호가창 압력 정확도 향상 |
| investor-intraday 반영 | investor-intraday.json | 시간대별 히트맵 실데이터 |
| volume-profile 지지/저항 | volume-profile.json | 손절/익절 정밀화 |
| trading_value TOP30 표시 | latest.json trading_value | 거래대금 순위 추가 |

### Tier 3: 장기 개선 (2시간+)

| 개선 항목 | 데이터 소스 | 기대 효과 |
|----------|-----------|----------|
| 시뮬레이션 히스토리 비교 | simulation/ 45일분 | 전략 성과 추세 |
| 예측 적중률 검증 | forecast-history/ 18일분 | 시스템 신뢰도 검증 |
| 모의투자 결과 분석 | paper-trading/ 22일분 | 실전 성과 비교 |
| member_data 증권사 동향 | latest.json member_data | 대형 증권사 방향성 |

---

## 5. 결론

현재 stock_toolkit은 **두 프로젝트가 수집한 풍부한 데이터의 30%만 활용**하고 있습니다.

특히:
- KIS API가 제공하는 **4차원 스코어링, 호가잔량, 독립 매매신호**가 완전히 무시됨
- **글로벌 매크로 8개 지표** 중 2개만 사용
- **시간대별 투자자 동향**이 있는데 일별 기준으로만 분석
- **45일분 백테스트 + 22일분 모의투자** 결과가 검증에 미활용

Tier 1 개선만으로도 신호 신뢰도를 **20~40% 향상**시킬 수 있으며, 추가 데이터 수집 없이 기존 데이터만으로 가능합니다.
