from dataclasses import dataclass, field


@dataclass
class Deal:
    title: str
    url: str
    price: float
    old_price: float | None = None
    discount_pct: int | None = None
    image_url: str | None = None
    source: str = "unknown"
    store: str = ""
    tagline: str = ""
    installments: int | None = None
    installment_value: float | None = None
    coupon_code: str | None = None
    coins_discount_value: float | None = None
    affiliate_url: str = ""
    tracked_url: str = ""
    is_price_low: bool = False
    tax_note: str | None = None
    # Chave estável para dedup quando `url` muda a cada coleta (ex: promotion_link
    # do AliExpress, gerado novo a cada chamada da API). Vazio = usa `url`.
    dedup_key: str = ""
    # Título como veio da loja, antes de qualquer limpeza para exibição.
    # Classificação e busca querem o máximo de palavras; o usuário quer o mínimo.
    # Vazio = `title` já é o original.
    raw_title: str = ""

    def text_for_matching(self) -> str:
        """Texto mais rico disponível para classificar o produto."""
        return self.raw_title or self.title

    def key(self) -> str:
        """Identidade estável do produto — base do dedup e do id no catálogo.

        Usa dedup_key quando o scraper fornece um (URL volátil); senão a URL sem
        query string/fragment, para que parâmetros de tracking não criem um novo
        produto a cada coleta."""
        raw = self.dedup_key or self.url
        return raw.split("?")[0].split("#")[0].rstrip("/")

    def __post_init__(self) -> None:
        if (
            self.discount_pct is None
            and self.old_price is not None
            and self.old_price > self.price > 0
        ):
            self.discount_pct = int((1 - self.price / self.old_price) * 100)
