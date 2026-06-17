import pytest
from unittest.mock import AsyncMock
from src.scrapers.amazon_scraper import AmazonScraper, _parse_brl, _parse_discount_pct
from src.config.settings import MIN_DISCOUNT_PERCENT, MAX_DEALS_PER_RUN

# ── dados de teste ────────────────────────────────────────────────────────────

_MOCK_CARDS = [
    {
        "url":       "https://www.amazon.com.br/Notebook-Dell-Inspiron/dp/B0CX12345Y/ref=sr_1_1",
        "id":        "B0CX12345Y",
        "title":     "Notebook Dell Inspiron 15 8GB 256GB SSD",
        "price":     "R$ 2.499,00",
        "old_price": "R$ 4.999,00",
        "discount":  "-50%",
        "image":     "https://m.media-amazon.com/images/I/abc.jpg",
    },
    {
        "url":       "https://www.amazon.com.br/dp/B0AB67890Z",
        "id":        "B0AB67890Z",
        "title":     "Smart TV Samsung 55\" 4K QLED",
        "price":     "R$ 1.899,00",
        "old_price": "R$ 3.200,00",
        "discount":  "41%",
        "image":     "https://m.media-amazon.com/images/I/xyz.jpg",
    },
    {
        "url":       "https://www.amazon.com.br/dp/B0LOWDISCT",
        "id":        "B0LOWDISCT",
        "title":     "Produto com desconto abaixo do mínimo",
        "price":     "R$ 99,00",
        "old_price": "R$ 101,00",
        "discount":  "2%",
        "image":     None,
    },
    {
        "url":       "https://www.amazon.com.br/dp/B0NOPRICE0",
        "id":        "B0NOPRICE0",
        "title":     "Produto sem preço",
        "price":     None,
        "old_price": None,
        "discount":  None,
        "image":     None,
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
    return AmazonScraper()


@pytest.fixture
def mock_page():
    return _make_page_mock(_MOCK_CARDS)


# ── _parse_brl ────────────────────────────────────────────────────────────────

def test_parse_brl_standard():
    assert _parse_brl("R$ 2.499,00") == 2499.0

def test_parse_brl_nonbreaking_space():
    assert _parse_brl("R$\xa02.499,00") == 2499.0

def test_parse_brl_no_decimal():
    assert _parse_brl("R$ 1.000") == 1000.0

def test_parse_brl_none():
    assert _parse_brl(None) is None

def test_parse_brl_invalid():
    assert _parse_brl("grátis") is None


# ── _parse_discount_pct ───────────────────────────────────────────────────────

def test_parse_discount_negative_badge():
    assert _parse_discount_pct("-50%") == 50

def test_parse_discount_plain():
    assert _parse_discount_pct("41%") == 41

def test_parse_discount_off_suffix():
    assert _parse_discount_pct("30% OFF") == 30

def test_parse_discount_none():
    assert _parse_discount_pct(None) is None

def test_parse_discount_no_number():
    assert _parse_discount_pct("Oferta") is None


# ── _scrape ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scrape_returns_deals(scraper, mock_page):
    deals = await scraper._scrape(mock_page)
    assert len(deals) > 0

@pytest.mark.asyncio
async def test_scrape_maps_fields_correctly(scraper, mock_page):
    deals = await scraper._scrape(mock_page)
    dell = next(d for d in deals if "Dell" in d.title)
    assert dell.price == 2499.0
    assert dell.old_price == 4999.0
    assert dell.discount_pct == 50
    assert dell.source == "amazon"
    assert dell.store == "Amazon"
    assert "amazon.com.br" in dell.url

@pytest.mark.asyncio
async def test_scrape_filters_low_discount(scraper, mock_page):
    deals = await scraper._scrape(mock_page)
    for deal in deals:
        if deal.discount_pct is not None:
            assert deal.discount_pct >= MIN_DISCOUNT_PERCENT

@pytest.mark.asyncio
async def test_scrape_skips_missing_price(scraper):
    page = _make_page_mock([_MOCK_CARDS[3]])  # B0NOPRICE0
    deals = await scraper._scrape(page)
    assert all("B0NOPRICE0" not in d.url for d in deals)

@pytest.mark.asyncio
async def test_scrape_deduplicates_by_asin(scraper):
    dup = [_MOCK_CARDS[0], {**_MOCK_CARDS[0]}]
    page = _make_page_mock(dup)
    deals = await scraper._scrape(page)
    assert len([d for d in deals if "B0CX12345Y" in d.url]) == 1

@pytest.mark.asyncio
async def test_scraper_returns_all_qualified_deals(scraper):
    # O cap pertence ao main.py; o scraper deve devolver TODOS os deals válidos.
    many = [
        {
            "url":       f"https://www.amazon.com.br/dp/B{i:09d}",
            "id":        f"B{i:09d}",
            "title":     f"Produto {i}",
            "price":     "R$ 100,00",
            "old_price": "R$ 200,00",
            "discount":  "-50%",
            "image":     None,
        }
        for i in range(MAX_DEALS_PER_RUN * 4)
    ]
    page = _make_page_mock(many)
    deals = await scraper._scrape(page)
    assert len(deals) == MAX_DEALS_PER_RUN * 4

@pytest.mark.asyncio
async def test_scrape_calculates_discount_from_prices(scraper):
    card = {**_MOCK_CARDS[0], "discount": None}
    page = _make_page_mock([card])
    deals = await scraper._scrape(page)
    assert deals[0].discount_pct == 50

@pytest.mark.asyncio
async def test_scrape_bad_item_does_not_break_batch(scraper):
    bad = {"url": None, "id": "B0BADITEM1", "title": "Mal formado", "price": "invalido", "old_price": None, "discount": None, "image": None}
    page = _make_page_mock([bad, _MOCK_CARDS[0]])
    deals = await scraper._scrape(page)
    assert any("Dell" in d.title for d in deals)
