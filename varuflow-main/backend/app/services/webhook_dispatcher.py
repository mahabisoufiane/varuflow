"""Outbound webhook dispatcher (v30).

Producers (routers) call ``enqueue_event(db, org_id, event_type, payload)``
to fan an event out to every active endpoint subscribed to that event.
The dispatcher persists a ``WebhookDelivery`` row, then attempts an
immediate HTTP POST. On non-2xx the row is left with ``next_retry_at``
set per ``RETRY_DELAYS``; the scheduler sweep promotes it forward
through the schedule until it succeeds or runs out of attempts.

The endpoint secret is stored hashed; signing uses the *plaintext*
secret which the caller of ``register_endpoint`` keeps. To support
verification we sign with the SHA-256 hash of the secret as the HMAC
key — that way the server never needs the plaintext after registration
and customers verify by computing
``hmac_sha256(sha256(secret).hexdigest(), payload_bytes)``. This is
documented in the API response when an endpoint is created.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.integrations.webhook import (
    SUPPORTED_EVENTS,
    WebhookDelivery,
    WebhookEndpoint,
)

log = logging.getLogger(__name__)

# Exponential backoff between retries. Index = attempt_count *before*
# the next attempt is made. After the last entry the delivery is
# considered dead and ``next_retry_at`` is set to NULL.
RETRY_DELAYS: tuple[timedelta, ...] = (
    timedelta(minutes=5),
    timedelta(minutes=30),
    timedelta(hours=2),
    timedelta(hours=12),
    timedelta(hours=24),
)
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1  # initial + 5 retries

# Per-attempt HTTP timeout. Webhooks must not block API request
# threads, so this stays well under the FastAPI request budget.
DELIVERY_TIMEOUT_SECONDS = 5.0


def hash_secret(secret: str) -> str:
    """SHA-256 hex of the plaintext secret used as the HMAC key."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def generate_secret() -> str:
    """Cryptographically random plaintext secret. 32 bytes ≈ 256 bits
    of entropy — matches Stripe's `whsec_*` strength."""
    return secrets.token_urlsafe(32)


def sign_payload(secret_hash: str, body: bytes) -> str:
    """Return the HMAC-SHA256 hex digest used in ``X-Varuflow-Signature``."""
    return hmac.new(
        secret_hash.encode("ascii"), body, hashlib.sha256,
    ).hexdigest()


def _next_retry(attempt_count: int) -> datetime | None:
    """Return the next retry timestamp for a delivery that has just
    failed its ``attempt_count``-th attempt, or ``None`` if no more
    retries should be scheduled (delivery is now dead)."""
    if attempt_count >= MAX_ATTEMPTS:
        return None
    delay = RETRY_DELAYS[attempt_count - 1]
    return datetime.now(timezone.utc) + delay


async def _attempt_delivery(
    client: httpx.AsyncClient,
    *,
    endpoint: WebhookEndpoint,
    delivery: WebhookDelivery,
) -> None:
    """Single HTTP attempt. Updates ``delivery`` in-place; caller commits."""
    body = json.dumps(delivery.payload, separators=(",", ":"), sort_keys=True).encode()
    signature = sign_payload(endpoint.secret_hash, body)
    delivery.attempt_count += 1
    try:
        resp = await client.post(
            endpoint.url,
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Varuflow-Event": delivery.event_type,
                "X-Varuflow-Signature": signature,
                "X-Varuflow-Delivery-Id": str(delivery.id),
            },
            timeout=DELIVERY_TIMEOUT_SECONDS,
        )
    except (httpx.TimeoutException, httpx.HTTPError) as e:
        # Network failure — treat like a 5xx for backoff purposes.
        log.warning(
            "webhook transport error endpoint=%s err=%s",
            endpoint.id, str(e)[:200],
        )
        delivery.status_code = None
        delivery.next_retry_at = _next_retry(delivery.attempt_count)
        delivery.delivered_at = None
        return

    delivery.status_code = resp.status_code
    if 200 <= resp.status_code < 300:
        delivery.delivered_at = datetime.now(timezone.utc)
        delivery.next_retry_at = None
    else:
        # 4xx and 5xx both retry — a transient 429 or temporary 4xx from
        # an LB warming up shouldn't lose the event. Customer code that
        # truly rejects an event should return 410 GONE; we still retry
        # because the backoff caps attempts anyway.
        delivery.delivered_at = None
        delivery.next_retry_at = _next_retry(delivery.attempt_count)


async def enqueue_event(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    event_type: str,
    payload: dict,
) -> list[uuid.UUID]:
    """Fan ``event_type`` out to every active endpoint subscribed to it.

    Returns the list of created delivery IDs (mostly useful for tests).
    Always commits its own transaction so the caller's main work is
    independent of webhook fan-out — a failed delivery never rolls back
    the underlying invoice/order/etc.
    """
    if event_type not in SUPPORTED_EVENTS:
        # Defensive — programmer error caught early in dev.
        log.error("unknown webhook event_type=%s", event_type)
        return []

    endpoints = (await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.org_id == org_id,
            WebhookEndpoint.active.is_(True),
            WebhookEndpoint.events.contains([event_type]),
        )
    )).scalars().all()
    if not endpoints:
        return []

    deliveries: list[WebhookDelivery] = []
    for ep in endpoints:
        d = WebhookDelivery(
            endpoint_id=ep.id,
            event_type=event_type,
            payload=payload,
        )
        db.add(d)
        deliveries.append(d)
    await db.flush()

    async with httpx.AsyncClient() as client:
        for ep, d in zip(endpoints, deliveries):
            await _attempt_delivery(client, endpoint=ep, delivery=d)

    await db.commit()
    return [d.id for d in deliveries]


async def retry_pending(db: AsyncSession, *, now: datetime | None = None) -> int:
    """Scheduler entry point: process every delivery whose
    ``next_retry_at <= now`` and which has not yet been delivered.
    Returns the number of attempts made."""
    now = now or datetime.now(timezone.utc)
    rows = (await db.execute(
        select(WebhookDelivery, WebhookEndpoint)
        .join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id)
        .where(
            WebhookDelivery.delivered_at.is_(None),
            WebhookDelivery.next_retry_at.is_not(None),
            WebhookDelivery.next_retry_at <= now,
            WebhookEndpoint.active.is_(True),
        )
        .limit(200)  # bounded batch — avoids one tenant starving others
    )).all()
    if not rows:
        return 0

    async with httpx.AsyncClient() as client:
        for delivery, endpoint in rows:
            await _attempt_delivery(client, endpoint=endpoint, delivery=delivery)

    await db.commit()
    return len(rows)
