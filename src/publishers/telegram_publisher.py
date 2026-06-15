import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from loguru import logger
from src.config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
from src.models import Deal
from src.publishers.base_publisher import BasePublisher
from src.utils.formatters import brl
from src.utils.retry import publisher_retry

_RATE_LIMIT_DELAY = 1.1


class TelegramPublisher(BasePublisher):
    name = "telegram"

    def __init__(self) -> None:
        self._bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self._channel = TELEGRAM_CHANNEL_ID

    @publisher_retry
    async def publish(self, deal: Deal) -> None:
        caption = self._format_caption(deal)
        url = deal.affiliate_url or deal.url
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🛒 Comprar agora", url=url)
        ]])

        if deal.image_url:
            await self._bot.send_photo(
                chat_id=self._channel,
                photo=deal.image_url,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
        else:
            await self._bot.send_message(
                chat_id=self._channel,
                text=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )

        logger.info("[Telegram] Publicado: {}", deal.title[:60])
        await asyncio.sleep(_RATE_LIMIT_DELAY)

    def _format_caption(self, deal: Deal) -> str:
        lines = [f"🔥 <b>{deal.title}</b>"]
        if deal.tagline:
            lines.append(f"\n{deal.tagline}\n")
        else:
            lines.append("")
        if deal.old_price:
            lines.append(f"💰 De: <s>{brl(deal.old_price)}</s>")
        lines.append(f"🎯 Por: <b>{brl(deal.price)}</b>")
        if deal.discount_pct:
            lines.append(f"🏷️ Desconto: <b>{deal.discount_pct}% OFF</b>")
        store = deal.store or deal.source.capitalize()
        lines.append(f"\n🏪 Loja: {store}")
        return "\n".join(lines)
