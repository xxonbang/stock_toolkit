-- 알림 설정 테이블
-- Supabase Dashboard > SQL Editor에서 실행
CREATE TABLE IF NOT EXISTS alert_config (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  alert_mode TEXT NOT NULL DEFAULT 'all' CHECK (alert_mode IN ('all', 'portfolio_only')),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id)
);

-- RLS 활성화
ALTER TABLE alert_config ENABLE ROW LEVEL SECURITY;

-- 정책: 로그인 사용자는 자신의 설정만 CRUD
CREATE POLICY "Users manage own alert config"
  ON alert_config FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- 정책: service_role(daemon)은 전체 읽기 가능
CREATE POLICY "Service role reads all"
  ON alert_config FOR SELECT
  USING (auth.role() = 'service_role');
