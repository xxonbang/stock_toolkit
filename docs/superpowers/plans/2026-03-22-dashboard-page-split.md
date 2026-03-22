# Dashboard 페이지 분리 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dashboard.tsx(2,516줄)의 5개 카테고리를 독립 페이지 컴포넌트로 분리하여, 탭 전환 시 해당 카테고리 데이터만 로드하도록 개선

**Architecture:** 하단 퀵 네비(시장/신호/분석/전략/시스템)를 상단 4탭(대시보드/포트폴리오/스캐너/모의투자)과 동일한 라우팅 방식으로 전환. 각 카테고리를 독립 컴포넌트로 추출하되, 공유 헤더와 공통 유틸은 그대로 유지. 기존 렌더링 결과를 완벽히 보존하면서 점진적으로 분리.

**Tech Stack:** React, react-router-dom (HashRouter), TypeScript

**Side-Effect 방지 원칙:**
- 각 Task 완료 후 반드시 기존 화면과 동일한 렌더링 결과를 확인
- 한 번에 1개 카테고리만 분리 (점진적 마이그레이션)
- 기존 코드를 먼저 복사 → 동작 확인 → Dashboard에서 제거 순서
- 공유 state는 props로 전달, 불필요한 전역 상태 도입 금지

---

## 파일 구조

### 신규 생성
```
frontend/src/pages/
  CategoryMarket.tsx      — 시장 카테고리 (프리마켓, 브리핑, 시장현황, AI주목종목)
  CategorySignal.tsx      — 신호 카테고리 (연속시그널, 교차신호, 라이프사이클, 이상거래, 위험종목, 스마트머니, 시뮬레이션, 패턴매칭)
  CategoryAnalysis.tsx    — 분석 카테고리 (뉴스, 갭, 역발상, 밸류에이션, 거래량괴리, 자금흐름, 전이예측)
  CategoryStrategy.tsx    — 전략 카테고리 (손절익절, 이벤트, 프로그램매매, 히트맵, 내부자, 컨센서스, 동시호가, 호가창, 상관관계, 실적, 멘토, 증권사, 거래대금, 모의투자현황, 적중률, 매물대, 일관성)
  CategorySystem.tsx      — 시스템 카테고리 (시뮬레이션 히스토리, 장중수급, 매매일지)
```

### 수정
```
frontend/src/pages/Dashboard.tsx  — 카테고리 섹션 제거, 라우팅 분기 추가
frontend/src/App.tsx              — 카테고리별 라우트 추가
```

---

## 공유 데이터 전략

**카테고리 간 공유되는 state:**
- `performance` — 시장(시장현황, AI주목종목) + 신호(연속시그널 배지에서 간접 참조)
- `ts` (타임스탬프) — 모든 카테고리 SectionHeader에서 사용

**해결:** 각 카테고리 컴포넌트가 자체적으로 필요한 데이터를 로드. `performance`는 시장과 신호 양쪽에서 독립적으로 fetch (동일 JSON, 캐시 히트). `ts`는 performance에서 추출하므로 각 컴포넌트에서 독립 계산.

---

## Task 0: 사전 검증 — 현재 상태 스냅샷

**목적:** 분리 전 기준점 확보

- [ ] **Step 1: 현재 빌드 정상 확인**

Run: `cd frontend && npx tsc --noEmit && cd .. && python -m pytest tests/ -q`
Expected: 에러 없음, 55 passed

- [ ] **Step 2: 기존 렌더링 스크린샷 저장 (수동)**

각 카테고리 영역의 현재 렌더링을 브라우저에서 확인하여 기준점으로 삼음

---

## Task 1: CategoryMarket 추출

**Files:**
- Create: `frontend/src/pages/CategoryMarket.tsx`
- Modify: `frontend/src/pages/Dashboard.tsx`
- Modify: `frontend/src/App.tsx`

**범위:** 라인 610~1018 (프리마켓, 브리핑, 시장현황, AI주목종목)
**State:** premarket, briefing, performance, sentiment, indicatorHistory, supplyCluster, crossSignal, smartMoney, consecutiveSignals
**dataService:** getPremarket, getBriefing, getPerformance, getSentiment, getIndicatorHistory, getSupplyCluster, getCrossSignal, getSmartMoney, getConsecutiveSignals

