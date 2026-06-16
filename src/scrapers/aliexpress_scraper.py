import hashlib
import time
import httpx
from loguru import logger
from src.config.settings import (
    MIN_DISCOUNT_PERCENT,
    MAX_DEALS_PER_RUN,
    ALIEXPRESS_APP_KEY,
    ALIEXPRESS_SECRET_KEY,
    ALIEXPRESS_TRACKING_ID,
    PROXY_URL,
)
from src.models import Deal
from src.scrapers.base_scraper import BaseScraper
from src.utils.retry import scraper_retry

_API_URL = "https://api-sg.aliexpress.com/sync"

# localSalePrice / localOriginalPrice já vêm com impostos BR calculados pelo AliExpress
_FIELDS = (
    "productId,productTitle,productUrl,promotionLink,"
    "salePrice,originalPrice,localSalePrice,localOriginalPrice,"
    "discount,productMainImageUrl"
)


def _sign(params: dict, secret: str) -> str:
    sorted_str = "".join(f"{k}{v}" for k, v in sorted(params.items()))
    raw = f"{secret}{sorted_str}{secret}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()


def _parse_price(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = str(value).replace("BRL", "").replace("R$", "").strip()
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned.strip())
    except ValueError:
        return None


class AliExpressScraper(BaseScraper):
    name = "aliexpress"

    @scraper_retry
    async def fetch(self) -> list[Deal]:
        if not ALIEXPRESS_APP_KEY or not ALIEXPRESS_SECRET_KEY:
            logger.warning("AliExpress: credenciais não configuradas. Scraper ignorado.")
            return []

        timestamp = str(int(time.time() * 1000))
        params: dict[str, str] = {
            "app_key": ALIEXPRESS_APP_KEY,
            "method": "aliexpress.affiliate.hotproduct.query",
            "sign_method": "md5",
            "timestamp": timestamp,
            "v": "2.0",
            "fields": _FIELDS,
            "page_no": "1",
            "page_size": str(min(MAX_DEALS_PER_RUN * 5, 50)),
            "sort": "LAST_VOLUME_DESC",
            "target_currency": "BRL",
            "target_language": "PT",
            "tracking_id": ALIEXPRESS_TRACKING_ID,
        }
        params["sign"] = _sign(params, ALIEXPRESS_SECRET_KEY)

        proxies = {"all://": PROXY_URL} if PROXY_URL else None
        async with httpx.AsyncClient(timeout=20, proxies=proxies) as client:
            resp = await client.post(_API_URL, data=params)
            resp.raise_for_status()
            data = resp.json()

        wrapper = data.get("aliexpress_affiliate_hotproduct_query_response")
        if not wrapper:
            logger.warning(
                "AliExpress: chave de resposta não encontrada. Chaves presentes: {} | Trecho: {}",
                list(data.keys()),
                str(data)[:300],
            )
            return []

        resp_result = wrapper.get("resp_result", {})
        if resp_result.get("resp_code") != 200:
            logger.warning(
                "AliExpress: erro na API — código {} | {}",
                resp_result.get("resp_code"),
                resp_result.get("resp_msg", "desconhecido"),
            )
            return []

        products = (
            resp_result
            .get("result", {})
            .get("products", {})
            .get("product", [])
        )
        logger.info("AliExpress: {} produtos recebidos.", len(products))

        deals: list[Deal] = []
        for p in products:
            try:
                discount_raw = str(p.get("discount", "0")).rstrip("%")
                try:
                    discount_pct = int(float(discount_raw))
                except (ValueError, TypeError):
                    discount_pct = 0

                if discount_pct < MIN_DISCOUNT_PERCENT:
                    continue

                price = _parse_price(p.get("local_sale_price")) or _parse_price(p.get("sale_price"))
                old_price = _parse_price(p.get("local_original_price")) or _parse_price(p.get("original_price"))
                has_local_price = bool(_parse_price(p.get("local_sale_price")))

                if not price or price <= 0:
                    continue

                url = p.get("promotion_link") or p.get("product_url", "")
                if not url:
                    continue

                tax_note = "🌐 Preço com impostos de importação incluídos (BR)" if has_local_price else None

                deals.append(Deal(
                    title=str(p.get("product_title", "")).strip(),
                    url=url,
                    price=price,
                    old_price=old_price if old_price and old_price > price else None,
                    discount_pct=discount_pct,
                    image_url=p.get("product_main_image_url"),
                    source=self.name,
                    store="AliExpress",
                    tax_note=tax_note,
                ))

            except Exception as exc:
                logger.warning(
                    "AliExpress: erro ao processar produto id={}: {}",
                    p.get("product_id", "?"), exc,
                )
                continue

            if len(deals) >= MAX_DEALS_PER_RUN:
                break

        logger.info("AliExpress: {} deals válidos após filtros.", len(deals))
        return deals
