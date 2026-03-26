# 프로젝트 전체 소스 진단 보고서

**작성일:** 2026-03-26 KST
**분석 범위:** daemon/, core/, frontend/, modules/, scripts/ 전체 소스
**수정:** 1차 15건 + 2차 8건 + 3차 4건 + 4차 4건 + 5차 6건 + 6차 3건 = 총 40건 정정 반영

---

## P1 — 높음 (성능 병목)

### 1. 순차적 API 호출 (`daemon/trader.py`)
- 매수 대상별 개별 현재가 조회 (N종목 x ~2초 = 최대 20초)
- 미체결 취소 루프에서 `asyncio.sleep(0.3)` x N건 (10건 = 3초 추가)
- `schedule_sell_check`(라인 938-960)에서 30초마다 모든 포지션 REST 폴링
- **해결**: `asyncio.gather()` 병렬화, WebSocket 기반 가격 활용

```python
# 현재 (순차)
for c in buy_candidates:
    price = await _get_current_price(code)

# 개선안 (병렬)
prices = await asyncio.gather(
    *[_get_current_price(c["code"]) for c in buy_candidates]
)
```

### 2. 당일 매도 조회 중복 API 호출 (`daemon/trader.py:479-508`)
- `_get_sold_today_trades()`(라인 479) + `_get_sold_today_codes()`(라인 500) → 동일 WHERE 조건으로 2회 쿼리
- **해결**: 단일 함수로 통합

```python
async def _get_sold_today() -> tuple[dict[str, float], set[str]]:
    rows = await fetch_sold_today_from_db()
    pnl_map = {r["code"]: r["pnl_pct"] for r in rows}
    return pnl_map, set(pnl_map.keys())
```

### 3. Dashboard.tsx 약 39개 API 동시 폴링 (`frontend`)
- `loadAllData()`(라인 150-188)에서 약 39개 API를 5분(장중 h>=9 && h<16)/10분(장외)마다 호출 (캐싱 전무)
- **폴링 간격 버그**: `isMarketHours`가 useEffect 초기 1회만 판단(라인 268-270). 장중 진입 후 장외로 전환되어도 5분 폴링이 계속 유지됨 (컴포넌트 언마운트 전까지)
- 탭 비활성 상태에서도 백그라운드 폴링 지속 (visibilitychange 리스너가 폴링을 멈추지 않음)
- volume_profile 조건부 이중 호출 (JSON fetch → 실패 시 dataService 폴백)
- cleanup은 정상 (라인 272: clearInterval + unsubscribe + removeEventListener)
- **해결**: React Query/SWR 도입, staleTime 설정, visibility 기반 폴링 + isMarketHours 동적 재판단

---

## P2 — 중간 (코드 중복/구조)

### 4. `daemon/trader.py` 대규모 중복 (1013줄)

| 중복 내용 | 반복 횟수 | 권장 조치 |
|-----------|----------|----------|
| 계정번호 파싱 로직 | 6곳 (라인 126 `_kis_order`, 181 `_cancel_unfilled`, 234 `_cancel_unfilled_sell`, 441 `fetch_available_balance`, 700 `cancel_all_pending_orders`, 986 `_kis_order_market`) | `_parse_account_parts()` 유틸리티 추출 |
| 미체결 취소 함수 (매수/매도 80% 동일, 차이점은 `SLL_BUY_DVSN_CD`만) | 2곳 (라인 176-226, 229-279) | `_cancel_unfilled(code, is_sell)` 통합 |
| 보유일 계산 로직 | 2곳 (라인 656-666, 805-813) | `_calc_hold_days()` 유틸리티 추출 |
| 토큰 만료 재시도 로직 (파라미터명 `retry` vs `_retry` 불일치) | 2곳 (라인 120, 980) | `_with_token_retry()` 데코레이터 |

### 5. Dashboard.tsx 2,887줄 단일 파일

