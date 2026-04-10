# 거래대금 모멘텀 전략 성능 향상 리서치

> 작성일: 2026-04-10
> 현행 전략: 09:05 거래대금×가점 스코어 TOP2 매수 → 15:15 청산
> 백테스트 성과: 평균 +5.27%, 승률 71%, 손익비 2.07 (499거래일)

---

## 1. 매수 종목 수 최적화 (TOP1 vs TOP2 vs TOP3)

### 1.1 집중 투자의 이론적 근거

- **켈리 기준(Kelly Criterion)**: 승률 71%, 손익비 2.07에서 최적 비중은 상당히 높음. 이론상 단일 종목 집중이 기대값 극대화
- **워런 버핏**: 3~5개 "최고 확신 종목"에 집중 투자를 공개적으로 옹호. "분산은 무지에 대한 보호"
- **학술 연구**: 집중 포트폴리오(1~5종목)가 분산 포트폴리오 대비 기대 수익률이 높으나 분산(variance)도 비례하여 증가

### 1.2 분산 투자의 이론적 근거

- 2% 룰: 단일 트레이드에 계좌의 2% 이상 위험 노출 금지 — 프롭 트레이딩의 표준 리스크 관리
- 종목 수 증가 시 단일 종목의 극단적 손실(-5% 손절) 영향이 희석
- 다양한 시장·전략에 걸쳐 분산할수록 더 높은 위험 감수 가능

### 1.3 현행 전략에의 시사점

| 항목 | TOP1 | TOP2 (현행) | TOP3 |
|------|------|-------------|------|
| 기대 수익률 | 가장 높음 (최고 확신) | 중간 | 가장 낮음 (3위 종목 품질↓) |
| 변동성/MDD | 가장 높음 | 중간 | 가장 낮음 |
| 단일 손절(-5%) 영향 | -5% 전체 | -2.5% 전체 | -1.67% 전체 |
| 승률 변화 예상 | 소폭 상승 | 현행 71% | 소폭 하락 |

**권장**: 백테스트에서 TOP1/TOP2/TOP3별 MDD·샤프비 비교 필요. 일반적으로 **TOP2가 수익-위험 균형점**으로 적절. TOP1은 MDD가 과도할 수 있고, TOP3은 3위 종목의 예측력 저하로 수익률 희석 가능.

---

## 2. 청산 시간 최적화

### 2.1 한국 시장 장중 모멘텀 패턴

- **거래량·변동성 U자형 패턴**: 한국 거래소(09:00~15:30)에서 거래량과 변동성이 장 시작/마감에 높고 중간(11:00~13:00)에 낮은 U자형 확인 (MDPI, 2022)
- **장중 모멘텀(MIM)**: KOSPI 지수에서 첫 30분 수익률이 마지막 30분 수익률을 유의하게 예측. 장 마감으로 갈수록 거래비용(스프레드)이 줄어들어 MIM 전략 순수익 개선
- **오전 모멘텀 감쇠**: 오전 9시~10시의 강한 모멘텀이 11시경 약화. 점심시간 거래량 급감 후 오후 재개

### 2.2 청산 전략 비교

| 전략 | 장점 | 단점 |
|------|------|------|
| **15:15 고정 (현행)** | 단순, MIM 마지막 30분 효과 포착 | 오후 반전 시 이익 환수 |
| **11:00 조기 청산** | 모멘텀 감쇠 전 수익 확정 | 오후 추가 상승분 놓침 |
| **Trailing Stop** | 상승 시 수익 극대화, 하락 시 조기 차단 | 변동성에 조기 탈출 위험 |
| **하이브리드 (시간+trailing)** | 10분 후 trailing 전환 → 수익 보호 + 상승 추종 | 파라미터 과적합 위험 |

### 2.3 학술/실증 근거

- **567,000건 백테스트 분석** (KJ Trading Systems): 복잡한 청산(trailing stop, profit target)이 단순 시간 기반 청산을 일관되게 이기지 못함. 단순할수록 robust
- **SPY 장중 모멘텀 연구** (Zarattini et al., SSRN): trailing stop + 장중 모멘텀 조합이 2007~2024 총 수익률 1,985%, 샤프 1.33 달성
- **End-of-day vs Intraday stop loss**: 3건 백테스트 중 2건에서 EOD 손절이 장중 손절보다 수익성 높음

