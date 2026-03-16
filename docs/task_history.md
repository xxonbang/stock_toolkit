# Task History

## 2026-03-16

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
