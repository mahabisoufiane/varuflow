"""Booking engine — slot computation, prayer-time blocking, waitlist.

All logic here is pure functional against materialised lists of
windows; database reads happen in narrow loader helpers at the top.
This split keeps the scheduling math unit-testable without Postgres.

MENA-specific pieces
--------------------
* ``prayer_times_to_windows`` turns the org's ``booking_prayer_times``
  JSONB array into concrete ``(start, end)`` datetime windows for the
  requested day. The times are stored as ``"HH:MM"`` strings and are
  interpreted in the org's local timezone — we use Europe/Stockholm as
  a temporary default until the per-org timezone column lands in a
  later item. A production MENA deployment will override via the env
  var ``BOOKING_DEFAULT_TZ``.
* ``female_only_staff_filter`` drops any staff row whose ``gender``
  is not ``"female"`` when the org flag is on. NULL gender is treated
  as *unspecified* and also dropped, so a mis-configured staff row
  fails closed (hidden) rather than leaking into a female-only salon.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Iterable


_DEFAULT_TZ = os.getenv("BOOKING_DEFAULT_TZ", "Europe/Stockholm")

# Slot grid granularity in minutes. 15-min grid is the MENA salon norm
# (matches Fresha/Booksy defaults); shorter grids explode combinatorics
# for multi-staff availability grids with no real UX benefit.
SLOT_GRID_MINUTES = 15


# ── Data classes ────────────────────────────────────────────────────


@dataclass(frozen=True)
class TimeWindow:
    """A half-open ``[start, end)`` datetime window."""

    start: datetime
    end: datetime

    def overlaps(self, other: "TimeWindow") -> bool:
        return self.start < other.end and other.start < self.end


# ── Working-hours / break parsing ──────────────────────────────────


_WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _parse_hhmm(raw: str) -> time:
    """Parse ``"HH:MM"`` or ``"HH:MM:SS"`` into a ``datetime.time``."""
    parts = raw.strip().split(":")
    hh = int(parts[0])
    mm = int(parts[1]) if len(parts) > 1 else 0
    ss = int(parts[2]) if len(parts) > 2 else 0
    return time(hour=hh, minute=mm, second=ss)


def working_hours_for_day(
    working_hours: dict | None, day: datetime
) -> list[TimeWindow]:
    """Return the staff's working windows for ``day`` (00:00 local).

    Empty/None working_hours returns an empty list → staff treated as
    off that day, which is the conservative default (no slots shown).
    """
    if not working_hours:
        return []
    key = _WEEKDAY_KEYS[day.weekday()]
    entries = working_hours.get(key) or []
    out: list[TimeWindow] = []
    for entry in entries:
        try:
            start = _parse_hhmm(entry["start"])
            end = _parse_hhmm(entry["end"])
        except (KeyError, TypeError, ValueError):
            # Malformed row → skip rather than 500 the booking page
            continue
        out.append(
            TimeWindow(
                start=_attach_time(day, start),
                end=_attach_time(day, end),
            )
        )
    return out


def break_windows_for_day(
    break_times: list | None, day: datetime
) -> list[TimeWindow]:
    if not break_times:
        return []
    out: list[TimeWindow] = []
    for entry in break_times:
        try:
            start = _parse_hhmm(entry["start"])
            end = _parse_hhmm(entry["end"])
        except (KeyError, TypeError, ValueError):
            continue
        out.append(
            TimeWindow(
                start=_attach_time(day, start),
                end=_attach_time(day, end),
            )
        )
    return out


def prayer_times_to_windows(
    prayer_times: list | None, day: datetime
) -> list[TimeWindow]:
    """Turn org's prayer schedule into blocked windows for ``day``.

    Each entry is ``{"name": "Dhuhr", "start": "12:15",
    "duration_minutes": 20}``. The ``duration_minutes`` gives us a
    concrete end time without a second clock lookup per day.
    """
    if not prayer_times:
        return []
    out: list[TimeWindow] = []
    for entry in prayer_times:
        try:
            start_t = _parse_hhmm(entry["start"])
            duration = int(entry.get("duration_minutes", 15))
        except (KeyError, TypeError, ValueError):
            continue
        start_dt = _attach_time(day, start_t)
        end_dt = start_dt + timedelta(minutes=max(1, duration))
        out.append(TimeWindow(start=start_dt, end=end_dt))
    return out


def _attach_time(day: datetime, t: time) -> datetime:
    """Compose a tz-aware datetime from a naive day + time-of-day.

    The day's tzinfo is preserved; naive days default to UTC. Callers
    that need org-local times should pass a tz-aware ``day``.
    """
    tz = day.tzinfo or timezone.utc
    return datetime(
        year=day.year,
        month=day.month,
        day=day.day,
        hour=t.hour,
        minute=t.minute,
        second=t.second,
        tzinfo=tz,
    )


# ── Slot availability ──────────────────────────────────────────────


def subtract_windows(
    base: list[TimeWindow], blockers: Iterable[TimeWindow]
) -> list[TimeWindow]:
    """Return ``base`` minus every ``blocker`` overlap.

    Pure function; no I/O, no mutation. O(n·m) which is fine for the
    n<10, m<30 scale a single salon day produces.
    """
    result = list(base)
    for block in blockers:
        next_result: list[TimeWindow] = []
        for win in result:
            if not win.overlaps(block):
                next_result.append(win)
                continue
            # Left chunk
            if win.start < block.start:
                next_result.append(TimeWindow(start=win.start, end=block.start))
            # Right chunk
            if block.end < win.end:
                next_result.append(TimeWindow(start=block.end, end=win.end))
        result = next_result
    return result


def fits_slots(
    windows: list[TimeWindow], duration_minutes: int, grid_minutes: int = SLOT_GRID_MINUTES
) -> list[datetime]:
    """Enumerate every valid start time whose slot fits in ``windows``.

    Starts are aligned to the wall-clock grid — e.g. a 15-min grid
    produces :00/:15/:30/:45 starts regardless of where the free window
    begins. Aligning to the wall clock (not the window start) matches
    MENA salon UIs (Fresha/Booksy/Zenoti) and means a prayer window at
    12:15–12:35 still produces a 12:45 start, not 12:35.

    A slot is valid iff ``[start, start+duration]`` is fully inside the
    free window — partial overhang is never returned.
    """
    duration = timedelta(minutes=duration_minutes)
    grid = timedelta(minutes=grid_minutes)
    grid_seconds = grid.total_seconds()
    out: list[datetime] = []
    for win in windows:
        # Ceiling-align the cursor to the wall-clock grid. Using seconds
        # from epoch sidesteps DST edge cases — we want arithmetic grid
        # alignment, not calendar alignment.
        epoch_secs = win.start.timestamp()
        aligned_secs = -(-epoch_secs // grid_seconds) * grid_seconds
        cursor = datetime.fromtimestamp(aligned_secs, tz=win.start.tzinfo or timezone.utc)
        while cursor + duration <= win.end:
            out.append(cursor)
            cursor = cursor + grid
    return out


def compute_available_slots(
    day: datetime,
    *,
    duration_minutes: int,
    working_hours: dict | None,
    break_times: list | None,
    prayer_times: list | None,
    existing_appointments: Iterable[TimeWindow],
    prayer_blocking_enabled: bool,
) -> list[datetime]:
    """Top-level slot computation for a single staff on a single day.

    Pipeline:
        1. staff's working windows for that weekday
        2. minus break times
        3. minus prayer windows (if org flag set)
        4. minus existing non-cancelled appointments
        5. grid-align + enumerate starts that fit ``duration_minutes``
    """
    base = working_hours_for_day(working_hours, day)
    blockers: list[TimeWindow] = list(break_windows_for_day(break_times, day))
    if prayer_blocking_enabled:
        blockers.extend(prayer_times_to_windows(prayer_times, day))
    blockers.extend(existing_appointments)
    free = subtract_windows(base, blockers)
    return fits_slots(free, duration_minutes)


# ── Gender filter for female-only mode ─────────────────────────────


def female_only_staff_filter(staff_rows: Iterable, *, enabled: bool):
    """Filter a staff iterable when female-only mode is on.

    Rows with ``gender != "female"`` (including NULL) are dropped. This
    is a fail-closed filter — a mis-configured staff record stays hidden
    rather than leaking into a female-only salon's booking UI.
    """
    if not enabled:
        return list(staff_rows)
    return [s for s in staff_rows if getattr(s, "gender", None) == "female"]


# ── Loyalty points ─────────────────────────────────────────────────


def loyalty_points_for_appointment(price) -> int:
    """Compute loyalty points awarded on completion.

    Formula: ``floor(price)`` → 1 point per unit of currency. This is
    intentionally simple; a future item can introduce tier multipliers
    and redemption ledgering. Keeping the formula in one place lets
    the service layer and the test suite stay in sync.
    """
    try:
        value = float(price or 0)
    except (TypeError, ValueError):
        return 0
    if value <= 0:
        return 0
    return int(value)


# ── Waitlist ───────────────────────────────────────────────────────


def pick_waitlist_candidate(appointments: Iterable) -> "Appointment | None":
    """Return the oldest-created waitlisted appointment, or None.

    Purely order-based today; a future item can add priority tiers
    (VIP, membership) without changing the call sites.
    """
    oldest = None
    for appt in appointments:
        if getattr(appt, "status", None) != "waitlisted":
            continue
        if oldest is None or appt.created_at < oldest.created_at:
            oldest = appt
    return oldest
