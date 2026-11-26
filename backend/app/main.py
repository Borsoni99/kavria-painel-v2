"""Painel KAVRIA v2 (multicanal: Mercado Livre, Shopee, Amazon e TikTok Shop) via API da Jodda AI.

Rodar em dev (a partir de backend/):  .venv\\Scripts\\python -m uvicorn app.main:app --port 8001
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api import admin, auth, tv
from app.api.auth import NotAuthenticated, is_admin
from app.backup import backup_loop
from app.config import DATA_DIR, FRONTEND_DIST, get_settings
from app.migrate import run_migrations
from app.security import new_secret
from app.sources.jodda.client import jodda
from app.sources.jodda.sync import orders_loop, summaries_loop

log = logging.getLogger("app")


def setup_logging() -> None:
    logs = DATA_DIR / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler = RotatingFileHandler(logs / "app.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        root.addHandler(file_handler)
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        root.addHandler(console)
    logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    await asyncio.to_thread(run_migrations)
    tasks: list[asyncio.Task] = [asyncio.create_task(tv.hub.run()), asyncio.create_task(backup_loop())]
    if get_settings().workers_enabled:
        tasks += [asyncio.create_task(orders_loop()), asyncio.create_task(summaries_loop())]
        log.info("Sincronização com a Jodda ativa")
    else:
        log.warning("WORKERS_ENABLED=false: esta instância não sincroniza com a Jodda")
    yield
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await jodda.aclose()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Kavria Painel v2", lifespan=lifespan, docs_url=None, redoc_url=None)
    secret = s.app_secret
    if len(secret) < 32:
        logging.getLogger("app").error("APP_SECRET ausente/curto: sessões não sobrevivem a reinícios")
        secret = new_secret()
    app.add_middleware(SessionMiddleware, secret_key=secret, same_site="lax",
                       https_only=s.public_base_url.startswith("https://"), max_age=7 * 24 * 3600)

    @app.exception_handler(NotAuthenticated)
    async def _login_redirect(_request: Request, _exc: NotAuthenticated):
        return RedirectResponse("/admin/login", status_code=303)

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    @app.get("/")
    async def root():
        return RedirectResponse("/admin", status_code=303)

    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(tv.router)
    _mount_frontend(app)
    return app


def _icon_route(path):
    async def icon():
        if not path.exists():
            return Response(status_code=404)
        return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})
    return icon


def _mount_frontend(app: FastAPI) -> None:
    """Serve o build do React (frontend/dist). Rotas do admin exigem login."""
    index = FRONTEND_DIST / "index.html"
    if (FRONTEND_DIST / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")
    for name in ("favicon.ico", "icon-192.png", "apple-touch-icon.png"):
        app.add_api_route(f"/{name}", _icon_route(FRONTEND_DIST / name), methods=["GET"], include_in_schema=False)

    @app.get("/tv", include_in_schema=False)
    async def tv_page():
        if not index.exists():
            return HTMLResponse("Frontend não compilado: rode `npm run build` em frontend/", status_code=503)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    @app.get("/admin", include_in_schema=False)
    @app.get("/admin/{path:path}", include_in_schema=False)
    async def admin_spa(request: Request, path: str = ""):
        if not is_admin(request):
            return RedirectResponse("/admin/login", status_code=303)
        if not index.exists():
            return HTMLResponse("Frontend não compilado: rode `npm run build` em frontend/", status_code=503)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = create_app()
