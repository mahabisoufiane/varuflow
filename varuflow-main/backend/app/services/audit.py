"""Append-only audit log helper.

Usage:
    from app.services.audit import log_action
    await log_action(
        db,
        action="gdpr.org_anonymise",
        org_id=org_id,
        actor_user_id=user_id,
        target_type="organization",
        target_id=str(org_id),
        request=request,
        extra={"reason": "owner_request"},
    )

Never raises — audit failures must not block the underlying business
action. Errors are logged and swallowed.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.features.compliance.audit_models import AuditLogEntry

log = logging.getLogger(__name__)


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    # Only trust X-Forwarded-For when the app is actually behind a known
    # proxy (Railway, Render, Cloudflare). If TRUST_PROXY is false the
    # header can be spoofed by any attacker — use the direct peer instead,
    # matching the logic in rate_limit.py so audit attribution stays
    # consistent with rate-limit attribution.
    if settings.TRUST_PROXY:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
    client = request.client
    return client.host if client else None


# Public alias so other modules (middleware/auth.py for the IP allowlist
# check introduced in Item 25) can reuse the exact same TRUST_PROXY-aware
# attribution logic without importing a private name. Keeping them as a
# single symbol means a future change to proxy handling only has one
# call site to update.
get_client_ip = _client_ip


async def log_action(
    db: AsyncSession,
    *,
    action: str,
    org_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    request: Request | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    # Item 30 — enrich ``extra`` with correlation metadata BEFORE the DB
    # write so the audit row and the stdout security event share an
    # identical payload. ``enrich_extra`` lives in ``observability`` (no
    # ORM imports) so the pure enrichment logic can be unit-tested
    # without pulling the whole model graph into the test import chain.
    from app.services.observability import enrich_extra, log_security_event

    ip = _client_ip(request)
    enriched = enrich_extra(extra, request)

    try:
        entry = AuditLogEntry(
            org_id=org_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip_address=ip,
            extra=enriched,
        )
        db.add(entry)
        await db.flush()
    except Exception as e:  # noqa: BLE001 — audit must never break caller
        log.error("audit_log_failed action=%s err=%s", action, str(e))

    # Item 30 — mirror the audit write as a structured security event on
    # stdout. ``log_security_event`` swallows its own exceptions, so a
    # broken logger never breaks an audit write and vice versa. Kept
    # OUTSIDE the try/except above so the log still fires even if the DB
    # flush failed (the operator then sees two signals: a failed audit
    # row and a stdout line that tells them the action still happened).
    try:
        log_security_event(
            action,
            actor_user_id=str(actor_user_id) if actor_user_id else None,
            org_id=str(org_id) if org_id else None,
            target_type=target_type,
            target_id=target_id,
            ip_address=ip,
            extra=enriched or None,
        )
    except Exception as e:  # noqa: BLE001 — observability must never break caller
        log.error("security_event_failed action=%s err=%s", action, str(e))


def _enrich_extra(*args, **kwargs):
    """Backwards-compatible alias forwarding to observability.enrich_extra.

    Kept so any internal import path that was briefly pointed at the
    audit-module helper during Item 30's refactor continues to work
    during deploy windows. Intentionally undocumented — new callers
    should import ``app.services.observability.enrich_extra`` directly.
    """
    from app.services.observability import enrich_extra
    return enrich_extra(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════════
# Query helpers (Item 47 — inventory audit trail)
# ═══════════════════════════════════════════════════════════════════


async def fetch_audit_for_targets(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    target_type: str,
    target_ids: list[str],
) -> dict[str, "AuditLogEntry"]:
    """Return a ``target_id → AuditLogEntry`` map for the given targets.

    The inventory-audit router uses this to attach actor + IP metadata
    to each ``StockMovement`` row in a single query. Capped at the
    caller-supplied id list so the query is always bounded.
    """
    from sqlalchemy import select as _select

    if not target_ids:
        return {}
    rows = (
        await db.execute(
            _select(AuditLogEntry).where(
                AuditLogEntry.org_id == org_id,
                AuditLogEntry.target_type == target_type,
                AuditLogEntry.target_id.in_(target_ids),
            )
        )
    ).scalars().all()
    return {r.target_id: r for r in rows if r.target_id}
