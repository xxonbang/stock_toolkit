#!/usr/bin/env bash
# PostToolUse — frontend/src 편집 후 tsc --noEmit 자동 실행.
FILE=$(jq -r '.tool_input.file_path // ""')
if [[ "$FILE" == */stock_toolkit/frontend/src/* ]]; then
  cd /Users/sonbyeongcheol/DEV/stock_toolkit/frontend 2>/dev/null || exit 0
  npx tsc --noEmit 2>&1 | head -30
fi
exit 0
