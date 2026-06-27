"""Pure helpers for shift management and payroll (Item 67).

Covers:
* shift validation (start < end, reasonable duration),
* overlap detection across a staff member's shifts,
* punch arithmetic (open punch, close punch, round to 15 minutes),
* payroll aggregation (sum of hours per staff for a period, optional
  CSV rendering).
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

MIN_SHIFT_MINUTES: int = 15
MAX_SHIFT_MINUTES: int = 16 * 60  # 16 hours
MAX_NOTE_LENGTH:   int = 500
ROUND_TO_MINUTES:  int = 15

_Q2 = Decimal("0.01")
_Q4 = Decimal("0.0001")


@dataclass(frozen=True)
class ShiftSpan:
    id:       str
    staff_id: str
    start:    datetime
    end:      datetime


@dataclass(frozen=True)
class PunchPair:
    clock_in:  datetime
    clock_out: datetime | None


@dataclass(frozen=True)
class PayrollRow:
    staff_id:     str
    hours:        Decimal
    hourly_rate:  Decimal | None
    gross_amount: Decimal | None


# ── Shift validation ──────────────────────────────────────────────────────


def _require_utc(dt: datetime, *, field: str) -> datetime:
    if not isinstance(dt, datetime):
        raise ValueError(f"{field} must be a datetime")
    if dt.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    return dt.astimezone(timezone.utc)


def validate_shift_bounds(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    s = _require_utc(start, field="start_at")
    e = _require_utc(end, field="end_at")
    if e <= s:
        raise ValueError("end_at must be after start_at")
    minutes = (e - s).total_seconds() / 60
    if minutes < MIN_SHIFT_MINUTES:
        raise ValueError(f"shift must be at least {MIN_SHIFT_MINUTES} minutes")
    if minutes > MAX_SHIFT_MINUTES:
        raise ValueError(
            f"shift cannot exceed {MAX_SHIFT_MINUTES} minutes "
            f"({MAX_SHIFT_MINUTES // 60} hours)"
        )
    return s, e


def validate_notes(notes: str | None) -> str | None:
    if notes is None:
        return None
    if not isinstance(notes, str):
        raise ValueError("notes must be a string")
    if len(notes) > MAX_NOTE_LENGTH:
        raise ValueError(f"notes too long ({MAX_NOTE_LENGTH} chars max)")
    return notes


def validate_hourly_rate(rate) -> Decimal | None:
    if rate is None:
        return None
    if isinstance(rate, bool):
        raise ValueError("hourly_rate must be a number")
    try:
        r = rate if isinstance(rate, Decimal) else Decimal(str(rate))
    except Exception:
        raise ValueError("hourly_rate must be a number")
    if r <= 0:
        raise ValueError("hourly_rate must be positive")
    if r > Decimal("100000"):
        raise ValueError("hourly_rate exceeds 100000")
    return r


# ── Overlap detection ─────────────────────────────────────────────────────


def detect_overlap(
    candidate: ShiftSpan,
    existing: Iterable[ShiftSpan],
) -> ShiftSpan | None:
    """Return the first existing shift that overlaps ``candidate``.

    Two shifts overlap iff ``start_a < end_b`` AND ``start_b < end_a``.
    Touching shifts (``end_a == start_b``) are allowed.
    """
    for other in existing:
        if other.id == candidate.id:
            continue
        if other.staff_id != candidate.staff_id:
            continue
        if candidate.start < other.end and other.start < candidate.end:
            return other
    return None


# ── Punch arithmetic ──────────────────────────────────────────────────────


def round_to_quarter(dt: datetime) -> datetime:
    """Round to the nearest 15-minute boundary, HALF_UP."""
    dt = _require_utc(dt, field="dt")
    minutes = dt.minute
    q, rem = divmod(minutes, ROUND_TO_MINUTES)
    if rem == 0:
        base_minute = minutes
    elif rem >= ROUND_TO_MINUTES // 2 + (ROUND_TO_MINUTES % 2):
        base_minute = (q + 1) * ROUND_TO_MINUTES
    else:
        base_minute = q * ROUND_TO_MINUTES
    # base_minute may be 60 → roll forward.
    if base_minute == 60:
        return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return dt.replace(minute=base_minute, second=0, microsecond=0)


def hours_between(start: datetime, end: datetime) -> Decimal:
    s = _require_utc(start, field="start")
    e = _require_utc(end, field="end")
    if e <= s:
        return Decimal("0")
    seconds = Decimal(str((e - s).total_seconds()))
    hours = (seconds / Decimal("3600")).quantize(_Q4, rounding=ROUND_HALF_UP)
    return hours


def open_punch(
    *, existing_open: int, shift_has_ended: bool
) -> None:
    """Validate a clock-in attempt. Raises on rule violations."""
    if existing_open > 0:
        raise ValueError("there is already an open punch for this shift")
    if shift_has_ended:
        raise ValueError("cannot clock in after the shift has ended")


def close_punch(clock_in: datetime, clock_out: datetime) -> Decimal:
    """Validate and close a punch pair; returns the billable hours."""
    s = _require_utc(clock_in, field="clock_in")
    e = _require_utc(clock_out, field="clock_out")
    if e <= s:
        raise ValueError("clock_out must be after clock_in")
    return hours_between(s, e)


# ── Payroll aggregation ───────────────────────────────────────────────────


def aggregate_payroll(
    punches: Iterable[tuple[str, datetime, datetime | None, Decimal | None]],
    *,
    period_start: datetime,
    period_end:   datetime,
) -> list[PayrollRow]:
    """Aggregate punches into per-staff hours for a period.

    Each tuple is ``(staff_id, clock_in, clock_out, hourly_rate)``.
    Unclosed punches are ignored. The intersection of the punch with
    ``[period_start, period_end)`` is what counts — a punch starting
    before the period contributes only the in-period slice.
    """
    ps = _require_utc(period_start, field="period_start")
    pe = _require_utc(period_end, field="period_end")
    if pe <= ps:
        raise ValueError("period_end must be after period_start")

    totals: dict[str, Decimal] = {}
    rate_for: dict[str, Decimal | None] = {}
    for staff_id, ci, co, rate in punches:
        if co is None:
            continue
        ci_u = _require_utc(ci, field="clock_in")
        co_u = _require_utc(co, field="clock_out")
        lo = max(ci_u, ps)
        hi = min(co_u, pe)
        if hi <= lo:
            continue
        h = hours_between(lo, hi)
        totals[staff_id] = totals.get(staff_id, Decimal("0")) + h
        # Keep the latest-seen rate for the staff (simplest reasonable
        # default for fixed-rate orgs; mixed-rate callers should split
        # the input before aggregating).
        if rate is not None:
            rate_for[staff_id] = rate
        elif staff_id not in rate_for:
            rate_for[staff_id] = None

    out: list[PayrollRow] = []
    for sid in sorted(totals.keys()):
        hours = totals[sid].quantize(_Q4, rounding=ROUND_HALF_UP)
        rate = rate_for.get(sid)
        gross: Decimal | None
        if rate is None:
            gross = None
        else:
            gross = (rate * hours).quantize(_Q2, rounding=ROUND_HALF_UP)
        out.append(
            PayrollRow(
                staff_id=sid, hours=hours, hourly_rate=rate, gross_amount=gross
            )
        )
    return out


def render_payroll_csv(rows: list[PayrollRow]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["staff_id", "hours", "hourly_rate", "gross_amount"])
    for r in rows:
        w.writerow([
            r.staff_id,
            f"{r.hours:.4f}",
            "" if r.hourly_rate is None else f"{r.hourly_rate:.2f}",
            "" if r.gross_amount is None else f"{r.gross_amount:.2f}",
        ])
    return buf.getvalue()
