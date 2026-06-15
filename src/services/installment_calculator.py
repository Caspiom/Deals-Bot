import re

_MIN_INSTALLMENT_VALUE = 50.0  # valor mínimo por parcela aceito pelo mercado BR
_MAX_INSTALLMENTS = 12


def parse_installment_string(text: str) -> tuple[int, float] | None:
    """Extrai (n, valor) de strings como '10x de R$ 280,00' ou '12x R$83,25'."""
    m = re.search(r"(\d+)x[^R]*R\$\s*([\d.,]+)", text)
    if not m:
        return None
    count = int(m.group(1))
    value = float(m.group(2).replace(".", "").replace(",", "."))
    return count, value


def estimate(price: float) -> tuple[int, float] | None:
    """Estima parcelas sem juros com base no preço. Retorna None se não fizer sentido parcelar."""
    if price < _MIN_INSTALLMENT_VALUE * 2:
        return None
    n = min(_MAX_INSTALLMENTS, int(price // _MIN_INSTALLMENT_VALUE))
    return n, round(price / n, 2)
