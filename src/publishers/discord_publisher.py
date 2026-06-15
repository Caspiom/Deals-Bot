import asyncio
import discord
from loguru import logger
from src.config.settings import DISCORD_BOT_TOKEN, DISCORD_CHANNEL_NAME
from src.models import Deal
from src.publishers.base_publisher import BasePublisher
from src.utils.formatters import brl

_EMBED_COLOR = discord.Color.from_str("#FF7C00")
_RATE_LIMIT_DELAY = 1.0


class DiscordPublisher(BasePublisher):
    name = "discord"

    def __init__(self) -> None:
        intents = discord.Intents.default()
        self._client = discord.Client(intents=intents)
        self._ready = asyncio.Event()

        @self._client.event
        async def on_ready() -> None:
            logger.info("[Discord] Bot conectado como {}. {} servidor(es).",
                        self._client.user, len(self._client.guilds))
            self._ready.set()

        asyncio.create_task(self._client.start(DISCORD_BOT_TOKEN))

    async def publish(self, deal: Deal) -> None:
        await asyncio.wait_for(self._ready.wait(), timeout=30)

        embed = self._build_embed(deal)
        posted = 0

        for guild in self._client.guilds:
            channel = discord.utils.get(guild.text_channels, name=DISCORD_CHANNEL_NAME)
            if channel is None:
                logger.warning("[Discord] Canal '{}' não encontrado em '{}'.",
                               DISCORD_CHANNEL_NAME, guild.name)
                continue
            try:
                await channel.send(embed=embed)
                posted += 1
                await asyncio.sleep(_RATE_LIMIT_DELAY)
            except discord.HTTPException as exc:
                logger.error("[Discord] Falha ao postar em '{}'/#{}: {}",
                             guild.name, DISCORD_CHANNEL_NAME, exc)

        if posted:
            logger.info("[Discord] Publicado em {} servidor(es): {}", posted, deal.title[:60])

    async def close(self) -> None:
        await self._client.close()

    def _build_embed(self, deal: Deal) -> discord.Embed:
        url = deal.affiliate_url or deal.url
        embed = discord.Embed(
            title=f"🔥 {deal.title}",
            url=url,
            description=self._format_description(deal),
            color=_EMBED_COLOR,
        )
        embed.set_footer(text=f"Fonte: {deal.source.capitalize()} • achadinhos")
        if deal.image_url:
            embed.set_thumbnail(url=deal.image_url)
        return embed

    def _format_description(self, deal: Deal) -> str:
        lines = []
        if deal.old_price:
            lines.append(f"💰 De: ~~{brl(deal.old_price)}~~")
        lines.append(f"🎯 Por: **{brl(deal.price)}**")
        if deal.discount_pct:
            lines.append(f"🏷️ **{deal.discount_pct}% OFF**")
        return "\n".join(lines)
