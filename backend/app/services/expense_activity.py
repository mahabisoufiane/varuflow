"""Pure helpers for the expense activity timeline (Item 96).

Builds a unified chronological feed of audit events touching a
given expense, drawn from the append-only ``audit_log``. No DB
access here; the router pulls raw rows and feeds them to
:func:`build_timeline`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

MAX_PAGE_LIMIT: int = 200
DEFAULT_PAGE_LIMIT: int = 50

# Actions that directly target the expense (``target_id`` carries
# the expense's UUID).
_EXPENSE_TARGETED_ACTIONS: frozenset[str] = frozenset({
    "expense.created",
    "expense.updated",
    "expense.deleted",
    "expense.submitted",
    "expense.approved",
    "expense.rejected",
    "expense.paid",
    "expense_tag.assigned",
    "expense_tag.unassigned",
})

# Actions whose ``target_id`` is a different entity (note, …) but
# whose ``extra`` dict carries the expense id.
_EXTRA_EXPENSE_ACTIONS: frozenset[str] = frozenset({
    "expense_note.created",
    "expense_note.updated",
    "expense_note.deleted",
    "expense_note.pinned",
    "expense_note.unpinned",
})

# Human-readable categories the UI groups entries under.
_CATEGORY_PREFIXES: tuple[tuple[str, str], ...] = (
    ("expense_note.",  "note"),
    ("expense_tag.",   "tag"),
    ("expense.",       "expense"),
)


@dataclass(frozen=True)
class AuditRow:
    """Minimal shape the router hands to :func:`build_timeline`."""
    id:            str
    action:        str
    actor_user_id: str | None
    target_type:   str | None
    target_id:     str | None
    extra:         dict | None
    created_at:    datetime


@dataclass(frozen=True)
class TimelineEntry:
    id:            str
    action:        str
    category:      str
    actor_user_id: str | None
    target_type:   str | None
    target_id:     str | None
    extra:         dict
    created_at:    datetime


@dataclass(frozen=True)
class Timeline:
    expense_id: str
    total:      int   # number of matches (pre-pagination)
    entries:    list[TimelineEntry]


def normalize_page(*, limit: int | None, offset: int | None) -> tuple[int, int]:
    """Clamp pagination to sane bounds."""
    if limit is None:
        limit_v = DEFAULT_PAGE_LIMIT
    else:
        if not isinstance(limit, int):
            raise ValueError("limit must be an integer")
        if limit < 1:
            raise ValueError("limit must be >= 1")
        limit_v = min(limit, MAX_PAGE_LIMIT)

    if offset is None:
        offset_v = 0
    else:
        if not isinstance(offset, int):
            raise ValueError("offset must be an integer")
        if offset < 0:
            raise ValueError("offset must be >= 0")
        offset_v = offset

    return limit_v, offset_v


def categorize(action: str) -> str:
    for prefix, cat in _CATEGORY_PREFIXES:
        if action.startswith(prefix):
            return cat
    return "other"


def known_actions() -> frozenset[str]:
    """Every action name the timeline recognises."""
    return _EXPENSE_TARGETED_ACTIONS | _EXTRA_EXPENSE_ACTIONS


def matches_expense(row: AuditRow, *, expense_id: str) -> bool:
    """True iff ``row`` describes an event on ``expense_id``."""
    if row.action in _EXPENSE_TARGETED_ACTIONS:
        if row.target_id is not None and row.target_id == expense_id:
            return True
    if row.action in _EXTRA_EXPENSE_ACTIONS:
        extra = row.extra or {}
        eid = extra.get("expense_id")
        if eid is not None and str(eid) == expense_id:
            return True
    return False


def build_timeline(
    *,
    expense_id: str,
    rows:       list[AuditRow],
    limit:      int | None = None,
    offset:     int | None = None,
) -> Timeline:
    """Filter + sort + paginate raw audit rows into a timeline."""
    limit_v, offset_v = normalize_page(limit=limit, offset=offset)

    filtered = [r for r in rows if matches_expense(r, expense_id=expense_id)]
    filtered.sort(key=lambda r: (r.created_at, r.id), reverse=True)

    total = len(filtered)
    window = filtered[offset_v : offset_v + limit_v]

    entries = [
        TimelineEntry(
            id=r.id,
            action=r.action,
            category=categorize(r.action),
            actor_user_id=r.actor_user_id,
            target_type=r.target_type,
            target_id=r.target_id,
            extra=(r.extra or {}),
            created_at=r.created_at,
        )
        for r in window
    ]
    return Timeline(
        expense_id=expense_id, total=total, entries=entries,
    )
