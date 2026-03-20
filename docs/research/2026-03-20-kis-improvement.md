# KIS API 활용 개선/강화 포인트 연구

**작성일:** 2026-03-20
**목적:** 현재 프로젝트의 KIS API 활용 현황 대비, KIS 공식 GitHub(open-trading-api) 및 MCP 서비스를 기반으로 개선/강화 포인트 도출

---

## 1. 현재 프로젝트 KIS API 활용 현황

| 항목 | 현재 상태 |
|------|----------|
| **사용 API** | 현재가 시세 조회 1개 (`FHKST01010100`) |
| **사용 방식** | REST API 직접 호출 (`requests`) |
| **구현 파일** | `core/kis_client.py` (186줄) |
| **토큰 관리** | Supabase 중앙 저장 + KIS 신규 발급 폴백 |
| **Rate Limiting** | `time.sleep(0.05)` (50ms, 초당 20건) |
| **에러 처리** | 토큰 만료 시 1회 재발급, 그 외 None 반환 |
| **WebSocket** | 미구현 |
| **MCP** | 미사용 |

**핵심 문제:** 334개 KIS API 중 **1개만 사용** — 프로젝트가 이미 수집하는 데이터 대비 KIS API 활용이 극히 제한적.

---

## 2. KIS 공식 GitHub (open-trading-api) 분석

### 2.1 저장소 구조

```
open-trading-api/
├── examples_llm/          # LLM용 기능별 샘플 (한줄 호출)
├── examples_user/         # 사용자용 통합 예제 (REST + WebSocket)
├── strategy_builder/      # 전략 설계 + 시그널 생성 (80개 기술지표)
├── backtester/            # 백테스팅 엔진 (Docker/QuantConnect Lean)
├── MCP/                   # MCP 서버 2종
│   ├── KIS Code Assistant MCP/   # API 검색 + 코드 생성
│   └── Kis Trading MCP/          # 실시간 거래 (166개 API)
├── stocks_info/           # 종목정보 참고 데이터
└── kis_devlp.yaml         # API 설정 파일
```

### 2.2 제공되는 국내주식 API (156개) — 주요 카테고리

| 카테고리 | 주요 API | 현재 프로젝트 활용 |
|---------|---------|------------------|
| **주가 시세** | inquire_price, inquire_price_2, inquire_daily_price | ✅ inquire_price만 사용 |
| **차트 데이터** | daily_itemchartprice, time_itemchartprice, time_indexchartprice | ❌ 미사용 |
| **호가** | inquire_asking_price_exp_ccn | ❌ 미사용 (mock 데이터 사용 중) |
| **투자자 동향** | inquire_investor, investor_daily_by_market, foreign_institution_total | ❌ 미사용 |
| **프로그램 매매** | program_trade_krx | ❌ 미사용 |
| **공매도** | daily_short_sale | ❌ 미사용 |
| **거래량 순위** | volume_rank | ❌ 미사용 |
| **배당** | ksdinfo_dividend | ❌ 미사용 |
| **계좌/잔고** | inquire_balance, inquire_account_balance | ❌ 미사용 |
| **주문** | order_cash, order_credit, order_rvsecncl | ❌ 미사용 |

### 2.3 MCP 서비스 2종

#### (A) KIS Code Assistant MCP — 개발 보조용

- **역할:** 자연어로 334개 API 검색 + 샘플코드 자동 생성
- **도구:** `kis_detailed_code`, `kis_easy_code`
- **연동:** Claude Desktop / Cursor / HTTP (8081포트)
- **실행:** `uv run server.py --stdio` 또는 Docker
- **이 프로젝트와의 관계:** 개발 시 참고용 (런타임 통합 불필요)

#### (B) Kis Trading MCP — 실거래용

- **역할:** AI에서 직접 166개 API 호출 (시세 조회 + 주문 + 잔고 관리)
- **카테고리:** 국내주식(74), 해외주식(34), 선물옵션(39), 채권(14), ETF(2), ELW(1)
- **연동:** Docker 컨테이너 → `npx -y mcp-remote http://localhost:3000/sse`
- **인증:** 환경변수 (`KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_HTS_ID` 등)
- **특징:** GitHub에서 실시간 API 코드 다운로드 후 동적 실행

---

## 3. 개선/강화 포인트 분석

### 3.1 방향 A: 기존 REST API 확장 (점진적 개선)

현재 `kis_client.py`에 API를 추가하는 방식.