**상태 관리:**
- 64개 useState (라인 78-139에 62개, 라인 295-296에 2개)
- useMemo/useCallback/useRef 전무 → 매 렌더링마다 Set/배열/객체 재생성
- useEffect 4개: `[anyModalOpen]`(라인 143), `[]`(초기화, 라인 203), `[]`(IntersectionObserver, 라인 299), `[]`(스크롤 감지, 라인 323)
- anyModalOpen(라인 142): stockDetail, showLogin, showSettings, confExp, streakPopup, lifecyclePopup, badgePopup, showStockSearch 8개 변수로 계산

**분리 가능한 섹션 (IIFE 블록 19개 — 무조건부 9개 + 조건부 10개, 주요 6개 나열):**

| 섹션 | 대략적 줄 범위 | 권장 컴포넌트 |
|------|--------------|------------|
| AI 모닝 브리핑 | ~971-1175 | `<AiBriefingSection />` |
| AI 주목 종목 | ~1383-1496 | `<FocusedStockSection />` |
| 연속 시그널 | ~1502-1600 | `<ConsecutiveSignalSection />` |
| 테마 라이프사이클 | ~1650-1728 | `<LifecycleSection />` |
| 위험 종목 모니터 | ~1855-1880 | `<RiskMonitorSection />` |
| 시뮬레이션 | ~1978-2050 | `<SimulationSection />` |

**번들 관련:**
- recharts ScatterChart: 테마 라이프사이클 섹션(~1653줄)에서 실제 사용중
- lucide-react: 19개 아이콘 임포트, 모두 사용중

### 6. `scripts/run_all.py` 2,285줄 단일 파일
- **Phase 1-8**까지 존재 (코드 내 명시적 주석/print로 구분)
  - Phase 1 (라인 40-135): 알림 & 브리핑
  - Phase 2 (라인 137-549): 모니터링
  - Phase 3 (라인 551-775): 분석
  - Phase 4 (라인 777-796): 라이프사이클
  - Phase 5 (라인 798-1153): 신규 분석 (조건부 import)
  - Phase 6 (라인 1155-1404): 추가 분석 (조건부 import)
  - Phase 7 (라인 1406-1915): 추가 데이터
  - Phase 8 (라인 1916-2256): 확장 분석
- 매직 넘버 **50개 이상** (RSI 80/20, Fear&Greed 25/45/55/75, 거래량 200% 등)
- `print()` 32회 사용 (`logging` 모듈 미적용)
- 동일 데이터를 여러 Phase에서 재로드
- **해결**: Phase별 모듈 분할 + config 파일 + logging 모듈

### 7. modules/ 디렉토리 — 33개 중 10개(30%) 미사용

**run_all.py에서 사용되는 모듈 (22개):**
- Phase 1-4 상단 import (11개): cross_signal, daily_briefing, system_performance, anomaly_detector, smart_money, sector_flow, news_impact, theme_lifecycle, risk_monitor, pattern_matcher, scenario_simulator
- Phase 5 조건부 import (라인 799-804, 6개): sentiment_index, gap_analyzer, valuation_screener, volume_price_divergence, premarket_monitor, short_squeeze
- Phase 6 조건부 import (라인 1156-1160, 5개): supply_cluster, exit_optimizer, event_calendar, theme_propagation, program_tracker

**다른 파일에서도 사용:**
- stock_scanner: `bot/handlers.py`, `modules/scenario_simulator.py`에서 import

**미사용 모듈 (10개):**
- `ai_mentor.py`, `auction_analyzer.py`, `consensus_drift.py`
- `correlation_network.py`, `earnings_preview.py`, `insider_tracker.py`
- `intraday_heatmap.py`, `orderbook_pressure.py`, `portfolio_advisor.py`
- `trading_journal.py` (테스트 파일에서만 import)

**공통 중복 패턴:**
- 알림 포맷팅 패턴 다수 모듈에서 동일 반복 → `utils/alert_formatter.py` 추출
- 점수 계산 로직 5개 모듈에서 중복 → `utils/scoring.py` 추출
- 데이터 검증 패턴 전 모듈 반복 → `utils/validators.py` 추출
- 각 모듈에 하드코딩된 threshold 산재 → `config/module_thresholds.py` 중앙화

