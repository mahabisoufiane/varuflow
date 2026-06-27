import hmac

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

router = APIRouter(tags=["health"])


def _config_status() -> dict[str, bool]:
    """Which external integrations are configured. No network calls."""
    return {
        "supabase":    bool(settings.SUPABASE_URL and settings.SUPABASE_JWT_SECRET),
        "stripe":      bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET),
        "openai":      bool(settings.OPENAI_API_KEY),
        "resend":      bool(settings.RESEND_API_KEY),
        "fortnox":     bool(settings.FORTNOX_CLIENT_ID and settings.FORTNOX_REDIRECT_URI),
        "smtp":        bool(settings.SMTP_HOST),
        "sentry":      bool(settings.SENTRY_DSN),
    }


@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
    deep: bool = Query(default=False, description="Also probe scheduler + migrations_applied"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    """Liveness + dependency probe.

    Returns 200 when the database is reachable, 503 otherwise. The `config`
    block lists which optional integrations are wired — useful for smoke
    tests without exposing any secrets.

    `?deep=1` also checks that Alembic has run the expected head revision
    and that advisory-lock support is available. Gated behind X-Admin-Token
    (must match settings.ADMIN_API_KEY) to avoid leaking the migration
    version to unauthenticated callers.
    """
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    overall = "ok" if db_status == "ok" else "degraded"
    body: dict = {
        "status":   overall,
        "version":  "0.1.0",
        "database": db_status,
        "readonly": bool(settings.READONLY_MODE),
        "config":   _config_status(),
    }

    deep_authorized = (
        deep
        and bool(settings.ADMIN_API_KEY)
        and x_admin_token is not None
        and hmac.compare_digest(x_admin_token, settings.ADMIN_API_KEY)
    )
    if deep_authorized and db_status == "ok":
        deep_body: dict = {}
        try:
            rev = await db.execute(text("SELECT version_num FROM alembic_version"))
            deep_body["migration_head"] = rev.scalar_one_or_none() or "unknown"
        except Exception:
            deep_body["migration_head"] = "error"
        try:
            # Confirm advisory locks work (needed by scheduler)
            got = await db.execute(text("SELECT pg_try_advisory_lock(9999999)"))
            if bool(got.scalar()):
                await db.execute(text("SELECT pg_advisory_unlock(9999999)"))
            deep_body["advisory_locks"] = "ok"
        except Exception:
            deep_body["advisory_locks"] = "error"
        body["deep"] = deep_body

    return JSONResponse(
        status_code=200 if overall == "ok" else 503,
        content=body,
    )


@router.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "disconnected"},
        )


@router.get("/health/status-history")
async def status_history(db: AsyncSession = Depends(get_db)):
    """Public, unauthenticated endpoint that powers the /status page.

    Aggregates the last 90 days of recorded probes into per-service
    daily uptime buckets plus the most recent incidents. Cached with
    a short Cache-Control so the page can auto-refresh aggressively
    without thundering the DB.
    """
    from app.services.status_page import build_status_rollup

    payload = await build_status_rollup(db)
    return JSONResponse(
        content=payload,
        headers={"Cache-Control": "public, max-age=30"},
    )


# ── Admin: incident management (X-Admin-Token gated) ─────────────────────────

class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=4000)
    severity: str = Field("minor", pattern="^(minor|major|critical)$")


class IncidentResolve(BaseModel):
    resolved: bool = True


def _require_admin_token(x_admin_token: str | None) -> None:
    """Compare the supplied header with the configured admin token in
    constant time. Returns 404 (not 401) so the endpoint's existence is
    not advertised to unauthenticated callers."""
    from fastapi import HTTPException

    if (
        not settings.ADMIN_API_KEY
        or x_admin_token is None
        or not hmac.compare_digest(x_admin_token, settings.ADMIN_API_KEY)
    ):
        raise HTTPException(status_code=404)


@router.post("/health/incidents", status_code=201)
async def create_incident(
    body: IncidentCreate,
    db: AsyncSession = Depends(get_db),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    from app.features.portal.status import StatusIncident

    _require_admin_token(x_admin_token)
    inc = StatusIncident(
        title=body.title,
        description=body.description,
        severity=body.severity,
    )
    db.add(inc)
    await db.commit()
    await db.refresh(inc)
    return {"id": str(inc.id), "started_at": inc.started_at.isoformat()}


@router.patch("/health/incidents/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    import uuid as _uuid
    from datetime import datetime as _dt, timezone as _tz
    from fastapi import HTTPException
    from app.features.portal.status import StatusIncident

    _require_admin_token(x_admin_token)
    try:
        inc = await db.get(StatusIncident, _uuid.UUID(incident_id))
    except ValueError:
        raise HTTPException(status_code=404)
    if not inc:
        raise HTTPException(status_code=404)
    inc.resolved_at = _dt.now(_tz.utc)
    await db.commit()
    return {"id": str(inc.id), "resolved_at": inc.resolved_at.isoformat()}
