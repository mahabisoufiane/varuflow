"""Review-request dispatch helper (Item 49).

Thin DB-aware shim around :mod:`review_service`. Lives separately so
the pure helpers stay stdlib-only and testable without a DB.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.marketing.reviews_models import ReviewRequest
from app.services import review_service as svc


async def maybe_create_review_request(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    customer_id: uuid.UUID,
    source_type: str,
    source_id: uuid.UUID,
) -> ReviewRequest | None:
    """Create a ``ReviewRequest`` for this source unless one already
    exists. Idempotent — calling twice for the same booking/invoice
    never creates a duplicate prompt.

    The plaintext token is emailed via the email queue; the DB stores
    only the SHA-256 hash. Returns the new row (with ``_raw_token``
    attached so the caller can hand the plaintext to the mailer)
    or ``None`` if a request already exists.
    """
    # Duplicate guard — one prompt per source.
    existing = (
        await db.execute(
            select(ReviewRequest).where(
                ReviewRequest.org_id == org_id,
                ReviewRequest.source_type == source_type,
                ReviewRequest.source_id == source_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None

    raw = svc.generate_token()
    rr = ReviewRequest(
        org_id=org_id,
        customer_id=customer_id,
        source_type=source_type,
        source_id=source_id,
        token_hash=svc.hash_token(raw),
        expires_at=svc.compute_expiry(),
    )
    db.add(rr)
    await db.flush()
    # Stash the raw token for the caller (email dispatcher) without
    # persisting it. ``_raw_token`` is a convention used by the
    # supplier-portal module.
    rr._raw_token = raw  # type: ignore[attr-defined]
    return rr
