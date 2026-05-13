"""Read-only mode middleware.

When `settings.READONLY_MODE` is True, all non-GET / non-HEAD / non-OPTIONS
requests are rejected with 503. Intended for use during:

  • Database restores from a snapshot
  • Emergency maintenance windows
  • Stripe / Supabase incidents where we need to freeze writes

Whitelisted paths keep working so operators can still hit /api/health and
the Stripe webhook (which is server-to-server and signature-verified).

Toggle via Railway Variables:
    READONLY_MODE=true
then redeploy — no code change required. Flip back to False when done.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Paths that stay writable even in read-only mode.
# Keep this list short — each entry is a potential footgun.
_WHITELIST_PREFIXES = (
    "/api/health",
    # Stripe webhooks are idempotent + signature-verified; we want to keep
    # receiving events in read-only mode so Stripe doesn't exhaust its
    # retry budget and mark our endpoint as broken.
    # NOTE: the invoice-payments webhook is mounted at
    # /api/invoicing/webhooks/stripe (plural "webhooks"); matching on
    # "webhooks" (instead of "webhook") catches both billing and invoicing.
    "/api/billing/webhook",
    "/api/invoicing/webhooks",
)


class ReadOnlyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.READONLY_MODE:
            return await call_next(request)

        if request.method in _SAFE_METHODS:
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(p) for p in _WHITELIST_PREFIXES):
            return await call_next(request)

        return JSONResponse(
            status_code=503,
            content={
                "detail": "Varuflow is temporarily in read-only mode for maintenance. "
                          "Writes will resume shortly.",
                "code": "READONLY_MODE",
            },
            headers={"Retry-After": "300"},
        )
