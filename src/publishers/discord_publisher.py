import asyncio
import discord
from discord import app_commands
from loguru import logger

from src.config.settings import DISCORD_BOT_TOKEN
from src.models import Deal
from src.publishers.base_publisher import BasePublisher
from src.services.guild_config import GuildConfigStore
from src.utils.formatters import brl

_EMBED_COLOR = discord.Color.from_str("#FF7C00")
_RATE_LIMIT_DELAY = 1.0
_WELCOME_MSG = (
    "👋 Olá! Sou o **Achadinhos Bot** e vou postar promoções aqui.\n\n"
    "Use `/set-channel #canal` para escolher o canal onde as promos vão aparecer.\n"
    "Precisa de permissão **Gerenciar Servidor** para configurar."
)


class DiscordPublisher(BasePublisher):
    name = "discord"

    def __init__(self, config: GuildConfigStore | None = None) -> None:
        self._config = config or GuildConfigStore()
        intents = discord.Intents.default()
        self._client = discord.Client(intents=intents)
        self._tree = app_commands.CommandTree(self._client)
        self._ready = asyncio.Event()

        self._register_events()
        self._register_commands()

        asyncio.create_task(self._client.start(DISCORD_BOT_TOKEN))

    def _register_events(self) -> None:
        @self._client.event
        async def on_ready() -> None:
            await self._tree.sync()
            logger.info(
                "[Discord] Bot conectado como {}. {} servidor(es).",
                self._client.user, len(self._client.guilds),
            )
            self._ready.set()

        @self._client.event
        async def on_guild_join(guild: discord.Guild) -> None:
            channel = (
                guild.system_channel
                or next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
            )
            if channel:
                await channel.send(_WELCOME_MSG)
            logger.info("[Discord] Bot adicionado ao servidor '{}'.", guild.name)

    def _register_commands(self) -> None:
        @self._tree.command(name="set-channel", description="Define o canal onde as promoções serão postadas")
        @app_commands.default_permissions(manage_guild=True)
        @app_commands.describe(canal="Canal de texto que vai receber as promoções")
        async def set_channel(interaction: discord.Interaction, canal: discord.TextChannel) -> None:
            self._config.set_channel(interaction.guild_id, canal.id)
            await interaction.response.send_message(
                f"✅ Promoções serão postadas em {canal.mention}!", ephemeral=True
            )
            logger.info("[Discord] '{}' configurou canal #{} em '{}'.",
                        interaction.user, canal.name, interaction.guild.name)

        @self._tree.command(name="remove-channel", description="Remove o canal de promoções configurado")
        @app_commands.default_permissions(manage_guild=True)
        async def remove_channel(interaction: discord.Interaction) -> None:
            self._config.remove_channel(interaction.guild_id)
            await interaction.response.send_message(
                "✅ Canal de promoções removido. Use `/set-channel` para configurar novamente.",
                ephemeral=True,
            )
            logger.info("[Discord] '{}' removeu o canal em '{}'.",
                        interaction.user, interaction.guild.name)

        @self._tree.command(name="help", description="Mostra como configurar o bot")
        async def help_cmd(interaction: discord.Interaction) -> None:
            channel_id = self._config.get_channel(interaction.guild_id)
            if channel_id:
                channel = self._client.get_channel(channel_id)
                status = f"✅ Canal configurado: {channel.mention if channel else f'ID {channel_id}'}"
            else:
                status = "⚠️ Nenhum canal configurado ainda."

            embed = discord.Embed(
                title="📖 Achadinhos Bot — Ajuda",
                color=_EMBED_COLOR,
            )
            embed.add_field(
                name="/set-channel #canal",
                value="Define o canal onde as promoções serão postadas.\n*Requer: Gerenciar Servidor*",
                inline=False,
            )
            embed.add_field(
                name="/remove-channel",
                value="Remove o canal configurado.\n*Requer: Gerenciar Servidor*",
                inline=False,
            )
            embed.add_field(
                name="/help",
                value="Mostra esta mensagem.",
                inline=False,
            )
            embed.add_field(name="Status atual", value=status, inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def publish(self, deal: Deal) -> None:
        await asyncio.wait_for(self._ready.wait(), timeout=30)

        embed = self._build_embed(deal)
        posted = 0

        for guild in self._client.guilds:
            channel_id = self._config.get_channel(guild.id)
            if channel_id is None:
                logger.debug("[Discord] Sem canal configurado em '{}' — use /set-channel.", guild.name)
                continue

            channel = self._client.get_channel(channel_id)
            if channel is None:
                logger.warning("[Discord] Canal ID {} não encontrado em '{}'.", channel_id, guild.name)
                continue

            try:
                await channel.send(embed=embed)
                posted += 1
                await asyncio.sleep(_RATE_LIMIT_DELAY)
            except discord.HTTPException as exc:
                logger.error("[Discord] Falha ao postar em '{}': {}", guild.name, exc)

        if posted:
            logger.info("[Discord] Publicado em {} servidor(es): {}", posted, deal.title[:60])

    async def close(self) -> None:
        self._config.close()
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