| 우선순위 | 추가 API | 효과 | 난이도 |
|---------|---------|------|--------|
| **P0** | `inquire_asking_price_exp_ccn` (호가) | 현재 mock → 실데이터 전환 | 낮음 |
| **P0** | `inquire_investor` (투자자별 매매동향) | 기관/외국인 수급 실데이터 | 낮음 |
| **P1** | `inquire_daily_itemchartprice` (일봉 차트) | 기술분석 강화 | 낮음 |
| **P1** | `volume_rank` (거래량 순위) | 시장 관심 종목 탐지 | 낮음 |
| **P1** | `program_trade_krx` (프로그램 매매) | 기관 프로그램 수급 | 낮음 |
| **P2** | `daily_short_sale` (공매도) | 공매도 추세 분석 | 낮음 |
| **P2** | `foreign_institution_total` (외인/기관 종합) | 수급 종합 분석 | 낮음 |
| **P2** | `ksdinfo_dividend` (배당) | 배당 전략 데이터 | 낮음 |

**장점:** 기존 아키텍처 변경 없음, 점진적 도입 가능
**단점:** API마다 일일이 구현 필요, MCP 대비 확장성 낮음

### 3.2 방향 B: KIS Trading MCP 도입 (전면 전환)

Trading MCP를 Docker로 띄우고, 프로젝트에서 MCP 프로토콜로 호출하는 방식.

**아키텍처 변경:**
```
현재: run_all.py → kis_client.py → KIS REST API (1개)
변경: run_all.py → MCP Client → Trading MCP Server (Docker) → KIS REST API (166개)
```

**장점:**
- 166개 API 즉시 사용 가능 (개별 구현 불필요)
- KIS가 공식 유지보수 (API 변경 시 자동 반영)
- GitHub에서 실시간 코드 다운로드 → 항상 최신
- Claude Code에서 직접 거래 가능 (인터랙티브 분석)

**단점:**
- Docker 의존성 추가
- MCP 프로토콜 학습 곡선
- 현재 GitHub Actions 파이프라인과의 통합 복잡도 증가
- 네트워크 레이어 추가 (로컬 Docker ↔ KIS API)
- 실거래 기능 포함 → 보안 리스크 증가

### 3.3 방향 C: 하이브리드 (권장)

**기존 REST + 선별적 MCP 활용**

1. **Phase 1 (즉시):** `kis_client.py`에 P0 API 2~3개 추가 (호가, 투자자동향)
2. **Phase 2 (단기):** KIS Code Assistant MCP를 Claude Code에 연결 → 개발 시 API 탐색 도구로 활용
3. **Phase 3 (중기):** Trading MCP를 로컬 개발 환경에 Docker로 설치 → 인터랙티브 분석/탐색용
4. **Phase 4 (장기):** 자동매매 기능 도입 시 Trading MCP 본격 통합

---

## 4. 즉시 활용 가능한 구체적 개선안

### 4.1 호가 데이터 실데이터 전환 (P0)

현재 `generate_missing_data.py`에서 mock 호가 데이터 생성 중. KIS API로 대체 가능.

```
Endpoint: /uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn
TR_ID: FHKST01010200
```

### 4.2 투자자별 매매동향 (P0)

현재 투자자 수급 데이터가 외부 소스에 의존. KIS 직접 조회로 보강 가능.

```
Endpoint: /uapi/domestic-stock/v1/quotations/inquire-investor
TR_ID: FHKST01010900
```

### 4.3 일봉 차트 데이터 (P1)

기술분석에 필요한 OHLCV 히스토리. 현재 단일 시점 현재가만 조회 중.

```
Endpoint: /uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice
TR_ID: FHKST03010100
```

### 4.4 Rate Limiting 고도화

현재 단순 50ms sleep → exponential backoff + 429 상태코드 처리 추가 권장.

### 4.5 KIS Code Assistant MCP 연결 (개발 도구)

Claude Code의 MCP 설정에 추가하면 개발 중 자연어로 API 탐색 가능:

```json
// ~/.claude/settings.json 또는 claude_desktop_config.json
{
  "mcpServers": {
    "kis-code-assistant-mcp": {
      "command": "uv",
      "args": ["--directory", "/path/to/open-trading-api/MCP/KIS Code Assistant MCP", "run", "server.py", "--stdio"]
    }
  }
}
```

---

## 5. 결론 및 권장 사항

| 항목 | 권장 |
|------|------|
| **API 호출 방식** | 당분간 REST 유지 (MCP 전면 전환은 시기상조) |
| **즉시 추가할 API** | 호가(`FHKST01010200`), 투자자동향(`FHKST01010900`) |
| **MCP 활용** | Code Assistant MCP를 개발 도구로 연결 |
| **Trading MCP** | 자동매매 도입 시점에 검토 |
| **WebSocket** | 실시간 대시보드 구현 시 별도 검토 |
| **strategy_builder/backtester** | 80개 기술지표 + 백테스팅 엔진은 참고 가치 높음, 별도 검토 |

**핵심:** 현재 프로젝트는 REST API 1개만 사용 중이므로, MCP 전환보다 **활용 API 확대가 우선**. 호가·투자자동향·일봉 차트 3개만 추가해도 데이터 품질이 크게 향상됨.
