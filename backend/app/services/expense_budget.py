"""Pure helpers for expense budgets (Item 99).

Window math (period → start/end), alert-level classification,
cap/threshold/note/currency validators, and the ``assess`` helper
that turns a cap + a running total into a UI-friendly status.

No DB access; the router layer handles persistence and spend-rollup
SQL.
"""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

MIN_CAP: Decimal = Decimal("0.01")
MAX_CAP: Decimal = Decimal("9999999999.99")
MIN_THRESHOLD_PCT: int = 1
MAX_THRESHOLD_PCT: int = 100
MAX_NOTE: int = 2_000

PERIODS: tuple[str, ...] = ("MONTH", "QUARTER", "YEAR")

# Alert levels — keep the vocabulary tiny so the UI can map each to
# one colour.
LEVEL_OK:      str = "OK"
LEVEL_WARNING: str = "WARNING"
LEVEL_OVER:    str = "OVER"


# ── validators ─────────────────────────────────────────────────────────


def validate_period(raw: object) -> str:
    if not isinstance(raw, str):
        raise ValueError("period must be a string")
    s = raw.strip().upper()
    if s not in PERIODS:
        raise ValueError(f"period must be one of {', '.join(PERIODS)}")
    return s


def validate_cap(raw: object) -> Decimal:
    if isinstance(raw, bool):
        raise ValueError("amount_cap must be numeric")
    try:
        v = Decimal(str(raw))
    except Exception as e:  # noqa: BLE001
        raise ValueError("amount_cap must be numeric") from e
    if v < MIN_CAP:
        raise ValueError(f"amount_cap must be >= {MIN_CAP}")
    if v > MAX_CAP:
        raise ValueError(f"amount_cap must be <= {MAX_CAP}")
    return v.quantize(Decimal("0.01"))


def validate_threshold_pct(raw: object) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError("alert_threshold_pct must be an integer")
    if raw < MIN_THRESHOLD_PCT:
        raise ValueError(
            f"alert_threshold_pct must be >= {MIN_THRESHOLD_PCT}"
        )
    if raw > MAX_THRESHOLD_PCT:
        raise ValueError(
            f"alert_threshold_pct must be <= {MAX_THRESHOLD_PCT}"
        )
    return raw


def validate_currency(raw: object) -> str:
    if not isinstance(raw, str):
        raise ValueError("currency must be a string")
    s = raw.strip().upper()
    if len(s) != 3 or not s.isalpha():
        raise ValueError("currency must be a 3-letter ISO code")
    return s


def validate_note(raw: object | None) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError("note must be a string or None")
    s = raw.strip()
    if not s:
        return None
    if len(s) > MAX_NOTE:
        raise ValueError(f"note exceeds {MAX_NOTE} characters")
    return s


# ── window math ────────────────────────────────────────────────────────


def normalize_period_start(*, period: str, anchor: date) -> date:
    """Snap ``anchor`` back to the first day of its window.

    * MONTH:   first day of the month containing ``anchor``.
    * QUARTER: first day of the quarter (Jan/Apr/Jul/Oct).
    * YEAR:    January 1st of the anchor's year.
    """
    period = validate_period(period)
    if not isinstance(anchor, date):
        raise ValueError("anchor must be a date")
    if period == "MONTH":
        return date(anchor.year, anchor.month, 1)
    if period == "QUARTER":
        q_month = ((anchor.month - 1) // 3) * 3 + 1
        return date(anchor.year, q_month, 1)
    return date(anchor.year, 1, 1)


def period_end(*, period: str, period_start: date) -> date:
    """Return the inclusive last day of the window anchored at
    ``period_start`` (which must already be normalised).
    """
    period = validate_period(period)
    if not isinstance(period_start, date):
        raise ValueError("period_start must be a date")
    if period == "MONTH":
        last_dom = monthrange(period_start.year, period_start.month)[1]
        return date(period_start.year, period_start.month, last_dom)
    if period == "QUARTER":
        # Quarter = 3 months.
        end_month = period_start.month + 2
        year = period_start.year
        if end_month > 12:
            end_month -= 12
            year += 1
        last_dom = monthrange(year, end_month)[1]
        return date(year, end_month, last_dom)
    return date(period_start.year, 12, 31)


def contains(*, period: str, period_start: date, day: date) -> bool:
    """True iff ``day`` falls inside the window."""
    return period_start <= day <= period_end(
        period=period, period_start=period_start,
    )


# ── assessment ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BudgetAssessment:
    spent:          Decimal
    remaining:      Decimal
    pct_used:       int       # clamped to [0, 999] so the UI can't overflow
    level:          str       # OK / WARNING / OVER
    over_by:        Decimal   # zero when level != OVER


def assess(
    *,
    cap:           Decimal,
    spent:         Decimal,
    threshold_pct: int,
) -> BudgetAssessment:
    """Classify a running total against a cap.

    * ``spent >= cap``        → OVER  (over_by = spent - cap)
    * ``pct_used >= threshold`` → WARNING
    * otherwise               → OK

    ``pct_used`` is an integer percentage rounded **down** (floor) so
    99.99% of cap stays WARNING until the final cent tips it over.
    """
    if not isinstance(cap, Decimal) or not isinstance(spent, Decimal):
        raise ValueError("cap and spent must be Decimal")
    if cap <= 0:
        raise ValueError("cap must be positive")
    threshold_pct = validate_threshold_pct(threshold_pct)

    # Floor-percentage (avoid float rounding surprises).
    pct_raw = (spent * Decimal(100)) / cap
    pct = int(pct_raw)  # Decimal → int truncates toward zero
    if pct < 0:
        pct = 0
    pct_clamped = min(pct, 999)

    remaining = (cap - spent).quantize(Decimal("0.01"))
    if spent >= cap:
        return BudgetAssessment(
            spent=spent.quantize(Decimal("0.01")),
            remaining=remaining,
            pct_used=pct_clamped,
            level=LEVEL_OVER,
            over_by=(spent - cap).quantize(Decimal("0.01")),
        )
    level = LEVEL_WARNING if pct >= threshold_pct else LEVEL_OK
    return BudgetAssessment(
        spent=spent.quantize(Decimal("0.01")),
        remaining=remaining,
        pct_used=pct_clamped,
        level=level,
        over_by=Decimal("0.00"),
    )
