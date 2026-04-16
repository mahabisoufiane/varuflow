import asyncio
import logging
import logging.config
import os
from contextlib import asynccontextmanager

import alembic.command
import alembic.config
import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

# Structured JSON-style logging
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)r}',
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
})

from app.config import settings, validate_production_config
from app.database import engine
from app.middleware.country import CountryMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.routers import ai_engine, analytics, auth, billing, countries, health, integrations, inventory, invoicing, local_auth, portal, pos, recurring, team, waitlist
from app.services.scheduler import create_scheduler

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENV,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.2,
        send_default_pii=False,
    )

log = logging.getLogger(__name__)


def _run_migrations() -> None:
    """Run Alembic migrations synchronously (called from a thread executor)."""
    ini_path = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    cfg = alembic.config.Config(os.path.abspath(ini_path))
    alembic.command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── 1. Security config validation (crashes on bad production config) ──────
    validate_production_config()

    # ── 2. Database migrations ────────────────────────────────────────────────
    # Executed in a thread executor because Alembic's online migration path
    # calls asyncio.run() internally, which cannot be nested inside the
    # already-running event loop.
    loop = asyncio.get_running_loop()
    try:
        log.info("Running Alembic migrations…")
        await loop.run_in_executor(None, _run_migrations)
        log.info("Alembic migrations complete.")
    except Exception:
        log.exception("Alembic migration failed — continuing startup anyway.")

    scheduler = create_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(
    title="Varuflow API",
    version="0.1.0",
    description="Inventory and invoicing API for Swedish wholesalers",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# IP-based rate limit: 100 req/min — must be added BEFORE CORSMiddleware
# so CORS headers are still injected on 429 responses.
app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With", "X-Country-Code"],
    expose_headers=["X-Country-Code"],
    max_age=3600,
)

# Country resolution — must run AFTER CORS (inner layer) so it sees real
# client headers but does not interfere with preflight short-circuiting.
app.add_middleware(CountryMiddleware)


@app.middleware("http")
async def _add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.middleware("http")
async def _log_requests(request: Request, call_next):
    # Do NOT catch exceptions here — this middleware is outermost (last decorator =
    # outermost in Starlette's LIFO stack). Catching and re-raising a JSONResponse
    # here would bypass CORSMiddleware (which is inner), stripping CORS headers from
    # error responses and causing browser CORS errors. Let exceptions propagate so
    # @app.exception_handler(Exception) fires inside ExceptionMiddleware (inside CORS).
    response = await call_next(request)
    log.info(
        '"method":"%s","path":"%s","status":%d',
        request.method, request.url.path, response.status_code,
    )
    return response


# Catch all unhandled exceptions so they stay inside the middleware stack
# (not handled by ServerErrorMiddleware which is outside CORSMiddleware).
# Without this, 500s reach the browser without Access-Control-Allow-Origin.
@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the full traceback so Railway logs surface root causes.
    # The client receives only a generic message — no internal details ever leak.
    log.exception(
        "Unhandled exception | method=%s path=%s",
        request.method, request.url.path,
    )

    origin = request.headers.get("origin")
    allowed_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    headers = {}
    if origin in allowed_origins:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Vary"] = "Origin"

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers=headers,
    )

app.include_router(health.router, prefix="/api")
app.include_router(auth.router)
app.include_router(local_auth.router)
app.include_router(inventory.router)
app.include_router(invoicing.router)
app.include_router(waitlist.router)
app.include_router(analytics.router)
app.include_router(team.router)
app.include_router(recurring.router)
app.include_router(pos.router)
app.include_router(billing.router)
app.include_router(integrations.router)
app.include_router(portal.router)
app.include_router(ai_engine.router)
app.include_router(countries.router)
