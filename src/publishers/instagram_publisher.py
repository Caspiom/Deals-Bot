import asyncio
import httpx
from loguru import logger
from src.config.settings import INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_USER_ID
from src.models import Deal
from src.publishers.base_publisher import BasePublisher
from src.utils.formatters import brl
from src.utils.retry import publisher_retry

_GRAPH_BASE = "https://graph.facebook.com/v20.0"
_CONTAINER_WAIT = 3.0  # segundos para o container de mídia ficar pronto


class InstagramPublisher(BasePublisher):
    name = "instagram"

    @publisher_retry
    async def publish(self, deal: Deal) -> None:
        if not deal.image_url:
            logger.warning("[Instagram] Deal sem imagem — pulando: {}", deal.title[:50])
            return

        caption = self._format_caption(deal)

        async with httpx.AsyncClient(timeout=20) as client:
            # Passo 1: cria container de mídia
            r = await client.post(
                f"{_GRAPH_BASE}/{INSTAGRAM_USER_ID}/media",
                params={
                    "image_url": deal.image_url,
                    "caption": caption,
                    "access_token": INSTAGRAM_ACCESS_TOKEN,
                },
            )
            r.raise_for_status()
            container_id = r.json()["id"]

            # Passo 2: aguarda processamento e publica
            await asyncio.sleep(_CONTAINER_WAIT)
            r = await client.post(
                f"{_GRAPH_BASE}/{INSTAGRAM_USER_ID}/media_publish",
                params={
                    "creation_id": container_id,
                    "access_token": INSTAGRAM_ACCESS_TOKEN,
                },
            )
            r.raise_for_status()

        logger.info("[Instagram] Post publicado: {}", deal.title[:50])

    def _format_caption(self, deal: Deal) -> str:
        lines = [f"🔥 {deal.title}\n"]
        if deal.old_price:
            lines.append(f"💰 De: {brl(deal.old_price)}")
        lines.append(f"🎯 Por: {brl(deal.price)}")
        if deal.discount_pct:
            lines.append(f"🏷️ {deal.discount_pct}% OFF\n")
        url = deal.affiliate_url or deal.url
        lines.append(f"🛒 {url}\n")
        lines.append(f"#achadinhos #promoção #desconto #{deal.source}")
        return "\n".join(lines)
