-- 주가 계산기(가상 매수 시나리오) 공유 저장소
-- 양 프로젝트(stock_toolkit / theme-analysis)가 동일 user_id 기준으로 공유
-- user_id 1개당 1 row, tabs는 JSONB로 전체 시나리오 상태 저장
-- 새로고침 시 fetch + 변경 시 upsert (Realtime 미사용)
-- updated_at은 application에서 직접 전송 (트리거 미사용 — Supabase SQL Editor에서 $$ 파싱 이슈 회피)

create table if not exists public.paper_calc_history (
  user_id uuid primary key references auth.users(id) on delete cascade,
  tabs jsonb not null default '[]'::jsonb,
  active_tab_id text,
  updated_at timestamptz not null default now()
);

alter table public.paper_calc_history enable row level security;

drop policy if exists "paper_calc_history_owner" on public.paper_calc_history;
create policy "paper_calc_history_owner"
  on public.paper_calc_history
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
