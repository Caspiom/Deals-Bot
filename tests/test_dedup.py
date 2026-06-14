import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import patch

from src.models import Deal
from src.services.dedup_filter import DedupFilter


def _deal(url: str, old_price: float | None = None, discount_pct: int | None = None) -> Deal:
    d = Deal(title="Produto Teste", url=url, price=99.90, old_price=old_price, source="test")
    if discount_pct is not None:
        object.__setattr__(d, "discount_pct", discount_pct)
    return d


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
    dedup.mark_seen(deal)
    assert dedup.is_new(deal) is False


def test_discount_pct_calculated_automatically():
    deal = _deal("https://example.com/produto/4", old_price=199.90)
    assert deal.discount_pct == 50


def test_discount_pct_none_when_no_old_price():
    deal = _deal("https://example.com/produto/5")
    assert deal.discount_pct is None


# ── can_repost ────────────────────────────────────────────────────────────────

def test_can_repost_false_for_unseen_deal(dedup):
    deal = _deal("https://example.com/produto/hot", discount_pct=50)
    assert dedup.can_repost(deal) is False


def test_can_repost_false_when_low_discount(dedup):
    deal = _deal("https://example.com/produto/cheap", discount_pct=20)
    dedup.mark_seen(deal)
    # mesmo que o intervalo tenha passado, desconto insuficiente
    past = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
    dedup._conn.execute(
        "UPDATE seen_deals SET last_posted_at = ? WHERE url_hash = ?",
        (past, dedup._hash(deal.url)),
    )
    dedup._conn.commit()
    assert dedup.can_repost(deal) is False


def test_can_repost_false_when_interval_not_elapsed(dedup):
    deal = _deal("https://example.com/produto/recent", discount_pct=50)
    dedup.mark_seen(deal)
    # last_posted_at = agora → intervalo ainda não decorreu
    assert dedup.can_repost(deal) is False


def test_can_repost_true_when_interval_elapsed(dedup):
    deal = _deal("https://example.com/produto/elapsed", discount_pct=50)
    dedup.mark_seen(deal)
    past = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
    dedup._conn.execute(
        "UPDATE seen_deals SET last_posted_at = ? WHERE url_hash = ?",
        (past, dedup._hash(deal.url)),
    )
    dedup._conn.commit()
    assert dedup.can_repost(deal) is True


def test_mark_seen_updates_last_posted_at(dedup):
    deal = _deal("https://example.com/produto/update", discount_pct=50)
    dedup.mark_seen(deal)

    # simula que a primeira postagem foi há 3h
    past = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
    dedup._conn.execute(
        "UPDATE seen_deals SET last_posted_at = ? WHERE url_hash = ?",
        (past, dedup._hash(deal.url)),
    )
    dedup._conn.commit()
    assert dedup.can_repost(deal) is True

    # re-posta → mark_seen atualiza last_posted_at para agora
    dedup.mark_seen(deal)
    assert dedup.can_repost(deal) is False


def test_seen_at_preserved_on_repost(dedup):
    deal = _deal("https://example.com/produto/seen-at", discount_pct=50)

    original_time = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    dedup._conn.execute(
        "INSERT INTO seen_deals (url_hash, seen_at, last_posted_at) VALUES (?, ?, ?)",
        (dedup._hash(deal.url), original_time, original_time),
    )
    dedup._conn.commit()

    dedup.mark_seen(deal)

    row = dedup._conn.execute(
        "SELECT seen_at FROM seen_deals WHERE url_hash = ?",
        (dedup._hash(deal.url),),
    ).fetchone()
    # seen_at original deve ser preservado
    assert row[0] == original_time
