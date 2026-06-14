import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from loguru import logger
from src.config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
from src.models import Deal
from src.utils.retry import telegram_retry

_RATE_LIMIT_DELAY = 1.1  # Telegram: máx 1 msg/s por chat


def _brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class TelegramPoster:
    def __init__(self) -> None:
        self._bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self._channel = TELEGRAM_CHANNEL_ID

    @telegram_retry
    async def send(self, deal: Deal) -> None:
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

        logger.info("Postado no canal: {}", deal.title[:60])
        await asyncio.sleep(_RATE_LIMIT_DELAY)

    def _format_caption(self, deal: Deal) -> str:
        lines = [f"🔥 <b>{deal.title}</b>\n"]

        if deal.old_price:
            lines.append(f"💰 De: <s>{_brl(deal.old_price)}</s>")

        lines.append(f"🎯 Por: <b>{_brl(deal.price)}</b>")

        if deal.discount_pct:
            lines.append(f"🏷️ Desconto: <b>{deal.discount_pct}% OFF</b>")

        lines.append(f"\n📦 Fonte: {deal.source.capitalize()}")

        return "\n".join(lines)
