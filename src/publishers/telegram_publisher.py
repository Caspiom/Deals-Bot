import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from loguru import logger
from src.config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
from src.models import Deal
from src.publishers.base_publisher import BasePublisher
from src.services.category_classifier import classify
from src.utils.formatters import brl
from src.utils.retry import publisher_retry

_RATE_LIMIT_DELAY = 1.5

_CATEGORY_TAGS: dict[str, str] = {
    "console":                "#Console #Gaming",
    "smartphone":             "#Smartphone #Tech",
    "notebook":               "#Notebook #Tech",
    "tv_monitor":             "#TV #Eletrônicos",
    "fone_headset":           "#Áudio #Tech",
    "eletronico_acessorio":   "#Acessórios #Tech",
    "eletronico_geral":       "#Eletrônicos #Tech",
    "kit_intimo":             "#Moda #Íntimos",
    "calcado_esporte":        "#Tênis #Moda",
    "calcado":                "#Calçados #Moda",
    "roupa_esporte":          "#Moda #Esporte",
    "roupa_social":           "#Moda",
    "roupa":                  "#Moda",
    "eletrodomestico_grande": "#Eletrodomésticos #Casa",
    "eletrodomestico_pequeno":"#Eletrodomésticos #Casa",
    "cama_banho":             "#Casa",
    "moveis":                 "#Móveis #Casa",
    "utensilio_cozinha":      "#Cozinha #Casa",
    "casa_geral":             "#Casa",
    "churrasco":              "#Churrasco",
    "cafe":                   "#Café",
    "condimento":             "#Alimentação",
    "chocolate_doce":         "#Doces",
    "bebida_alcoolica":       "#Bebidas",
    "suplemento":             "#Suplementos #Fitness",
    "alimento":               "#Alimentação",
    "bebe":                   "#Bebê",
    "perfume":                "#Perfume #Beleza",
    "skincare":               "#Skincare #Beleza",
    "cabelo":                 "#Cabelo #Beleza",
    "barba":                  "#Barba #Beleza",
    "higiene":                "#Higiene",
    "ferramenta_eletrica":    "#Ferramentas",
    "ferramenta":             "#Ferramentas",
    "livro_negocio":          "#Livros",
    "livro":                  "#Livros",
    "brinquedo_educativo":    "#Brinquedos #Kids",
    "brinquedo":              "#Brinquedos",
    "pet":                    "#Pet",
    "musculacao":             "#Fitness #Musculação",
    "cardio_outdoor":         "#Fitness #Esporte",
    "esporte":                "#Esporte",
    "geral":                  "#Ofertas",
}


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

        if deal.is_price_low:
            lines.append("🏆 <b>Menor preço em 30 dias!</b>\n")

        if deal.old_price:
            lines.append(f"💰 De: <s>{brl(deal.old_price)}</s>")
        lines.append(f"🎯 Por: <b>{brl(deal.price)}</b>")
        if deal.discount_pct:
            lines.append(f"🏷️ Desconto: <b>{deal.discount_pct}% OFF</b>")
        if deal.installments and deal.installment_value:
            lines.append(f"💳 <b>{deal.installments}x de {brl(deal.installment_value)} sem juros</b>")

        store = deal.store or deal.source.capitalize()
        lines.append(f"\n🏪 Loja: {store}")

        category = classify(deal)
        lines.append(_CATEGORY_TAGS.get(category, "#Ofertas"))

        return "\n".join(lines)