### 8. Frontend 타입 안전성 부재
- AutoTrader.tsx: `user: any`, `prices: Record<string, number>` 등
- Portfolio.tsx: `portfolio: any`, `portfolioRaw: any`
- Scanner.tsx: `allStocks`, `results` 모두 `any[]`, 4개 `Set<string>` state (signals, risks, flows, markets)
- dataService.ts: 제너릭 `<T>`는 TypeScript 컴파일 타입 힌트로만 사용, 런타임 검증 없음 (`res.json()`이 any 반환)
- null/undefined 체크 불충분 다수

### 9. Frontend 추가 구조 문제

**AutoTrader.tsx (775줄):**
- 메인 함수 약 714줄 (라인 62-775), 20개 useState + 1개 useRef
- 내부에 5개 서브 컴포넌트 정의 (SummaryCard, Section, TradeRow, HistoryByDate, LoginModal)
- 세션 복원 로직 중복 (103-123줄, 154-165줄에서 동일한 localStorage 파싱)

**RefreshButtons.tsx (141줄):**
- 매직 넘버: `150000`(라인 65), `90000`(라인 73), `75000`(라인 29) 하드코딩
- Job ID `"7376450"`(라인 5), `"7376451"`(라인 6) 하드코딩

**Portfolio.tsx (650줄):**
- `useEffect`(라인 73-102, 의존성 `[dbHoldings, portfolioRaw]`)에서 매 변경 시 전체 포트폴리오 재계산 (useMemo 미사용)
- 종목 리스트 렌더링 O(n×m) 복잡도 (매 항목마다 3개 배열 spread + find, 라인 282)
- `JSON.parse(JSON.stringify(...))` 깊은 복사 사용 (라인 241)

**Scanner.tsx (298줄):**
- 매 `handleSearch()` 호출 시 12개 조건 순차 필터링
- 이미 정렬된 데이터 매번 재정렬

---

### 10. `core/kis_client.py` 동기 코드 중복 (289줄, scripts 전용)
- `requests.get/post/patch` 사용 (라인 36, 67, 99, 103, 146, 195, 250) — 동기 라이브러리
- **daemon/trader.py에서는 import하지 않음** (daemon은 자체 aiohttp 비동기 구현 사용)
- 사용처: `scripts/run_all.py`, `scripts/generate_missing_data.py`, `tests/` — 모두 동기 스크립트이므로 asyncio 블로킹 문제 없음
- 토큰 갱신 로직 7개 메서드에서 반복, 헤더 생성 5곳 중복 (라인 32, 87, 134, 183, 238 — tr_id만 상이)
- **해결**: 헤더/토큰 유틸리티 함수 추출 (aiohttp 전환은 daemon에 불필요, scripts는 동기 스크립트)

---

## P3 — 낮음 (개선 기회)

### 11. 부분 체결 시 `unmark_selling()` (`daemon/trader.py:398-401`)
- 부분 체결 → 즉시 락 해제 → 재매도 가능
- **3차 검증 결과**: `update_position_quantity()`(라인 399)가 `unmark_selling()`(라인 400) **전에** 실행되므로, 재매도 시 줄어든 수량(잔여분)으로만 주문됨. 이는 **이중 매도가 아닌 의도된 동작**(잔여분 재매도)
- 다만, 실행 순서(DB 업데이트→락 해제)에 의존하므로 **방어적 개선 권장**: DB 업데이트 완료 확인 후 unmark

### 12. is_selling/mark_selling 패턴 (`daemon/trader.py:640-682`)
- 라인 640~682 사이에 **await 호출 없음** (모두 동기 코드: dict 접근, 산술 연산, datetime 계산)
- asyncio 단일 스레드에서 **원자적 실행**, 현재 race condition 불가
- `_selling_locks`는 `set[str]` 기반 원자 연산으로 안전
- **향후 코드 변경 시 방어적으로** `try_mark_selling()` 패턴 권장

