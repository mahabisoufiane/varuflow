"""Loyalty engine — pure + DB-bound helpers (Item 35).

The **pure** block (``points_for_amount``, ``tier_for_lifetime``,
``redemption_discount``, ``validate_redemption``, ``sum_active_points``)
has zero ORM dependencies and is unit-testable against
``SimpleNamespace`` stand-ins — same pattern as Items 30–34.

The **DB-bound** block (``ensure_account``, ``award_points``,
``redeem_points``, ``adjust_points``, ``expire_old_points``,
``active_program``) talks to SQLAlchemy.

Ledger invariant
----------------
Every mutation produces exactly one :class:`LoyaltyTransaction` row
(signed). The account's ``points_balance`` and ``lifetime_points``
are derived caches kept in sync by the helpers below — never mutate
them without adding a ledger row.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Model classes are imported lazily inside the DB-bound helpers to
# avoid pulling the whole ``app.models`` package into unit tests of
# the pure helpers (Python 3.9 doesn't evaluate annotations at
# runtime when ``from __future__ import annotations`` is set, so
# type hints referencing these classes are safe).

# ── Tier thresholds (lifetime points required to reach tier) ────────
TIER_THRESHOLDS: dict[str, int] = {
    "bronze": 0,
    "silver": 500,
    "gold": 2_000,
    "platinum": 10_000,
}
TIER_ORDER: tuple[str, ...] = ("bronze", "silver", "gold", "platinum")

ALLOWED_TX_TYPES = frozenset({"earn", "redeem", "expire", "adjust"})


# ═══════════════════════════════════════════════════════════════════
# Pure helpers (no DB access — safe for unit tests)
# ═══════════════════════════════════════════════════════════════════


def _to_decimal(value: Any) -> Decimal:
    """Coerce ``value`` to ``Decimal``. Returns ``0`` for junk input."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def points_for_amount(amount: Any, rate: Any = 1) -> int:
    """Compute earned points for a monetary amount.

    ``floor(amount * rate)``. Negative or malformed inputs → 0. The
    floor keeps the ledger in integer points (no partial credits).
    """
    amt = _to_decimal(amount)
    r = _to_decimal(rate)
    if amt <= 0 or r <= 0:
        return 0
    product = (amt * r).to_integral_value(rounding=ROUND_DOWN)
    return int(product) if product >= 0 else 0


def tier_for_lifetime(lifetime_points: int) -> str:
    """Return the highest tier achieved for a lifetime-points total."""
    tier = "bronze"
    for name in TIER_ORDER:
        if lifetime_points >= TIER_THRESHOLDS[name]:
            tier = name
    return tier


def redemption_discount(points: int, rate: Any) -> Decimal:
    """Monetary value of redeeming ``points`` at ``rate``.

    Clamps to two decimal places (rounding half-up is fine for a
    discount — the customer never sees a fraction of a currency unit).
    """
    if points <= 0:
        return Decimal("0.00")
    r = _to_decimal(rate)
    if r <= 0:
        return Decimal("0.00")
    value = (Decimal(points) * r).quantize(Decimal("0.01"))
    return value if value > 0 else Decimal("0.00")


@dataclass(frozen=True)
class RedemptionCheck:
    ok: bool
    reason: str | None
    discount: Decimal


def validate_redemption(
    points: int, *, balance: int, cap: Decimal | None = None, rate: Any = Decimal("0.01")
) -> RedemptionCheck:
    """Validate a redemption request against the account balance + cap."""
    if points <= 0:
        return RedemptionCheck(False, "points_must_be_positive", Decimal("0.00"))
    if points > balance:
        return RedemptionCheck(False, "insufficient_balance", Decimal("0.00"))
    discount = redemption_discount(points, rate)
    if cap is not None and discount > cap:
        return RedemptionCheck(False, "exceeds_cap", discount)
    return RedemptionCheck(True, None, discount)


def sum_active_points(rows: Iterable, *, now: datetime | None = None) -> int:
    """Reconstruct a balance from a ledger.

    Unexpired earn/redeem/adjust rows all count; rows where
    ``expires_at`` has passed are ignored (they'd have been zeroed out
    by the expiry job, but this makes the pure helper reversible).
    """
    when = now or datetime.now(timezone.utc)
    total = 0
    for r in rows:
        expires = getattr(r, "expires_at", None)
        if expires is not None and expires <= when:
            continue
        total += int(getattr(r, "points", 0) or 0)
    return total


