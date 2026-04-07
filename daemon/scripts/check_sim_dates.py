"""시뮬레이션 날짜 및 origSold 매칭 확인"""
import asyncio
import sys
sys.path.insert(0, ".")


async def main():
    from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
    from daemon.http_session import get_session, close_session
    session = await get_session()
    headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}
    base = SUPABASE_URL + "/rest/v1"

    # stepped 시뮬의 trade_id → sim_only auto_trades
    url = f"{base}/strategy_simulations?strategy_type=eq.stepped&select=id,trade_id,status,entry_price,created_at&order=created_at.desc"
    async with session.get(url, headers=headers) as resp:
        sims = await resp.json()

    for s in sims:
        tid = s["trade_id"]
        # sim_only auto_trades
        url2 = f"{base}/auto_trades?id=eq.{tid}&select=code,name,status,created_at"
        async with session.get(url2, headers=headers) as resp2:
            trades = await resp2.json()
        tr = trades[0] if trades else {}
        code = tr.get("code", "?")
        name = tr.get("name", "?")
        sim_only_created = tr.get("created_at", "")[:19]

        # origSold: 같은 code의 sim_only 이전 sold 기록
        if code != "?":
            url3 = f"{base}/auto_trades?code=eq.{code}&status=eq.sold&created_at=lt.{tr.get('created_at','')}&select=name,created_at&order=created_at.desc&limit=1"
            async with session.get(url3, headers=headers) as resp3:
                sold = await resp3.json()
            orig_date = sold[0]["created_at"][:19] if sold else "없음"
        else:
            orig_date = "?"

        print(f"{name:>14}({code}) sim={s['status']:<6} sim_only={sim_only_created} origSold={orig_date}")

    await close_session()


asyncio.run(main())
