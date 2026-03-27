-- alert_config에 flash_spike_pct 컬럼 추가
ALTER TABLE alert_config ADD COLUMN IF NOT EXISTS flash_spike_pct NUMERIC DEFAULT 5.0;
