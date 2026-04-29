#!/usr/bin/env bash
# Stop — 최근 커밋 후 task_history.md 갱신 누락 경고.
cd /Users/sonbyeongcheol/DEV/stock_toolkit 2>/dev/null || exit 0
[ -f docs/task_history.md ] || exit 0
LAST_COMMIT_TS=$(git log -1 --format=%ct 2>/dev/null || echo 0)
HISTORY_TS=$(stat -f %m docs/task_history.md 2>/dev/null || echo 0)
NOW=$(date +%s)
COMMIT_AGO=$((NOW - LAST_COMMIT_TS))
HISTORY_AGO=$((NOW - HISTORY_TS))
# 최근 1시간 이내 커밋 + task_history가 그보다 오래됐으면 경고
if [ "$COMMIT_AGO" -lt 3600 ] && [ "$HISTORY_AGO" -gt "$COMMIT_AGO" ]; then
  LAST_MSG=$(git log -1 --format=%s 2>/dev/null)
  echo "⚠️  최근 커밋(\"$LAST_MSG\") 후 docs/task_history.md 갱신 없음 — 기록 추가 권장"
fi
exit 0
