import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.models import Deal
from src.publishers.discord_publisher import DiscordPublisher


def _deal(with_image: bool = True) -> Deal:
    return Deal(
        title="Notebook Dell Inspiron 16GB 512GB",
        url="https://www.kabum.com.br/produto/12345/notebook-dell",
        affiliate_url="https://shope.ee/exemplo?afiliado=MEU_ID",
        price=2499.90,
        old_price=3999.90,
        image_url="https://images.kabum.com.br/12345/m.jpg" if with_image else None,
        source="kabum",
    )


@pytest.fixture
def publisher():
    with patch("src.publishers.discord_publisher.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=resp)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            yield DiscordPublisher(), mock_client


@pytest.mark.asyncio
async def test_publish_posts_to_webhook(publisher):
    p, client = publisher
    await p.publish(_deal())
    client.post.assert_called_once()


@pytest.mark.asyncio
async def test_publish_uses_affiliate_url_in_embed(publisher):
    p, client = publisher
    await p.publish(_deal())
    payload = client.post.call_args.kwargs["json"]
    assert payload["embeds"][0]["url"] == "https://shope.ee/exemplo?afiliado=MEU_ID"


@pytest.mark.asyncio
async def test_publish_embed_has_thumbnail_when_image(publisher):
    p, client = publisher
    await p.publish(_deal(with_image=True))
    payload = client.post.call_args.kwargs["json"]
    assert "thumbnail" in payload["embeds"][0]


@pytest.mark.asyncio
async def test_publish_embed_no_thumbnail_without_image(publisher):
    p, client = publisher
    await p.publish(_deal(with_image=False))
    payload = client.post.call_args.kwargs["json"]
    assert "thumbnail" not in payload["embeds"][0]


def test_format_description_shows_old_price_strikethrough(publisher):
    p, _ = publisher
    desc = p._format_description(_deal())
    assert "~~" in desc
    assert "3.999,90" in desc


def test_format_description_shows_current_price_bold(publisher):
    p, _ = publisher
    desc = p._format_description(_deal())
    assert "**R$ 2.499,90**" in desc


def test_format_description_shows_discount(publisher):
    p, _ = publisher
    desc = p._format_description(_deal())
    assert "37% OFF" in desc


def test_embed_footer_contains_source(publisher):
    p, _ = publisher
    payload = p._build_payload(_deal())
    assert "Kabum" in payload["embeds"][0]["footer"]["text"]
