# Stock Toolkit 구현 계획서

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** theme_analysis + signal_analysis의 데이터를 종합 활용하는 14개 투자 도구를 단일 프로젝트로 구현

**Architecture:** Python 백엔드 + React 프론트엔드. 공통 데이터 접근 레이어가 두 프로젝트의 JSON 결과물을 읽고, 각 기능 모듈이 이를 가공하여 텔레그램 알림 또는 웹 대시보드로 출력. GitHub Actions로 자동화.

**Tech Stack:** Python 3.11, React 18 + TypeScript + TailwindCSS, Vite, Gemini API, KIS API, Telegram Bot API, Supabase, GitHub Actions, pykrx, numpy/scipy

---

## 프로젝트 구조

```
stock_toolkit/
├── config/
│   └── settings.py              # 환경변수, API키, 경로 설정
├── core/
│   ├── data_loader.py           # theme_analysis/signal_analysis JSON 로더
│   ├── telegram_bot.py          # 텔레그램 봇 (공통)
│   ├── gemini_client.py         # Gemini API 클라이언트 (키 로테이션)
│   └── models.py                # 공통 데이터 모델
├── modules/
│   ├── cross_signal.py          # #1  크로스 시그널 알림
│   ├── daily_briefing.py        # #2  모닝 브리프 & 이브닝 리뷰
│   ├── theme_lifecycle.py       # #3  테마 라이프사이클 트래커
│   ├── risk_monitor.py          # #4  보유종목 리스크 모니터
│   ├── smart_money.py           # #7  스마트 머니 수급 레이더
│   ├── trading_journal.py       # #8  매매 일지 & AI 회고
│   ├── news_impact.py           # #9  뉴스 임팩트 분석기
│   ├── stock_scanner.py         # #10 커스텀 종목 스캐너
│   ├── system_performance.py    # #11 시스템 성과 대시보드
│   ├── sector_flow.py           # #12 섹터 자금 흐름 맵
│   ├── pattern_matcher.py       # #13 종목 유사 패턴 매칭
│   ├── anomaly_detector.py      # #14 이상 거래 탐지
│   └── scenario_simulator.py    # #15 투자 시나리오 시뮬레이터
├── bot/
│   ├── handlers.py              # 텔레그램 봇 명령어 핸들러
│   └── formatters.py            # 텔레그램 메시지 포매터
├── frontend/
│   ├── src/
│   │   ├── pages/               # 기능별 페이지
│   │   ├── components/          # 공통 컴포넌트
│   │   └── services/            # API/데이터 서비스
│   └── public/data/             # 생성된 JSON 데이터
├── scripts/
│   ├── run_phase1.py            # Phase 1 실행
│   ├── run_phase2.py            # Phase 2 실행
│   ├── run_phase3.py            # Phase 3 실행
│   ├── run_phase4.py            # Phase 4 실행
│   └── run_all.py               # 전체 실행
├── tests/                       # 모듈별 테스트
├── .github/workflows/           # GitHub Actions
├── results/                     # 분석 결과 JSON
├── requirements.txt
└── .env.example
```

## 외부 데이터 경로 (읽기 전용)

```
theme_analysis/frontend/public/data/
├── latest.json, theme-forecast.json, intraday-history.json
├── volume-profile.json, macro-indicators.json, investor-intraday.json
├── history/ (90일+), forecast-history/ (20일+), paper-trading/

signal_analysis/results/
├── vision/vision_analysis.json, kis/kis_analysis.json
├── combined/combined_analysis.json
├── kis/fear_greed.json, kis/vix.json, kis/market_status.json
├── simulation/, */history/ (30일)
```

---

## Chunk 1: 공통 인프라

### Task 1: 프로젝트 초기화

**Files:** `requirements.txt`, `.env.example`, `config/settings.py`

- [ ] git init + requirements.txt (python-dotenv, requests, supabase, pykrx, yfinance, python-telegram-bot, google-genai, numpy, scipy, pytz)
- [ ] .env.example (KIS, Gemini×5, Telegram, Naver, Supabase, 외부 프로젝트 경로)
- [ ] config/settings.py (환경변수 로드, 경로 설정, Gemini 키 리스트)
- [ ] 커밋: `chore: 프로젝트 초기화`

### Task 2: 데이터 로더

**Files:** `core/data_loader.py`, `tests/test_data_loader.py`

- [ ] 테스트 작성: get_themes, get_vision_signals, get_combined_signals, get_macro, get_stock(code) 통합조회
- [ ] DataLoader 클래스 구현: JSON 캐싱, theme/signal 양쪽 데이터 통합 접근
- [ ] 테스트 PASS 확인
- [ ] 커밋: `feat: 데이터 로더`

### Task 3: 텔레그램 봇 + 포매터

**Files:** `core/telegram_bot.py`, `bot/formatters.py`

- [ ] send_message(text, chat_id, parse_mode) 구현
- [ ] format_stock_card, format_section 포매터
- [ ] 커밋: `feat: 텔레그램 봇`

