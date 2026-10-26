"""FastAPI entrypoint: HTML pages + JSON API."""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from . import risk as riskmod
from .ai import GeminiAgent, MockAgent
from .config import Settings
from .db import DB
from .services import FlowError, JalParakh
from .standards import STRIP_PARAMS, limits_table

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent

log = logging.getLogger("jalparakh")
if not log.handlers:  # make INFO lines visible in Render / uvicorn logs
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s:     [jalparakh] %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False


def log_available_flash_models(agent: GeminiAgent) -> None:
    """One startup line listing 'flash' models visible to the key (never prints the key). Best effort."""
    try:
        names = agent.list_flash_models(timeout=8.0)
        log.info("Gemini models with 'flash' available to this key: %s (using %s%s)",
                 ", ".join(names) or "none", agent.model,
                 f", fallback {agent.fallback_model}" if agent.fallback_model else "")
    except Exception as e:  # noqa: BLE001 - diagnostics only
        log.info("Could not list Gemini models at startup: %s", type(e).__name__)


class ManualBody(BaseModel):
    values: dict[str, float | str | None]
    state: str = ""
    district: str = ""
    pincode: str = ""
    lang: str = "hi"
    practice: bool = False


class RateLimiter:
    """In-memory sliding window per client IP. IPs are kept only in memory, only for 10 minutes."""

    def __init__(self, limit: int, window: float = 600.0):
        self.limit, self.window = limit, window
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if self.limit <= 0:
            return True
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True


def create_app(settings: Settings | None = None, agent=None) -> FastAPI:
    settings = settings or Settings()
    db = DB(settings.database_path)
    if agent is None:
        if settings.ai_mock:
            agent = MockAgent()
        else:
            agent = GeminiAgent(settings.gemini_api_key, settings.gemini_model,
                                fallback_model=settings.gemini_fallback_model,
                                timeout=settings.gemini_timeout, budget=settings.gemini_total_budget)
            threading.Thread(target=log_available_flash_models, args=(agent,), name="jalparakh-models",
                             daemon=True).start()
    svc = JalParakh(settings, db, agent)
    limiter = RateLimiter(settings.rate_limit)

    app = FastAPI(title="Jal Parakh", description="Agentic AI water-safety assistant for India.", version="1.0.0")
    app.state.svc = svc
    app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
    app.mount("/demo_assets", StaticFiles(directory=ROOT / "demo_assets"), name="demo_assets")
    templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

    @app.exception_handler(FlowError)
    async def flow_error(_: Request, exc: FlowError):
        return JSONResponse({"error": str(exc)}, status_code=exc.status_code)

    def ctx(request: Request, **kw):
        return {"request": request, "modes": settings.summary(), "ai_mock": settings.ai_mock, **kw}

    def client_key(request: Request) -> str:
        fwd = request.headers.get("x-forwarded-for", "")
        return (fwd.split(",")[0].strip() if fwd else "") or (request.client.host if request.client else "?")

    def get_test(test_id: str) -> dict:
        t = db.get_test(test_id)
        if not t:
            raise HTTPException(404, "Test not found")
        return t

    # ------------------------------------------------------------- pages
    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        return templates.TemplateResponse(request, "index.html", ctx(request, params=STRIP_PARAMS))

    @app.get("/t/{test_id}", response_class=HTMLResponse)
    def test_page(request: Request, test_id: str):
        get_test(test_id)
        return templates.TemplateResponse(request, "test.html", ctx(request, test_id=test_id))

    @app.get("/impact", response_class=HTMLResponse)
    def impact_page(request: Request):
        return templates.TemplateResponse(request, "impact.html", ctx(request))

    @app.get("/about", response_class=HTMLResponse)
    def about_page(request: Request):
        return templates.TemplateResponse(request, "about.html", ctx(request, limits=limits_table()))

    @app.get("/healthz")
    def health():
        return {"ok": True, **settings.summary()}

    # --------------------------------------------------------------- API
    @app.post("/api/tests")
    async def api_strip(request: Request, photo: UploadFile = File(...), state: str = Form(""),
                        district: str = Form(""), pincode: str = Form(""), lang: str = Form("hi"),
                        practice: bool = Form(False)):
        if not limiter.allow(client_key(request)):
            raise FlowError("rate_limited", 429)
        blob = await photo.read(int(settings.max_photo_mb * 1024 * 1024) + 1)
        from starlette.concurrency import run_in_threadpool
        t = await run_in_threadpool(svc.create_strip_test, blob, photo.content_type or "", photo.filename or "",
                                    state, district, pincode, lang, practice)
        return svc.view(db.get_test(t["id"]))

    @app.post("/api/manual")
    def api_manual(request: Request, body: ManualBody):
        if not limiter.allow(client_key(request)):
            raise FlowError("rate_limited", 429)
        t = svc.create_manual_test(body.values, body.state, body.district, body.pincode, body.lang, body.practice)
        return svc.view(db.get_test(t["id"]))

    @app.get("/api/tests/{test_id}")
    def api_test(test_id: str):
        return svc.view(get_test(test_id))

    @app.post("/api/tests/{test_id}/complaint")
    def api_complaint(test_id: str, lang: str = "hi"):
        return svc.complaint(test_id, lang)

    @app.get("/api/risk")
    def api_risk(state: str = "", district: str = "", pincode: str = ""):
        place = svc.resolve_place(state, district, pincode)
        if not (place["state"] or place["district"]):
            raise FlowError("place_not_found", 404)
        out = riskmod.district_risk(place["state"], place["district"])
        out["pincode_via"] = place.get("pincode_via")
        return out

    @app.get("/api/places")
    def api_places(state: str = ""):
        if state:
            return {"state": riskmod.canonical_state(state), "districts": riskmod.district_names(state)}
        return {"states": [{"en": s, "hi": riskmod.STATE_HI.get(s, s)} for s in riskmod.STATES]}

    @app.get("/api/limits")
    def api_limits():
        return {"standard": "BIS IS 10500:2012", "limits": limits_table()}

    @app.get("/api/impact")
    def api_impact(include_demo: bool = False):
        return svc.impact(include_demo)

    @app.get("/api/impact.csv")
    def api_impact_csv(include_demo: bool = False):
        return Response(svc.impact_csv(include_demo), media_type="text/csv",
                        headers={"Content-Disposition": 'attachment; filename="jal-parakh-reports.csv"'})

    @app.get("/api/risk-layer")
    def api_risk_layer():
        return {"source": riskmod.SRC_FA, "districts": riskmod.risk_layer()}

    @app.post("/api/admin/import")
    async def api_import(request: Request):
        token = request.headers.get("x-admin-token", "")
        if not settings.admin_token or token != settings.admin_token:
            raise FlowError("forbidden", 403)
        n = svc.import_csv((await request.body()).decode("utf-8", "replace"))
        return {"imported": n}

    @app.get("/robots.txt", response_class=PlainTextResponse)
    def robots():
        return "User-agent: *\nAllow: /\nDisallow: /t/\n"

    return app


app = create_app()
