"""Pure helpers for the purchase order activity timeline (Item 91).

Builds a unified chronological feed of audit events touching a
given purchase order, drawn from the append-only ``audit_log``.
No DB access here; the router pulls raw rows and feeds them to
:func:`build_timeline`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

MAX_PAGE_LIMIT: int = 200
DEFAULT_PAGE_LIMIT: int = 50

# Actions that directly target the purchase order (``target_id``
# carries the PO's UUID).
_PO_TARGETED_ACTIONS: frozenset[str] = frozenset({
    "purchase_order_tag.assigned",
    "purchase_order_tag.unassigned",
    "purchase_order.auto_created",
    "supplier_portal.po_confirmed",
})

# Actions whose ``target_id`` is a different entity (note) but whose
# ``extra`` dict carries the purchase-order id. The timeline joins on
# that.
_EXTRA_PO_ACTIONS: frozenset[str] = frozenset({
    "purchase_order_note.created",
    "purchase_order_note.updated",
    "purchase_order_note.deleted",
    "purchase_order_note.pinned",
    "purchase_order_note.unpinned",
})

# Human-readable categories the UI groups entries under. Mapping is
# prefix-based so we don't have to enumerate every action twice.
# Order matters — longer / more specific prefixes first so the
# ``purchase_order_*`` rows never fall through to ``purchase_order.``.
_CATEGORY_PREFIXES: tuple[tuple[str, str], ...] = (
    ("purchase_order_note.", "note"),
    ("purchase_order_tag.",  "tag"),
    ("supplier_portal.",     "supplier"),
    ("purchase_order.",      "purchase_order"),
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
    purchase_order_id: str
    total:             int   # number of matches (pre-pagination)
    entries:           list[TimelineEntry]


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
    return _PO_TARGETED_ACTIONS | _EXTRA_PO_ACTIONS


def matches_po(row: AuditRow, *, purchase_order_id: str) -> bool:
    """True iff ``row`` describes an event on ``purchase_order_id``."""
    if row.action in _PO_TARGETED_ACTIONS:
        if row.target_id is not None and row.target_id == purchase_order_id:
            return True
    if row.action in _EXTRA_PO_ACTIONS:
        extra = row.extra or {}
        pid = extra.get("purchase_order_id")
        if pid is not None and str(pid) == purchase_order_id:
            return True
    return False


def build_timeline(
    *,
    purchase_order_id: str,
    rows:              list[AuditRow],
    limit:             int | None = None,
    offset:            int | None = None,
) -> Timeline:
    """Filter + sort + paginate raw audit rows into a timeline."""
    limit_v, offset_v = normalize_page(limit=limit, offset=offset)

    filtered = [
        r for r in rows
        if matches_po(r, purchase_order_id=purchase_order_id)
    ]
    # Newest first; stable tiebreak on id so the feed is deterministic.
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
        purchase_order_id=purchase_order_id, total=total, entries=entries,
    )