### 13. 에러 핸들링 패턴
- `except Exception as e` → 모든 예외를 동일 처리 (trader.py 전역)
- kis_client.py: `print()` 사용, 예외 전파 없음 (silent failure)
- notifier.py: Telegram 발송 실패 시 재시도 없음 (메시지 손실 확인됨)
- 큐 크기 고정 (_MAX_QUEUE=50 라인 54, Queue 생성 라인 60) → 중요 알림 손실 가능

### 14. `data_loader.py` 비효율
- `get_stock()` 복합 탐색 (라인 131-150): 4개 키 선형 순회 + themes 중첩 루프(theme×leaders) + signals 순회 → O(m + n×l + s)
- 매 호출마다 `path.exists()` 반복
- `get_theme_history()`, `get_forecast_history()` 매번 glob() 실행
- **해결**: 초기화 시 `{code: data}` 인덱스 구축

### 15. `daemon/config.py` 필수 환경변수 검증 부재
- `KIS_APP_KEY`, `SUPABASE_URL` 등 모두 기본값 빈 문자열(""), 검증 로직 없음

### 16. `daemon/ws_client.py` 문제
- 하드코딩된 필드 인덱스 (라인 12-20: IDX_CODE=0, IDX_PRICE=3 등)
- `_subscribed_codes` 동시 접근 Lock 부재 (asyncio 단일 스레드 set 원자 연산으로 실질 안전)

### 17. `daemon/http_session.py` 문제
- 타임아웃 15초 하드코딩 (`aiohttp.ClientTimeout(total=15)`) → API별 차등 불가

### 18. `asyncio.ensure_future()` (`daemon/trader.py:369-373, 412-416`)
- `trigger_subscription_refresh()` 함수 내부에서 자체 예외 처리 수행하므로 실질 위험도 낮음
- `done_callback` 미등록이지만 현재 코드에서는 문제 없음

### 19. `schedule_sell_check` 종료 지연 (`daemon/trader.py:938-960`)
- `_main._shutdown = True` 후에도 sleep(30) 완료까지 최대 30초 지연
- **해결**: `asyncio.Event` + `wait_for()` 패턴

### 20. `_get_trade_config` TTL 하드코딩 (`daemon/trader.py:593-604`)
- 캐시 TTL `30`(초)이 매직 넘버로 하드코딩 (라인 600)

### 21. `daemon/main.py` 전역 상태
- `_alert_codes`(라인 39), `_trade_codes`(라인 40) 전역 set 변수
- `_buy_running` 플래그 (라인 36, 176-192) — asyncio 단일 스레드에서 안전하나 클래스화 권장
- 10분마다 DB 강제 갱신 (라인 139: `asyncio.sleep(600)`, 라인 146: `force_refresh=True`)
- 5분마다 GitHub API 호출 (라인 173: `asyncio.sleep(300)`, 라인 179)

### 22. `daemon/position_db.py` 캐시
- 5초 TTL 캐시 (라인 13: `_CACHE_TTL = 5`)
- 빈번한 조회 시 효율 낮을 수 있음 (30-60초로 증가 고려)

---

## 정량 요약

| 영역 | 파일 수 | 총 줄 수 | 가장 심각한 문제 |
|------|--------|---------|----------------|
| daemon/ | 11 | ~2,500 | 순차 API 호출, 중복 코드 |
| core/ | 5 | ~600 | 동기 코드 중복 (scripts 전용, daemon 영향 없음) |
| frontend/ | 11 | ~5,300 | 2,887줄 단일 컴포넌트, 캐싱 전무, 폴링 간격 버그 |
| modules/ | 33 | ~2,100 | 30% 미사용, 중복 패턴 |
| scripts/ | 6 | ~3,500 | 2,285줄 단일 파일 (Phase 8개) |

**참고**: daemon/trader.py는 자체 aiohttp 비동기 구현을 사용하며, core/kis_client.py를 import하지 않음. asyncio 이벤트 루프 블로킹 문제 없음.

---

## 권장 조치 순서

