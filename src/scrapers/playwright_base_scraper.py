import asyncio
import random

from loguru import logger
from playwright.async_api import async_playwright, Page

from src.config.settings import PLAYWRIGHT_MAX_BROWSERS, PROXY_URL
from src.models import Deal
from src.scrapers.base_scraper import BaseScraper

# ── User-Agent rotation ───────────────────────────────────────────────────────

try:
    from fake_useragent import UserAgent as _UALib
    _ua_pool = _UALib(browsers=["chrome", "firefox"], platforms=["desktop"])

    def _random_ua() -> str:
        return _ua_pool.random
except Exception:
    _FALLBACK_UAS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    ]

    def _random_ua() -> str:
        return random.choice(_FALLBACK_UAS)


# ── Anti-detecção ─────────────────────────────────────────────────────────────

_STEALTH_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US'] });
    window.chrome = { runtime: {} };
"""

# ── Semáforo global ───────────────────────────────────────────────────────────
# Criado lazy para garantir que existe um event loop no momento da primeira aquisição.
# PLAYWRIGHT_MAX_BROWSERS=2 mantém o consumo de RAM dentro de ~1.2GB em container 1.5GB.
_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(PLAYWRIGHT_MAX_BROWSERS)
    return _semaphore


class PlaywrightBaseScraper(BaseScraper):
    """Base para scrapers que dependem de JavaScript no browser headless."""

    name = "playwright_base"

    async def fetch(self) -> list[Deal]:
        async with _get_semaphore():
            async with async_playwright() as pw:
                launch_kwargs: dict = {
                    "headless": True,
                    "args": [
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                    ],
                }
                if PROXY_URL:
                    launch_kwargs["proxy"] = {"server": PROXY_URL}

                browser = await pw.chromium.launch(**launch_kwargs)
                try:
                    ctx = await browser.new_context(
                        user_agent=_random_ua(),
                        viewport={"width": 1366, "height": 768},
                        locale="pt-BR",
                        timezone_id="America/Sao_Paulo",
                        extra_http_headers={
                            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                        },
                    )
                    await ctx.add_init_script(_STEALTH_SCRIPT)
                    page = await ctx.new_page()
                    logger.debug("{}: browser iniciado (UA: {}...)", self.name, _random_ua()[:40])
                    return await self._scrape(page)
                finally:
                    await browser.close()

    async def _scrape(self, page: Page) -> list[Deal]:
        raise NotImplementedError
