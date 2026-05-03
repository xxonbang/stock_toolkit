---
description: Supabase auto_trades + strategy_simulations DB를 KST 기준으로 직접 조회. 오늘/특정일/누적 매매·시뮬 성과 산출.
---

조회 절차:

1. **인증**: `daemon/.env`의 `SUPABASE_URL` + `SUPABASE_SECRET_KEY` 사용 (python-dotenv).
2. **KST 정확 분리**: `created_at=gte.YYYY-MM-DDT00:00:00%2B09:00&...lt.{day}T23:59:59%2B09:00`
3. **테이블 분리**:
   - `auto_trades`: 실전(`status=executed`) + sim_only(`status=sim_only`) 구분 필수
   - `strategy_simulations`: 7전략(`strategy_type` 컬럼)
4. **출력 KST**: `datetime.now(timezone(timedelta(hours=9)))`

자세한 쿼리 템플릿은 `.claude/skills/query-trades/SKILL.md` 참고.

## 사용 예
- "오늘 모의투자 성과" → `created_at` 오늘 + `status=sim_only` 필터
- "특정 종목 추적" → `code=eq.XXXXXX`
- "전략별 누적 성과" → `strategy_simulations` group by `strategy_type`

## 주의
- `daemon/.env` Read는 deny 룰. python `load_dotenv`로 메모리 적재만 (값 출력 X).
- 핵심 테이블 DELETE/UPDATE 금지 (block-destructive.sh 차단).
