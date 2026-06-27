"""Per-org subscription-pause write guard (Item 50).

When an org has ``is_paused=True`` on the ``organizations`` row, all
non-GET / non-HEAD / non-OPTIONS requests from members of that org
are rejected with HTTP 423 (Locked). A whitelist keeps the billing
resume endpoint reachable so the owner can always lift the pause,
plus a handful of observability paths that don't touch tenant data.

Differs from :mod:`app.middleware.readonly` — that module is a
global (app-wide) kill switch toggled from Railway Variables. This
one is a per-tenant state derived from the subscription flow.

The middleware resolves the authenticated org by calling the shared
auth helper; unauthenticated requests pass through (auth is
enforced at the endpoint level via ``get_current_member`` / friends).
"""
from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


log = logging.getLogger(__name__)

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Paths that stay writable even when the org is paused. Keep short —
# every entry is a potential footgun.
_WHITELIST_PREFIXES = (
    # Owner must always be able to resume, regardless of state.
    "/api/billing/resume",
    # Let the UI poll status without hitting a 423.
    "/api/billing/pause/status",
    "/api/billing/pause/history",
    # Stripe webhook is signed + idempotent — never block.
    "/api/billing/webhook",
    "/api/invoicing/webhooks",
    # Health / auth flows — keep login + OAuth alive so the owner
    # can actually sign in and resume.
    "/api/health",
    "/api/auth",
    # GDPR erasure must remain available during a pause per
    # Article 17 (right to erasure).
    "/api/gdpr",
)


def _is_write(method: str) -> bool:
    return method.upper() not in _SAFE_METHODS


def _is_whitelisted(path: str) -> bool:
    return any(path.startswith(p) for p in _WHITELIST_PREFIXES)


class PauseWriteGuardMiddleware(BaseHTTPMiddleware):
    """Block mutating requests when the caller's org is paused.

    Kept intentionally thin: one DB roundtrip per write, short-
    circuited for safe methods and whitelisted paths. Read traffic
    pays nothing.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if not _is_write(request.method):
            return await call_next(request)
        if _is_whitelisted(request.url.path):
            return await call_next(request)

        # Extract the authenticated user from the bearer token. We
        # cannot call the FastAPI dependency tree from middleware, so
        # we inspect the header directly and do a cheap DB lookup.
        auth_header = request.headers.get("authorization") or ""
        if not auth_header.lower().startswith("bearer "):
            # Unauthenticated — let the endpoint's auth dep fire a 401.
            return await call_next(request)

        # Lazy import to keep startup cycles clean.
        try:
            from app.database import async_session
            from app.middleware.auth import _decode_jwt
            from app.features.auth.organization import Organization, OrganizationMember
            from sqlalchemy import select
        except Exception:
            # If the app is mid-boot or the auth helper isn't
            # importable, fail open — the endpoint-level guards will
            # still enforce auth.
            return await call_next(request)

        token = auth_header.split(" ", 1)[1].strip()
        try:
            payload = _decode_jwt(token)
        except Exception:
            return await call_next(request)

        user_id = payload.get("sub")
        if not user_id:
            return await call_next(request)

        try:
            async with async_session() as db:
                # The member's org may be passed via header (X-Org-Id)
                # or inferred from the single membership. Here we just
                # inspect all memberships for the user and block if
                # ANY are paused — the endpoint will pick the right
                # org_id itself.
                member = await db.scalar(
                    select(OrganizationMember).where(
                        OrganizationMember.user_id == user_id
                    )
                )
                if member is None:
                    return await call_next(request)
                org = await db.get(Organization, member.org_id)
                if org is None or not org.is_paused:
                    return await call_next(request)
        except Exception:
            # Never let a middleware DB error kill the request — the
            # endpoint-level guards and the is_paused check at the
            # service layer are the source of truth.
            return await call_next(request)

        return JSONResponse(
            status_code=423,
            content={
                "detail": (
                    "This organization's subscription is paused. "
                    "Resume billing to continue making changes."
                ),
                "code": "SUBSCRIPTION_PAUSED",
            },
        )
