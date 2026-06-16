from src.services.affiliate import convert, is_commissionable
from src.config.settings import AMAZON_ASSOCIATE_TAG, AFFILIATE_ID


def test_amazon_url_receives_tag():
    url = "https://www.amazon.com.br/dp/B0CX1234AB"
    result = convert(url)
    assert f"tag={AMAZON_ASSOCIATE_TAG}" in result


def test_amazon_url_preserves_existing_params():
    url = "https://www.amazon.com.br/dp/B0CX1234AB?ref=sr_1_1"
    result = convert(url)
    assert "ref=sr_1_1" in result
    assert f"tag={AMAZON_ASSOCIATE_TAG}" in result


def test_magalu_url_receives_partner_id():
    url = "https://www.magazineluiza.com.br/produto/mock/p/001/et/"
    result = convert(url)
    assert f"partner_id={AFFILIATE_ID}" in result


def test_unknown_source_returns_original_url():
    url = "https://www.kabum.com.br/produto/123456"
    assert convert(url) == url


def test_convert_always_returns_string():
    for url in [
        "https://www.amazon.com.br/dp/B001",
        "https://www.magazineluiza.com.br/p/001/",
        "https://www.kabum.com.br/produto/999",
    ]:
        assert isinstance(convert(url), str)


# ── is_commissionable ────────────────────────────────────────────────────────

def test_commissionable_direct_store_urls():
    assert is_commissionable("https://www.kabum.com.br/produto/123") is True
    assert is_commissionable("https://www.amazon.com.br/dp/B001") is True
    assert is_commissionable("https://www.mercadolivre.com.br/produto") is True
    assert is_commissionable("https://www.magazineluiza.com.br/produto/p/001/") is True
    assert is_commissionable("https://www.netshoes.com.br/produto") is True
    assert is_commissionable("https://www.casasbahia.com.br/produto") is True


def test_not_commissionable_aggregator_urls():
    assert is_commissionable("https://www.promobit.com.br/oferta/produto-123") is False
    assert is_commissionable("https://www.pelando.com.br/produto/exemplo") is False
    assert is_commissionable("https://promoby.me/abc123") is False
    assert is_commissionable("https://www.zoom.com.br/produto/abc") is False
    assert is_commissionable("https://www.buscape.com.br/produto") is False
    assert is_commissionable("https://www.meliuz.com.br/i/xxxxxx") is False
