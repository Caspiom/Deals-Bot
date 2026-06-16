import re
from playwright.async_api import Page
from loguru import logger
from src.config.settings import MIN_DISCOUNT_PERCENT, MAX_DEALS_PER_RUN
from src.models import Deal
from src.scrapers.playwright_base_scraper import PlaywrightBaseScraper
from src.services.installment_calculator import parse_installment_string

# Busca por "desconto" ordenada por maior percentual — garante os maiores descontos primeiro
_OFFERS_URL = (
    "https://www.magazineluiza.com.br/busca/desconto/"
    "?ordenacao=-percentual_desconto&tipo=oferta"
)

# Magalu usa Next.js + Luizalabs design system.
# Seletores por data-testid (mais estáveis) com fallback em padrão de classe.
_EXTRACT_JS = """() => {
    const cards = document.querySelectorAll(
        '[data-testid="product-card-container"], ' +
        '[class*="productCard__"], ' +
        '[class*="ProductCard"]'
    );
    return Array.from(cards).map(card => {
        const link      = card.querySelector('a[href*="/p/"]');
        const titleEl   = card.querySelector(
            '[data-testid="product-title"], [class*="title__"], h2'
        );
        const priceEl   = card.querySelector(
            '[data-testid="price-value"], [class*="price-value__"], [class*="priceValue"]'
        );
        const oldEl     = card.querySelector('s, del, [data-testid="old-price"]');
        const discEl    = card.querySelector(
            '[data-testid="discount-flag"], [class*="discount__"], [class*="Discount"]'
        );
        const installEl = card.querySelector(
            '[data-testid="installment"], [class*="installment__"]'
        );
        const imgEl     = card.querySelector('img');
        return {
            url:         link?.href ?? null,
            title:       titleEl?.innerText?.trim() ?? null,
            price:       priceEl?.innerText?.trim() ?? null,
            old_price:   oldEl?.innerText?.trim() ?? null,
            discount:    discEl?.innerText?.trim() ?? null,
            installment: installEl?.innerText?.trim() ?? null,
            image:       imgEl?.src || imgEl?.dataset?.src || null,
        };
    }).filter(i => i.url && i.title && i.price);
}"""


def _parse_brl(text: str | None) -> float | None:
    if not text:
        return None
    # Remove "R$", espaço normal e não-quebrável (\xa0)
    cleaned = re.sub(r"[R$\s\xa0]", "", text)
    # BRL: "." separador de milhar, "," separador decimal → converte para float
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_discount_pct(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"(\d+)\s*%", text)
    return int(m.group(1)) if m else None


class MagaluScraper(PlaywrightBaseScraper):
    name = "magalu"

    async def _scrape(self, page: Page) -> list[Deal]:
        await page.goto(_OFFERS_URL, wait_until="networkidle", timeout=30000)

        for _ in range(3):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(800)

        raw: list[dict] = await page.evaluate(_EXTRACT_JS)
        logger.info("Magalu: {} cards extraídos do DOM.", len(raw))

        deals: list[Deal] = []
        seen_urls: set[str] = set()

        for item in raw:
            # Normaliza URL removendo query string de tracking para dedup
            url = item.get("url", "")
            base_url = url.split("?")[0].rstrip("/")
            if not base_url or base_url in seen_urls:
                continue
            seen_urls.add(base_url)

            discount_pct = _parse_discount_pct(item.get("discount"))
            if discount_pct is not None and discount_pct < MIN_DISCOUNT_PERCENT:
                continue

            price = _parse_brl(item.get("price"))
            if price is None or price <= 0:
                continue

            old_price = _parse_brl(item.get("old_price"))

            parsed = parse_installment_string(item.get("installment") or "")
            n_inst, v_inst = parsed if parsed else (None, None)

            # Filtra imagens placeholder (base64 ou data URI de lazy loading)
            image = item.get("image") or ""
            image_url = image if image.startswith("http") else None

            deals.append(Deal(
                title=item["title"],
                url=url,
                price=price,
                old_price=old_price,
                discount_pct=discount_pct,
                image_url=image_url,
                source=self.name,
                store="Magazine Luiza",
                installments=n_inst,
                installment_value=v_inst,
            ))

            if len(deals) >= MAX_DEALS_PER_RUN:
                break

        logger.info("Magalu: {} deals válidos após filtros.", len(deals))
        return deals