**권장**: 현행 15:15 고정은 단순성과 MIM 효과 면에서 합리적. 개선 시 **"11:00~11:30에 수익률이 음수이면 조기 청산, 양수이면 15:15까지 보유"** 같은 조건부 로직이 과적합 없이 효과적일 수 있음.

---

## 3. 동적 손절 (고정 -5% vs ATR 기반)

### 3.1 ATR 기반 손절의 장점

- **변동성 적응**: ATR이 큰 날은 SL 폭을 넓혀 정상 변동에 의한 조기 손절 방지, ATR이 작은 날은 타이트하게
- **실증**: ATR + 추세 지표 조합 시 고정 손절 대비 **성과 15% 향상**, 1,000건 트레이드에서 2x ATR 손절이 고정 대비 **최대 낙폭(MDD) 32% 감소**
- **일반적 배수**: 데이트레이딩은 **1.5~2x ATR**, 스윙은 3~4x ATR 권장

### 3.2 고정 손절의 장점

- 단순성, 과적합 위험 없음
- 백테스트에서 ATR 배수=1은 오히려 성과 저하 (배수 선택이 핵심)

### 3.3 시간대별 SL 조정

- 장 초반(09:00~09:30): 변동성 최대 → SL 넓게 (2x ATR)
- 점심(11:00~13:00): 변동성 최소 → SL 좁게 (1.5x ATR)  
- 장 마감(14:30~15:15): 변동성 재증가 → SL 다시 넓게

### 3.4 권장

현행 -5% 고정은 이미 적절한 수준. 개선 시 **2x ATR(14) SL을 계산하고, max(-5%, -2×ATR)로 floor 설정**하는 하이브리드가 안전. ATR 배수 1.0은 피해야 함.

---

## 4. 시장 레짐 필터

### 4.1 필터 후보

| 지표 | 구현 난이도 | 과적합 위험 | 설명 |
|------|-----------|-----------|------|
| **VKOSPI 레벨** | 중 | 낮음 | VIX 한국판. >25이면 Risk-Off |
| **KOSPI 전일 수익률** | 하 | 낮음 | 지수 -1% 이상 하락 시 스킵 |
| **시장 breadth** | 중 | 낮음 | 상승종목 비율 <40%이면 Risk-Off |
| **거래대금 총합** | 하 | 낮음 | 전일 대비 시장 전체 거래대금 급감 시 스킵 |
| **이동평균선** | 하 | 중 | KOSPI가 20일선 아래이면 보수적 |

### 4.2 과적합 방지 원칙

- **변수는 1~2개만**: VKOSPI + KOSPI 수익률 정도. 3개 이상은 과적합 위험 급증
- **임계값을 자주 바꾸지 않기**: "변동성이 2배 이상 변하거나 수주간 지속될 때만 재조정"
- **Walk-forward 검증**: 120일 이상 안정화 기간을 두고 재학습. 일별 재학습은 과적합
- **K-fold 교차검증**: 최적 하이퍼파라미터 범위를 교차검증으로 확인
- **단순 규칙 우선**: "VKOSPI > 25이면 매수 안 함" 같은 바이너리 규칙이 복잡한 ML 모델보다 robust

### 4.3 실증 근거

- 레짐 인식 전략은 위기 시 낙폭을 줄이면서 안정기 수익을 보존 (Dozen Diamonds 리서치)
- Breadth 60% 이상 = Risk-On, 40~60% = 중립(고품질만), <40% = Risk-Off (TradingSim)
- "복수 자산에 동일 설정을 적용해도 작동해야 진짜" — 설정을 종목별로 바꿔야 한다면 과적합

**권장**: **VKOSPI ≤ 25 AND KOSPI 전일 종가 > 20일 이동평균** 조합. 단 2개 변수로 단순하고 과적합 위험 낮음.

---

## 5. 갭 크기와 수익률 관계

### 5.1 갭 크기별 특성

| 갭 크기 | 속성 | 충전율(Fill Rate) | 모멘텀 지속성 |
|---------|------|-----------------|-------------|
| <2% | 노이즈, 유의미하지 않음 | 높음 (~70%) | 약함 |
| 2~5% | **최적 구간** — 모멘텀 + 안정성 균형 | 30~33% | 강함 |
| 5~10% | 강한 모멘텀이나 변동성 트랩 위험 | 낮음 | 양방향 극단 |
| >10% | 과열 — 폭락 반전 또는 추가 폭등 | 매우 낮음 | 불확실 |

