import httpx
from loguru import logger
from src.config.settings import MIN_DISCOUNT_PERCENT
from src.models import Deal
from src.scrapers.base_scraper import BaseScraper

_API_URL = "https://api.promobit.com.br/offers"
_IMAGE_BASE = "https://i.promobit.com.br/300"
_DEAL_BASE = "https://www.promobit.com.br/oferta"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Referer": "https://www.promobit.com.br/",
    "Origin": "https://www.promobit.com.br",
}


class PromobitScraper(BaseScraper):
    name = "promobit"

    async def fetch(self) -> list[Deal]:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=15) as client:
            resp = await client.get(
                _API_URL,
                params={"sort": "hot", "limit": 100},
            )
            resp.raise_for_status()
            data = resp.json()

        offers = data.get("offers", [])
        logger.info("Promobit: {} ofertas recebidas da API.", len(offers))

        deals: list[Deal] = []

        for offer in offers:
            price     = float(offer.get("offer_price") or 0)
            old_price = float(offer.get("offer_old_price") or 0)
            api_pct   = int(offer.get("offer_discont_percentage") or 0)

            if price <= 0:
                continue

            # calcula desconto via preços se a API retornar 0
            if api_pct == 0 and old_price > price:
                api_pct = int((1 - price / old_price) * 100)

            if api_pct < MIN_DISCOUNT_PERCENT:
                continue

            slug        = offer.get("offer_slug", "")
            photo       = offer.get("offer_photo", "")
            image_url   = f"{_IMAGE_BASE}{photo}" if photo and not photo.startswith("http") else photo
            store       = offer.get("store_name") or offer.get("merchant_name") or ""
            coupon_code = (offer.get("offer_coupon") or "").strip() or None

            deals.append(Deal(
                title=offer.get("offer_title", "").strip(),
                url=f"{_DEAL_BASE}/{slug}",
                price=price,
                old_price=old_price if old_price > price else None,
                discount_pct=api_pct,
                image_url=image_url or None,
                source=self.name,
                store=store,
                coupon_code=coupon_code,
            ))

        logger.info("Promobit: {} deals válidos após filtros.", len(deals))
        return deals