- [ ] **Step 1: CategoryMarket.tsx 생성**

Dashboard.tsx에서 시장 카테고리 관련 코드를 복사:
- 필요한 state 선언 (9개)
- loadData() 함수 (해당 9개 dataService 호출만)
- useEffect(() => loadData(), [])
- 시장 카테고리 JSX (프리마켓~AI주목종목)
- 필요한 import (SectionHeader, Badge, lucide-react 아이콘 등)
- 기존 Dashboard의 헬퍼 함수 중 시장 섹션에서 사용하는 것만 포함 (signalBadge 등)

- [ ] **Step 2: App.tsx에 라우트 추가**

```tsx
import CategoryMarket from './pages/CategoryMarket'
// Routes 안에 추가:
<Route path="/market" element={<CategoryMarket />} />
```

- [ ] **Step 3: 브라우저에서 /market 접속하여 기존 시장 섹션과 동일 렌더링 확인**

Run: `cd frontend && npx tsc --noEmit`
Expected: 에러 없음

확인: `localhost:5177/stock_toolkit/#/market`에서 프리마켓, 브리핑, 시장현황, AI주목종목이 기존과 동일하게 표시

- [ ] **Step 4: Dashboard.tsx에서 시장 카테고리 섹션 제거**

cat-market 앵커부터 cat-signal 앵커 직전까지의 JSX를 제거.
대신 `page === "market"` 조건으로 `<CategoryMarket />` 렌더링 추가.

- [ ] **Step 5: Dashboard loadAllData()에서 시장 전용 데이터 로드 제거**

시장 카테고리에서만 사용하는 dataService 호출 제거:
getPremarket, getBriefing, getSentiment, getIndicatorHistory, getSupplyCluster
(getPerformance, getCrossSignal, getSmartMoney, getConsecutiveSignals는 다른 카테고리에서도 사용할 수 있으므로 확인 후 제거)

- [ ] **Step 6: 빌드 + 테스트**

Run: `cd frontend && npx tsc --noEmit && cd .. && python -m pytest tests/ -q`
Expected: 에러 없음

- [ ] **Step 7: 커밋**

```bash
git add frontend/src/pages/CategoryMarket.tsx frontend/src/pages/Dashboard.tsx frontend/src/App.tsx
git commit -m "refactor: 시장 카테고리를 CategoryMarket.tsx로 분리"
```

---

## Task 2: CategorySignal 추출

**Files:**
- Create: `frontend/src/pages/CategorySignal.tsx`
- Modify: `frontend/src/pages/Dashboard.tsx`
- Modify: `frontend/src/App.tsx`

**범위:** 라인 1446~1779 (연속시그널, 교차신호, 라이프사이클, 이상거래, 위험종목, 스마트머니, 시뮬레이션, 패턴매칭)
**State:** consecutiveSignals, crossSignal, lifecycle, anomalies, riskMonitor, smartMoney, simulation, pattern, performance(ts용)
**dataService:** getConsecutiveSignals, getCrossSignal, getLifecycle, getAnomalies, getRiskMonitor, getSmartMoney, getSimulation, getPattern, getPerformance(ts추출용)

- [ ] **Step 1: CategorySignal.tsx 생성** — Task 1과 동일 패턴
- [ ] **Step 2: App.tsx에 `/signal` 라우트 추가**
- [ ] **Step 3: 브라우저에서 렌더링 동일 확인**
- [ ] **Step 4: Dashboard.tsx에서 신호 카테고리 섹션 제거**
- [ ] **Step 5: Dashboard loadAllData()에서 신호 전용 데이터 로드 제거**
- [ ] **Step 6: 빌드 + 테스트**
- [ ] **Step 7: 커밋**

---

## Task 3: CategoryAnalysis 추출

**Files:**
- Create: `frontend/src/pages/CategoryAnalysis.tsx`
- Modify: `frontend/src/pages/Dashboard.tsx`
- Modify: `frontend/src/App.tsx`

**범위:** 라인 1780~1961 (뉴스, 갭, 역발상, 밸류에이션, 거래량괴리, 자금흐름, 전이예측)
**State:** newsImpact, gapAnalysis, shortSqueeze, valuation, divergence, sectors, propagation
**dataService:** getNewsImpact, getGapAnalysis, getShortSqueeze, getValuation, getVolumeDivergence, getSectorFlow, getThemePropagation

