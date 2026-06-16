import re
from playwright.async_api import Page
from loguru import logger
from src.config.settings import MIN_DISCOUNT_PERCENT, MAX_DEALS_PER_RUN
from src.models import Deal
from src.scrapers.playwright_base_scraper import PlaywrightBaseScraper

# Página central de Ofertas do Dia da Amazon BR — sem necessidade de PA API
_DEALS_URL = "https://www.amazon.com.br/deals"

# ASIN: 10 caracteres A-Z0-9 logo após /dp/
_ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})")

# Ancora em links de produto /dp/{ASIN} — estrutura estável há +10 anos.
# Usa .a-offscreen para preços (spans legíveis por screen readers, mais confiável
# que parsear whole+fraction separados).
_EXTRACT_JS = """() => {
    const asinRe = /\\/dp\\/([A-Z0-9]{10})/;
    const seen = new Set();
    const results = [];

    for (const link of document.querySelectorAll('a[href*="/dp/"]')) {
        try {
            const m = asinRe.exec(link.href);
            if (!m || seen.has(m[1])) continue;
            seen.add(m[1]);

            const card = (
                link.closest('[class*="DealCard"]') ||
                link.closest('[data-testid*="deal"]') ||
                link.closest('[class*="deal-card"]') ||
                link.closest('li') ||
                link.parentElement?.parentElement
            );

            const titleEl = link.querySelector('span') ||
                            card?.querySelector('h2 span, [class*="title"] span');

            // .a-offscreen contém o preço completo ("R$ 1.299,00") — mais fácil de parsear
            const offscreens = Array.from((card || link).querySelectorAll('.a-offscreen'));
            const currentEl = offscreens.find(el =>
                !el.closest('s') && !el.closest('.a-text-strike') && el.innerText.includes('R$')
            );
            const oldEl = offscreens.find(el =>
                (el.closest('s') || el.closest('.a-text-strike')) && el.innerText.includes('R$')
            );

            const discountEl = card?.querySelector(
                '[class*="badgeLabel"] span, [class*="percent-off"], ' +
                '[class*="savings"] span, [class*="discount"] span'
            );

            const imgEl = (card || link).querySelector(
                'img[src*="amazon.com"], img[src*="ssl-images-amazon"]'
            );

            results.push({
                url:       link.href,
                asin:      m[1],
                title:     titleEl?.innerText?.trim() ?? null,
                price:     currentEl?.innerText?.trim() ?? null,
                old_price: oldEl?.innerText?.trim() ?? null,
                discount:  discountEl?.innerText?.trim() ?? null,
                image:     imgEl?.src ?? null,
            });
        } catch (_) {}
    }
    return results.filter(r => r.asin && r.title);
}"""


def _parse_brl(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = re.sub(r"[R$\s\xa0]", "", text)
    if "," in cleaned and "." in cleaned:
        # "1.299,00" → BRL completo: ponto = milhar, vírgula = decimal
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        # "299,90" → só decimal BRL
        cleaned = cleaned.replace(",", ".")
    elif "." in cleaned:
        # "1.000" → ponto com 3 dígitos = separador de milhar BRL
        parts = cleaned.split(".")
        if len(parts) == 2 and len(parts[1]) == 3 and parts[1].isdigit():
            cleaned = parts[0] + parts[1]
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_discount_pct(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"(\d+)\s*%", text)
    return int(m.group(1)) if m else None


class AmazonScraper(PlaywrightBaseScraper):
    name = "amazon"

    async def _scrape(self, page: Page) -> list[Deal]:
        await page.goto(_DEALS_URL, wait_until="domcontentloaded", timeout=30000)

        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        try:
            await page.wait_for_selector('a[href*="/dp/"]', timeout=15000)
        except Exception:
            logger.warning("Amazon: nenhum produto encontrado na página de ofertas.")
            return []

        for i in range(5):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(500 + (i % 3) * 200)

        raw: list[dict] = await page.evaluate(_EXTRACT_JS)
        logger.info("Amazon: {} cards extraídos do DOM.", len(raw))

        seen_asins: set[str] = set()
        deals: list[Deal] = []

        for item in raw:
            try:
                asin = item.get("asin", "")
                if not asin or asin in seen_asins:
                    continue
                seen_asins.add(asin)

                price = _parse_brl(item.get("price"))
                if not price or price <= 0:
                    continue

                old_price = _parse_brl(item.get("old_price"))
                discount_pct = _parse_discount_pct(item.get("discount"))

                if discount_pct is None and old_price and old_price > price:
                    discount_pct = int((1 - price / old_price) * 100)

                if discount_pct is not None and discount_pct < MIN_DISCOUNT_PERCENT:
                    continue

                image = item.get("image") or ""

                deals.append(Deal(
                    title=item["title"],
                    url=item["url"],
                    price=price,
                    old_price=old_price if old_price and old_price > price else None,
                    discount_pct=discount_pct,
                    image_url=image if image.startswith("http") else None,
                    source=self.name,
                    store="Amazon",
                ))
            except Exception as exc:
                logger.warning("Amazon: erro ao processar ASIN={}: {}", item.get("asin", "?"), exc)
                continue

            if len(deals) >= MAX_DEALS_PER_RUN:
                break

        logger.info("Amazon: {} deals válidos após filtros.", len(deals))
        return deals
