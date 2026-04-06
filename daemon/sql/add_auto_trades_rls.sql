-- auto_trades RLS 정책 추가
-- 인증된 사용자가 자신의 거래만 조회/수정 가능하도록 제한

-- 1) RLS 활성화
ALTER TABLE auto_trades ENABLE ROW LEVEL SECURITY;

-- 2) SELECT: 인증된 사용자는 전체 조회 (1인 사용 기준, 다중 사용자 시 user_id 필터 추가)
CREATE POLICY "auto_trades_select" ON auto_trades
  FOR SELECT USING (auth.role() = 'authenticated');

-- 3) INSERT: 인증된 사용자만 (daemon은 service_role로 우회)
CREATE POLICY "auto_trades_insert" ON auto_trades
  FOR INSERT WITH CHECK (auth.role() = 'authenticated');

-- 4) UPDATE: 인증된 사용자만
CREATE POLICY "auto_trades_update" ON auto_trades
  FOR UPDATE USING (auth.role() = 'authenticated');

-- 5) DELETE: 인증된 사용자만
CREATE POLICY "auto_trades_delete" ON auto_trades
  FOR DELETE USING (auth.role() = 'authenticated');
