def brl(value: float) -> str:
    """Formata float como moeda brasileira: 1234.56 → R$ 1.234,56"""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
