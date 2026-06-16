import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timezone

import httpx
from loguru import logger

from src.config.settings import (
    AMAZON_ACCESS_KEY,
    AMAZON_SECRET_KEY,
    AMAZON_ASSOCIATE_TAG,
    MIN_DISCOUNT_PERCENT,
    MAX_DEALS_PER_RUN,
)
from src.models import Deal
from src.scrapers.base_scraper import BaseScraper

_HOST = "webservices.amazon.com.br"
_ENDPOINT = f"https://{_HOST}/paapi5/searchitems"
_SERVICE = "ProductAdvertisingAPI"
_REGION = "us-east-1"
_TARGET = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"

_RESOURCES = [
    "Images.Primary.Medium",
    "ItemInfo.Title",
    "Offers.Listings.Price",
    "Offers.Listings.SavingBasis",
]

# Categorias com maior volume de deals no Amazon BR → keyword amplo por categoria
# MinSavingPercent faz o filtro de desconto; keyword apenas direciona a busca
_CATEGORIES: dict[str, str] = {
    "Electronics":    "smart tv",
    "Computers":      "notebook",
    "Wireless":       "smartphone",
    "HomeAndKitchen": "eletrodoméstico",
    "OfficeProducts": "impressora",
    "VideoGames":     "controle",
}


# ── AWS Signature v4 ─────────────────────────────────────────────────────────

def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, date_stamp: str) -> bytes:
    k = _hmac_sha256(("AWS4" + secret).encode("utf-8"), date_stamp)
    k = _hmac_sha256(k, _REGION)
    k = _hmac_sha256(k, _SERVICE)
    return _hmac_sha256(k, "aws4_request")


def _signed_headers(access_key: str, secret_key: str, body: str) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    payload_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()

    # Ordem lexicográfica obrigatória para SigV4
    canonical_headers = (
        f"content-encoding:amz-1.0\n"
        f"content-type:application/json; charset=utf-8\n"
        f"host:{_HOST}\n"
        f"x-amz-date:{amz_date}\n"
        f"x-amz-target:{_TARGET}\n"
    )
    signed_headers = "content-encoding;content-type;host;x-amz-date;x-amz-target"

    canonical_request = "\n".join([
        "POST",
        "/paapi5/searchitems",
        "",  # sem query string
        canonical_headers,
        signed_headers,
        payload_hash,
    ])

    credential_scope = f"{date_stamp}/{_REGION}/{_SERVICE}/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])

    sig = hmac.new(
        _signing_key(secret_key, date_stamp),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    auth = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={sig}"
    )

    return {
        "Content-Encoding": "amz-1.0",
        "Content-Type": "application/json; charset=utf-8",
        "Host": _HOST,
        "X-Amz-Date": amz_date,
        "X-Amz-Target": _TARGET,
        "Authorization": auth,
    }


# ── Scraper ──────────────────────────────────────────────────────────────────

class AmazonScraper(BaseScraper):
    name = "amazon"

    async def fetch(self) -> list[Deal]:
        if not AMAZON_ACCESS_KEY or not AMAZON_SECRET_KEY:
            logger.warning("Amazon: AMAZON_ACCESS_KEY / AMAZON_SECRET_KEY não configurados. Scraper ignorado.")
            return []

        results = await asyncio.gather(
            *[self._fetch_category(idx, kw) for idx, kw in _CATEGORIES.items()],
            return_exceptions=True,
        )

        seen_asins: set[str] = set()
        deals: list[Deal] = []

        for search_index, result in zip(_CATEGORIES.keys(), results):
            if isinstance(result, Exception):
                logger.warning("Amazon [{}]: falhou — {}", search_index, result)
                continue
            for deal, asin in result:
                if asin in seen_asins:
                    continue
                seen_asins.add(asin)
                deals.append(deal)
                if len(deals) >= MAX_DEALS_PER_RUN:
                    break
            if len(deals) >= MAX_DEALS_PER_RUN:
                break

        logger.info("Amazon: {} deals válidos após filtros.", len(deals))
        return deals

    async def _fetch_category(self, search_index: str, keywords: str) -> list[tuple[Deal, str]]:
        payload = {
            "Keywords": keywords,
            "Resources": _RESOURCES,
            "SearchIndex": search_index,
            "ItemCount": 10,
            "MinSavingPercent": MIN_DISCOUNT_PERCENT,
            "SortBy": "Featured",
            "PartnerTag": AMAZON_ASSOCIATE_TAG,
            "PartnerType": "Associates",
            "Marketplace": "www.amazon.com.br",
        }
        body = json.dumps(payload)
        headers = _signed_headers(AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, body)

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(_ENDPOINT, content=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        items = data.get("SearchResult", {}).get("Items", [])
        logger.debug("Amazon [{}]: {} itens recebidos.", search_index, len(items))

        deals: list[tuple[Deal, str]] = []
        for item in items:
            deal = self._parse_item(item)
            if deal:
                deals.append((deal, item.get("ASIN", "")))
        return deals

    def _parse_item(self, item: dict) -> Deal | None:
        asin = item.get("ASIN", "")
        title = (
            item.get("ItemInfo", {})
            .get("Title", {})
            .get("DisplayValue", "")
            .strip()
        )
        if not title:
            return None

        # DetailPageURL já vem com ?tag= da resposta da API
        url = item.get("DetailPageURL", "")
        if not url:
            url = f"https://www.amazon.com.br/dp/{asin}?tag={AMAZON_ASSOCIATE_TAG}"

        listings = item.get("Offers", {}).get("Listings", [])
        if not listings:
            return None

        listing = listings[0]
        price = listing.get("Price", {}).get("Amount")
        saving = listing.get("SavingBasis", {})
        old_price = saving.get("Amount")
        discount_pct = saving.get("Percentage")

        if not price or price <= 0:
            return None

        if discount_pct is None and old_price and old_price > price:
            discount_pct = int((1 - price / old_price) * 100)

        if not discount_pct or discount_pct < MIN_DISCOUNT_PERCENT:
            return None

        image_url = (
            item.get("Images", {})
            .get("Primary", {})
            .get("Medium", {})
            .get("URL")
        )

        return Deal(
            title=title,
            url=url,
            price=float(price),
            old_price=float(old_price) if old_price and old_price > price else None,
            discount_pct=int(discount_pct),
            image_url=image_url,
            source=self.name,
            store="Amazon",
        )
