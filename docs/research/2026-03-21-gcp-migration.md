# GCP 이전 연구 — 비용 분석 + 기존 프로젝트 제약사항 진단

> 작성일: 2026-03-21

## 1. 하이브리드 A 구성 비용 분석

### 구성 요약

| 컴포넌트 | GCP 서비스 | 역할 |
|---------|-----------|------|
| WebSocket 수신기 | Compute Engine e2-micro | KIS 실시간 체결/호가 수신 (24/7) |
| 분석 모듈 | Cloud Functions | 이벤트 트리거 분석 실행 |
| 스케줄링 | Cloud Scheduler | 장 전/중/후 cron |
| 실시간 데이터 저장 | Firestore | 변경 감지 + 프론트엔드 전달 |
| 프론트엔드 | GitHub Pages (유지) | 대시보드 |

### 서비스별 무료 한도 vs 실사용 예상치

#### (1) Compute Engine e2-micro — ⚠️ 조건부 무료

| 항목 | 무료 한도 | 예상 사용 | 판정 |
|------|----------|----------|------|
| 인스턴스 | 1개 e2-micro (0.25 vCPU, 1GB RAM) | 1개 | ✅ 무료 |
| 리전 | **us-west1, us-central1, us-east1만** 무료 (asia-east1 대만은 과금됨) | US 리전 사용 (KIS 서버 대비 ~150ms 레이턴시) | ✅ 무료 (US만) |
| 디스크 | 30GB standard PD | 10GB이면 충분 | ✅ 무료 |
| **네트워크 이그레스** | **1GB/월** (북미→외부) | 웹소켓 수신은 인그레스(무료), Firestore 쓰기는 Google 내부 네트워크 | ⚠️ 주의 |
| 외부 IP | 에페메럴 IP 무료, 고정 IP는 $3.65/월 | 에페메럴 사용 | ✅ 무료 |
| OS | Debian/Ubuntu 무료 | Debian | ✅ 무료 |

**비용 위험:**
- 네트워크 이그레스 1GB/월 한도 — Firestore 쓰기가 Google 내부 트래픽이면 이그레스 미소비. 단, 외부 API 호출(KIS REST, Telegram 등)의 응답 수신은 인그레스(무료)이므로 문제없음
- **asia-east1(대만)** 리전 사용 가능 확인됨 — KIS 서버(한국)와의 레이턴시 최소화
- e2-micro의 CPU 버스트: 기본 0.25 vCPU, 버스트 가능하나 지속 사용 시 제한됨

#### (2) Firestore — ❌ 무료 한도 초과 거의 확실

| 항목 | 무료 한도 | 예상 사용 | 판정 |
|------|----------|----------|------|
| 저장소 | 1GB/월 | 최신 데이터만 유지 시 충분 | ✅ |
| **쓰기** | **20,000건/일** (Spark) 또는 **20,000건/월** (Blaze) | 40종목 × 평균 3,000건/일 체결 = **~120,000건/일** | ❌ **대폭 초과** |
| **읽기** | **50,000건/일** (Spark) 또는 **50,000건/월** (Blaze) | 프론트엔드 리스너 + 분석 트리거 | ⚠️ 초과 가능 |
| 삭제 | 20,000건/일 | 오래된 데이터 정리 | ✅ |

**핵심 문제: Firestore 쓰기 비용**
- 인기 종목 40개의 실시간 체결가를 건건이 Firestore에 쓰면 **하루 10만건 이상**
- Spark Plan(무료): 일 20,000건 쓰기 → **5배 이상 초과**
- Blaze Plan(종량제): 무료 20,000건/월 이후 $0.18/100K건
  - 월 예상: 120,000건/일 × 22일 = 2,640,000건 → 초과분 2,620,000건 × $0.18/100K = **~$4.72/월**
- **onSnapshot 리스너**: 클라이언트가 리스닝 중일 때, 문서 변경마다 읽기 1건으로 카운트

**대안: 배치 쓰기로 비용 절감**
- 체결가를 건건이 쓰지 않고, 5~10초 단위로 배치 집계 → 종목당 하루 ~2,160건 (6시간/10초)
- 40종목 × 2,160 = 86,400건/일 — 여전히 초과하지만 금액은 더 낮아짐
- 30초 단위 배치: 40 × 720 = 28,800건/일 → Spark Plan 초과, Blaze Plan에서 월 ~$0.90

#### (3) Cloud Functions — ⚠️ 트리거 방식에 따라 초과 가능

| 항목 | 무료 한도 | 예상 사용 | 판정 |
|------|----------|----------|------|
| 호출 | 2M건/월 | Firestore 트리거 건건이면 수백만건 가능 | ⚠️ |
| 컴퓨팅 | 400K GB-sec/월 | 분석 모듈 실행 시간에 따라 | ⚠️ |
| 이그레스 | 5GB/월 | Telegram/API 응답 정도 | ✅ |

**비용 위험:**
- Firestore 문서 변경마다 Function이 트리거되면, 체결가 건건이 = 월 수백만 호출 → 2M 초과
- **대안:** Firestore 트리거 대신 **Pub/Sub 배치** 또는 **Cloud Scheduler 주기 실행**(1~5분 간격)으로 분석 모듈 호출 → 호출 수 대폭 감소
- Cloud Scheduler 1분 간격 × 6시간 × 22일 = 7,920건/월 → 무료 범위 충분

