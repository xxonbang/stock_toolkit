# Dashboard 섹션 중복/유사성 분석 및 통폐합 연구

## 개요

Dashboard.tsx(2,516줄)의 31개 섹션에 대해 중복/유사 콘텐츠를 분석하고 통폐합 방안을 도출한 연구 문서.

- **분석 대상:** results/ 디렉토리 50개 JSON 파일 + Dashboard.tsx 31개 섹션 렌더링
- **분석 날짜:** 2026-03-22
- **1차 분석:** 데이터 구조 + 렌더링 비교로 6개 통폐합 그룹 도출
- **2차 재검토:** 각 그룹의 고유 정보/관점/효용 정밀 검증 → 원안 수정

---

## 최종 통폐합 안 (2차 재검토 반영)

### 그룹 A: 신호 기반 — signals를 cross에 흡수, consecutive 독립 유지

**원안:** 3개(signals + consecutive + cross) → 1개
**수정안:** signals를 cross에 흡수 (2개→1개), **consecutive 독립 유지**

| 섹션 | 고유 정보 | 판정 |
|------|----------|------|
| `signals` | 신호 강도 분류(적극매수/매수), 전체 분석 규모 통계 | → **cross에 흡수** (배지 추가) |
| `consecutive` | 연속 일수(streak), AND/OR 논리 조합, 날짜 이력(dates[]), 누적 등장일 | → **독립 유지** |
| `cross` | 실시간 유효성(intraday validation), 신호 나이(signal_age_hours), 이중 신호, 테마, 뉴스 | → **signals 흡수하여 확장** |

**수정 근거:**
- 실제 종목 중복도: 3개 파일 모두 포함 종목 = **1개(SK이터닉스)**뿐 → 중복 매우 낮음
- 각 섹션이 답하는 질문이 다름:
  - signals: "**뭘** 살까?" (종목 목록)
  - consecutive: "**얼마나 오래** 유지됐나?" (시간적 지속성)
  - cross: "지금 **유효한가**?" (실시간 검증)
- consecutive의 시계열 데이터(streak, dates[], total_days)는 cross에 없으므로 통합 시 손실

---

### 그룹 B: 시뮬레이션 — 통합 적합 (변경 없음)

**원안 유지:** 2개(simulation + sim_history) → 1개

| 섹션 | 고유 정보 | 판정 |
|------|----------|------|
| `simulation` | 전략별 누적 통계 (3전략 × 거래수/승률/수익률) | → 통합 상단 |
| `sim_history` | 날짜별 일일 통계 (by_category 현재 미렌더링) | → 통합 하단 (히스토리) |

**근거:** 동일 지표(거래수, 승률, 수익률)의 현재/과거 뷰. sim_history의 `by_category`(vision/kis/combined)는 현재도 미렌더링이므로 손실 없음. 1개 섹션에 현재 성과 + 히스토리 추이를 함께 표시.

---

### 그룹 C: 스코어/랭킹 — 독립 유지 (원안 철회)

**원안:** 2개(smartmoney + valuation) → 1개
**수정안:** **독립 유지** (통합 부적절)

| 섹션 | 고유 정보 | 판정 |
|------|----------|------|
| `smartmoney` | dual_signal, intraday validation, 뉴스 카탈리스트, **수급 관점** 스코어 | → **독립 유지** |
| `valuation` | PER/PBR/ROE/영업이익률/부채비율, 이동평균 정배열, **펀더멘탈 관점** 스코어 | → **독립 유지** |

**수정 근거:**
- 종목 40% 겹침이지만, 겹치는 종목에서도 **표시 정보가 완전히 다름**
- SmartMoney에는 재무지표(PER/PBR/ROE) 없음
- Valuation에는 뉴스/신호/intraday 없음
- 둘 다 "TOP 랭킹" 형태지만 평가 차원이 **수급 vs 펀더멘탈**로 근본적으로 다름

---

