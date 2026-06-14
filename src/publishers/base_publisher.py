from abc import ABC, abstractmethod
from src.models import Deal


class BasePublisher(ABC):
    name: str = "base"

    @abstractmethod
    async def publish(self, deal: Deal) -> None:
        """Formata e publica um deal na plataforma. Implementado por cada publisher concreto."""
        ...
