import re
from playwright.async_api import Page
from loguru import logger
from src.config.settings import MIN_DISCOUNT_PERCENT
from src.models import Deal
from src.scrapers.playwright_base_scraper import PlaywrightBaseScraper
from src.services.installment_calculator import parse_installment_string
from src.utils.price_parser import parse_brl as _parse_brl

# A API REST do KaBuM ignora sort/filter sem autenticação interna.
# A página Super Ofertas carrega os produtos via CSR — Playwright resolve isso.
_OFFERS_URL = "https://www.kabum.com.br/produtos/super-ofertas"
_PRODUCT_BASE = "https://www.kabum.com.br"

# Âncora em links de produto /produto/{numeric_id}/ — padrão estável entre redesigns.
# Extrai dados subindo ao container pai (article ou li).
_EXTRACT_JS = """() => {
    const productPattern = /\\/produto\\/(\\d+)\\//;
    const seen = new Set();

    const links = Array.from(document.querySelectorAll('a[href*="/produto/"]'))
        .filter(a => productPattern.test(a.pathname));

    return links
        .filter(a => {
            const m = a.pathname.match(productPattern);
            if (!m || seen.has(m[1])) return false;
            seen.add(m[1]);
            return true;
        })
        .map(link => {
            const m = link.pathname.match(productPattern);
            // KaBuM usa o próprio <a> como card — scope = link evita capturar cards vizinhos
            const scope = link;

            // Título: texto folha com conteúdo significativo (não preço, não ícone)
            // length > 10 elimina ícones de 1 char (Material Icons, emojis)
            const title = Array.from(scope.querySelectorAll('*'))
                .filter(el => !el.querySelector('*'))
                .map(el => el.innerText?.trim())
                .find(t => t && t.length > 10 && !t.includes('R$') &&
                           !/^(Desconto|Restam|Frete|No\\s|MEGA|Avalia|Adicionar)/i.test(t)) ?? null;

            // Preço antigo: elemento FOLHA cuja innerText COMPLETA é "R$ X.XXX,XX"
            // (KaBuM mostra o preço cheio sem estilo especial, riscado via CSS)
            const completePrices = Array.from(scope.querySelectorAll('*'))
                .filter(el => !el.querySelector('*'))
                .map(el => {
                    const t = el.innerText?.trim() || '';
                    const mo = t.match(/^R\\$[\\s\\u00a0]*(\\d[\\d.]*,\\d{2})$/);
                    return mo ? parseFloat(mo[1].replace(/\\./g,'').replace(',','.')) : null;
                })
                .filter(v => v && v > 0);

            // Preço atual: estrutura DIVIDIDA "R$" + "2.299,99" em elementos irmãos
            // KaBuM estiliza "R$" em span separado do valor numérico
            const splitPrices = Array.from(scope.querySelectorAll('*'))
                .filter(el => {
                    const ch = Array.from(el.children);
                    return ch.some(c => c.innerText?.trim() === 'R$') &&
                           ch.some(c => /^\\d[\\d.,]*$/.test(c.innerText?.trim() || ''));
                })
                .map(el => {
                    const numCh = Array.from(el.children)
                        .find(c => /^\\d[\\d.,]*$/.test(c.innerText?.trim() || ''));
                    const t = numCh?.innerText?.trim() || '';
                    return t ? parseFloat(t.replace(/\\./g,'').replace(',','.')) : null;
                })
                .filter(v => v && v > 0);

            // currentPrice = menor valor split (preço com desconto, em destaque)
            // oldPrice     = maior valor complete (preço original, riscado via CSS)
            const currentPrice = splitPrices.length ? Math.min(...splitPrices) :
                                 completePrices.length ? Math.min(...completePrices) : null;
            const oldPrice = completePrices.length && splitPrices.length
                ? Math.max(...completePrices)
                : completePrices.length > 1 ? Math.max(...completePrices) : null;

            // Parcelas: "No PIX ou Nx de R$ Y"
            const installEl = Array.from(scope.querySelectorAll('*'))
                .find(el => !el.querySelector('*') && /\\dx\\s+de\\s+R\\$|sem\\s+juros/i.test(el.innerText ?? ''));

            // Imagem: primeira <img> com src http
            const imgEl = Array.from(scope.querySelectorAll('img[src]'))
                .find(img => img.src?.startsWith('http'));

            return {
                id:          m ? m[1] : null,
                url:         link.href,
                title:       title,
                price:       currentPrice !== null ? String(currentPrice) : null,
                old_price:   oldPrice !== null ? String(oldPrice) : null,
                discount:    null,
                image:       imgEl?.src ?? null,
                installment: installEl?.innerText?.trim() ?? null,
            };
        }).filter(i => i.id && i.title && i.price);
}"""


