import re
from playwright.async_api import Page
from loguru import logger
from src.config.settings import MIN_DISCOUNT_PERCENT
from src.models import Deal
from src.scrapers.playwright_base_scraper import PlaywrightBaseScraper
from src.services.installment_calculator import parse_installment_string
from src.utils.price_parser import parse_brl as _parse_brl

_OFFERS_URL = "https://www.magazineluiza.com.br/ofertas/"

# Estratégia: ancora em links de produto (/p/{sku}/) que são estáveis entre redesigns.
# Extrai dados subindo ao container pai — resistente a ofuscação de classes.
_EXTRACT_JS = """() => {
    const productPattern = /\\/p\\/[a-z0-9]+\\//i;
    const seen = new Set();

    const links = Array.from(document.querySelectorAll('a[href*="/p/"]'))
        .filter(a => productPattern.test(a.pathname));

    return links
        .filter(a => { if (seen.has(a.pathname)) return false; seen.add(a.pathname); return true; })
        .map(link => {
            const card = link.closest('li') || link.closest('article') || link.parentElement;

            const titleEl   = card?.querySelector('h2, h3, [data-testid*="title"]');
            const priceEl   = card?.querySelector(
                '[data-testid="price-value"], [class*="price-value"], [class*="priceValue"]'
            );
            const oldEl     = card?.querySelector('s, del');
            const discEl    = card?.querySelector(
                '[data-testid*="discount"], [class*="discount"], [class*="Discount"]'
            );
            const installEl = card?.querySelector(
                '[data-testid*="installment"], [class*="installment"]'
            );
            const imgEl     = card?.querySelector('img');

            return {
                url:         link.href,
                title:       titleEl?.innerText?.trim() ?? null,
                price:       priceEl?.innerText?.trim() ?? null,
                old_price:   oldEl?.innerText?.trim() ?? null,
                discount:    discEl?.innerText?.trim() ?? null,
                installment: installEl?.innerText?.trim() ?? null,
                image:       imgEl?.src || imgEl?.dataset?.src || null,
            };
        }).filter(i => i.url && i.title && i.price);
}"""



def _parse_discount_pct(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"(\d+)\s*%", text)
    return int(m.group(1)) if m else None


class MagaluScraper(PlaywrightBaseScraper):
    name = "magalu"

    async def _scrape(self, page: Page) -> list[Deal]:
        await page.goto(_OFFERS_URL, wait_until="domcontentloaded", timeout=30000)

        # React precisa de tempo para hidratar após domcontentloaded.
        # Tentamos networkidle por até 10s; se analytics travar, continuamos mesmo assim.
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        # Aguarda pelo menos um link de produto aparecer
        try:
            await page.wait_for_selector('a[href*="/p/"]', timeout=20000)
        except Exception:
            logger.warning("Magalu: nenhum link de produto encontrado — possível bloqueio ou DOM vazio.")
            return []

        for i in range(5):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(600 + (i % 3) * 200)

        raw: list[dict] = await page.evaluate(_EXTRACT_JS)
        logger.info("Magalu: {} cards extraídos do DOM.", len(raw))

        deals: list[Deal] = []
        seen_urls: set[str] = set()

        for item in raw:
            try:
                url = item.get("url", "")
                base_url = url.split("?")[0].rstrip("/")
                if not base_url or base_url in seen_urls:
                    continue
                seen_urls.add(base_url)

                discount_pct = _parse_discount_pct(item.get("discount"))
                price        = _parse_brl(item.get("price"))
                old_price    = _parse_brl(item.get("old_price"))

                if discount_pct is None and old_price and old_price > (price or 0):
                    discount_pct = int((1 - (price or 0) / old_price) * 100)

                sku_m = re.search(r'/p/([a-z0-9]+)/', base_url, re.I)
                sku   = sku_m.group(1) if sku_m else base_url[-20:]
                logger.info(
                    "Magalu [dump] {} | '{}' | preço: '{}' → {} | old: '{}' → {} | desc: '{}' → {}%",
                    sku,
                    (item.get("title") or "")[:45],
                    item.get("price"),     f"{price:.2f}"     if price     is not None else "NONE",
                    item.get("old_price"), f"{old_price:.2f}" if old_price is not None else "NONE",
                    item.get("discount"),  discount_pct if discount_pct is not None else "NONE",
                )

                if discount_pct is not None and discount_pct < MIN_DISCOUNT_PERCENT:
                    logger.info("Magalu [dump] {} → DROP: desconto {}% < mínimo {}%", sku, discount_pct, MIN_DISCOUNT_PERCENT)
                    continue

                if price is None or price <= 0:
                    logger.info("Magalu [dump] {} → DROP: preço inválido ('{}')", sku, item.get("price"))
                    continue

                parsed = parse_installment_string(item.get("installment") or "")
                n_inst, v_inst = parsed if parsed else (None, None)

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

            except Exception as exc:
                logger.warning(
                    "Magalu: erro ao processar item '{}': {}",
                    (item.get("title") or "?")[:40], exc,
                )
                continue

        logger.info("Magalu: {} deals válidos após filtros.", len(deals))
        return deals
