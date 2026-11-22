"""The Claude Lens API: `uvicorn claude_lens.api.main:app`.

On startup it loads settings, opens the connection pool, applies pending
migrations, and bootstraps the admin user when `users` is empty (refusing to
start without ADMIN_USERNAME / ADMIN_PASSWORD in that case). Every router is
mounted under `/api`; all of them need a login except `GET /api/health` and
`POST /api/auth/login` (and the idempotent logout).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Union

from fastapi import APIRouter, Depends, FastAPI

from .. import __version__
from ..config import Settings, load_settings
from ..core.pricing import DEFAULT_PRICING_PATH, make_pricing_loader
from ..db.migrate import migrate
from ..db.pool import make_pool
from . import auth
from .deps import current_user
from .routers import (
    activity, analytics, export, projects, prompts, search, sessions,
    settings as settings_router, tips, tools,
)
from .schemas import Health
from .security import CSRFMiddleware, LoginLockout

POOL_MIN, POOL_MAX = 1, 10
POOL_OPEN_TIMEOUT = 30  # seconds


def create_app(
    settings: Optional[Settings] = None,
    *,
    pricing_path: Union[str, Path] = DEFAULT_PRICING_PATH,
    pool_max: int = POOL_MAX,
) -> FastAPI:
    """Build the app. `settings=None` loads them (env + .env.local) at startup."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        s = settings or load_settings()
        get_pricing = make_pricing_loader(pricing_path)
        get_pricing()  # fail fast if pricing.json is missing or invalid
        pool = make_pool(s, min_size=POOL_MIN, max_size=pool_max, open=False)
        pool.open(wait=True, timeout=POOL_OPEN_TIMEOUT)
        try:
            with pool.connection() as conn:
                migrate(conn, s.db_schema)
                auth.bootstrap_admin(conn, s)
            app.state.settings = s
            app.state.get_pricing = get_pricing
            app.state.pool = pool
            yield
        finally:
            pool.close()

    app = FastAPI(
        title="Claude Lens API",
        description="Usage, cost & workflow analytics for Claude Code.",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.lockout = LoginLockout()
    app.add_middleware(CSRFMiddleware)

    api = APIRouter(prefix="/api")

    @api.get("/health", response_model=Health, tags=["health"])
    def health() -> Health:
        """Liveness probe; needs no login."""
        return Health(status="ok", version=__version__)

    api.include_router(auth.router)
    protected = [Depends(current_user)]
    for module in (analytics, activity, projects, sessions, prompts, tools, search, export,
                   tips, settings_router):
        api.include_router(module.router, dependencies=protected,
                           responses={401: {"description": "not logged in"}})
    app.include_router(api)
    return app


app = create_app()
