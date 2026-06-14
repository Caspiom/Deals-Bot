import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.models import Deal
from src.publishers.x_publisher import XPublisher


def _deal(long_title: bool = False) -> Deal:
    title = "A" * 200 if long_title else "RTX 4060 ASUS Dual 8GB GDDR6"
    return Deal(
        title=title,
        url="https://www.kabum.com.br/produto/456789",
        affiliate_url="https://shope.ee/exemplo?afiliado=MEU_ID",
        price=2199.00,
        old_price=2899.00,
        source="mock",
    )


@pytest.fixture
def publisher():
    with patch("src.publishers.x_publisher.AsyncClient") as mock_cls:
        mock_client = MagicMock()
        mock_client.create_tweet = AsyncMock()
        mock_cls.return_value = mock_client
        yield XPublisher(), mock_client


@pytest.mark.asyncio
async def test_publish_calls_create_tweet(publisher):
    p, client = publisher
    await p.publish(_deal())
    client.create_tweet.assert_called_once()


@pytest.mark.asyncio
async def test_publish_passes_text(publisher):
    p, client = publisher
    await p.publish(_deal())
    text = client.create_tweet.call_args.kwargs["text"]
    assert "RTX 4060" in text
    assert "shope.ee" in text


def test_format_tweet_within_280_chars(publisher):
    p, _ = publisher
    tweet = p._format_tweet(_deal())
    assert len(tweet) <= 280


def test_format_tweet_truncates_long_title(publisher):
    p, _ = publisher
    tweet = p._format_tweet(_deal(long_title=True))
    assert len(tweet) <= 280
    assert "..." in tweet


def test_format_tweet_contains_price(publisher):
    p, _ = publisher
    tweet = p._format_tweet(_deal())
    assert "2.199,00" in tweet
    assert "2.899,00" in tweet
