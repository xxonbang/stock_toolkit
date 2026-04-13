#!/usr/bin/env python3
"""수동 매수 트리거 — run_tv_scan_and_buy() 1회 실행"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    from daemon.trader import run_tv_scan_and_buy
    print("=== 수동 거래대금 매수 트리거 ===")
    count = await run_tv_scan_and_buy()
    print(f"매수 완료: {count}종목")

if __name__ == "__main__":
    asyncio.run(main())
