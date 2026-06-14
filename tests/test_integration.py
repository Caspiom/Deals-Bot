import pytest
from unittest.mock import AsyncMock, patch

from src.models import Deal
from src.scrapers.mock_scraper import MockScraper
from src.services.dedup_filter import DedupFilter
from src.services.telegram_poster import TelegramPoster
from main import run_cycle


def _fixed_deals() -> list[Deal]:
    return [
        Deal(
            title="Produto Teste A",
            url="https://www.amazon.com.br/dp/MOCK001",
            price=199.90,
            old_price=399.90,
            image_url="https://example.com/img_a.jpg",
            source="mock",
        ),
        Deal(
            title="Produto Teste B",
            url="https://www.kabum.com.br/produto/MOCK002",
            price=99.90,
            old_price=199.90,
            image_url=None,
            source="mock",
        ),
    ]


@pytest.fixture
def dedup(tmp_path):
    f = DedupFilter(db_path=tmp_path / "integration.db")
    yield f
    f.close()


@pytest.fixture
def poster():
    with patch("src.services.telegram_poster.Bot") as mock_bot_class:
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        with patch("asyncio.sleep", new_callable=AsyncMock):
            yield TelegramPoster(), mock_bot


@pytest.mark.asyncio
async def test_pipeline_posts_new_deals(dedup, poster):
    """Deals novos devem ser postados no Telegram."""
    p, bot = poster
    scraper = MockScraper()
    deals = _fixed_deals()

    with patch.object(scraper, "fetch", new=AsyncMock(return_value=deals)):
        await run_cycle(scraper, dedup, p)

    total_posts = bot.send_photo.call_count + bot.send_message.call_count
    assert total_posts == 2


@pytest.mark.asyncio
async def test_pipeline_deduplicates_on_second_run(dedup, poster):
    """Deals já postados não devem ser postados novamente."""
    p, bot = poster
    scraper = MockScraper()
    deals = _fixed_deals()

    with patch.object(scraper, "fetch", new=AsyncMock(return_value=deals)):
        await run_cycle(scraper, dedup, p)  # 1º ciclo — posta 2 deals
        bot.send_photo.reset_mock()
        bot.send_message.reset_mock()
        await run_cycle(scraper, dedup, p)  # 2º ciclo — dedup filtra tudo

    total_posts = bot.send_photo.call_count + bot.send_message.call_count
    assert total_posts == 0


@pytest.mark.asyncio
async def test_pipeline_affiliate_url_is_set(dedup, poster):
    """Após o ciclo, deals devem ter affiliate_url preenchida."""
    p, bot = poster
    scraper = MockScraper()
    deals = _fixed_deals()

    with patch.object(scraper, "fetch", new=AsyncMock(return_value=deals)):
        await run_cycle(scraper, dedup, p)

    assert deals[0].affiliate_url != ""
    assert deals[1].affiliate_url != ""


@pytest.mark.asyncio
async def test_pipeline_continues_after_post_failure(dedup, poster):
    """Falha em um post não deve interromper os demais deals do ciclo."""
    p, bot = poster
    scraper = MockScraper()
    deals = _fixed_deals()

    # Primeiro send_photo levanta exceção, segundo deve ser chamado normalmente
    bot.send_photo.side_effect = [Exception("Timeout"), None]

    with patch.object(scraper, "fetch", new=AsyncMock(return_value=deals)):
        await run_cycle(scraper, dedup, p)

    # send_photo foi chamado para o deal com imagem (falhou)
    # send_message foi chamado para o deal sem imagem (sucesso)
    assert bot.send_message.call_count == 1
