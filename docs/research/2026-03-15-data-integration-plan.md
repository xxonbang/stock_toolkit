# 데이터 통합 개선 계획서

> 2026-03-15 — 데이터 활용 심층 재조사(v2) 결과 기반
> 목표: 데이터 활용률 19% → 80%+ 달성

---

## 1. 현황 분석

### 1.1 문제 정의

stock_toolkit은 두 외부 프로젝트(signal-pulse, theme-analyzer)가 수집한 **482개 JSON 파일, ~30MB의 정형 데이터**를 활용하지만, 실제 사용률은 필드 레벨 기준 **19%**에 불과하다. 나머지 81%의 데이터는 수집되었으나 분석 파이프라인에 연결되지 않은 상태다.

### 1.2 핵심 원인

| 원인 | 설명 | 영향 |
|------|------|------|
| 단일 신호 의존 | Vision 분석의 `vision_signal`만 사용, KIS API의 독립 분석(`api_signal`) 완전 무시 | 신호 신뢰도 저하, 이중 검증 불가 |
| 데이터 키 불일치 | `run_all.py`가 참조하는 키(rising_stocks, leaders)가 실제 데이터 구조(rising.kospi, leader_stocks)와 다름 | 빈 데이터 빈번 발생 |
| DataLoader 불완전 | `get_kis_signals()`, `get_volume_profile()` 등 메서드가 존재하나 `run_all.py`에서 호출하지 않음 | 풍부한 데이터 접근 경로 미사용 |
| 최대 데이터 소스 미연결 | `kis_gemini.json`(1.7MB, 100종목 × 13개 카테고리)이 DataLoader에도 없고 어디서도 로드하지 않음 | PER/PBR/호가/RSI/펀더멘탈 전체 미활용 |

### 1.3 영향 범위

```
현재 데이터 흐름:
signal-pulse ──→ combined_analysis.json ──→ vision_signal만 추출 ──→ 대시보드
                                             (api_signal 무시)
                                             (api_data 무시)
                                             (match_status 무시)

theme-analyzer ──→ latest.json ──→ rising/volume/investor_data만 추출 ──→ 대시보드
                                    (exchange 무시)
                                    (trading_value 무시)
                                    (member_data 무시)
                                    (news 무시)
                                    (criteria_data 무시)
                                    (history 무시)

kis_gemini.json ──→ (아무도 로드하지 않음) ──→ PER/PBR/호가/RSI/펀더멘탈 전체 사장

개선 후 데이터 흐름:
signal-pulse ──→ combined_analysis ──→ vision_signal + api_signal + match_status ──→ 이중 검증
             ──→ kis_gemini.json ──→ PER/PBR/호가/RSI/60일가격/펀더멘탈 ──→ 5개 섹션 고도화
             ──→ kis_analysis.json ──→ 4차원 점수 ──→ 종목 스코어카드
             ──→ simulation/ 41일 ──→ 시스템 성과 검증

theme-analyzer ──→ latest.json 전체 19개 키 활용
               ──→ theme-forecast.json ──→ AI 브리핑 보강
               ──→ macro-indicators.json ──→ 심리온도계 고도화
               ──→ volume-profile.json ──→ 지지/저항 + 손절 정밀화
               ──→ investor-intraday.json ──→ 시간대별 히트맵 실데이터
               ──→ paper-trading/ 22일 ──→ 전략 검증
```

---

## 2. 개선 계획

### 2.1 Tier 1: 즉시 개선 (기존 섹션에 실제 데이터 연결)

#### T1-1. 이중 신호 검증 (교차 신호, 스마트 머니, 위험 종목)

**현재:** `vision_signal` 하나만 사용. KIS API의 독립 분석 결과가 같은 파일에 있지만 무시됨.

**개선:**
```
현재:
  신호 = vision_signal ("매수")
  → 단일 소스 판단

개선 후:
  신호A = vision_signal ("매수")
  신호B = api_signal ("적극매수")
  일치도 = match_status ("match")
  종합 신뢰도 = confidence (0.82)

  → 둘 다 매수 = "고확신 매수" (빨강 강조)
  → 하나만 매수 = "매수 (확인 필요)" (주황)
  → 불일치 = "신호 혼조" (회색)
```

**영향 섹션:** 교차 신호, 스마트 머니 TOP, 위험 종목 모니터, 종목 스캐너
**기대 효과:** 거짓 신호(false positive) 20~30% 감소

