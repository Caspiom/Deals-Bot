import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

import src.utils.logger  # noqa: F401 — aciona setup_logger()

from src.config.settings import SCRAPE_INTERVAL_MINUTES, ENABLED_PUBLISHERS, SHOW_ESTIMATED_INSTALLMENTS, MAX_DEALS_PER_RUN
from src.models import Deal
from src.scrapers.base_scraper import BaseScraper
from src.scrapers.mercadolivre_scraper import MercadoLivreScraper
from src.scrapers.kabum_scraper import KabumScraper
from src.scrapers.aliexpress_scraper import AliExpressScraper
from src.scrapers.amazon_scraper import AmazonScraper
from src.scrapers.magalu_scraper import MagaluScraper
from src.scrapers.shopee_scraper import ShopeeScraper
from src.services.affiliate import convert, is_commissionable
from src.services.copywriter import generate as generate_tagline
from src.services.installment_calculator import estimate as estimate_installments
from src.services.dedup_filter import DedupFilter
from src.publishers.base_publisher import BasePublisher
from src.publishers.telegram_publisher import TelegramPublisher


def _build_publishers() -> list[BasePublisher]:
    publishers: list[BasePublisher] = []

    if "telegram" in ENABLED_PUBLISHERS:
        publishers.append(TelegramPublisher())

    if "x" in ENABLED_PUBLISHERS:
        from src.publishers.x_publisher import XPublisher
        publishers.append(XPublisher())

    if "instagram" in ENABLED_PUBLISHERS:
        from src.publishers.instagram_publisher import InstagramPublisher
        publishers.append(InstagramPublisher())

    if "discord" in ENABLED_PUBLISHERS:
        from src.publishers.discord_publisher import DiscordPublisher
        publishers.append(DiscordPublisher())

    if not publishers:
        raise RuntimeError("Nenhum publisher configurado. Verifique ENABLED_PUBLISHERS no .env.")

    logger.info("Publishers ativos: {}", [p.name for p in publishers])
    return publishers


async def run_cycle(
    scrapers: list[BaseScraper],
    dedup: DedupFilter,
    publishers: list[BasePublisher],
) -> None:
    logger.info(">>> Iniciando ciclo | scrapers={}", [s.name for s in scrapers])

    # busca em todos os scrapers em paralelo
    results = await asyncio.gather(*[s.fetch() for s in scrapers], return_exceptions=True)

    all_deals: list[Deal] = []
    for scraper, result in zip(scrapers, results):
        if isinstance(result, Exception):
            logger.exception("Scraper '{}' falhou: {}", scraper.name, result)
        else:
            all_deals.extend(result)

    # registra histórico de preço para TODOS os deals coletados (antes do filtro de dedup)
    dedup.record_prices(all_deals)

    # Descarta deals de agregadores que retêm a comissão de afiliado (diretriz 4.11)
    monetizable = [d for d in all_deals if is_commissionable(d.url)]
    blocked = len(all_deals) - len(monetizable)
    if blocked:
        logger.warning("⛔ {} deal(s) bloqueado(s) por URL de agregador (sem comissão nossa).", blocked)

    new_deals   = [d for d in monetizable if dedup.is_new(d)]
    hot_reposts = [d for d in monetizable if not dedup.is_new(d) and dedup.can_repost(d)]
    to_publish  = new_deals + hot_reposts
    logger.info(
        "{} deal(s) coletado(s) — {} bloqueado(s) — {} novo(s), {} re-post(s) → publicando em {} plataforma(s).",
        len(all_deals), blocked, len(new_deals), len(hot_reposts), len(publishers),
    )

    posts_sent = 0
    for deal in to_publish:
        if posts_sent >= MAX_DEALS_PER_RUN:
            logger.info(
                "Limite de {} postagens/ciclo atingido — {} deal(s) inédito(s) guardados para o próximo ciclo.",
                MAX_DEALS_PER_RUN, len(to_publish) - posts_sent,
            )
            break

        deal.affiliate_url = convert(deal.url)
        deal.tagline = generate_tagline(deal)
        deal.is_price_low = dedup.is_lowest_price(deal)
        if deal.installments is None and SHOW_ESTIMATED_INSTALLMENTS:
            est = estimate_installments(deal.price)
            if est:
                deal.installments, deal.installment_value = est
        published_any = False
        for publisher in publishers:
            try:
                await publisher.publish(deal)
                published_any = True
            except Exception as exc:
                logger.error("[{}] Falha ao publicar '{}': {}", publisher.name, deal.title[:40], exc)
        if not published_any:
            logger.warning(
                "Deal marcado como visto apesar de falha em todos os publishers: {}",
                deal.title[:60],
            )
        dedup.mark_seen(deal)
        if published_any:
            posts_sent += 1

    logger.info("<<< Ciclo concluído.")


async def main() -> None:
    logger.info("Deals Bot iniciando...")

    # Apenas scrapers de lojas diretas — ver diretriz 4.11 em docs/context.md
    scrapers: list[BaseScraper] = [
        MercadoLivreScraper(),
        KabumScraper(),
        MagaluScraper(),
        AliExpressScraper(),
        AmazonScraper(),
        ShopeeScraper(),
    ]
    dedup = DedupFilter()
    publishers = _build_publishers()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_cycle,
        trigger="interval",
        minutes=SCRAPE_INTERVAL_MINUTES,
        args=[scrapers, dedup, publishers],
        next_run_time=datetime.now(),
        max_instances=1,
        misfire_grace_time=60,
    )
    scheduler.start()

    logger.info(
        "Scheduler ativo — ciclos a cada {} minuto(s). Ctrl+C para encerrar.",
        SCRAPE_INTERVAL_MINUTES,
    )

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown(wait=False)
        dedup.close()
        for p in publishers:
            if hasattr(p, "close"):
                await p.close()
        logger.info("Bot encerrado.")


if __name__ == "__main__":
    asyncio.run(main())
