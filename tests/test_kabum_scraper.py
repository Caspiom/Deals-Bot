import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.scrapers.kabum_scraper import KabumScraper
from src.config.settings import MIN_DISCOUNT_PERCENT, MAX_DEALS_PER_RUN

_MOCK_PRODUCTS = [
    {
        "id": 101,
        "attributes": {
            "title": "Placa de Vídeo RTX 4070 Super 12GB",
            "price": 3000.00,
            "price_with_discount": 1800.00,
            "discount_percentage": 40,
            "available": True,
            "product_link": "placa-rtx-4070-super",
            "photos": {"m": ["https://images.kabum.com.br/101/m.jpg"]},
        },
    },
    {
        "id": 102,
        "attributes": {
            "title": "SSD NVMe 1TB Samsung 980 Pro",
            "price": 600.00,
            "price_with_discount": 420.00,
            "discount_percentage": 30,
            "available": True,
            "product_link": "ssd-samsung-980-pro-1tb",
            "photos": {"m": ["https://images.kabum.com.br/102/m.jpg"]},
        },
    },
    {
        "id": 103,
        "attributes": {
            "title": "Cabo HDMI 2.0 1.5m",
            "price": 30.00,
            "price_with_discount": 28.00,
            "discount_percentage": 6,
            "available": True,
            "product_link": "cabo-hdmi",
            "photos": {},
        },
    },
    {
        "id": 104,
        "attributes": {
            "title": "Monitor 4K 27 polegadas (sem estoque)",
            "price": 2000.00,
            "price_with_discount": 1200.00,
            "discount_percentage": 40,
            "available": False,
            "product_link": "monitor-4k-27",
            "photos": {},
        },
    },
]

_MOCK_RESPONSE = {"data": _MOCK_PRODUCTS}


@pytest.fixture
def scraper():
    return KabumScraper()


@pytest.fixture
def mock_api():
    mock_resp = MagicMock()
    mock_resp.json.return_value = _MOCK_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch("src.scrapers.kabum_scraper.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_cls.return_value = mock_client
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
async def test_fetch_skips_unavailable_products(scraper, mock_api):
    deals = await scraper.fetch()
    titles = [d.title for d in deals]
    assert not any("sem estoque" in t for t in titles)


@pytest.mark.asyncio
async def test_fetch_maps_fields_correctly(scraper, mock_api):
    deals = await scraper.fetch()
    rtx = next(d for d in deals if "RTX" in d.title)
    assert rtx.price == 1800.00
    assert rtx.old_price == 3000.00
    assert rtx.discount_pct == 40
    assert rtx.source == "kabum"
    assert "kabum.com.br/produto/101" in rtx.url
    assert "images.kabum.com.br" in rtx.image_url


@pytest.mark.asyncio
async def test_fetch_respects_max_deals(scraper, mock_api):
    deals = await scraper.fetch()
    assert len(deals) <= MAX_DEALS_PER_RUN


@pytest.mark.asyncio
async def test_fetch_deduplicates_across_categories(scraper, mock_api):
    # 6 categorias retornam os mesmos IDs → dedup deve manter apenas 1 cópia de cada
    deals = await scraper.fetch()
    urls = [d.url for d in deals]
    assert len(urls) == len(set(urls))


@pytest.mark.asyncio
async def test_fetch_calculates_pct_from_prices_when_api_returns_zero(scraper):
    mock_product = {
        "id": 201,
        "attributes": {
            "title": "Headset Logitech G435",
            "price": 500.00,
            "price_with_discount": 300.00,
            "discount_percentage": 0,   # API retornou 0
            "available": True,
            "product_link": "headset-g435",
            "photos": {},
        },
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": [mock_product]}
    mock_resp.raise_for_status = MagicMock()

    with patch("src.scrapers.kabum_scraper.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_cls.return_value = mock_client

        deals = await scraper.fetch()

    assert len(deals) == 1
    assert deals[0].discount_pct == 40


@pytest.mark.asyncio
async def test_fetch_continues_when_category_fails(scraper):
    """Falha em uma categoria não interrompe as demais."""
    ok_resp = MagicMock()
    ok_resp.json.return_value = {"data": [_MOCK_PRODUCTS[0]]}  # RTX com 40% OFF
    ok_resp.raise_for_status = MagicMock()

    err_resp = MagicMock()
    err_resp.raise_for_status.side_effect = Exception("HTTP 503")

    call_count = 0

    async def get_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return err_resp if call_count == 1 else ok_resp

    with patch("src.scrapers.kabum_scraper.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=get_side_effect)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_cls.return_value = mock_client

        deals = await scraper.fetch()

    # primeira categoria falhou, mas as demais retornaram dados
    assert len(deals) > 0
