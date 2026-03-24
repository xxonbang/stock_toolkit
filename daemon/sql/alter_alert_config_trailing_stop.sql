-- trailing_stop_pct 컬럼 추가 (고점 대비 급락 손절 %)
ALTER TABLE alert_config
ADD COLUMN IF NOT EXISTS trailing_stop_pct REAL DEFAULT -3.0;
