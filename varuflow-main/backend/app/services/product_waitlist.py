"""Pure helpers for the product back-in-stock waitlist (Item 56).

All DB work stays in the router; these helpers make the rules
testable without fixtures:

* :func:`normalise_email` — trim + lowercase.
* :func:`is_valid_email` — minimal check used before hitting the DB
  so we can reject obvious garbage with a 400 instead of a unique-key
  conflict.
* :func:`should_notify` — decides whether a single entry is ripe for
  a back-in-stock email (not yet notified, not cancelled, stock
  above the notify threshold).
* :func:`filter_pending` — list-level convenience over ``should_notify``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

# Default threshold — mirror the existing "low stock" notion. The
# router accepts a per-request override so an admin can force-notify
# even when only 1 unit comes in.
DEFAULT_NOTIFY_THRESHOLD: int = 1
MAX_NAME_LENGTH: int = 255
MAX_EMAIL_LENGTH: int = 320

# Deliberately permissive: the real validator is the MTA. We only
# reject strings that definitely can't be an email so they never reach
# the DB's UNIQUE index.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class WaitlistCandidate:
    """Subset of :class:`ProductWaitlistEntry` needed for notify logic."""
    entry_id:     str
    email:        str
    notified_at:  datetime | None
    cancelled_at: datetime | None


def normalise_email(raw: str | None) -> str:
    if raw is None:
        return ""
    return raw.strip().lower()


def is_valid_email(email: str) -> bool:
    if not email or len(email) > MAX_EMAIL_LENGTH:
        return False
    return bool(_EMAIL_RE.match(email))


def should_notify(candidate: WaitlistCandidate, *, current_stock: int,
                  threshold: int = DEFAULT_NOTIFY_THRESHOLD) -> bool:
    """True when ``candidate`` is ripe for a back-in-stock email."""
    if candidate.notified_at is not None:
        return False
    if candidate.cancelled_at is not None:
        return False
    if threshold < 1:
        # Guard against misconfiguration — never send on "0 or more".
        threshold = 1
    return current_stock >= threshold


def filter_pending(candidates: Iterable[WaitlistCandidate], *,
                   current_stock: int,
                   threshold: int = DEFAULT_NOTIFY_THRESHOLD,
                   ) -> list[WaitlistCandidate]:
    return [c for c in candidates
            if should_notify(c, current_stock=current_stock, threshold=threshold)]
