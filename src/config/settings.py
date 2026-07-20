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
AFFILIATE_ID: str           = os.getenv("AFFILIATE_ID", "MEU_ID_AFILIADO")
AMAZON_ASSOCIATE_TAG: str   = os.getenv("AMAZON_ASSOCIATE_TAG", "meutag-20")
ALIEXPRESS_APP_KEY: str      = os.getenv("ALIEXPRESS_APP_KEY", "")
ALIEXPRESS_SECRET_KEY: str   = os.getenv("ALIEXPRESS_SECRET_KEY", "")
ALIEXPRESS_TRACKING_ID: str  = os.getenv("ALIEXPRESS_TRACKING_ID", "")
# Merchant ID da Americanas no Awin Brasil (obtido no painel Awin → My Advertisers)
AMERICANAS_AWIN_MID: str      = os.getenv("AMERICANAS_AWIN_MID", "")

# ── Scraper ──────────────────────────────────────────────────────────────────
SCRAPE_INTERVAL_MINUTES: int  = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "5"))
MIN_DISCOUNT_PERCENT: int     = int(os.getenv("MIN_DISCOUNT_PERCENT", "15"))
MAX_DEALS_PER_RUN: int        = int(os.getenv("MAX_DEALS_PER_RUN", "20"))
# Máximo de navegadores Chromium simultâneos — 2 cabe em container de 1.5GB
PLAYWRIGHT_MAX_BROWSERS: int  = int(os.getenv("PLAYWRIGHT_MAX_BROWSERS", "2"))
# Proxy residencial/datacenter para evasão de bloqueios (ex: http://user:pass@host:port)
PROXY_URL: str                = os.getenv("PROXY_URL", "")

# ── Parcelamento ─────────────────────────────────────────────────────────────
# Quando o scraper não retornar dado real de parcelas, exibir estimativa calculada?
SHOW_ESTIMATED_INSTALLMENTS: bool = os.getenv("SHOW_ESTIMATED_INSTALLMENTS", "false").lower() == "true"

# ── Re-post ──────────────────────────────────────────────────────────────────
# Deals com desconto >= HIGH_DISCOUNT_PCT: repost a cada REPOST_HIGH_HOURS horas.
# Demais deals: repost a cada REPOST_LOW_HOURS horas.
HIGH_DISCOUNT_PCT: int     = int(os.getenv("HIGH_DISCOUNT_PCT", "50"))
REPOST_HIGH_HOURS: int     = int(os.getenv("REPOST_HIGH_HOURS", "24"))
REPOST_LOW_HOURS: int      = int(os.getenv("REPOST_LOW_HOURS", "48"))

# ── Rastreamento de cliques ───────────────────────────────────────────────────
# URL base do servidor de tracking (ex: https://achadinhosbr.com/r)
# Deixar vazio para desativar tracking (publishers usarão affiliate_url diretamente)
TRACKER_BASE_URL: str = os.getenv("TRACKER_BASE_URL", "").rstrip("/")

# ── Catálogo da API ──────────────────────────────────────────────────────────
# Por quanto tempo um produto continua no site após a última vez que um scraper
# o viu em promoção. Precisa ser bem maior que SCRAPE_INTERVAL_MINUTES: as páginas
# de ofertas rotacionam os itens, então um produto ainda em promoção pode faltar
# em alguns ciclos. Baixo demais = produto pisca no site; alto demais = oferta
# vencida fica no ar.
DEALS_ACTIVE_MINUTES: int = int(os.getenv("DEALS_ACTIVE_MINUTES", "180"))
# Origens permitidas no CORS (frontend). Só importa para chamadas feitas pelo
# NAVEGADOR — o site busca dados em Server Component, então quem chama a API é o
# servidor da Vercel. Manter restrito mesmo assim, por defesa em profundidade.
CORS_ORIGINS: list[str] = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()
]
# Segredo compartilhado com o frontend. Vazio = API aberta (modo desenvolvimento).
# Em produção, exposta na internet, isto é o que impede terceiros de consumirem
# o catálogo e os links de afiliado.
API_TOKEN: str = os.getenv("API_TOKEN", "")

# ── Backup ───────────────────────────────────────────────────────────────────
# O histórico de preços é acumulado ao longo de semanas e não se recompra.
BACKUP_DIR: Path      = BASE_DIR / os.getenv("BACKUP_DIR", "data/backups")
BACKUP_KEEP: int      = int(os.getenv("BACKUP_KEEP", "7"))
BACKUP_HOUR_UTC: int  = int(os.getenv("BACKUP_HOUR_UTC", "6"))  # 03h em Brasília

# ── Banco de dados ───────────────────────────────────────────────────────────
DATABASE_PATH: Path  = BASE_DIR / os.getenv("DATABASE_PATH", "data/deals.db")
DEDUP_TTL_DAYS: int  = int(os.getenv("DEDUP_TTL_DAYS", "7"))

# ── Logs ─────────────────────────────────────────────────────────────────────
LOG_LEVEL: str    = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: Path    = BASE_DIR / os.getenv("LOG_FILE", "logs/bot.log")
