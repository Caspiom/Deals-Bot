import pytest
import asyncio
import discord
from unittest.mock import AsyncMock, MagicMock, patch
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


def _make_guild(channel_name: str = "achadinhos") -> MagicMock:
    channel = MagicMock(spec=discord.TextChannel)
    channel.name = channel_name
    channel.send = AsyncMock()
    guild = MagicMock(spec=discord.Guild)
    guild.name = "Servidor Teste"
    guild.text_channels = [channel]
    return guild, channel


@pytest.fixture
def publisher():
    with patch("src.publishers.discord_publisher.asyncio.create_task"):
        p = DiscordPublisher.__new__(DiscordPublisher)
        p._ready = asyncio.Event()
        p._ready.set()
        p._client = MagicMock(spec=discord.Client)
        p._client.user = MagicMock()
        p._client.user.__str__ = lambda self: "DealsBot#0001"
        p._client.guilds = []
        yield p


@pytest.mark.asyncio
async def test_publish_sends_to_matching_channel(publisher):
    guild, channel = _make_guild("achadinhos")
    publisher._client.guilds = [guild]

    with patch("src.publishers.discord_publisher.discord.utils.get", return_value=channel):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await publisher.publish(_deal())

    channel.send.assert_called_once()


@pytest.mark.asyncio
async def test_publish_skips_guild_without_channel(publisher):
    guild, channel = _make_guild("outro-canal")
    publisher._client.guilds = [guild]

    with patch("src.publishers.discord_publisher.discord.utils.get", return_value=None):
        await publisher.publish(_deal())

    channel.send.assert_not_called()


@pytest.mark.asyncio
async def test_publish_posts_to_all_guilds(publisher):
    guild1, ch1 = _make_guild()
    guild2, ch2 = _make_guild()
    publisher._client.guilds = [guild1, guild2]

    with patch("src.publishers.discord_publisher.discord.utils.get", side_effect=[ch1, ch2]):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await publisher.publish(_deal())

    ch1.send.assert_called_once()
    ch2.send.assert_called_once()


@pytest.mark.asyncio
async def test_publish_continues_after_http_error(publisher):
    guild1, ch1 = _make_guild()
    guild2, ch2 = _make_guild()
    ch1.send = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "erro"))
    publisher._client.guilds = [guild1, guild2]

    with patch("src.publishers.discord_publisher.discord.utils.get", side_effect=[ch1, ch2]):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await publisher.publish(_deal())

    ch2.send.assert_called_once()


def test_build_embed_uses_affiliate_url(publisher):
    embed = publisher._build_embed(_deal())
    assert embed.url == "https://shope.ee/exemplo?afiliado=MEU_ID"


def test_build_embed_has_thumbnail_when_image(publisher):
    embed = publisher._build_embed(_deal(with_image=True))
    assert embed.thumbnail.url == "https://images.kabum.com.br/12345/m.jpg"


def test_build_embed_no_thumbnail_without_image(publisher):
    embed = publisher._build_embed(_deal(with_image=False))
    assert embed.thumbnail.url is None


def test_format_description_shows_old_price_strikethrough(publisher):
    desc = publisher._format_description(_deal())
    assert "~~" in desc
    assert "3.999,90" in desc


def test_format_description_shows_current_price_bold(publisher):
    desc = publisher._format_description(_deal())
    assert "**R$ 2.499,90**" in desc


def test_format_description_shows_discount(publisher):
    desc = publisher._format_description(_deal())
    assert "37% OFF" in desc
