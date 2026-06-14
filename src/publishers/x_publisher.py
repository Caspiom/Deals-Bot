from tweepy.asynchronous import AsyncClient
from loguru import logger
from src.config.settings import X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
from src.models import Deal
from src.publishers.base_publisher import BasePublisher
from src.utils.formatters import brl
from src.utils.retry import publisher_retry

_MAX_CHARS = 280


class XPublisher(BasePublisher):
    name = "x"

    def __init__(self) -> None:
        self._client = AsyncClient(
            consumer_key=X_API_KEY,
            consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_SECRET,
        )

    @publisher_retry
    async def publish(self, deal: Deal) -> None:
        text = self._format_tweet(deal)
        await self._client.create_tweet(text=text)
        logger.info("[X] Tweet publicado: {}", deal.title[:50])

    def _format_tweet(self, deal: Deal) -> str:
        url = deal.affiliate_url or deal.url
        body_lines = []
        if deal.old_price:
            body_lines.append(f"💰 De: {brl(deal.old_price)}")
        body_lines.append(f"🎯 Por: {brl(deal.price)}")
        if deal.discount_pct:
            body_lines.append(f"🏷️ {deal.discount_pct}% OFF")
        body_lines.append(f"\n🛒 {url}")
        body = "\n".join(body_lines)

        title_line = f"🔥 {deal.title}"
        tweet = f"{title_line}\n\n{body}"

        if len(tweet) > _MAX_CHARS:
            max_title_len = _MAX_CHARS - len(body) - 5  # 🔥 + \n\n + "..."
            title_line = f"🔥 {deal.title[:max_title_len]}..."
            tweet = f"{title_line}\n\n{body}"

        return tweet[:_MAX_CHARS]
