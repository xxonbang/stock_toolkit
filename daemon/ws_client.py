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


def parse_asking_price(data_str: str) -> dict | None:
    """H0STASP0 호가 데이터 문자열을 파싱"""
    if not data_str:
        return None
    fields = data_str.split("^")
    if len(fields) < 25:
        return None
    try:
        # H0STASP0 필드: 0=종목코드, 3~7=매도호가1~5, 13~17=매수호가1~5,
        # 23~27=매도잔량1~5, 33~37=매수잔량1~5, 43=총매도잔량, 44=총매수잔량
        code = fields[0]
        ask_prices = []
        bid_prices = []
        ask_qtys = []
        bid_qtys = []
        for i in range(5):
            ask_prices.append(int(fields[3 + i]) if fields[3 + i] else 0)
            bid_prices.append(int(fields[13 + i]) if fields[13 + i] else 0)
            ask_qtys.append(int(fields[23 + i]) if fields[23 + i] else 0)
            bid_qtys.append(int(fields[33 + i]) if fields[33 + i] else 0)
        total_ask = int(fields[43]) if len(fields) > 43 and fields[43] else sum(ask_qtys)
        total_bid = int(fields[44]) if len(fields) > 44 and fields[44] else sum(bid_qtys)
        return {
            "code": code,
            "ask_prices": ask_prices,
            "bid_prices": bid_prices,
            "ask_qtys": ask_qtys,
            "bid_qtys": bid_qtys,
            "total_ask": total_ask,
            "total_bid": total_bid,
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
    def __init__(self, on_execution=None, on_asking_price=None):
        self._on_execution = on_execution
        self._on_asking_price = on_asking_price
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
                        await ws.send(build_subscribe_message(
                            self._approval_key, "H0STASP0", code, True
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
        elif tr_id == "H0STASP0" and self._on_asking_price:
            parsed = parse_asking_price(data_str)
            if parsed:
                await self._on_asking_price(parsed)

    async def subscribe(self, stock_code: str):
        self._subscribed_codes.add(stock_code)
        if self._ws and self._approval_key:
            await self._ws.send(build_subscribe_message(
                self._approval_key, "H0STCNT0", stock_code, True
            ))
            await self._ws.send(build_subscribe_message(
                self._approval_key, "H0STASP0", stock_code, True
            ))
            logger.info(f"구독 추가: {stock_code} (총 {len(self._subscribed_codes)}종목, {len(self._subscribed_codes) * 2}슬롯)")

    async def unsubscribe(self, stock_code: str):
        self._subscribed_codes.discard(stock_code)
        if self._ws and self._approval_key:
            await self._ws.send(build_subscribe_message(
                self._approval_key, "H0STCNT0", stock_code, False
            ))
            await self._ws.send(build_subscribe_message(
                self._approval_key, "H0STASP0", stock_code, False
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
