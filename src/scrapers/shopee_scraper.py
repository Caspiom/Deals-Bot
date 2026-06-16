import re
from playwright.async_api import Page
from loguru import logger
from src.config.settings import MIN_DISCOUNT_PERCENT, MAX_DEALS_PER_RUN
from src.models import Deal
from src.scrapers.playwright_base_scraper import PlaywrightBaseScraper

# httpx retorna 403 — Shopee exige cookies de sessão real; Playwright resolve isso.
#
# Ordem de prioridade de fontes:
#  1. Flash Sale — produtos com 40-80% OFF, renovados a cada poucas horas
#  2. Buscas por categoria com sortBy=price (os mais baratos tendem a ter maior desconto)
_SEARCH_URLS = [
    "https://shopee.com.br/flash_sale",
    "https://shopee.com.br/search?keyword=smartphone&sortBy=price&order=asc",
    "https://shopee.com.br/search?keyword=notebook&sortBy=price&order=asc",
    "https://shopee.com.br/search?keyword=eletrodomestico&sortBy=price&order=asc",
]

# Links de produto Shopee terminam com -i.{shopid}.{itemid}
_PRODUCT_PATTERN = r"-i\.(\d+)\.(\d+)$"

# Extrai produtos localizando links pelo padrão -i.{shopid}.{itemid}.
# Shopee usa class names ofuscados — ancoramos nos links cujo formato é estável.
_EXTRACT_JS = """() => {
    const pattern = /-i\\.(\\d+)\\.(\\d+)$/;
    const seen = new Set();
    const results = [];

    for (const link of document.querySelectorAll('a[href]')) {
        try {
            const path = new URL(link.href).pathname;
            const m = path.match(pattern);
            if (!m || seen.has(link.href)) continue;
            seen.add(link.href);

            const container = link.closest('li') || link.parentElement?.parentElement || link.parentElement;

            // Título: primeiro texto folha dentro do link com mais de 8 chars que não é preço
            const title = Array.from(link.querySelectorAll('*'))
                .filter(el => !el.querySelector('*'))
                .map(el => el.innerText?.trim())
                .find(t => t && t.length > 8 && !t.includes('R$') && !/^\\d+%$/.test(t)) ?? null;

            // Preço atual: primeiro elemento com R$ fora de <s>/<del>
            const currentPriceEl = Array.from((container || link).querySelectorAll('*'))
                .find(el => !el.querySelector('*') && el.innerText?.includes('R$')
                         && !el.closest('s') && !el.closest('del'));

            // Preço antigo: dentro de <s> ou <del>
            const oldPriceEl = Array.from((container || link).querySelectorAll('s *, del *'))
                .find(el => !el.querySelector('*') && el.innerText?.includes('R$'));

            // Desconto: badge com "X%" ou "-X%"
            const discountEl = Array.from((container || link).querySelectorAll('*'))
                .find(el => !el.querySelector('*') && /^-?\\d+%$/.test(el.innerText?.trim() ?? ''));

            const imgEl = (container || link).querySelector('img[src*="shopee"]');

            results.push({
                url:      link.href,
                title:    title,
                price:    currentPriceEl?.innerText?.trim() ?? null,
                old_price: oldPriceEl?.innerText?.trim() ?? null,
                discount: discountEl?.innerText?.trim() ?? null,
                image:    imgEl?.src ?? null,
                item_id:  m[2],
                shop_id:  m[1],
            });
        } catch (_) {}
    }
    return results.filter(i => i.title && i.price && i.item_id);
}"""


def _parse_brl(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = re.sub(r"[R$\s\xa0]", "", text).replace(".", "").replace(",", ".")
    try:
        return float(cleaned.strip())
    except ValueError:
        return None


def _parse_discount_pct(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"(\d+)%", text)
    return int(m.group(1)) if m else None


class ShopeeScraper(PlaywrightBaseScraper):
    name = "shopee"

    async def _scrape(self, page: Page) -> list[Deal]:
        seen_ids: set[str] = set()
        deals: list[Deal] = []

        for url in _SEARCH_URLS:
            if len(deals) >= MAX_DEALS_PER_RUN:
                break

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Aguarda produtos aparecerem antes de scrollar — crítico para flash_sale
                try:
                    await page.wait_for_selector('a[href]', timeout=8000)
                except Exception:
                    logger.warning("Shopee: timeout aguardando links em {}.", url)
                    continue

                for i in range(4):
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await page.wait_for_timeout(600 + (i % 2) * 200)

                raw: list[dict] = await page.evaluate(_EXTRACT_JS)
                source_name = url.split("/")[-1].split("?")[0] or "flash_sale"
                logger.debug("Shopee [{}]: {} cards extraídos.", source_name, len(raw))

            except Exception as exc:
                logger.warning("Shopee: erro ao navegar em {}: {}", url, exc)
                continue

            for item in raw:
                try:
                    item_id = item.get("item_id", "")
                    if not item_id or item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)

                    discount_pct = _parse_discount_pct(item.get("discount"))
                    price = _parse_brl(item.get("price"))
                    old_price = _parse_brl(item.get("old_price"))

                    if not price or price <= 0:
                        continue

                    if discount_pct is None and old_price and old_price > price:
                        discount_pct = int((1 - price / old_price) * 100)

                    if discount_pct is not None and discount_pct < MIN_DISCOUNT_PERCENT:
                        continue

                    image = item.get("image") or ""
                    image_url = image if image.startswith("http") else None

                    deals.append(Deal(
                        title=item["title"],
                        url=item["url"],
                        price=price,
                        old_price=old_price if old_price and old_price > price else None,
                        discount_pct=discount_pct,
                        image_url=image_url,
                        source=self.name,
                        store="Shopee",
                    ))

                except Exception as exc:
                    logger.warning(
                        "Shopee: erro ao processar item '{}': {}",
                        (item.get("title") or "?")[:40], exc,
                    )
                    continue

                if len(deals) >= MAX_DEALS_PER_RUN:
                    break

        logger.info("Shopee: {} deals válidos após filtros.", len(deals))
        return deals
