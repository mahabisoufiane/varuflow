"""Expo Push notification service (v25).

Thin wrapper over the Expo Push API:
  POST https://exp.host/--/api/v2/push/send
  Body: [{to, title, body, data, sound, priority, channelId}, ...]

Design notes
============
* Sending is **best-effort**. Failures must never bubble up into
  scheduler jobs or user-facing HTTP handlers — push is an additive
  signal, not a transactional guarantee.
* Tokens are sent in batches of 100 (Expo's documented cap).
* When Expo reports ``DeviceNotRegistered`` for a ticket, we delete
  the row so the token stops generating traffic.
* An env override ``EXPO_PUSH_URL`` is honoured so tests can point at
  an ``httpx.MockTransport`` without patching.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Iterable
from uuid import UUID

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notifications import DeviceToken
from app.models.organization import OrgRole, OrganizationMember

log = logging.getLogger(__name__)

_EXPO_PUSH_URL = os.environ.get(
    "EXPO_PUSH_URL", "https://exp.host/--/api/v2/push/send"
)
_MAX_BATCH = 100

# Map logical event types → OrganizationMember preference column.
# Consumers pass the event key so callers don't need to know schema.
_PREF_COLUMN = {
    "stockout": "push_stockout_enabled",
    "overdue": "push_overdue_enabled",
    "portal_order": "push_portal_order_enabled",
}


async def send_expo_push(
    tokens: list[str],
    *,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    """POST a push to Expo. Returns the aggregated response dict.

    If ``db`` is supplied and Expo reports tokens as
    ``DeviceNotRegistered``, those rows are deleted. Any other error
    is logged and swallowed — callers should never try/except around
    this function.
    """
    if not tokens:
        return {"sent": 0, "errors": []}

    results: list[dict[str, Any]] = []
    dead_tokens: list[str] = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Chunk into batches of 100 to respect Expo's API limit.
        for i in range(0, len(tokens), _MAX_BATCH):
            batch = tokens[i : i + _MAX_BATCH]
            payload = [
                {
                    "to": tok,
                    "title": title,
                    "body": body,
                    "data": data or {},
                    "sound": "default",
                    "priority": "high",
                    "channelId": "default",
                }
                for tok in batch
            ]
            try:
                resp = await client.post(
                    _EXPO_PUSH_URL,
                    json=payload,
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip, deflate",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                body_json = resp.json()
            except Exception as exc:  # noqa: BLE001 — best-effort
                log.warning("expo_push_failed: %s", exc)
                continue

            # Expo returns {"data": [{status, id} | {status, message, details}, ...]}
            tickets = body_json.get("data", []) if isinstance(body_json, dict) else []
            results.extend(tickets)
            for tok, ticket in zip(batch, tickets):
                if isinstance(ticket, dict) and ticket.get("status") == "error":
                    details = ticket.get("details") or {}
                    if details.get("error") == "DeviceNotRegistered":
                        dead_tokens.append(tok)

    if dead_tokens and db is not None:
        try:
            await db.execute(
                delete(DeviceToken).where(DeviceToken.token.in_(dead_tokens))
            )
            await db.commit()
        except Exception as exc:  # noqa: BLE001
            log.warning("expo_push_cleanup_failed: %s", exc)

    return {"sent": len(tokens) - len(dead_tokens), "errors": dead_tokens}


async def _fetch_tokens_for_event(
    db: AsyncSession,
    *,
    org_id: UUID,
    event: str,
    roles: Iterable[OrgRole] | None = None,
) -> list[str]:
    """Collect push tokens for org members who have opted-in to ``event``.

    ``roles`` restricts fan-out (e.g. only OWNERS receive overdue
    invoice pings). When ``None``, all members are candidates.
    """
    col_name = _PREF_COLUMN[event]
    pref_col = getattr(OrganizationMember, col_name)

    stmt = (
        select(DeviceToken.token)
        .join(
            OrganizationMember,
            (OrganizationMember.user_id == DeviceToken.user_id)
            & (OrganizationMember.org_id == DeviceToken.org_id),
        )
        .where(DeviceToken.org_id == org_id, pref_col.is_(True))
    )
    if roles is not None:
        stmt = stmt.where(OrganizationMember.role.in_(list(roles)))
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


async def send_to_org_members(
    db: AsyncSession,
    *,
    org_id: UUID,
    event: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
    roles: Iterable[OrgRole] | None = None,
) -> dict[str, Any]:
    """Fan out a push to all opted-in members of an org.

    ``event`` must be one of ``stockout``, ``overdue``, ``portal_order``.
    """
    tokens = await _fetch_tokens_for_event(
        db, org_id=org_id, event=event, roles=roles
    )
    if not tokens:
        return {"sent": 0, "errors": []}
    return await send_expo_push(
        tokens, title=title, body=body, data=data, db=db
    )
