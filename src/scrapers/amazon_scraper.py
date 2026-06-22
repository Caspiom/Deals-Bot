import re
from playwright.async_api import Page
from loguru import logger
from src.config.settings import MIN_DISCOUNT_PERCENT
from src.models import Deal
from src.scrapers.playwright_base_scraper import PlaywrightBaseScraper
from src.utils.price_parser import parse_brl as _parse_brl

# URL pré-filtrada: apenas deals com 40-90% OFF, evita poluição de produtos sem desconto real
_DEALS_URL = (
    "https://www.amazon.com.br/events/deals"
    "?discounts-widget=%2522%257B%255C%2522state%255C%2522%253A%257B%255C%2522rangeRefinement"
    "Filters%255C%2522%253A%257B%255C%2522percentOff%255C%2522%253A%257B%255C%2522min%255C%2522"
    "%253A40%252C%255C%2522max%255C%2522%253A90%257D%257D%257D%252C%255C%2522version%255C%2522"
    "%253A1%257D%2522"
)

# Extrator "Selector Agnostic": ancora nos links /dp/ e sobe via closest().
# Seletores confirmados via inspeção do DOM da URL /events/deals com filtro 40-90%.
_EXTRACT_JS = """() => {
    const asinRe = /\\/dp\\/([A-Z0-9]{10})/;
    const brlRe  = /R\\$\\s*(\\d{1,3}(?:\\.\\d{3})*,\\d{2})/;
    const discRe = /(\\d+)%\\s*off/i;

    const links    = Array.from(document.querySelectorAll('a[href*="/dp/"]'));
    const seenCards = new Set();
    const results  = [];

    for (const link of links) {
        // Sobe para o card contêiner usando os seletores confirmados no DOM real.
        // [data-testid="product-card"] e [class*="GridItem-module__container"]
        // são os contêineres raiz da view /events/deals com filtro aplicado.
        const card = (
            link.closest('[data-testid="product-card"]') ||
            link.closest('[class*="GridItem-module__container"]')
        );
        if (!card || seenCards.has(card)) continue;
        seenCards.add(card);

        const href       = link.href;
        const asinMatch  = href.match(asinRe);
        if (!asinMatch) continue;
        const asin = asinMatch[1];

        // Título: img[class*="ProductCardImage"][alt] → p[id*="title-"] truncate-full
        let title = card.querySelector('img[class*="ProductCardImage"]')?.getAttribute('alt')?.trim() ?? null;
        if (!title || title.length < 5) {
            title = (
                card.querySelector('p[id*="title-"] [class*="truncate-full"]') ??
                card.querySelector('[class*="ProductCard-module__title"] [class*="truncate-full"]')
            )?.innerText?.trim() ?? null;
        }
        if (!title || title.length < 5) continue;

        // Preço atual: [class*="priceToPay"] .a-offscreen
        const priceStr = card.querySelector('[class*="priceToPay"] .a-offscreen')?.innerText?.trim() ?? null;

        // Preço antigo: [class*="text-price"] .a-offscreen → span[aria-hidden]
        let oldPriceStr = card.querySelector('[class*="text-price"] .a-offscreen')?.innerText?.trim() ?? null;
        if (!oldPriceStr) {
            oldPriceStr = card.querySelector('[class*="text-price"] span[aria-hidden="true"]')?.innerText?.trim() ?? null;
        }

        // Desconto: badgeContainer contém "60% off"
        const discountStr = card.querySelector('[class*="badgeContainer"]')?.innerText?.trim() ?? null;

        results.push({
            id:        asin,
            title:     title,
            url:       href,
            price:     priceStr,
            old_price: oldPriceStr,
            discount:  discountStr,
            image:     card.querySelector('img')?.src ?? null,
        });
    }
    return results;
}"""


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

        for _ in range(8):
            await page.evaluate("window.scrollBy(0, 800)")
            await page.wait_for_timeout(700)
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(500)

        raw: list[dict] = await page.evaluate(_EXTRACT_JS)
        logger.info("Amazon: {} cards brutos extraídos (antes de filtros).", len(raw))

        seen_asins:  set[str] = set()
        seen_titles: set[str] = set()
        deals: list[Deal] = []

        for item in raw:
            try:
                asin = item.get("id", "")   # JS agora retorna campo "id" (era "asin")
                if not asin or asin in seen_asins:
                    continue
                seen_asins.add(asin)

                # Dedup intra-ciclo por título normalizado: evita o mesmo produto
                # com ASINs diferentes (cores, tamanhos) spammar o canal no mesmo ciclo.
                title_key = re.sub(r'\s+', ' ', (item.get("title") or "").lower().strip())[:60]
                if title_key and title_key in seen_titles:
                    logger.info("Amazon [dump] {} → DROP: título duplicado no ciclo ('{}')", asin, title_key[:40])
                    continue
                if title_key:
                    seen_titles.add(title_key)

                price     = _parse_brl(item.get("price"))
                old_price = _parse_brl(item.get("old_price"))
                discount_pct = _parse_discount_pct(item.get("discount"))

                if discount_pct is None and old_price and old_price > (price or 0):
                    discount_pct = int((1 - (price or 0) / old_price) * 100)

                # ── DUMP DIAGNÓSTICO ──────────────────────────────────────────
                logger.info(
                    "Amazon [dump] {} | '{}' | preço: '{}' → {} | old: '{}' → {} | desc: '{}' → {}%",
                    asin,
                    (item.get("title") or "")[:45],
                    item.get("price"),    f"{price:.2f}"     if price     is not None else "NONE",
                    item.get("old_price"), f"{old_price:.2f}" if old_price is not None else "NONE",
                    item.get("discount"), discount_pct if discount_pct is not None else "NONE",
                )
                # ─────────────────────────────────────────────────────────────

                if not price or price <= 0:
                    logger.info("Amazon [dump] {} → DROP: preço inválido ('{}')", asin, item.get("price"))
                    continue

                if discount_pct is None:
                    logger.info("Amazon [dump] {} → DROP: desconto não determinado", asin)
                    continue

                if discount_pct < MIN_DISCOUNT_PERCENT:
                    logger.info(
                        "Amazon [dump] {} → DROP: desconto {}% < mínimo {}%",
                        asin, discount_pct, MIN_DISCOUNT_PERCENT,
                    )
                    continue

                image = item.get("image") or ""
                if image.startswith("http"):
                    image = re.sub(r'\._[A-Z][^.]*(?=\.\w+$)', '', image)

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
                logger.warning("Amazon: erro ao processar ASIN={}: {}", item.get("id", "?"), exc)
                continue

        logger.info("Amazon: {} deals válidos após filtros.", len(deals))
        return deals
