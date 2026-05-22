"""FastAPI entry point.

`lifespan` runs at startup/shutdown: opens the Postgres pool, builds the
OIDC authenticator (which fetches Keycloak metadata + JWKS once), and
exposes both on `app.state` so dependencies can pick them up per-request.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth import Authenticator
from .config import get_settings
from .db import open_pool
from .routers import api as api_router
from .routers import auth as auth_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("taskboard")

UI_DIST = Path(__file__).resolve().parent.parent / "ui" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log.info("starting (issuer=%s, public=%s)", settings.oidc_issuer, settings.public_base_url)

    app.state.pool = await open_pool(settings.database_url)
    app.state.auth = await Authenticator.build(
        issuer=settings.oidc_issuer,
        client_id=settings.oidc_client_id,
        redirect_uri=settings.oidc_redirect_uri,
        cookie_insecure=settings.cookie_insecure,
    )

    try:
        yield
    finally:
        log.info("shutting down")
        await app.state.pool.close()


app = FastAPI(title="taskboard", lifespan=lifespan)

app.include_router(auth_router.router)
app.include_router(api_router.router)


@app.get("/healthz", include_in_schema=False)
async def healthz():
    return {"status": "ok"}


# --- SPA serving (mounted last so /api/* and /auth/* win) ---


def _mount_spa(app: FastAPI) -> None:
    """Serve the built SPA, falling back to index.html for client-side routes."""
    index = UI_DIST / "index.html"
    assets = UI_DIST / "assets"

    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        candidate = (UI_DIST / full_path).resolve()
        # Path traversal guard: candidate must stay inside UI_DIST.
        try:
            candidate.relative_to(UI_DIST.resolve())
        except ValueError:
            return FileResponse(index) if index.exists() else _no_ui()
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index) if index.exists() else _no_ui()


def _no_ui():
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse("UI not built yet. Run `npm run build` in src/taskboard/ui.", status_code=503)


_mount_spa(app)
