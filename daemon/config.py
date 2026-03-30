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

# 호가 관련 임계값
ALERT_WALL_RATIO = 5.0                    # 호가 벽 판정: 특정 호가 잔량 ≥ 평균의 N배
ALERT_SUPPLY_REVERSAL_THRESHOLD = 0.3     # 수급 반전: 매수비율 변동 ≥ 30%p
MAX_SUBSCRIPTION_STOCKS = 20              # 최대 구독 종목 수 (체결가+호가 = 종목당 2슬롯)

# 자동매매 설정
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "xxonbang/theme-analyzer")
GITHUB_WORKFLOW = os.getenv("GITHUB_WORKFLOW", "daily-theme-analysis.yml")

# signal-pulse 감시
SIGNAL_PULSE_REPO = "xxonbang/signal-pulse"
SIGNAL_PULSE_WORKFLOW = "analyze.yml"

# deploy-pages 트리거
DEPLOY_REPO = "xxonbang/stock_toolkit"
DEPLOY_WORKFLOW = "deploy-pages.yml"

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "")

KIS_MOCK_ACCOUNT_NO = os.getenv("KIS_MOCK_ACCOUNT_NO", "")
KIS_MOCK_APP_KEY = os.getenv("KIS_MOCK_APP_KEY", KIS_APP_KEY)
KIS_MOCK_APP_SECRET = os.getenv("KIS_MOCK_APP_SECRET", KIS_APP_SECRET)
KIS_MOCK_BASE_URL = "https://openapivts.koreainvestment.com:29443"

TRADE_MIN_AMOUNT_PER_STOCK = 1_000_000  # 종목당 최소 투자금 (원)
TRADE_TAKE_PROFIT_PCT = 7.0             # 익절 기준 (%) — 백테스트 최적 균형 조합
TRADE_STOP_LOSS_PCT = -2.0           # 손절 기준 (%) — 백테스트 최적
TRADE_TRAILING_STOP_PCT = -3.0       # 급락 손절 (%, 고점 대비 낙폭) — 백테스트 최적
TRADE_FLASH_SPIKE_PCT = 15.0         # flash spike 필터 (%, 이전 peak 대비 초과 점프 무시)


def validate_required_env():
    """필수 환경변수 검증 — daemon 시작 시 호출"""
    required = {
        "KIS_MOCK_APP_KEY": KIS_MOCK_APP_KEY,
        "KIS_MOCK_APP_SECRET": KIS_MOCK_APP_SECRET,
        "KIS_MOCK_ACCOUNT_NO": KIS_MOCK_ACCOUNT_NO,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_SECRET_KEY": SUPABASE_SECRET_KEY,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(f"필수 환경변수 누락: {', '.join(missing)}")
