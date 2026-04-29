---
name: gcp-logs
description: GCP ws-daemon의 journalctl 로그를 시나리오별로 조회. Use when 사용자가 "데몬 로그", "오늘 매매 로그", "특정 종목 추적", "에러 로그", "장중 활동 확인" 등을 요청할 때.
allowed-tools: Bash(gcloud compute ssh ws-daemon --zone=us-central1-a --command=*)
---

# GCP ws-daemon Logs

journalctl을 시나리오별로 정형화하여 빠르게 조회.

## 1. 오늘 활동 요약 (heartbeat 제외)
```bash
gcloud compute ssh ws-daemon --zone=us-central1-a --command='sudo journalctl -u ws-daemon --since "today" 2>/dev/null | grep -v heartbeat | tail -50'
```

## 2. 특정 종목 추적 (전수)
```bash
# 코드 또는 종목명 둘 중 매칭
gcloud compute ssh ws-daemon --zone=us-central1-a --command='sudo journalctl -u ws-daemon --since "today" 2>/dev/null | grep -E "{CODE}|{NAME}" | head -100'
```
예: `131760|파인텍`, `098460|고영`

## 3. 에러/경고만
```bash
gcloud compute ssh ws-daemon --zone=us-central1-a --command='sudo journalctl -u ws-daemon --since "today" -p warning 2>/dev/null | tail -50'
```

## 4. 매수/매도 이벤트만
```bash
gcloud compute ssh ws-daemon --zone=us-central1-a --command='sudo journalctl -u ws-daemon --since "today" 2>/dev/null | grep -E "매수 체결|매도|EOD|시뮬 close|stop_loss|trailing|max_hold|emergency" | head -50'
```

## 5. WebSocket 연결 이력
```bash
gcloud compute ssh ws-daemon --zone=us-central1-a --command='sudo journalctl -u ws-daemon --since "today" 2>/dev/null | grep -E "WebSocket|구독|approval_key|PINGPONG" | tail -30'
```

## 6. systemd 상태 + 최근 5분 로그
```bash
gcloud compute ssh ws-daemon --zone=us-central1-a --command='sudo systemctl status ws-daemon --no-pager | head -15; echo "---"; sudo journalctl -u ws-daemon --since "5 min ago" 2>/dev/null | tail -20'
```

## 7. 특정 시간대만 (예: 09:00~09:10 KST = 00:00~00:10 UTC)
```bash
gcloud compute ssh ws-daemon --zone=us-central1-a --command='sudo journalctl -u ws-daemon --since "today 00:00:00" --until "today 00:10:00" 2>/dev/null | grep -v heartbeat | head -100'
```

## 8. 디스크/메모리 점검
```bash
gcloud compute ssh ws-daemon --zone=us-central1-a --command='df -h | head -5; echo "---"; free -h'
```

## 시각 변환 메모
- KST 09:05 = UTC 00:05
- KST 15:15 = UTC 06:15
- KST 15:30 = UTC 06:30 (장 마감)
- journalctl 시각은 **UTC 표시** (Apr 28 00:05:26 = 2026-04-28 09:05:26 KST)

## 보고 시 주의
- heartbeat 라인은 보통 정보 가치 없음 → 제외 권장
- ERROR 라인은 항상 포함
- 장중 핵심 이벤트: 매수 체결 → 시뮬 close → heartbeat 누적 → EOD 강제 매도
- ms 단위 파인 추적이 필요하면 `--output=short-precise` 옵션 추가
