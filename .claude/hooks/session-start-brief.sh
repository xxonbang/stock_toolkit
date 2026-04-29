#!/usr/bin/env bash
# SessionStart — 프로젝트 현황 자동 브리프.
cd /Users/sonbyeongcheol/DEV/stock_toolkit 2>/dev/null || exit 0
TODAY=$(date +%Y-%m-%d)
echo "=== stock_toolkit brief ($TODAY) ==="
echo "[HEAD] $(git log -1 --oneline 2>/dev/null)"
echo "[branch] $(git branch --show-current 2>/dev/null)"
echo "[status]"
git status --short 2>/dev/null | head -8

# 오늘자 task_history 확인 (CLAUDE.md 규칙 5)
if [ -f docs/task_history.md ]; then
  TODAY_COUNT=$(awk -v d="## $TODAY" '$0==d{f=1;next} /^## /{f=0} f && /^### /{c++} END{print c+0}' docs/task_history.md 2>/dev/null)
  if [ "${TODAY_COUNT:-0}" -gt 0 ] 2>/dev/null; then
    echo "[task_history] 오늘자 ${TODAY_COUNT}건 ✓"
  else
    PREV_DATE=$(grep -E '^## 2026' docs/task_history.md 2>/dev/null | head -1 | awk '{print $2}')
    PREV_COUNT=$(awk -v d="## $PREV_DATE" '$0==d{f=1;next} /^## /{f=0} f && /^### /{c++} END{print c+0}' docs/task_history.md 2>/dev/null)
    echo "[task_history] 오늘자 없음 — 직전($PREV_DATE) ${PREV_COUNT:-0}건"
  fi
fi

echo "[recent commits]"
git log --oneline -3 2>/dev/null
echo "==================================="
exit 0
