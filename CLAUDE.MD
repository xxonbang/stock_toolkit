# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## 5. 세션/컴팩팅 시 작업 연속성 유지

**새 세션 시작 또는 context compacting 발생 시, 반드시 `docs/task_history.md`에서 오늘자 작업 이력을 읽고 확인한 뒤 작업을 이어갈 것.** 이전 작업 맥락을 파악하여 연속성을 최대화한다.

- 오늘자 이력이 있으면: **"[task_history 확인 완료] 오늘자 N건 확인"** 형식으로 표시.
- 오늘자 이력이 없으면: **직전 작업일** 이력을 확인하고 **"[task_history 확인 완료] 오늘자 이력 없음, 직전 작업일(YYYY-MM-DD) N건 확인"** 형식으로 표시.
- 확인하지 않은 채 작업을 시작하지 말 것.

## 6. Task History 기록

**기록 시점**: 커밋 완료 직후 또는 단위 작업 종료 시, 다음 작업으로 넘어가기 전에 반드시 `docs/task_history.md`에 이력을 기록한다.

**포맷 규칙:**

- 날짜별 `## YYYY-MM-DD` 헤더 (최신 날짜가 상단)
- 각 항목은 `### [카테고리] 제목 (YYYY-MM-DD HH:MM KST)` 형식 — 날짜와 시각 모두 포함, **KST 기준**
- 같은 날짜 내에서도 **최신 항목이 상단**에 위치하도록 역순 정렬
  - 카테고리: `기능`, `버그픽스`, `개선`, `리팩토링`, `설정`, `진단` 중 택1
- 필수 항목: 변경 파일, 내용 (1~2줄 요약)
- 선택 항목: 커밋 해시, 원인 (버그픽스 시)
- 최신 항목이 해당 날짜의 하단에 추가되도록 기록

## 6. 추측 금지 — 사실 기반 답변 원칙

**데이터 단위, 의미, 출처에 대한 질문에는 반드시 원본 소스코드(API 필드명, 주석, 수집 로직)까지 추적 확인한 후 답변한다.**

- 추측, 추정, 가정으로 답변 금지. 확인 안 된 내용은 "확인 필요"로 표기.
- 특히 금융 수치(금액, 수량, 비율)는 단위를 소스코드로 검증한 후에만 답변.
- 실행 이력, 설정값, 모드 등 사실 확인이 필요한 질문은 실제 로그/데이터를 전수 조회.

## 7. Research 문서 관리

조사/연구/진단 결과로 생성되는 md 문서는 `docs/research/` 폴더에 저장한다.

**파일명 규칙:** `YYYY-MM-DD-<단어1>-<단어2>.md`

- 날짜 뒤에 작업의 성격과 내용을 대표하는 **2개 단어**를 하이픈으로 연결
- 예: `2026-03-11-project-diagnostic.md`, `2026-04-01-api-latency.md`

## Doc Sync (doc-sync 스킬)

프로젝트 진행 중 `docs/` 하위 9개 문서를 자동 관리하고 세션 간 작업 상태를 복구한다.

- 모든 관리 문서는 **`docs/`** 폴더에 생성
- **누적형** 문서(`todo.md`, `decision.md`)는 기존 내용을 절대 삭제하지 않음
- 문서 업데이트 후 반드시 사용자에게 알림 출력
- UI와 문서 생성은 한국어 기본

## 8. 하네스 활용 가이드 (Agents · Commands · Hooks)

`.claude/` 하위에 5 agent · 5 command · 5 hook이 정의되어 있다. 메인이 직접 처리하지 말고 작업 성격에 맞는 컴포넌트로 위임/발동시킨다.

### Agents (Agent tool, subagent_type 지정)
- **`gcp-ops`** — GCP VM 운영(ssh / git pull / systemctl / journalctl / VM reset). 컨텍스트 격리로 ssh 반복 출력이 메인에 누적되는 것 방지.
- **`daemon-impl`** — daemon/** 코드 수정 (KIS WebSocket, alert_rules, position_db 등). 모의투자 정책·실거래 영향 검토 필수.
- **`frontend-impl`** — frontend/src/** 수정 (StockInsight, Dashboard, AuthContext 등). tsc + 빌드 검증 자동.
- **`analysis-impl`** — modules/news/, scripts/ 백테스트·분석 코드 수정.
- **`code-reviewer`** — 단위 작업 완료 후 plan 대비 검증. 한 chunk 끝나면 자동 호출 권장.

**호출 기준**: 한 작업이 ssh 명령 3회 이상, edit 5회 이상, 또는 다른 도메인(GCP↔frontend↔daemon)에 걸쳐있으면 agent로 위임.

### Slash Commands (`/<name>`)
- `/download-data` — 원격 JSON을 results/ + frontend/public/data/ 양쪽 동기화 (history 폴더 포함)
- `/query-trades` — Supabase auto_trades + strategy_simulations KST 기준 조회
- `/deploy-daemon` — push + GCP git pull + restart + 헬스체크
- `/gcp-logs` — journalctl / 시리얼 콘솔 로그 조회
- `/pr-checklist` — PR 생성 전 체크리스트

### Hooks (자동 발동)
- `block-destructive.sh` (PreToolUse Bash) — rm -rf, force push, ws-daemon stop, .env 노출, KIS 주문 직접 호출, ssh wrapper 안 sudo 위험 패턴 차단
- `tsc-after-edit.sh` / `python-syntax-check.sh` (PostToolUse Edit/Write) — frontend/src/** 편집 후 tsc, python 편집 후 py_compile 동기 실행
- `task-history-reminder.sh` (Stop) — 최근 4시간 커밋 중 task_history 미갱신이면 경고
- `session-start-brief.sh` (SessionStart) — HEAD/branch/today's task_history 자동 브리프

### 우선순위
**한 작업이 진입할 때 가장 먼저 묻는 것**: 이 작업에 매칭되는 slash command 또는 agent가 있는가? 있으면 위임. 없으면 메인 처리.