#### T1-2. 실제 밸류에이션 (밸류에이션 스크리너)

**현재:** `criteria_data.market_cap_range` + `ma_alignment`으로 프록시 점수 산출. PER/PBR 없음.

**개선:**
```
현재:
  점수 = MA정배열(+25) + 시가총액적정(+50) + 매수신호(+15) + 외국인매수(+10)
  → 가치 투자와 무관한 기술적 지표 조합

개선 후:
  kis_gemini.json에서:
  PER = 12.5 (업종 평균 18.3 → 저평가)
  PBR = 0.8 (자산가치 대비 할인)
  PEG = 0.6 (성장 대비 저평가)
  ROE = 15.2% (양호)
  부채비율 = 42% (안정)

  점수 = PER 순위(25%) + PBR(20%) + PEG(20%) + ROE(15%) + 부채(10%) + 성장(10%)
  → 진정한 가치 투자 스크리너
```

**영향 섹션:** 밸류에이션 스크리너
**기대 효과:** 프록시 → 실제 펀더멘탈 기반 스크리닝

#### T1-3. 실제 호가잔량 (호가창 압력)

**현재:** `investor_data.foreign_net` 기반 추정치. 실제 호가 데이터 미사용.

**개선:**
```
현재:
  매수 압력 = 50% + (외국인순매수 / 50000)
  → 외국인 수급으로 간접 추정

개선 후:
  kis_gemini.json에서:
  ask_volume_total = 1,250,000 (매도 대기)
  bid_volume_total = 2,100,000 (매수 대기)
  bid_ask_ratio = 1.68 (매수 우위)
  best_ask = 132,500원 (1호가 매도)
  best_bid = 132,000원 (1호가 매수)

  → 실제 매수벽/매도벽 + 비율 게이지 표시
```

**영향 섹션:** 호가창 압력
**기대 효과:** 추정치 → 실제 호가 데이터

#### T1-4. 글로벌 매크로 종합 (시장 심리 온도계)

**현재:** Fear & Greed + VIX 2개만 사용. 6개 추가 지표 미사용.

**개선:**
```
현재 센티멘트 구성:
  F&G (20%) + VIX (20%) + KOSPI이격도 (15%) + 외국인수급 (20%) + 기타 (25%)
  → 2개 글로벌 + 2개 국내

개선 후:
  macro-indicators.json에서:
  나스닥선물(NQ=F) → 글로벌 기술주 방향
  KOSPI200선물 → 국내 선물 방향
  마이크론(MU) → 반도체 선행지표
  SOXX → 반도체 ETF
  EWY → 한국 ETF (글로벌 시각)
  KORU → 한국 3배 레버리지
  VIX → 변동성
  F&G → 심리

  + exchange에서:
  USD/KRW 환율 변동 → 수출주 영향

  + investor_trend (20일):
  외국인/기관/개인 일별 순매수 추세

  → 10개+ 지표 종합 센티멘트
```

**영향 섹션:** 시장 심리 온도계, 프리마켓 모니터
**기대 효과:** 2개 → 10개+ 지표로 시장 심리 정밀 판정

#### T1-5. 환율 데이터 (시장 현황)

**현재:** 시장 현황에 KOSPI/KOSDAQ/F&G/VIX만 표시. 환율 없음.

**개선:**
```
latest.json.exchange에서:
  USD: { rate: 1452.5, change: +5.2, change_rate: +0.36% }
  JPY: { rate: 965.8, change: -2.1, change_rate: -0.22% }
  EUR: { rate: 1578.3, change: +3.8 }
  CNY: { rate: 199.5, change: +0.5 }

  → 시장 현황 섹션에 원/달러, 원/엔 등 환율 표시
  → 프리마켓 모니터에 환율 방향 포함
```

**영향 섹션:** 시장 현황, 프리마켓 모니터
**기대 효과:** 수출주/환율 민감 종목 판단 근거 제공

#### T1-6. Fear & Greed 추세 (시장 현황)

**현재:** F&G 현재 점수(19.7)만 표시.

**개선:**
```
fear_greed.json에서:
  현재: 19.7 (극단적 공포)
  1주 전: 25.1 → ▼5.4p 하락 중
  1달 전: 37.8 → ▼18.1p 급락
  1년 전: 15.2 → ▲4.5p (작년보다는 양호)

  → 추세 화살표 + 1주/1달/1년 비교 표시
  → "1달간 18p 하락 — 공포 심화 중" 해석 추가
```

