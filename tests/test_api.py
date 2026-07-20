import pytest
from fastapi.testclient import TestClient

from src.models import Deal
from src.services.catalog import DealCatalog, deal_id


@pytest.fixture
def client(tmp_path, monkeypatch):
    """API apontando para um banco temporário, isolado do banco real."""
    import src.api.app as app_module

    catalog = DealCatalog(db_path=tmp_path / "api.db")
    monkeypatch.setattr(app_module, "_catalog", catalog)
    with TestClient(app_module.app) as c:
        yield c, catalog
    catalog.close()


def _deal(title="Fone Bluetooth XB500", price=99.90, store="KaBuM") -> Deal:
    return Deal(
        title=title,
        url=f"https://loja.com/{title.replace(' ', '-')}",
        price=price,
        old_price=price * 2,
        source="test",
        store=store,
    )


def test_deals_empty_by_default(client):
    c, _ = client
    body = c.get("/deals").json()
    assert body["total"] == 0 and body["items"] == []


def test_deals_returns_active_products(client):
    c, catalog = client
    catalog.upsert_many([_deal()])
    body = c.get("/deals").json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["title"] == "Fone Bluetooth XB500"
    assert item["discount_pct"] == 50
    assert "affiliate_url" in item


def test_deals_search_query(client):
    c, catalog = client
    catalog.upsert_many([_deal("Fone Bluetooth"), _deal("Cadeira Gamer")])
    assert c.get("/deals", params={"q": "cadeira"}).json()["total"] == 1


def test_deals_rejects_invalid_sort(client):
    c, _ = client
    assert c.get("/deals", params={"sort": "; DROP TABLE"}).status_code == 422


def test_deals_rejects_out_of_range_limit(client):
    c, _ = client
    assert c.get("/deals", params={"limit": 5000}).status_code == 422


def test_deal_detail(client):
    c, catalog = client
    d = _deal()
    catalog.upsert_many([d])
    assert c.get(f"/deals/{deal_id(d)}").json()["title"] == d.title


def test_deal_detail_404_when_out_of_promo(client):
    c, _ = client
    assert c.get("/deals/naoexiste").status_code == 404


def test_filters_endpoint(client):
    c, catalog = client
    catalog.upsert_many([_deal("A", store="KaBuM"), _deal("B", store="Amazon")])
    body = c.get("/filters").json()
    assert {s["value"] for s in body["stores"]} == {"KaBuM", "Amazon"}
    assert "categories" in body


def test_cors_header_present(client):
    c, _ = client
    resp = c.get("/deals", headers={"Origin": "https://achadinhosbr.com"})
    assert "access-control-allow-origin" in resp.headers
