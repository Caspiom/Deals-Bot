import asyncio
import httpx
from loguru import logger
from src.config.settings import DISCORD_WEBHOOK_URL
from src.models import Deal
from src.publishers.base_publisher import BasePublisher
from src.utils.formatters import brl
from src.utils.retry import publisher_retry

_RATE_LIMIT_DELAY = 1.1
_EMBED_COLOR = 0xFF7C00  # laranja


class DiscordPublisher(BasePublisher):
    name = "discord"

    @publisher_retry
    async def publish(self, deal: Deal) -> None:
        payload = self._build_payload(deal)

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(DISCORD_WEBHOOK_URL, json=payload)
            resp.raise_for_status()

        logger.info("[Discord] Publicado: {}", deal.title[:60])
        await asyncio.sleep(_RATE_LIMIT_DELAY)

    def _build_payload(self, deal: Deal) -> dict:
        url = deal.affiliate_url or deal.url
        embed: dict = {
            "title": f"🔥 {deal.title}",
            "url": url,
            "description": self._format_description(deal),
            "color": _EMBED_COLOR,
            "footer": {"text": f"Fonte: {deal.source.capitalize()} • achadinhos"},
        }
        if deal.image_url:
            embed["thumbnail"] = {"url": deal.image_url}

        return {"embeds": [embed]}

    def _format_description(self, deal: Deal) -> str:
        lines = []
        if deal.old_price:
            lines.append(f"💰 De: ~~{brl(deal.old_price)}~~")
        lines.append(f"🎯 Por: **{brl(deal.price)}**")
        if deal.discount_pct:
            lines.append(f"🏷️ **{deal.discount_pct}% OFF**")
        return "\n".join(lines)
