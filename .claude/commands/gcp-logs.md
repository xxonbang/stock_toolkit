---
description: GCP ws-daemon journalctl 로그 조회 — 데몬 동작/에러/자막 fetch 결과 확인
---

GCP 로그 조회:

## 최근 5분
```bash
gcloud compute ssh ws-daemon --zone=us-central1-a --command='sudo journalctl -u ws-daemon --since="5 minutes ago" --no-pager | tail -50'
```

## 자막 fetch 결과만
```bash
gcloud compute ssh ws-daemon --zone=us-central1-a --command='sudo journalctl -u ws-daemon --since="2 hours ago" --no-pager | grep -E "YouTube|자막|fetch_and_store"'
```

## 에러만
```bash
gcloud compute ssh ws-daemon --zone=us-central1-a --command='sudo journalctl -u ws-daemon --since="1 hour ago" -p err --no-pager | tail -30'
```

## 데몬 상태
```bash
gcloud compute ssh ws-daemon --zone=us-central1-a --command='sudo systemctl status ws-daemon --no-pager | head -15'
```

## 시리얼 콘솔 (ssh 끊긴 상태에서도 가능)
```bash
gcloud compute instances get-serial-port-output ws-daemon --zone=us-central1-a | tail -50
```

상세 패턴은 `.claude/skills/gcp-logs/SKILL.md`.
