---
description: PR 생성 전 체크리스트 (커밋·테스트·문서·배포 영향 검증)
---

PR 생성 전 다음 항목을 모두 점검하라:

## 1. 커밋 위생
- [ ] 커밋 메시지가 변경 의도를 명확히 설명하는가?
- [ ] 한 커밋이 한 가지 일만 하는가? (mixed concerns 없음)
- [ ] `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` 포함됐는가?
- [ ] task_history.md 갱신 커밋이 있는가?

## 2. 검증
- [ ] frontend 변경 시 `cd frontend && npx tsc --noEmit` 통과
- [ ] frontend 변경 시 `cd frontend && npm run build` 성공
- [ ] daemon/python 변경 시 `python3 -m py_compile <file>` 통과
- [ ] daemon 변경 시 `cd daemon && pytest -q` 통과 (해당되면)

## 3. 영향 범위
- [ ] frontend만? → GitHub Actions deploy-pages.yml로 자동 배포됨
- [ ] daemon/** 변경? → GCP ws-daemon 재시작 필요 (사용자 명시 요청 시)
- [ ] modules/** 변경? → 다음 cron(GitHub Actions) 실행 시 반영
- [ ] DB 스키마 변경? → Supabase Dashboard에서 ALTER TABLE 수동 실행 필요

## 4. 안전 점검
- [ ] .env 같은 비밀 파일이 staged되지 않았는가?
- [ ] KIS 키, Supabase Secret이 코드/주석/로그에 노출됐는가?
- [ ] `git diff --stat`로 의도하지 않은 파일 추가 없는지 확인

## 5. 문서
- [ ] 새 기능/변경의 의도를 docs/research/YYYY-MM-DD-W1-W2.md에 기록할 가치가 있는가?
- [ ] CLAUDE.md 또는 메모리에 영구 보존할 새 도메인 지식/제약이 있는가?

## PR 본문 권장 형식
```
## Summary
- 핵심 변경 1~3 bullet

## Test plan
- [ ] 검증 항목

## Affects
- frontend / daemon / modules / docs (해당 영역만)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```
