"""api_credentials의 access_token 값 확인"""
import asyncio
import aiohttp
import json
import sys
sys.path.insert(0, ".")
from daemon.config import SUPABASE_URL, SUPABASE_SECRET_KEY


async def main():
    async with aiohttp.ClientSession() as s:
        url = f"{SUPABASE_URL}/rest/v1/api_credentials?service_name=eq.kis&credential_type=eq.access_token&select=credential_value"
        headers = {"apikey": SUPABASE_SECRET_KEY, "Authorization": f"Bearer {SUPABASE_SECRET_KEY}"}
        async with s.get(url, headers=headers) as resp:
            data = await resp.json()
            if not data:
                print("access_token 레코드 없음")
                return
            val = data[0].get("credential_value", "")
            print(f"credential_value 길이: {len(val)}")
            print(f"앞 80자: {val[:80]}")
            try:
                parsed = json.loads(val)
                print(f"JSON 파싱 성공, keys: {list(parsed.keys())}")
                has_token = "access_token" in parsed and bool(parsed["access_token"])
                print(f"access_token 키 존재: {has_token}")
                if has_token:
                    print(f"토큰 앞 20자: {parsed['access_token'][:20]}...")
            except Exception as e:
                print(f"JSON 파싱 실패: {e}")
                print(f"raw 값: {val[:200]}")


asyncio.run(main())
