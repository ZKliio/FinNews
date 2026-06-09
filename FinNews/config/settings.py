import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
NEWSAPI_API_KEY = os.getenv("NEWSAPI_API_KEY", "")
EODHD_API_KEY = os.getenv("EODHD_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
APIFY_API_KEY = os.getenv("APIFY_API_KEY", "")
SCWEET_AUTH_TOKEN = os.getenv("SCWEET_AUTH_TOKEN", "")

# --- Delivery ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

DELIVERY_EMAIL_ENABLED = os.getenv("DELIVERY_EMAIL_ENABLED", "false").lower() == "true"
DELIVERY_EMAIL_TO = os.getenv("DELIVERY_EMAIL_TO", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

# --- Scoring Weights ---
CONTENT_WEIGHT = float(os.getenv("CONTENT_WEIGHT", "0.40"))
VELOCITY_WEIGHT = float(os.getenv("VELOCITY_WEIGHT", "0.30"))
MARKET_WEIGHT = float(os.getenv("MARKET_WEIGHT", "0.30"))

# --- Trigger Thresholds ---
TRIGGER_IMMEDIATE = float(os.getenv("TRIGGER_IMMEDIATE", "0.80"))
TRIGGER_BATCH = float(os.getenv("TRIGGER_BATCH", "0.60"))
TRIGGER_WATCH = float(os.getenv("TRIGGER_WATCH", "0.45"))

# --- Cooldown ---
NEWSLETTER_COOLDOWN_MINUTES = int(os.getenv("NEWSLETTER_COOLDOWN_MINUTES", "15"))
BATCH_INTERVAL_MINUTES = int(os.getenv("BATCH_INTERVAL_MINUTES", "30"))

# --- Database ---
DB_PATH = os.getenv("DB_PATH", "fintwit.db")

# --- Dashboard ---
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8080"))
