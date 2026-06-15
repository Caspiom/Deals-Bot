import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

import src.utils.logger  # noqa: F401 — aciona setup_logger()

from src.config.settings import SCRAPE_INTERVAL_MINUTES, ENABLED_PUBLISHERS
from src.models import Deal
from src.scrapers.base_scraper import BaseScraper
from src.scrapers.pelando_scraper import PelandoScraper
from src.scrapers.promobit_scraper import PromobitScraper
from src.scrapers.mercadolivre_scraper import MercadoLivreScraper
from src.scrapers.kabum_scraper import KabumScraper
from src.services.affiliate import convert
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
            logger.error("Scraper '{}' falhou: {}", scraper.name, result)
        else:
            all_deals.extend(result)

    new_deals   = [d for d in all_deals if dedup.is_new(d)]
    hot_reposts = [d for d in all_deals if not dedup.is_new(d) and dedup.can_repost(d)]
    to_publish  = new_deals + hot_reposts
    logger.info(
        "{} deal(s) coletado(s) — {} novo(s), {} re-post(s) → publicando em {} plataforma(s).",
        len(all_deals), len(new_deals), len(hot_reposts), len(publishers),
    )

    for deal in to_publish:
        deal.affiliate_url = convert(deal.url)
        for publisher in publishers:
            try:
                await publisher.publish(deal)
            except Exception as exc:
                logger.error("[{}] Falha ao publicar '{}': {}", publisher.name, deal.title[:40], exc)
        dedup.mark_seen(deal)

    logger.info("<<< Ciclo concluído.")


async def main() -> None:
    logger.info("Deals Bot iniciando...")

    scrapers: list[BaseScraper] = [PelandoScraper(), PromobitScraper(), MercadoLivreScraper(), KabumScraper()]
    dedup = DedupFilter()
    publishers = _build_publishers()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_cycle,
        trigger="interval",
        minutes=SCRAPE_INTERVAL_MINUTES,
        args=[scrapers, dedup, publishers],
        next_run_time=datetime.now(),
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