### Task 4: Gemini 클라이언트

**Files:** `core/gemini_client.py`

- [ ] GeminiClient: 키 로테이션, generate(), generate_json() (마크다운 제거 포함)
- [ ] 커밋: `feat: Gemini 클라이언트`

---

## Chunk 2: Phase 1 (#11, #1, #10, #2)

### Task 5: #11 시스템 성과 대시보드

**Files:** `modules/system_performance.py`, `tests/test_system_performance.py`

- [ ] 테스트: calculate_hit_rate, calculate_avg_return, classify_market_regime, analyze_performance_by_source
- [ ] 구현: 적중률/수익률/샤프비율 계산, 시장국면 분류(상승/하락/횡보), 소스별 성과 비교
- [ ] 테스트 PASS
- [ ] 커밋: `feat: #11 시스템 성과`

### Task 6: #1 크로스 시그널 알림

**Files:** `modules/cross_signal.py`, `tests/test_cross_signal.py`

- [ ] 테스트: find_cross_signals(themes, signals), 매칭/비매칭 케이스
- [ ] 구현: 테마 대장주 × 매수신호 교차, 점수순 정렬, 텔레그램 포매팅
- [ ] 테스트 PASS
- [ ] 커밋: `feat: #1 크로스 시그널`

### Task 7: #10 커스텀 종목 스캐너

**Files:** `modules/stock_scanner.py`, `tests/test_stock_scanner.py`

- [ ] 테스트: parse_condition, scan_stocks (단일/복합/임계값/불리언 조건)
- [ ] 구현: 조건 파서(field op value), AND 조합 평가, 결과 포매팅
- [ ] 테스트 PASS
- [ ] 커밋: `feat: #10 종목 스캐너`

### Task 8: #2 모닝 브리프 & 이브닝 리뷰

**Files:** `modules/daily_briefing.py`, `tests/test_daily_briefing.py`

- [ ] 테스트: build_morning_context, build_evening_context
- [ ] 구현: 컨텍스트 빌더 + Gemini 프롬프트 (모닝: 글로벌+테마+종목+전략, 이브닝: 시장+성과+변동+관전포인트)
- [ ] 테스트 PASS
- [ ] 커밋: `feat: #2 모닝/이브닝 브리핑`

### Task 9: Phase 1 실행 스크립트 + GitHub Actions

**Files:** `scripts/run_phase1.py`, `.github/workflows/phase1-alerts.yml`

- [ ] run_phase1.py: --mode morning|evening|cross|performance|all
- [ ] GitHub Actions: workflow_dispatch + 환경변수 주입
- [ ] 커밋: `feat: Phase 1 실행 스크립트`

---

## Chunk 3: Phase 2 (#14, #7, #12)

### Task 10: #14 이상 거래 탐지

**Files:** `modules/anomaly_detector.py`, `tests/test_anomaly_detector.py`

- [ ] 테스트: detect_volume_spike, detect_simultaneous_surge, detect_gap
- [ ] 구현: 거래량 폭발(20일평균 대비), 동시급등(테마 3종목+), 갭(시가vs전일종가), 가격급변(5분 ±3%)
- [ ] 테스트 PASS
- [ ] 커밋: `feat: #14 이상 거래 탐지`

### Task 11: #7 스마트 머니 수급 레이더

**Files:** `modules/smart_money.py`, `tests/test_smart_money.py`

- [ ] 테스트: calculate_smart_money_score, detect_accumulation_pattern, classify_flow_pattern
- [ ] 구현: 스코어링(외국인25%+기관20%+순매수비율20%+매집패턴20%+프로그램역가중15%), 패턴분류(조용한매집/급속유입/쌍방이탈/교차수급)
- [ ] 테스트 PASS
- [ ] 커밋: `feat: #7 스마트 머니`

### Task 12: #12 섹터 자금 흐름 맵

**Files:** `modules/sector_flow.py`, `tests/test_sector_flow.py`

- [ ] 테스트: aggregate_by_sector, detect_rotation
- [ ] 구현: 테마 기반 섹터 집계, 유입/유출 전환 감지, 포매팅
- [ ] 테스트 PASS
- [ ] 커밋: `feat: #12 섹터 자금 흐름`

### Task 13: Phase 2 실행 스크립트

**Files:** `scripts/run_phase2.py`

- [ ] --mode anomaly|smart_money|sector|all
- [ ] results/ 디렉토리에 JSON 저장
- [ ] 커밋: `feat: Phase 2 실행 스크립트`

---

## Chunk 4: Phase 3 (#9, #15)

### Task 14: #9 뉴스 임팩트 분석기

**Files:** `modules/news_impact.py`, `tests/test_news_impact.py`

- [ ] 테스트: classify_news_type(정규식 기반), calculate_impact_stats
- [ ] 구현: 뉴스유형 분류(FDA승인/실적/수주/공매도/증자/정책 등), 임팩트 통계(D+1,3,5 평균/상승확률), 히스토리 DB 구축
- [ ] 테스트 PASS
- [ ] 커밋: `feat: #9 뉴스 임팩트`

