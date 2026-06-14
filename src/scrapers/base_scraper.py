from abc import ABC, abstractmethod
from src.models import Deal


class BaseScraper(ABC):
    name: str = "base"

    @abstractmethod
    async def fetch(self) -> list[Deal]:
        """Coleta e retorna lista de deals da fonte. Implementado por cada scraper concreto."""
        ...
