import pytest
from src.models import Deal
from src.services.dedup_filter import DedupFilter


def _deal(url: str, old_price: float | None = None) -> Deal:
    return Deal(title="Produto Teste", url=url, price=99.90, old_price=old_price, source="test")


@pytest.fixture
def dedup(tmp_path):
    f = DedupFilter(db_path=tmp_path / "test.db")
    yield f
    f.close()


def test_new_deal_is_new(dedup):
    assert dedup.is_new(_deal("https://example.com/produto/1")) is True


def test_seen_deal_is_not_new(dedup):
    deal = _deal("https://example.com/produto/2")
    dedup.mark_seen(deal)
    assert dedup.is_new(deal) is False


def test_different_urls_are_independent(dedup):
    deal_a = _deal("https://example.com/produto/a")
    deal_b = _deal("https://example.com/produto/b")
    dedup.mark_seen(deal_a)
    assert dedup.is_new(deal_b) is True


def test_mark_seen_is_idempotent(dedup):
    deal = _deal("https://example.com/produto/3")
    dedup.mark_seen(deal)
    dedup.mark_seen(deal)  # segunda chamada não deve lançar erro
    assert dedup.is_new(deal) is False


def test_discount_pct_calculated_automatically():
    deal = _deal("https://example.com/produto/4", old_price=199.90)
    assert deal.discount_pct == 50


def test_discount_pct_none_when_no_old_price():
    deal = _deal("https://example.com/produto/5")
    assert deal.discount_pct is None
