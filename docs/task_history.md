# Task History

## 2026-03-31

### [버그픽스] time_exit 시뮬 11:00 이후 매수 시 즉시 close 방지 (2026-03-31 13:20 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** 13:00 signal-pulse 오후 분석 후 매수 시 time_exit 시뮬이 `now_kst.hour >= 11` 조건으로 즉시 close되는 문제. 11:00 KST 이전 매수에서만 time_exit 시뮬 생성하도록 조건 추가.
- **커밋:** `b850202`

### [버그픽스] 매수 체결 확인 — 잔고 차분 검증 + pending 삭제 제거 (2026-03-31 12:58 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** KIS 미체결 조회 API(inquire-nccs) 404 실패 시 pending 삭제 → 잔고 API(inquire-balance) fallback으로 변경. pre_balance(매수 전)→post_balance(매수 후) 차분으로 정확한 체결 수량 산출. 기존 로직은 KIS 계좌에 실제 보유 중인 주식을 DB에서 삭제하여 매도 관리 불가 유발.
- **원인:** KIS 모의투자 서버가 inquire-nccs API에 지속적 404 반환. 시장가 즉시체결인데 "체결 0주→pending 삭제" 처리.
- **영향:** 오늘(3/31) 태경케미컬 325주, 흥구석유 166주가 KIS 계좌에 보유 중이나 DB 미등록 → 손절 미처리(-8%, -6%).
- **커밋:** `46f4434`

### [버그픽스] 시뮬레이션 독립 운영 hole 5건 수정 (2026-03-31 12:30 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/main.py`
- **내용:** (1) _close_open_simulations에 code 직접 전달 (2) orphan_sim_codes DB 재조회 정리 (3) daemon 시작 시 orphan 복원 (4) EOD 모든 open 시뮬 일괄 close. 실전 매도 후에도 시뮬이 자체 조건까지 독립 체크되도록 보장.
- **커밋:** `be9ca2d`, `1d11d5e`, `1e2bfe5`

## 2026-03-30

### [기능] 시간전략(09:30→11:00) 시뮬레이션 추가 (2026-03-30 21:55 KST)
- **변경 파일:** `daemon/trader.py`, `frontend/src/pages/AutoTrader.tsx`
- **내용:** 매수 시 time_exit 가상 포지션 자동 생성. 11:00 KST 이후 현재가 매도, SL=-2% 병행. 실전 매도 시 open 시뮬 일괄 close. 프론트엔드 전략 비교 UI에서 time_exit 제외 (데이터 축적 전용). 2~4주 데이터 축적 후 실전 전환 판단 예정.
- **커밋:** `9c8f8f9`

### [기능] 호가창 압력 이모지→Lucide + 종목선정 기준 설명 (2026-03-30 17:40 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/HelpDialog.tsx`
- **내용:** 📊 이모지를 BarChart3 Lucide 아이콘으로 변경. HelpDialog에 데이터 소스(장중 WebSocket/장외 KIS 스냅샷)와 선정 기준(편향 ±5%p, 매수/매도 각 10개) 상세 설명 추가.
- **커밋:** `4681598`

### [개선] 모의투자 화면 가독성 개선 — 폰트/간격/정렬 (2026-03-30 17:30 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`
- **내용:** 섹션 제목 11→12px, TradeRow 매수 상세 10→11px, SummaryCard 값 lg→xl, 매매 이력 날짜 헤더 13px semibold, 전략 비교 카드 라벨 9→10px/수익률 sm→base/패딩 p-2→p-3.
- **커밋:** `18e90bc`

### [버그픽스] 전략 비교 수익률 합계→평균으로 변경 + 빨간 테두리 제거 (2026-03-30 17:20 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`
- **내용:** 전략 비교 PnL을 합계→평균으로 변경(매매 이력과 동일 기준). 가상 전략 우위 시 빨간 border/체크마크 제거.
- **커밋:** `f42a8fe`, `8c680f5`

### [버그픽스] 전략 비교 바텀시트 — 뒷면 스크롤 잠금 + 헤더 고정 (2026-03-30 17:15 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`
- **내용:** 바텀시트 열림 시 body overflow hidden(뒷면 스크롤 방지). 핸들바/닫기/제목을 flex-shrink-0으로 고정, 콘텐츠만 스크롤.
- **커밋:** `6baabb9`

### [기능] Stepped Trailing 프리셋 선택 — 기본/공격형 토글 (2026-03-30 17:10 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/stock_manager.py`, `frontend/src/pages/AutoTrader.tsx`, `frontend/src/lib/supabase.ts`
- **내용:** Stepped Trailing Step 구간을 기본(5/10/15/20/25)/공격형(7/15/20/25/30) 프리셋으로 선택 가능. DB `stepped_preset` 컬럼 추가. daemon에서 프리셋별 `_STEPPED_PRESETS` 분기 적용. 141종목 200일 백테스트 기반 공격형이 평균PnL +0.29%p 우위.
- **커밋:** `6e5b1ba`

### [버그픽스] 가상 시뮬레이션 생성 실패(400) — user_id 빈문자열 방지 (2026-03-30 17:00 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** user_id가 빈 값이면 시뮬레이션 생성 스킵(UUID 파싱 에러 방지). 생성 실패 시 응답 본문 로깅 추가.
- **커밋:** `7981baf`

### [버그픽스] stepped_trailing 텔레그램 라벨 추가 + _buy_running→asyncio.Lock (2026-03-30 16:50 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/main.py`
- **내용:** reason_labels/emoji에 stepped_trailing 키 추가. _buy_running boolean→asyncio.Lock으로 교체하여 매수 프로세스 동시 실행 방지 보장.
- **커밋:** `3efd030`

### [개선] KIS API rate limit 방어 — 주요 함수에 재시도 로직 통합 (2026-03-30 16:48 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** _get_current_price, _kis_order_market, is_upper_limit, fetch_available_balance에 rate limit 3회 재시도(2/4/6초) 추가. _RATE_LIMIT_RETRIES, _RATE_LIMIT_BASE_SEC 상수화.
- **커밋:** `810b317`

### [개선] flash_spike_pct 임계값 5% → 15% 상향 (2026-03-30 16:45 KST)
- **변경 파일:** `daemon/config.py`, `daemon/stock_manager.py`
- **내용:** 테마주/소형주 장중 5% 이상 급등이 빈번하여, 정상 급등도 peak 갱신 무시되는 문제. 임계값을 15%로 상향하여 실제 불가능한 수준만 필터.
- **커밋:** `239def2`

### [기능] 매수 프로세스 종합 보고 텔레그램 메시지 추가 (2026-03-30 14:00 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** 매수 실행 시 1단계(스코어링 과정) → 2단계(보유/당일매도 필터링) → 3단계(잔고 배분/매수 대상) 종합 보고 텔레그램 발송.
- **커밋:** `b14bbc6`

### [기능] 모의투자 실행 ON/OFF 토글 추가 (2026-03-30 13:50 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`
- **내용:** 투자 전략 섹션 위에 '모의투자 실행' 섹션+토글 배치. OFF 시 buy_signal_mode=none(매수 중지), ON 시 research_optimal(재개). 확인 버튼 방식.
- **커밋:** `a8eb519`

### [버그픽스] setAlertConfig에서 buy_signal_mode 덮어쓰기 버그 수정 (2026-03-30 12:30 KST)
- **변경 파일:** `frontend/src/lib/supabase.ts`
- **내용:** select 쿼리에 buy_signal_mode, criteria_filter 누락 → 다른 설정 변경 시 기본값으로 덮어쓰기되는 치명적 버그 수정.
- **원인:** 연구 최적 전략 적용 후 전략 타입 등 다른 설정 변경 시 buy_signal_mode가 "and"로 리셋.
- **커밋:** `d0c8f62`

### [버그픽스] fetch_alert_config 전체 설정 무시 버그 수정 (2026-03-30 13:35 KST)
- **변경 파일:** `daemon/stock_manager.py`
- **내용:** SELECT 쿼리에 DB 미존재 컬럼 `flash_spike_pct` 포함으로 400 에러 발생 → 전체 설정이 기본값(fixed, all, criteria_filter=false)으로 동작. SELECT에서 해당 컬럼 제거.
- **원인:** `flash_spike_pct` 컬럼 ALTER TABLE SQL이 Supabase에 미적용 상태에서 코드에 추가됨. 에러 시 `defaults` dict 반환하는 fallback이 모든 사용자 설정을 무시.
- **영향:** strategy_type(stepped→fixed), alert_mode(portfolio_only→all), criteria_filter(true→false) 모두 기본값으로 동작. 비보유 종목 알림, fixed 전략 동작, 과열필터 미적용 문제의 근본 원인.
- **커밋:** `7989aa3`

### [버그픽스] 매도 실패 시 무한 재시도 루프 방지 (2026-03-30 11:10 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** KIS 매도 주문 실패(잔고 없음) 또는 미체결 조회 실패 시 현재가 기반 DB 즉시 정리. 예외 발생 시에도 포지션 종료 보장. 기존에는 unmark_selling 후 30초마다 재시도 → 텔레그램 스팸 발생.
- **원인:** KIS 모의투자 "잔고내역이 없습니다" 반환 시 매도 실패 → selling 마크 해제 → 다음 가격 체크에서 재시도 → 무한 루프.
- **커밋:** `62bf00f`

### [버그픽스] 체결가 조회 실패 시 현재가 fallback 추가 (2026-03-30 10:35 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** 모의투자 API 체결가 조회 404 실패 시 현재가 REST API를 fallback으로 사용(매수/매도 양쪽). 기존에는 전일종가를 체결가로 기록하여 PnL 왜곡 → 불필요한 손절 발동.
- **원인:** KIS 모의투자 서버가 체결 조회 API에 404 반환 → _get_actual_fill_price() 실패 → 주문가(전일종가)를 체결가로 기록. 실제 시가 대비 3~8% 높은 가격이 기록되어 매수 즉시 손절 발동.
- **커밋:** `21b2b27`

### [개선] 데몬 시작 직후 첫 워크플로우 매수 스킵 → 15분 경과 기반으로 변경 (2026-03-30 10:00 KST)
- **변경 파일:** `daemon/main.py`
- **내용:** _first_trade_check_done/_first_sp_check_done 플래그 제거. _is_stale_completion() 도입하여 완료 후 15분 이내면 데몬 시작 직후라도 즉시 매수 실행. 재시작 시 오래된 워크플로우 중복 매수 방지.
- **커밋:** `240d49f`

### [버그픽스] 매수 직후 손절 체크 공백 제거 + Stepped 손익 라벨 수정 (2026-03-30 09:40 KST)
- **변경 파일:** `daemon/trader.py`, `frontend/src/pages/AutoTrader.tsx`
- **내용:** 매수 체결 직후 즉시 현재가 조회→손절 체크 추가(기존 30초 공백 제거). ensure_future→await로 WebSocket 구독 갱신 완료 보장. stepped_trailing 매도 시 실제 PnL 기준 익절/손절 라벨 분기.
- **원인:** 매수 후 WebSocket 구독 갱신이 비동기(ensure_future)로 지연되어, 구독 전 가격 하락을 감지 못해 -2% 손절 초과 손실(-8%까지) 발생. 프론트에서 손실인데 "Stepped 익절"로 표시되는 라벨 버그.
- **커밋:** `e9fbe4f`

