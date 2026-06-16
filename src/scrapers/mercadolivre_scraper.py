import re
from playwright.async_api import Page
from loguru import logger
from src.config.settings import MIN_DISCOUNT_PERCENT, MAX_DEALS_PER_RUN
from src.models import Deal
from src.scrapers.playwright_base_scraper import PlaywrightBaseScraper
from src.services.installment_calculator import parse_installment_string

_OFFERS_URL = "https://www.mercadolivre.com.br/ofertas"

_EXTRACT_JS = """() => {
    const allCards = document.querySelectorAll('[class*="poly-card"]');
    const topCards = Array.from(allCards).filter(
        card => !card.parentElement?.closest('[class*="poly-card"]')
    );
    return topCards.map(card => {
        const titleEl  = card.querySelector('[class*="poly-component__title"]');
        const link     = card.querySelector('a[href*="mercadolivre"], a[href*="produto."]');
        const discEl   = card.querySelector('[class*="andes-money-amount__discount"]');
        const imgEl    = card.querySelector('img[src*="mlstatic"]');
        const strikeEl = card.querySelector('s [class*="andes-money-amount__fraction"]');
        const fractions = card.querySelectorAll('[class*="andes-money-amount__fraction"]');
        let curFraction = null;
        for (const f of fractions) {
            if (!f.closest('s')) { curFraction = f; break; }
        }
        const installEl = card.querySelector('[class*="installments"], [class*="poly-price__installments"]');
        const couponEl  = card.querySelector('[class*="coupon"], [class*="cupom"], [data-testid*="coupon"]');
        const coinsEl   = card.querySelector('[class*="coins"], [class*="moedas"], [class*="poly-coins"]');
        return {
            title:       titleEl?.innerText?.trim() ?? null,
            url:         link?.href ?? null,
            current:     curFraction?.innerText?.trim() ?? null,
            original:    strikeEl?.innerText?.trim() ?? null,
            discount:    discEl?.innerText?.trim() ?? null,
            image:       imgEl?.src ?? null,
            installment: installEl?.innerText?.trim() ?? null,
            coupon:      couponEl?.innerText?.trim() ?? null,
            coins:       coinsEl?.innerText?.trim() ?? null,
        };
    }).filter(item => item.title && item.url && item.current);
}"""


def _parse_brl(text: str) -> float | None:
    # BRL usa "." como separador de milhar: "1.080" → 1080
    cleaned = re.sub(r"[R$\s]", "", text).replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_discount_pct(text: str) -> int | None:
    m = re.search(r"(\d+)\s*%\s*OFF", text, re.IGNORECASE)
    return int(m.group(1)) if m else None


class MercadoLivreScraper(PlaywrightBaseScraper):
    name = "mercadolivre"

    async def _scrape(self, page: Page) -> list[Deal]:
        await page.goto(_OFFERS_URL, wait_until="networkidle", timeout=30000)

        for _ in range(3):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(800)

        raw: list[dict] = await page.evaluate(_EXTRACT_JS)
        logger.info("MercadoLivre: {} cards extraídos do DOM.", len(raw))

        deals: list[Deal] = []
        seen_urls: set[str] = set()

        for item in raw:
            url = item.get("url", "")
            # remove parâmetros de tracking para dedup
            base_url = url.split("#")[0]
            if base_url in seen_urls or not base_url:
                continue
            seen_urls.add(base_url)

            discount_pct = _parse_discount_pct(item.get("discount") or "")
            if discount_pct is not None and discount_pct < MIN_DISCOUNT_PERCENT:
                continue

            price = _parse_brl(item["current"])
            if price is None or price <= 0:
                continue

            old_price = _parse_brl(item["original"]) if item.get("original") else None

            parsed = parse_installment_string(item.get("installment") or "")
            n_inst, v_inst = parsed if parsed else (None, None)

            coupon_code = (item.get("coupon") or "").strip() or None
            coins_val = _parse_brl(item.get("coins") or "") if item.get("coins") else None

            deals.append(Deal(
                title=item["title"],
                url=url,
                price=price,
                old_price=old_price,
                discount_pct=discount_pct,
                image_url=item.get("image"),
                source=self.name,
                store="Mercado Livre",
                installments=n_inst,
                installment_value=v_inst,
                coupon_code=coupon_code,
                coins_discount_value=coins_val,
            ))

            if len(deals) >= MAX_DEALS_PER_RUN:
                break

        logger.info("MercadoLivre: {} deals válidos após filtros.", len(deals))
        return deals
