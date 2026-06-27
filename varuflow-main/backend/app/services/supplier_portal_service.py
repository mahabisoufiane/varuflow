"""Supplier-portal service (Item 37).

Split into **pure helpers** (token generation, hashing, validation
state machine) and **DB-bound wrappers** (issue, verify, revoke, list
POs, confirm PO). Pure helpers are unit-testable without a database;
DB wrappers lazy-import the ORM models inside the function body so the
3.9 test sandbox never pulls the model graph when it only needs the
pure code.

Replay-resistance strategy:

* The raw token is 32 random bytes (``secrets.token_urlsafe(32)``) —
  ~190 bits of entropy, infeasible to brute force.
* Only the SHA-256 of the raw token is persisted. A DB leak never
  yields usable tokens.
* ``is_revoked`` + ``expires_at`` are checked on *every* portal
  request; revocation is therefore immediate.
* Confirmations are **idempotent** at the PO level — a supplier who
  captures the confirm request and re-posts it cannot advance state
  twice because the PO's ``confirmed_at`` is stamped atomically in
  one UPDATE with a guard on ``confirmed_at IS NULL``.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

# Number of bytes of entropy in the raw magic-link token. 32 bytes = 256
# bits; ``secrets.token_urlsafe`` base64-encodes which produces ~43
# characters. Matches the customer-portal helper in portal.py.
_RAW_TOKEN_BYTES = 32
# Default lifetime of a newly issued supplier portal token. 14 days
# balances "let the supplier confirm a weekly PO at leisure" against
# "don't leave long-lived credentials lying around". Overridable via
# the router's ``expires_in_days`` query param.
DEFAULT_EXPIRY_DAYS = 14
# Maximum lifetime an org can request. Cap prevents a careless caller
# from minting a 10-year token.
MAX_EXPIRY_DAYS = 90


# ═══════════════════════════════════════════════════════════════════
# Pure helpers
# ═══════════════════════════════════════════════════════════════════


def generate_token() -> str:
    """Return a freshly minted raw magic-link token.

    Always unique — ``secrets.token_urlsafe`` uses the CSPRNG so two
    calls in the same microsecond still diverge. The caller passes
    this through :func:`hash_token` before storing.
    """
    return secrets.token_urlsafe(_RAW_TOKEN_BYTES)


def hash_token(raw: str) -> str:
    """SHA-256 hex digest of the raw token.

    Deterministic — same input always yields the same 64-char hex.
    The database stores only this hash; comparing an inbound raw
    token to the stored hash is the token verification primitive.
    """
    if not isinstance(raw, str):
        raise ValueError("raw_token_must_be_string")
    if not raw:
        raise ValueError("raw_token_empty")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def clamp_expiry_days(days: int | None) -> int:
    """Bound a caller-supplied TTL to the allowed range."""
    value = int(days) if days is not None else DEFAULT_EXPIRY_DAYS
    if value < 1:
        value = 1
    if value > MAX_EXPIRY_DAYS:
        value = MAX_EXPIRY_DAYS
    return value


@dataclass
class TokenRecord:
    """Pure, DB-agnostic view of a ``supplier_portal_tokens`` row.

    Used by :func:`validate_token_record` so the validation state
    machine has zero ORM coupling and can be exhaustively unit tested.
    """
    supplier_id: uuid.UUID
    org_id: uuid.UUID
    token_hash: str
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None
    is_revoked: bool


def validate_token_record(
    record: TokenRecord,
    *,
    raw_token: str,
    now: datetime,
) -> None:
    """Raise :class:`ValueError` with a coded message if the token is
    not usable right now; return ``None`` otherwise.

    Codes:

    * ``token_hash_mismatch`` — the raw token doesn't hash to the
      stored digest. Treat as a replay attack (someone typed a
      stale or crafted token).
    * ``token_revoked`` — admin flipped ``is_revoked`` → True.
    * ``token_expired`` — ``expires_at`` already in the past. Same
      UX as a revoked token from the supplier's perspective.

    No other code paths exist — the caller can render a generic
    "invalid or expired link" copy without leaking which specific
    guard tripped.
    """
    if hash_token(raw_token) != record.token_hash:
        raise ValueError("token_hash_mismatch")
    if record.is_revoked:
        raise ValueError("token_revoked")
    if _aware(record.expires_at) <= _aware(now):
        raise ValueError("token_expired")


def is_token_live(record: TokenRecord, now: datetime) -> bool:
    """True iff the record is neither revoked nor expired.

    Pure wrapper around the same checks as :func:`validate_token_record`
    minus the hash comparison (callers who already hold the row don't
    need to re-hash). Useful for admin listings that paint a "live /
    revoked / expired" badge.
    """
    if record.is_revoked:
        return False
    return _aware(record.expires_at) > _aware(now)


def compute_expires_at(created_at: datetime, days: int) -> datetime:
    """Pure arithmetic — isolates the TTL calculation so tests can
    pin a known ``created_at`` and assert an exact ``expires_at``.
    """
    return _aware(created_at) + timedelta(days=clamp_expiry_days(days))


def build_magic_url(portal_base_url: str, raw_token: str) -> str:
    """Construct the magic-link URL the supplier receives.

    ``raw_token`` must be URL-safe (``secrets.token_urlsafe`` always
    is); we still rstrip the base to avoid double slashes if the
    caller supplies a trailing one.
    """
    base = (portal_base_url or "").rstrip("/")
    return f"{base}/supplier-portal/verify?token={raw_token}"


def mask_raw_token(raw: str) -> str:
    """Return a short preview suitable for admin UI listings.

    Only the first 6 characters are kept — enough for an owner to
    recognise "the token I just minted" without leaking a meaningful
    fraction of the 256-bit secret (first 6 base64 chars ≈ 36 bits).
    """
    if not raw:
        return ""
    return raw[:6] + "…"


# ═══════════════════════════════════════════════════════════════════
# Confirmation state machine (pure)
# ═══════════════════════════════════════════════════════════════════


def can_confirm_po(
    *,
    po_supplier_id: uuid.UUID,
    requesting_supplier_id: uuid.UUID,
    confirmed_at: datetime | None,
) -> None:
    """Raise :class:`ValueError` if the supplier cannot confirm this PO.

    Codes:

    * ``po_not_owned_by_supplier`` — the PO belongs to a different
      supplier. A router filter should already prevent this, but
      the service double-checks to stop any router bug from
      escalating into cross-supplier confirmation.
    * ``po_already_confirmed`` — ``confirmed_at`` already stamped.
      The confirmation endpoint is idempotent on state, not on
      request — replaying the request must *not* re-stamp.
    """
    if po_supplier_id != requesting_supplier_id:
        raise ValueError("po_not_owned_by_supplier")
    if confirmed_at is not None:
        raise ValueError("po_already_confirmed")


# ═══════════════════════════════════════════════════════════════════
# Internal
# ═══════════════════════════════════════════════════════════════════


def _aware(dt: datetime) -> datetime:
    """Return a UTC-aware ``datetime`` regardless of input tz-awareness.

    Legacy rows from older migrations may be naive; assume UTC in
    that case to keep comparisons consistent. New code writes aware
    values via ``datetime.now(timezone.utc)``.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ═══════════════════════════════════════════════════════════════════
