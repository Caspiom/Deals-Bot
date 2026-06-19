import asyncio
import random

from loguru import logger
from playwright.async_api import async_playwright, Page
from playwright_stealth import Stealth

from src.config.settings import PLAYWRIGHT_MAX_BROWSERS, PROXY_URL
from src.models import Deal
from src.scrapers.base_scraper import BaseScraper

# ── User-Agent rotation ───────────────────────────────────────────────────────
# Lista própria de desktop UAs recentes — fake-useragent 2.x retorna mobile UAs
# quando requisitado sem filtro confiável de plataforma.
# Restrito a Chrome/Windows para maximizar consistência com sec-ch-ua injetado pelo stealth.

_DESKTOP_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
]


def _random_ua() -> str:
    return random.choice(_DESKTOP_UAS)


# ── Stealth singleton ─────────────────────────────────────────────────────────
# Configurado para simular Chrome/Windows com locale BR — cobre webdriver, plugins,
# languages, chrome.runtime, WebGL, sec-ch-ua e demais fingerprints detectados por
# Cloudflare/Akamai/PerimeterX.
_STEALTH = Stealth(
    navigator_languages_override=("pt-BR", "pt"),
    navigator_platform_override="Win32",
)

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
                    ua = _random_ua()
                    ctx = await browser.new_context(
                        user_agent=ua,
                        viewport={"width": 1366, "height": 768},
                        locale="pt-BR",
                        timezone_id="America/Sao_Paulo",
                        extra_http_headers={
                            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                        },
                    )
                    page = await ctx.new_page()
                    await _STEALTH.apply_stealth_async(page)
                    logger.debug("{}: browser iniciado (UA: {}...)", self.name, ua[:40])
                    return await self._scrape(page)
                finally:
                    await browser.close()

    async def _scrape(self, page: Page) -> list[Deal]:
        raise NotImplementedError
