"""KIS WebSocket 클라이언트 — 체결가/호가 실시간 수신"""
import asyncio
import json
import logging
import time
import aiohttp
import websockets
from daemon.config import KIS_APP_KEY, KIS_APP_SECRET, WS_URL

logger = logging.getLogger("daemon.ws")

IDX_CODE = 0
IDX_TIME = 2
IDX_PRICE = 3
IDX_SIGN = 4
IDX_CHANGE = 5
IDX_CHANGE_RATE = 8
IDX_TICK_VOLUME = 11
IDX_VOLUME = 12
IDX_TRADE_AMOUNT = 13


def parse_stock_execution(data_str: str) -> dict | None:
    if not data_str:
        return None
    fields = data_str.split("^")
    if len(fields) < 14:
        return None
    try:
        return {
            "code": fields[IDX_CODE],
            "time": fields[IDX_TIME],
            "price": int(fields[IDX_PRICE]),
            "change_sign": fields[IDX_SIGN],
            "change": int(fields[IDX_CHANGE]),
            "change_rate": float(fields[IDX_CHANGE_RATE]),
            "tick_volume": int(fields[IDX_TICK_VOLUME]),
            "volume": int(fields[IDX_VOLUME]),
            "trade_amount": int(fields[IDX_TRADE_AMOUNT]),
        }
    except (ValueError, IndexError):
        return None


async def get_approval_key() -> str | None:
    url = "https://openapi.koreainvestment.com:9443/oauth2/Approval"
    body = {
        "grant_type": "client_credentials",
        "appkey": KIS_APP_KEY,
        "secretkey": KIS_APP_SECRET,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("approval_key")
    except Exception as e:
        logger.error(f"approval_key 발급 실패: {e}")
    return None


def build_subscribe_message(approval_key: str, tr_id: str, stock_code: str, subscribe: bool = True) -> str:
    return json.dumps({
        "header": {
            "approval_key": approval_key,
            "custtype": "P",
            "tr_type": "1" if subscribe else "2",
            "content-type": "utf-8",
        },
        "body": {
            "input": {
                "tr_id": tr_id,
                "tr_key": stock_code,
            }
        }
    })


class KISWebSocketClient:
    def __init__(self, on_execution=None):
        self._on_execution = on_execution
        self._ws = None
        self._approval_key = None
        self._subscribed_codes: set[str] = set()
        self._running = False

    async def connect(self):
        self._running = True
        retry_count = 0
        max_retries = 5

        while self._running and retry_count < max_retries:
            self._approval_key = await get_approval_key()
            if not self._approval_key:
                logger.error("approval_key 없음 — 2초 후 재시도")
                retry_count += 1
                await asyncio.sleep(2)
                continue

            try:
                async with websockets.connect(WS_URL, ping_interval=None) as ws:
                    self._ws = ws
                    retry_count = 0
                    logger.info(f"KIS WebSocket 연결 성공: {WS_URL}")

                    for code in list(self._subscribed_codes):
                        await ws.send(build_subscribe_message(
                            self._approval_key, "H0STCNT0", code, True
                        ))

                    async for raw_msg in ws:
                        await self._handle_message(raw_msg)

            except Exception as e:
                retry_count += 1
                logger.warning(f"WebSocket 끊김 ({retry_count}/{max_retries}): {e}")
                if self._running and retry_count < max_retries:
                    await asyncio.sleep(2)

        logger.info("WebSocket 클라이언트 종료")

    async def _handle_message(self, raw_msg: str):
        if "PINGPONG" in raw_msg:
            if self._ws:
                await self._ws.send(raw_msg)
            return

        if raw_msg.startswith("{"):
            return

        parts = raw_msg.split("|", 3)
        if len(parts) < 4:
            return

        tr_id = parts[1]
        data_str = parts[3]

        if tr_id == "H0STCNT0" and self._on_execution:
            parsed = parse_stock_execution(data_str)
            if parsed:
                await self._on_execution(parsed)

    async def subscribe(self, stock_code: str):
        self._subscribed_codes.add(stock_code)
        if self._ws and self._approval_key:
            await self._ws.send(build_subscribe_message(
                self._approval_key, "H0STCNT0", stock_code, True
            ))
            logger.info(f"구독 추가: {stock_code} (총 {len(self._subscribed_codes)}개)")

    async def unsubscribe(self, stock_code: str):
        self._subscribed_codes.discard(stock_code)
        if self._ws and self._approval_key:
            await self._ws.send(build_subscribe_message(
                self._approval_key, "H0STCNT0", stock_code, False
            ))

    async def update_subscriptions(self, new_codes: set[str]):
        to_remove = self._subscribed_codes - new_codes
        to_add = new_codes - self._subscribed_codes
        for code in to_remove:
            await self.unsubscribe(code)
        for code in to_add:
            await self.subscribe(code)

    def stop(self):
        self._running = False

    @property
    def subscribed_count(self) -> int:
        return len(self._subscribed_codes)