#### (4) Cloud Scheduler — ✅ 무료

| 항목 | 무료 한도 | 예상 사용 | 판정 |
|------|----------|----------|------|
| 잡 개수 | 3개/빌링 계정 | 장 전/중/후 3개 | ✅ 딱 맞음 |

**비용 위험:** 추가 잡이 필요하면 개당 $0.10/월

#### (5) 기타 숨은 비용

| 항목 | 비용 | 대응 |
|------|------|------|
| Cloud Logging | 50GB/월 무료, 초과 시 $0.50/GB | 로그 레벨 조절로 충분 |
| Secret Manager | 6개 시크릿 무료, 10K 액세스/월 무료 | 14개 시크릿 → 초과분 $0.06/시크릿/월 = ~$0.48/월 |
| Artifact Registry | 0.5GB 무료 | Docker 이미지 1개면 충분 |
| Cloud Build | 120분/일 무료 | CI/CD에 충분 |
| Cloud NAT | 사용하면 $0.045/시간 ≈ $32/월 | **사용하지 않도록 설계** |

### 비용 시나리오 요약

| 시나리오 | 예상 월 비용 |
|---------|------------|
| **A. 이상적 (30초 배치 + Scheduler 트리거)** | **$0 ~ $2/월** |
| **B. 현실적 (10초 배치 + Firestore 트리거)** | **$3 ~ $8/월** |
| **C. 건건이 실시간 (배치 없음)** | **$10 ~ $20/월** |

**결론:** 완전 무료는 어렵지만, 배치 쓰기 + Scheduler 트리거 설계로 **월 $1~2 수준**으로 최소화 가능. Firestore 대신 **e2-micro 메모리 내 캐시 + SSE/WebSocket 직접 전달** 방식을 쓰면 Firestore 비용 자체를 제거할 수 있음.

---

## 2. 기존 프로젝트 제약사항 진단

### 위험도 매트릭스

| # | 항목 | 위험도 | 핵심 이슈 |
|---|------|--------|-----------|
| 1 | 데이터 의존성 | **높음** | DataLoader가 로컬 파일시스템 전제, 외부 레포 2개 접근 재설계 필요 |
| 2 | 메모리 | **높음** | run_all.py 2,031줄 모놀리식, 50개 JSON 생성, e2-micro OOM 가능 |
| 3 | Cloud Functions 호환성 | **높음** | 파일시스템 쓰기 50건, Phase간 데이터 커플링 |
| 4 | 프론트엔드 데이터 소스 | **높음** | dataService.ts 45개 메서드가 정적 JSON fetch |
| 5 | 시크릿 관리 | **중간** | 14개 시크릿 이전 + DART_KEY 평문 하드코딩 |
| 6 | CI/CD 파이프라인 | **중간** | 빌드+데이터+배포 통합 워크플로우 해체 필요 |
| 7 | 외부 API 호환성 | **낮음** | 모두 HTTP 기반, 환경변수만 이전하면 동작 |
| 8 | 테스트 환경 | **낮음** | 변경 불필요 |

### 상세 진단

#### (1) 데이터 의존성 — 위험도: 높음

**현상:** `DataLoader`는 `Path` 기반 로컬 파일시스템에서 JSON을 읽음

- `config/settings.py`: `THEME_DATA_PATH = "../theme_analysis/frontend/public/data"`, `SIGNAL_DATA_PATH = "../signal_analysis/results"` — 상대 경로로 외부 레포 참조
- `core/data_loader.py`: 20개+ JSON 파일을 `Path` 객체로 직접 읽음, `history_dir.glob("*.json")` 패턴도 사용
- GitHub Actions에서는 `actions/checkout`으로 워크스페이스에 배치

**GCP에서의 영향:**
- Compute Engine: git clone 또는 GCS 동기화 전처리 필요
- Cloud Functions: 콜드 스타트마다 데이터 확보 방법 필요
- theme-analyzer/signal-pulse의 실행 파이프라인도 함께 고려해야 함

**대응:** GCS 버킷을 중앙 데이터 스토어로 사용. 외부 레포가 결과를 GCS에 업로드 → stock_toolkit이 GCS에서 다운로드.

#### (2) 메모리 — 위험도: 높음

**현상:** `run_all.py` 2,031줄, Phase 1~7 단일 프로세스 순차 실행

- import 모듈 20개+, numpy/supabase/google-genai 등 무거운 라이브러리
- DataLoader._cache에 JSON 파일 전부 메모리 적재 (100~500MB)
- Python 런타임 + 라이브러리: ~250MB
- **e2-micro(1GB RAM)에서 전체 실행 시 OOM 가능성 높음**

**대응:**
- 분석 모듈(run_all.py) 실행은 Cloud Functions로 분리 (개별 Phase만 담당)
- e2-micro는 WebSocket 수신 전담 (경량)
- 또는 swap 메모리 설정 (성능 저하 감수)

#### (3) Cloud Functions 호환성 — 위험도: 높음