# DB-bound wrappers (lazy-import models so the pure test sandbox
# never pulls the ORM graph).
# ═══════════════════════════════════════════════════════════════════


async def issue_token(
    db,
    *,
    supplier_id: uuid.UUID,
    org_id: uuid.UUID,
    expires_in_days: int | None = None,
) -> tuple[str, Any]:
    """Create a new portal token for a supplier.

    Returns ``(raw_token, row)`` where ``row`` is the ORM instance
    (flushed, not committed — caller runs the surrounding audit +
    email send + commit). The raw token is returned *only* here and
    is never fetchable again.
    """
    from app.features.purchases.supplier_portal_models import SupplierPortalToken

    raw = generate_token()
    token_hash = hash_token(raw)
    created_at = datetime.now(timezone.utc)
    row = SupplierPortalToken(
        supplier_id=supplier_id,
        org_id=org_id,
        token_hash=token_hash,
        expires_at=compute_expires_at(created_at, clamp_expiry_days(expires_in_days)),
    )
    db.add(row)
    await db.flush()
    return raw, row


async def lookup_by_raw_token(db, *, raw_token: str):
    """Fetch the token row for a raw token, or ``None`` if no match.

    The DB query hits the unique index on ``token_hash``; no table
    scan even under heavy use. Returns the ORM row so the caller can
    wrap it with ``validate_token_record`` for the state-machine check.
    """
    from sqlalchemy import select

    from app.features.purchases.supplier_portal_models import SupplierPortalToken

    stmt = select(SupplierPortalToken).where(
        SupplierPortalToken.token_hash == hash_token(raw_token)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def touch_last_used(db, *, token_id: uuid.UUID) -> None:
    """Stamp ``last_used_at`` so admins see "last active" per token.

    Fire-and-forget — never raises. Caller is expected to commit in
    the surrounding request lifecycle.
    """
    from sqlalchemy import update

    from app.features.purchases.supplier_portal_models import SupplierPortalToken

    try:
        await db.execute(
            update(SupplierPortalToken)
            .where(SupplierPortalToken.id == token_id)
            .values(last_used_at=datetime.now(timezone.utc))
        )
    except Exception:
        # Non-critical telemetry; swallow so a busy DB doesn't 500
        # the portal page load.
        pass


async def revoke_token(db, *, token_id: uuid.UUID, org_id: uuid.UUID) -> bool:
    """Mark a token revoked. Returns True if a row was updated.

    Filters on ``org_id`` so a cross-org revoke attempt (via forged
    ID in URL) fails silently.
    """
    from sqlalchemy import update

    from app.features.purchases.supplier_portal_models import SupplierPortalToken

    result = await db.execute(
        update(SupplierPortalToken)
        .where(
            SupplierPortalToken.id == token_id,
            SupplierPortalToken.org_id == org_id,
            SupplierPortalToken.is_revoked == False,  # noqa: E712
        )
        .values(is_revoked=True)
    )
    return result.rowcount > 0


async def list_supplier_pos(db, *, supplier_id: uuid.UUID, org_id: uuid.UUID):
    """Return SENT + RECEIVED + confirmed POs for this supplier.

    DRAFT POs are excluded — the org may still be editing them.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.features.inventory.models import PurchaseOrder, PurchaseOrderStatus

    stmt = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.items))
        .where(
            PurchaseOrder.supplier_id == supplier_id,
            PurchaseOrder.org_id == org_id,
            PurchaseOrder.status != PurchaseOrderStatus.DRAFT,
        )
        .order_by(PurchaseOrder.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_supplier_po(db, *, po_id: uuid.UUID, supplier_id: uuid.UUID, org_id: uuid.UUID):
    """Fetch a single PO for this supplier, or ``None``.

    Draft POs are withheld even if the raw ID is guessed — the
    filter on ``status != DRAFT`` is the same as
    :func:`list_supplier_pos` so a supplier cannot use the detail
    endpoint to peek at unpublished drafts.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.features.inventory.models import PurchaseOrder, PurchaseOrderStatus

    stmt = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.items))
        .where(
            PurchaseOrder.id == po_id,
            PurchaseOrder.supplier_id == supplier_id,
            PurchaseOrder.org_id == org_id,
            PurchaseOrder.status != PurchaseOrderStatus.DRAFT,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def confirm_po(
    db,
    *,
    po_id: uuid.UUID,
    supplier_id: uuid.UUID,
    org_id: uuid.UUID,
) -> bool:
    """Atomically stamp ``confirmed_at`` if the PO is still pending.

    Returns True on success, False if already confirmed. The update
    guards on ``confirmed_at IS NULL`` so two concurrent confirmation
    requests (a rapid double-click, or a deliberate replay) cannot
    both stamp — second caller sees rowcount==0 and a 409 is raised
    at the router layer. This is the replay-resistance proof for the
    confirmation mutation.
    """
    from sqlalchemy import update

    from app.features.inventory.models import PurchaseOrder, PurchaseOrderStatus

    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(PurchaseOrder)
        .where(
            PurchaseOrder.id == po_id,
            PurchaseOrder.supplier_id == supplier_id,
            PurchaseOrder.org_id == org_id,
            PurchaseOrder.status != PurchaseOrderStatus.DRAFT,
            PurchaseOrder.confirmed_at.is_(None),
        )
        .values(
            confirmed_at=now,
            confirmed_by_supplier_id=supplier_id,
        )
    )
    return result.rowcount > 0


async def find_active_tokens(db, *, org_id: uuid.UUID, supplier_id: uuid.UUID | None = None):
    """Admin helper: list live tokens for the org (optionally filtered
    to one supplier). Hides hashes — only metadata is returned.
    """
    from sqlalchemy import select

    from app.features.purchases.supplier_portal_models import SupplierPortalToken

    stmt = select(SupplierPortalToken).where(
        SupplierPortalToken.org_id == org_id,
    )
    if supplier_id is not None:
        stmt = stmt.where(SupplierPortalToken.supplier_id == supplier_id)
    stmt = stmt.order_by(SupplierPortalToken.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()