```
1단계 (1주):  P1 — API 병렬화, 중복 쿼리 통합, React Query + 폴링 버그 수정
2단계 (2주):  P2 — trader.py 중복 제거, Dashboard 분리, 미사용 모듈 정리
3단계 (여유): P3 — 방어적 패턴 개선, 에러 핸들링, 타입 안전성
```

---

## 모듈 의존성 그래프

```
run_all.py
├── Phase 1-4 (상단 import, 11개)
│   ├── cross_signal (독립)
│   ├── daily_briefing
│   │   ├── cross_signal (재호출)
│   │   └── system_performance
│   ├── system_performance (독립)
│   ├── anomaly_detector (독립)
│   ├── smart_money (독립)
│   ├── sector_flow (독립)
│   ├── news_impact (독립)
│   ├── theme_lifecycle (독립)
│   ├── risk_monitor (독립)
│   ├── pattern_matcher (독립)
│   └── scenario_simulator
│       ├── stock_scanner (내부 의존)
│       └── system_performance
├── Phase 5 (조건부 import 라인 799-804, 6개)
│   ├── sentiment_index
│   ├── gap_analyzer
│   ├── valuation_screener
│   ├── volume_price_divergence
│   ├── premarket_monitor
│   └── short_squeeze
├── Phase 6 (조건부 import 라인 1156-1160, 5개)
│   ├── supply_cluster
│   ├── exit_optimizer
│   ├── event_calendar
│   ├── theme_propagation
│   └── program_tracker
├── Phase 7 (라인 1406-1915, 추가 데이터 — modules import 없음)
└── Phase 8 (라인 1916-2256, 확장 분석 — modules import 없음)

별도 사용: stock_scanner → bot/handlers.py, modules/scenario_simulator.py
```

---

## 정정 내역

### 1차 재검토 (15건)

| # | 원본 | 정정 | 이유 |
|---|------|------|------|
| 1 | is_selling/mark_selling 40줄 간격 | 42줄 간격 | 실측 |
| 2 | 계정번호 파싱 7곳 | 6곳 | 검색 결과 |
| 3 | 헤더 생성 3곳 중복 | 5곳 | 실측 |
| 4 | Dashboard 40개 API | 약 39개 | Promise 실측 |
| 5 | Dashboard 6개 팝업/모달 | 8개 (anyModalOpen 기준) | state 카운트 |
| 6 | ScatterChart 미사용 | ~1653줄에서 사용중 | JSX 확인 |
| 7 | lucide-react 7개만 사용 | 19개 임포트, 모두 사용 | 전수 확인 |
| 8 | AI 브리핑 970-1110줄 | ~971-1175줄 | IIFE 범위 실측 |
| 9 | modules 21개(64%) 미사용 | 10개(30%) 미사용 | run_all.py import 전수 + bot/handlers.py 확인 |
| 10 | AutoTrader 537줄, 13개 state | 477줄, 20개 state | 범위/카운트 |
| 11 | 익절/손절 UI 2회 반복 | 1회만 존재 | 코드 확인 |
| 12 | 매직 넘버 AutoTrader에 존재 | RefreshButtons.tsx에 존재 | 파일 위치 |
| 13 | Portfolio 검색 미구현 | 502-575줄에 구현됨 | 코드 확인 |
| 14 | Scanner 11개 Set state | 4개 Set state | 타입 확인 |
| 15 | Scanner 11개 필터 조건 | 12개 조건 | 실측 |

### 2차 재검토 (8건)

| # | 원본 | 정정 | 이유 |
|---|------|------|------|
| 16 | P0 Race Condition (즉시 조치) | P3 (방어적 개선) | 라인 640-682 사이 await 없음, asyncio 원자적 실행 |
| 17 | 글로벌 Lock 필요 (P0) | P3 | set 원자 연산 + asyncio 단일 스레드 |
| 18 | _peak_prices 메모리 누수 | 삭제 | 모든 경로에서 pop 확인 |
| 19 | 미사용 모듈 11개 | 10개 | stock_scanner → bot/handlers.py에서 사용 확인 |
| 20 | AutoTrader 477줄 | 약 714줄 | 전체 함수 범위 재측정 |
| 21 | Dashboard useState 62-64개 | 64개 확정 | grep 전수 확인 |
| 22 | Portfolio O(n^2) | O(n×m) | 정확한 복잡도 |
| 23 | ensure_future 위험 높음 | 실질 위험도 낮음 | 내부 자체 예외 처리 |

