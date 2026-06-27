"""Pure helpers for staff availability (Item 57).

A staff member's availability on any given day is:

    baseline weekly window
      minus ``time_off`` / ``sick`` / ``holiday`` overrides
      plus  ``extra_shift`` overrides

This module works on simple ``(start, end)`` datetime tuples so every
rule is unit-testable without a booking-row fixture. The router
hands it the baseline window and the list of override rows for the
day, and gets back the final list of bookable intervals.

All intervals are half-open: ``[start, end)``. Zero-length windows
are dropped. The output is sorted and non-overlapping.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Iterable

# Kinds that subtract from availability vs. add to it. Keep in sync
# with :class:`app.models.staff_availability.StaffAvailabilityKind`.
BLOCKING_KINDS: frozenset[str] = frozenset({"time_off", "sick", "holiday"})
ADDITIVE_KINDS: frozenset[str] = frozenset({"extra_shift"})


@dataclass(frozen=True)
class Interval:
    start: datetime
    end:   datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError("Interval end must be after start")

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    def overlaps(self, other: "Interval") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class Override:
    kind:  str
    start: datetime
    end:   datetime


def parse_hhmm(value: str) -> time:
    """Parse ``"HH:MM"`` (24-hour) into a :class:`datetime.time`."""
    hh, mm = value.split(":", 1)
    return time(int(hh), int(mm))


def window_from_day(day: datetime, start_hhmm: str, end_hhmm: str) -> Interval:
    """Build an :class:`Interval` anchored at ``day``'s date."""
    date = day.date()
    s = datetime.combine(date, parse_hhmm(start_hhmm), tzinfo=day.tzinfo)
    e = datetime.combine(date, parse_hhmm(end_hhmm), tzinfo=day.tzinfo)
    return Interval(s, e)


def subtract_interval(base: Interval, cut: Interval) -> list[Interval]:
    """Return ``base`` minus ``cut`` — 0, 1, or 2 resulting intervals."""
    if not base.overlaps(cut):
        return [base]
    # Fully consumed
    if cut.start <= base.start and cut.end >= base.end:
        return []
    out: list[Interval] = []
    if cut.start > base.start:
        out.append(Interval(base.start, min(cut.start, base.end)))
    if cut.end < base.end:
        out.append(Interval(max(cut.end, base.start), base.end))
    return out


def merge_intervals(intervals: Iterable[Interval]) -> list[Interval]:
    """Sort + merge overlapping intervals. Empty input → ``[]``."""
    ivs = sorted(intervals, key=lambda i: (i.start, i.end))
    merged: list[Interval] = []
    for iv in ivs:
        if merged and iv.start <= merged[-1].end:
            last = merged[-1]
            merged[-1] = Interval(last.start, max(last.end, iv.end))
        else:
            merged.append(iv)
    return merged


def apply_overrides(baseline: Iterable[Interval],
                    overrides: Iterable[Override],
                    ) -> list[Interval]:
    """Apply override rows to a list of baseline intervals."""
    blockers = [Override(o.kind, o.start, o.end) for o in overrides if o.kind in BLOCKING_KINDS]
    extras = [Override(o.kind, o.start, o.end) for o in overrides if o.kind in ADDITIVE_KINDS]

    result = list(baseline)
    for b in blockers:
        cut = Interval(b.start, b.end)
        next_result: list[Interval] = []
        for iv in result:
            next_result.extend(subtract_interval(iv, cut))
        result = next_result

    # Add extra shifts and merge so the caller gets a clean list.
    merged_input = list(result) + [Interval(e.start, e.end) for e in extras]
    return merge_intervals(merged_input)


def is_available(target: Interval, availability: Iterable[Interval]) -> bool:
    """True when ``target`` is fully covered by ``availability``."""
    for iv in availability:
        if iv.start <= target.start and iv.end >= target.end:
            return True
    return False


def total_duration(intervals: Iterable[Interval]) -> timedelta:
    """Sum the duration of a list of non-overlapping intervals."""
    return sum((i.duration for i in intervals), timedelta())
