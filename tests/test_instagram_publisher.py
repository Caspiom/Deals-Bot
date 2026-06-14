import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.models import Deal
from src.publishers.instagram_publisher import InstagramPublisher


def _deal(with_image: bool = True) -> Deal:
    return Deal(
        title="Smart TV LG 55 4K OLED",
        url="https://www.magazineluiza.com.br/produto/mock",
        affiliate_url="https://shope.ee/exemplo?afiliado=MEU_ID",
        price=3799.00,
        old_price=5999.00,
        image_url="https://media.pelando.com.br/mock.jpg" if with_image else None,
        source="pelando",
    )


@pytest.fixture
def publisher():
    with patch("src.publishers.instagram_publisher.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        container_resp = MagicMock()
        container_resp.json.return_value = {"id": "container_123"}
        container_resp.raise_for_status = MagicMock()

        publish_resp = MagicMock()
        publish_resp.json.return_value = {"id": "post_456"}
        publish_resp.raise_for_status = MagicMock()

        mock_client.post = AsyncMock(side_effect=[container_resp, publish_resp])

        with patch("asyncio.sleep", new_callable=AsyncMock):
            yield InstagramPublisher(), mock_client


@pytest.mark.asyncio
async def test_publish_calls_two_graph_endpoints(publisher):
    p, client = publisher
    await p.publish(_deal())
    assert client.post.call_count == 2


@pytest.mark.asyncio
async def test_publish_skips_deal_without_image(publisher):
    p, client = publisher
    await p.publish(_deal(with_image=False))
    client.post.assert_not_called()


def test_format_caption_contains_title(publisher):
    p, _ = publisher
    assert "Smart TV LG" in p._format_caption(_deal())


def test_format_caption_contains_hashtags(publisher):
    p, _ = publisher
    caption = p._format_caption(_deal())
    assert "#achadinhos" in caption
    assert "#pelando" in caption


def test_format_caption_shows_discount(publisher):
    p, _ = publisher
    caption = p._format_caption(_deal())
    assert "36% OFF" in caption
