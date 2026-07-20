import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.scrapers.aliexpress_scraper import AliExpressScraper, _parse_price, _sign
from src.config.settings import MIN_DISCOUNT_PERCENT, MAX_DEALS_PER_RUN


def _make_response(products: list[dict]) -> dict:
    return {
        "aliexpress_affiliate_product_query_response": {
            "resp_result": {
                "resp_code": 200,
                "resp_msg": "OK",
                "result": {
                    "products": {"product": products},
                    "current_page_no": 1,
                },
            }
        }
    }


_MOCK_PRODUCTS = [
    {
        "product_id": "1001",
        "product_title": "Fone Bluetooth XB500",
        "product_url": "https://www.aliexpress.com/item/1001.html",
        "promotion_link": "https://s.click.aliexpress.com/e/_abc1",
        "sale_price": "80.00 BRL",
        "original_price": "200.00 BRL",
        "local_sale_price": "115.20 BRL",    # com impostos BR
        "local_original_price": "288.00 BRL",
        "discount": "60%",
        "product_main_image_url": "https://ae01.alicdn.com/img/1001.jpg",
    },
    {
        "product_id": "1002",
        "product_title": "Smartwatch Barato",
        "product_url": "https://www.aliexpress.com/item/1002.html",
        "promotion_link": "https://s.click.aliexpress.com/e/_abc2",
        "sale_price": "50.00 BRL",
        "original_price": "60.00 BRL",
        "local_sale_price": "72.00 BRL",
        "local_original_price": "86.40 BRL",
        "discount": "5%",   # abaixo do mínimo
        "product_main_image_url": None,
    },
    {
        "product_id": "1003",
        "product_title": "Cabo USB-C 2m",
        "product_url": "https://www.aliexpress.com/item/1003.html",
        "promotion_link": "https://s.click.aliexpress.com/e/_abc3",
        "sale_price": "15.00 BRL",
        "original_price": "25.00 BRL",
        "local_sale_price": "21.60 BRL",
        "local_original_price": "36.00 BRL",
        "discount": "40%",
        "product_main_image_url": "https://ae01.alicdn.com/img/1003.jpg",
    },
]


@pytest.fixture
def scraper():
    return AliExpressScraper()


