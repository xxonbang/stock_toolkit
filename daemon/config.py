import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

KIS_APP_KEY = os.getenv("KIS_APP_KEY", "")
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DATA_BASE_URL = os.getenv("DATA_BASE_URL", "https://xxonbang.github.io/stock_toolkit/data")

# KIS WebSocket
WS_URL_REAL = "ws://ops.koreainvestment.com:21000"
WS_URL_MOCK = "ws://ops.koreainvestment.com:31000"
WS_URL = os.getenv("KIS_WS_URL", WS_URL_REAL)

# 알림 임계값
ALERT_SURGE_LEVELS = [5.0, 10.0, 15.0]   # 급등 단계별 (%)
ALERT_DROP_LEVELS = [-3.0, -5.0]          # 급락 단계별 (%)
ALERT_VOLUME_RATIO = 3.0                  # 거래량 폭증 배수
ALERT_COOLDOWN_SEC = 300                  # 동일 종목 동일 이벤트 재알림 방지 (초)
