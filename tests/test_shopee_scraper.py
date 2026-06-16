import pytest
from unittest.mock import AsyncMock
from src.scrapers.shopee_scraper import ShopeeScraper, _parse_brl, _parse_discount_pct
from src.config.settings import MIN_DISCOUNT_PERCENT, MAX_DEALS_PER_RUN

_MOCK_CARDS = [
    {
        "url": "https://shopee.com.br/smartphone-samsung-a54-i.123456.9876543",
        "title": "Smartphone Samsung Galaxy A54 128GB",
        "price": "R$\xa0899,90",
        "old_price": "R$\xa01.499,90",
        "discount": "-40%",
        "image": "https://cf.shopee.com.br/file/br-abc123",
        "item_id": "9876543",
        "shop_id": "123456",
    },
    {
        "url": "https://shopee.com.br/notebook-dell-i.111.222",
        "title": "Notebook Dell Inspiron 15 16GB",
        "price": "R$\xa02.499,00",
        "old_price": "R$\xa03.999,00",
        "discount": "-37%",
        "image": "https://cf.shopee.com.br/file/br-xyz789",
        "item_id": "222",
        "shop_id": "111",
    },
    {
        "url": "https://shopee.com.br/produto-barato-i.999.888",
        "title": "Produto com desconto abaixo do mínimo",
        "price": "R$\xa049,90",
        "old_price": "R$\xa051,00",
        "discount": "-2%",
        "image": None,
        "item_id": "888",
        "shop_id": "999",
    },
    {
        "url": "https://shopee.com.br/produto-sem-preco-antigo-i.333.444",
        "title": "Produto sem preço antigo mas com desconto calculável",
        "price": "R$\xa0100,00",
        "old_price": None,
        "discount": None,
        "image": None,
        "item_id": "444",
        "shop_id": "333",
    },
]


def _make_page_mock(cards: list[dict]) -> AsyncMock:
    page = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    async def evaluate_side_effect(expr):
        if "scrollBy" in expr:
            return None
        return cards

    page.evaluate = AsyncMock(side_effect=evaluate_side_effect)
    return page


@pytest.fixture
def scraper():
    return ShopeeScraper()


@pytest.fixture
def mock_page():
    return _make_page_mock(_MOCK_CARDS)


# ── _parse_brl ───────────────────────────────────────────────────────────────

def test_parse_brl_with_nonbreaking_space():
    assert _parse_brl("R$\xa0899,90") == 899.90

def test_parse_brl_thousands():
    assert _parse_brl("R$\xa01.499,90") == 1499.90

def test_parse_brl_none():
    assert _parse_brl(None) is None

def test_parse_brl_invalid():
    assert _parse_brl("grátis") is None


# ── _parse_discount_pct ──────────────────────────────────────────────────────

def test_parse_discount_negative_badge():
    assert _parse_discount_pct("-40%") == 40

def test_parse_discount_plain():
    assert _parse_discount_pct("37%") == 37

def test_parse_discount_none():
    assert _parse_discount_pct(None) is None


# ── _scrape ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scrape_returns_deals(scraper, mock_page):
    deals = await scraper._scrape(mock_page)
    assert len(deals) > 0


@pytest.mark.asyncio
async def test_scrape_filters_low_discount(scraper, mock_page):
    deals = await scraper._scrape(mock_page)
    for deal in deals:
        if deal.discount_pct is not None:
            assert deal.discount_pct >= MIN_DISCOUNT_PERCENT


@pytest.mark.asyncio
async def test_scrape_maps_fields_correctly(scraper, mock_page):
    deals = await scraper._scrape(mock_page)
    samsung = next(d for d in deals if "Samsung" in d.title)
    assert samsung.price == 899.90
    assert samsung.old_price == 1499.90
    assert samsung.discount_pct == 40
    assert samsung.source == "shopee"
    assert samsung.store == "Shopee"
    assert "shopee.com.br" in samsung.url


@pytest.mark.asyncio
async def test_scrape_deduplicates_by_item_id(scraper):
    dup_cards = [_MOCK_CARDS[0], {**_MOCK_CARDS[0]}]
    page = _make_page_mock(dup_cards)
    deals = await scraper._scrape(page)
    assert len([d for d in deals if "9876543" in d.url]) == 1


@pytest.mark.asyncio
async def test_scrape_respects_max_deals(scraper):
    many = [
        {
            "url": f"https://shopee.com.br/produto-i.{i}.{i}00",
            "title": f"Produto {i}",
            "price": "R$\xa0100,00",
            "old_price": "R$\xa0200,00",
            "discount": "-50%",
            "image": None,
            "item_id": str(i),
            "shop_id": str(i),
        }
        for i in range(1, MAX_DEALS_PER_RUN * 4 + 1)
    ]
    page = _make_page_mock(many)
    deals = await scraper._scrape(page)
    assert len(deals) <= MAX_DEALS_PER_RUN


@pytest.mark.asyncio
async def test_scrape_skips_invalid_image(scraper):
    card = {**_MOCK_CARDS[0], "image": "data:image/gif;base64,R0lGODlh"}
    page = _make_page_mock([card])
    deals = await scraper._scrape(page)
    assert deals[0].image_url is None


@pytest.mark.asyncio
async def test_scrape_source_and_store(scraper, mock_page):
    deals = await scraper._scrape(mock_page)
    for deal in deals:
        assert deal.source == "shopee"
        assert deal.store == "Shopee"
