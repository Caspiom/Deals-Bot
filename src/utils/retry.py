from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential, RetryCallState
from loguru import logger


def _log_retry(retry_state: RetryCallState) -> None:
    logger.warning(
        "Tentativa {} falhou — próxima em {:.1f}s | erro: {}",
        retry_state.attempt_number,
        retry_state.next_action.sleep,  # type: ignore[union-attr]
        retry_state.outcome.exception(),  # type: ignore[union-attr]
    )


def _is_retriable(exc: BaseException) -> bool:
    """Não retenta erros HTTP permanentes (4xx exceto 429 rate-limit)."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status is not None and 400 <= status < 500 and status != 429:
        return False
    return True


publisher_retry = retry(
    retry=retry_if_exception(_is_retriable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    before_sleep=_log_retry,
    reraise=True,
)

telegram_retry = publisher_retry  # alias de compatibilidade
