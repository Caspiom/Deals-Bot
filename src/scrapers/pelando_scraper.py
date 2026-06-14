import re
from playwright.async_api import Page
from loguru import logger
from src.config.settings import MIN_DISCOUNT_PERCENT, MAX_DEALS_PER_RUN
from src.models import Deal
from src.scrapers.playwright_base_scraper import PlaywrightBaseScraper

_BASE_URL = "https://www.pelando.com.br"
_FEED_URL = f"{_BASE_URL}"

# JS que extrai todos os dados de cada card em uma única chamada ao browser
_EXTRACT_JS = """() => {
    const links = document.querySelectorAll('a[data-deal-id]');
    return Array.from(links).map(a => {
        const root = a.closest('[class*="deal"]') || a.parentElement?.parentElement?.parentElement;
        const img   = root?.querySelector('img[class*="deal-card-image"]');
        const price = root?.querySelector('[class*="deal-card-stamp"]');
        const temp  = root?.querySelector('[class*="deal-card-temperature"] span');
        return {
            title:      a.innerText.trim(),
            url:        a.href,
            deal_id:    a.dataset.dealId,
            price_text: price?.innerText ?? null,
            image:      img?.src ?? null,
            temp:       temp?.innerText ?? null,
        };
    });
}"""


def _parse_brl(text: str) -> float | None:
    cleaned = re.sub(r"[R$\s\n]", "", text).replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_pct_from_title(title: str) -> int | None:
    m = re.search(r"(\d{1,3})\s*%?\s*(?:de\s+)?(?:desconto|off)", title, re.IGNORECASE)
    return int(m.group(1)) if m else None


class PelandoScraper(PlaywrightBaseScraper):
    name = "pelando"

    async def _scrape(self, page: Page) -> list[Deal]:
        await page.goto(_FEED_URL, wait_until="networkidle", timeout=30000)

        # scroll para carregar mais cards via lazy loading
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(800)

        raw: list[dict] = await page.evaluate(_EXTRACT_JS)
        logger.info("Pelando: {} cards extraídos do DOM.", len(raw))

        deals: list[Deal] = []
        seen_ids: set[str] = set()

        for item in raw:
            deal_id = item.get("deal_id") or ""
            if deal_id in seen_ids or not deal_id:
                continue
            seen_ids.add(deal_id)

            title = item.get("title", "").strip()
            url   = item.get("url", "")
            if not title or not url:
                continue

            price = _parse_brl(item["price_text"]) if item.get("price_text") else None
            if price is None:
                continue

            discount_pct = _extract_pct_from_title(title)

            # inclui o deal se tiver desconto explícito >= mínimo, ou se
            # não for possível calcular (confia na curadoria da comunidade)
            if discount_pct is not None and discount_pct < MIN_DISCOUNT_PERCENT:
                continue

            deals.append(Deal(
                title=title,
                url=url,
                price=price,
                old_price=None,
                discount_pct=discount_pct,
                image_url=item.get("image"),
                source=self.name,
            ))

            if len(deals) >= MAX_DEALS_PER_RUN:
                break

        logger.info("Pelando: {} deals válidos após filtros.", len(deals))
        return deals