- **파일시스템 쓰기:** results/ 디렉토리에 50개 JSON 파일 기록 → Cloud Functions는 /tmp만 쓰기 가능, 종료 시 삭제
- **Phase간 데이터 커플링:** Phase 2는 Phase 1의 `cross_matches` 사용, Phase 3~7은 Phase 2의 결과 사용
- **하드코딩 경로:** `generate_missing_data.py`에 절대 경로 3건
- **⚠️ 보안 문제:** `generate_missing_data.py` 16행에 **DART API 키 평문 하드코딩** — GCP 이전과 무관하게 즉시 수정 필요

**대응:** 결과 저장을 GCS/Firestore로 변경. Phase간 데이터는 GCS에 중간 결과 저장 후 다음 Function에서 읽기.

#### (4) 프론트엔드 데이터 소스 변경 — 위험도: 높음

- `frontend/src/services/dataService.ts`: 45개 fetch 메서드, 모두 `BASE_URL + "xxx.json"` 정적 JSON
- Firestore 전환 시: 45개 메서드 전부 교체 + Firebase SDK 추가 + 구독 lifecycle 관리

**대응 (비용+복잡도 최소화):**
- **GCS에 JSON 업로드 + 정적 URL 유지** → `dataService.ts`에서 BASE_URL만 변경하면 됨
- 실시간성이 필요한 데이터만 선별적으로 Firestore/SSE 도입
- 프론트엔드 전면 개편 없이 점진적 전환 가능

#### (5) 시크릿 관리 — 위험도: 중간

- GitHub Secrets에 14개 키 저장 중
- GCP Secret Manager 이전 필요 (6개 무료, 초과분 미미한 비용)
- **즉시 수정:** `generate_missing_data.py`의 DART_KEY 평문 하드코딩 제거

#### (6) CI/CD 파이프라인 — 위험도: 중간

- `deploy-pages.yml`: 외부 레포 checkout + Python 실행 + Node 빌드 + 검증 + 배포 + Telegram 알림 — 하나의 통합 파이프라인
- GCP에서는 해체 후 재구성 필요:
  - 데이터 생성: Cloud Scheduler → Compute Engine/Cloud Functions
  - 프론트엔드: Cloud Build → GCS/Firebase Hosting
  - 알림: Pub/Sub → Cloud Functions

#### (7) 외부 API — 위험도: 낮음

KIS REST, Telegram, Gemini, DART, Naver — 모두 HTTP 기반. 환경변수만 이전하면 동작.

#### (8) 테스트 — 위험도: 낮음

55개 유닛 테스트, 외부 API 미호출 구조. Cloud Build에 테스트 스텝 추가하면 됨.

---

## 3. 수정된 아키텍처 제안 (비용 최적화)

기존 하이브리드 A에서 Firestore 비용 문제를 해결한 **개선안:**

```
┌─────────────────────────────────────────────────────┐
│ Compute Engine e2-micro (US 리전) — 무료         │
│                                                      │
│  [KIS WebSocket 수신기]                              │
│    ↓ 체결/호가 데이터                                │
│  [인메모리 캐시 (최신 N건)]                           │
│    ↓                                                 │
│  [경량 HTTP/SSE 서버]  ←── 프론트엔드 직접 연결      │
│    ↓ 조건 충족 시                                    │
│  [Telegram 알림 전송]                                │
│                                                      │
│  [Cloud Scheduler cron] → run_all.py 실행            │
│    → 결과 JSON을 GCS에 업로드                        │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ GCS 버킷 — 무료 범위 내 (5GB, Standard)             │
│  - 분석 결과 JSON 50개 (정적 데이터)                 │
│  - theme-analyzer/signal-pulse 데이터                │
│  - 프론트엔드에서 직접 fetch (CORS 설정)             │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ GitHub Pages (유지) — 무료                           │
│  - React SPA 호스팅                                  │
│  - 정적 데이터 → GCS에서 fetch                       │
│  - 실시간 데이터 → e2-micro SSE 연결                 │
└─────────────────────────────────────────────────────┘
```

**핵심 변경:**
- Firestore 제거 → e2-micro 인메모리 캐시 + SSE로 실시간 전달 (비용 $0)
- Cloud Functions 제거 → e2-micro에서 Cloud Scheduler 트리거로 분석 실행
- GCS를 정적 데이터 중간 저장소로 활용

**예상 비용: $0/월** (무료 티어 범위 내)

단, e2-micro 1GB RAM으로 WebSocket + 분석 모듈 동시 실행은 OOM 위험 → 분석 모듈은 경량화 또는 swap 활용 필요.

---

## 4. Side-Effect 분석 — 기존 프로그램 부작용 진단

### 전제: 권장 방식은 "병행 운영" (GitHub Actions 유지 + GCP e2-micro 추가)

완전 이관이 아닌 병행 방식이면 기존 코드를 일체 변경하지 않으므로 side-effect가 없음.

### 완전 이관 시 Side-Effect 목록

| # | 영역 | Side-Effect | 심각도 |
|---|------|------------|--------|
| 1 | DataLoader | Path 기반 로컬 파일 읽기 → GCP에서 외부 레포 데이터 접근 불가 | **높음** |
| 2 | results/ 파일 쓰기 | run_all.py가 50개 JSON 기록 → Cloud Functions /tmp만 쓰기 가능 | **높음** |
| 3 | 프론트엔드 데이터 소스 | dataService.ts BASE_URL 변경 (1줄) | **낮음** |
| 4 | RefreshButtons | cron-job.org → GitHub Actions 트리거 대상 변경 필요 | **중간** |
| 5 | Supabase 연동 | 변경 불필요 (외부 서비스, 실행 환경 무관) | **없음** |
| 6 | Telegram/Gemini/KIS REST | 변경 불필요 (HTTP 기반, 환경변수만 이전) | **없음** |
| 7 | generate_missing_data.py | 절대 경로 3건 하드코딩 + DART_KEY 평문 → 경로 불일치로 실패 | **높음** |
| 8 | 테스트 55건 | 변경 불필요 (유닛 테스트, 외부 API 미호출) | **없음** |

