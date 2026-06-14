import pytest
from src.scrapers.mock_scraper import MockScraper
from src.config.settings import MIN_DISCOUNT_PERCENT, MAX_DEALS_PER_RUN


@pytest.fixture
def scraper():
    return MockScraper()


@pytest.mark.asyncio
async def test_fetch_returns_list(scraper):
    deals = await scraper.fetch()
    assert isinstance(deals, list)


@pytest.mark.asyncio
async def test_fetch_respects_max_deals(scraper):
    deals = await scraper.fetch()
    assert len(deals) <= MAX_DEALS_PER_RUN


@pytest.mark.asyncio
async def test_all_deals_meet_min_discount(scraper):
    deals = await scraper.fetch()
    for deal in deals:
        assert deal.discount_pct is not None
        assert deal.discount_pct >= MIN_DISCOUNT_PERCENT


@pytest.mark.asyncio
async def test_deals_have_required_fields(scraper):
    deals = await scraper.fetch()
    for deal in deals:
        assert deal.title
        assert deal.url.startswith("https://")
        assert deal.price > 0
        assert deal.old_price is not None and deal.old_price > deal.price
        assert deal.source == "mock"


@pytest.mark.asyncio
async def test_scraper_name():
    assert MockScraper.name == "mock"
