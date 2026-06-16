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
    is_price_low: bool = False

    def __post_init__(self) -> None:
        if (
            self.discount_pct is None
            and self.old_price is not None
            and self.old_price > self.price > 0
        ):
            self.discount_pct = int((1 - self.price / self.old_price) * 100)
