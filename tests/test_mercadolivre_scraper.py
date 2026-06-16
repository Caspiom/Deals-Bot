import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.scrapers.mercadolivre_scraper import MercadoLivreScraper, _parse_brl, _parse_discount_pct
from src.config.settings import MIN_DISCOUNT_PERCENT, MAX_DEALS_PER_RUN

_MOCK_CARDS = [
    {
        "title": "Smartphone Samsung Galaxy S24 256GB",
        "url": "https://www.mercadolivre.com.br/produto-a?tracking_id=abc#polycard_client=offers",
        "current": "2.499",
        "original": "3.999",
        "discount": "37% OFF",
        "image": "https://http2.mlstatic.com/D_Q_NP_produto-a.webp",
    },
    {
        "title": "Notebook Lenovo IdeaPad 16GB",
        "url": "https://www.mercadolivre.com.br/produto-b",
        "current": "2.199",
        "original": "3.299",
        "discount": "33% OFF no Pix",
        "image": "https://http2.mlstatic.com/D_Q_NP_produto-b.webp",
    },
    {
        "title": "Produto com desconto mínimo",
        "url": "https://www.mercadolivre.com.br/produto-c",
        "current": "98",
        "original": "100",
        "discount": "2% OFF",
        "image": None,
    },
    {
        "title": "Produto sem percentual de desconto",
        "url": "https://www.mercadolivre.com.br/produto-d",
        "current": "50",
        "original": None,
        "discount": None,
        "image": None,
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
    return MercadoLivreScraper()


@pytest.fixture
def mock_page():
    return _make_page_mock(_MOCK_CARDS)


# ── Testes de parse de utilitários ──────────────────────────────────────────

def test_parse_brl_integer():
    assert _parse_brl("610") == 610.0

def test_parse_brl_thousands_separator():
    assert _parse_brl("1.080") == 1080.0

def test_parse_brl_invalid():
    assert _parse_brl("N/A") is None

def test_parse_discount_pct_simple():
    assert _parse_discount_pct("37% OFF") == 37

def test_parse_discount_pct_pix():
    assert _parse_discount_pct("31% OFF no Pix") == 31

def test_parse_discount_pct_none():
    assert _parse_discount_pct("sem desconto") is None


# ── Testes de scraping ───────────────────────────────────────────────────────

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
    assert samsung.price == 2499.0
    assert samsung.old_price == 3999.0
    assert samsung.discount_pct == 37
    assert "mercadolivre.com.br" in samsung.url
    assert samsung.source == "mercadolivre"


@pytest.mark.asyncio
async def test_scrape_deduplicates_by_base_url(scraper):
    dup_cards = [
        {**_MOCK_CARDS[0], "url": "https://www.mercadolivre.com.br/produto-a?pdp_filters=deal:1#polycard_client=offers&position=1"},
        {**_MOCK_CARDS[0], "url": "https://www.mercadolivre.com.br/produto-a?pdp_filters=deal:1#polycard_client=offers&position=2"},
    ]
    page = _make_page_mock(dup_cards)
    deals = await scraper._scrape(page)
    assert len(deals) == 1


@pytest.mark.asyncio
async def test_scrape_respects_max_deals(scraper):
    many = [
        {
            "title": f"Produto {i}",
            "url": f"https://www.mercadolivre.com.br/produto-{i}",
            "current": "100",
            "original": "200",
            "discount": "50% OFF",
            "image": None,
        }
        for i in range(MAX_DEALS_PER_RUN * 4)
    ]
    page = _make_page_mock(many)
    deals = await scraper._scrape(page)
    assert len(deals) <= MAX_DEALS_PER_RUN


@pytest.mark.asyncio
async def test_scrape_includes_deal_without_discount_text(scraper):
    # card sem discount_pct deve ser incluído (confia na curadoria do ML Ofertas)
    page = _make_page_mock([_MOCK_CARDS[3]])
    deals = await scraper._scrape(page)
    assert len(deals) == 1
    assert deals[0].discount_pct is None


@pytest.mark.asyncio
async def test_scrape_extracts_coupon_code(scraper):
    card = {**_MOCK_CARDS[0], "coupon": "DESCONTO10"}
    page = _make_page_mock([card])
    deals = await scraper._scrape(page)
    assert deals[0].coupon_code == "DESCONTO10"


@pytest.mark.asyncio
async def test_scrape_extracts_coins_discount_value(scraper):
    card = {**_MOCK_CARDS[0], "coins": "2.199"}
    page = _make_page_mock([card])
    deals = await scraper._scrape(page)
    assert deals[0].coins_discount_value == 2199.0


@pytest.mark.asyncio
async def test_scrape_coupon_none_when_absent(scraper, mock_page):
    deals = await scraper._scrape(mock_page)
    for deal in deals:
        assert deal.coupon_code is None
        assert deal.coins_discount_value is None
