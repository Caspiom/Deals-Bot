from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── Publishers ativos ────────────────────────────────────────────────────────
ENABLED_PUBLISHERS: list[str] = [
    p.strip().lower()
    for p in os.getenv("ENABLED_PUBLISHERS", "telegram").split(",")
    if p.strip()
]

# ── Telegram ─────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL_ID: str = os.environ["TELEGRAM_CHANNEL_ID"]

# ── X (Twitter) ──────────────────────────────────────────────────────────────
X_API_KEY: str        = os.getenv("X_API_KEY", "")
X_API_SECRET: str     = os.getenv("X_API_SECRET", "")
X_ACCESS_TOKEN: str   = os.getenv("X_ACCESS_TOKEN", "")
X_ACCESS_SECRET: str  = os.getenv("X_ACCESS_SECRET", "")

# ── Instagram ────────────────────────────────────────────────────────────────
INSTAGRAM_ACCESS_TOKEN: str = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_USER_ID: str      = os.getenv("INSTAGRAM_USER_ID", "")

# ── Discord ───────────────────────────────────────────────────────────────────
DISCORD_BOT_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")

# ── Afiliados ────────────────────────────────────────────────────────────────
AFFILIATE_ID: str         = os.getenv("AFFILIATE_ID", "MEU_ID_AFILIADO")
AMAZON_ASSOCIATE_TAG: str = os.getenv("AMAZON_ASSOCIATE_TAG", "meutag-20")

# ── Scraper ──────────────────────────────────────────────────────────────────
SCRAPE_INTERVAL_MINUTES: int = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "5"))
MIN_DISCOUNT_PERCENT: int    = int(os.getenv("MIN_DISCOUNT_PERCENT", "15"))
MAX_DEALS_PER_RUN: int       = int(os.getenv("MAX_DEALS_PER_RUN", "5"))

# ── Re-post de promos quentes ─────────────────────────────────────────────────
# Deals com desconto >= MIN_HOT_DISCOUNT_PCT são re-postados se o último post
# foi há pelo menos REPOST_INTERVAL_HOURS horas.
# Deals com desconto >= HIGH_DISCOUNT_PCT usam intervalo maior (HIGH_DISCOUNT_REPOST_HOURS).
MIN_HOT_DISCOUNT_PCT: int        = int(os.getenv("MIN_HOT_DISCOUNT_PCT", "40"))
REPOST_INTERVAL_HOURS: int       = int(os.getenv("REPOST_INTERVAL_HOURS", "2"))
HIGH_DISCOUNT_PCT: int           = int(os.getenv("HIGH_DISCOUNT_PCT", "50"))
HIGH_DISCOUNT_REPOST_HOURS: int  = int(os.getenv("HIGH_DISCOUNT_REPOST_HOURS", "12"))

# ── Banco de dados ───────────────────────────────────────────────────────────
DATABASE_PATH: Path  = BASE_DIR / os.getenv("DATABASE_PATH", "data/deals.db")
DEDUP_TTL_DAYS: int  = int(os.getenv("DEDUP_TTL_DAYS", "7"))

# ── Logs ─────────────────────────────────────────────────────────────────────
LOG_LEVEL: str    = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: Path    = BASE_DIR / os.getenv("LOG_FILE", "logs/bot.log")
