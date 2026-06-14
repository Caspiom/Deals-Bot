import pytest
from unittest.mock import AsyncMock, patch
from src.models import Deal
from src.publishers.telegram_publisher import TelegramPublisher


def _deal(with_image: bool = True) -> Deal:
    return Deal(
        title="RTX 4060 ASUS Dual 8GB GDDR6",
        url="https://www.kabum.com.br/produto/456789",
        affiliate_url="https://shope.ee/exemplo?afiliado=MEU_ID",
        price=2199.00,
        old_price=2899.00,
        image_url="https://images.kabum.com.br/mock.jpg" if with_image else None,
        source="mock",
    )


@pytest.fixture
def publisher():
    with patch("src.publishers.telegram_publisher.Bot") as mock_bot_class:
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        with patch("asyncio.sleep", new_callable=AsyncMock):
            yield TelegramPublisher(), mock_bot


@pytest.mark.asyncio
async def test_publish_with_image_calls_send_photo(publisher):
    p, bot = publisher
    await p.publish(_deal(with_image=True))
    bot.send_photo.assert_called_once()
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_publish_without_image_calls_send_message(publisher):
    p, bot = publisher
    await p.publish(_deal(with_image=False))
    bot.send_message.assert_called_once()
    bot.send_photo.assert_not_called()


@pytest.mark.asyncio
async def test_publish_uses_affiliate_url(publisher):
    p, bot = publisher
    deal = _deal()
    await p.publish(deal)
    markup = bot.send_photo.call_args.kwargs["reply_markup"]
    assert markup.inline_keyboard[0][0].url == deal.affiliate_url


def test_format_caption_contains_title(publisher):
    p, _ = publisher
    assert "RTX 4060" in p._format_caption(_deal())


def test_format_caption_shows_discount(publisher):
    p, _ = publisher
    assert "24% OFF" in p._format_caption(_deal())


def test_format_caption_shows_brl_format(publisher):
    p, _ = publisher
    caption = p._format_caption(_deal())
    assert "R$ 2.199,00" in caption
    assert "R$ 2.899,00" in caption
