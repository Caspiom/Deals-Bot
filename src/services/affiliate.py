from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from src.config.settings import AFFILIATE_ID, AMAZON_ASSOCIATE_TAG


def convert(url: str) -> str:
    """Converte URL de produto em link de afiliado. Pronto para receber integrações reais."""
    if "amazon.com.br" in url:
        return _amazon(url)
    if "magazineluiza.com.br" in url or "magalu.com.br" in url:
        return _magalu(url)
    return _default(url)


def _amazon(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params["tag"] = [AMAZON_ASSOCIATE_TAG]
    return urlunparse(parsed._replace(query=urlencode(params, doseq=True)))


def _magalu(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params["partner_id"] = [AFFILIATE_ID]
    return urlunparse(parsed._replace(query=urlencode(params, doseq=True)))


def _default(url: str) -> str:
    # Mock para fontes sem integração oficial — substituir pela API real futuramente
    return f"https://shope.ee/exemplo?afiliado={AFFILIATE_ID}"