### 3차 재검토 (4건)

| # | 원본 | 정정 | 이유 |
|---|------|------|------|
| 24 | P0 부분체결 이중매도 위험 | P3 (의도된 동작) | update_position_quantity()가 unmark 전에 실행, 재매도 시 줄어든 수량으로 주문. 이중 매도 아님 |
| 25 | run_all.py Phase 1-6 | Phase 1-8 | 코드 내 명시적 주석 확인 |
| 26 | 보유일 계산 라인 805-815 | 805-813 | 실제 코드 범위 |
| 27 | kis_client.py 288줄 | 289줄 | 실측 |

### 4차 재검토 (4건)

| # | 원본 | 정정 | 이유 |
|---|------|------|------|
| 28 | P1: kis_client.py가 daemon asyncio 블로킹 | **P2로 하향, 블로킹 아님** | daemon/trader.py는 kis_client.py를 import하지 않음. daemon은 자체 aiohttp 비동기 구현(http_session.py + _get_current_price 등). kis_client.py는 scripts/run_all.py 전용 동기 클라이언트 |
| 29 | 계정번호 파싱 "5-6곳" | 정확히 6곳 | 전수 검색 확정 (라인 126, 181, 234, 441, 700, 986) |
| 30 | Dashboard 폴링 간격 정상 | **버그 발견** | isMarketHours가 useEffect 초기 1회만 판단 → 장중→장외 전환 시 5분 폴링 유지 |
| 31 | 당일 매도 중복 쿼리 (보고만) | 코드 전문 확인 완료 | _get_sold_today_trades(라인 556-571) / _get_sold_today_codes(라인 574-590), 동일 WHERE 조건 SELECT만 상이 |

### 5차 재검토 (6건)

| # | 원본 | 정정 | 이유 |
|---|------|------|------|
| 32 | IIFE 블록 "약 10개" | **19개** (무조건부 9 + 조건부 10) | `(() => {` 전수 검색 |
| 33 | 정정 #9: 미사용 모듈 "11개(33%)" | **10개(30%)** | 본문과 정정 내역 간 불일치 해소, 10개가 정확 |
| 34 | Phase 2-7 경계 라인 (136, 550, 776, 797, 1154, 1405) | 각각 1라인 뒤 (137, 551, 777, 798, 1155, 1406) | 실제 print문 라인 확인 |
| 35 | 의존성 그래프 Phase 7-8 상세 부재 | "modules import 없음" 명시 | Phase 7-8은 모듈 import 없이 데이터 처리만 수행 |
| 36 | 사용 모듈 "22개" vs 그래프 stock_scanner 포함 | 본문 22개 + 별도 사용 1개(stock_scanner) = 23개 모듈 사용 | 그래프와 본문 정합성 확보 |
| 37 | 함수명 "cancel_all_orders()" 혼용 | **cancel_all_pending_orders()** | 실제 함수명 확인 (trader.py 라인 694) |

### 6차 재검토 (3건)

| # | 원본 | 정정 | 이유 |
|---|------|------|------|
| 38 | daemon/ 파일 수 "9개" | **11개** | __init__.py 포함 전수 확인 (alert_rules, config, github_monitor, http_session, main, notifier, position_db, stock_manager, trader, ws_client + __init__) |
| 39 | core/ 파일 수 "4개" | **5개** | __init__.py 포함 전수 확인 (data_loader, gemini_client, kis_client, telegram_bot + __init__) |
| 40 | data_loader.py "O(n), 최악 O(n²)" | **O(m + n×l + s)** | 4키 선형 + themes 중첩(theme×leaders) + signals 순회의 복합 탐색 |