**핵심:** 비즈니스 로직(30+ 분석 모듈) 자체는 변경 불필요. Side-effect는 모두 인프라 접점(파일 I/O, 경로, 트리거 방식)에서 발생.

**즉시 수정 필요 (GCP 이전과 무관):** `generate_missing_data.py` 16행에 DART API 키 평문 하드코딩

---

## 5. 실제 이득 분석 — GCP 이관으로 얻는 것 vs 잃는 것

### 현재 시스템 실제 동작 (소스코드 확인 기준)

| 항목 | 현재 상태 (소스코드 확인) |
|------|--------------------------|
| 실행 방식 | GitHub Actions workflow_dispatch (수동) + cron-job.org 간접 트리거 |
| 스케줄링 | cron 없음. RefreshButtons에서 cron-job.org로 수동 트리거 |
| 데이터 갱신 주기 | 사용자가 버튼 → ~2.5분 후 반영 |
| 실시간 시세 | Supabase Edge Function kis-proxy 경유 REST 스냅샷 |
| 알림 | run_all.py 실행 시에만 Telegram 전송 (cross_signal, 연속시그널) |
| 급등 감지 | run_all.py 실행 시점의 스냅샷에서 change_rate≥15% + volume_rate≥200% 필터 |

### 확실한 이득

| 이득 | 현재 → GCP 후 | 구체적 시나리오 |
|------|---------------|----------------|
| **실시간 급등/급락 감지** | 수동 실행 시에만 → 발생 즉시 감지 | 장중 특정 종목 15%+ 급등 시 현재는 다음 수동 갱신까지 미감지. WebSocket이면 초 단위 감지 |
| **실시간 수급 반전 알림** | 배치 분석에서만 → 실시간 | 외국인/기관 대량 매수 전환을 체결 데이터로 실시간 추적 |
| **호가 변동 모니터링** | KIS REST 단건 조회 → 실시간 호가창 스트리밍 | 매수/매도 벽 형성·소멸을 실시간 관찰 |
| **자동 스케줄링** | cron-job.org 의존 + 수동 → Cloud Scheduler 직접 제어 | 장 전 08:30 자동 프리마켓, 장 중 매 시간 갱신, 장 후 자동 리뷰 |
| **포트폴리오 실시간 평가** | kis-proxy REST 스냅샷 → WebSocket 스트리밍 | 보유 종목 현재가가 초 단위로 자동 갱신 |

### 불확실한 이득 (비용 대비 의문)

| 항목 | 현실적 판단 |
|------|-------------|
| 대시보드 전체 실시간화 | 45개 데이터 중 실시간이 의미 있는 것은 5~6개뿐. 나머지(테마분석, 시나리오, 패턴 등)는 일 1회 배치로 충분 |
| 성능 향상 | e2-micro(0.25 vCPU, 1GB) < GitHub Actions runner(2 vCPU, 7GB). 분석 실행은 오히려 느려짐 |
| 비용 절감 | 둘 다 무료. GCP는 인프라 관리 오버헤드 추가 |

### 잃게 되는 것 (완전 이관 시)

| 손실 | 설명 |
|------|------|
| 운영 단순성 | GitHub Actions: push만으로 CI/CD. GCP: VM 모니터링, 보안 패치, 디스크 관리 |
| 외부 레포 연동 | actions/checkout → git clone/GCS 파이프라인 재구축 |
| 빌드 파워 | GitHub Actions 2vCPU 7GB → e2-micro 0.25vCPU 1GB |

### 최종 결론: 병행 운영 권장

| 역할 | 담당 | 이유 |
|------|------|------|
| 정기 분석 + 배포 | **GitHub Actions 유지** | 2vCPU/7GB, 외부 레포 checkout 용이, 기존 코드 변경 제로 |
| 실시간 WebSocket + 알림 + SSE | **GCP e2-micro 추가** | 장중 상시 가동, 경량 수신기 전담, 비용 $0 |

기존 시스템 side-effect 제로. 실시간 기능만 새 코드로 추가.

---

## 6. WebSocket + SSE가 주는 실제 이점 — 구체적 시나리오

### 현재 시스템의 한계 (소스코드 기반 사실)

**run_all.py의 급등 감지 로직 (351~369행):**
```python
surge_alerts = []
for s in rising_stocks:
    cr = s.get("change_rate", 0)
    vr = s.get("volume_rate", 0)
    if cr >= 15 and vr >= 200:
        surge_alerts.append({...})
```
→ 이 로직은 run_all.py가 **실행되는 시점**에만 동작. 장중 사용자가 수동 갱신하지 않으면 급등을 놓침.

**Telegram 알림 (1994~2002행):**
```python
if use_ai and and_results:
    lines = ["연속 매수+대장주 (AND 조건)"]
    send_message("\n".join(lines))
```
→ mode=full로 실행할 때만 알림. data-only 모드에서는 알림 없음.

