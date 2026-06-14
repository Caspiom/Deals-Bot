import pytest
from unittest.mock import AsyncMock, patch
from src.models import Deal
from src.services.telegram_poster import TelegramPoster


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
def poster():
    with patch("src.services.telegram_poster.Bot") as mock_bot_class:
        mock_bot = AsyncMock()
        mock_bot_class.return_value = mock_bot
        with patch("asyncio.sleep", new_callable=AsyncMock):
            yield TelegramPoster(), mock_bot


@pytest.mark.asyncio
async def test_send_with_image_calls_send_photo(poster):
    p, bot = poster
    await p.send(_deal(with_image=True))
    bot.send_photo.assert_called_once()
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_without_image_calls_send_message(poster):
    p, bot = poster
    await p.send(_deal(with_image=False))
    bot.send_message.assert_called_once()
    bot.send_photo.assert_not_called()


@pytest.mark.asyncio
async def test_send_uses_affiliate_url(poster):
    p, bot = poster
    deal = _deal()
    await p.send(deal)
    call_kwargs = bot.send_photo.call_args.kwargs
    markup = call_kwargs["reply_markup"]
    button = markup.inline_keyboard[0][0]
    assert button.url == deal.affiliate_url


def test_format_caption_contains_title(poster):
    p, _ = poster
    caption = p._format_caption(_deal())
    assert "RTX 4060" in caption


def test_format_caption_shows_discount(poster):
    p, _ = poster
    caption = p._format_caption(_deal())
    assert "24% OFF" in caption


def test_format_caption_shows_brl_format(poster):
    p, _ = poster
    caption = p._format_caption(_deal())
    assert "R$ 2.199,00" in caption
    assert "R$ 2.899,00" in caption