## 2026-03-28

### [기능] signal-pulse 완료 감지 → deploy-pages 트리거 → 매수 실행 (2026-03-30 KST)
- **변경 파일:** `daemon/config.py`, `daemon/github_monitor.py`, `daemon/main.py`
- **내용:** daemon에 signal-pulse analyze.yml 완료 감시 추가. 완료 감지 시 deploy-pages 직접 트리거(data-only), 완료 대기 후 최신 cross_signal.json으로 매수 실행. _buy_running 플래그로 theme-analyzer/signal-pulse 동시 매수 방지.
- **커밋:** `ff158dc`

### [기능] 종목 액션 팝업 + D등급 제거 + 스크롤 프로그레스바 + 다수 UI 개선 (2026-03-28 KST)
- **변경 파일:** `Dashboard.tsx`, `dataService.ts`, `HelpDialog.tsx`, `BriefingSection.tsx`, `run_all.py`, `test_cross_signal.py`
- **내용:** 종목 클릭 시 액션 팝업(상세/포함 섹션/네이버), D등급 6개 섹션 제거, 스크롤 프로그레스바, 브리핑 종목명 클릭, 밸류에이션 AI보너스 제거+계산식 도움말, 테마 자금 흐름 generated_at 버그 수정, 팝업 스크롤 잠금+시프트 방지
- **커밋:** `09ec573`

### [리팩토링] D등급 6개 섹션 제거 + 테스트 수정 + 연구 문서 (2026-03-28 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/services/dataService.ts`, `tests/test_cross_signal.py`, `docs/research/2026-03-28-dashboard-evaluation.md`, `docs/research/2026-03-28-implementation-plan.md`
- **내용:** 하드코딩/플레이스홀더 D등급 6개 섹션 제거(테마전이/손절익절/이벤트캘린더/내부자/컨센서스/동시호가). test_cross_signal.py 2건 실패 수정(UNION 로직+dual_signal 명칭 반영). 투자지표 유효성 연구 14차 120+회 검증 확정 결론 문서 추가.
- **커밋:** `7bc1fde`

### [진단] 대시보드 히스토리 데이터 활용도 분석 (2026-03-28 KST)
- **변경 파일:** `docs/research/2026-03-28-historical-utilization.md`
- **내용:** 7개 대시보드 섹션별 히스토리 데이터 활용 현황 분석. 핵심 발견: (1) 교차 신호가 연속 시그널 데이터 미참조(프론트 수정만으로 즉시 개선 가능), (2) 이상 거래가 60일 평균 미사용(전일 대비만 사용), (3) 차트 패턴/예측 적중률/연속 시그널은 이미 히스토리 적극 활용 중.

### [개선] 42일 백테스트 최종 합성 — 100-round 결론 비교 (2026-03-28 KST)
- **변경 파일:** `docs/research/2026-03-28-backtest-synthesis.md`
- **내용:** 42일 백테스트 3개 병렬 분석(알파, 소스비교, 신뢰도) 결과를 100-round 대시보드 평가 결론과 비교. 핵심 3개 결론 뒤집힘 확인: 알파 부호 반전(-0.95%→+1.53%p), 쌍방매수 최안정→최열위, Confidence 무효→역방향 예측력(p=0.01).

### [개선] 호가창 압력 장중 실시간 평균 기반으로 개선 (2026-03-28 KST)
- **변경 파일:** `daemon/alert_rules.py`, `daemon/main.py`, `scripts/run_all.py`, `frontend/src/pages/Dashboard.tsx`
- **내용:** 장 마감 후 스냅샷 1회 → 장중 호가 수신 시 bid_ratio 누적 평균으로 개선. 15:15 장 마감 시 Supabase `orderbook_avg` 테이블에 저장, run_all.py에서 우선 사용. 프론트에 데이터 소스·샘플 수 표시.
- **커밋:** `f9fd563`

### [리팩토링] dual_signal 명칭 통일 + 텔레그램 종목 선정 알림 (2026-03-28 KST)
- **변경 파일:** `modules/cross_signal.py`, `scripts/run_all.py`, `daemon/trader.py`, `bot/handlers.py`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/dashboard/FocusedStockSection.tsx`, `frontend/src/components/dashboard/BriefingSection.tsx`
- **내용:** dual_signal 값 명칭 통일(고확신→쌍방매수, 확인필요→Vision매수, KIS매수→API매수). 종목 선정 완료 시 점수 산출 내역·종목 상세 포함 텔레그램 알림 추가. 선정 0건 시 텔레그램 알림 추가.
- **커밋:** `f41d548`

### [개선] 5팩터 동점 시 타이브레이커 추가 (2026-03-28 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** `select_research_optimal` 동점 종목 발생 시 입력 순서 의존 대신 명확한 타이브레이커 적용. 1차 거래대금(높은순), 2차 등락률(높은순), 3차 현재가(낮은순).
- **커밋:** `b608317`

## 2026-03-27

### [버그픽스] 밸류에이션 스크리너 Path A 진입 조건 확장 (2026-03-27 17:10 KST)
- **변경 파일:** `scripts/run_all.py`
- **내용:** PER 0~30 범위만 허용하던 진입 조건을 PER/PBR/ROE 중 하나라도 양수면 펀더멘탈 스코어링(Path A)으로 진입하도록 확장. 기존 104종목 중 0종목이 Path A 진입 → 94종목으로 정상화. OPM 역방향 스코어링 수정.
- **커밋:** `87185b0`

### [개선] 역발상 시그널 → 수급 다이버전스 재설계 (2026-03-27 23:00 KST)
- **변경 파일:** `scripts/run_all.py`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/HelpDialog.tsx`
- **내용:** 단일팩터(과열+외국인) 기반 역발상 시그널을 5팩터 수급 다이버전스로 재설계. 가격 하락/외국인 순매수/기관 순매수/RSI 과매도/거래량 급증 스코어링. 프론트엔드 팩터 태그 표시, 도움말 업데이트. falling 종목 중복 경로 제거.

### [개선] 거래대금 TOP → 거래대금 이상 감지 리포지셔닝 (2026-03-27 22:30 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/HelpDialog.tsx`
- **내용:** 30개 전체 나열에서 flow_signal/폭증+급등/신규진입 조건 필터링으로 전환. 0건이면 섹션 숨김. flow_signal 뱃지 색상 분류, 시장 구분 표시 추가.
- **커밋:** `4a355fe`

