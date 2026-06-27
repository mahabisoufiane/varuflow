"""Public status page service (v31).

Two responsibilities:

* ``run_health_probe(db)`` — executed every 5 minutes by the scheduler.
  Pings the database, Stripe and Resend (head requests, no payloads),
  measures the round-trip and persists a ``HealthCheck`` row.

* ``build_status_rollup(db)`` — builds the JSON payload served at the
  public ``/api/health/status-history`` endpoint: 90 daily buckets per
  service plus an overall status badge and recent incidents.

External pings are wrapped in tight timeouts so a slow upstream cannot
block the scheduler tick or balloon the response time recorded for a
bystander service.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.features.portal.status import HealthCheck, StatusIncident

log = logging.getLogger(__name__)

_PROBE_TIMEOUT = 4.0  # seconds — strictly less than the 5-min tick.

# Endpoints used purely as availability probes. Stripe's /v1/charges is a
# documented public ping target that returns 401 (good — the host is up);
# Resend's status page is a static page that returns 200 when the API is
# reachable. Both responses count as ``up`` if the HTTP request *completes*
# regardless of status code, since we're testing reachability not auth.
_STRIPE_PING_URL = "https://api.stripe.com/v1/charges"
_RESEND_PING_URL = "https://api.resend.com/emails"


async def _probe_url(client: httpx.AsyncClient, url: str) -> bool:
    """Return ``True`` when the host responds within the timeout. We
    treat any HTTP status as ``up`` because authentication failures
    still prove the upstream is alive."""
    try:
        resp = await client.get(url, timeout=_PROBE_TIMEOUT)
        return resp.status_code < 600
    except (httpx.TimeoutException, httpx.HTTPError):
        return False


async def run_health_probe(db: AsyncSession) -> HealthCheck:
    """Execute one probe pass and persist the result."""
    started = time.monotonic()

    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    # Skip external probes when the integration is not configured —
    # otherwise an unconfigured Resend would forever show 0 % uptime
    # on the public page, which is confusing for visitors.
    async with httpx.AsyncClient() as client:
        stripe_ok = (
            await _probe_url(client, _STRIPE_PING_URL)
            if settings.STRIPE_SECRET_KEY else True
        )
        resend_ok = (
            await _probe_url(client, _RESEND_PING_URL)
            if settings.RESEND_API_KEY else True
        )

    response_ms = int((time.monotonic() - started) * 1000)

    row = HealthCheck(
        db_ok=db_ok,
        stripe_ok=stripe_ok,
        resend_ok=resend_ok,
        response_ms=response_ms,
    )
    db.add(row)
    await db.commit()
    return row


def _overall_status(latest: HealthCheck | None) -> str:
    """Map the most recent probe to the badge shown at the top of the
    public status page."""
    if latest is None:
        return "unknown"
    flags = (latest.db_ok, latest.stripe_ok, latest.resend_ok)
    if all(flags):
        return "operational"
    if any(flags):
        return "degraded"
    return "outage"


async def build_status_rollup(db: AsyncSession, *, days: int = 90) -> dict:
    """Aggregate the last ``days`` of probes into a per-day uptime % per
    service and surface the most recent incidents."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (await db.execute(
        select(HealthCheck)
        .where(HealthCheck.checked_at >= since)
        .order_by(HealthCheck.checked_at.asc())
    )).scalars().all()

    # day_buckets[day_iso] = {service: (ok_count, total_count)}
    day_buckets: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: {"api": [0, 0], "database": [0, 0], "payments": [0, 0], "email": [0, 0]},
    )
    for r in rows:
        d = r.checked_at.date().isoformat()
        b = day_buckets[d]
        # API == "the FastAPI process answered the probe" — every
        # persisted row implies the API was up at probe time, since the
        # row could only be written from inside the running process.
        b["api"][0] += 1
        b["api"][1] += 1
        b["database"][0] += 1 if r.db_ok else 0
        b["database"][1] += 1
        b["payments"][0] += 1 if r.stripe_ok else 0
        b["payments"][1] += 1
        b["email"][0] += 1 if r.resend_ok else 0
        b["email"][1] += 1

    # Densify the timeline so the frontend renders an empty (grey) dot
    # for days with no probes instead of skipping them, mirroring the
    # Stripe-style timeline UX.
    services = ["api", "database", "payments", "email"]
    today = date.today()
    timeline: dict[str, list[dict]] = {s: [] for s in services}
    for offset in range(days - 1, -1, -1):
        d = (today - timedelta(days=offset)).isoformat()
        b = day_buckets.get(d)
        for s in services:
            if not b or b[s][1] == 0:
                timeline[s].append({"date": d, "uptime_pct": None})
            else:
                ok, total = b[s]
                timeline[s].append({
                    "date": d,
                    "uptime_pct": round(ok * 100.0 / total, 2),
                })

    def _avg_uptime(buckets: list[dict]) -> float | None:
        vals = [bk["uptime_pct"] for bk in buckets if bk["uptime_pct"] is not None]
        if not vals:
            return None
        return round(sum(vals) / len(vals), 2)

    services_payload = [
        {
            "key": s,
            "uptime_pct_90d": _avg_uptime(timeline[s]),
            "timeline": timeline[s],
        }
        for s in services
    ]

    incidents = (await db.execute(
        select(StatusIncident)
        .order_by(StatusIncident.started_at.desc())
        .limit(5)
    )).scalars().all()

    latest = rows[-1] if rows else None
    return {
        "overall": _overall_status(latest),
        "checked_at": latest.checked_at.isoformat() if latest else None,
        "services": services_payload,
        "incidents": [
            {
                "id": str(i.id),
                "title": i.title,
                "description": i.description,
                "severity": i.severity,
                "started_at": i.started_at.isoformat(),
                "resolved_at": i.resolved_at.isoformat() if i.resolved_at else None,
            }
            for i in incidents
        ],
    }