**영향 섹션:** 시장 현황
**기대 효과:** 현재값 → 방향성 판단

#### T1-7. AI 테마 예측 (AI 모닝 브리프)

**현재:** 모닝 브리프에 테마 예측 미포함. `theme-forecast.json`이 존재하지만 미사용.

**개선:**
```
theme-forecast.json에서:
  market_context: "글로벌 긴축 완화 기대..."
  us_market_summary: "S&P +0.8%, 나스닥 +1.2%..."
  today: [
    { theme_name: "2차전지", confidence: 0.85, catalyst: "유럽 보조금 확대", risk: "원자재 가격" },
    { theme_name: "AI반도체", confidence: 0.72, catalyst: "엔비디아 실적", risk: "밸류에이션" },
  ]

  → AI 브리핑에 "오늘의 주목 테마 예측" 섹션 추가
  → 각 테마별 신뢰도, 촉매, 리스크 표시
```

**영향 섹션:** AI 모닝 브리프
**기대 효과:** 단순 시황 → 테마 예측 포함 종합 브리핑

#### T1-8. 실제 장중 투자자 동향 (시간대별 히트맵)

**현재:** 합성 데이터 `{str(h): round((h-12)*0.1+0.5, 2) for h in range(9,16)}` 사용. 가짜 데이터.

**개선:**
```
investor-intraday.json에서:
  snapshots: [
    { time: "09:31", data: { 외국인: +520억, 기관: -180억, 개인: -340억 } },
    { time: "10:31", data: { 외국인: +780억, 기관: -250억, 개인: -530억 } },
    { time: "11:31", data: { 외국인: +1,200억, 기관: -380억, 개인: -820억 } },
    { time: "13:31", data: { 외국인: +1,050억, 기관: -420억, 개인: -630억 } },
    { time: "14:31", data: { 외국인: +950억, 기관: -350억, 개인: -600억 } },
  ]

  → 시간대별 외국인/기관/개인 매수세 히트맵 (실데이터)
  → "외국인 오전 집중 매수 패턴" 등 해석 추가
```

**영향 섹션:** 시간대별 수익률 히트맵
**기대 효과:** 가짜 데이터 → 실제 장중 투자자 동향

---

### 2.2 Tier 2: 중간 난이도 (기존 섹션 보강)

#### T2-9. 펀더멘탈 분석

**데이터:** `kis_gemini.json` → `fundamental` (ROE, OPM, debt_ratio, eps_growth, sales_growth, profit_growth)

**적용:** 밸류에이션 스크리너에 펀더멘탈 탭 추가, 스캐너 필터에 "ROE > 15%" 등 조건 추가

#### T2-10. RSI 과매수/과매도

**데이터:** `kis_gemini.json` → `price_history[].rsi_14`

**적용:**
- RSI > 70: 이상 거래에 "과매수 경고" 추가
- RSI < 30: 역발상 시그널에 "과매도 반등 후보" 추가
- 위험 종목에 RSI 극단값 경고

#### T2-11. 60일 캔들 데이터 패턴 매칭

**데이터:** `kis_gemini.json` → `price_history` (60일 OHLCV)

**적용:** 현재 `intraday-history.json`의 구조 불일치로 빈 데이터인 패턴 매칭을 `kis_gemini`의 60일 일봉 데이터로 대체. 코사인 유사도 기반 과거 패턴 검색.

#### T2-12. 증권사 매매 동향

**데이터:** `latest.json` → `member_data` (종목별 buy_top5, sell_top5, is_foreign 포함)

**적용:**
```
삼성전자 (005930):
  매수 TOP5:
  1. 모건스탠리 (외국계) — 15.2만주
  2. 골드만삭스 (외국계) — 12.8만주
  3. NH투자 — 8.5만주

  매도 TOP5:
  1. 미래에셋 — 22.1만주
  2. 키움 — 18.3만주

  → 외국계 증권사 집중 매수 = 스마트 머니 신호 강화
```

#### T2-13. 거래대금 TOP30

**데이터:** `latest.json` → `trading_value` (kospi 30 + kosdaq 30)

**적용:** 스캐너에 "거래대금 TOP30" 필터 추가. 거래대금 상위 = 기관 관심 종목.

#### T2-14. 하락 종목 분석

**데이터:** `latest.json` → `falling` (kospi + kosdaq)

**현재:** `falling_stocks`를 로드하지만 반복문에서 사용하지 않음.