### 5.2 현행 갭 상한(10%) 평가

- 2~5% 갭이 모멘텀 지속성과 안정성에서 가장 유리
- 5% 이상 갭은 "변동성 트랩"과 "허위 돌파(false breakout)" 위험 증가
- 최소 갭 4% 이상에서 노이즈 필터링 효과 (QuantifiedStrategies)

### 5.3 권장

현행 갭 상한 10%는 적절하나, **갭 5~10% 구간에 감점 가중치(×0.8 등)를 적용**하면 변동성 트랩을 일부 회피 가능. 갭 2~5%가 "sweet spot"이므로 이 구간에 가점 부여도 고려.

---

## 6. 거래대금 절대값 순위 vs 거래대금 증가율(RVOL)

### 6.1 RVOL(Relative Volume)의 우위

- **절대 거래대금**: 삼성전자·SK하이닉스 등 대형주가 항상 상위. 대형주는 단타 변동성 낮음
- **RVOL (전일 대비 증가율)**: 해당 종목 기준 "평소 대비 얼마나 비정상적인가"를 측정
  - RVOL > 1.5: 유의미한 증가
  - RVOL > 3.0: 주요 촉매(이벤트) 신호
- RVOL은 "맥락적 정보"를 제공 — 절대 거래대금만으로는 "높음/낮음" 판단 불가
- 높은 거래량 주식이 더 강한 모멘텀과 "high volume return premium" 보유

### 6.2 학술 근거

- MDPI (2026): 높은 시가 거래량 + 낮은 정보 불확실성 결합 시 방향 예측 정확도 63.04%
- ML 모델: 고불확실성 레짐에서 RVOL 기반 71.43% 정확도, 총 수익률 117.99%, 샤프 3.02

### 6.3 현행 전략에의 시사점

현행은 **09:05 거래대금 순위(절대값)**를 사용 중. 이는 유동성 확보에는 유리하나, 대형주 편향 위험.

**권장**: **절대 거래대금 순위 + RVOL 필터** 하이브리드.
- 1차: 거래대금 상위 30위 이내 (유동성 확보)
- 2차: 그 중 RVOL(전일 동시간 대비) > 2.0인 종목만 후보
- 최종: 가점 스코어로 TOP2 선정

이렇게 하면 "평소에도 거래가 많은 대형주"보다 "오늘 특별히 거래가 폭증한 종목"을 우선 포착.

---

## 7. 외국인/기관 수급

### 7.1 학술 근거

- **정보 비대칭 연구** (Emerging Markets Finance and Trade, 2018): 한국 시장에서 이질적 투자자(외국인, 기관, 개인)의 일별 거래가 정보 비대칭에 유의미한 영향. 외국인 기관은 정보 비대칭을 완화하는 경향
- **기관의 단기 투자** (Emerging Markets Finance and Trade, 2016): 한국 시장에서 기관 투자자의 단기 투자 행태 연구 존재
- **KDI 연구**: 외국인 투자자 주식매매 분석 보고서 — 외국인의 매매 패턴이 시장에 미치는 영향 분석

### 7.2 KIS API에서 얻을 수 있는 데이터

- **`/uapi/domestic-stock/v1/quotations/inquire-investor`**: 종목별 투자자별(외국인/기관/개인 등) 매매동향 조회
  - 일별 투자자별 순매수/순매도 금액
  - 장중 실시간 누적 순매수 조회 가능
- **KRX Data Marketplace**: 투자자별 순매수 상위종목 데이터 제공

### 7.3 현행 전략에의 시사점

외국인/기관 동반 순매수 종목은 개인 주도 종목 대비 모멘텀 지속성이 높을 가능성.

**권장**: 
- 09:05 시점에서 외국인+기관 순매수인 종목에 **가점(×1.3)** 부여
- 순매도 종목에는 **감점(×0.7)** 부여
- 단, API 호출 횟수 제한(rate limit)에 주의. 상위 10종목에 대해서만 조회하는 등 범위 제한 필요

---

## 8. 복수 종목 상관관계 (섹터 분산)

### 8.1 동일 섹터 집중의 위험

- 같은 섹터 내 복수 종목 보유 시 **분산 효과 없음** — 동일 리스크 드라이버(금리, 유가, 반도체 수급 등)에 동시 노출
- "수십 종목을 보유해도 같은 성장·유동성 조건에 의존하면 여전히 집중(concentrated)" (GoTrade)
- 기술주 여러 개 = 분산처럼 보이지만 실제로는 높은 상관관계

