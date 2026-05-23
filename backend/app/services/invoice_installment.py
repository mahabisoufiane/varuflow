"""Pure helpers for invoice installment plans (Item 54)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

STATUS_SCHEDULED = "scheduled"
STATUS_PARTIAL = "partial"
STATUS_PAID = "paid"
STATUS_OVERDUE = "overdue"
STATUS_CANCELLED = "cancelled"

ACTIVE_STATUSES = {STATUS_SCHEDULED, STATUS_PARTIAL, STATUS_OVERDUE}
REMINDER_DAYS_BEFORE = 3


@dataclass(frozen=True)
class PlannedInstallment:
    sequence: int
    amount_sek: Decimal
    due_date: date


def _q(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_plan(
    *,
    total_sek: Decimal,
    parts: int,
    start_date: date,
    interval_days: int = 30,
) -> list[PlannedInstallment]:
    """Split ``total_sek`` into ``parts`` installments.

    Equal shares rounded to 2 dp; any rounding remainder is added to
    the final installment so the sum matches ``total_sek`` exactly.
    """
    if parts <= 0:
        raise ValueError("parts must be >= 1")
    if parts > 36:
        raise ValueError("parts must be <= 36")
    if total_sek <= 0:
        raise ValueError("total_sek must be > 0")
    if interval_days <= 0:
        raise ValueError("interval_days must be > 0")

    total = _q(total_sek)
    base = _q(total / Decimal(parts))
    plan: list[PlannedInstallment] = []
    running = Decimal("0.00")
    for i in range(1, parts + 1):
        if i < parts:
            amount = base
        else:
            amount = _q(total - running)
        plan.append(
            PlannedInstallment(
                sequence=i,
                amount_sek=amount,
                due_date=start_date + timedelta(days=interval_days * (i - 1)),
            )
        )
        running += amount
    return plan


def apply_payment(
    *,
    paid_amount_sek: Decimal,
    amount_sek: Decimal,
    payment_sek: Decimal,
) -> tuple[Decimal, str]:
    """Apply ``payment_sek`` to a single installment.

    Returns the new ``(paid_amount_sek, status)`` pair. Status is
    ``paid`` once the paid amount covers the full amount (within a
    rounding-safe epsilon), ``partial`` if some payment landed, or
    the prior implied scheduled state otherwise.
    """
    if payment_sek < 0:
        raise ValueError("payment_sek must be >= 0")
    new_paid = _q(paid_amount_sek + payment_sek)
    amt = _q(amount_sek)
    if new_paid >= amt:
        return amt, STATUS_PAID
    if new_paid > 0:
        return new_paid, STATUS_PARTIAL
    return Decimal("0.00"), STATUS_SCHEDULED


def is_overdue(
    *,
    due_date: date,
    status: str,
    today: date,
) -> bool:
    """An installment is overdue if past due_date and not yet fully paid."""
    if status in (STATUS_PAID, STATUS_CANCELLED):
        return False
    return today > due_date


def needs_reminder(
    *,
    due_date: date,
    status: str,
    last_reminded_at: date | None,
    today: date,
) -> bool:
    """Remind once when within ``REMINDER_DAYS_BEFORE`` of due date."""
    if status not in ACTIVE_STATUSES:
        return False
    if last_reminded_at is not None:
        return False
    delta = (due_date - today).days
    return 0 <= delta <= REMINDER_DAYS_BEFORE


def plan_sum(plan: Iterable[PlannedInstallment]) -> Decimal:
    total = Decimal("0.00")
    for p in plan:
        total += p.amount_sek
    return _q(total)
