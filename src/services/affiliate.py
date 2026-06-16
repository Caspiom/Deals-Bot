import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from src.config.settings import AFFILIATE_ID, AMAZON_ASSOCIATE_TAG

# Domínios de agregadores que interceptam a comissão de afiliado.
# Deals cujas URLs pertençam a esses domínios são descartados na pipeline.
_AGGREGATOR_DOMAINS: frozenset[str] = frozenset({
    "promobit.com.br",
    "pelando.com.br",
    "promoby.me",          # encurtador interno do Promobit
    "zoom.com.br",
    "buscape.com.br",
    "bondfaro.com.br",
    "comparaonline.com.br",
    "menor-preco.com.br",
    "buscapé.com.br",
    "cuponomia.com.br",
    "meliuz.com.br",
})


def is_commissionable(url: str) -> bool:
    """Retorna True se a URL pertence a uma loja direta onde podemos injetar nossa tag de afiliado.
    Retorna False para URLs de agregadores que retêm a comissão."""
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    return not any(domain == agg or domain.endswith("." + agg) for agg in _AGGREGATOR_DOMAINS)


def convert(url: str) -> str:
    """Converte URL de produto em link de afiliado. Pronto para receber integrações reais."""
    if "amazon.com.br" in url:
        return _amazon(url)
    if "magazineluiza.com.br" in url or "magalu.com.br" in url:
        return _magalu(url)
    if "mercadolivre.com.br" in url or "mercadolibre.com.br" in url:
        return _mercadolivre(url)
    if "shopee.com.br" in url:
        return _shopee(url)
    return _default(url)


def _amazon(url: str) -> str:
    # Extrai ASIN e reconstrói URL canônica — elimina /ref=... e parâmetros de tracking
    m = re.search(r"/dp/([A-Z0-9]{10})", url)
    if m:
        return f"https://www.amazon.com.br/dp/{m.group(1)}?tag={AMAZON_ASSOCIATE_TAG}"
    # Fallback: URL sem /dp/{ASIN} — injeta tag sem modificar o path
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params["tag"] = [AMAZON_ASSOCIATE_TAG]
    return urlunparse(parsed._replace(query=urlencode(params, doseq=True)))


def _magalu(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params["partner_id"] = [AFFILIATE_ID]
    return urlunparse(parsed._replace(query=urlencode(params, doseq=True)))


def _mercadolivre(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params["partner_id"] = [AFFILIATE_ID]
    return urlunparse(parsed._replace(query=urlencode(params, doseq=True)))


def _shopee(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params["af_id"] = [AFFILIATE_ID]
    return urlunparse(parsed._replace(query=urlencode(params, doseq=True)))


def _default(url: str) -> str:
    return url
