import httpx
from loguru import logger
from src.config.settings import MIN_DISCOUNT_PERCENT, AMERICANAS_MAX_DISCOUNT_PCT, PROXY_URL
from src.models import Deal
from src.scrapers.base_scraper import BaseScraper
from src.utils.retry import scraper_retry

# VTEX Catalog API pública — sem autenticação, sem browser
_API_URL = "https://www.americanas.com.br/api/catalog_system/pub/products/search/"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.americanas.com.br/",
}


def _best_installment(installments: list[dict]) -> tuple[int, float] | None:
    interest_free = [i for i in installments if not i.get("hasInterestRate", True)]
    if not interest_free:
        return None
    best = max(interest_free, key=lambda i: i.get("NumberOfInstallments", 0))
    n = best.get("NumberOfInstallments")
    v = best.get("Value")
    if n and v:
        return int(n), float(v)
    return None


class AmericanasScraper(BaseScraper):
    name = "americanas"

    @scraper_retry
    async def fetch(self) -> list[Deal]:
        params = {
            "O": "OrderByBestDiscountDESC",
            "_from": "0",
            "_to": "49",
        }
        async with httpx.AsyncClient(headers=_HEADERS, proxy=PROXY_URL or None, timeout=20) as client:
            resp = await client.get(_API_URL, params=params)
            resp.raise_for_status()
            data: list[dict] = resp.json()

        logger.info("Americanas: {} produtos retornados pela API.", len(data))

        seen_ids: set[str] = set()
        deals: list[Deal] = []

        for product in data:
            try:
                pid = str(product.get("productId", ""))
                if not pid or pid in seen_ids:
                    continue
                seen_ids.add(pid)

                items = product.get("items") or []
                if not items:
                    continue

                offer = (items[0].get("sellers") or [{}])[0].get("commertialOffer", {})

                if not offer.get("IsAvailable", False):
                    continue

                price     = float(offer.get("Price") or 0)
                old_price = float(offer.get("ListPrice") or 0)

                if price <= 0:
                    continue

                if old_price > price:
                    discount_pct = int((1 - price / old_price) * 100)
                else:
                    old_price = None
                    discount_pct = None

                if discount_pct is not None and discount_pct < MIN_DISCOUNT_PERCENT:
                    continue
                if discount_pct is not None and discount_pct > AMERICANAS_MAX_DISCOUNT_PCT:
                    logger.info(
                        "Americanas [dump] {} → DROP: desconto {}% > teto {}% (ListPrice inflado)",
                        pid, discount_pct, AMERICANAS_MAX_DISCOUNT_PCT,
                    )
                    continue

                title = product.get("productName") or ""
                if not title:
                    continue

                url = product.get("link") or ""
                if not url:
                    continue

                images = items[0].get("images") or []
                image_url = images[0].get("imageUrl") if images else None
                if image_url and not image_url.startswith("http"):
                    image_url = None

                installment_data = _best_installment(offer.get("Installments") or [])
                n_inst, v_inst = installment_data if installment_data else (None, None)

                logger.info(
                    "Americanas [dump] {} | '{}' | R${} → {}% desc",
                    pid,
                    title[:45],
                    f"{price:.2f}",
                    discount_pct if discount_pct is not None else "?",
                )

                deals.append(Deal(
                    title=title,
                    url=url,
                    price=price,
                    old_price=float(old_price) if old_price else None,
                    discount_pct=discount_pct,
                    image_url=image_url,
                    source=self.name,
                    store="Americanas",
                    installments=n_inst,
                    installment_value=v_inst,
                ))

            except Exception as exc:
                logger.warning(
                    "Americanas: erro ao processar produto id={}: {}",
                    product.get("productId", "?"), exc,
                )
                continue

        logger.info("Americanas: {} deals válidos após filtros.", len(deals))
        return deals
