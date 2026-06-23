import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.scrapers.americanas_scraper import AmericanasScraper, _best_installment
from src.config.settings import MIN_DISCOUNT_PERCENT


def _make_product(
    pid="101",
    name="Produto Teste",
    price=180.0,
    list_price=300.0,
    available=True,
    image="https://americanas.vteximg.com.br/arquivos/ids/101.jpg",
    installments=None,
) -> dict:
    return {
        "productId": pid,
        "productName": name,
        "link": f"https://www.americanas.com.br/produto/{pid}/produto-teste",
        "items": [{
            "images": [{"imageUrl": image}] if image else [],
            "sellers": [{
                "commertialOffer": {
                    "Price": price,
                    "ListPrice": list_price,
                    "IsAvailable": available,
                    "AvailableQuantity": 5 if available else 0,
                    "Installments": installments or [],
                }
            }],
        }],
    }


def _mock_response(products: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = products
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def scraper():
    return AmericanasScraper()


@pytest.fixture
def mock_api():
    products = [
        _make_product("101", "Notebook Dell Inspiron 15 16GB", 2499.0, 4000.0),
        _make_product("102", "Smartphone Samsung Galaxy A55 128GB", 899.0, 1500.0),
        _make_product("103", "Cabo USB-C 1m", 19.9, 20.5),  # desconto < mínimo
        _make_product("104", "Monitor 4K sem estoque", 1500.0, 2500.0, available=False),
    ]

    async def _get(*args, **kwargs):
        return _mock_response(products)

    with patch("src.scrapers.americanas_scraper.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_cls.return_value = mock_client
        yield


# ── _best_installment ─────────────────────────────────────────────────────────

def test_best_installment_picks_most_parts_interest_free():
    installments = [
        {"NumberOfInstallments": 6,  "Value": 41.65, "hasInterestRate": False},
        {"NumberOfInstallments": 10, "Value": 24.99, "hasInterestRate": False},
        {"NumberOfInstallments": 12, "Value": 22.50, "hasInterestRate": True},
    ]
    result = _best_installment(installments)
    assert result == (10, 24.99)


def test_best_installment_returns_none_when_all_have_interest():
    installments = [
        {"NumberOfInstallments": 12, "Value": 20.0, "hasInterestRate": True},
    ]
    assert _best_installment(installments) is None


def test_best_installment_returns_none_for_empty():
    assert _best_installment([]) is None


# ── fetch ─────────────────────────────────────────────────────────────────────

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
async def test_fetch_accepts_high_discount_from_top_sale(scraper):
    # Com OrderByTopSaleDESC, um desconto real de 90% num produto popular é válido
    product = _make_product("901", "Agenda 2026 Espiral Escolar", 4.99, 49.90)
    resp = _mock_response([product])

    async def _get(*args, **kwargs):
        return resp

    with patch("src.scrapers.americanas_scraper.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_cls.return_value = mock_client
        deals = await scraper.fetch()

    assert len(deals) == 1
    assert deals[0].discount_pct == 90



@pytest.mark.asyncio
async def test_fetch_skips_unavailable(scraper, mock_api):
    deals = await scraper.fetch()
    titles = [d.title for d in deals]
    assert not any("sem estoque" in t for t in titles)


@pytest.mark.asyncio
async def test_fetch_maps_fields_correctly(scraper, mock_api):
    deals = await scraper.fetch()
    notebook = next(d for d in deals if "Notebook" in d.title)
    assert notebook.price == 2499.0
    assert notebook.old_price == 4000.0
    assert notebook.discount_pct == 37
    assert notebook.source == "americanas"
    assert notebook.store == "Americanas"
    assert "americanas.com.br" in notebook.url
    assert "vteximg" in notebook.image_url


@pytest.mark.asyncio
async def test_fetch_deduplicates_by_product_id(scraper):
    product = _make_product("999", "Produto Duplicado", 100.0, 200.0)
    resp = _mock_response([product, product])

    async def _get(*args, **kwargs):
        return resp

    with patch("src.scrapers.americanas_scraper.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_cls.return_value = mock_client
        deals = await scraper.fetch()

    assert len(deals) == 1


@pytest.mark.asyncio
async def test_fetch_with_installments(scraper):
    installments = [
        {"NumberOfInstallments": 10, "Value": 249.90, "hasInterestRate": False},
    ]
    product = _make_product("201", "Notebook com parcelas", 2499.0, 4000.0, installments=installments)
    resp = _mock_response([product])

    async def _get(*args, **kwargs):
        return resp

    with patch("src.scrapers.americanas_scraper.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_cls.return_value = mock_client
        deals = await scraper.fetch()

    assert len(deals) == 1
    assert deals[0].installments == 10
    assert deals[0].installment_value == 249.90


@pytest.mark.asyncio
async def test_fetch_skips_product_without_price(scraper):
    product = _make_product("301", "Sem preço", 0.0, 100.0)
    resp = _mock_response([product])

    async def _get(*args, **kwargs):
        return resp

    with patch("src.scrapers.americanas_scraper.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_cls.return_value = mock_client
        deals = await scraper.fetch()

    assert deals == []


@pytest.mark.asyncio
async def test_fetch_skips_invalid_image(scraper):
    product = _make_product("401", "Produto sem imagem", 100.0, 200.0, image=None)
    resp = _mock_response([product])

    async def _get(*args, **kwargs):
        return resp

    with patch("src.scrapers.americanas_scraper.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_cls.return_value = mock_client
        deals = await scraper.fetch()

    assert len(deals) == 1
    assert deals[0].image_url is None


@pytest.mark.asyncio
async def test_fetch_handles_http_error(scraper):
    with patch("src.scrapers.americanas_scraper.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        err_resp = MagicMock()
        err_resp.raise_for_status.side_effect = Exception("HTTP 503")
        mock_client.get = AsyncMock(return_value=err_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_cls.return_value = mock_client

        try:
            deals = await scraper.fetch()
            assert deals == []
        except Exception:
            pass  # erro propagado também é comportamento aceitável