### 그룹 D: 수급 흐름 — sector+member 통합, heatmap·intraday_flow 독립

**원안:** 4개 → 1개
**수정안:** sector+member 통합 (2개→1개), **heatmap·intraday_flow 독립 유지**

| 섹션 | 고유 정보 | 관점 | 판정 |
|------|----------|------|------|
| `heatmap` | **시간대별** 외국인/기관 순매매 추이 | 시간축 | → **독립 유지** |
| `intraday_flow` | **종목별** 외국인/기관 순매수 + 현재가/변동률 | 종목축 | → **독립 유지** |
| `sector` | **테마별** 외국인 순매수 + 종목수 | 테마축 | → **member와 통합** |
| `member` | **증권사별** 외국인 순매수 + 매수 TOP5 | 증권사축 | → **sector와 통합** |

**수정 근거:**
- 4개 모두 "외국인 수급"이지만 **관점 축이 완전히 다름** (시간/종목/테마/증권사)
- heatmap의 시간대별 추이는 다른 섹션에서 대체 불가
- intraday_flow의 종목별 현재가+변동률은 고유
- sector와 member는 모두 "상위 수준 자금 흐름"으로 탭 전환에 적합

---

### 그룹 E: 테마 분석 — 통합 적합 (변경 없음)

**원안 유지:** 2개(lifecycle + propagation) → 1개

| 섹션 | 고유 정보 | 판정 |
|------|----------|------|
| `lifecycle` | 테마 단계(탄생/성장/과열), 평균수익률, 버블차트, **strategy 미렌더링** | → 통합 상단 |
| `propagation` | 리더→팔로워 전이 경로, 예상 전이 시간(lag_minutes) | → 통합 하단 |

**근거:** 동일 3개 테마를 다름. lifecycle의 미사용 필드(`strategy`: "초기 진입 기회" 등)를 통합 시 표시하면 오히려 정보 증가. briefing의 테마 부분은 AI 해석 성격이므로 별도 유지.

---

### 그룹 F: 이상치 감지 — anomaly+gap 통합, divergence 독립

**원안:** 3개 → 1개
**수정안:** anomaly+gap 통합 (2개→1개), **divergence 독립 유지**

| 섹션 | 고유 정보 | 감지 기준 | 판정 |
|------|----------|----------|------|
| `anomaly` | 거래량 배율(ratio), 이상 유형(가격급변/거래량폭발) | 절대적 이상치 | → **gap과 통합** |
| `gap` | 갭 방향/크기, **메꿈 확률(fill_probability)** | 시가 갭 | → **anomaly와 통합** |
| `divergence` | 괴리 유형, interpretation(미렌더링), 거래량-가격 불일치 | 상대적 괴리 | → **독립 유지** |

**수정 근거:**
- anomaly의 `change_rate`와 gap의 `gap_pct`가 거의 동일 (우리로: 29.98% = 29.98%)
- 종목 중복도 높음 (2/3 이상 겹침)
- 하지만 gap의 **메꿈 확률**은 고유한 예측 정보 → 통합 시 반드시 포함
- divergence는 "거래량↔가격 불일치"라는 근본적으로 다른 관점 + 고유 종목 존재 (라온피플 등)

---

## 약한 중복 — 현행 유지 (변경 없음)

