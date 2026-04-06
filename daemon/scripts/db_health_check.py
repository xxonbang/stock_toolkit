"""DB 데이터 정합성 검증 스크립트"""
import asyncio
import sys
sys.path.insert(0, ".")


async def main():
    from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY
    from daemon.http_session import get_session, close_session
    session = await get_session()
    headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}
    base = SUPABASE_URL + "/rest/v1"

    # 1. auto_trades 상태별 카운트
    print("=== auto_trades 상태별 카운트 ===")
    for status in ["pending", "filled", "sold", "sell_requested", "sim_only"]:
        url = f"{base}/auto_trades?status=eq.{status}&select=id"
        h = {**headers, "Prefer": "count=exact"}
        async with session.get(url, headers=h) as resp:
            count = resp.headers.get("content-range", "0").split("/")[-1]
            print(f"  {status}: {count}건")

    # 2. sold + sell_price=NULL
    url = f"{base}/auto_trades?status=eq.sold&sell_price=is.null&select=id,code,name,sold_at"
    async with session.get(url, headers=headers) as resp:
        data = await resp.json()
        print(f"\n=== sold + sell_price=NULL: {len(data)}건 ===")
        for d in data[:5]:
            print(f"  {d.get('name','?')}({d.get('code','?')}) sold_at={d.get('sold_at','?')}")

    # 3. sold + pnl_pct=NULL
    url = f"{base}/auto_trades?status=eq.sold&pnl_pct=is.null&select=id,code,name"
    async with session.get(url, headers=headers) as resp:
        data = await resp.json()
        print(f"sold + pnl_pct=NULL: {len(data)}건")

    # 4. filled + filled_price=NULL
    url = f"{base}/auto_trades?status=eq.filled&filled_price=is.null&select=id,code,name"
    async with session.get(url, headers=headers) as resp:
        data = await resp.json()
        print(f"filled + filled_price=NULL: {len(data)}건")

    # 5. open sims orphan 체크
    url = f"{base}/strategy_simulations?status=eq.open&select=id,trade_id,strategy_type"
    async with session.get(url, headers=headers) as resp:
        sims = await resp.json()
    orphans = []
    if sims:
        trade_ids = list(set(s["trade_id"] for s in sims if s.get("trade_id")))
        for tid in trade_ids:
            url2 = f"{base}/auto_trades?id=eq.{tid}&select=id"
            async with session.get(url2, headers=headers) as resp2:
                trades = await resp2.json()
                if not trades:
                    orphans.append(tid)
    print(f"\n=== open sims: {len(sims)}건, orphan: {len(orphans)}건 ===")

    # 6. pending/sell_requested 잔류
    url = f"{base}/auto_trades?status=in.(pending,sell_requested)&select=id,code,name,status,created_at"
    async with session.get(url, headers=headers) as resp:
        data = await resp.json()
        print(f"\n=== pending/sell_requested 잔류: {len(data)}건 ===")
        for d in data:
            print(f"  {d.get('name','?')}({d.get('code','?')}) {d['status']} {d.get('created_at','?')}")

    # 7. sim_only orphan
    url = f"{base}/auto_trades?status=eq.sim_only&select=id,code,name"
    async with session.get(url, headers=headers) as resp:
        sim_onlys = await resp.json()
    orphan_so = []
    if sim_onlys:
        for so in sim_onlys:
            url2 = f"{base}/strategy_simulations?trade_id=eq.{so['id']}&select=id"
            async with session.get(url2, headers=headers) as resp2:
                linked = await resp2.json()
                if not linked:
                    orphan_so.append(so)
    print(f"\n=== sim_only: {len(sim_onlys)}건, orphan(sim 미연결): {len(orphan_so)}건 ===")
    for o in orphan_so[:5]:
        print(f"  orphan: {o.get('name','?')}({o.get('code','?')})")

    # 8. sold인데 sell_price < filled_price * 0.7 (비정상 큰 손실)
    url = f"{base}/auto_trades?status=eq.sold&select=id,code,name,filled_price,sell_price,pnl_pct"
    async with session.get(url, headers=headers) as resp:
        sold = await resp.json()
    anomalies = []
    for s in sold:
        fp = s.get("filled_price", 0) or 0
        sp = s.get("sell_price", 0) or 0
        pnl = s.get("pnl_pct", 0) or 0
        if fp > 0 and sp > 0:
            calc_pnl = (sp - fp) / fp * 100
            if abs(calc_pnl - pnl) > 1:  # pnl_pct와 실제 계산 1%p 이상 차이
                anomalies.append({"name": s.get("name"), "code": s.get("code"), "fp": fp, "sp": sp, "db_pnl": pnl, "calc_pnl": round(calc_pnl, 2)})
    print(f"\n=== pnl_pct vs (sell-buy)/buy 불일치(>1%p): {len(anomalies)}건 ===")
    for a in anomalies[:5]:
        print(f"  {a['name']}({a['code']}) buy={a['fp']} sell={a['sp']} db_pnl={a['db_pnl']}% calc={a['calc_pnl']}%")

    await close_session()


asyncio.run(main())