- [ ] **Step 1~7:** Task 1과 동일 패턴, `/analysis` 라우트

---

## Task 4: CategoryStrategy 추출

**Files:**
- Create: `frontend/src/pages/CategoryStrategy.tsx`
- Modify: `frontend/src/pages/Dashboard.tsx`
- Modify: `frontend/src/App.tsx`

**범위:** 라인 1963~2394 (손절익절 ~ 신호일관성, 17개 섹션)
**State:** exitOptimizer, eventCalendar, programTrading, heatmap, insiderTrades, consensus, auction, orderbook, correlationData, earningsCalendar, aiMentor, memberTrading, tradingValue, paperTrading, forecastAccuracy, volumeProfile, signalConsistency
**dataService:** 17개 해당 메서드

- [ ] **Step 1~7:** Task 1과 동일 패턴, `/strategy` 라우트

---

## Task 5: CategorySystem 추출

**Files:**
- Create: `frontend/src/pages/CategorySystem.tsx`
- Modify: `frontend/src/pages/Dashboard.tsx`
- Modify: `frontend/src/App.tsx`

**범위:** 라인 2396~2477 (시뮬레이션히스토리, 장중수급, 매매일지)
**State:** simulationHistory, intradayStockFlow, tradingJournal
**dataService:** getSimulationHistory, getIntradayStockFlow, getTradingJournal

- [ ] **Step 1~7:** Task 1과 동일 패턴, `/system` 라우트

---

## Task 6: 하단 퀵 네비를 탭 네비게이션으로 전환

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx` — 하단 fixed 네비 제거
- Modify: `frontend/src/App.tsx` — 기본 라우트를 `/market`으로 리다이렉트

**변경 내용:**
- 하단 고정 네비(cat-market~cat-system 버튼 바) 제거
- 대시보드 탭 진입 시 기본적으로 시장(CategoryMarket) 표시
- 각 카테고리는 독립 페이지로 라우팅

- [ ] **Step 1: 하단 퀵 네비 JSX 제거** (라인 2492~2513)
- [ ] **Step 2: IntersectionObserver 코드 제거** (라인 291~312)
- [ ] **Step 3: categories 배열 제거** (라인 282~289)
- [ ] **Step 4: App.tsx에서 `/` 라우트를 CategoryMarket으로 변경 또는 리다이렉트**
- [ ] **Step 5: 빌드 + 테스트**
- [ ] **Step 6: 커밋**

---

## Task 7: Dashboard.tsx 정리

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

- [ ] **Step 1: 사용하지 않는 state 선언 제거**
- [ ] **Step 2: 사용하지 않는 import 제거**
- [ ] **Step 3: loadAllData()에서 제거된 호출 정리**
- [ ] **Step 4: 빌드 + 테스트**
- [ ] **Step 5: 최종 라인 수 확인** — 목표: 헤더+포트폴리오+라우팅만 남아 ~500줄 이하
- [ ] **Step 6: 커밋**

---

## Task 8: 카테고리 네비게이션 UI

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx` — 헤더 탭 또는 서브 네비 추가

**변경:** 대시보드 진입 시 5개 카테고리 탭(시장/신호/분석/전략/시스템)을 상단 또는 헤더 하단에 표시. 현재 활성 카테고리 강조.

- [ ] **Step 1: 카테고리 서브탭 UI 추가**

대시보드/포트폴리오/스캐너/모의투자 탭 아래에 카테고리 서브탭 표시.
page가 카테고리 중 하나일 때만 서브탭 표시.

- [ ] **Step 2: 빌드 + 브라우저 확인**
- [ ] **Step 3: 커밋**

---

## 검증 체크리스트

각 Task 완료 후 반드시 확인:

1. **빌드:** `npx tsc --noEmit` 에러 없음
2. **테스트:** `python -m pytest tests/ -q` 전체 PASS
3. **렌더링:** 해당 카테고리 페이지가 기존 스크롤 섹션과 동일하게 표시
4. **다른 페이지 영향 없음:** 포트폴리오, 스캐너, 모의투자 페이지 정상 동작
5. **데이터 로드:** 해당 카테고리 진입 시에만 관련 API 호출 (Network 탭 확인)