| 섹션 ID | 이유 |
|---------|------|
| `premarket` | 장 시작 전 전용, 시간대 특화 |
| `briefing` | AI 종합 분석, 다른 섹션과 성격 다름 |
| `market` | 시장 전체 지표, 종목 단위 아님 |
| `risk` | 위험 경고 전용, 매수 신호와 반대 관점 |
| `exit` | 매매 실행 가이드, 분석이 아님 |
| `pattern` | 차트 패턴 매칭, 고유한 분석 방법론 |
| `news` | 뉴스 기반, 수치 분석과 완전히 다름 |
| `insider` | 내부자 거래 공시, 고유 데이터 |
| `events` | 이벤트 일정, 고유 데이터 |
| `earnings` | 실적 공시 일정, 고유 데이터 |
| `orderbook` | 실시간 호가, 고유 관점 |
| `auction` | 동시호가 전용, 시간대 특화 |
| `consensus` | 애널리스트 목표가, 고유 데이터 |
| `correlation` | 종목쌍 상관도, 고유 관점 |
| `volume_profile` | 매물대 가격대, 고유 분석 |
| `consistency` | 신호 안정성 추적, 보조 지표 |
| `paper_trading` | 모의투자 성과, 고유 데이터 |
| `trading_value` | 거래대금 순위, 고유 관점 |
| `journal` | 매매 일지, 고유 데이터 |
| `mentor` | AI 조언, 고유 성격 |
| `forecast` | 예측 적중률, 성과 추적 |
| `squeeze` | 역발상 신호, 공매도 특화 |
| `program` | 프로그램 매매, 기관 차익거래 특화 |

---

## 최종 효과 예상

| 항목 | 현재 | 통폐합 후 | 감소 |
|------|------|----------|------|
| 섹션 수 | 31개 | **~26개** | -5개 |
| API 호출 | 42개 | **~37개** | -5개 |

**원안(31→20) 대비 보수적이지만, 정보 누락 제로를 보장.**

---

## 통폐합 우선순위

| 순위 | 그룹 | 변경 내용 | 복잡도 | 비고 |
|------|------|----------|--------|------|
| 1 | B | simulation + sim_history → 1개 | **낮음** | 동일 지표, 가장 안전 |
| 2 | E | lifecycle + propagation → 1개 | **낮음** | 동일 테마, strategy 필드 추가 가능 |
| 3 | F | anomaly + gap → 1개 (divergence 독립) | **중간** | 종목/수치 거의 동일, 메꿈확률 보존 |
| 4 | A | signals를 cross에 흡수 (consecutive 독립) | **중간** | signals의 강도 배지를 cross에 추가 |
| 5 | D | sector + member → 1개 (heatmap·flow 독립) | **중간** | 테마/증권사 탭 전환 |

---

## 부록: 2차 재검토에서 발견된 미활용 데이터

통폐합과 별개로, 현재 렌더링하지 않는 유용한 데이터 필드:

| 파일 | 필드 | 내용 | 활용 제안 |
|------|------|------|----------|
| `lifecycle.json` | `strategy` | "초기 진입 기회", "추세 추종" 등 | 테마 통합 섹션에서 전략 가이드로 표시 |
| `volume_divergence.json` | `interpretation` | "매도 물량 고갈 주의", "세력 매집" 등 | divergence 섹션에 해석 텍스트 추가 |
| `simulation_history.json` | `by_category` | vision/kis/combined 카테고리별 통계 | 통합 시뮬레이션에서 소스별 성과 비교 |
| `intraday_stock_flow.json` | `individual` | 개인 투자자 순매매 | 수급 섹션에 개인 투자자 흐름 추가 |

---

## 참고: 데이터 수준 중복 상세

### JSON 파일 간 종목 중복도

| 파일 쌍 | 공통 종목 수 | 비고 |
|---------|------------|------|
| pattern ↔ cross_signal | 4/4 (100%) | 완전 동일 대상 |
| volume_profile ↔ volume_profile_alerts | 19/25 (76%) | 같은 기반 다른 필터 |
| anomalies ↔ scanner_stocks | 27/34 (79%) | 대부분 스캐너 종목 |
| risk_monitor ↔ scanner_stocks | 22/22 (100%) | 스캐너 부분집합 |
| anomalies ↔ gap_analysis | ~67% | change_rate ≈ gap_pct 수치 동일 |
| smart_money ↔ valuation | 8/20 (40%) | 종목 겹침 있으나 필드 완전히 다름 |
| cross_signal ∩ consecutive ∩ consistency | 1/전체 | SK이터닉스만 3파일 공통 |
