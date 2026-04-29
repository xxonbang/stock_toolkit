---
name: deploy-daemon
description: stock_toolkit 코드 배포 — local push + GCP ws-daemon git pull + systemctl restart + 헬스체크. Use when 사용자가 "배포", "GCP 반영", "데몬 업데이트", "git push 후 GCP 동기화" 등을 요청할 때.
allowed-tools: Bash(git push *), Bash(gcloud compute ssh *), Bash(gh run list*), Bash(curl *)
---

# Deploy stock_toolkit

코드 변경 후 GitHub + GCP ws-daemon에 안전하게 배포.

## 사전 점검
1. `git status --short` — 커밋되지 않은 변경 없는지 확인
2. 최신 커밋 확인: `git log --oneline -3`
3. 현재 분기 확인: `git branch --show-current` (보통 `main`)

## 단계

### 1. GitHub push (원격 동기화)
```bash
git push origin main
```
- 자동 트리거: `deploy-pages.yml` (프론트 배포) + `phase1-alerts.yml` (briefing 생성)
- 진행 확인: `gh run list -L 3`

### 2. daemon 코드 변경이 있으면 GCP 반영
변경 파일에 `daemon/**` 또는 `modules/**`이 포함되면 필요:
```bash
gcloud compute ssh ws-daemon --zone=us-central1-a --command='cd ~/stock_toolkit && git pull --ff-only 2>&1 | tail -5'
```

### 3. systemd 재시작 (장중 회피 권고)
**현재 시각 확인 — 09:00~15:30 KST 장중에는 보유 종목이 있을 수 있어 재시작 신중**:
```bash
gcloud compute ssh ws-daemon --zone=us-central1-a --command='sudo systemctl restart ws-daemon && sleep 2 && sudo systemctl status ws-daemon --no-pager | head -10'
```

### 4. 헬스체크
```bash
gcloud compute ssh ws-daemon --zone=us-central1-a --command='sudo journalctl -u ws-daemon --since "1 minute ago" | tail -20'
```
**정상 신호:**
- `Active: active (running)`
- 로그에 `[daemon.main] INFO: WebSocket 알림 데몬 시작` 또는 heartbeat 발생

### 5. GitHub Actions 완료 확인
```bash
gh run list -L 3
```
- 모두 `success` 상태 확인

## 주의사항
- **ws-daemon.service stop/disable 절대 금지** — 실거래 중단됨
- 장중(09:00~15:30 KST) 재시작은 사용자 명시적 요청 시만
- daemon 코드 변경 없이 frontend/modules만 수정한 경우 GCP pull은 선택 (GitHub Actions로 충분)

## 배포 범위 결정 매트릭스

| 변경 영역 | git push | GCP pull | systemctl restart |
|-----------|----------|----------|-------------------|
| frontend/** | ✓ | - | - |
| modules/** | ✓ | ✓ | - (다음 cron 실행 시 반영) |
| daemon/** | ✓ | ✓ | ✓ (사용자 확인 후) |
| docs/**, scripts/** | ✓ | (선택) | - |

## 실패 복구
- git push 실패 → conflict resolve 후 재시도
- GCP pull 실패 → 원격 변경 충돌 → 사용자에게 보고
- systemctl restart 실패 → journalctl 확인 후 직전 커밋 `git checkout <SHA>` + 재시작