### [버그픽스] 전략 비교 시뮬레이션 로직 수정 + UI 개선 (2026-03-27 16:00 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/stock_manager.py`, `daemon/config.py`, `daemon/ws_client.py`, `frontend/src/pages/AutoTrader.tsx`, `frontend/vite.config.ts`, `frontend/src/services/dataService.ts`
- **내용:**
  - daemon: _check_simulations 종목 필터 누락 수정, hold_days 하드코딩 제거, EOD 시뮬레이션 close 추가, user_id alert_config에서 조회, flash_spike_pct DB관리, config 캐시 5초 단축, WS 무한 재시도+알림, 미체결 보수적 처리
  - frontend: 모의투자 카드 정보 계층 재구성, +수익 빨강/-파랑 색상, 전략 비교 바텀시트(날짜별 그룹핑+접기), fixed 전략 TP/SL cap, Step 구간 시각화, 매집 기준 접기/펼치기
  - PWA: data/*.json precache 제거 → NetworkFirst, cache: no-cache
- **커밋:** `50a2586`, `342d60e`, `2473482`, `71b6f82`

### [개선] 예측 적중률 일별 카드 UI 개선 (2026-03-27 22:20 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 일별 태그 범람 해결(접기/펼치기), 적중률 progress bar 추가, 적중/미적중 ✓/✗ 그룹 분리, Badge→dot+truncate 리스트로 변경.
- **커밋:** `28f1340` (갭 분석 리팩토링과 동일 커밋에 포함)

### [리팩토링] 갭 분석 섹션 제거 + 뱃지 흡수 (2026-03-27 22:15 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 독립 섹션으로 가치가 낮은 갭 분석 섹션을 제거하고, 갭 정보를 교차 신호·스마트 머니 카드에 `▼시가 -4.6%` / `▲시가 +3.2%` 뱃지로 통합. 검색 통합 부분도 정리.
- **커밋:** `28f1340`

### [개선] HelpDialog bottom sheet → 팝오버 방식 + 텍스트 구조화 (2026-03-27 16:20 KST)
- **변경 파일:** `frontend/src/components/HelpDialog.tsx`
- **내용:** 도움말 UI를 전체화면 bottom sheet에서 클릭 위치 기반 팝오버로 변경. desc 텍스트를 구조화 렌더링(■→소제목, ·→불릿), 색상 키워드에 컬러 칩 자동 표시, 닫기 버튼 접근성 개선.
- **커밋:** c99b01c

### [개선] 프론트엔드 UI/디자인 대규모 개선 (2026-03-27 12:55 KST)
- **변경 파일:** `frontend/src/index.css`, `frontend/src/App.tsx`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Scanner.tsx`, `frontend/src/pages/Portfolio.tsx`, `frontend/src/pages/AutoTrader.tsx`, `frontend/src/components/HelpDialog.tsx`, `frontend/src/components/dashboard/FocusedStockSection.tsx`, `frontend/src/components/dashboard/LifecycleSection.tsx`, `frontend/src/components/dashboard/SimulationSection.tsx`
- **내용:** 데이터 표시 일절 변경 없이 순수 UI/디자인만 개선. 10개 Phase로 나누어 순차 진행.
  - CSS 기반: tabular-nums, 모달/토스트 애니메이션(fadeIn/slideUp/scaleIn/toastIn), card-hover, custom-check, 라이트 모드 스크롤바, no-select
  - 헤더: 페이지 탭 슬라이딩 인디케이터, 카테고리 퀵네비 pill 슬라이딩 배경, 드롭다운 메뉴 인라인→t-card 통일
  - 카드/레이아웃: 카테고리 전환점 디바이더 라벨(신호/분석/전략/시스템), AI 주목 종목 카테고리 뱃지 스타일, 종목 카드 card-hover
  - 데이터 시각화: Gauge 바 높이 증가+transition, 심리 온도계 dot 마커, LifecycleSection 차트 다크모드 수정(축/툴팁)
  - 모달/토스트: 바텀시트 드래그 핸들, 모달 진입 애니메이션, 토스트 pulse→slide+실패 빨강 배경
  - 포트폴리오: 수익률 영역 배경 tint(수익=빨강/손실=파랑), 커스텀 체크박스, 미니 수익률 바
  - 모의투자: 전략 비교 승자 강조+✓, 매매 이력 상태별 좌측 accent border
  - 스캐너: 필터 그룹 색상 dot, 검색 결과 card-hover
  - 마이크로: 로고 hover 회전, 수치 tabular-nums, 모바일 no-select

## 2026-03-26

### [버그픽스] 시장가 주문 실제 체결가 사용 (2026-03-27 10:48 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** 매수/매도 시 주문 전 현재가 대신 KIS inquire-daily-ccld API로 실제 체결 단가 조회. `_get_actual_fill_price()` 함수 추가, `place_buy_order_with_qty()`와 `place_sell_order()`에서 실제 체결가 사용 (조회 실패 시 기존 가격 fallback)
- **원인:** 시장가 주문은 매도호가에 체결되어 주문 전 현재가(최근 체결가)와 차이 발생
- **커밋:** `f7cbe9f`

### [기능] 전략 선택 UI + 비교 성과 표시 (2026-03-27 06:15 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`, `frontend/src/lib/supabase.ts`
- **내용:** Stepped Trailing / 고정 익절 전략 전환 UI, 전략 비교 성과 펼치기/접기 카드, strategyType에 따른 익절/손절 설정 분기(stepped 시 손절만 편집 가능). supabase.ts에 strategy_type 지원 추가 및 getStrategySimulations() 함수 추가
- **커밋:** `3cf1790`

### [기능] 가상 시뮬레이션 기록/추적 구현 (2026-03-27 05:30 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** 매수 시 비선택 전략의 가상 포지션을 `strategy_simulations` 테이블에 생성하고, 현재가 체크 시 가상 매도 조건(fixed: TP/SL/trailing, stepped: SL/stepped_trailing)을 평가하여 자동 close. `_create_simulation()`, `_check_simulations()` 함수 추가, `place_buy_order_with_qty()`와 `check_positions_for_sell()`에 훅 연결
- **커밋:** `b2b274b`

### [기능] Stepped Trailing 매도 로직 구현 (2026-03-27 00:16 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** `calc_stepped_stop_pct()` 함수 추가 및 `check_positions_for_sell()`에 strategy_type별 분기 로직 구현. stepped 전략: 고정 TP 없이 고점 수익률 기반 5단계 stop 상향(+5%→본전, +10%→+5%, +15%→+10%, +20%→+15%, +25%+→동적 trailing). fixed 전략은 기존 로직 유지
- **커밋:** `9877269`

### [진단] 최적 익절(Take-Profit) 전략 연구 (2026-03-27 04:30 KST)
- **변경 파일:** `docs/research/2026-03-26-takeprofit-strategy.md`
- **내용:** 고정 TP +7% vs Trailing-only vs Hybrid 전략 비교 연구. 학술/실증 자료 8건+ 조사. 상한가 종목에서 +7% TP가 잠재 수익의 77% 차단하는 문제 분석. **1순위 권장: Stepped Trailing (고정 TP 제거 + 단계별 stop 상향)**, 2순위: 50% 분할매도 Hybrid. Breakeven stop(+5% 도달 시 stop→0%)으로 round-trip 리스크 차단 가능

### [진단] 진입 타이밍 + 종목 선별 전략 연구 (2026-03-27 03:30 KST)
- **변경 파일:** `docs/research/2026-03-26-entry-timing.md`, `docs/research/2026-03-26-volatility-stoploss.md`
- **내용:** 당일 19종목 실전 데이터 기반 진입 전략 연구. 초기 4종목(손절) 분석에서 "지정가 매수 전환"을 권장했으나, 19종목 확대 검증 결과 **상한가 직행 종목의 수익이 손절 손실을 크게 상쇄**하여 결론 반전. 현재 시스템(시장가+손절-2%)이 지정가 대비 5배 유리. 진짜 개선 방향은 손절폭/진입 타이밍이 아닌 **종목 선별력 강화 + 오후 급등 포착**

### [진단] 변동성 기반 동적 손절 전략 연구 (2026-03-27 02:30 KST)
- **변경 파일:** `docs/research/2026-03-26-volatility-stoploss.md`
- **내용:** ATR 기반 손절, Chandelier Exit, 학술 연구(Han et al.) 조사. 6종목 실전 검증으로 10건 보완점 도출. whipsaw 전제 오류 발견(시스템에 재매수 방지 이미 구현). 최종 결론: -2% 고정 손절은 "보험료"로 수용 가능, 종목 선별이 핵심

### [개선] run_all.py print→logging 전환 + 매직 넘버 상수 추출 (2026-03-27 02:00 KST)
- **변경 파일:** `scripts/run_all.py`
- **내용:** 전체 31개 print() 호출을 logging(logger.info/error/warning)으로 전환, RSI/거래량/F&G/연속일수 등 10개 매직 넘버를 파일 상단 상수로 추출
- **커밋:** `ea8c2b3`

### [리팩토링] Dashboard 섹션별 컴포넌트 분리 (2026-03-27 01:10 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/dashboard/BriefingSection.tsx`, `FocusedStockSection.tsx`, `ConsecutiveSignalSection.tsx`, `LifecycleSection.tsx`, `RiskMonitorSection.tsx`, `SimulationSection.tsx`
- **내용:** Dashboard.tsx의 6개 IIFE 섹션(AI 모닝 브리핑, AI 주목 종목, 연속 시그널, 테마 라이프사이클, 위험 종목 모니터, 전략 시뮬레이션)을 개별 컴포넌트로 추출, 2893→2313줄(~20% 감소), 미사용 import/상수 정리
- **커밋:** `784f59c`

### [개선] Frontend 구조 개선 3건 (2026-03-27 00:30 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`, `frontend/src/components/RefreshButtons.tsx`, `frontend/src/pages/Portfolio.tsx`
- **내용:** AutoTrader 세션 복원 중복 로직을 restoreSessionFromStorage 헬퍼로 추출, RefreshButtons 매직 넘버(150000/90000/75000) 상수화, Portfolio 병합 계산을 useEffect→useMemo 변환
- **커밋:** `64c4b8c`

### [개선] data_loader get_stock() O(1) 인덱스 조회 최적화 (2026-03-27 00:05 KST)
- **변경 파일:** `core/data_loader.py`
- **내용:** get_stock()의 O(m+n×l+s) 순차 탐색을 _build_stock_index()로 인덱스 구축 후 O(1) dict 조회로 개선, clear_cache() 시 인덱스도 초기화
- **커밋:** `45ba28b`

### [개선] daemon P3 소규모 개선 5건 (2026-03-26 21:38 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/position_db.py`
- **내용:** TTL 상수화, schedule_sell_check 종료 개선(1초 단위 shutdown 체크), ensure_future done_callback 추가, 부분체결 방어 코멘트, try_mark_selling 원자적 check-and-set 도입
- **커밋:** `3b9ba1f`

### [개선] run_buy_process 현재가 조회 asyncio.gather 병렬화 (2026-03-26 23:50 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** run_buy_process()에서 현재가 조회를 순차 for-loop → asyncio.gather 병렬 호출로 변경, N종목×2초 → ~2초로 단축
- **커밋:** `94b568e`

### [리팩토링] 토큰 재시도 파라미터명 통일 (2026-03-26 23:40 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** `_kis_order_market`의 `_retry` → `retry`로 변경, `_kis_order`와 파라미터명 통일
- **커밋:** `1871fd4`

### [버그픽스] Dashboard 폴링 간격 버그 수정 (2026-03-26 23:30 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** setInterval→setTimeout 재귀 방식으로 변경하여 장중→장외 전환 시 폴링 간격 동적 재판단, 탭 비활성 시 폴링 스킵
- **커밋:** `443eff1`

### [리팩토링] 미체결 취소 함수 통합 (2026-03-26 23:20 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** `_cancel_unfilled` + `_cancel_unfilled_sell` 통합, `is_sell` 파라미터로 매수/매도 구분, 50줄 중복 제거
- **커밋:** `95cdc63`

### [개선] 당일 매도 조회 중복 쿼리 통합 (2026-03-26 23:15 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** `_get_sold_today_trades` + `_get_sold_today_codes` 동일 쿼리 2회 → 1회로 통합, `_get_sold_today_codes` 삭제
- **커밋:** `f9a1018`

### [리팩토링] 보유일 계산 유틸리티 _calc_hold_days() 추출 (2026-03-26 23:10 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** check_positions_for_sell()과 EOD 함수에서 중복된 보유일수 계산 로직을 `_calc_hold_days()` 유틸리티로 추출, `_KST` 모듈 레벨 상수화
- **커밋:** `b600172`

### [리팩토링] 계정번호 파싱 유틸리티 _parse_account() 추출 (2026-03-26 22:50 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** KIS_MOCK_ACCOUNT_NO 파싱 로직 6곳 중복을 `_parse_account()` 함수로 추출
- **커밋:** `8cb04e4`

### [버그픽스] iOS PWA 백그라운드 복귀 시 무한 로딩 수정 (2026-03-26 16:20 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`, `frontend/src/pages/Dashboard.tsx`
- **내용:** getSession()에 5초 타임아웃 추가, 타임아웃 시 localStorage 폴백, TOKEN_REFRESHED에서 sessionExpired 자동 해제
- **커밋:** `53afc1e`

### [버그픽스] 모의투자 미체결 조회 API 404 대응 (2026-03-26 15:23 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** KIS 모의투자 inquire-nccs API 미지원(404). 미체결 조회 실패 시 시장가 즉시체결 간주(return ordered_qty)
- **커밋:** `f6612fc`

### [버그픽스] 재검증 신규 이슈 2건 수정 (2026-03-26 15:18 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/position_db.py`
- **내용:** _shutdown import 값 복사 버그(모듈 참조로 수정), sell_price DB 컬럼 미존재 시 fallback
- **커밋:** `139d556`

### [개선] 최종 검증 12건 조치 (2026-03-26 15:14 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/main.py`, `daemon/position_db.py`, `daemon/config.py`
- **내용:** sell_price DB 저장, EOD 재시도 buy_price 스코프 버그, schedule_sell_check shutdown 감지, heartbeat 로깅, 당일 누적 손실 한도(-10%), sell_requested→filled 복구, dead code 제거, HTTP 상태 로깅, config 캐시 30초, MIN_AMOUNT_PER_STOCK config 이동
- **커밋:** `cb30756`

### [개선] 보유/모니터링 전략 검증 11건 조치 (2026-03-26 14:57 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/main.py`
- **내용:** startup cleanup(pending 정리+peak 초기화), sell_requested EOD 포함, 금요일 carry ×1.5, 공휴일 다년도, flash spike 방지(+5%), hold_days filled_at 우선, config 캐시 30초
- **커밋:** `4dd5f51`

### [버그픽스] 매수/매도 로직 전수 검증 8건 조치 (2026-03-26 14:45 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** EOD _verify_sell_fill 추가, 미체결 조회 실패 처리, _kis_order_market 토큰 재시도, place_sell_order try/except, EOD 실패 재시도, _peak_prices 정리, timezone UTC 변환
- **커밋:** `afe24ba`

### [버그픽스] 통합 시나리오 검증 5건 조치 (2026-03-26 13:11 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/main.py`
- **내용:** EOD price=0 재조회, 매도 실패 _peak_prices 정리, check_positions_for_sell .get() 방어, 데몬 재시작 첫 체크 skip, EOD 15:15~15:20 윈도우+당일 1회 보장
- **커밋:** `9d09999`

### [버그픽스] 매수 루프 방지 — 당일 재매수 차단 + 상한가 사전 필터 (2026-03-26 13:00 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** _get_sold_today_codes 당일 매도 종목 재매수 방지, 상한가 체크를 분배 전 수행하여 균등 재분배
- **커밋:** `a1ff5d0`

### [버그픽스] 매도 체결 확인 추가 (2026-03-26 14:35 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** _cancel_unfilled_sell + _verify_sell_fill 추가, 전량/부분/미체결 분기 처리
- **커밋:** `559a452`

### [개선] 매도 실시간 처리 — 30초 REST API 폴링 백업 (2026-03-26 09:00 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/main.py`
- **내용:** schedule_sell_check 30초마다 보유종목 현재가 REST API 조회, WebSocket 백업
- **커밋:** `dbe1df4`

### [개선] cross_signal 데이터 수집 UNION 방식 + KIS API 가격 보강 (2026-03-26 11:10 KST)
- **변경 파일:** `modules/cross_signal.py`, `scripts/run_all.py`, `daemon/trader.py`
- **내용:** signal-pulse 매수종목 ∪ theme-analyzer 대장주 전체 수집, api_data 없는 종목에 KIS API 가격 보강, run_buy_process 현재가 폴백
- **커밋:** `55fe0d8`, `f007e5d`

### [기능] 보유일수 연동 익절/보유 기준 (2026-03-26 01:00 KST)
- **변경 파일:** `daemon/trader.py`, `frontend/src/pages/AutoTrader.tsx`
- **내용:** D+0~D+4+ 익절 기준(7→10→15→20→25%), 장 마감 보유 기준(3→5→8→12→15%), MAX_HOLD_DAYS 제거, 프론트엔드 미니 테이블
- **커밋:** `e314fa3`

### [기능] 모의투자 탭 UI/UX 대폭 개선 (2026-03-26 00:30 KST)
- **변경 파일:** `daemon/trader.py`, `frontend/src/pages/AutoTrader.tsx`
- **내용:** 토글 기반 매집 기준(차트/지표/대장주1위/대장주전체), 확인/취소 UX, 토스트 알림, 로그인 모달, Lucide 아이콘, 설정 디자인 세련화, parseBuyMode 레거시 호환
- **커밋:** `827974a`, `79922d9`, `76a2555`

## 2026-03-25

### [개선] 모의투자 제거 + 예측 적중률 압축 + 거래대금 TOP 개선 (2026-03-26 00:05 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/HelpDialog.tsx`
- **내용:** 모의투자 현황(theme_analysis 데이터) 제거. 예측 적중률 날짜별 합산+테마별 적중률 뱃지 추가. 거래대금 TOP에 거래량 비율/순위 변동/NEW/폭증+급등 뱃지/클릭 팝업 추가.
- **커밋:** `1f70379`

### [개선] 매물대 지지/저항 경보 데이터 교체 + 도움말 현행화 (2026-03-25 23:40 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/HelpDialog.tsx`
- **내용:** volume_profile_alerts.json으로 교체 — 현재가+상태 뱃지+괴리율 표시, 클릭 팝업, 도움말 현행화
- **커밋:** `a89d9ef`

### [리팩토링] 시뮬레이션 히스토리 제거 + 신호 변동 모니터 교체 (2026-03-25 23:25 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 시뮬레이션 히스토리(더미 데이터) 제거. 신호 일관성→신호 변동 모니터로 교체 — 중립 반복 제외, 시그널 변경 종목만 표시(매수/매도 전환 뱃지, 클릭 팝업)
- **커밋:** `0ab9346`

### [개선] 장중 종목별 수급 — 종목명, 쌍끌이 뱃지, 시그널 연계, 클릭 팝업 (2026-03-25 23:00 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** stock-master 초기 로드로 종목명 매핑, 외국인+기관 동시 매수/매도 쌍끌이 뱃지, 시그널 뱃지 연계, 의미순 정렬, 종목 클릭 상세 팝업
- **커밋:** `884ddba`

### [리팩토링] 대시보드 매매 일지 섹션 제거 (2026-03-25 22:45 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 매매 일지 섹션 제거 — 보유 종목 스냅샷일 뿐 실제 매매 기록이 아니며 포트폴리오 탭과 정보 중복
- **커밋:** `131cb0c`

### [개선] 편집 버튼 상단 이동 + 하단 퀵 네비 높이 확대 (2026-03-25 22:30 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 편집 버튼을 건강도 영역 → refresh 버튼 우측으로 이동. 하단 카테고리 네비 터치 영역 확대(py-2→py-3, 패딩 추가).
- **커밋:** `893e516`

### [개선] 건강도 5축 가중 점수 + 계산 방법 설명 팝업 (2026-03-25 22:20 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 건강도를 서버 단일값 → 프론트 5축 가중 점수(수익/시그널/수급/분산/위험)로 교체. 축별 미니 바 + HelpCircle 클릭 시 설명 팝업 추가.
- **커밋:** `6d55ba2`

### [버그픽스] 포트폴리오 종목 상세 팝업 데이터 누락 수정 (2026-03-25 22:05 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 팝업 검색 대상에 portfolioRaw.holdings 추가 — crossSignal/smartMoney에 없는 보유 종목도 분석 데이터 표시
- **원인:** crossSignal(4건)+smartMoney(20건)에만 검색하여 포트폴리오 종목이 누락
- **커밋:** `d851f25`

### [기능] 포트폴리오 종목 카드 클릭 시 상세 팝업 표시 (2026-03-25 21:55 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 포트폴리오 종목 카드 클릭 시 대시보드와 동일한 종목 상세 팝업 표시 (crossSignal/smartMoney 데이터 활용). 체크박스 stopPropagation 처리.
- **커밋:** `3e7b432`

### [개선] 포트폴리오 탭 — 세션 hang 방지, Lucide 아이콘, 리밸런싱 시그널 기반 (2026-03-25 21:50 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Scanner.tsx`
- **내용:** refresh 버튼 세션 유효성 사전 확인+8초 타임아웃, 이모지→Lucide 아이콘 교체, 편집 모달 섹터 입력 제거+자동 병합, 리밸런싱 제안을 시그널/수급/위험/연속매집 데이터 기반으로 교체 (위험도별 색상, 종목당 최대 2개, 우선순위 정렬)
- **커밋:** `c12b88c`

### [버그픽스+개선] 세션 만료 오판 수정 + 매집 기준 세그먼트 UI (2026-03-25 17:40 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`
- **내용:** fetchTrades에서 Promise.race 타임아웃 제거, 인증 에러(jwt/token/auth)만 세션 만료 처리. 매집 기준 토글을 AND/OR/대장주 3개 세그먼트 버튼으로 변경.
- **커밋:** `68e1db6`

### [버그픽스] 모의투자 세션 만료 후 무한 로딩 재발 방지 (2026-03-25 17:25 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`
- **내용:** sessionExpiredRef로 세션 만료 확정 시 onAuthStateChange/handleVisibility의 loadData 재호출 차단. Supabase SDK 백그라운드 토큰 갱신이 무한 로딩을 유발하는 문제 해결.
- **커밋:** `679d140`

## 2026-03-24

### [버그픽스+개선] dual_signal 재계산, 위험 등급, 패턴 매칭 등 (2026-03-24 23:55 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/HelpDialog.tsx`, `frontend/src/lib/supabase.ts`, `scripts/run_all.py`
- **내용:** 상세 팝업 dual_signal을 실제 vision/api 기반 재계산, 중립 신호 방향 뱃지 미표시, 위험 종목 등급화+보유 종목 강조+외인 금액, 차트 패턴 matches 0건 미표시+name 빈값 fallback, HelpDialog 스크롤+sticky 헤더
- **커밋:** `2b4aa6e`

### [기능] AI 주목 종목 분류 + 이상 거래 급등 확인 뱃지 (2026-03-24 23:35 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/AutoTrader.tsx`
- **내용:** AI 주목 종목 4단계 카테고리 분류(고확신/대장주/매수일치/매수) + 연속일수/수급/테마 컨텍스트 표시. 이상 거래에 급등 확인 뱃지(10~25%+거래량x2) 추가, 뱃지 클릭 시 설명 팝업.
- **커밋:** `4d17b14`

### [개선] UI/UX 일괄 개선 — 신선도/그룹핑/팝업/방향 표시 (2026-03-24 23:25 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/AutoTrader.tsx`, `frontend/src/components/HelpDialog.tsx`, `frontend/src/lib/supabase.ts`, `scripts/run_all.py`
- **내용:** 연속 시그널 신선도 뱃지+종료 접기, 이상 거래 종목별 그룹핑+액션 분류+수급 표시, 라이프사이클 팝업(단계 설명+포함 종목), 교차 신호 방향 표시(↑매수유효/↓매도유효), 도움말 줄바꿈, 모의투자 손실 색상 파랑 변경, _calc_streak 7일 cutoff
- **커밋:** `af5e452`

### [기능] 매집 신호 AND/OR 토글 + 리밸런싱 제안 실데이터 기반 (2026-03-24 22:45 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/stock_manager.py`, `daemon/tests/test_trader.py`, `frontend/src/pages/AutoTrader.tsx`, `frontend/src/lib/supabase.ts`, `frontend/src/pages/Dashboard.tsx`
- **내용:** 모의투자 페이지에 매집 기준 AND/OR 토글 추가 (Supabase alert_config.buy_signal_mode 연동). 리밸런싱 제안을 서버 JSON 대신 실제 보유 데이터 기반으로 계산. OR 모드 테스트 추가.
- **커밋:** `7e898e6`

### [버그픽스] 미체결 조회 실패 시 전량 체결 오판 수정 (2026-03-24 22:20 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** _cancel_unfilled 반환값을 조회 실패 시 0→None으로 변경, _verify_fill_with_retry에서 None 감지 시 ordered_qty 그대로 반영 (안전 fallback)
- **커밋:** `e46cba8`

### [개선] 모의투자 미체결 시 최대 3회 시장가 재주문 (2026-03-24 22:10 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** _verify_fill → _cancel_unfilled + _verify_fill_with_retry로 분리. 미체결 감지 시 취소 후 잔여 수량으로 시장가 재주문 (최대 3회). 3회 모두 실패 시 실제 체결 수량만 DB 반영.
- **커밋:** `f74b3dd`

### [버그픽스] 모의투자 부분 체결 감지 + 미체결 자동 취소 (2026-03-24 22:00 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/position_db.py`, `frontend/src/components/HelpDialog.tsx`
- **내용:** 매수 주문 후 KIS 미체결 조회로 실제 체결 수량 확인, 미체결분 자동 취소, DB에 실제 체결 수량만 반영. 부분 체결 시 텔레그램 경고. VIX 구간 설명 세분화.
- **커밋:** `d2509d5`

### [개선] 헤더 새로고침 결과 toast 알림 추가 + 로고 회전 제거 (2026-03-24 21:45 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** loadAllData()에 Promise.allSettled 기반 성공/실패 집계 추가, 헤더 클릭 시 새로고침 완료/실패 toast 표시, 로고 animate-spin 제거 (animate-bounce 유지)
- **커밋:** `9366bd6`

### [버그픽스] 앱 복귀 시 세션 자동 갱신 (2026-03-24 14:40 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/AutoTrader.tsx`
- **내용:** visibilitychange 이벤트로 앱 복귀 감지 → getSession()으로 토큰 자동 갱신. PWA/모바일 백그라운드 방치 후 로그인 풀림 방지.
- **커밋:** `5287f5c`

### [버그픽스] 모의투자 구독 분리 + 시장가 매수 + 기본값 현행화 (2026-03-24 14:10 KST)
- **변경 파일:** `daemon/main.py`, `daemon/stock_manager.py`, `daemon/trader.py`, `frontend/src/lib/supabase.ts`, `frontend/src/pages/AutoTrader.tsx`
- **내용:**
  - 알림용(cross_signal+portfolio)과 모의투자용(auto_trades filled) 구독 분리 관리
  - on_execution 콜백에서 용도별 분기 (알림 종목→알림 발송, 보유 종목→손익 체크)
  - 보유 종목 우선 구독 확보 (20슬롯 한도 내), 매수/매도 후 구독 즉시 갱신
  - 매수: 지정가→시장가 전환 (미체결 방지)
  - 익절/손절 기본값 전 레이어 7%/-2%로 통일 (DB 포함)
  - AutoTrader: 현재가/수익률 표시 + refresh 버튼 추가
- **커밋:** `913661a`

### [버그픽스] 모의투자 페이지 무한 로딩 수정 (2026-03-24 10:30 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`
- **내용:** `supabase.auth.getUser()` 호출이 토큰 갱신 시 hang → localStorage 즉시 세션 복원 패턴으로 변경 (Dashboard.tsx와 동일)
- **커밋:** `a91a038`

### [버그픽스] alert_config 기본값 불일치 수정 + dead code 제거 (2026-03-24 09:30 KST)
- **변경 파일:** `daemon/stock_manager.py`
- **내용:**
  - `fetch_alert_config()` 기본값: 하드코딩 3%/-3% → config.py의 7%/-2% 참조 (DB 조회 실패 시 올바른 값 적용)
  - `fetch_alert_mode()` 도달 불가 `return "all"` dead code 제거
- **커밋:** `6e804df`

## 2026-03-23

### [버그픽스] daemon 로직 2차 진단 4건 수정 (2026-03-23 23:30 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:**
  - 매도 주문: 지정가→시장가 변경 (미체결 방지)
  - 매도 실패 시 텔레그램 알림 추가
  - 불필요한 import 제거
  - 최대 보유일 3일 제한 (초과 시 강제 청산)
- **커밋:** `2fa1772`

### [버그픽스] daemon 로직 1차 진단 3건 수정 (2026-03-23 23:00 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:**
  - 매수 실패 시 DB pending 잔재 삭제 (영구 매수 불가 방지)
  - datetime import 파일 상단으로 이동
  - 익일 보유 종목 고점 추적 초기화 (trailing stop 오발동 방지)
- **커밋:** `973a733`

### [기능] 매수 분배 로직 수정 — 종목당 100만원 기준 (2026-03-23 22:45 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:** 잔고 기준 종목당 100만원씩 균등 분배, 100만원 이하 1종목만 매수
- **커밋:** `0385560`

### [기능] Phase 2 적용 — 익일 보유 + 종목당 최소 투자금 (2026-03-23 22:30 KST)
- **변경 파일:** `daemon/trader.py`
- **내용:**
  - 15:15 청산 시 수익 +3% 이상 종목은 익일 보유 (익절 10%, trailing stop -3%)
  - 익일 보유 종목 텔레그램 알림
  - 최대 보유일 3일 제한
- **커밋:** `446b44c`

### [기능] 백테스트 연구 + daemon 설정 변경 + trailing stop 구현 (2026-03-23 22:00 KST)
- **변경 파일:** `scripts/backtest_abc.py`, `daemon/config.py`, `daemon/trader.py`, `frontend/src/pages/AutoTrader.tsx`, `docs/research/2026-03-23-backtest-abc.md`
- **내용:**
  - 일봉 200일 48조합 백테스트: 복수일 최적 a=10%/b=-2%/c=-3%, 당일청산 최적 a=5%/b=-2%/c=-3%
  - daemon 설정: 익절 3%→7%, 손절 -3%→-2%, trailing stop -3% 신규
  - trailing stop 구현: 종목별 고점 추적, 수익 중 고점 대비 3% 하락 시 매도
- **커밋:** `98615fa`

### [기능] 설정 바텀시트 추가 — 알림 대상 선택을 ⋮ > 설정으로 이동 (2026-03-23 15:30 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 포트폴리오 섹션의 알림 대상 버튼을 ⋮ 메뉴 > 설정 바텀시트로 이동, 계정 정보 표시 추가
- **커밋:** `d9c0d59`

### [버그픽스] 포트폴리오 평단/수량 오류 + 로그인 모달 안 닫히는 문제 (2026-03-23 15:00 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:**
  - 평단 오류: loadAllData()에서 DB 로드 전 portfolio.json의 잘못된 avg_price로 병합 → useEffect로 DB 로드 완료 후 병합으로 변경
  - 로그인 모달: await fetchHoldingsFromDB()가 블로킹 → fire-and-forget으로 변경
- **커밋:** `077138a`, `b7891f9`

### [버그픽스] 호가 알림 전면 중단 — UTC/KST 시간대 오류 (2026-03-23 14:00 KST)
- **변경 파일:** `daemon/alert_rules.py`
- **내용:** GCP 서버가 UTC인데 datetime.now()로 로컬 시간 사용 → KST 09:00~18:05 동안 호가 알림 전면 차단 → datetime.now(KST)로 수정
- **커밋:** `0817978`

### [버그픽스] alert_config 406 에러 + 모의투자 전용 앱키 분리 (2026-03-23 13:30 KST)
- **변경 파일:** `frontend/src/lib/supabase.ts`, `daemon/config.py`, `daemon/trader.py`
- **내용:**
  - .single()이 0건일 때 406 반환 → .maybeSingle()로 변경
  - KIS_MOCK_APP_KEY/SECRET 별도 변수 분리 (실전투자 키와 모의투자 키 분리)
- **커밋:** `1ec0260`, `ae60010`

### [기능] 당일 청산 로직 + 상한가 매수 스킵 + 미체결 취소 (2026-03-23 13:15 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/main.py`, `daemon/position_db.py`
- **내용:**
  - 15:15 보유 전 포지션 시장가 매도 (schedule_eod_close)
  - 매수 시 상한가 체크 (현재가 >= 상한가 → 스킵)
  - 15:15 청산 시 KIS 미체결 조회(VTTC8036R) → 전건 취소(VTTC0803U) + DB pending 삭제
- **커밋:** `1f1bac9`, `58f7fae`

### [기능] 모의투자 3가지 개선 — 균등분배 + 수동매도 + 잔고조회 (2026-03-23 13:00 KST)
- **변경 파일:** `daemon/trader.py`, `daemon/position_db.py`, `frontend/src/pages/AutoTrader.tsx`
- **내용:**
  1. 매수 금액: 고정 1000만원 → KIS 잔고 조회(VTTC8908R) 후 종목 수로 균등 분배
  2. daemon: sell_requested 상태 감지 → 수동 매도 실행 (manual_sell reason)
  3. 프론트엔드: 종목별 매도 버튼 + 전체 매도 버튼 (auto_trades.status → sell_requested)
- **커밋:** `c5e063a`

### [개선] 로그인 안정성 + 모달 UI 전면 개선 (2026-03-23 12:00 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** form 태그 감싸 Enter 키 동작, 에러 메시지 한글화, 로딩 중 모달 닫기 방지, createPortal z-9999, CSS 변수 기반 테마 대응, 세련된 레이아웃
- **커밋:** `d46824c`

### [기능] 알림 대상 모드 선택 — 교차신호+포트폴리오 / 포트폴리오만 (2026-03-23 11:00 KST)
- **변경 파일:** `daemon/sql/create_alert_config.sql`, `daemon/stock_manager.py`, `frontend/src/lib/supabase.ts`, `frontend/src/pages/Dashboard.tsx`
- **내용:** Supabase alert_config 테이블 기반 알림 모드 선택. 프론트엔드 포트폴리오 섹션에 토글 버튼, daemon에서 폴링하여 portfolio_only 모드 시 cross_signal 구독 스킵
- **사전 작업 필요:** Supabase Dashboard에서 `daemon/sql/create_alert_config.sql` 실행
- **커밋:** `f5d65aa`

### [버그픽스] 호가 알림 과다 발생 수정 — 장 초반 억제 + 수급 전환 조건 강화 (2026-03-23 10:30 KST)
- **변경 파일:** `daemon/alert_rules.py`, `daemon/tests/test_alert_rules.py`
- **내용:** 장 초반(09:00~09:05) 호가 알림 억제, 수급 전환 최소 데이터 2→10개, buy/sell 독립 쿨다운→단일 쿨다운
- **원인:** 호가 수신 빈도(초당 10회)와 쿨다운(5분)의 불균형 + 장 초반 비정상 호가에 과민 반응 + buy/sell 독립 쿨다운으로 같은 종목 수급 전환 반복
- **커밋:** `14e41d1`

### [버그픽스] 포트폴리오 리프레쉬 버튼 영구 로딩 수정 (2026-03-23 10:00 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** refreshPortfolioPrices가 IIFE 렌더 함수 안에서 정의되어 리렌더링 시 타이밍 이슈로 스피닝 지속 → 컴포넌트 최상위 레벨로 이동하여 해결
- **원인:** setPriceRefreshing(true) → 리렌더링 → IIFE 재실행 → 새 함수 생성 → finally 상태 불일치
- **커밋:** `751fb9b`

## 2026-03-22

### [버그픽스] 모의투자 헤더를 공통 헤더로 통합 (2026-03-22 16:30 KST)
- **변경 파일:** `frontend/src/pages/AutoTrader.tsx`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/App.tsx`
- **내용:** 모의투자 페이지의 독자 헤더 제거, Dashboard 공통 헤더를 공유하도록 변경. 탭 활성화를 page prop 기반으로 일반화
- **커밋:** `42e5172`

### [기능] 패턴 매칭 D+1~D+5 일별 수익률 표시 (2026-03-22 16:00 KST)
- **변경 파일:** `scripts/run_all.py`, `frontend/src/pages/Dashboard.tsx`
- **내용:** D+5만 보여주던 것을 D+1~D+5 각 거래일 실제 수익률로 확장, 태그 배열로 일별 추이 표시
- **커밋:** `6ba489b`

### [개선] 패턴 매칭 로직 전면 교체 — 현재↔과거 비교로 변경 (2026-03-22 15:30 KST)
- **변경 파일:** `scripts/run_all.py`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/HelpDialog.tsx`
- **내용:**
  - 기존: 대상 종목의 오늘 패턴 vs 다른 종목의 오늘 패턴 (동일 시점 비교, 예측 가치 없음)
  - 변경: 대상 종목의 오늘 패턴 vs intraday-history 과거 시점 패턴 (실제 D+5 수익률 포함)
  - 과거 풀 233건(87개 종목), 마지막 엔트리 제외로 현재↔현재 비교 방지
  - 프론트엔드: 과거 패턴 날짜 + 종목명 표시, 도움말 업데이트
- **커밋:** `fba248f`

### [버그픽스] 패턴 매칭 D+5 빈값 수정 — peer를 stock-history 보유 종목으로 필터링 (2026-03-22 14:30 KST)
- **변경 파일:** `scripts/run_all.py`
- **내용:** intraday-history(677종목)에서 peer를 선택하나 stock-history(153종목)에만 일봉이 있어 D+5 전부 null → peer 후보를 _close_map 6일 이상 종목으로 한정, 비교 풀 405→136, D+5 표시율 0%→100%
- **커밋:** `b65452b`

### [버그픽스] 시뮬레이션 0건 수정 — signal history 날짜 파싱 오류 (2026-03-22 12:20 KST)
- **변경 파일:** `scripts/run_all.py`
- **내용:** data_loader가 파일명 stem 전체를 date로 반환(vision_2026-03-20_1945)하여 stock-history 날짜와 불일치 → 정규식으로 YYYY-MM-DD 추출, 같은 날짜 중복 snapshot 제거
- **커밋:** `1e08f4d`

### [기능] 전략 시뮬레이션 + 패턴 매칭 데이터 보강 (2026-03-22 12:05 KST)
- **변경 파일:** `scripts/run_all.py`, `frontend/src/pages/Dashboard.tsx`
- **내용:** stock-history 일봉으로 price_d0~d5 역산하여 시뮬레이션 구현, 유사 종목 5일 수익률(future_return) 산출, 프론트엔드 데이터 부족 안내 + future_return 표시 개선
- **커밋:** `f8e615c`

### [버그픽스] 모의투자 페이지 — 헤더 로고 + 빈 데이터 안내 + 무한 로딩 방지 (2026-03-22 11:38 KST)
- **변경 파일:** `frontend/src/pages/PaperTrading.tsx` (추정)
- **내용:** 모의투자 페이지에 헤더 로고 추가, 빈 데이터 시 안내 표시, 무한 로딩 방지
- **커밋:** `d54ad3d`

### [버그픽스] iOS PWA 상단 safe area 콘텐츠 비침 방지 (2026-03-22 11:35 KST)
- **변경 파일:** 프론트엔드 CSS/HTML
- **내용:** iOS PWA 상단 safe area에 콘텐츠가 비치는 문제 수정
- **커밋:** `9e40660`

### [기능] 로고 클릭 시 데이터 새로고침 + 시각적 피드백 (2026-03-22 11:31 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** 로고 클릭 시 데이터 새로고침 트리거 + 시각적 피드백 애니메이션
- **커밋:** `2ab3d8a`

### [버그픽스] 로그인 상태 유실 방지 (2026-03-22 11:25 KST)
- **변경 파일:** 프론트엔드 인증 관련 파일
- **내용:** 로그인 상태 유실 3가지 원인 수정
- **커밋:** `ac4167b`

### [버그픽스] 포트폴리오 평단 오류 근본 수정 (2026-03-22 11:20 KST)
- **변경 파일:** 프론트엔드 포트폴리오 컴포넌트
- **내용:** dbHoldingsRef를 useRef로 변경하여 평단 오류 근본 수정
- **커밋:** `6e101df`

### [개선] 데몬 안정화 — 위험 요소 전면 수정 + 2차/3차 진단 (2026-03-22 11:01~11:15 KST)
- **변경 파일:** `daemon/` 디렉토리 다수
- **내용:** 8건 위험 요소 전면 수정, 2차 진단 4건 수정, 3차 진단 3건 개선, 불필요한 지역 import asyncio 제거
- **커밋:** `adf2bc2`, `53d26a6`, `2d4ba5b`, `7cb8995`

### [리팩토링] iOS safe area 통합 — 업계 권장 방식 (2026-03-22 09:00~10:18 KST)
- **변경 파일:** `frontend/index.html`, `frontend/src/index.css`, `frontend/src/pages/Dashboard.tsx`
- **내용:** 다이나믹 아일랜드 대응을 위해 여러 차례 수정 후 최종적으로 body padding 방식으로 통합. 메뉴 팝업 라이트 테마 대응, sticky 헤더 safe-area-inset-top 적용, 상태바 default 변경
- **커밋:** `db9cac5`, `fb8ba9d`, `4723bb8`, `65b03f0`, `b1fc066`, `65eb7f1`

### [버그픽스] cron-job.org 무한 트리거 방지 (2026-03-22 09:50 KST)
- **변경 파일:** `.github/workflows/` 또는 관련 스크립트
- **내용:** cron-job.org 무한 트리거 방지 안전장치 3중 추가
- **커밋:** `575426c`

### [버그픽스] 로그아웃 버튼 클릭 불가 — 메뉴 UI 전면 재구현 (2026-03-22 00:34~00:57 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/` 관련
- **내용:** 로그인/로그아웃 불안정 → z-index 조정 → stopPropagation → fixed 이동 → 바텀시트 모달 재구현 → 최종 createPortal로 document.body에 직접 렌더하여 해결
- **커밋:** `612eb5c`, `8749300`, `21a7c68`, `9e926dc`, `fd94ec5`, `38a1d69`, `d8a3f9a`, `c4941da`, `c5e4149`

### [기능] 포트폴리오 기능 강화 — 체크박스 선택 계산 + 총 손익 (2026-03-22 00:26~00:30 KST)
- **변경 파일:** 프론트엔드 포트폴리오 컴포넌트
- **내용:** 포트폴리오 평단 오류 수정(DB avg_price 우선), 종목별 체크박스로 투자금/평가금/수익률 선택 계산, 총 손익 금액 표시
- **커밋:** `73497d3`, `713867d`, `67af69e`

### [버그픽스] 네비게이션 + 대시보드 정리 (2026-03-22 00:14~00:31 KST)
- **변경 파일:** 프론트엔드 페이지 컴포넌트
- **내용:** 대시보드 탭에서 포트폴리오 섹션 제거(포트폴리오 탭 전용), 스캐너/모의투자 페이지에 통일된 4탭 네비게이션 적용
- **커밋:** `73369d4`, `d591510`

### [개선] daemon 설정 수정 (2026-03-22 00:14~00:22 KST)
- **변경 파일:** `daemon/` 관련
- **내용:** GitHub 레포명 수정(theme_analysis → theme-analyzer), 주말/공휴일/장외 시간 체크 추가
- **커밋:** `4d776a6`, `04187e6`

### [버그픽스] AI 브리핑 표시 오류 수정 (2026-03-22 00:10~00:11 KST)
- **변경 파일:** 프론트엔드 브리핑 관련 컴포넌트
- **내용:** AI 브리핑 파싱 오류(잔여 번호/콜론 제거 + 가독성 개선), 빈 불릿(초록 점만) 제거, 빈 본문 시 "해당 항목 없음" 표시
- **커밋:** `733475f`, `81385cd`, `0c9ab0a`

### [버그픽스] 모바일 safe area + iOS 상태 바 (2026-03-22 00:05~00:08 KST)
- **변경 파일:** `frontend/index.html`, `frontend/src/index.css`
- **내용:** viewport-fit=cover + 하단 바 패딩 적용, iOS 상태 바 테마 색상 동기화 복원
- **커밋:** `f611c23`, `31eab4c`

### [버그픽스] 포트폴리오 무한 리렌더 수정 (2026-03-22 00:04 KST)
- **변경 파일:** 프론트엔드 포트폴리오 컴포넌트
- **내용:** stale closure + finally 블록으로 인한 무한 리렌더 수정
- **커밋:** `6bfcde0`

## 2026-03-21

### [기능] 모의투자 리포트 페이지 + 자동매매 (2026-03-21 23:55 KST)
- **변경 파일:** 프론트엔드 모의투자 페이지, `daemon/` 관련
- **내용:** 모의투자 리포트 페이지 신규, 익절 기준 +3%로 변경, daemon에 모의투자 자동매매 구현(고확신 종목 매수 + 익절 +3% / 손절 -3%)
- **커밋:** `9c927be`, `c8d74ea`

### [개선] daemon 호가 구독 + 알림 태그 제거 (2026-03-21 23:04~23:09 KST)
- **변경 파일:** `daemon/` 관련
- **내용:** 호가(H0STASP0) 구독 추가(수급 반전 + 호가 벽 감지), 알림 메시지에서 [ST] 태그 제거
- **커밋:** `8a944ac`, `cef0a46`

### [기능] KIS WebSocket 실시간 알림 데몬 구현 (2026-03-21 23:30 KST)
- **변경 파일:** `daemon/` 디렉토리 전체 (15파일 신규 생성), `docs/research/2026-03-21-gcp-migration.md`, `docs/superpowers/plans/2026-03-21-websocket-alert-daemon.md`
- **내용:**
  - GCP e2-micro 독립 실행용 WebSocket 알림 데몬 (`daemon/` 디렉토리)
  - KIS WebSocket(H0STCNT0) 체결가 실시간 수신 + PINGPONG + 자동 재연결
  - 알림 엔진: 급등(+5/10/15%), 급락(-3/5%), 거래량 폭증(5분 3배), 목표가 도달
  - Telegram 비동기 알림 발송 ([ST] 태그), 쿨다운(5분) 중복 방지
  - GitHub Pages JSON 폴링으로 구독 종목 자동 갱신 (cross_signal + portfolio)
  - GCP 이전 연구 문서 (비용 분석, side-effect 진단, 알림 중복 분석)
  - 기존 코드 변경 제로, 테스트 21건 PASS, 기존 55건 영향 없음
- **커밋:** `f96fe11`

## 2026-03-20

### [기능] KIS API 확장 — 호가/투자자동향 + MCP 연결 (2026-03-20 14:00 KST)
- **변경 파일:** `core/kis_client.py`, `scripts/generate_missing_data.py`, `tests/test_kis_client.py`, `docs/research/2026-03-20-kis-improvement.md`, `docs/superpowers/plans/2026-03-20-kis-api-expansion.md`, `~/.claude/settings.local.json`
- **내용:**
  - **Phase 1:** kis_client.py에 `get_asking_price` (호가 5단계, TR:FHKST01010200), `get_investor` (투자자동향, TR:FHKST01010900) 메서드 추가
  - **Phase 1:** gen_orderbook()에서 KIS 호가 실데이터 시도 → 실패 시 기존 mock 폴백 (side-effect 없음)
  - **Phase 2:** KIS Code Assistant MCP를 Claude Code 개발 도구로 연결 (settings.local.json)
  - **연구:** docs/research/2026-03-20-kis-improvement.md (KIS API 334개 중 활용 현황 + 개선 포인트)
  - **테스트:** 4건 추가 (전체 55건 PASS)
- **커밋:** `8c62a8f`

## 2026-03-18

### [기능] 실시간 데이터 격차 해소 — 10회 연구 결과 구현 (2026-03-18 16:00 KST)
- **변경 파일:** `scripts/run_all.py`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/HelpDialog.tsx`, `frontend/src/components/RefreshButtons.tsx`, `.github/workflows/deploy-pages.yml`, `docs/research/2026-03-18-realtime-gap.md`
- **내용:**
  - **Intraday Overlay:** cross_signal/smart_money에 장중 등락률·수급·거래량 오버레이, intraday_score, validation(신호유효/약화/무효화)
  - **신뢰도 Decay:** 0.98^h 공식, signal_age_hours, decayed_confidence 필드
  - **장중 급등 경보:** surge_alerts.json (등락률>15% + 거래량>200%, 6건 감지)
  - **수급 반전 강화:** 시점 간 가속/둔화 추세 판정 (trend 필드)
  - **미활용 데이터 활용:** market_breadth(5스냅샷), program_detail(12투자자유형), investor_trend_stocks(10일 추세 20종목)
  - **인프라:** deploy-pages concurrency 제어, 필수 JSON 검증 스텝, RefreshButtons 90초 중복 방지
  - **UX:** 교차 신호/스마트머니 카드에 overlay 표시, 타임스탬프 가시성 개선
- **연구:** docs/research/2026-03-18-realtime-gap.md (10회 연구, ~1,500줄)
- **커밋:** `a01fbbd`

## 2026-03-17

### [버그픽스] 크로스 시그널 #None + 점수 누락 수정 (2026-03-17 22:50 KST)
- **변경 파일:** `modules/cross_signal.py`
- **내용:** theme_rank None → 테마 배열 순서 폴백, score(존재하지 않음) → confidence 필드 사용(백분율 표시)
- **원인:** 테마 데이터에 rank 키 부재, 시그널 데이터에 score 키 없고 confidence 키만 존재
- **커밋:** `a215273`

### [개선] 외부 데이터 활용 종합 개선 — Tier 1~3 (2026-03-17 15:00 KST)
- **변경 파일:** `scripts/run_all.py`, `docs/research/2026-03-17-data-utilization.md`
- **내용:**
  - **연구:** theme-analyzer(10개 파일) + signal-pulse(8개 파일) 전체 재조사, 18건 활용 방안 도출
  - **Tier 1 버그 수정 (3건):** volume_profile 키매핑 수정(0→20건), intraday_heatmap 파싱 수정(0값→실데이터), pattern 매칭 로직 전면 교체(intraday-history 교차 비교, 0→7건)
  - **Tier 2 기존 기능 개선 (7건):** paper_trading 25일 히스토리 추가, forecast_accuracy 대장주 코드 기준 매칭(0%→75%), simulation_history 48일 집계(0→15건), valuation fundamental_data 폴백+EPS성장률/52주위치, premarket 시황맥락+미국시장+투자자동향5일, short_squeeze 공매도/골든크로스 필드 추가, indicator_history F&G/VIX 트렌드 추가
  - **Tier 3 신규 기능 (4건):** intraday_stock_tracker(장중 종목별 수급 전환 감지), consecutive_monitor(연속 상승/하락 모니터), volume_profile_alerts(매물대 지지/저항 경보 23건), source_performance(vision/kis/combined 성과 비교)
  - **데이터 활용률:** theme-analyzer 18.5%→~80%, 빈 JSON 6개→0개

## 2026-03-16

### [기능] Light/Dark 모드 전면 개편 — 금융 앱 스타일 (2026-03-16 10:00 KST)
- **변경 파일:** `frontend/src/index.css`, `frontend/src/App.tsx`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Scanner.tsx`, `frontend/src/components/HelpDialog.tsx`, `frontend/src/components/RefreshButtons.tsx`
- **내용:** CSS 변수 기반 테마 시스템 구축. Light(슬레이트+흰 카드) / Dark(네이비#0b0f14+다크카드#131a24). 헤더 테마 토글 버튼, 퀵 네비/섹션/카드/텍스트 전체 CSS 변수 적용, localStorage 저장 + prefers-color-scheme 자동 감지.
- **커밋:** `0093f74`

### [버그픽스] 새로고침 시 퀵 네비 '신호' 선택 버그 수정 (2026-03-16 08:20 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** scrollY < 100일 때 항상 '시장' 활성화. IntersectionObserver rootMargin 조정.
- **커밋:** `bbad24c`

### [버그픽스] investor_data None 값 TypeError + full 모드 KeyError 수정 (2026-03-16 07:47 KST)
- **변경 파일:** `scripts/run_all.py`, `modules/cross_signal.py`
- **내용:** investor_data의 foreign_net/individual_net 등이 None일 때 sum() TypeError 발생 → `(inv.get("key") or 0)` 패턴으로 전체 11개소 일괄 수정. full 모드에서 cross_signal의 `m['signal']` KeyError → `m.get('vision_signal')` 안전 접근으로 수정.
- **커밋:** `c94e59b`, `bd8f78a`

### [기능] 로고 클릭 시 캐시 삭제 + 새로고침 (2026-03-16 07:30 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`
- **내용:** Stock Toolkit 로고/사이트명 클릭 시 Cache Storage 전체 삭제 + Service Worker 해제 + 페이지 새로고침.
- **커밋:** `99bb3e1`

## 2026-03-15

### [개선] UX/UI 전면 개선 — 가독성/레이아웃/직관성 (2026-03-15 22:40 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Scanner.tsx`, `frontend/src/components/HelpDialog.tsx`, `frontend/src/components/RefreshButtons.tsx`, `frontend/src/App.tsx`
- **내용:** 카테고리 퀵 네비(iOS 세그먼트 스타일, IntersectionObserver 활성 추적), 장전 프리마켓 카드형 개선, AI 모닝 브리핑 섹션별 카드 분리(🌍🔥🎯⚠️💡), 환율/매크로/선물 카드형 통일, 시장 심리 온도계를 시장 현황에 통합, 밸류에이션 서브텍스트 2줄 분리, 서브타이틀/라벨/설명문 폰트 스타일 전체 통일, 호가창 bid/ask 재계산, 컨센서스 0원 처리, 시뮬레이션 전략 한국어화, 투자자 동향 데이터 구조 매핑 수정, Empty 컴포넌트 보강, 최상단 이동 플로팅 버튼, 도움말 팝업 React Portal, 갱신 버튼 토스트, 하단 네비바 safe-area, F&G 소수점 반올림.
- **커밋:** `1c134cd` ~ `1f20b7f`

### [기능] 주요 선물 6종 + cron-job PAT 토큰 갱신 (2026-03-15 21:30 KST)
- **변경 파일:** `scripts/run_all.py`, `frontend/src/pages/Dashboard.tsx`
- **내용:** theme-analyzer macro-indicators.json의 futures 키 신규 연동 (코스피200 주간/야간, S&P500, 나스닥, 원유, 금 선물). cron-job.org 7개 잡에 stock_toolkit용 GitHub PAT 토큰 적용.
- **커밋:** `64a4c80`

### [기능] 데이터 활용률 100% 달성 — 33개 항목 전체 구현 (2026-03-15 15:30 KST)
- **변경 파일:** `core/data_loader.py`, `scripts/run_all.py`, `modules/cross_signal.py`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Scanner.tsx`, `frontend/src/services/dataService.ts`, `frontend/src/components/HelpDialog.tsx`
- **내용:** DataLoader 6개 메서드 추가, run_all.py Phase 1~7 전면 보강, kis_gemini 실데이터(PER/PBR/호가/RSI) 연동, investor-intraday 히트맵, 이중 신호 검증(dual_signal), 매크로/환율/F&G추세/테마예측 통합, 증권사 매매/거래대금 TOP/모의투자/예측적중률 신규 섹션 4개, Scanner UI 7개 필터 추가(골든크로스/BNF/공매도/신고가/RSI/이중매칭), kis_analysis 4차원 점수, Volume Profile 지지/저항, 신호 일관성 추적, 시뮬레이션 히스토리, 장중 종목별 수급.
- **커밋:** `6db18ac` ~ `7f22409`

### [기능] 대시보드 8개 누락 JSON 데이터 파일 생성 (2026-03-15 14:07 KST)
- **변경 파일:** `scripts/generate_missing_data.py`, `frontend/public/data/insider_trades.json`, `frontend/public/data/consensus.json`, `frontend/public/data/auction.json`, `frontend/public/data/orderbook.json`, `frontend/public/data/correlation.json`, `frontend/public/data/earnings_calendar.json`, `frontend/public/data/ai_mentor.json`, `frontend/public/data/trading_journal.json`
- **내용:** DART API(내부자거래 실제 데이터 10건, 실적공시 20건 취득 성공), signal-pulse/theme-analyzer 소스 데이터 활용. correlation은 외국인 순매수 Pearson 상관계수(10종목), consensus는 증권사 목표주가 6종목, auction·orderbook은 rising stocks 기반 플레이스홀더, ai_mentor는 시장상황+신호 기반 6개 조언, trading_journal은 SK하이닉스+LG CNS 2건 등록.

### [기능] 투자 아이디어 5차 연구 — 10개 신규 아이디어 (2026-03-15 03:30 KST)
- **변경 파일:** `docs/research/2026-03-15-investment-ideas-5.md`
- **내용:** 기존 25개와 겹치지 않는 10개 신규 아이디어(#26~#35) 연구. 호가창 압력 분석기, 대주주/내부자 거래 추적기, 기관 컨센서스 괴리 탐지기, 테마 전이 예측기, 시간대별 수익률 히트맵, 동시호가 이상 감지기, 프로그램 매매 역추적기, 수급 클러스터 분석기, 손절/익절 최적화 엔진, 이벤트 캘린더 복합 분석기. 5차 비교표 + 추천 우선순위 + 1~5차 통합 로드맵(35개) 포함.

### [기능] 신규 모듈 10개 구현 — #16~#25 (2026-03-15 02:30 KST)
- **변경 파일:** `modules/short_squeeze.py`, `modules/earnings_preview.py`, `modules/portfolio_advisor.py`, `modules/sentiment_index.py`, `modules/correlation_network.py`, `modules/gap_analyzer.py`, `modules/valuation_screener.py`, `modules/volume_price_divergence.py`, `modules/ai_mentor.py`, `modules/premarket_monitor.py`
- **내용:** 공매도 역발상(#16), 실적 서프라이즈 프리뷰(#17), 포트폴리오 리밸런싱(#18), 시장 심리 온도계(#19), 종목 상관관계(#20), 갭 분석(#21), 밸류에이션 스크리너(#22), 거래량-가격 괴리(#23), AI 투자 멘토(#24), 장전 프리마켓 모니터(#25) 구현. 전 모듈 smoke test 통과.

### [기능] 투자 아이디어 4차 연구 — 10개 신규 아이디어 (2026-03-15 01:30 KST)
- **변경 파일:** `docs/research/2026-03-15-investment-ideas-4.md`
- **내용:** 기존 15개와 겹치지 않는 10개 신규 아이디어(#16~#25) 연구. 공매도 역발상, 실적 서프라이즈 프리뷰, 포트폴리오 리밸런싱, 시장 심리 온도계, 상관관계 네트워크, 갭 분석, 밸류에이션 스크리너, 거래량-가격 괴리, AI 투자 멘토, 프리마켓 모니터. 4차 비교표 + 추천 우선순위 + 1~4차 통합 로드맵 포함.

### [개선] UI/UX 전면 개편 — Light 테마 + 도움말 + 지표 해석 (2026-03-15 00:10 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Scanner.tsx`, `frontend/src/App.tsx`, `frontend/src/index.css`, `frontend/src/components/HelpDialog.tsx`
- **내용:** shadcn 스타일 Light 테마 적용, 모든 섹션에 ? 도움말 팝업, 모든 수치에 해석 텍스트 추가, 2열 그리드 레이아웃, lucide-react 아이콘 통합.
- **커밋:** `498a1d1`

### [기능] PWA + 버블차트 + 종목 스캐너 페이지 (2026-03-15 00:00 KST)
- **변경 파일:** `frontend/vite.config.ts`, `frontend/index.html`, `frontend/src/App.tsx`, `frontend/src/pages/Scanner.tsx`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/services/dataService.ts`, `scripts/run_all.py`
- **내용:** PWA(manifest+ServiceWorker+오프라인캐시), recharts 버블차트(테마 라이프사이클), 체크박스 필터 기반 종목 스캐너 페이지, HashRouter 라우팅, 하단 네비게이션.
- **커밋:** `e600291`

### [기능] 대시보드 전체 모듈 추가 (2026-03-14 23:50 KST)
- **변경 파일:** `frontend/src/pages/Dashboard.tsx`, `frontend/src/services/dataService.ts`, `scripts/run_all.py`, `frontend/public/data/*.json`
- **내용:** 교차신호, 라이프사이클, 위험종목, 뉴스임팩트, AI브리핑, 시뮬레이션, 패턴매칭 섹션 추가. run_all.py에 cross_signal, risk_monitor, briefing, simulation, pattern JSON 저장 추가.
- **커밋:** `2b61675`, `6547c73`, `4e3a2de`

### [설정] 텔레그램 연결 + GitHub 원격 저장소 설정 (2026-03-14 23:30 KST)
- **변경 파일:** `.env`, `.github/workflows/deploy-pages.yml`, `.github/workflows/phase1-alerts.yml`
- **내용:** 텔레그램 봇 토큰/chat_id 설정, GitHub remote 연결(xxonbang/stock_toolkit), GitHub Pages 배포, Gemini API 키 5개 설정, GitHub Secrets 저장.
- **커밋:** `ecc3288`, `89c995a`, `606b135`, `e71cf08`, `18cbd01`

## 2026-03-14

### [기능] 전체 통합 — 실행 스크립트 + 봇 핸들러 + CI/CD (2026-03-14 23:09 KST)
- **변경 파일:** `scripts/run_phase4.py`, `scripts/run_all.py`, `bot/handlers.py`, `.github/workflows/deploy-pages.yml`
- **내용:** Phase 4 실행 스크립트(라이프사이클+패턴매칭), 전체 Phase 1~4 통합 실행(run_all.py), 텔레그램 봇 핸들러(scan/top/stock/market), GitHub Pages 배포 워크플로우 생성.
- **커밋:** `8884cd1`

### [기능] 통합 프론트엔드 — React + Vite + TailwindCSS 대시보드 (2026-03-14 23:08 KST)
- **변경 파일:** `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/index.css`, `frontend/src/App.tsx`, `frontend/src/services/dataService.ts`, `frontend/src/pages/Dashboard.tsx`
- **내용:** React 18 + Vite 6 + TailwindCSS 4 기반 프론트엔드 셋업. 시장 현황, 시스템 성과, 이상 거래, 스마트 머니, 섹터 자금 흐름 대시보드 구현.
- **커밋:** `0d40330`

### [기능] 패턴 매칭 — 코사인 유사도 기반 차트 패턴 비교 (2026-03-14 23:06 KST)
- **변경 파일:** `modules/pattern_matcher.py`, `tests/test_pattern_matcher.py`
- **내용:** 패턴 정규화, 코사인 유사도 계산, 유사 패턴 검색, 결과 포매터 구현. pytest 4건 통과.
- **커밋:** `80730f6`

### [기능] 매매 일지 & AI 회고 (2026-03-14 23:06 KST)
- **변경 파일:** `modules/trading_journal.py`, `tests/test_trading_journal.py`
- **내용:** 매매 맥락 매칭, 편향 탐지(추격 매수/섹터 편중), 매매 통계, Gemini 기반 AI 회고 일지 생성. pytest 4건 통과.
- **커밋:** `0bf6882`

### [기능] 리스크 모니터 (2026-03-14 23:05 KST)
- **변경 파일:** `modules/risk_monitor.py`, `tests/test_risk_monitor.py`
- **내용:** 종목 위험도 평가(신호 악화/외국인 매도/MA20 이탈/공매도/투매 징후), 섹터 편중 감지, 알림 포매터. pytest 3건 통과.
- **커밋:** `e6d7fec`

### [기능] 테마 라이프사이클 트래커 (2026-03-14 23:05 KST)
- **변경 파일:** `modules/theme_lifecycle.py`, `tests/test_theme_lifecycle.py`
- **내용:** 테마 단계 분류(탄생/성장/과열/쇠퇴), 트렌드 계산, 라이프사이클 추적, 알림 포매터. pytest 5건 통과.
- **커밋:** `07b62f0`

### [기능] 시나리오 시뮬레이터 (2026-03-14 23:04 KST)
- **변경 파일:** `modules/scenario_simulator.py`, `tests/test_scenario_simulator.py`
- **내용:** 전략 파서, 백테스트, 전략 비교, 결과 포매터. stop-loss 지원. pytest 3건 통과.
- **커밋:** `651c694`

### [기능] Phase 3 실행 스크립트 (2026-03-14 23:03 KST)
- **변경 파일:** `scripts/run_phase3.py`
- **내용:** Phase 3 통합 실행 — 뉴스 임팩트 DB 구축 + 시나리오 시뮬레이션.
- **커밋:** `dbd6fa4`

### [기능] 뉴스 임팩트 분석기 (2026-03-14 23:03 KST)
- **변경 파일:** `modules/news_impact.py`, `tests/test_news_impact.py`
- **내용:** 뉴스 유형 분류, 주가 영향도 통계, 임팩트 DB 구축, 알림 포매터. pytest 2건 통과.
- **커밋:** `8f58f7c`

### [기능] Phase 2 실행 스크립트 (2026-03-14 23:02 KST)
- **변경 파일:** `scripts/run_phase2.py`
- **내용:** Phase 2 통합 실행 — 이상 거래 탐지, 스마트 머니 분석, 섹터 자금 흐름.
- **커밋:** `aaa777c`

### [기능] 섹터 자금 흐름 맵 (2026-03-14 23:01 KST)
- **변경 파일:** `modules/sector_flow.py`, `tests/test_sector_flow.py`
- **내용:** 섹터별 집계, 로테이션 감지, 포맷터. pytest 2건 통과.
- **커밋:** `4bf8431`

### [기능] 스마트 머니 수급 레이더 (2026-03-14 23:01 KST)
- **변경 파일:** `modules/smart_money.py`, `tests/test_smart_money.py`
- **내용:** 스마트 머니 스코어링, 매집 패턴 탐지, 수급 흐름 분류, 알림 포매터. pytest 4건 통과.
- **커밋:** `0279505`

### [기능] 이상 거래 탐지 (2026-03-14 23:01 KST)
- **변경 파일:** `modules/anomaly_detector.py`, `tests/test_anomaly_detector.py`
- **내용:** 거래량 폭발, 동시 급등, 갭, 가격 급변 탐지 및 통합 스캔, 알림 포매터. pytest 4건 통과.
- **커밋:** `e27b8b7`

### [기능] Phase 1 실행 스크립트 + GitHub Actions 워크플로우 (2026-03-14 23:00 KST)
- **변경 파일:** `scripts/run_phase1.py`, `.github/workflows/phase1-alerts.yml`
- **내용:** Phase 1 통합 실행 스크립트 및 GitHub Actions workflow_dispatch 워크플로우.
- **커밋:** `defc025`

### [기능] 모닝 브리프 & 이브닝 리뷰 (2026-03-14 22:59 KST)
- **변경 파일:** `modules/daily_briefing.py`, `tests/test_daily_briefing.py`
- **내용:** 컨텍스트 빌더 및 Gemini 프롬프트 기반 브리핑 생성. pytest 2건 통과.
- **커밋:** `a7f2b38`

### [기능] 커스텀 종목 스캐너 (2026-03-14 22:59 KST)
- **변경 파일:** `modules/stock_scanner.py`, `tests/test_stock_scanner.py`
- **내용:** 조건 파서, 조건 평가, 종목 필터링, 결과 포매터. pytest 6건 통과.
- **커밋:** `3aac205`

### [기능] 시스템 성과 대시보드 (2026-03-14 22:58 KST)
- **변경 파일:** `modules/__init__.py`, `modules/system_performance.py`, `tests/test_system_performance.py`
- **내용:** 적중률, 평균수익률, 시장국면 분류, 소스별 성과 분석. pytest 4건 통과.
- **커밋:** `4000247`

### [기능] 데이터 로더 (2026-03-14 22:57 KST)
- **변경 파일:** `core/__init__.py`, `core/data_loader.py`, `tests/test_data_loader.py`
- **내용:** DataLoader 클래스 — theme/signal JSON 파일 로딩, 캐싱, 통합 조회. pytest 5건 통과.
- **커밋:** `76eb560`

### [기능] 텔레그램 봇 + Gemini 클라이언트 (2026-03-14 22:57 KST)
- **변경 파일:** `core/telegram_bot.py`, `core/gemini_client.py`, `bot/__init__.py`, `bot/formatters.py`
- **내용:** 텔레그램 메시지 전송 함수, 종목 카드/섹션 포매터, Gemini API 라운드로빈 클라이언트.
- **커밋:** `0dfaef6`

### [설정] 프로젝트 초기화 (2026-03-14 22:55 KST)
- **변경 파일:** `requirements.txt`, `.env.example`, `.gitignore`, `config/__init__.py`, `config/settings.py`
- **내용:** git 저장소 초기화, 의존성 정의, 환경변수 템플릿, 설정 모듈 생성.
- **커밋:** `8f1d9db`