@pytest.fixture
def mock_api():
    mock_resp = MagicMock()
    mock_resp.json.return_value = _make_response(_MOCK_PRODUCTS)
    mock_resp.raise_for_status = MagicMock()

    with patch("src.scrapers.aliexpress_scraper.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_cls.return_value = mock_client
        yield


# ── _parse_price ─────────────────────────────────────────────────────────────

def test_parse_price_standard():
    assert _parse_price("115.20 BRL") == 115.20

def test_parse_price_brl_notation():
    assert _parse_price("1.234,56 BRL") == 1234.56

def test_parse_price_comma_decimal():
    assert _parse_price("99,90") == 99.90

def test_parse_price_none():
    assert _parse_price(None) is None

def test_parse_price_invalid():
    assert _parse_price("abc") is None


# ── _sign ────────────────────────────────────────────────────────────────────

def test_sign_is_uppercase_hex():
    sig = _sign({"a": "1", "b": "2"}, "secret")
    assert sig == sig.upper()
    assert len(sig) == 32


# ── fetch ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_returns_deals(scraper, mock_api):
    deals = await scraper.fetch()
    assert len(deals) > 0


@pytest.mark.asyncio
async def test_fetch_filters_low_discount(scraper, mock_api):
    deals = await scraper.fetch()
    for deal in deals:
        assert deal.discount_pct >= MIN_DISCOUNT_PERCENT


@pytest.mark.asyncio
async def test_fetch_uses_local_price_with_tax(scraper, mock_api):
    deals = await scraper.fetch()
    fone = next(d for d in deals if "Fone" in d.title)
    # Deve usar local_sale_price (com impostos), não sale_price
    assert fone.price == 115.20
    assert fone.old_price == 288.00


@pytest.mark.asyncio
async def test_fetch_sets_tax_note_when_local_price_available(scraper, mock_api):
    deals = await scraper.fetch()
    fone = next(d for d in deals if "Fone" in d.title)
    assert fone.tax_note is not None
    assert "imposto" in fone.tax_note.lower()


@pytest.mark.asyncio
async def test_fetch_uses_promotion_link_as_url(scraper, mock_api):
    deals = await scraper.fetch()
    fone = next(d for d in deals if "Fone" in d.title)
    assert fone.url == "https://s.click.aliexpress.com/e/_abc1"


@pytest.mark.asyncio
async def test_fetch_maps_source_and_store(scraper, mock_api):
    deals = await scraper.fetch()
    for deal in deals:
        assert deal.source == "aliexpress"
        assert deal.store == "AliExpress"


@pytest.mark.asyncio
async def test_fetch_respects_max_deals(scraper, mock_api):
    deals = await scraper.fetch()
    assert len(deals) <= MAX_DEALS_PER_RUN


@pytest.mark.asyncio
async def test_fetch_handles_api_error(scraper):
    error_resp = {
        "aliexpress_affiliate_product_query_response": {
            "resp_result": {
                "resp_code": 500,
                "resp_msg": "Internal error",
            }
        }
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = error_resp
    mock_resp.raise_for_status = MagicMock()

    with patch("src.scrapers.aliexpress_scraper.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_cls.return_value = mock_client

        deals = await scraper.fetch()

    assert deals == []


@pytest.mark.asyncio
async def test_fetch_falls_back_to_sale_price_without_local(scraper):
    product_no_local = {
        "product_id": "9001",
        "product_title": "Produto Sem Preço Local",
        "promotion_link": "https://s.click.aliexpress.com/e/_fallback",
        "sale_price": "50.00 BRL",
        "original_price": "100.00 BRL",
        "local_sale_price": None,
        "local_original_price": None,
        "discount": "50%",
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = _make_response([product_no_local])
    mock_resp.raise_for_status = MagicMock()

    with patch("src.scrapers.aliexpress_scraper.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_cls.return_value = mock_client

        deals = await scraper.fetch()

    assert len(deals) == 1
    assert deals[0].price == 50.00
    assert deals[0].tax_note is None  # sem local_price → sem nota de imposto


@pytest.mark.asyncio
async def test_fetch_skips_missing_credentials():
    with patch("src.scrapers.aliexpress_scraper.ALIEXPRESS_APP_KEY", ""), \
         patch("src.scrapers.aliexpress_scraper.ALIEXPRESS_SECRET_KEY", ""):
        deals = await AliExpressScraper().fetch()
    assert deals == []


@pytest.mark.asyncio
async def test_fetch_collapses_same_title_from_different_sellers(scraper):
    """Mesmo produto anunciado por vendedores distintos (ids diferentes,
    título idêntico) deve virar um único deal — o mais barato."""
    dupes = [
        {**_MOCK_PRODUCTS[0], "product_id": "7001", "local_sale_price": "90.00 BRL"},
        {**_MOCK_PRODUCTS[0], "product_id": "7002", "local_sale_price": "70.00 BRL"},
    ]
    mock_resp = MagicMock()
    mock_resp.json.return_value = _make_response(dupes)
    mock_resp.raise_for_status = MagicMock()

    with patch("src.scrapers.aliexpress_scraper.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_cls.return_value = mock_client

        deals = await scraper.fetch()

    same = [d for d in deals if "Fone" in d.title]
    assert len(same) == 1
    assert same[0].price == 70.00


@pytest.mark.asyncio
async def test_dedup_key_is_title_based(scraper, mock_api):
    deals = await scraper.fetch()
    fone = next(d for d in deals if "Fone" in d.title)
    assert fone.dedup_key == f"aliexpress:{fone.title.lower()}"
