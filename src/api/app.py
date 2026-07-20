import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse

from src.config.settings import API_TOKEN, CORS_ORIGINS
from src.services.catalog import DealCatalog
from src.services.tracker import ClickTracker

app = FastAPI(title="Achadinhos BR", docs_url="/docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def exige_token(x_api_token: str = Header(default="")) -> None:
    """Protege os dados do catálogo quando a API está exposta na internet.

    API_TOKEN vazio libera o acesso — é o modo de desenvolvimento local. A
    comparação usa compare_digest para não vazar o segredo pelo tempo de
    resposta.
    """
    if not API_TOKEN:
        return
    if not secrets.compare_digest(x_api_token, API_TOKEN):
        raise HTTPException(status_code=401, detail="token inválido ou ausente")


_tracker = ClickTracker()
_catalog = DealCatalog()


@app.get("/deals", dependencies=[Depends(exige_token)])
async def list_deals(
    q: str = Query("", description="Busca por título"),
    store: str = "",
    group: str = Query("", description="Grupo exibido no site (ver /filters)"),
    category: str = Query("", description="Categoria fina, mais específica que o grupo"),
    min_discount: int = Query(0, ge=0, le=100),
    max_price: float | None = Query(None, gt=0),
    sort: str = Query("discount", pattern="^(discount|price_asc|price_desc|recent)$"),
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Produtos atualmente em promoção. Quem sai de promoção deixa de aparecer."""
    return _catalog.search(
        q=q, store=store, category=category, group=group, min_discount=min_discount,
        max_price=max_price, sort=sort, limit=limit, offset=offset,
    )


@app.get("/deals/{deal_id}", dependencies=[Depends(exige_token)])
async def get_deal(deal_id: str):
    deal = _catalog.get(deal_id)
    if not deal:
        return JSONResponse({"error": "produto não está mais em promoção"}, status_code=404)
    return deal


@app.get("/filters", dependencies=[Depends(exige_token)])
async def filters():
    """Lojas e categorias disponíveis, com contagem — para montar os filtros."""
    return _catalog.facets()


# Sem token de propósito: é o link que o usuário final clica no Telegram.
@app.get("/r/{deal_id}")
async def redirect(deal_id: str, s: str = ""):
    url = _tracker.get_affiliate_url(deal_id)
    if not url:
        return JSONResponse({"error": "link não encontrado"}, status_code=404)
    _tracker.log_click(deal_id, s)
    return RedirectResponse(url, status_code=302)


@app.get("/stats", dependencies=[Depends(exige_token)])
async def stats():
    return _tracker.get_stats()


@app.get("/health")
async def health():
    """Endpoint público de monitoramento — não expõe dado do catálogo."""
    return {"status": "ok"}
