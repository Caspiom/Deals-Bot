import pytest
import asyncio
import discord
from unittest.mock import AsyncMock, MagicMock, patch
from src.models import Deal
from src.publishers.discord_publisher import DiscordPublisher
from src.services.guild_config import GuildConfigStore


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


def _make_guild(guild_id: int = 1) -> tuple[MagicMock, MagicMock]:
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = guild_id * 100
    channel.name = "promos"
    channel.mention = f"<#{channel.id}>"
    channel.send = AsyncMock()

    guild = MagicMock(spec=discord.Guild)
    guild.id = guild_id
    guild.name = f"Servidor {guild_id}"
    guild.text_channels = [channel]
    return guild, channel


@pytest.fixture
def config(tmp_path):
    s = GuildConfigStore(db_path=tmp_path / "test.db")
    yield s
    s.close()


@pytest.fixture
def publisher(config):
    with patch("src.publishers.discord_publisher.asyncio.create_task"):
        p = DiscordPublisher.__new__(DiscordPublisher)
        p._config = config
        p._ready = asyncio.Event()
        p._ready.set()
        p._client = MagicMock(spec=discord.Client)
        p._client.user = MagicMock()
        p._client.guilds = []
        yield p


# ── publish ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_sends_to_configured_channel(publisher, config):
    guild, channel = _make_guild(guild_id=1)
    config.set_channel(guild.id, channel.id)
    publisher._client.guilds = [guild]
    publisher._client.get_channel = MagicMock(return_value=channel)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await publisher.publish(_deal())

    channel.send.assert_called_once()


@pytest.mark.asyncio
async def test_publish_skips_guild_without_config(publisher, config):
    guild, channel = _make_guild(guild_id=1)
    # sem configurar canal para o guild
    publisher._client.guilds = [guild]
    publisher._client.get_channel = MagicMock(return_value=channel)

    await publisher.publish(_deal())

    channel.send.assert_not_called()


@pytest.mark.asyncio
async def test_publish_posts_to_all_configured_guilds(publisher, config):
    guild1, ch1 = _make_guild(guild_id=1)
    guild2, ch2 = _make_guild(guild_id=2)
    config.set_channel(guild1.id, ch1.id)
    config.set_channel(guild2.id, ch2.id)
    publisher._client.guilds = [guild1, guild2]
    publisher._client.get_channel = MagicMock(side_effect=[ch1, ch2])

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await publisher.publish(_deal())

    ch1.send.assert_called_once()
    ch2.send.assert_called_once()


@pytest.mark.asyncio
async def test_publish_continues_after_http_error(publisher, config):
    guild1, ch1 = _make_guild(guild_id=1)
    guild2, ch2 = _make_guild(guild_id=2)
    ch1.send = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "erro"))
    config.set_channel(guild1.id, ch1.id)
    config.set_channel(guild2.id, ch2.id)
    publisher._client.guilds = [guild1, guild2]
    publisher._client.get_channel = MagicMock(side_effect=[ch1, ch2])

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await publisher.publish(_deal())

    ch2.send.assert_called_once()


@pytest.mark.asyncio
async def test_publish_skips_when_channel_not_found(publisher, config):
    guild, channel = _make_guild(guild_id=1)
    config.set_channel(guild.id, channel.id)
    publisher._client.guilds = [guild]
    publisher._client.get_channel = MagicMock(return_value=None)  # canal deletado

    await publisher.publish(_deal())

    channel.send.assert_not_called()


# ── embed ─────────────────────────────────────────────────────────────────────

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
    assert "~~" in desc and "3.999,90" in desc


def test_format_description_shows_current_price_bold(publisher):
    assert "**R$ 2.499,90**" in publisher._format_description(_deal())


def test_format_description_shows_discount(publisher):
    assert "37% OFF" in publisher._format_description(_deal())
