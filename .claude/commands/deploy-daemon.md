---
description: 코드 push + GCP ws-daemon git pull + systemctl restart + 헬스체크
---

배포 절차:

## 1. GitHub push
```bash
git push origin main
gh run list -R xxonbang/stock_toolkit -L 3   # deploy-pages 트리거 확인
```

## 2. daemon/** 또는 modules/** 변경 시 GCP 반영
```bash
gcloud compute ssh ws-daemon --zone=us-central1-a --command='cd ~/stock_toolkit && git pull --ff-only && sudo systemctl restart ws-daemon && sleep 3 && sudo systemctl is-active ws-daemon'
```

## 3. 헬스체크
```bash
gcloud compute ssh ws-daemon --zone=us-central1-a --command='sudo journalctl -u ws-daemon --since="1 minute ago" --no-pager | tail -20'
```

## 안전 가드
- 토요일/일요일은 한국 증시 휴장 → systemctl restart 자유
- 평일 09:00–15:30 장중에는 신중 (재시작 시 WebSocket 알림 일시 끊김)
- ws-daemon **stop/disable**은 block-destructive.sh가 차단 — restart만 가능

## DNS 이슈 시
GCP VM의 Tailscale이 외부 DNS를 hijack하면 git pull 실패. 우회:
```bash
gcloud compute ssh ws-daemon --zone=us-central1-a --command='sudo tailscale set --accept-dns=false'
```

## 최후의 수단
ssh 자체가 응답 안 하면 (google-guest-agent timeout 누적):
```bash
gcloud compute instances reset ws-daemon --zone=us-central1-a   # 휴장 시에만 사용자 승인 후
```

상세는 `.claude/skills/deploy-daemon/SKILL.md`.
