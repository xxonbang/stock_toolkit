#!/usr/bin/env bash
# PostToolUse — Python 파일 편집 후 syntax check (py_compile).
# daemon/, modules/, scripts/ 하위만 대상.
FILE=$(jq -r '.tool_input.file_path // ""')
case "$FILE" in
  */stock_toolkit/daemon/*.py|*/stock_toolkit/modules/*.py|*/stock_toolkit/scripts/*.py)
    python3 -m py_compile "$FILE" 2>&1 | head -20
    ;;
esac
exit 0