# ── Pure reducers (no DB access) ────────────────────────────────────
# Each returns the new ``(balance, lifetime, tier)`` tuple for the
# corresponding mutation. The DB-bound helpers below use the same
# reducers so tests and production agree byte-for-byte.


def apply_earn(balance: int, lifetime: int, points: int) -> tuple[int, int, str]:
    """Credit ``points`` to an earn. Tier recomputed from lifetime."""
    if points <= 0:
        return int(balance), int(lifetime), tier_for_lifetime(int(lifetime))
    new_balance = int(balance) + int(points)
    new_lifetime = int(lifetime) + int(points)
    return new_balance, new_lifetime, tier_for_lifetime(new_lifetime)


def apply_redeem(balance: int, lifetime: int, points: int) -> tuple[int, int, str]:
    """Debit ``points`` for a redemption. Lifetime is preserved."""
    if points <= 0 or points > int(balance):
        raise ValueError("insufficient_balance")
    new_balance = int(balance) - int(points)
    return new_balance, int(lifetime), tier_for_lifetime(int(lifetime))


def apply_adjust(balance: int, lifetime: int, delta: int) -> tuple[int, int, str]:
    """Staff adjustment. Positive delta bumps lifetime; negative doesn't."""
    if delta == 0:
        raise ValueError("delta_must_be_nonzero")
    new_balance = int(balance) + int(delta)
    if new_balance < 0:
        raise ValueError("insufficient_balance")
    new_lifetime = int(lifetime) + int(delta) if delta > 0 else int(lifetime)
    return new_balance, new_lifetime, tier_for_lifetime(new_lifetime)


def apply_expire(balance: int, lifetime: int, expired: int) -> tuple[int, int, str]:
    """Expire ``expired`` points, clamped to the current balance."""
    debit = max(0, min(int(expired), int(balance)))
    new_balance = int(balance) - debit
    return new_balance, int(lifetime), tier_for_lifetime(int(lifetime))


def bucket_expiring_rows(
    rows: Iterable, *, within_days: int = 14, now: datetime | None = None
) -> "dict[Any, tuple[int, datetime]]":
    """Group ledger rows expiring within the window by account.

    Returns ``{account_id: (total_points, earliest_expiry)}``. Pure —
    the DB-bound helper uses this to build the notification payload.
    """
    when = now or datetime.now(timezone.utc)
    cutoff = when + timedelta(days=max(1, int(within_days)))
    buckets: dict = {}
    for row in rows:
        expires = getattr(row, "expires_at", None)
        pts = int(getattr(row, "points", 0) or 0)
        tx_type = getattr(row, "type", None)
        if expires is None or pts <= 0 or tx_type != "earn":
            continue
        if expires <= when or expires > cutoff:
            continue
        acc_id = getattr(row, "account_id", None)
        if acc_id is None:
            continue
        existing_pts, existing_earliest = buckets.get(acc_id, (0, expires))
        buckets[acc_id] = (
            existing_pts + pts,
            min(existing_earliest, expires) if existing_earliest else expires,
        )
    return buckets


# ═══════════════════════════════════════════════════════════════════
# DB-bound helpers
# ═══════════════════════════════════════════════════════════════════


