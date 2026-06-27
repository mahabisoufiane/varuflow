"""Pure helpers for customer contracts (Item 66).

All rules the router depends on live here so they're unit-testable
without a DB. The state machine is deliberately tiny:

    DRAFT ──activate──▶ ACTIVE ──expire──▶ EXPIRED
                       └──terminate──▶ TERMINATED
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable

MAX_TITLE_LENGTH: int = 200
MAX_BODY_LENGTH: int = 100_000
MAX_REASON_LENGTH: int = 500
MIN_VALUE: Decimal = Decimal("0")
MAX_VALUE: Decimal = Decimal("1000000000")  # 1B cap
MIN_RENEW_MONTHS: int = 1
MAX_RENEW_MONTHS: int = 120  # 10 years

ALLOWED_STATUSES: frozenset[str] = frozenset({
    "DRAFT", "ACTIVE", "EXPIRED", "TERMINATED",
})
# Source → allowed targets.
_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT":      frozenset({"ACTIVE"}),
    "ACTIVE":     frozenset({"EXPIRED", "TERMINATED"}),
    "EXPIRED":    frozenset(),
    "TERMINATED": frozenset(),
}


@dataclass(frozen=True)
class ContractDates:
    start: date
    end:   date | None


def validate_title(title: str) -> str:
    if not isinstance(title, str):
        raise ValueError("title must be a string")
    s = " ".join(title.strip().split())
    if not s:
        raise ValueError("title is required")
    if len(s) > MAX_TITLE_LENGTH:
        raise ValueError(f"title too long ({MAX_TITLE_LENGTH} chars max)")
    return s


def validate_body(body: str | None) -> str | None:
    if body is None:
        return None
    if not isinstance(body, str):
        raise ValueError("body must be a string")
    if len(body) > MAX_BODY_LENGTH:
        raise ValueError(f"body too long ({MAX_BODY_LENGTH} chars max)")
    return body


def validate_value_amount(value) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("value_amount must be a number")
    try:
        v = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception:
        raise ValueError("value_amount must be a number")
    if v < MIN_VALUE:
        raise ValueError("value_amount must be non-negative")
    if v > MAX_VALUE:
        raise ValueError(f"value_amount exceeds {MAX_VALUE}")
    return v


def validate_currency(code: str) -> str:
    if not isinstance(code, str) or len(code) != 3 or not code.isalpha():
        raise ValueError("currency must be a 3-letter ISO code")
    return code.upper()


def validate_renew_months(months: int | None) -> int | None:
    if months is None:
        return None
    if isinstance(months, bool) or not isinstance(months, int):
        raise ValueError("auto_renew_months must be an integer")
    if months < MIN_RENEW_MONTHS or months > MAX_RENEW_MONTHS:
        raise ValueError(
            f"auto_renew_months must be between "
            f"{MIN_RENEW_MONTHS} and {MAX_RENEW_MONTHS}"
        )
    return months


def validate_reason(reason: str) -> str:
    if not isinstance(reason, str):
        raise ValueError("reason must be a string")
    s = reason.strip()
    if not s:
        raise ValueError("reason is required")
    if len(s) > MAX_REASON_LENGTH:
        raise ValueError(f"reason too long ({MAX_REASON_LENGTH} chars max)")
    return s


def validate_dates(start: date, end: date | None) -> ContractDates:
    if not isinstance(start, date):
        raise ValueError("start_date must be a date")
    if end is not None:
        if not isinstance(end, date):
            raise ValueError("end_date must be a date")
        if end < start:
            raise ValueError("end_date cannot be before start_date")
    return ContractDates(start=start, end=end)


def assert_transition(current: str, target: str) -> None:
    if current not in ALLOWED_STATUSES:
        raise ValueError(f"unknown source status: {current}")
    if target not in ALLOWED_STATUSES:
        raise ValueError(f"unknown target status: {target}")
    allowed = _TRANSITIONS[current]
    if target not in allowed:
        raise ValueError(
            f"cannot transition {current} → {target}"
            + (f" (only {sorted(allowed)})" if allowed else " (terminal state)")
        )


def is_expired(end: date | None, today: date) -> bool:
    """True iff the contract's end date is strictly before ``today``.

    Contracts ending *today* are still active (end_date is inclusive);
    the sweep runs after midnight so "yesterday or earlier" is the
    canonical condition.
    """
    if end is None:
        return False
    return end < today


def next_renewal_end(current_end: date, months: int) -> date:
    """Compute the next end_date after an auto-renew."""
    if months < MIN_RENEW_MONTHS:
        raise ValueError("months must be >= 1")
    # Month arithmetic without pulling dateutil: normalise to
    # (year, month) and clamp the day to the month's last valid day.
    y = current_end.year
    m = current_end.month + months
    while m > 12:
        y += 1
        m -= 12
    # Clamp day to month length (handles Jan 31 → Feb 28/29 etc.)
    if m == 2:
        last_day = 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28
    elif m in (4, 6, 9, 11):
        last_day = 30
    else:
        last_day = 31
    day = min(current_end.day, last_day)
    return date(y, m, day)


def select_renewals(
    contracts: Iterable[tuple[str, str, date | None, int | None]],
    today: date,
) -> list[str]:
    """Given ``(id, status, end_date, auto_renew_months)`` tuples,
    return the ids of ACTIVE contracts whose end_date is on or before
    ``today`` AND have auto_renew configured.
    """
    out: list[str] = []
    for cid, status, end, months in contracts:
        if status != "ACTIVE":
            continue
        if end is None or months is None:
            continue
        if end <= today:
            out.append(cid)
    return out