**적용:**
- 하락 종목 중 거래량 급증 = 투매 징후 (위험 종목에 추가)
- 하락 종목 중 외국인 순매수 = 역발상 매수 기회 (역발상 시그널에 추가)

#### T2-15. 종목별 프로그램 매매

**데이터:** `investor_data.*.program_net` + `criteria_data.*.program_trading`

**현재:** `program_trade`를 시장 전체 합계로만 패스스루. 종목별 데이터 미사용.

**적용:** 프로그램 매매 섹션에 종목별 프로그램 순매수/순매도 표시. 프로그램 대량 매수 종목 하이라이트.

#### T2-16. Volume Profile 지지/저항

**데이터:** `volume-profile.json` (165종목 × 6기간 × POC + 가격대별 거래량)

**적용:**
```
삼성전자:
  1개월 POC: 58,200원 (가장 많이 거래된 가격)
  3개월 POC: 56,800원
  현재가: 59,100원

  → 현재가가 POC 위: "지지선 58,200원" 표시
  → 손절/익절에 POC 기반 지지/저항 가격 반영
```

#### T2-17. 신호 일관성 추적

**데이터:** `kis/history/` (74파일) + `vision/history/` (77파일) + `combined/history/` (74파일)

**적용:**
```
SK하이닉스:
  3/10: 매수 → 3/11: 매수 → 3/12: 적극매수 → 3/13: 매수
  → "4일 연속 매수 유지" 표시
  → 연속 기간이 길수록 신호 신뢰도 상승

에코프로:
  3/10: 중립 → 3/11: 매수 → 3/12: 매도 → 3/13: 중립
  → "신호 불안정 (4일간 4회 변동)" 경고
```

---

### 2.3 Tier 3: 장기 개선 (신규 데이터 연동)

#### T3-18. 시뮬레이션 히스토리 (시스템 성과)

**데이터:** `simulation/` 41일분 — 매일의 전략별 수익률

**적용:** 시스템 성과 대시보드에 41일 누적 수익률 차트, 승률 추세, 최대 낙폭 표시.

#### T3-19. 예측 적중률 검증 (시스템 성과)

**데이터:** `forecast-history/` 18파일 — AI가 예측한 테마 vs 실제 결과

**적용:**
```
3/10 예측: "2차전지 강세" (신뢰도 85%)
3/10 결과: 2차전지 대장주 평균 +3.2%
→ 적중 ✅

3/11 예측: "바이오 반등" (신뢰도 62%)
3/11 결과: 바이오 대장주 평균 -1.5%
→ 미스 ❌

18일 전체 적중률: 72% (13/18)
```

#### T3-20. 모의투자 성과 (전략 시뮬레이션)

**데이터:** `paper-trading/` 22파일 — 장중 가격 스냅샷 포함 실제 모의투자

**적용:** 전략 시뮬레이션에 실제 모의투자 결과 비교. "이 전략으로 22일간 모의투자했으면 +12.5%" 표시.

#### T3-21~25. 추가 항목

| # | 데이터 | 적용 |
|---|------|------|
| 21 | criteria_data 11개 중 8개 미사용 | 스캐너 필터에 "신고가 돌파", "골든크로스", "거래량 TOP30 진입" 등 추가 |
| 22 | criteria_data.high_breakout | "52주 신고가 종목" 별도 섹션 또는 이상거래에 통합 |
| 23 | kis_gemini.foreign_holding_pct | 외국인 보유비율 30% 이상 = 외국인 선호주 필터 |
| 24 | kis_gemini.volume_turnover_pct | 거래회전율 급증 = 매집 또는 분산 신호 |
| 25 | kis_gemini.market_cap_billion | 대형주/중형주/소형주 세그먼트별 신호 분석 |

---

## 3. 구현 우선순위 및 일정

```
Phase A: Tier 1 즉시 개선 (8개 항목)
├── T1-1. 이중 신호 검증 ──────────── run_all.py + Dashboard
├── T1-2. 실제 밸류에이션 ──────────── DataLoader + run_all.py + Dashboard
├── T1-3. 실제 호가잔량 ──────────── DataLoader + run_all.py + Dashboard
├── T1-4. 글로벌 매크로 종합 ────────── run_all.py + Dashboard
├── T1-5. 환율 데이터 ──────────── run_all.py + Dashboard
├── T1-6. F&G 추세 ──────────── run_all.py + Dashboard
├── T1-7. 테마 예측 ──────────── run_all.py + Dashboard
└── T1-8. 실제 장중 투자자 동향 ────── run_all.py + Dashboard

Phase B: Tier 2 보강 (9개 항목)
├── T2-9~11. 펀더멘탈 + RSI + 60일 캔들
├── T2-12~13. 증권사 매매 + 거래대금
├── T2-14~15. 하락 종목 + 프로그램 매매
└── T2-16~17. 지지/저항 + 신호 일관성

Phase C: Tier 3 장기 (8개 항목)
├── T3-18~20. 시뮬레이션/예측/모의투자 히스토리
└── T3-21~25. criteria 확장 + 보유비율 + 회전율 + 시가총액
```

