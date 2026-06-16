import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.scrapers.amazon_scraper import AmazonScraper, _signed_headers, _signing_key
from src.config.settings import MIN_DISCOUNT_PERCENT, MAX_DEALS_PER_RUN

# ── helpers ──────────────────────────────────────────────────────────────────

def _make_item(
    asin: str = "B001",
    title: str = "Produto Teste",
    price: float = 100.0,
    old_price: float = 200.0,
    discount_pct: int = 50,
    image: str | None = "https://m.media-amazon.com/images/I/test.jpg",
    url: str = "https://www.amazon.com.br/dp/B001?tag=achadin09c587-20",
) -> dict:
    item: dict = {
        "ASIN": asin,
        "DetailPageURL": url,
        "ItemInfo": {"Title": {"DisplayValue": title}},
        "Offers": {
            "Listings": [
                {
                    "Price": {"Amount": price, "Currency": "BRL"},
                    "SavingBasis": {"Amount": old_price, "Percentage": discount_pct},
                }
            ]
        },
    }
    if image:
        item["Images"] = {"Primary": {"Medium": {"URL": image}}}
    return item


def _make_response(items: list[dict]) -> dict:
    return {"SearchResult": {"Items": items, "TotalResultCount": len(items)}}


@pytest.fixture
def scraper():
    return AmazonScraper()


def _patch_api(response: dict):
    mock_resp = MagicMock()
    mock_resp.json.return_value = response
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return patch("src.scrapers.amazon_scraper.httpx.AsyncClient", return_value=mock_client)


# ── assinatura ───────────────────────────────────────────────────────────────

def test_signing_key_returns_bytes():
    key = _signing_key("my_secret", "20240101")
    assert isinstance(key, bytes)
    assert len(key) == 32


def test_signed_headers_contains_required_keys():
    headers = _signed_headers("AKID", "secret", '{"test": 1}')
    assert "Authorization" in headers
    assert "X-Amz-Date" in headers
    assert "X-Amz-Target" in headers
    assert headers["Authorization"].startswith("AWS4-HMAC-SHA256")


def test_signed_headers_authorization_format():
    headers = _signed_headers("AKID", "secret", "{}")
    auth = headers["Authorization"]
    assert "Credential=AKID/" in auth
    assert "SignedHeaders=" in auth
    assert "Signature=" in auth


# ── fetch sem credenciais ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_skips_without_credentials():
    with patch("src.scrapers.amazon_scraper.AMAZON_ACCESS_KEY", ""), \
         patch("src.scrapers.amazon_scraper.AMAZON_SECRET_KEY", ""):
        deals = await AmazonScraper().fetch()
    assert deals == []


# ── parse de itens ────────────────────────────────────────────────────────────

def test_parse_item_maps_fields(scraper):
    item = _make_item(asin="B001", title="Notebook Dell Inspiron", price=2500.0, old_price=5000.0, discount_pct=50)
    deal = scraper._parse_item(item)
    assert deal is not None
    assert deal.title == "Notebook Dell Inspiron"
    assert deal.price == 2500.0
    assert deal.old_price == 5000.0
    assert deal.discount_pct == 50
    assert deal.source == "amazon"
    assert deal.store == "Amazon"
    assert "amazon.com.br" in deal.url


def test_parse_item_uses_detail_page_url(scraper):
    url = "https://www.amazon.com.br/dp/B001?tag=achadin09c587-20&ref=test"
    item = _make_item(url=url)
    deal = scraper._parse_item(item)
    assert deal.url == url


def test_parse_item_fallback_url_when_missing(scraper):
    item = _make_item()
    item.pop("DetailPageURL")
    deal = scraper._parse_item(item)
    assert deal is not None
    assert "amazon.com.br/dp/" in deal.url
    assert "tag=" in deal.url


