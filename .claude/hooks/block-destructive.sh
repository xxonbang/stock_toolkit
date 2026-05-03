#!/usr/bin/env bash
# PreToolUse — 강도 "강": 파일 파괴 + git 위험 + 데몬 정지 + DB 삭제 + KIS 주문 차단.
# exit 2 만이 block (exit 1은 block 안 됨).
set -e
CMD=$(jq -r '.tool_input.command // ""')

# 1. 파일/디스크 파괴
case "$CMD" in
  *"rm -rf "*|*"rm -fr "*|*"rm --recursive --force"*)
    echo "BLOCKED: rm -rf 파괴적 작업 금지" >&2; exit 2 ;;
esac

# 2. git 위험 명령
case "$CMD" in
  *"git push --force"*|*"git push -f "*)
    echo "BLOCKED: force push 금지" >&2; exit 2 ;;
  *"git reset --hard"*)
    echo "BLOCKED: git reset --hard 금지" >&2; exit 2 ;;
  *"git commit --no-verify"*|*"git commit -n "*)
    echo "BLOCKED: pre-commit hook skip 금지" >&2; exit 2 ;;
esac

# 3. ws-daemon 제어 (실거래 데몬 — 정지 금지)
case "$CMD" in
  *"systemctl stop ws-daemon"*|*"systemctl disable ws-daemon"*)
    echo "BLOCKED: ws-daemon 정지 금지 (실거래 중단됨). 재시작은 명시적으로만 요청." >&2; exit 2 ;;
  *"gcloud compute instances delete"*)
    echo "BLOCKED: GCP instance 삭제 금지" >&2; exit 2 ;;
esac

# 4. Supabase DB 삭제/대량 업데이트 (auto_trades / strategy_simulations 보호)
# REST API delete: DELETE method 또는 ?... 패턴 + curl
if echo "$CMD" | grep -qE 'curl.*-X[[:space:]]*DELETE.*(auto_trades|strategy_simulations|alert_config|portfolio_holdings|orderbook_avg)'; then
  echo "BLOCKED: Supabase 핵심 테이블 DELETE 금지 (auto_trades/strategy_simulations 등)" >&2; exit 2
fi
# Python supabase.from(...).delete()
if echo "$CMD" | grep -qE '\.from\("?(auto_trades|strategy_simulations|alert_config|portfolio_holdings|orderbook_avg)"?\)\.delete\(\)'; then
  echo "BLOCKED: Supabase 핵심 테이블 .delete() 호출 금지" >&2; exit 2
fi
# SQL DELETE FROM
if echo "$CMD" | grep -qiE 'DELETE[[:space:]]+FROM[[:space:]]+(auto_trades|strategy_simulations|alert_config|portfolio_holdings|orderbook_avg)'; then
  echo "BLOCKED: SQL DELETE FROM 핵심 테이블 금지" >&2; exit 2
fi
# TRUNCATE / DROP TABLE
if echo "$CMD" | grep -qiE '(TRUNCATE|DROP)[[:space:]]+TABLE'; then
  echo "BLOCKED: TRUNCATE/DROP TABLE 금지" >&2; exit 2
fi

# 5. KIS 주문 API 직접 호출 (실수로 매수/매도 발생 방지)
# TTTC0801U/TTTC0802U=실투자 매수/매도, VTTC0801U/VTTC0802U=모의 매수/매도
if echo "$CMD" | grep -qE 'curl.*(TTTC080[12]U|VTTC080[12]U)'; then
  echo "BLOCKED: KIS 주문 API 직접 curl 금지 (place_buy_order/place_sell_order 함수 통해서만)" >&2; exit 2
fi
if echo "$CMD" | grep -qE 'order-cash.*(TTTC080[12]U|VTTC080[12]U)'; then
  echo "BLOCKED: KIS order-cash 엔드포인트 직접 호출 금지" >&2; exit 2
fi

# 6. .env 노출
case "$CMD" in
  *"cat "*".env"*|*"cat "*"daemon/.env"*)
    echo "BLOCKED: .env 파일 cat 금지 (Read 도구로 신중히)" >&2; exit 2 ;;
esac

# 7. wrapper(ssh/gcloud --command) 안의 위험 패턴 차단 — settings.json deny가 wrapper에 적용 안 됨
# gcloud compute ssh ... --command="..." 또는 ssh user@host '...' 형태 안 sudo/위험 명령 검사
INNER=""
if echo "$CMD" | grep -qE '^(gcloud[[:space:]]+compute[[:space:]]+ssh|ssh[[:space:]])'; then
  # --command="..." 또는 마지막 따옴표 인자 추출
  INNER=$(echo "$CMD" | sed -nE 's/.*--command="([^"]*)".*/\1/p')
  [ -z "$INNER" ] && INNER=$(echo "$CMD" | sed -nE "s/.*--command='([^']*)'.*/\1/p")
fi
if [ -n "$INNER" ]; then
  case "$INNER" in
    *"systemctl stop ws-daemon"*|*"systemctl disable ws-daemon"*)
      echo "BLOCKED: ws-daemon 정지/비활성화는 wrapper 안에서도 금지" >&2; exit 2 ;;
    *"tailscale down"*|*"tailscale logout"*)
      echo "BLOCKED: tailscale down/logout 금지 (ssh 연결 끊김)" >&2; exit 2 ;;
    *"rm -rf "*"~/stock_toolkit"*|*"rm -rf "*"/stock_toolkit"*)
      echo "BLOCKED: GCP 측 stock_toolkit 디렉토리 rm -rf 금지" >&2; exit 2 ;;
    *"shutdown"*|*"reboot"*|*"halt"*|*"poweroff"*)
      echo "BLOCKED: VM shutdown/reboot 금지 (gcloud reset만 명시적으로)" >&2; exit 2 ;;
    *"cat "*".env"*)
      echo "BLOCKED: 원격 .env cat 금지" >&2; exit 2 ;;
    *">"*".env"*|*"echo "*">"*".env"*)
      # ".env" 직접 덮어쓰기 차단 (>>는 append라 허용)
      if echo "$INNER" | grep -qE '[^>]>[[:space:]]*[^>]*\.env'; then
        echo "BLOCKED: .env 파일 덮어쓰기(>) 금지 (>> append만 허용)" >&2; exit 2
      fi ;;
  esac
fi

exit 0