### WebSocket 도입 시 달라지는 것

#### 시나리오 1: 장중 급등 실시간 감지

```
[현재] 09:30 급등 발생 → 사용자가 11:00에 갱신 버튼 → 11:02에 감지 (1.5시간 지연)
[GCP]  09:30 급등 발생 → WebSocket 체결가 수신 → 3초 내 Telegram 알림
```

- KIS WebSocket H0STCNT0 (실시간 체결가)로 40종목 등락률 실시간 계산
- 기존 surge_alerts 조건(등락률≥15%, 거래량≥200%) 동일 적용, 다만 **실시간으로**
- 감지 → 즉시 Telegram 알림 + SSE로 대시보드에 경보 표시

#### 시나리오 2: 호가 매수벽/매도벽 감지

```
[현재] get_asking_price() REST 호출 → 요청 시점 스냅샷 1회
[GCP]  H0STASP0 실시간 호가 → 매수벽 형성·소멸 연속 추적
```

- 대량 매수 호가 집중(매수벽) → 지지선 형성 신호
- 매수벽 소멸 → 지지 붕괴 경고
- 현재 orderbook_pressure 모듈이 이미 분석 로직 보유 → 입력만 실시간으로 변경

#### 시나리오 3: 수급 반전 즉시 알림

```
[현재] run_all.py 실행 시 investor_data 일괄 조회 → 일 1~2회 분석
[GCP]  실시간 체결 데이터 누적 → 외국인/기관 순매수 반전 시 즉시 감지
```

- 현재 smart_money 모듈의 수급 점수 로직을 실시간 체결 데이터에 적용
- "외국인 순매도 → 순매수 전환" 시 Telegram 알림

#### 시나리오 4: 대시보드 실시간 갱신 (SSE)

```
[현재] 정적 JSON → 수동 갱신 버튼 → 2.5분 대기 → 새로고침
[GCP]  e2-micro SSE 서버 → 프론트엔드 EventSource 연결 → 자동 갱신
```

- 대시보드에 실시간 위젯 추가 (현재가, 등락률, 체결량)
- 기존 45개 정적 데이터는 그대로 유지 (일 1~2회 배치)
- **실시간이 의미 있는 5~6개 데이터만** SSE로 전달:
  - 보유 종목 현재가
  - 급등 경보
  - 수급 반전 알림
  - 호가 압력
  - 체결 강도

#### 시나리오 5: 자동 스케줄링

```
[현재] 사용자가 RefreshButtons 수동 클릭 → cron-job.org → GitHub Actions
[GCP]  Cloud Scheduler 자동 실행:
       08:30 KST — 프리마켓 분석
       09:00 KST — WebSocket 연결 시작 (장 시작)
       15:30 KST — WebSocket 종료 + 장 마감 리뷰
       18:00 KST — 이브닝 브리핑
```

### 종목 수 제한(40개)에 대한 현실적 운용

KIS WebSocket은 동시 40구독으로 제한. 현실적 배분:

| 용도 | 구독 수 | 데이터 타입 |
|------|---------|------------|
| 보유 종목 실시간 시세 | ~10 | 체결가(H0STCNT0) |
| 매수 시그널 종목 감시 | ~15 | 체결가(H0STCNT0) |
| 핵심 종목 호가 | ~10 | 호가(H0STASP0) |
| 여유분 | ~5 | 동적 교체 |

→ 40개면 핵심 종목 감시에 충분. 전 종목 감시가 아닌 **시그널 기반 선별 감시**.

---

## 7. 보완 사항 (theme_analysis 연구 교차 검토)

> `theme_analysis/docs/research/2026-03-21-websocket-alert.md`와 교차 비교하여 발견된 보완점.

### 보완 1: e2-micro 무료 리전 — 오류 정정

**기존 기재 (오류):** asia-east1(대만) 사용 가능 → 레이턴시 최소화
**실제 확인:** e2-micro 무료 티어는 **US 리전만 해당** (us-west1, us-central1, us-east1)

