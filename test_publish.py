"""
Script descartável para validar links do botão inline no Telegram.
Roda uma vez, sem dedup, sem scheduler. Deletar após o teste.

Uso: uv run python test_publish.py
"""
import asyncio
from src.scrapers.kabum_scraper import KabumScraper
from src.services.affiliate import convert
from src.publishers.telegram_publisher import TelegramPublisher

_N_DEALS = 3


async def main() -> None:
    print("Buscando deals reais do KaBuM...")
    deals = await KabumScraper().fetch()

    if not deals:
        print("Nenhum deal retornado.")
        return

    publisher = TelegramPublisher()
    for deal in deals[:_N_DEALS]:
        deal.affiliate_url = convert(deal.url)
        print(f"Enviando: {deal.title[:60]}")
        print(f"  URL do botão → {deal.affiliate_url}")
        await publisher.publish(deal)

    print(f"\n{min(_N_DEALS, len(deals))} deal(s) enviado(s). Confira o canal.")


asyncio.run(main())
