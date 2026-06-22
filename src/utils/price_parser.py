import re

# Busca agressiva: extrai o primeiro padrão monetário BRL da string,
# ignorando qualquer texto antes ("Com oferta especial: R$ 45,90" → 45.90).
_BRL_RE = re.compile(r'R\$\s*([\d.,]+)')


def parse_brl(text: str | None) -> float | None:
    if not text:
        return None
    m = _BRL_RE.search(text)
    if m:
        cleaned = m.group(1)
    else:
        cleaned = re.sub(r'[^\d.,]', '', text)
    if not cleaned:
        return None
    if ',' in cleaned and '.' in cleaned:
        cleaned = cleaned.replace('.', '').replace(',', '.')
    elif ',' in cleaned:
        cleaned = cleaned.replace(',', '.')
    elif '.' in cleaned:
        parts = cleaned.split('.')
        if parts[0].isdigit() and all(len(p) == 3 and p.isdigit() for p in parts[1:]):
            cleaned = ''.join(parts)
    try:
        return float(cleaned)
    except ValueError:
        return None
