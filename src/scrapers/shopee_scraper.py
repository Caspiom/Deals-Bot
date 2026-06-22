import re
from playwright.async_api import Page
from loguru import logger
from src.config.settings import MIN_DISCOUNT_PERCENT
from src.models import Deal
from src.scrapers.playwright_base_scraper import PlaywrightBaseScraper
from src.utils.price_parser import parse_brl as _parse_brl

# httpx retorna 403 — Shopee exige cookies de sessão real; Playwright resolve isso.
#
# Ordem de prioridade de fontes:
#  1. Shopee Deals — página pública de promoções sem exigir login
#  2. Buscas por categoria com sortBy=sales (mais vendidos = produtos com oferta real)
#     Evitamos sortBy=price&order=asc pois retorna os itens mais baratos, não os mais descontados.
_SEARCH_URLS = [
    "https://shopee.com.br/flash_sale",
    "https://shopee.com.br/search?keyword=smartphone&sortBy=sales&order=desc",
    "https://shopee.com.br/search?keyword=notebook&sortBy=sales&order=desc",
    "https://shopee.com.br/search?keyword=televisao&sortBy=sales&order=desc",
    "https://shopee.com.br/search?keyword=fone+de+ouvido&sortBy=sales&order=desc",
    "https://shopee.com.br/search?keyword=eletrodomestico&sortBy=sales&order=desc",
    "https://shopee.com.br/search?keyword=ar+condicionado&sortBy=sales&order=desc",
]

# Links de produto Shopee terminam com -i.{shopid}.{itemid}
_PRODUCT_PATTERN = r"-i\.(\d+)\.(\d+)$"

# Extrai produtos localizando links pelo padrão -i.{shopid}.{itemid}.
# Shopee usa class names ofuscados — ancoramos nos links (estáveis) e no aria-label.
#
# DOM do flash_sale (confirmado via browser real):
#   - Imagem: CSS background-image em div[style*="susercontent"], NÃO <img src>
#   - Preço: <span>R$</span><strong>48,99</strong> em divs irmãos — nenhuma folha tem "R$48,99" completo
#   - aria-label na <a>: "...menos 23% preço atual R$48,99..." — âncora estável para preço e desconto
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
            const scope = container || link;

            // Imagem: flash_sale usa CSS background-image em div, não <img src>
            const bgDivs = Array.from(scope.querySelectorAll('[style*="background-image"]'));
            const imgDiv = bgDivs.find(el => (el.getAttribute('style') || '').includes('susercontent'));
            const bgUrl  = imgDiv?.getAttribute('style')?.match(/url\\(["']?([^"')]+)["']?\\)/)?.[1] ?? null;
            const image  = bgUrl ? bgUrl.replace(/_tn$/, '') : null;

            // Título: folha de texto com conteúdo significativo (não preço, não badge %)
            const title = Array.from(link.querySelectorAll('*'))
                .filter(el => !el.querySelector('*'))
                .map(el => el.innerText?.trim())
                .find(t => t && t.length > 8 && !t.includes('R$') && !/^-?\\d+%$/.test(t)) ?? null;

            // Caixas de preço: div com exatamente 2 filhos (label "R$" + número decimal)
            // Estrutura: <div><span>R$</span><strong>48,99</strong></div>
            // Ordem no DOM: [0]=preço original (riscado), [last]=preço atual com desconto
            const priceBoxes = Array.from(scope.querySelectorAll('div'))
                .filter(el => {
                    const ch = Array.from(el.children);
                    return ch.length === 2 &&
                           ch.some(c => /^R\\$$/.test(c.innerText?.trim() || '')) &&
                           ch.some(c => /^[\\d.,]+$/.test(c.innerText?.trim() || ''));
                });

            const oldPriceText     = priceBoxes.length > 1 ? priceBoxes[0].innerText?.trim() : null;
            const currentPriceText = priceBoxes.length > 0 ? priceBoxes[priceBoxes.length - 1].innerText?.trim() : null;

            // aria-label da <a> inclui preço atual e desconto — mais estável que class names
            const aria = link.getAttribute('aria-label') || '';
            const priceFromAria = aria.match(/preço atual R\\$\\s*([\\d.,]+)/i)?.[1] ?? null;
            const discFromAria  = aria.match(/menos\\s+(\\d+)%/i)?.[1] ?? null;

            results.push({
                url:       link.href,
                title:     title,
                price:     priceFromAria ? ('R$ ' + priceFromAria) : currentPriceText,
                old_price: oldPriceText,
                discount:  discFromAria ? (discFromAria + '%') : null,
                image:     image,
                item_id:   m[2],
                shop_id:   m[1],
            });
        } catch (e) { console.warn('[shopee-extract]', link?.href, e?.message || String(e)); }
    }
    return results.filter(i => i.title && i.price && i.item_id);
}"""



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

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Aguarda link de produto com padrão -i.{shopid}.{itemid}
                # seletor genérico (a[href]) seria satisfeito pela página de login após redirect
                try:
                    await page.wait_for_selector('a[href*="-i."]', timeout=10000)
                except Exception:
                    final_url = page.url
                    logger.warning(
                        "Shopee: nenhum produto encontrado em {} (URL final: {}).",
                        url, final_url,
                    )
                    continue

                for i in range(5):
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await page.wait_for_timeout(600 + (i % 2) * 200)

                raw: list[dict] = await page.evaluate(_EXTRACT_JS)
                source_name = url.split("/")[-1].split("?")[0] or "deals"
                logger.info("Shopee [{}]: {} cards extraídos.", source_name, len(raw))

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
                    price        = _parse_brl(item.get("price"))
                    old_price    = _parse_brl(item.get("old_price"))

                    if discount_pct is None and old_price and old_price > (price or 0):
                        discount_pct = int((1 - (price or 0) / old_price) * 100)

                    logger.info(
                        "Shopee [dump] {} | '{}' | preço: '{}' → {} | old: '{}' → {} | desc: '{}' → {}%",
                        item_id,
                        (item.get("title") or "")[:45],
                        item.get("price"),     f"{price:.2f}"     if price     is not None else "NONE",
                        item.get("old_price"), f"{old_price:.2f}" if old_price is not None else "NONE",
                        item.get("discount"),  discount_pct if discount_pct is not None else "NONE",
                    )

                    if not price or price <= 0:
                        logger.info("Shopee [dump] {} → DROP: preço inválido ('{}')", item_id, item.get("price"))
                        continue

                    if discount_pct is None:
                        logger.info("Shopee [dump] {} → DROP: desconto não determinado", item_id)
                        continue

                    if discount_pct < MIN_DISCOUNT_PERCENT:
                        logger.info("Shopee [dump] {} → DROP: desconto {}% < mínimo {}%", item_id, discount_pct, MIN_DISCOUNT_PERCENT)
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

        logger.info("Shopee: {} deals válidos após filtros.", len(deals))
        return deals
