from tenacity import retry, stop_after_attempt, wait_exponential, RetryCallState
from loguru import logger


def _log_retry(retry_state: RetryCallState) -> None:
    logger.warning(
        "Tentativa {} falhou — próxima em {:.1f}s | erro: {}",
        retry_state.attempt_number,
        retry_state.next_action.sleep,  # type: ignore[union-attr]
        retry_state.outcome.exception(),  # type: ignore[union-attr]
    )


publisher_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    before_sleep=_log_retry,
    reraise=True,
)

telegram_retry = publisher_retry  # alias de compatibilidade