- [GCP 공식 문서](https://cloud.google.com/free/docs/free-cloud-features) 확인: asia-east1은 무료 대상 아님
- **US 리전 사용 시 KIS 서버(한국)와 ~150ms 레이턴시 발생**
- 실시간 알림 용도(초 단위 감지)에는 150ms가 실질적 문제 없음
- 다만 REST API 200건 순차 호출 시 200 × 150ms = 30초 추가 지연 가능

### 보완 2: KIS 토큰 경합 — 누락된 side-effect

theme_analysis 문서에서 **심각도 중간**으로 지적한 문제.

**현재 구조:**
- `stock_toolkit/core/kis_client.py`: Supabase에서 토큰 조회 → 만료 시 신규 발급
- `theme_analysis`: 동일 Supabase에서 토큰 공유
- KIS API: **토큰 1일 1회 발급 제한**

**e2-micro 추가 시:**
- e2-micro WebSocket 데몬도 KIS approval key가 필요 (REST 토큰과 별도)
- 그러나 REST 토큰은 e2-micro/stock_toolkit GA/theme_analysis GA 3곳에서 공유
- 한쪽이 토큰 재발급하면 다른 쪽이 무효화될 수 있음

**대응:**
- WebSocket approval key는 REST access_token과 별도이므로 WebSocket 자체는 경합 없음
- REST 토큰 경합은 기존에도 stock_toolkit ↔ theme_analysis 간 존재하는 문제
- Supabase에서 토큰 조회 시 만료 여부를 먼저 확인하고, 유효하면 재발급하지 않는 현재 로직으로 충분
- 다만 동시 실행 시 race condition 가능 → **Supabase row-level lock 또는 발급 시각 비교 로직 강화** 권장

### 보완 3: 프로젝트별 별개 e2-micro 구성

theme_analysis와 stock_toolkit은 **각각 독립된 e2-micro 데몬**으로 구성.

**비용 영향:**
- GCP 무료 티어는 e2-micro **1개만 무료** (us-west1/central1/east1)
- 2개 운영 시 1개는 과금: **~$3.88/월** (e2-micro, us-central1 기준)
- 또는 1개는 무료 e2-micro, 다른 1개는 Oracle Cloud 무료 VM 등 대안 검토 가능

**별개 구성의 장점:**
- 프로젝트 간 장애 격리 (한쪽 데몬 오류가 다른 쪽에 영향 없음)
- 각 프로젝트 독립 배포/업데이트
- KIS WebSocket 40구독 한도를 프로젝트별 독립 운용

**별개 구성의 제약:**
- KIS WebSocket은 **앱키 1개당 1개 연결만 허용** — 동일 앱키로 2개 데몬 동시 연결 불가
- 해결: 앱키 2세트 발급 (KIS Developers 포털에서 추가 앱 등록) 또는 1개 앱키 공유 시 연결 시간대 분리
- Telegram 알림이 2곳에서 발송 → 중복 알림 가능성 (아래 섹션 8에서 상세 분석)

```
┌─ e2-micro #1 (stock_toolkit 전용) ──────────────────────┐
│  [KIS WebSocket] — 매수시그널 종목 중심 감시              │
│   ├─ cross_signal.json에서 매수 시그널 종목 추출          │
│   ├─ 급등/수급 반전/호가 벽 감지 → Telegram               │
│   └─ 30초 PINGPONG 유지                                  │
│  RAM: ~100MB (1GB 중 900MB 여유)                          │
└───────────────────────────────────────────────────────────┘

┌─ e2-micro #2 (theme_analysis 전용) ─────────────────────┐
│  [KIS WebSocket] — 테마 대장주 중심 감시                  │
│   ├─ latest.json에서 leader_code 추출                     │
│   ├─ 급등/급락/거래량 폭증 감지 → Telegram                │
│   └─ 30초 PINGPONG 유지                                  │
│  RAM: ~100MB (1GB 중 900MB 여유)                          │
└───────────────────────────────────────────────────────────┘

두 데몬 모두 기존 GitHub Actions 파이프라인 변경 없음
```

### 보완 4: 종목 선별 기준 — 프로젝트별 분리

**stock_toolkit 데몬 슬롯 배분:**

| 슬롯 | 종목 수 | 선별 기준 |
|------|---------|----------|
| 매수 시그널 | 15~20 | cross_signal.json 매수/적극매수 종목 |
| 보유 종목 | 5~10 | 포트폴리오 보유 종목 (Supabase) |
| 수동 지정 | 5~10 | Telegram /watch 또는 설정 파일 |
| **합계** | **~30~35** | 40 한도 내 여유 |

**theme_analysis 데몬 슬롯 배분** (참고, 별도 문서에서 관리):

| 슬롯 | 종목 수 | 선별 기준 |
|------|---------|----------|
| 지수 | 2 | KOSPI, KOSDAQ |
| 테마 대장주 | 10~15 | latest.json leader_code |
| 모의투자 보유 | 5~10 | paper-trading 매수 종목 |
| 수동 지정 | 5~10 | Telegram /watch |
| **합계** | **~30~35** | 40 한도 내 여유 |

### 보완 5: 알림 기준 — stock_toolkit 데몬

| 이벤트 | 기준 | 설명 |
|--------|------|------|
| 급등 | 등락률 ≥15% + 거래량 ≥200% | 기존 surge_alerts 기준 유지 |
| 수급 반전 (매수 전환) | 외국인/기관 순매도→순매수 | 매수 기회 감지 |
| 호가 매수벽/매도벽 | 호가 데이터 기반 집중/소멸 | 지지/저항 변동 |
| 목표가 도달 | 수동 설정 가격 | 보유 종목 관리 |

### 보완 6: 투입 대비 효과 — 현실적 공수

theme_analysis 문서의 공수 추정 반영 (WebSocket 알림 데몬만 = B안):

```
[투입] ~2일
- GCP e2-micro 셋업: 0.5일
- WebSocket 데몬 개발 (Python websockets + asyncio): 1일
- Telegram 알림 연동 + 종목 갱신 스케줄러: 0.5일

[효과]
- 급등/급락 즉시 감지 (현재 수십 분~수 시간 지연 → 초 단위)
- cron-job.org 의존 없이 장중 상시 감시
- 기존 시스템 side-effect 제로

[비용] 무료(1개) 또는 ~$3.88/월(2개 별개 운영 시)
[부작용] 거의 없음 — 기존 코드 변경 불필요, 독립 운영
```

---

## 8. 크로스 프로젝트 알림 중복 분석

> theme_analysis와 stock_toolkit의 알림이 별개 e2-micro에서 독립 운영될 때, 동일 종목에 대해 중복 알림이 발생하는지 분석.

### 현재 배치 알림 — 중복 없음

| 알림 내용 | theme_analysis | stock_toolkit | 중복 |
|----------|---------------|---------------|------|
| 상승/하락 종목 TOP10 | `main.py` | 없음 | - |
| AI 테마 분석 | `main.py` (Gemini) | 없음 | - |
| 대장주 수급 현황 | `collect_investor_data.py` | 없음 | - |
| 거래대금 TOP20 수급 | `collect_investor_data.py` | 없음 | - |
| 모닝 브리프 | 없음 | `daily_briefing.py` (Gemini) | - |
| 이브닝 리뷰 | 없음 | `daily_briefing.py` (Gemini) | - |
| 크로스 시그널 | 없음 | `cross_signal.py` | - |
| 연속 매수+대장주 | 없음 | `run_all.py` | - |
| 이상 거래 감지 | 없음 | `anomaly_detector.py` | - |
| 섹터 자금 흐름 | 없음 | `sector_flow.py` | - |
| 테마 라이프사이클 | 없음 | `theme_lifecycle.py` | - |

**현재 배치 알림은 역할이 완전 분리되어 중복 없음.**

### WebSocket 데몬 알림 — 중복 위험 2건

#### ⚠️ 중복 1: 급등 감지 (동일 종목, 다른 임계값)

| | theme_analysis 데몬 | stock_toolkit 데몬 |
|--|---------------------|-------------------|
| 기준 | 전일 종가 대비 **+5%** | 등락률 **≥15%** + 거래량 ≥200% |
| 구독 대상 | 테마 대장주 (leader_code) | 매수 시그널 종목 (cross_signal) |

**중복 시나리오:**
종목 A가 테마 대장주이면서 동시에 매수 시그널 종목인 경우:
1. +5% 도달 → theme_analysis 데몬이 Telegram 알림
2. +15% 도달 → stock_toolkit 데몬이 Telegram 알림
3. 같은 종목에 대해 **2번 알림** (단, 임계값이 다르므로 시점도 다름)

**판단:**
- 임계값이 +5% vs +15%로 **3배 차이** → 실질적으로 다른 이벤트 (조기 감지 vs 확실한 급등)
- 다만 양쪽 데몬 모두 동일 종목을 구독하고 있을 때만 발생
- **구독 종목이 겹치는 비율**에 따라 빈도 결정

**구독 종목 겹침 가능성:**
- theme_analysis: 테마 대장주 10~15종목 (latest.json leader_code)
- stock_toolkit: 매수 시그널 15~20종목 (cross_signal.json)
- cross_signal은 **테마 대장주 + 매수 시그널 교차**로 생성되므로, 대장주와 상당 부분 겹침
- **예상 겹침: 5~10종목** → 이 종목들에서 급등 발생 시 2번 알림 가능

**대응 방안:**
- (a) **허용 (권장):** +5%와 +15%는 실질적으로 다른 시그널이므로, 단계별 알림으로 활용
- (b) **stock_toolkit 데몬에서 급등 기준을 +15%로 유지:** theme_analysis의 +5% 조기 경보와 차별화가 이미 되어 있음
- (c) **메시지에 출처 태그 추가:** `[TA]`, `[ST]` 접두어로 어느 데몬에서 온 알림인지 구분

#### ⚠️ 중복 2: 수급 반전 — 실제 중복 아님 (보완적)

| | theme_analysis 데몬 | stock_toolkit 데몬 |
|--|---------------------|-------------------|
| 기준 | 순매수 → **순매도** 전환 | 순매도 → **순매수** 전환 |
| 의미 | 이탈 경고 | 매수 기회 감지 |

**판단:** 감지 방향이 반대이므로 **중복이 아니라 보완적**. 동일 종목에서 수급이 오전에 순매수→순매도(theme_analysis 알림), 오후에 순매도→순매수(stock_toolkit 알림) 발생하면, 수급 전환의 양방향을 모두 포착하는 효과.

### 알림 중복 요약

| 알림 유형 | 겹침 여부 | 심각도 | 대응 |
|----------|----------|--------|------|
| 급등 감지 | +5% vs +15% 다른 임계값 | **낮음** | 단계별 알림으로 활용. 메시지에 출처 태그 추가 권장 |
| 급락 감지 | theme_analysis만 (-3%) | 없음 | - |
| 거래량 폭증 | theme_analysis만 (5분 3배) | 없음 | - |
| 수급 반전 | 방향 반대 (보완적) | 없음 | 양방향 포착으로 오히려 유익 |
| 호가 벽 감지 | stock_toolkit만 | 없음 | - |
| 목표가 도달 | 양쪽 모두 가능 | **중간** | 한쪽에서만 관리하도록 역할 지정 필요 |

**결론:** 별개 e2-micro 운영 시 **실질적 중복 위험은 낮음**. 급등 감지만 임계값 차이로 동일 종목에 2번 알림 가능하나, 의미가 다르므로 허용 가능. 목표가 도달 알림은 한쪽 데몬에서만 관리하도록 역할 분리 필요.

---

## 9. 알림 통합 — theme_analysis 알림 중단 시 보완 분석

> theme_analysis의 Telegram 알림을 사용하지 않고, stock_toolkit에서만 알림 기능을 운영할 때 발생하는 공백과 보완 방안.

### 배치 알림 공백 5건

theme_analysis에서 제공하던 알림 중 stock_toolkit에 없는 것:

| # | 누락 알림 | theme_analysis 소스 | stock_toolkit 현황 | 보완 가능성 |
|---|----------|--------------------|--------------------|------------|
| 1 | **상승 종목 TOP10** (거래량+상승률+3일 등락률) | `main.py` | rising_stocks 데이터 보유 (run_all.py 141행), 알림 미발송 | **쉬움** — 포맷+send_message 추가 |
| 2 | **하락 종목 TOP10** | `main.py` | falling_stocks 데이터 보유 (run_all.py 145행), 알림 미발송 | **쉬움** — 동일 |
| 3 | **AI 테마 분석** (시장요약+테마+대장주+뉴스근거) | `main.py` (Gemini) | 모닝 브리프가 유사하나 테마별 대장주+뉴스 근거는 별도 | **중간** — Gemini 프롬프트 추가 또는 모닝 브리프 확장 |
| 4 | **대장주 수급 현황** (외/기/개/프 + 거래원 매수·매도 상위) | `collect_investor_data.py` (7회/일) | investor_data에서 외/기/개 순매수는 있으나, **거래원 정보(골드만삭스 등) 미수집** | **중간** — KIS API `FHKST01010600` (거래원별 매매) 호출 추가 필요 |
| 5 | **거래대금 TOP20 수급** | `collect_investor_data.py` | 미수집 | **중간** — 거래대금 상위 종목 조회 + 수급 조회 추가 필요 |

### WebSocket 데몬 알림 공백 5건

| # | 누락 알림 | theme_analysis 설계 기준 | stock_toolkit 현재 설계 | 보완 난이도 |
|---|----------|------------------------|----------------------|------------|
| 6 | **급등 조기 경보 (+5%)** | 전일 종가 대비 +5% | +15% + 거래량 200%만 | **쉬움** — 단계별 임계값 추가 (+5%/+10%/+15%) |
| 7 | **급락 감지 (-3%)** | 전일 종가 대비 -3% | 없음 | **쉬움** — 하락 방향 조건 추가 |
| 8 | **거래량 폭증 (실시간)** | 직전 5분 평균 대비 3배 | 배치(anomaly_detector)에만 존재 | **쉬움** — 5분 윈도우 체결량 누적 로직 |
| 9 | **수급 반전 (매수→매도)** | 순매수→순매도 전환 | 순매도→순매수만 | **쉬움** — 반대 방향 조건 추가 |
| 10 | **목표가 도달** | 수동 설정 가격 | 없음 | **쉬움** — 설정 가격 대비 체결가 비교 |

### 보완 우선순위

**즉시 필요 (stock_toolkit 데몬 설계에 반영):**

| 순위 | 항목 | 사유 |
|------|------|------|
| 1 | 급락 감지 (-3%) | 손실 방어에 필수, 현재 전혀 없음 |
| 2 | 급등 조기 경보 (+5%) | +15%는 너무 높아서 이미 급등 완료 후 감지. +5%가 실용적 |
| 3 | 거래량 폭증 (실시간) | 세력 유입 초기 감지. 배치에서만 있으면 수십 분 지연 |
| 4 | 수급 반전 (매수→매도) | 보유 종목 이탈 신호 — 매도 타이밍에 중요 |
| 5 | 목표가 도달 | 보유 종목 익절/손절 관리 |

**점진적 보완 (배치 알림 추가):**

| 순위 | 항목 | 사유 |
|------|------|------|
| 6 | 상승/하락 종목 TOP10 | 데이터 이미 있음, 포맷+발송만 추가 |
| 7 | 대장주 수급 + 거래원 | KIS API 거래원 조회 추가 개발 필요 |
| 8 | AI 테마 분석 | 모닝 브리프와 역할 겹침 검토 후 결정 |

### 보완된 stock_toolkit WebSocket 데몬 알림 기준 (최종)

| 이벤트 | 기준 | 설명 |
|--------|------|------|
| **급등 (단계별)** | +5% / +10% / +15% | 조기 경보 → 주의 → 확실한 급등 |
| **급락** | -3% / -5% | 손절 경고 → 급락 확정 |
| **거래량 폭증** | 직전 5분 평균 대비 3배 | 세력 유입 가능성 |
| **수급 반전 (양방향)** | 순매수↔순매도 전환 | 매수 기회 + 이탈 경고 모두 감지 |
| **호가 매수벽/매도벽** | 호가 집중·소멸 감지 | 지지/저항 변동 |
| **목표가 도달** | 수동 설정 가격 | 익절/손절 관리 |

이 기준으로 theme_analysis의 WebSocket 알림 설계를 완전히 흡수.

---

## Sources

- [Firestore pricing | Google Cloud](https://cloud.google.com/firestore/pricing)
- [Firebase Pricing](https://firebase.google.com/pricing)
- [Compute Engine free tier](https://www.freetiers.com/directory/google-compute-engine)
- [Cloud Functions pricing](https://cloud.google.com/functions/pricing-1stgen)
- [GCP Free Cloud Features](https://docs.cloud.google.com/free/docs/free-cloud-features)