async def active_program(db: AsyncSession, org_id: uuid.UUID) -> "LoyaltyProgram | None":
    """Return the org's currently active program, or ``None``."""
    from app.models.loyalty import LoyaltyProgram

    stmt = (
        select(LoyaltyProgram)
        .where(LoyaltyProgram.org_id == org_id, LoyaltyProgram.is_active.is_(True))
        .order_by(LoyaltyProgram.created_at.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def ensure_account(
    db: AsyncSession, *, org_id: uuid.UUID, customer_id: uuid.UUID
) -> "LoyaltyAccount":
    """Return the customer's loyalty account, creating it if missing."""
    from app.models.loyalty import LoyaltyAccount

    stmt = select(LoyaltyAccount).where(
        LoyaltyAccount.org_id == org_id,
        LoyaltyAccount.customer_id == customer_id,
    )
    res = await db.execute(stmt)
    acc = res.scalar_one_or_none()
    if acc is not None:
        return acc
    acc = LoyaltyAccount(
        id=uuid.uuid4(),
        org_id=org_id,
        customer_id=customer_id,
        points_balance=0,
        lifetime_points=0,
        tier="bronze",
    )
    db.add(acc)
    await db.flush()
    return acc


def _expiry_for(program: "LoyaltyProgram | None") -> datetime | None:
    if program is None or not getattr(program, "expiry_days", 0):
        return None
    days = int(program.expiry_days or 0)
    if days <= 0:
        return None
    return datetime.now(timezone.utc) + timedelta(days=days)


async def _write_ledger(
    db: AsyncSession,
    *,
    account: "LoyaltyAccount",
    points: int,
    tx_type: str,
    source_type: str | None,
    source_id: str | None,
    reason: str | None,
    expires_at: datetime | None,
) -> "LoyaltyTransaction":
    from app.models.loyalty import LoyaltyTransaction

    if tx_type not in ALLOWED_TX_TYPES:
        raise ValueError(f"invalid loyalty transaction type: {tx_type!r}")
    tx = LoyaltyTransaction(
        id=uuid.uuid4(),
        account_id=account.id,
        points=int(points),
        type=tx_type,
        source_type=source_type,
        source_id=source_id,
        reason=reason,
        expires_at=expires_at,
    )
    db.add(tx)
    return tx


async def award_points(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    customer_id: uuid.UUID,
    amount: Any,
    source_type: str,
    source_id: str,
    program: "LoyaltyProgram | None" = None,
) -> "LoyaltyTransaction | None":
    """Award points for a transaction of ``amount``.

    No-ops (returns ``None``) when the org has no active program, the
    amount is zero/negative, or the computed points equal zero. Safe
    to call from POS / booking / invoice hooks — never raises for
    routine misses so payment flows are never blocked by loyalty
    bookkeeping.
    """
    prog = program if program is not None else await active_program(db, org_id)
    if prog is None or not prog.is_active:
        return None
    pts = points_for_amount(amount, prog.points_per_currency_unit)
    if pts <= 0:
        return None
    account = await ensure_account(db, org_id=org_id, customer_id=customer_id)
    tx = await _write_ledger(
        db,
        account=account,
        points=pts,
        tx_type="earn",
        source_type=source_type,
        source_id=source_id,
        reason=None,
        expires_at=_expiry_for(prog),
    )
    new_balance, new_lifetime, new_tier = apply_earn(
        int(account.points_balance), int(account.lifetime_points), pts
    )
    account.points_balance = new_balance
    account.lifetime_points = new_lifetime
    account.tier = new_tier
    return tx


async def redeem_points(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    customer_id: uuid.UUID,
    points: int,
    source_type: str,
    source_id: str,
    cap: Decimal | None = None,
) -> "tuple[LoyaltyTransaction, Decimal]":
    """Redeem ``points`` off a current transaction.

    Returns ``(transaction, discount_amount)``. Raises :class:`ValueError`
    with a coded reason on failed validation so the caller can surface
    a 400 to the client.
    """
    prog = await active_program(db, org_id)
    if prog is None:
        raise ValueError("no_active_program")
    account = await ensure_account(db, org_id=org_id, customer_id=customer_id)
    check = validate_redemption(
        int(points), balance=int(account.points_balance), cap=cap, rate=prog.redemption_rate
    )
    if not check.ok:
        raise ValueError(check.reason or "invalid_redemption")
    tx = await _write_ledger(
        db,
        account=account,
        points=-int(points),
        tx_type="redeem",
        source_type=source_type,
        source_id=source_id,
        reason=None,
        expires_at=None,
    )
    new_balance, _, _ = apply_redeem(
        int(account.points_balance), int(account.lifetime_points), int(points)
    )
    account.points_balance = new_balance
    # Lifetime points are NOT decreased on redemption — tier is earned.
    return tx, check.discount


async def adjust_points(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    customer_id: uuid.UUID,
    delta: int,
    reason: str,
) -> "LoyaltyTransaction":
    """Staff-initiated manual adjustment (grant or revoke)."""
    if delta == 0:
        raise ValueError("delta_must_be_nonzero")
    if not reason or not reason.strip():
        raise ValueError("reason_required")
    account = await ensure_account(db, org_id=org_id, customer_id=customer_id)
    if delta < 0 and abs(int(delta)) > int(account.points_balance):
        raise ValueError("insufficient_balance")
    tx = await _write_ledger(
        db,
        account=account,
        points=int(delta),
        tx_type="adjust",
        source_type="staff",
        source_id=None,
        reason=reason.strip()[:500],
        expires_at=None,
    )
    new_balance, new_lifetime, new_tier = apply_adjust(
        int(account.points_balance), int(account.lifetime_points), int(delta)
    )
    account.points_balance = new_balance
    account.lifetime_points = new_lifetime
    account.tier = new_tier
    return tx


async def expire_old_points(
    db: AsyncSession, *, now: datetime | None = None
) -> int:
    """Expire ledger rows whose ``expires_at`` has passed.

    For each account with net expired earn points, writes one negative
    ``expire`` row and decrements the balance. Lifetime points are
    preserved (they represent customer activity, not spendable value).

    Returns the number of accounts touched — used by the scheduler to
    log a summary line.
    """
    from app.models.loyalty import LoyaltyAccount, LoyaltyTransaction

    when = now or datetime.now(timezone.utc)
    # Pull all unexpired rows whose expires_at has passed AND that have
    # not been reversed by an earlier expire row (we flag expiry rows
    # by negating + setting expires_at=None on the expire entry).
    stmt = (
        select(LoyaltyTransaction)
        .where(
            LoyaltyTransaction.expires_at.isnot(None),
            LoyaltyTransaction.expires_at <= when,
            LoyaltyTransaction.type == "earn",
            LoyaltyTransaction.points > 0,
        )
    )
    res = await db.execute(stmt)
    rows = list(res.scalars())
    if not rows:
        return 0

    # Group expired earn points per account.
    by_account: dict[uuid.UUID, int] = {}
    to_mark: list[LoyaltyTransaction] = []
    for row in rows:
        by_account[row.account_id] = by_account.get(row.account_id, 0) + int(row.points)
        to_mark.append(row)

    touched = 0
    for acc_id, expired_points in by_account.items():
        if expired_points <= 0:
            continue
        account = await db.get(LoyaltyAccount, acc_id)
        if account is None:
            continue
        # Clamp to current balance — if staff already debited the
        # account, we don't over-expire.
        debit = min(int(expired_points), int(account.points_balance))
        if debit <= 0:
            continue
        await _write_ledger(
            db,
            account=account,
            points=-debit,
            tx_type="expire",
            source_type="scheduler",
            source_id=None,
            reason="points_expired",
            expires_at=None,
        )
        new_balance, _, _ = apply_expire(
            int(account.points_balance), int(account.lifetime_points), debit
        )
        account.points_balance = new_balance
        touched += 1

    # Flip expires_at on the consumed earn rows so they're not picked
    # up again on the next sweep (we keep the timestamp; the ``expire``
    # type on the offsetting row is enough for auditors).
    # No action required — the offsetting ``expire`` row is the marker.
    # The WHERE clause of the next sweep also requires ``points > 0``
    # and ``expires_at <= now``, which still matches the old rows.
    # So we null out expires_at on the consumed rows to skip them.
    for row in to_mark:
        row.expires_at = None

    return touched


async def points_expiring_soon(
    db: AsyncSession,
    *,
    within_days: int = 14,
    now: datetime | None = None,
) -> "list[tuple[LoyaltyAccount, int, datetime]]":
    """Return (account, expiring_points, earliest_expiry) per affected account."""
    from app.models.loyalty import LoyaltyAccount, LoyaltyTransaction

    when = now or datetime.now(timezone.utc)
    cutoff = when + timedelta(days=max(1, int(within_days)))
    stmt = (
        select(LoyaltyTransaction)
        .where(
            LoyaltyTransaction.expires_at.isnot(None),
            LoyaltyTransaction.expires_at > when,
            LoyaltyTransaction.expires_at <= cutoff,
            LoyaltyTransaction.type == "earn",
            LoyaltyTransaction.points > 0,
        )
    )
    res = await db.execute(stmt)
    rows = list(res.scalars())
    buckets: dict[uuid.UUID, tuple[int, datetime]] = {}
    for row in rows:
        pts, earliest = buckets.get(row.account_id, (0, row.expires_at))
        buckets[row.account_id] = (
            pts + int(row.points),
            min(earliest, row.expires_at) if earliest else row.expires_at,
        )
    out: list[tuple[LoyaltyAccount, int, datetime]] = []
    for acc_id, (pts, earliest) in buckets.items():
        account = await db.get(LoyaltyAccount, acc_id)
        if account is not None:
            out.append((account, pts, earliest))
    return out
