import pytest
from unittest.mock import AsyncMock
from src.scrapers.magalu_scraper import MagaluScraper, _parse_brl, _parse_discount_pct
from src.config.settings import MIN_DISCOUNT_PERCENT, MAX_DEALS_PER_RUN

_MOCK_CARDS = [
    {
        "title": "Notebook Samsung Galaxy Book3 16GB 512GB",
        "url": "https://www.magazineluiza.com.br/notebook-samsung/p/bc4568701/in/note/",
        "price": "R$\xa02.999,90",
        "old_price": "R$\xa04.999,90",
        "discount": "40% OFF",
        "installment": "12x de R$ 249,99 sem juros",
        "image": "https://a-static.mlcdn.com.br/800x560/notebook-samsung/abc.jpg",
    },
    {
        "title": "Smartphone Motorola Moto G54 128GB",
        "url": "https://www.magazineluiza.com.br/smartphone-motorola/p/gf1234567/te/moto/",
        "price": "R$\xa0899,00",
        "old_price": "R$\xa01.299,00",
        "discount": "30% OFF",
        "installment": None,
        "image": "https://a-static.mlcdn.com.br/800x560/motorola-moto-g54/xyz.jpg",
    },
    {
        "title": "Produto com desconto baixo",
        "url": "https://www.magazineluiza.com.br/produto/p/xx0000001/ca/desc/",
        "price": "R$\xa049,90",
        "old_price": "R$\xa051,00",
        "discount": "2% OFF",
        "installment": None,
        "image": None,
    },
    {
        "title": "Smart TV LG 55 4K OLED",
        "url": "https://www.magazineluiza.com.br/smart-tv-lg/p/hd1234567/et/tv55/",
        "price": "R$\xa03.499,00",
        "old_price": "R$\xa05.999,00",
        "discount": "41% OFF",
        "installment": "10x de R$ 349,90 sem juros",
        "image": "https://a-static.mlcdn.com.br/800x560/lg-oled/tv.jpg",
    },
    {
        "title": "Imagem lazy — sem URL válida",
        "url": "https://www.magazineluiza.com.br/produto/p/la0000001/ca/lazy/",
        "price": "R$\xa0199,00",
        "old_price": "R$\xa0399,00",
        "discount": "50% OFF",
        "installment": None,
        "image": "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7",
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
    return MagaluScraper()


@pytest.fixture
def mock_page():
    return _make_page_mock(_MOCK_CARDS)


# ── parse de utilitários ─────────────────────────────────────────────────────

def test_parse_brl_normal():
    assert _parse_brl("R$\xa02.999,90") == 2999.90

def test_parse_brl_simple():
    assert _parse_brl("R$\xa0899,00") == 899.00

def test_parse_brl_without_prefix():
    assert _parse_brl("1.299,00") == 1299.00

def test_parse_brl_none():
    assert _parse_brl(None) is None

def test_parse_brl_invalid():
    assert _parse_brl("grátis") is None

def test_parse_discount_pct_off():
    assert _parse_discount_pct("40% OFF") == 40

def test_parse_discount_pct_bare():
    assert _parse_discount_pct("30%") == 30

def test_parse_discount_pct_none():
    assert _parse_discount_pct(None) is None

def test_parse_discount_pct_no_match():
    assert _parse_discount_pct("sem desconto") is None


# ── scraping ─────────────────────────────────────────────────────────────────

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
    assert samsung.price == 2999.90
    assert samsung.old_price == 4999.90
    assert samsung.discount_pct == 40
    assert samsung.source == "magalu"
    assert samsung.store == "Magazine Luiza"
    assert "magazineluiza.com.br" in samsung.url


@pytest.mark.asyncio
async def test_scrape_maps_installments(scraper, mock_page):
    deals = await scraper._scrape(mock_page)
    samsung = next(d for d in deals if "Samsung" in d.title)
    assert samsung.installments == 12
    assert samsung.installment_value == 249.99


@pytest.mark.asyncio
async def test_scrape_deduplicates_by_base_url(scraper):
    dup_cards = [
        {**_MOCK_CARDS[0], "url": "https://www.magazineluiza.com.br/notebook-samsung/p/bc4568701/in/note/?partner_id=abc&utm=1"},
        {**_MOCK_CARDS[0], "url": "https://www.magazineluiza.com.br/notebook-samsung/p/bc4568701/in/note/?partner_id=abc&utm=2"},
    ]
    page = _make_page_mock(dup_cards)
    deals = await scraper._scrape(page)
    assert len(deals) == 1


@pytest.mark.asyncio
async def test_scrape_respects_max_deals(scraper):
    many = [
        {
            "title": f"Produto {i}",
            "url": f"https://www.magazineluiza.com.br/produto/p/xx{i:07d}/ca/cat/",
            "price": "R$\xa0100,00",
            "old_price": "R$\xa0200,00",
            "discount": "50% OFF",
            "installment": None,
            "image": f"https://a-static.mlcdn.com.br/{i}.jpg",
        }
        for i in range(MAX_DEALS_PER_RUN * 4)
    ]
    page = _make_page_mock(many)
    deals = await scraper._scrape(page)
    assert len(deals) <= MAX_DEALS_PER_RUN


@pytest.mark.asyncio
async def test_scrape_skips_lazy_placeholder_images(scraper, mock_page):
    deals = await scraper._scrape(mock_page)
    lazy = next((d for d in deals if "lazy" in d.url), None)
    if lazy:
        assert lazy.image_url is None


@pytest.mark.asyncio
async def test_scrape_sets_none_image_when_absent(scraper):
    card_no_image = {**_MOCK_CARDS[1], "image": None}
    page = _make_page_mock([card_no_image])
    deals = await scraper._scrape(page)
    assert deals[0].image_url is None


@pytest.mark.asyncio
async def test_scrape_source_and_store(scraper, mock_page):
    deals = await scraper._scrape(mock_page)
    for deal in deals:
        assert deal.source == "magalu"
        assert deal.store == "Magazine Luiza"
