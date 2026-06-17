import httpx
from loguru import logger
from src.config.settings import MIN_DISCOUNT_PERCENT, PROXY_URL
from src.models import Deal
from src.scrapers.base_scraper import BaseScraper
from src.services.installment_calculator import parse_installment_string
from src.utils.retry import scraper_retry

_API_URL = "https://servicespub.prod.api.aws.grupokabum.com.br/catalog/v2/products"
_PRODUCT_BASE = "https://www.kabum.com.br/produto"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Origin": "https://www.kabum.com.br",
    "Referer": "https://www.kabum.com.br/",
    "Accept": "application/json",
}


class KabumScraper(BaseScraper):
    name = "kabum"

    @scraper_retry
    async def fetch(self) -> list[Deal]:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=15, proxy=PROXY_URL or None) as client:
            resp = await client.get(
                _API_URL,
                params={
                    "page_number": 1,
                    "page_size": "100",
                    "sort": "most_discount_percentage",
                    "is_offer": "true",
                },
            )
            resp.raise_for_status()
            items = resp.json().get("data", [])

        logger.info("KaBuM: {} produtos recebidos.", len(items))

        seen_ids: set[int] = set()
        deals: list[Deal] = []

        for item in items:
            try:
                attr = item.get("attributes", {})
                product_id = int(item.get("id") or 0)
                if not product_id or product_id in seen_ids:
                    continue
                seen_ids.add(product_id)

                price          = float(attr.get("price_with_discount") or 0)
                original_price = float(attr.get("price") or 0)
                discount_pct   = int(attr.get("discount_percentage") or 0)

                if price <= 0:
                    continue

                if discount_pct == 0 and original_price > price:
                    discount_pct = int((1 - price / original_price) * 100)

                logger.info(
                    "KaBuM [dump] {} | '{}' | preço: {:.2f} | old: {:.2f} | desc: {}%",
                    product_id,
                    (attr.get("title") or "")[:45],
                    price, original_price, discount_pct,
                )

                if discount_pct < MIN_DISCOUNT_PERCENT:
                    logger.info("KaBuM [dump] {} → DROP: desconto {}% < mínimo {}%", product_id, discount_pct, MIN_DISCOUNT_PERCENT)
                    continue

                if not attr.get("available", True):
                    continue

                slug = attr.get("product_link", "")
                url = f"{_PRODUCT_BASE}/{product_id}/{slug}"

                image_url = None
                try:
                    photos = attr.get("photos", {})
                    for size in ("m", "g", "p"):
                        imgs = photos.get(size)
                        if imgs and isinstance(imgs, list) and imgs[0]:
                            image_url = imgs[0]
                            break
                except Exception:
                    pass

                n_inst, v_inst = None, None
                try:
                    installment_raw = attr.get("max_installment") or ""
                    parsed = parse_installment_string(installment_raw) if installment_raw else None
                    n_inst, v_inst = parsed if parsed else (None, None)
                except Exception:
                    pass

                deals.append(Deal(
                    title=attr.get("title", "").strip(),
                    url=url,
                    price=price,
                    old_price=original_price if original_price > price else None,
                    discount_pct=discount_pct,
                    image_url=image_url,
                    source=self.name,
                    store="KaBuM",
                    installments=n_inst,
                    installment_value=v_inst,
                ))

            except Exception as exc:
                logger.warning(
                    "KaBuM: erro ao processar item id={}: {}",
                    item.get("id", "?"), exc,
                )
                continue

        logger.info("KaBuM: {} deals válidos após filtros.", len(deals))
        return deals
