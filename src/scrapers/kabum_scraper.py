import asyncio
import httpx
from loguru import logger
from src.config.settings import MIN_DISCOUNT_PERCENT, MAX_DEALS_PER_RUN
from src.models import Deal
from src.scrapers.base_scraper import BaseScraper

_API_BASE = "https://servicespub.prod.api.aws.grupokabum.com.br/catalog/v2/products-by-category"
_PRODUCT_BASE = "https://www.kabum.com.br/produto"
_CATEGORIES = ["hardware", "perifericos", "computadores"]
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Origin": "https://www.kabum.com.br",
    "Referer": "https://www.kabum.com.br/",
}


class KabumScraper(BaseScraper):
    name = "kabum"

    async def fetch(self) -> list[Deal]:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=15) as client:
            results = await asyncio.gather(
                *[self._fetch_category(client, cat) for cat in _CATEGORIES],
                return_exceptions=True,
            )

        seen_ids: set[int] = set()
        deals: list[Deal] = []

        for cat, result in zip(_CATEGORIES, results):
            if isinstance(result, Exception):
                logger.error("KaBuM categoria '{}' falhou: {}", cat, result)
                continue
            for product_id, deal in result:
                if product_id in seen_ids:
                    continue
                seen_ids.add(product_id)
                deals.append(deal)
                if len(deals) >= MAX_DEALS_PER_RUN:
                    logger.info("KaBuM: {} deals válidos após filtros.", len(deals))
                    return deals

        logger.info("KaBuM: {} deals válidos após filtros.", len(deals))
        return deals

    async def _fetch_category(self, client: httpx.AsyncClient, category: str) -> list[tuple[int, Deal]]:
        resp = await client.get(
            f"{_API_BASE}/{category}",
            params={
                "page_number": 1,
                "page_size": MAX_DEALS_PER_RUN * 3,
                "sort": "most_discount_percentage",
                "is_offer": 1,
            },
        )
        resp.raise_for_status()
        items = resp.json().get("data", [])
        logger.info("KaBuM/{}: {} produtos recebidos.", category, len(items))

        results: list[tuple[int, Deal]] = []
        for item in items:
            attr = item.get("attributes", {})
            product_id = int(item.get("id") or 0)
            if not product_id:
                continue

            price = float(attr.get("price_with_discount") or 0)
            original_price = float(attr.get("price") or 0)
            discount_pct = int(attr.get("discount_percentage") or 0)

            if price <= 0:
                continue

            if discount_pct == 0 and original_price > price:
                discount_pct = int((1 - price / original_price) * 100)

            if discount_pct < MIN_DISCOUNT_PERCENT:
                continue

            if not attr.get("available", True):
                continue

            slug = attr.get("product_link", "")
            url = f"{_PRODUCT_BASE}/{product_id}/{slug}"

            photos = attr.get("photos", {})
            image_url = None
            for size in ("m", "g", "p"):
                imgs = photos.get(size)
                if imgs and isinstance(imgs, list) and imgs[0]:
                    image_url = imgs[0]
                    break

            results.append((product_id, Deal(
                title=attr.get("title", "").strip(),
                url=url,
                price=price,
                old_price=original_price if original_price > price else None,
                discount_pct=discount_pct,
                image_url=image_url,
                source=self.name,
                store="KaBuM",
            )))

        return results
