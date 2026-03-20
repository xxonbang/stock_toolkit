import os
from dotenv import load_dotenv

load_dotenv()

# 외부 프로젝트 데이터 경로
THEME_DATA_PATH = os.getenv("THEME_ANALYSIS_DATA_PATH", "../theme_analysis/frontend/public/data")
SIGNAL_DATA_PATH = os.getenv("SIGNAL_ANALYSIS_DATA_PATH", "../signal_analysis/results")

# API Keys
KIS_APP_KEY = os.getenv("KIS_APP_KEY", "")
KIS_APP_SECRET = os.getenv("KIS_APP_SECRET", "")
KIS_ACCOUNT_NO = os.getenv("KIS_ACCOUNT_NO", "")

GEMINI_API_KEYS = [
    os.getenv(f"GEMINI_API_KEY_{i:02d}", "") for i in range(1, 6)
]
GEMINI_API_KEYS = [k for k in GEMINI_API_KEYS if k]

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

DART_API_KEY = os.getenv("DART_API_KEY", "")

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