def _parse_discount_pct(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"(\d+)\s*%", text)
    return int(m.group(1)) if m else None


class KabumScraper(PlaywrightBaseScraper):
    name = "kabum"

    async def _scrape(self, page: Page) -> list[Deal]:
        await page.goto(_OFFERS_URL, wait_until="domcontentloaded", timeout=30000)

        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        try:
            await page.wait_for_selector('a[href*="/produto/"]', timeout=20000)
        except Exception:
            logger.warning("KaBuM: nenhum link de produto encontrado — DOM vazio ou bloqueio.")
            return []

        for i in range(15):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(500 + (i % 4) * 150)

        raw: list[dict] = await page.evaluate(_EXTRACT_JS)
        logger.info("KaBuM: {} cards extraídos do DOM.", len(raw))

        seen_ids: set[str] = set()
        deals: list[Deal] = []

        for item in raw:
            try:
                pid = item.get("id", "")
                if not pid or pid in seen_ids:
                    continue
                seen_ids.add(pid)

                price        = _parse_brl(item.get("price"))
                old_price    = _parse_brl(item.get("old_price"))
                discount_pct = _parse_discount_pct(item.get("discount"))

                if discount_pct is None and old_price and old_price > (price or 0):
                    discount_pct = int((1 - (price or 0) / old_price) * 100)

                logger.info(
                    "KaBuM [dump] {} | '{}' | preço: '{}' → {} | old: '{}' → {} | desc: '{}' → {}%",
                    pid,
                    (item.get("title") or "")[:45],
                    item.get("price"),     f"{price:.2f}"     if price     is not None else "NONE",
                    item.get("old_price"), f"{old_price:.2f}" if old_price is not None else "NONE",
                    item.get("discount"),  discount_pct if discount_pct is not None else "NONE",
                )

                if price is None or price <= 0:
                    logger.info("KaBuM [dump] {} → DROP: preço inválido", pid)
                    continue

                if discount_pct is None:
                    logger.info("KaBuM [dump] {} → DROP: desconto não determinado", pid)
                    continue

                if discount_pct < MIN_DISCOUNT_PERCENT:
                    logger.info("KaBuM [dump] {} → DROP: desconto {}% < mínimo {}%", pid, discount_pct, MIN_DISCOUNT_PERCENT)
                    continue

                parsed = parse_installment_string(item.get("installment") or "")
                n_inst, v_inst = parsed if parsed else (None, None)

                image = (item.get("image") or "").split("?")[0].replace("_m.jpg", "_g.jpg")
                image_url = image if image.startswith("http") else None

                deals.append(Deal(
                    title=item["title"],
                    url=item["url"],
                    price=price,
                    old_price=old_price if old_price and old_price > price else None,
                    discount_pct=discount_pct,
                    image_url=image_url,
                    source=self.name,
                    store="KaBuM",
                    installments=n_inst,
                    installment_value=v_inst,
                ))

            except Exception as exc:
                logger.warning(
                    "KaBuM: erro ao processar item id={}: {}",
                    item.get("id", "?"), exc,
                )
                continue

        logger.info("KaBuM: {} deals válidos após filtros.", len(deals))
        return deals
