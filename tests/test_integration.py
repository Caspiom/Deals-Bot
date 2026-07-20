import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.models import Deal
from src.scrapers.mock_scraper import MockScraper
from src.services.dedup_filter import DedupFilter
from src.publishers.telegram_publisher import TelegramPublisher
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
def publisher():
    with patch("src.publishers.telegram_publisher.Bot") as mock_bot_class:
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        with patch("asyncio.sleep", new_callable=AsyncMock):
            yield TelegramPublisher(), mock_bot


@pytest.mark.asyncio
async def test_pipeline_posts_new_deals(dedup, publisher):
    p, bot = publisher
    scraper = MockScraper()
    deals = _fixed_deals()

    with patch.object(scraper, "fetch", new=AsyncMock(return_value=deals)):
        await run_cycle([scraper], dedup, [p])

    assert bot.send_photo.call_count + bot.send_message.call_count == 2


@pytest.mark.asyncio
async def test_pipeline_deduplicates_on_second_run(dedup, publisher):
    p, bot = publisher
    scraper = MockScraper()
    deals = _fixed_deals()

    with patch.object(scraper, "fetch", new=AsyncMock(return_value=deals)):
        await run_cycle([scraper], dedup, [p])
        bot.send_photo.reset_mock()
        bot.send_message.reset_mock()
        await run_cycle([scraper], dedup, [p])

    assert bot.send_photo.call_count + bot.send_message.call_count == 0


@pytest.mark.asyncio
async def test_pipeline_affiliate_url_is_set(dedup, publisher):
    p, _ = publisher
    scraper = MockScraper()
    deals = _fixed_deals()

    with patch.object(scraper, "fetch", new=AsyncMock(return_value=deals)):
        await run_cycle([scraper], dedup, [p])

    assert all(d.affiliate_url for d in deals)


@pytest.mark.asyncio
async def test_pipeline_continues_after_post_failure(dedup, publisher):
    p, bot = publisher
    scraper = MockScraper()
    deals = _fixed_deals()

    bot.send_photo.side_effect = [Exception("Timeout"), None]

    with patch.object(scraper, "fetch", new=AsyncMock(return_value=deals)):
        await run_cycle([scraper], dedup, [p])

    assert bot.send_message.call_count == 1


@pytest.mark.asyncio
async def test_pipeline_parallel_scrapers(dedup, publisher):
    """Múltiplos scrapers em paralelo consolidam deals corretamente."""
    p, bot = publisher
    scraper_a = MockScraper()
    scraper_b = MockScraper()
    deals_a = [_fixed_deals()[0]]
    deals_b = [_fixed_deals()[1]]

    with patch.object(scraper_a, "fetch", new=AsyncMock(return_value=deals_a)), \
         patch.object(scraper_b, "fetch", new=AsyncMock(return_value=deals_b)):
        await run_cycle([scraper_a, scraper_b], dedup, [p])

    assert bot.send_photo.call_count + bot.send_message.call_count == 2


# ── diversidade de lojas no feed ─────────────────────────────────────────────

def test_interleave_alternates_stores():
    """Loja de alto volume não pode monopolizar o ciclo (AliExpress vs nacionais)."""
    from main import _interleave_by_store
    from src.models import Deal

    deals = (
        [Deal(title=f"ali {i}", url=f"https://a/{i}", price=10.0,
              discount_pct=90 - i, store="AliExpress") for i in range(10)]
        + [Deal(title="kabum", url="https://k/1", price=10.0, discount_pct=20, store="KaBuM")]
        + [Deal(title="ml", url="https://m/1", price=10.0, discount_pct=15, store="Mercado Livre")]
    )
    top3 = [d.store for d in _interleave_by_store(deals)[:3]]
    assert set(top3) == {"AliExpress", "KaBuM", "Mercado Livre"}


def test_interleave_orders_each_store_by_discount():
    from main import _interleave_by_store
    from src.models import Deal

    deals = [
        Deal(title="a", url="https://a/1", price=10.0, discount_pct=30, store="X"),
        Deal(title="b", url="https://a/2", price=10.0, discount_pct=70, store="X"),
    ]
    assert [d.discount_pct for d in _interleave_by_store(deals)] == [70, 30]
