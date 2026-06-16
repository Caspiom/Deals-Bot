import pytest
import httpx
from unittest.mock import patch, AsyncMock, MagicMock
from src.scrapers.promobit_scraper import PromobitScraper
from src.config.settings import MIN_DISCOUNT_PERCENT, MAX_DEALS_PER_RUN

_MOCK_OFFERS = [
    {
        "offer_id": 1001,
        "offer_title": "Notebook Dell Inspiron 16GB 512GB SSD",
        "offer_slug": "notebook-dell-inspiron-1001",
        "offer_price": 2499.90,
        "offer_old_price": 3999.90,
        "offer_discont_percentage": 37,
        "offer_photo": "/mock_dell.png",
        "offer_status_name": "HOT",
    },
    {
        "offer_id": 1002,
        "offer_title": "Fone Sony WH-1000XM5",
        "offer_slug": "fone-sony-xm5-1002",
        "offer_price": 1199.00,
        "offer_old_price": 1999.00,
        "offer_discont_percentage": 40,
        "offer_photo": "/mock_sony.png",
        "offer_status_name": "HOT",
    },
    {
        "offer_id": 1003,
        "offer_title": "Produto sem desconto",
        "offer_slug": "produto-sem-desconto-1003",
        "offer_price": 99.90,
        "offer_old_price": 100.00,
        "offer_discont_percentage": 0,
        "offer_photo": "/mock_nodiscount.png",
        "offer_status_name": "NORMAL",
    },
]

_MOCK_RESPONSE = {"after": "1003", "sort": "hot", "offers": _MOCK_OFFERS}


@pytest.fixture
def scraper():
    return PromobitScraper()


@pytest.fixture
def mock_api(respx_mock=None):
    """Mocka o httpx sem depender de respx — usa patch direto."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = _MOCK_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch("src.scrapers.promobit_scraper.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client
        yield


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
async def test_fetch_maps_fields_correctly(scraper, mock_api):
    deals = await scraper.fetch()
    first = deals[0]
    assert "Dell" in first.title
    assert first.price == 2499.90
    assert first.old_price == 3999.90
    assert first.discount_pct == 37
    assert "i.promobit.com.br" in first.image_url
    assert "promobit.com.br/oferta" in first.url
    assert first.source == "promobit"


@pytest.mark.asyncio
async def test_fetch_respects_max_deals(scraper, mock_api):
    deals = await scraper.fetch()
    assert len(deals) <= MAX_DEALS_PER_RUN


@pytest.mark.asyncio
async def test_fetch_calculates_pct_from_prices_when_api_returns_zero(scraper, mock_api):
    """Desconto calculado via preços quando offer_discont_percentage == 0."""
    # offer 1003 tem pct=0 mas old_price=100 e price=99.90 → ~0% → ainda filtrado
    # este teste verifica a lógica para um caso onde pct=0 mas desconto é real
    from src.scrapers.promobit_scraper import _API_URL, _HEADERS
    mock_offer_zero_pct = {
        "offer_id": 2001,
        "offer_title": "Smart TV 50 4K com 40% OFF",
        "offer_slug": "smart-tv-50-4k-2001",
        "offer_price": 1499.00,
        "offer_old_price": 2499.00,
        "offer_discont_percentage": 0,  # API retornou 0 mas há desconto real
        "offer_photo": "/mock_tv.png",
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"offers": [mock_offer_zero_pct]}
    mock_resp.raise_for_status = MagicMock()

    with patch("src.scrapers.promobit_scraper.httpx.AsyncClient") as cls:
        client = AsyncMock()
        client.get = AsyncMock(return_value=mock_resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        cls.return_value = client

        deals = await scraper.fetch()

    assert len(deals) == 1
    assert deals[0].discount_pct == 40


@pytest.mark.asyncio
async def test_fetch_extracts_coupon_code(scraper):
    offer_with_coupon = {
        "offer_id": 3001,
        "offer_title": "Smartphone Xiaomi 14T 256GB",
        "offer_slug": "xiaomi-14t-3001",
        "offer_price": 2199.00,
        "offer_old_price": 3499.00,
        "offer_discont_percentage": 37,
        "offer_photo": "/mock_xiaomi.png",
        "offer_coupon": "XIAOMI15",
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"offers": [offer_with_coupon]}
    mock_resp.raise_for_status = MagicMock()

    with patch("src.scrapers.promobit_scraper.httpx.AsyncClient") as cls:
        client = AsyncMock()
        client.get = AsyncMock(return_value=mock_resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        cls.return_value = client

        deals = await scraper.fetch()

    assert len(deals) == 1
    assert deals[0].coupon_code == "XIAOMI15"


@pytest.mark.asyncio
async def test_fetch_coupon_none_when_absent(scraper, mock_api):
    deals = await scraper.fetch()
    for deal in deals:
        assert deal.coupon_code is None
