"""Gift card & service bundle business logic (v49 — Item 33).

Two layers, matching the Item 30/31/32 isolation pattern:

* **Pure** — ``generate_code``, ``compute_redemption``,
  ``is_expired``, ``compute_remaining_sessions``,
  ``bundle_covers_service``. Testable under Python 3.9 without
  hitting Postgres or the ORM types.
* **DB-bound** — ``redeem_gift_card``, ``issue_gift_card``,
  ``consume_bundle_session``. Lazy-import the ORM; each is
  best-effort-safe for its caller (the POS / bookings / invoicing
  hooks must never break on a gift-card failure).
"""
from __future__ import annotations

import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable


# Code generation — A-Z+0-9, avoid look-alikes (0/O, 1/I).
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_DEFAULT_LENGTH = 12


def _q(value) -> Decimal:
    """Quantise to 2 decimals, half-up. Matches invoicing/commissions."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def generate_code(length: int = _DEFAULT_LENGTH) -> str:
    """Generate a cryptographically random, human-friendly gift-card code.

    Uses ``secrets`` (not ``random``) so codes can't be predicted
    from timing. 32^12 keyspace is ~1.15e18 — uniqueness within a
    single org is enforced by the DB unique constraint, so a clash
    just triggers a retry at the call site.
    """
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def is_expired(card_or_row, *, now: datetime | None = None) -> bool:
    """Return True if the card/row's ``expires_at`` is in the past.

    ``None`` expires_at means "never expires" → always False.
    Status ``expired`` / ``void`` short-circuits to True regardless
    of the timestamp.
    """
    status = getattr(card_or_row, "status", None)
    if status in ("expired", "void"):
        return True
    expires_at = getattr(card_or_row, "expires_at", None)
    if expires_at is None:
        return False
    now = now or datetime.now(tz=timezone.utc)
    # Treat naive timestamps as UTC — the DB column is tz-aware but
    # Python 3.9 test fixtures may pass naive datetimes.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= now


@dataclass(frozen=True)
class RedemptionResult:
    """Outcome of a proposed gift-card redemption.

    * ``applied`` — amount deducted from the card (and from the
      transaction total).
    * ``remaining_balance`` — card balance after this redemption.
    * ``shortfall`` — how much the caller still owes (0 when the
      card fully covered the amount).
    """

    applied: Decimal
    remaining_balance: Decimal
    shortfall: Decimal


def compute_redemption(
    *,
    card_balance,
    amount_due,
    card_expired: bool = False,
) -> RedemptionResult:
    """Work out how much a card covers of ``amount_due``.

    Pure arithmetic — no DB writes. An expired card contributes zero
    and the shortfall equals ``amount_due``. Negative amounts are
    clamped to zero (you can't redeem a refund).
    """
    balance = _q(card_balance or 0)
    due = _q(amount_due or 0)
    if due < 0:
        due = Decimal("0.00")
    if balance < 0:
        balance = Decimal("0.00")
    if card_expired:
        return RedemptionResult(
            applied=Decimal("0.00"), remaining_balance=balance, shortfall=due
        )
    applied = min(balance, due)
    return RedemptionResult(
        applied=_q(applied),
        remaining_balance=_q(balance - applied),
        shortfall=_q(due - applied),
    )


def compute_remaining_sessions(purchases: int, uses: int, sessions_per_purchase: int) -> int:
    """Return remaining sessions for a customer-bundle ledger.

    Clamps to zero — a customer can't have "negative" sessions even
    if a bad data row gets through.
    """
    total = max(purchases, 0) * max(sessions_per_purchase, 0)
    return max(total - max(uses, 0), 0)


def bundle_covers_service(bundle_services: Iterable, service_id) -> bool:
    """Does this bundle's service list include the given service?

    ``bundle_services`` is a JSONB list of stringified UUIDs; the
    comparison stringifies both sides so we don't care whether the
    caller passes a ``UUID`` instance or a string.
    """
    target = str(service_id) if service_id is not None else ""
    if not target:
        return False
    for s in bundle_services or []:
        if str(s) == target:
            return True
    return False


def expiry_from_days(days: int | None, *, now: datetime | None = None) -> datetime | None:
    """Convert a ``valid_days`` integer to an absolute ``expires_at``.

    ``None`` / non-positive → no expiry. Anchored in UTC so the
    scheduler's cron (Europe/Stockholm) never sees timezone drift.
    """
    if not days or days <= 0:
        return None
    base = now or datetime.now(tz=timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base + timedelta(days=days)


# ── DB-bound helpers ──────────────────────────────────────────────


async def issue_gift_card(
    db,
    *,
    org_id,
    initial_value,
    expires_at: datetime | None = None,
    issued_to_customer_id=None,
) -> "object | None":
    """Create a new gift card row with a unique random code.

    Retries up to 3 times on code collision (unique(org_id, code)).
    Returns the row on success, ``None`` on persistent failure —
    never raises, so POS/invoicing hooks stay safe.
    """
    try:
        from sqlalchemy import select

        from app.features.loyalty.gift_cards_models import GiftCard
    except Exception:
        return None
    import uuid as _uuid

    amount = _q(initial_value)
    for _ in range(3):
        code = generate_code()
        try:
            existing = (
                await db.execute(
                    select(GiftCard).where(GiftCard.org_id == org_id, GiftCard.code == code)
                )
            ).scalar_one_or_none()
            if existing:
                continue
            card = GiftCard(
                id=_uuid.uuid4(),
                org_id=org_id,
                code=code,
                initial_value=amount,
                remaining_value=amount,
                issued_to_customer_id=issued_to_customer_id,
                expires_at=expires_at,
                status="active",
            )
            db.add(card)
            await db.flush()
            return card
        except Exception:
            continue
    return None


async def redeem_gift_card(
    db,
    *,
    org_id,
    code: str,
    amount_due,
) -> RedemptionResult | None:
    """Apply a gift card against ``amount_due`` and persist the new balance.

    Returns ``None`` when the code doesn't belong to the org; the
    caller should treat that as "no redemption happened" and charge
    the full amount. For an expired card, returns a zero-apply
    ``RedemptionResult`` so the caller can surface the right message.
    """
    try:
        from sqlalchemy import select

        from app.features.loyalty.gift_cards_models import GiftCard
    except Exception:
        return None
    card = (
        await db.execute(
            select(GiftCard)
            .where(GiftCard.org_id == org_id, GiftCard.code == (code or "").strip().upper())
            .with_for_update()
        )
    ).scalar_one_or_none()
    if card is None:
        return None
    if is_expired(card):
        if card.status == "active":
            card.status = "expired"
            await db.flush()
        return compute_redemption(
            card_balance=card.remaining_value, amount_due=amount_due, card_expired=True
        )
    result = compute_redemption(card_balance=card.remaining_value, amount_due=amount_due)
    card.remaining_value = result.remaining_balance
    if card.remaining_value <= Decimal("0.00"):
        card.status = "redeemed"
    await db.flush()
    return result


async def consume_bundle_session(
    db,
    *,
    org_id,
    customer_id,
    service_id,
    appointment_id=None,
) -> "object | None":
    """Burn one bundle session for a customer on a completed appointment.

    Finds the oldest non-exhausted, non-expired bundle the customer
    owns that covers the given service and writes a ``kind='use'``
    row. Returns the redemption on success or ``None`` when no
    bundle applied (the most common case for tenants who don't sell
    bundles). Best-effort — swallows exceptions.
    """
    try:
        from sqlalchemy import select

        from app.features.loyalty.gift_cards_models import BundleRedemption, ServiceBundle
    except Exception:
        return None
    try:
        # Load all purchase rows for this customer in this org.
        rows = (
            await db.execute(
                select(BundleRedemption).where(
                    BundleRedemption.org_id == org_id,
                    BundleRedemption.customer_id == customer_id,
                    BundleRedemption.kind.in_(("purchase", "use")),
                )
            )
        ).scalars().all()
        # Group by bundle.
        per_bundle: dict = {}
        for row in rows:
            per_bundle.setdefault(row.bundle_id, {"purchases": [], "uses": 0})
            if row.kind == "purchase":
                per_bundle[row.bundle_id]["purchases"].append(row)
            else:
                per_bundle[row.bundle_id]["uses"] += 1
        # Pick the earliest-expiring bundle that still has sessions AND
        # covers this service.
        now = datetime.now(tz=timezone.utc)
        candidate = None  # (redemption_row, bundle, expires_at)
        for bundle_id, agg in per_bundle.items():
            if not agg["purchases"]:
                continue
            bundle = (
                await db.execute(select(ServiceBundle).where(ServiceBundle.id == bundle_id))
            ).scalar_one_or_none()
            if bundle is None or not bundle.is_active:
                continue
            if not bundle_covers_service(bundle.services, service_id):
                continue
            remaining = compute_remaining_sessions(
                purchases=len(agg["purchases"]),
                uses=agg["uses"],
                sessions_per_purchase=bundle.sessions_total,
            )
            if remaining <= 0:
                continue
            earliest = min(
                (p.expires_at for p in agg["purchases"] if p.expires_at is not None),
                default=None,
            )
            if earliest is not None:
                earliest_utc = earliest if earliest.tzinfo else earliest.replace(tzinfo=timezone.utc)
                if earliest_utc <= now:
                    continue
            if candidate is None or (
                earliest is not None
                and (candidate[2] is None or earliest < candidate[2])
            ):
                candidate = (agg["purchases"][0], bundle, earliest)
        if candidate is None:
            return None
        import uuid as _uuid

        use = BundleRedemption(
            id=_uuid.uuid4(),
            org_id=org_id,
            bundle_id=candidate[1].id,
            customer_id=customer_id,
            appointment_id=appointment_id,
            kind="use",
            expires_at=candidate[2],
        )
        db.add(use)
        await db.flush()
        return use
    except Exception:
        return None
