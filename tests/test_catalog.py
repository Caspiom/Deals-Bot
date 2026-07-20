import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import patch

from src.models import Deal
from src.services.catalog import DealCatalog, deal_id


def _deal(title="Fone Bluetooth XB500", price=99.90, url=None, **kw) -> Deal:
    return Deal(
        title=title,
        url=url or f"https://loja.com/{title.replace(' ', '-')}",
        price=price,
        old_price=kw.pop("old_price", 199.90),
        source=kw.pop("source", "test"),
        store=kw.pop("store", "KaBuM"),
        **kw,
    )


@pytest.fixture
def catalog(tmp_path):
    c = DealCatalog(db_path=tmp_path / "catalog.db")
    yield c
    c.close()


def _age(catalog: DealCatalog, deal: Deal, minutes: int) -> None:
    """Empurra last_seen_at para o passado, simulando ciclos sem ver o produto."""
    past = (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()
    catalog._conn.execute(
        "UPDATE catalog_deals SET last_seen_at = ? WHERE id = ?", (past, deal_id(deal))
    )
    catalog._conn.commit()


# ── ciclo de vida: em promoção → fora de promoção ────────────────────────────

def test_deal_appears_after_upsert(catalog):
    catalog.upsert_many([_deal()])
    assert catalog.search()["total"] == 1


def test_deal_disappears_when_no_longer_scraped(catalog):
    """Regra central do site: saiu de promoção → some da API."""
    d = _deal()
    catalog.upsert_many([d])
    _age(catalog, d, minutes=10_000)
    assert catalog.search()["total"] == 0
    assert catalog.get(deal_id(d)) is None


def test_deal_stays_while_still_scraped(catalog):
    d = _deal()
    catalog.upsert_many([d])
    _age(catalog, d, minutes=10_000)
    catalog.upsert_many([d])  # visto de novo no ciclo seguinte
    assert catalog.search()["total"] == 1


def test_upsert_updates_price_and_keeps_first_seen(catalog):
    d = _deal(price=100.0)
    catalog.upsert_many([d])
    first_seen = catalog.get(deal_id(d))["first_seen_at"]

    catalog.upsert_many([_deal(price=80.0)])
    row = catalog.get(deal_id(d))
    assert row["price"] == 80.0
    assert row["first_seen_at"] == first_seen


# ── busca e filtros ──────────────────────────────────────────────────────────

def test_search_by_title(catalog):
    catalog.upsert_many([_deal("Fone Bluetooth"), _deal("Cadeira Gamer")])
    assert catalog.search(q="fone")["total"] == 1


def test_filter_by_store(catalog):
    catalog.upsert_many([_deal("A", store="KaBuM"), _deal("B", store="Amazon")])
    assert catalog.search(store="Amazon")["total"] == 1


def test_filter_by_min_discount(catalog):
    catalog.upsert_many([
        _deal("Barato", price=50.0, old_price=100.0),   # 50%
        _deal("Fraco", price=90.0, old_price=100.0),    # 10%
    ])
    assert catalog.search(min_discount=40)["total"] == 1


def test_filter_by_max_price(catalog):
    catalog.upsert_many([_deal("Caro", price=500.0), _deal("Barato", price=50.0)])
    res = catalog.search(max_price=100.0)
    assert res["total"] == 1 and res["items"][0]["title"] == "Barato"


def test_sort_price_asc(catalog):
    catalog.upsert_many([_deal("Caro", price=500.0), _deal("Barato", price=50.0)])
    items = catalog.search(sort="price_asc")["items"]
    assert [i["price"] for i in items] == [50.0, 500.0]


def test_pagination_reports_total(catalog):
    catalog.upsert_many([_deal(f"Produto {i}", price=10.0 + i) for i in range(5)])
    res = catalog.search(limit=2, offset=2)
    assert res["total"] == 5 and len(res["items"]) == 2


def test_facets_only_count_active(catalog):
    a, b = _deal("A", store="KaBuM"), _deal("B", store="Amazon")
    catalog.upsert_many([a, b])
    _age(catalog, b, minutes=10_000)
    stores = {s["value"]: s["count"] for s in catalog.facets()["stores"]}
    assert stores == {"KaBuM": 1}


def test_purge_removes_long_expired(catalog):
    d = _deal()
    catalog.upsert_many([d])
    _age(catalog, d, minutes=10_000_000)
    assert catalog.purge_expired() == 1


# ── categoria acompanha o título ─────────────────────────────────────────────

def test_upsert_refreshes_category(catalog):
    """Categoria é derivada do título: congelá-la prende o produto na
    classificação do primeiro ciclo, mesmo depois do título melhorar."""
    generic = _deal(title="Produto sem termo reconhecível")
    catalog.upsert_many([generic])
    assert catalog.get(deal_id(generic))["category"] == "geral"

    # mesmo produto (mesma url → mesmo id), agora com título identificável
    improved = _deal(title="Produto sem termo reconhecível")
    improved.raw_title = "Fone de ouvido bluetooth sem fio"
    catalog.upsert_many([improved])
    assert catalog.get(deal_id(improved))["category"] == "fone_headset"


def test_upsert_refreshes_tax_note(catalog):
    d = _deal()
    catalog.upsert_many([d])
    assert catalog.get(deal_id(d))["tax_note"] is None

    with_note = _deal()
    with_note.tax_note = "🌐 Preço com impostos incluídos"
    catalog.upsert_many([with_note])
    assert catalog.get(deal_id(with_note))["tax_note"] == "🌐 Preço com impostos incluídos"


# ── grupos exibidos no site ──────────────────────────────────────────────────

def test_group_derived_from_category(catalog):
    d = _deal()
    d.raw_title = "Placa de Vídeo RTX 5070"
    catalog.upsert_many([d])
    row = catalog.get(deal_id(d))
    assert row["category"] == "hardware_pc"
    assert row["category_group"] == "informatica"


def test_filter_by_group(catalog):
    gpu = _deal("GPU", store="KaBuM")
    gpu.raw_title = "Placa de Vídeo RTX 5070"
    fone = _deal("Fone", store="KaBuM")
    fone.raw_title = "Fone de ouvido bluetooth"
    catalog.upsert_many([gpu, fone])

    assert catalog.search(group="informatica")["total"] == 1
    assert catalog.search(group="audio")["total"] == 1


def test_facets_expose_groups(catalog):
    d = _deal()
    d.raw_title = "Placa de Vídeo RTX 5070"
    catalog.upsert_many([d])
    grupos = {g["value"]: g["count"] for g in catalog.facets()["groups"]}
    assert grupos == {"informatica": 1}


def test_unmapped_category_falls_back_to_outros(catalog):
    """Categoria sem grupo definido não pode sumir do filtro."""
    catalog.upsert_many([_deal(title="Produto sem termo reconhecível")])
    row = catalog.get(deal_id(_deal(title="Produto sem termo reconhecível")))
    assert row["category"] == "geral"
    assert row["category_group"] == "outros"
