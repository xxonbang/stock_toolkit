"""신성이엔지 데이터 검증"""
import asyncio
import sys
sys.path.insert(0, ".")


async def main():
    from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
    from daemon.http_session import get_session, close_session
    session = await get_session()
    h = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}
    base = SUPABASE_URL + "/rest/v1"

    # 신성이엔지 auto_trades 전체
    print("=== 신성이엔지(011930) auto_trades ===")
    url = f"{base}/auto_trades?code=eq.011930&select=id,status,filled_price,sell_price,pnl_pct,sell_reason,created_at,filled_at,sold_at&order=created_at.asc"
    async with session.get(url, headers=h) as resp:
        trades = await resp.json()
    for t in trades:
        ca = str(t.get("created_at", ""))[:19]
        fa = str(t.get("filled_at", ""))[:19]
        sa = str(t.get("sold_at", ""))[:19]
        print(f"  [{t['status']:>10}] filled={t.get('filled_price','?'):>6} sell={str(t.get('sell_price','?')):>6} pnl={str(t.get('pnl_pct','?')):>6} reason={str(t.get('sell_reason','-')):<16} created={ca} filled_at={fa} sold_at={sa}")

    # 신성이엔지 stepped 시뮬
    print("\n=== 신성이엔지 strategy_simulations ===")
    url2 = f"{base}/strategy_simulations?select=id,trade_id,strategy_type,status,entry_price,exit_price,pnl_pct,exit_reason,created_at,exited_at&order=created_at.asc"
    async with session.get(url2, headers=h) as resp2:
        sims = await resp2.json()
    sim_only_ids = {t["id"] for t in trades}
    for s in sims:
        if s["trade_id"] in sim_only_ids:
            ca = str(s.get("created_at", ""))[:19]
            ea = str(s.get("exited_at", ""))[:19]
            print(f"  [{s['strategy_type']:>8}] {s['status']:<6} entry={s['entry_price']:>6} exit={str(s.get('exit_price','-')):>6} pnl={str(s.get('pnl_pct','-')):>6} reason={str(s.get('exit_reason','-')):<16} created={ca} exited={ea}")

    await close_session()


asyncio.run(main())