### 8.2 데이트레이딩에서의 섹터 분산

- 한 섹터의 하락이 전체 수익을 망치지 않도록 다른 섹터에 걸쳐야 함
- 기술, 헬스케어, 금융, 에너지 등 서로 다른 성장률과 변동성을 가진 산업에 분산

### 8.3 현행 전략에의 시사점

TOP2가 같은 테마/섹터에 속하면 실질적으로 TOP1과 동일한 리스크.

**권장**:
- TOP2 선정 시 **동일 업종(KRX 업종 분류) 중복 금지** 규칙 추가
- 1위 종목 선정 후, 2위 후보가 같은 업종이면 3위로 대체
- 업종 판별: KIS API `inquire-price` 응답의 `bstp_kor_isnm`(업종 한글명) 활용
- 같은 테마(반도체, 2차전지 등)도 가능하면 회피하나, 테마 분류는 주관적이므로 업종 기준이 객관적

---

## 종합 우선순위

| 순위 | 개선 항목 | 기대 효과 | 구현 난이도 | 과적합 위험 |
|------|----------|----------|-----------|-----------|
| 1 | RVOL 필터 추가 (6번) | 종목 선정 품질↑ | 중 (데이터 이미 보유) | 낮 |
| 2 | 섹터 분산 규칙 (8번) | MDD↓ | 하 (업종 코드 비교) | 없음 |
| 3 | 시장 레짐 필터 (4번) | 패배일 회피 | 하~중 | 낮 (변수 2개) |
| 4 | 갭 구간별 가중치 (5번) | 변동성 트랩 회피 | 하 | 낮 |
| 5 | 외국인/기관 수급 가점 (7번) | 모멘텀 지속성↑ | 중 (API 호출 추가) | 낮 |
| 6 | ATR 기반 동적 손절 (3번) | MDD↓ 15%+ | 중 | 중 (배수 선택) |
| 7 | 청산 시간 조건부 변경 (2번) | 수익률 소폭↑ | 하 | 중 |
| 8 | 종목 수 변경 (1번) | 불확실 | 하 | 높 (백테스트 의존) |

---

## Sources

- [Market Intraday Momentum - KOSPI (MDPI, 2022)](https://www.mdpi.com/1911-8074/15/11/523)
- [ATR vs Fixed Stop-Loss Comparison](https://blog.afterpullback.com/atr-vs-fixed-stop-loss-which-one-protects-your-trades-better/)
- [87 Stop Loss Strategies Tested](https://papertoprofit.substack.com/p/i-tested-87-different-stop-loss-strategies)
- [567,000 Backtests on Exits](https://kjtradingsystems.com/algo-trading-exits.html)
- [SPY Intraday Momentum Strategy (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4824172)
- [Volatility Regime Shifting](https://www.dozendiamonds.com/volatility-regime-shifting/)
- [Market Breadth for Day Trading (TradingSim)](https://www.tradingsim.com/blog/broad-market-indicators-for-day-trading)
- [RVOL Trading Guide (StockTitan)](https://www.stocktitan.net/articles/relative-volume-rvol-trading-indicator)
- [Volume-Based Intraday Momentum - Chinese Market (MDPI, 2026)](https://www.mdpi.com/2227-7072/14/2/47)
- [Gap Trading Strategies Backtest (QuantifiedStrategies)](https://www.quantifiedstrategies.com/gap-trading-strategies/)
- [Gap and Go Strategy](https://highstrike.com/gap-and-go-strategy/)
- [Korean Market Investor Trading & Info Asymmetry](https://www.tandfonline.com/doi/full/10.1080/1540496X.2018.1504291)
- [Institutional Investor Short-term Trading in Korea](https://www.tandfonline.com/doi/full/10.1080/1540496X.2015.1025648)
- [KIS Developers API Portal](https://apiportal.koreainvestment.com/intro)
- [Sector Concentration Risk](https://www.heygotrade.com/en/blog/portfolio-concentration-risk-when-diversification-isnt-enough)
- [Day Trading Diversification (Warrior Trading)](https://www.warriortrading.com/diversification-definition/)
- [Gap Size and Fill Rates](https://www.quantifiedstrategies.com/gaps/)
