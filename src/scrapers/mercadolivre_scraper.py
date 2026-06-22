import re
from playwright.async_api import Page
from loguru import logger
from src.config.settings import MIN_DISCOUNT_PERCENT
from src.models import Deal
from src.scrapers.playwright_base_scraper import PlaywrightBaseScraper
from src.services.installment_calculator import parse_installment_string
from src.utils.price_parser import parse_brl as _parse_brl

# Página central de Ofertas do Dia — todos os cards com desconto real
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
        const imgEl    = card.querySelector('img[src*="mlstatic"], img[data-src*="mlstatic"]');
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
            image:       (() => {
                const raw = imgEl?.getAttribute('data-src') || imgEl?.src || null;
                // ponytail: upgrade ML CDN thumbnail to original — _2X_ = retina thumb, -F/-I = front/item thumbnail
                return raw ? raw.replace(/_\\d+X_/, '_').replace(/-(F|I)\\.(webp|jpg|png)$/i, '-O.$2') : null;
            })(),
            installment: installEl?.innerText?.trim() ?? null,
            coupon:      couponEl?.innerText?.trim() ?? null,
            coins:       coinsEl?.innerText?.trim() ?? null,
        };
    }).filter(item => item.title && item.url && item.current);
}"""




def _parse_discount_pct(text: str) -> int | None:
    m = re.search(r"(\d+)\s*%\s*OFF", text, re.IGNORECASE)
    return int(m.group(1)) if m else None


class MercadoLivreScraper(PlaywrightBaseScraper):
    name = "mercadolivre"

    async def _scrape(self, page: Page) -> list[Deal]:
        await page.goto(_OFFERS_URL, wait_until="domcontentloaded", timeout=30000)

        # Aguarda o primeiro card aparecer antes de começar a scrollar
        try:
            await page.wait_for_selector('[class*="poly-card"]', timeout=12000)
        except Exception:
            logger.warning("MercadoLivre: nenhum card encontrado — possível bloqueio ou DOM vazio.")
            return []

        # 10 scrolls com delay variável para simular leitura humana
        # ML usa infinite scroll — cada viewport revela ~8 novos cards
        for i in range(10):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(500 + (i % 3) * 200)  # 500-900ms variável

        raw: list[dict] = await page.evaluate(_EXTRACT_JS)
        logger.info("MercadoLivre: {} cards extraídos do DOM.", len(raw))

        deals: list[Deal] = []
        seen_urls: set[str] = set()

        for item in raw:
            try:
                url = item.get("url", "")
                base_url = url.split("#")[0]
                if not base_url or base_url in seen_urls:
                    continue
                seen_urls.add(base_url)

                discount_pct = _parse_discount_pct(item.get("discount") or "")
                price        = _parse_brl(item.get("current") or "")
                old_price_raw = item.get("original") or ""
                old_price    = _parse_brl(old_price_raw) if old_price_raw else None

                if discount_pct is None and old_price and old_price > (price or 0):
                    discount_pct = int((1 - (price or 0) / old_price) * 100)

                pid_m = re.search(r'(MLB-?\d+)', url)
                pid   = pid_m.group(1) if pid_m else url[-20:]
                logger.info(
                    "ML [dump] {} | '{}' | preço: '{}' → {} | old: '{}' → {} | desc: '{}' → {}%",
                    pid,
                    (item.get("title") or "")[:45],
                    item.get("current"),  f"{price:.2f}"     if price     is not None else "NONE",
                    old_price_raw,        f"{old_price:.2f}" if old_price is not None else "NONE",
                    item.get("discount"), discount_pct if discount_pct is not None else "NONE",
                )

                if discount_pct is not None and discount_pct < MIN_DISCOUNT_PERCENT:
                    logger.info("ML [dump] {} → DROP: desconto {}% < mínimo {}%", pid, discount_pct, MIN_DISCOUNT_PERCENT)
                    continue

                if price is None or price <= 0:
                    logger.info("ML [dump] {} → DROP: preço inválido ('{}')", pid, item.get("current"))
                    continue

                parsed = parse_installment_string(item.get("installment") or "")
                n_inst, v_inst = parsed if parsed else (None, None)

                coupon_code = (item.get("coupon") or "").strip() or None
                coins_val = None
                if item.get("coins"):
                    try:
                        coins_val = _parse_brl(item["coins"])
                    except Exception:
                        pass

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

            except Exception as exc:
                logger.warning(
                    "MercadoLivre: erro ao processar item '{}': {}",
                    (item.get("title") or "?")[:40], exc,
                )
                continue

        logger.info("MercadoLivre: {} deals válidos após filtros.", len(deals))
        return deals
