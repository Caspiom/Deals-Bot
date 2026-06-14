import sys
from loguru import logger
from src.config.settings import LOG_LEVEL, LOG_FILE


def setup_logger() -> None:
    logger.remove()

    logger.add(
        sys.stdout,
        level=LOG_LEVEL,
        colorize=True,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan> - <level>{message}</level>"
        ),
    )

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        LOG_FILE,
        level=LOG_LEVEL,
        rotation="00:00",
        retention="7 days",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )


setup_logger()
