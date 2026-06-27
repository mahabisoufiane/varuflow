"""Pure helpers for the product activity timeline (Item 82).

Builds a unified chronological feed of audit events touching a
given product, drawn from the append-only ``audit_log``. No DB
access here; the router pulls raw rows and feeds them to
:func:`build_timeline`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

MAX_PAGE_LIMIT: int = 200
DEFAULT_PAGE_LIMIT: int = 50

# Actions that directly target the product (``target_id`` carries
# the product's UUID).
_PRODUCT_TARGETED_ACTIONS: frozenset[str] = frozenset({
    "product.created",
    "product.updated",
    "product.deleted",
    "product_tag.assigned",
    "product_tag.unassigned",
})

# Actions whose ``target_id`` is a different entity (note, batch,
# stock movement, …) but whose ``extra`` dict carries the product
# id. The timeline joins on that.
_EXTRA_PRODUCT_ACTIONS: frozenset[str] = frozenset({
    "product_note.created",
    "product_note.updated",
    "product_note.deleted",
    "product_note.pinned",
    "product_note.unpinned",
    "stock_movement.recorded",
    "product_batch.created",
    "product_batch.updated",
    "product_batch.expired",
    "purchase_order_item.received",
    "pos_sale_item.sold",
    "invoice_line.invoiced",
})

# Human-readable categories the UI groups entries under. Mapping is
# prefix-based so we don't have to enumerate every action twice.
_CATEGORY_PREFIXES: tuple[tuple[str, str], ...] = (
    ("product_note.",          "note"),
    ("product_tag.",           "tag"),
    ("product_batch.",         "batch"),
    ("stock_movement.",        "stock"),
    ("purchase_order_item.",   "purchase_order"),
    ("pos_sale_item.",         "pos"),
    ("invoice_line.",          "invoice"),
    ("product.",               "product"),
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
    product_id: str
    total:      int   # number of matches (pre-pagination)
    entries:    list[TimelineEntry]


def normalize_page(*, limit: int | None, offset: int | None) -> tuple[int, int]:
    """Clamp pagination to sane bounds.

    ``limit`` defaults to :data:`DEFAULT_PAGE_LIMIT`, caps at
    :data:`MAX_PAGE_LIMIT`. ``offset`` is non-negative.
    """
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
    return _PRODUCT_TARGETED_ACTIONS | _EXTRA_PRODUCT_ACTIONS


def matches_product(row: AuditRow, *, product_id: str) -> bool:
    """True iff ``row`` describes an event on ``product_id``."""
    if row.action in _PRODUCT_TARGETED_ACTIONS:
        if row.target_id is not None and row.target_id == product_id:
            return True
    if row.action in _EXTRA_PRODUCT_ACTIONS:
        extra = row.extra or {}
        pid = extra.get("product_id")
        if pid is not None and str(pid) == product_id:
            return True
    return False


def build_timeline(
    *,
    product_id: str,
    rows:       list[AuditRow],
    limit:      int | None = None,
    offset:     int | None = None,
) -> Timeline:
    """Filter + sort + paginate raw audit rows into a timeline."""
    limit_v, offset_v = normalize_page(limit=limit, offset=offset)

    filtered = [r for r in rows if matches_product(r, product_id=product_id)]
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
        product_id=product_id, total=total, entries=entries,
    )
