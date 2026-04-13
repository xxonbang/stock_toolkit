#!/usr/bin/env python3
"""volume-rank 전체 경로 테스트"""
import asyncio, logging, sys, time
sys.path.insert(0, ".")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s", stream=sys.stdout)

async def main():
    from daemon.trader import _ensure_real_token, _fetch_volume_rank, _ensure_mock_token, fetch_available_balance

    t0 = time.time()
    mock = await _ensure_mock_token()
    t1 = time.time()
    ok = "OK" if mock else "FAIL"
    print(f"[1] mock token: {ok} ({t1-t0:.1f}s)")

    real = await _ensure_real_token()
    t2 = time.time()
    ok2 = "OK" if real else "FAIL"
    print(f"[2] real token: {ok2} ({t2-t1:.1f}s)")

    vr = await _fetch_volume_rank(mock)
    t3 = time.time()
    print(f"[3] volume-rank: {len(vr)} stocks ({t3-t2:.1f}s)")
    for v in vr[:5]:
        print(f"    {v['name']} rate={v['change_rate']:+.1f}% TV={v.get('acml_tr_pbmn',0)/1e8:.0f}억 open={v['open_price']} prev={v['prev_close']}")

    bal = await fetch_available_balance()
    t4 = time.time()
    print(f"[4] balance: {bal:,} ({t4-t3:.1f}s)")
    print(f"\nTotal: {t4-t0:.1f}s")

asyncio.run(main())
