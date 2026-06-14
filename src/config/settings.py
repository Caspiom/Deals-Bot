from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Telegram
TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHANNEL_ID: str = os.environ["TELEGRAM_CHANNEL_ID"]

# Afiliados
AFFILIATE_ID: str = os.getenv("AFFILIATE_ID", "MEU_ID_AFILIADO")
AMAZON_ASSOCIATE_TAG: str = os.getenv("AMAZON_ASSOCIATE_TAG", "meutag-20")

# Scraper
SCRAPE_INTERVAL_MINUTES: int = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "5"))
MIN_DISCOUNT_PERCENT: int = int(os.getenv("MIN_DISCOUNT_PERCENT", "15"))
MAX_DEALS_PER_RUN: int = int(os.getenv("MAX_DEALS_PER_RUN", "5"))

# Banco de dados
DATABASE_PATH: Path = BASE_DIR / os.getenv("DATABASE_PATH", "data/deals.db")

DEDUP_TTL_DAYS: int = int(os.getenv("DEDUP_TTL_DAYS", "7"))

# Logs
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: Path = BASE_DIR / os.getenv("LOG_FILE", "logs/bot.log")
