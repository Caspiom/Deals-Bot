from fastapi import FastAPI
from fastapi.responses import RedirectResponse, JSONResponse

from src.services.tracker import ClickTracker

app = FastAPI(title="Achadinhos Tracker", docs_url=None, redoc_url=None)
_tracker = ClickTracker()


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
