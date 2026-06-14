import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

import src.utils.logger  # noqa: F401 — aciona setup_logger() como efeito colateral

from src.config.settings import SCRAPE_INTERVAL_MINUTES
from src.models import Deal
from src.scrapers.base_scraper import BaseScraper
from src.scrapers.mock_scraper import MockScraper
from src.services.affiliate import convert
from src.services.dedup_filter import DedupFilter
from src.services.telegram_poster import TelegramPoster


async def run_cycle(
    scraper: BaseScraper,
    dedup: DedupFilter,
    poster: TelegramPoster,
) -> None:
    logger.info(">>> Iniciando ciclo | scraper={}", scraper.name)

    try:
        deals: list[Deal] = await scraper.fetch()
    except Exception as exc:
        logger.error("Falha ao buscar deals: {}", exc)
        return

    new_deals = [d for d in deals if dedup.is_new(d)]
    logger.info(
        "Encontrados {} deal(s) — {} novo(s) para postar.",
        len(deals),
        len(new_deals),
    )

    for deal in new_deals:
        deal.affiliate_url = convert(deal.url)
        try:
            await poster.send(deal)
            dedup.mark_seen(deal)
        except Exception as exc:
            logger.error("Falha ao postar '{}': {}", deal.title[:50], exc)

    logger.info("<<< Ciclo concluído.")


async def main() -> None:
    logger.info("Deals Bot iniciando...")

    scraper = MockScraper()
    dedup = DedupFilter()
    poster = TelegramPoster()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_cycle,
        trigger="interval",
        minutes=SCRAPE_INTERVAL_MINUTES,
        args=[scraper, dedup, poster],
        next_run_time=datetime.now(),  # executa imediatamente no startup
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
        logger.info("Bot encerrado.")


if __name__ == "__main__":
    asyncio.run(main())
