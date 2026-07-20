from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse

from src.config.settings import CORS_ORIGINS
from src.services.catalog import DealCatalog
from src.services.tracker import ClickTracker

app = FastAPI(title="Achadinhos BR", docs_url="/docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)

_tracker = ClickTracker()
_catalog = DealCatalog()


@app.get("/deals")
async def list_deals(
    q: str = Query("", description="Busca por título"),
    store: str = "",
    category: str = "",
    min_discount: int = Query(0, ge=0, le=100),
    max_price: float | None = Query(None, gt=0),
    sort: str = Query("discount", pattern="^(discount|price_asc|price_desc|recent)$"),
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Produtos atualmente em promoção. Quem sai de promoção deixa de aparecer."""
    return _catalog.search(
        q=q, store=store, category=category, min_discount=min_discount,
        max_price=max_price, sort=sort, limit=limit, offset=offset,
    )


@app.get("/deals/{deal_id}")
async def get_deal(deal_id: str):
    deal = _catalog.get(deal_id)
    if not deal:
        return JSONResponse({"error": "produto não está mais em promoção"}, status_code=404)
    return deal


@app.get("/filters")
async def filters():
    """Lojas e categorias disponíveis, com contagem — para montar os filtros."""
    return _catalog.facets()


@app.get("/r/{deal_id}")
async def redirect(deal_id: str, s: str = ""):
    url = _tracker.get_affiliate_url(deal_id)
    if not url:
        return JSONResponse({"error": "link não encontrado"}, status_code=404)
    _tracker.log_click(deal_id, s)
    return RedirectResponse(url, status_code=302)


@app.get("/stats")
async def stats():
    return _tracker.get_stats()
