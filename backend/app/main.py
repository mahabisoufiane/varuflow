import logging
import logging.config
from contextlib import asynccontextmanager

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

from app.config import settings
from app.database import engine
from app.routers import ai_engine, analytics, auth, billing, health, integrations, inventory, invoicing, portal, pos, recurring, team, waitlist
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


@asynccontextmanager
async def lifespan(app: FastAPI):
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


log = logging.getLogger(__name__)


@app.middleware("http")
async def _log_requests(request: Request, call_next):
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
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

app.include_router(health.router)
app.include_router(auth.router)
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
