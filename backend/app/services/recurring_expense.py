"""Pure helpers for recurring expense templates (Item 97).

Cadence math, next-due computation, title/interval/date validators.
No DB access; the router layer handles persistence.
"""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

MIN_TITLE_LEN:   int = 1
MAX_TITLE_LEN:   int = 120
MIN_INTERVAL:    int = 1
MAX_INTERVAL:    int = 365
MAX_DESCRIPTION: int = 2_000
MIN_AMOUNT:      Decimal = Decimal("0.01")
MAX_AMOUNT:      Decimal = Decimal("9999999999.99")

# Cadence string keys — we keep them as plain strings in the service so
# tests don't have to pull the SA enum.
CADENCES: tuple[str, ...] = ("DAILY", "WEEKLY", "MONTHLY", "YEARLY")


@dataclass(frozen=True)
class GeneratedOccurrence:
    """A minted-expense carbon copy ready to insert."""
    expense_date: date
    amount:       Decimal
    currency:     str
    description:  str | None


def validate_title(raw: object) -> str:
    if not isinstance(raw, str):
        raise ValueError("title must be a string")
    s = raw.strip()
    if len(s) < MIN_TITLE_LEN:
        raise ValueError("title is required")
    if len(s) > MAX_TITLE_LEN:
        raise ValueError(f"title exceeds {MAX_TITLE_LEN} characters")
    return s


def validate_description(raw: object | None) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError("description must be a string or None")
    s = raw.strip()
    if not s:
        return None
    if len(s) > MAX_DESCRIPTION:
        raise ValueError(f"description exceeds {MAX_DESCRIPTION} characters")
    return s


def validate_amount(raw: object) -> Decimal:
    try:
        value = Decimal(str(raw))
    except Exception as e:  # noqa: BLE001
        raise ValueError("amount must be a decimal") from e
    if value < MIN_AMOUNT:
        raise ValueError(f"amount must be >= {MIN_AMOUNT}")
    if value > MAX_AMOUNT:
        raise ValueError(f"amount exceeds {MAX_AMOUNT}")
    # Quantise to cents.
    return value.quantize(Decimal("0.01"))


def validate_currency(raw: object) -> str:
    if not isinstance(raw, str):
        raise ValueError("currency must be a string")
    s = raw.strip().upper()
    if len(s) != 3 or not s.isalpha():
        raise ValueError("currency must be a 3-letter ISO code")
    return s


def validate_cadence(raw: object) -> str:
    if not isinstance(raw, str):
        raise ValueError("cadence must be a string")
    s = raw.strip().upper()
    if s not in CADENCES:
        raise ValueError(
            f"cadence must be one of {', '.join(CADENCES)}"
        )
    return s


def validate_interval(raw: object) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError("interval_count must be an integer")
    if raw < MIN_INTERVAL:
        raise ValueError(f"interval_count must be >= {MIN_INTERVAL}")
    if raw > MAX_INTERVAL:
        raise ValueError(f"interval_count must be <= {MAX_INTERVAL}")
    return raw


def validate_dates(
    *, start_date: date, end_date: date | None,
) -> tuple[date, date | None]:
    if not isinstance(start_date, date):
        raise ValueError("start_date must be a date")
    if end_date is not None:
        if not isinstance(end_date, date):
            raise ValueError("end_date must be a date")
        if end_date < start_date:
            raise ValueError("end_date must be >= start_date")
    return start_date, end_date


def _add_months(d: date, months: int) -> date:
    """Add ``months`` months to ``d``, clamping day-of-month to the
    last valid day of the target month (e.g. Jan 31 + 1 month = Feb 28).
    """
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    last_dom = monthrange(year, month)[1]
    day = min(d.day, last_dom)
    return date(year, month, day)


def advance(*, from_date: date, cadence: str, interval: int) -> date:
    """Return the next occurrence after ``from_date``."""
    cadence = validate_cadence(cadence)
    interval = validate_interval(interval)
    if cadence == "DAILY":
        return date.fromordinal(from_date.toordinal() + interval)
    if cadence == "WEEKLY":
        return date.fromordinal(from_date.toordinal() + 7 * interval)
    if cadence == "MONTHLY":
        return _add_months(from_date, interval)
    # YEARLY: reuse monthly math with interval * 12.
    return _add_months(from_date, 12 * interval)


def compute_next_due(
    *,
    start_date: date,
    cadence: str,
    interval: int,
    last_generated: date | None,
    end_date: date | None,
) -> date | None:
    """Return the next due date, or ``None`` if the schedule is done.

    - If nothing has been generated yet, the next due is ``start_date``.
    - Otherwise, it is ``last_generated + 1 cadence step``.
    - If the computed date passes ``end_date`` (when set), the schedule
      is finished and we return ``None``.
    """
    if last_generated is None:
        candidate = start_date
    else:
        candidate = advance(
            from_date=last_generated, cadence=cadence, interval=interval,
        )
    if end_date is not None and candidate > end_date:
        return None
    return candidate


def is_due(*, next_due_date: date, today: date) -> bool:
    """True iff the template should mint an expense at ``today``."""
    return next_due_date <= today


def plan_occurrences(
    *,
    start_date: date,
    cadence: str,
    interval: int,
    end_date: date | None,
    count:   int,
) -> list[date]:
    """Return the first ``count`` due dates for a schedule.

    Mostly a debugging / preview helper for the UI; production
    scheduling uses :func:`compute_next_due` one step at a time.
    """
    if count < 0:
        raise ValueError("count must be >= 0")
    out: list[date] = []
    last: date | None = None
    for _ in range(count):
        nd = compute_next_due(
            start_date=start_date,
            cadence=cadence,
            interval=interval,
            last_generated=last,
            end_date=end_date,
        )
        if nd is None:
            break
        out.append(nd)
        last = nd
    return out
