-- alert_config에 익절/손절 비율 컬럼 추가
-- Supabase Dashboard > SQL Editor에서 실행
ALTER TABLE alert_config ADD COLUMN IF NOT EXISTS take_profit_pct NUMERIC DEFAULT 3.0;
ALTER TABLE alert_config ADD COLUMN IF NOT EXISTS stop_loss_pct NUMERIC DEFAULT -3.0;