---

## 4. 기대 효과

### 4.1 정량적 효과

| 지표 | 현재 | Phase A 후 | Phase B 후 | Phase C 후 |
|------|:---:|:---:|:---:|:---:|
| 데이터 활용률 | 19% | 45% | 70% | 80%+ |
| 신호 신뢰도 | 단일 소스 | 이중 검증 (+20%) | 4차원 스코어 (+35%) | 히스토리 검증 (+40%) |
| 밸류에이션 정확도 | 프록시 | 실제 PER/PBR | + ROE/부채/성장 | + 시가총액 세그먼트 |
| 호가 데이터 | 추정치 | 실제 bid/ask | + volume profile | + 동시호가 |
| 매크로 지표 | 2개 | 10개+ | + 환율 추세 | + 히스토리 |
| 히트맵 | 가짜 데이터 | 실제 투자자 동향 | + 종목별 | + 히스토리 |

### 4.2 정성적 효과

- **투자 판단 근거 강화:** "vision_signal이 매수" → "Vision 매수 + KIS 적극매수 일치 (고확신), PER 12.5 (업종 평균 18.3 대비 저평가), 외국인 3일 순매수, RSI 45 (중립), 호가 매수벽 1.68배"
- **거짓 신호 감소:** 이중 검증으로 Vision-KIS 불일치 시 주의 표시
- **타이밍 개선:** 장중 투자자 동향 + 시간대별 매매 패턴으로 진입 시점 최적화
- **리스크 관리 정밀화:** volume-profile POC 기반 지지/저항 → 손절/익절 정밀화

---

## 5. 기술 구현 상세

### 5.1 DataLoader 확장 필요 메서드

현재 없는 메서드 (추가 필요):
```python
# kis_gemini.json 전체 로드
def get_kis_gemini(self) -> dict:
    return self._load_json(self.signal_path / "kis" / "kis_gemini.json")

# investor-intraday.json
def get_investor_intraday(self) -> dict:
    return self._load_json(self.theme_path / "investor-intraday.json")

# indicator-history.json
def get_indicator_history(self) -> dict:
    return self._load_json(self.theme_path / "indicator-history.json")
```

### 5.2 run_all.py 수정 범위

- Phase 1: performance에 환율, F&G 추세, 매크로 지표 추가
- Phase 2: smart_money에 api_signal + match_status 반영, scanner에 api_signal 추가
- Phase 5: sentiment에 매크로 전체 지표 반영, valuation에 kis_gemini 펀더멘탈
- Phase 6: orderbook에 kis_gemini.order_book, heatmap에 investor-intraday
- Phase 7: insider에 DART, consensus에 kis_analysis scores

### 5.3 Dashboard 수정 범위

- 시장 현황: 환율 행 추가, F&G 추세 표시
- 밸류에이션: PER/PBR/ROE 컬럼 추가
- 호가창 압력: 실제 bid/ask 비율 게이지
- 시간대별 히트맵: 외국인/기관/개인 3행 히트맵
- 교차 신호: "고확신/확인필요/혼조" 뱃지 추가
- 스캐너: "RSI", "거래대금 TOP", "52주 신고가" 필터 추가

---

## 6. 결론

현재 stock_toolkit은 두 프로젝트가 수집한 482개 파일, 30MB 데이터의 **19%만 활용**하고 있다. 특히 가장 풍부한 데이터 소스인 `kis_gemini.json`(1.7MB, 100종목 × PER/PBR/호가/RSI/펀더멘탈)이 **완전히 사장**되어 있다.

Tier 1(8개 항목)만 구현해도:
- 데이터 활용률: 19% → 45%
- 신호 신뢰도: 이중 검증으로 +20%
- 5개 섹션이 추정/가짜 데이터 → 실제 데이터로 전환
- 추가 데이터 수집 없이, **이미 있는 데이터**만으로 달성 가능
