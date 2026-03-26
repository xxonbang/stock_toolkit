-- 전략 비교 기능 마이그레이션
-- 1) alert_config에 strategy_type 컬럼 추가
ALTER TABLE alert_config ADD COLUMN IF NOT EXISTS strategy_type TEXT DEFAULT 'fixed';

-- 2) strategy_simulations 테이블 생성
CREATE TABLE IF NOT EXISTS strategy_simulations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  trade_id UUID REFERENCES auto_trades(id) ON DELETE CASCADE,
  strategy_type TEXT NOT NULL,
  entry_price INTEGER NOT NULL,
  exit_price INTEGER,
  exit_reason TEXT,
  pnl_pct NUMERIC,
  status TEXT DEFAULT 'open',
  peak_price INTEGER DEFAULT 0,
  stepped_stop_pct NUMERIC DEFAULT -2.0,
  created_at TIMESTAMPTZ DEFAULT now(),
  exited_at TIMESTAMPTZ,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE
);

-- 3) RLS 정책
ALTER TABLE strategy_simulations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users read own simulations" ON strategy_simulations
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Service role full access simulations" ON strategy_simulations
  FOR ALL USING (true);

-- 4) 인덱스
CREATE INDEX IF NOT EXISTS idx_sim_trade_id ON strategy_simulations(trade_id);
CREATE INDEX IF NOT EXISTS idx_sim_user_status ON strategy_simulations(user_id, status);
CREATE INDEX IF NOT EXISTS idx_sim_created ON strategy_simulations(created_at DESC);
