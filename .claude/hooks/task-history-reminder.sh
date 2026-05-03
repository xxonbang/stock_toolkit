#!/usr/bin/env bash
# Stop — task_history.md 갱신 누락 경고 (정밀화).
# 조건: 최근 4시간 내 main에 커밋 N개가 있고, 그 중 어떤 것도 docs/task_history.md를 변경하지 않았으면 경고.
# (mtime 기반은 부정확 — git tree 변경 여부로 판단)
cd /Users/sonbyeongcheol/DEV/stock_toolkit 2>/dev/null || exit 0
[ -f docs/task_history.md ] || exit 0

SINCE="4 hours ago"
RECENT=$(git log --since="$SINCE" --pretty=format:"%h %s" 2>/dev/null)
[ -z "$RECENT" ] && exit 0   # 최근 커밋 없음

# 최근 4시간 커밋들 중 task_history.md를 건드린 게 있는지
TOUCHED=$(git log --since="$SINCE" --name-only --pretty=format: 2>/dev/null | grep -c "^docs/task_history.md$")
if [ "${TOUCHED:-0}" -eq 0 ]; then
  COMMIT_COUNT=$(echo "$RECENT" | wc -l | tr -d ' ')
  LAST_MSG=$(git log -1 --format=%s 2>/dev/null)
  echo "⚠️  최근 4시간 ${COMMIT_COUNT}개 커밋 중 docs/task_history.md 갱신 없음 — 기록 추가 권장"
  echo "   (가장 최근: \"$LAST_MSG\")"
fi
exit 0
