import asyncio
import json
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


class _RequestContextFilter(logging.Filter):
    """Stamp every log record with the current request_id from the ContextVar.

    Uses a lazy import so this class can be defined before app.* modules are
    imported (logging is configured at module load time, before the import
    block below). Returns None outside an HTTP context (scheduler jobs, tests)
    which the formatter omits from the JSON output.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from app.middleware.request_id import request_id_ctx
            record.request_id = request_id_ctx.get()
        except Exception:
            record.request_id = None
        return True


class _JsonFormatter(logging.Formatter):
    """True structured-JSON formatter.

    Replaces the previous format-string approach which used %(message)r
    (Python repr) and produced invalid JSON whenever a log message contained
    double-quotes, newlines, or non-ASCII characters.

    Emits ``request_id`` when populated by ``_RequestContextFilter`` so every
    log line from the same HTTP request shares the same correlation ID without
    callers having to pass it explicitly.
    """

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        doc: dict = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.message,
        }
        rid = getattr(record, "request_id", None)
        if rid:
            doc["request_id"] = rid
        if record.exc_info:
            doc["exc"] = self.formatException(record.exc_info)
        return json.dumps(doc, ensure_ascii=False)


logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": _JsonFormatter,
        }
    },
    "filters": {
        "request_context": {
            "()": _RequestContextFilter,
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["request_context"],
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
})

from app.config import settings, validate_production_config, is_production
from app.database import engine
from app.middleware.country import CountryMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.readonly import ReadOnlyMiddleware
from app.middleware.pause_guard import PauseWriteGuardMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.features.invoicing.router import router as invoicing_router
from app.features.auth.router import router as auth_router
from app.features.pos.router import router as pos_router
from app.features.hr.router import router as hr_router
from app.features.expenses.router import router as expenses_router
from app.features.inventory.router import router as inventory_router
from app.features.customers.router import router as customers_router
from app.features.purchases.router import router as purchases_router
from app.features.analytics.router import router as analytics_router
from app.features.bookings.router import router as bookings_router
from app.features.loyalty.router import router as loyalty_router
from app.features.projects.router import router as projects_router
from app.features.storefront.router import router as storefront_router
from app.features.marketing.router import router as marketing_router
from app.features.compliance.router import router as compliance_router
from app.features.integrations.router import router as integrations_router
from app.features.notifications.router import router as notifications_router
from app.features.portal.router import router as portal_router
from app.features.admin.router import router as admin_router
from app.features.ai.router import router as ai_router
from app.features.billing.router import router as billing_router
from app.features.corporate.router import router as corporate_router
from app.features.mobile.router import router as mobile_router
from app.features.settings.router import router as settings_router

# Public sub-routers that must be mounted separately (no-auth endpoints)
from app.features.bookings.bookings import public_checkin_router as _bookings_public_checkin_router
from app.features.marketing.reviews import public_router as _reviews_public_router

# Infrastructure routers (intentionally NOT in feature packages)
from app.routers import health, uploads, scheduler as scheduler_router
from app.services.scheduler import create_scheduler

# slowapi's `get_remote_address` reads `request.client.host`, which on
# Railway (and any reverse-proxy deployment) is the PROXY's IP — so the
# 200/min default would be shared across every real client behind the
# proxy. A single aggressive user hitting 200/min would then lock out
# everyone else. Use a key_func that honours TRUST_PROXY via
# X-Forwarded-For, matching what the custom RateLimitMiddleware does.
def _slowapi_key(request: Request) -> str:
    if settings.TRUST_PROXY:
        fwd = request.headers.get("X-Forwarded-For")
        if fwd:
            return fwd.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_slowapi_key, default_limits=["200/minute"])

if settings.SENTRY_DSN:
    # Scrub PII and secrets from every event before it leaves the process.
    # Matches header/cookie/query-string keys that commonly carry sensitive
    # values. Body payloads are never attached by default when
    # send_default_pii=False, but we still redact request data that the
    # FastAPI integration may capture from exceptions raised mid-request.
    _SENSITIVE_KEYS = {
        "authorization", "cookie", "set-cookie", "x-admin-key",
        "x-confirm-delete", "stripe-signature", "password", "token",
        "access_token", "refresh_token", "totp_code", "api_key",
    }

    def _scrub(event, _hint):
        try:
            for section in ("request",):
                data = event.get(section) or {}
                for key in ("headers", "cookies", "query_string", "data"):
                    bucket = data.get(key)
                    if isinstance(bucket, dict):
                        for k in list(bucket.keys()):
                            if k.lower() in _SENSITIVE_KEYS:
                                bucket[k] = "[filtered]"
            # Strip user email/IP if somehow attached despite send_default_pii=False
            user = event.get("user") or {}
            for k in ("email", "ip_address", "username"):
                if k in user:
                    user[k] = "[filtered]"
        except Exception:
            pass
        return event

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENV,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.2,
        send_default_pii=False,
        before_send=_scrub,
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
    log.info("Running Alembic migrations…")
    await loop.run_in_executor(None, _run_migrations)
    log.info("Alembic migrations complete.")

    scheduler = create_scheduler()
    scheduler.start()
    yield
    # Drain in-flight jobs before the process exits so Railway's 30 s
    # SIGTERM→SIGKILL window is used for a clean shutdown.  shutdown() is
    # synchronous, so run it in the thread-pool executor to avoid blocking
    # the event loop while waiting for pending asyncio tasks to finish.
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: scheduler.shutdown(wait=True))
    await engine.dispose()


# In production, disable the interactive /docs and /redoc UIs to reduce
# attack surface (they enumerate every endpoint + schema for anyone who
# finds the URL). The raw OpenAPI JSON stays available at /openapi.json
# for internal tooling and the frontend API-types codegen.
_prod = is_production()
_docs_url    = None   if _prod else "/docs"
_redoc_url   = None   if _prod else "/redoc"
_openapi_url = None   if _prod else "/openapi.json"

app = FastAPI(
    title="Varuflow API",
    version="0.1.0",
    description="Inventory and invoicing API for Swedish wholesalers",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Read-only maintenance mode — added BEFORE CORS so CORS still wraps the
# 503 responses it produces (preventing browser CORS errors during a
# restore). Toggle with READONLY_MODE=true in Railway Variables.
app.add_middleware(ReadOnlyMiddleware)

# Per-org subscription-pause write guard (Item 50). Blocks mutating
# requests with 423 when the caller's org has ``is_paused=True``.
# Kept after ReadOnlyMiddleware so a global freeze still trumps it.
app.add_middleware(PauseWriteGuardMiddleware)

# IP-based rate limit: 100 req/min global, tighter per-path buckets
# (login/signup/MFA/billing/AI — see RateLimitMiddleware._PATH_LIMITS).
# Must be added BEFORE CORSMiddleware so CORS headers are still injected
# on 429 responses. Set RATE_LIMIT_DISABLED=true to bypass in tests.
if settings.RATE_LIMIT_DISABLED and _prod:
    # Loud startup warning — a production deploy with rate limiting
    # disabled is almost certainly a config accident.
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "RATE_LIMIT_DISABLED=true in production — middleware is a no-op. "
        "Verify this is intentional."
    )
app.add_middleware(RateLimitMiddleware)

# Request-ID correlation — registered before CORS (inner layer in Starlette's
# LIFO stack) so every downstream log line and Sentry event carries the same
# id and the header is echoed on the response.
app.add_middleware(RequestIdMiddleware)

# Country resolution — registered before CORS (inner layer) so it sees real
# client headers but does not interfere with preflight short-circuiting.
app.add_middleware(CountryMiddleware)

# CORSMiddleware MUST be the outermost add_middleware layer. In Starlette's
# LIFO execution model the last-registered middleware runs first on every
# request. CountryMiddleware and RequestIdMiddleware are registered above
# (inner) so any error they produce is still wrapped by CORS headers and
# never reaches the browser without Access-Control-Allow-Origin.
_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
if _prod:
    # Strip any localhost/dev origins that may have crept into the Railway env var.
    _filtered = [o for o in _cors_origins if "localhost" not in o and "127.0.0.1" not in o]
    if _filtered:
        _cors_origins = _filtered
    else:
        # CORS_ORIGINS on Railway only had localhost values — keep the full list so
        # the app stays reachable, but log loudly so an operator can correct it.
        log.warning(
            "CORS_ORIGINS contains only localhost origins in production mode. "
            "Set CORS_ORIGINS=https://varuflow.vercel.app on Railway."
        )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With", "X-Country-Code", "X-Request-ID", "X-Confirm-Delete", "X-Admin-Key"],
    expose_headers=["X-Country-Code", "X-Request-ID"],
    max_age=3600,
)


@app.middleware("http")
async def _add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), interest-cohort=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-site"
    # API responses are JSON only; a tight CSP blocks any script/style loads in
    # case an error path accidentally returns HTML. frame-ancestors 'none'
    # prevents clickjacking (redundant with X-Frame-Options but more modern).
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    )
    # HSTS — emit when in production or when Railway signals HTTPS via X-Forwarded-Proto.
    # The dual check handles ENV=prod (short form) and direct Railway TLS termination.
    if _prod or request.headers.get("x-forwarded-proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    return response


@app.middleware("http")
async def _log_requests(request: Request, call_next):
    # Do NOT catch exceptions here — this middleware is outermost (last decorator =
    # outermost in Starlette's LIFO stack). Catching and re-raising a JSONResponse
    # here would bypass CORSMiddleware (which is inner), stripping CORS headers from
    # error responses and causing browser CORS errors. Let exceptions propagate so
    # @app.exception_handler(Exception) fires inside ExceptionMiddleware (inside CORS).
    response = await call_next(request)
    # Prefer request.state (set by RequestIdMiddleware); fall back to the
    # Item 30 ContextVar so the log line stays correlated even if a
    # future middleware reshuffle removes the state attribute before this
    # handler runs. Both pointers are populated identically today; using
    # both as a defensive OR keeps this line from silently regressing.
    from app.middleware.request_id import get_current_request_id
    request_id = getattr(request.state, "request_id", None) or get_current_request_id() or "-"
    log.info(
        '"method":"%s","path":"%s","status":%d,"request_id":"%s"',
        request.method, request.url.path, response.status_code, request_id,
    )
    return response


# Catch all unhandled exceptions so they stay inside the middleware stack
# (not handled by ServerErrorMiddleware which is outside CORSMiddleware).
# Routers across the app catch exceptions and re-raise a bare
# HTTPException(500) — which FastAPI serves WITHOUT logging, so root causes
# were invisible (the 2026-07-06 audit found ~15 endpoints silently broken this
# way). This handler logs every 5xx HTTPException including the swallowed
# original exception (available as __context__ from the except block), then
# delegates to the default handler. One choke point instead of touching every
# router's except block.
from fastapi.exception_handlers import http_exception_handler as _default_http_handler  # noqa: E402
from starlette.exceptions import HTTPException as _StarletteHTTPException  # noqa: E402


@app.exception_handler(_StarletteHTTPException)
async def _logged_http_exception_handler(request: Request, exc: _StarletteHTTPException):
    if exc.status_code >= 500:
        origin = exc.__cause__ or exc.__context__
        log.error(
            "HTTP %s | method=%s path=%s request_id=%s swallowed=%r",
            exc.status_code,
            request.method,
            request.url.path,
            getattr(request.state, "request_id", "-"),
            origin,
            exc_info=origin if origin is not None else None,
        )
    return await _default_http_handler(request, exc)


# Without this, 500s reach the browser without Access-Control-Allow-Origin.
@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the full traceback so Railway logs surface root causes.
    # The client receives only a generic message — no internal details ever leak.
    request_id = getattr(request.state, "request_id", "-")
    log.exception(
        "Unhandled exception | method=%s path=%s request_id=%s",
        request.method, request.url.path, request_id,
    )

    origin = request.headers.get("origin")
    allowed_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    headers = {"X-Request-ID": request_id}
    if origin in allowed_origins:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Vary"] = "Origin"

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
        headers=headers,
    )

app.include_router(health.router, prefix="/api")
# Feature packages (each includes all their sub-routers)
app.include_router(auth_router)
app.include_router(invoicing_router)
# Invoicing sub-modules that declare absolute /api/... prefixes (quotes,
# recurring, credit notes, disputes, …) — mounted unprefixed at app level so
# their paths resolve where the frontend and public tokens expect. See the
# explanation in features/invoicing/router.py.
from app.features.invoicing.router import standalone_router as _invoicing_standalone  # noqa: E402
app.include_router(_invoicing_standalone)
app.include_router(pos_router)
app.include_router(hr_router)
app.include_router(expenses_router)
app.include_router(inventory_router)
app.include_router(customers_router)
app.include_router(purchases_router)
app.include_router(analytics_router)
app.include_router(bookings_router)
app.include_router(_bookings_public_checkin_router)
app.include_router(loyalty_router)
app.include_router(projects_router)
app.include_router(storefront_router)
app.include_router(marketing_router)
app.include_router(_reviews_public_router)
app.include_router(compliance_router)
app.include_router(integrations_router)
app.include_router(notifications_router)
app.include_router(portal_router)

# New feature packages
app.include_router(admin_router)
app.include_router(ai_router)
app.include_router(billing_router)
app.include_router(corporate_router)
app.include_router(mobile_router)
app.include_router(settings_router)

# Infrastructure (health, uploads, scheduler stay outside features/)
app.include_router(uploads.router)
app.include_router(scheduler_router.router)