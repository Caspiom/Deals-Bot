import pytest
from unittest.mock import AsyncMock
from src.scrapers.kabum_scraper import KabumScraper, _parse_discount_pct
from src.config.settings import MIN_DISCOUNT_PERCENT

_MOCK_CARDS = [
    {
        "id": "101",
        "url": "https://www.kabum.com.br/produto/101/placa-rtx-4070-super",
        "title": "Placa de Vídeo RTX 4070 Super 12GB",
        "price": "1800.0",
        "old_price": "3000.0",
        "discount": None,
        "image": "https://images.kabum.com.br/101/m.jpg",
        "installment": "10x de R$ 180,00 sem juros",
    },
    {
        "id": "102",
        "url": "https://www.kabum.com.br/produto/102/ssd-samsung-980-pro",
        "title": "SSD NVMe 1TB Samsung 980 Pro",
        "price": "420.0",
        "old_price": "600.0",
        "discount": None,
        "image": "https://images.kabum.com.br/102/m.jpg",
        "installment": None,
    },
    {
        "id": "103",
        "url": "https://www.kabum.com.br/produto/103/cabo-hdmi",
        "title": "Cabo HDMI 2.0 1.5m",
        "price": "28.0",
        "old_price": "30.0",
        "discount": None,
        "image": None,
        "installment": None,
    },
]


def _make_page_mock(cards: list[dict]) -> AsyncMock:
    page = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    async def evaluate_side_effect(expr):
        if "scrollBy" in expr:
            return None
        return cards

    page.evaluate = AsyncMock(side_effect=evaluate_side_effect)
    return page


@pytest.fixture
def scraper():
    return KabumScraper()


@pytest.fixture
def mock_page():
    return _make_page_mock(_MOCK_CARDS)


# ── _parse_discount_pct ───────────────────────────────────────────────────────

def test_parse_discount_negative_badge():
    assert _parse_discount_pct("-40%") == 40

def test_parse_discount_plain():
    assert _parse_discount_pct("40 %") == 40

def test_parse_discount_none():
    assert _parse_discount_pct(None) is None

def test_parse_discount_no_match():
    assert _parse_discount_pct("sem desconto") is None


# ── _scrape ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scrape_returns_deals(scraper, mock_page):
    deals = await scraper._scrape(mock_page)
    assert len(deals) > 0


@pytest.mark.asyncio
async def test_scrape_filters_low_discount(scraper, mock_page):
    deals = await scraper._scrape(mock_page)
    for deal in deals:
        assert deal.discount_pct >= MIN_DISCOUNT_PERCENT


@pytest.mark.asyncio
async def test_scrape_maps_fields_correctly(scraper, mock_page):
    deals = await scraper._scrape(mock_page)
    rtx = next(d for d in deals if "RTX" in d.title)
    assert rtx.price == 1800.0
    assert rtx.old_price == 3000.0
    assert rtx.discount_pct == 40
    assert rtx.source == "kabum"
    assert "kabum.com.br/produto/101" in rtx.url
    assert "images.kabum.com.br" in rtx.image_url


@pytest.mark.asyncio
async def test_scrape_with_installment(scraper, mock_page):
    deals = await scraper._scrape(mock_page)
    rtx = next(d for d in deals if "RTX" in d.title)
    assert rtx.installments == 10
    assert rtx.installment_value == 180.0


@pytest.mark.asyncio
async def test_scrape_deduplicates_by_id(scraper):
    duplicated = _MOCK_CARDS[:1] + _MOCK_CARDS[:1]
    deals = await scraper._scrape(_make_page_mock(duplicated))
    assert len(deals) == 1


@pytest.mark.asyncio
async def test_scrape_calculates_pct_from_prices_when_discount_null(scraper):
    cards = [{
        "id": "201",
        "url": "https://www.kabum.com.br/produto/201/headset-g435",
        "title": "Headset Logitech G435",
        "price": "300.0",
        "old_price": "500.0",
        "discount": None,
        "image": None,
        "installment": None,
    }]
    deals = await scraper._scrape(_make_page_mock(cards))
    assert len(deals) == 1
    assert deals[0].discount_pct == 40


@pytest.mark.asyncio
async def test_scrape_skips_item_without_price(scraper):
    cards = [{
        "id": "301",
        "url": "https://www.kabum.com.br/produto/301/produto-sem-preco",
        "title": "Produto sem preço",
        "price": None,
        "old_price": None,
        "discount": None,
        "image": None,
        "installment": None,
    }]
    deals = await scraper._scrape(_make_page_mock(cards))
    assert deals == []


@pytest.mark.asyncio
async def test_scrape_returns_empty_when_selector_not_found(scraper):
    page = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))
    deals = await scraper._scrape(page)
    assert deals == []


@pytest.mark.asyncio
async def test_scrape_skips_invalid_image(scraper):
    cards = [{
        "id": "401",
        "url": "https://www.kabum.com.br/produto/401/produto-sem-img",
        "title": "Produto sem imagem válida",
        "price": "999.0",
        "old_price": "1500.0",
        "discount": None,
        "image": "data:image/gif;base64,R0lGOD...",
        "installment": None,
    }]
    deals = await scraper._scrape(_make_page_mock(cards))
    assert len(deals) == 1
    assert deals[0].image_url is None


@pytest.mark.asyncio
async def test_scrape_source_and_store(scraper, mock_page):
    deals = await scraper._scrape(mock_page)
    for deal in deals:
        assert deal.source == "kabum"
        assert deal.store == "KaBuM"
