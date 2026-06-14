from src.services.affiliate import convert
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


def test_unknown_source_returns_shope_link():
    url = "https://www.kabum.com.br/produto/123456"
    result = convert(url)
    assert "shope.ee" in result
    assert AFFILIATE_ID in result


def test_convert_always_returns_string():
    for url in [
        "https://www.amazon.com.br/dp/B001",
        "https://www.magazineluiza.com.br/p/001/",
        "https://www.kabum.com.br/produto/999",
    ]:
        assert isinstance(convert(url), str)