### Task 15: #15 투자 시나리오 시뮬레이터

**Files:** `modules/scenario_simulator.py`, `tests/test_scenario_simulator.py`

- [ ] 테스트: parse_strategy, simulate_strategy, compare_strategies
- [ ] 구현: 전략 파서(signal=X hold=N stop=-N), 백테스트 엔진(stock_scanner 재활용), 손절 적용, 전략 비교
- [ ] 테스트 PASS
- [ ] 커밋: `feat: #15 시나리오 시뮬레이터`

### Task 16: Phase 3 실행 스크립트

**Files:** `scripts/run_phase3.py`

- [ ] --mode news|simulate|all
- [ ] 커밋: `feat: Phase 3 실행 스크립트`

---

## Chunk 5: Phase 4 (#3, #4, #8, #13, #5)

### Task 17: #3 테마 라이프사이클 트래커

**Files:** `modules/theme_lifecycle.py`, `tests/test_theme_lifecycle.py`

- [ ] 테스트: classify_lifecycle_stage(탄생/성장/과열/쇠퇴), track_theme_lifecycle
- [ ] 구현: 출현일수/순위트렌드/거래량트렌드/확산도 기반 단계 판정, 단계별 전략 제안
- [ ] 테스트 PASS
- [ ] 커밋: `feat: #3 테마 라이프사이클`

### Task 18: #4 보유종목 리스크 모니터

**Files:** `modules/risk_monitor.py`, `tests/test_risk_monitor.py`

- [ ] 테스트: evaluate_risk(신호악화/외국인매도/MA이탈/공매도/투매), detect_concentration(섹터편중)
- [ ] 구현: 위험도 3단계(높음/주의/낮음), 포트폴리오 집중도 분석
- [ ] 테스트 PASS
- [ ] 커밋: `feat: #4 리스크 모니터`

### Task 19: #8 매매 일지 & AI 회고

**Files:** `modules/trading_journal.py`, `tests/test_trading_journal.py`

- [ ] 테스트: match_trade_context, detect_trading_bias(추격매수/섹터편중), calculate_trade_stats
- [ ] 구현: 매매-시장맥락 매칭, 편향 탐지, Gemini 기반 일지 생성 프롬프트
- [ ] 테스트 PASS
- [ ] 커밋: `feat: #8 매매 일지`

### Task 20: #13 종목 유사 패턴 매칭

**Files:** `modules/pattern_matcher.py`, `tests/test_pattern_matcher.py`

- [ ] 테스트: normalize_pattern, calculate_similarity(코사인), find_similar_patterns
- [ ] 구현: 가격 정규화(상대 변화율), numpy 코사인 유사도, top-K 매칭 + 미래 수익률 통계
- [ ] 테스트 PASS
- [ ] 커밋: `feat: #13 패턴 매칭`

### Task 21: #5 통합 프론트엔드

**Files:** `frontend/` (React + Vite + TailwindCSS)

- [ ] 프로젝트 초기화: `npm create vite@latest . -- --template react-ts`
- [ ] dataService.ts: results/*.json 로드 서비스
- [ ] Dashboard.tsx: 시장현황 + 시스템성과 + 섹터흐름 + 크로스시그널
- [ ] 추가 페이지: 테마라이프사이클, 스마트머니, 이상거래, 패턴매칭, 시뮬레이션
- [ ] 커밋: `feat: #5 통합 프론트엔드`

### Task 22: 전체 통합

**Files:** `scripts/run_all.py`, `.github/workflows/`, `bot/handlers.py`

- [ ] run_all.py: Phase 1~4 순차 실행 + results/ JSON 저장 + frontend/public/data/ 복사
- [ ] bot/handlers.py: 텔레그램 봇 명령어 (/scan, /stock, /theme, /market, /top, /risk)
- [ ] GitHub Actions 워크플로우 4개 (phase1~4 + deploy-pages)
- [ ] 커밋: `feat: 전체 통합 — 실행 스크립트 + 봇 핸들러 + CI/CD`

---

## 실행 순서 요약

```
Chunk 1 (Task 1~4)  → 공통 인프라 (설정, 데이터로더, 텔레그램, Gemini)
Chunk 2 (Task 5~9)  → Phase 1: 성과 대시보드, 크로스 시그널, 스캐너, 브리핑
Chunk 3 (Task 10~13) → Phase 2: 이상 탐지, 스마트 머니, 섹터 흐름
Chunk 4 (Task 14~16) → Phase 3: 뉴스 임팩트, 시나리오 시뮬레이터
Chunk 5 (Task 17~22) → Phase 4: 라이프사이클, 리스크, 일지, 패턴매칭, 프론트엔드, 통합
```

각 Task는 TDD 방식: 테스트 작성 → FAIL 확인 → 구현 → PASS 확인 → 커밋
