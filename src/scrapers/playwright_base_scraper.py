from playwright.async_api import async_playwright, Page
from src.models import Deal
from src.scrapers.base_scraper import BaseScraper

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class PlaywrightBaseScraper(BaseScraper):
    """Base para scrapers que dependem de JavaScript no browser."""

    name = "playwright_base"

    async def fetch(self) -> list[Deal]:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page(user_agent=_USER_AGENT)
                return await self._scrape(page)
            finally:
                await browser.close()

    async def _scrape(self, page: Page) -> list[Deal]:
        raise NotImplementedError