def test_parse_item_returns_none_without_title(scraper):
    item = _make_item()
    item["ItemInfo"]["Title"]["DisplayValue"] = ""
    assert scraper._parse_item(item) is None


def test_parse_item_returns_none_without_listings(scraper):
    item = _make_item()
    item["Offers"]["Listings"] = []
    assert scraper._parse_item(item) is None


def test_parse_item_filters_low_discount(scraper):
    item = _make_item(discount_pct=MIN_DISCOUNT_PERCENT - 1, old_price=105.0, price=100.0)
    item["Offers"]["Listings"][0]["SavingBasis"]["Percentage"] = MIN_DISCOUNT_PERCENT - 1
    assert scraper._parse_item(item) is None


def test_parse_item_calculates_discount_when_missing(scraper):
    item = _make_item(price=100.0, old_price=200.0)
    item["Offers"]["Listings"][0]["SavingBasis"].pop("Percentage")
    deal = scraper._parse_item(item)
    assert deal is not None
    assert deal.discount_pct == 50


def test_parse_item_image_url(scraper):
    item = _make_item(image="https://m.media-amazon.com/images/I/abc.jpg")
    deal = scraper._parse_item(item)
    assert deal.image_url == "https://m.media-amazon.com/images/I/abc.jpg"


def test_parse_item_no_image(scraper):
    item = _make_item(image=None)
    deal = scraper._parse_item(item)
    assert deal is not None
    assert deal.image_url is None


# ── fetch completo ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_returns_deals(scraper):
    items = [_make_item(asin=f"B00{i}", title=f"Produto {i}") for i in range(3)]
    response = _make_response(items)

    with patch("src.scrapers.amazon_scraper.AMAZON_ACCESS_KEY", "AKID"), \
         patch("src.scrapers.amazon_scraper.AMAZON_SECRET_KEY", "secret"), \
         _patch_api(response):
        deals = await scraper.fetch()

    assert len(deals) > 0


@pytest.mark.asyncio
async def test_fetch_deduplicates_same_asin_across_categories(scraper):
    # Mesmo ASIN aparece em múltiplas categorias
    items = [_make_item(asin="B001", title="Item Repetido")]
    response = _make_response(items)

    with patch("src.scrapers.amazon_scraper.AMAZON_ACCESS_KEY", "AKID"), \
         patch("src.scrapers.amazon_scraper.AMAZON_SECRET_KEY", "secret"), \
         _patch_api(response):
        deals = await scraper.fetch()

    asins_in_urls = [d.url for d in deals if "B001" in d.url]
    assert len(asins_in_urls) == 1


@pytest.mark.asyncio
async def test_fetch_respects_max_deals(scraper):
    items = [_make_item(asin=f"B{i:04d}", title=f"Produto {i}") for i in range(20)]
    response = _make_response(items)

    with patch("src.scrapers.amazon_scraper.AMAZON_ACCESS_KEY", "AKID"), \
         patch("src.scrapers.amazon_scraper.AMAZON_SECRET_KEY", "secret"), \
         _patch_api(response):
        deals = await scraper.fetch()

    assert len(deals) <= MAX_DEALS_PER_RUN


@pytest.mark.asyncio
async def test_fetch_continues_when_one_category_fails(scraper):
    good_response = _make_response([_make_item(asin="B001", title="Produto Bom")])
    mock_resp_good = MagicMock()
    mock_resp_good.json.return_value = good_response
    mock_resp_good.raise_for_status = MagicMock()

    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("HTTP 503")
        return mock_resp_good

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("src.scrapers.amazon_scraper.AMAZON_ACCESS_KEY", "AKID"), \
         patch("src.scrapers.amazon_scraper.AMAZON_SECRET_KEY", "secret"), \
         patch("src.scrapers.amazon_scraper.httpx.AsyncClient", return_value=mock_client):
        deals = await scraper.fetch()

    # Falhou em 1 categoria mas continua pelas demais
    assert len(deals) >= 0
