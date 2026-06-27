"""Pure helpers for POS quick-sale buttons (Item 65).

Validation rules for the create/update flow plus a pure reorder
function that returns the new ``(id, position)`` pairs a router can
persist in a single transaction.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Iterable

MAX_BUTTONS_PER_ORG: int = 48
MAX_LABEL_LENGTH: int = 40
MIN_QUANTITY: Decimal = Decimal("0.001")
MAX_QUANTITY: Decimal = Decimal("9999.999")

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def validate_label(label: str) -> str:
    if not isinstance(label, str):
        raise ValueError("label must be a string")
    s = " ".join(label.strip().split())
    if not s:
        raise ValueError("label is required")
    if len(s) > MAX_LABEL_LENGTH:
        raise ValueError(f"label too long ({MAX_LABEL_LENGTH} chars max)")
    return s


def validate_color(color: str | None) -> str | None:
    if color is None or color == "":
        return None
    if not isinstance(color, str) or not _HEX_RE.match(color):
        raise ValueError("color must be 7-char hex like '#1E90FF'")
    return color.lower()


def validate_quantity(qty) -> Decimal:
    if isinstance(qty, bool):
        raise ValueError("quantity must be a number")
    try:
        q = qty if isinstance(qty, Decimal) else Decimal(str(qty))
    except Exception:
        raise ValueError("quantity must be a number")
    if q < MIN_QUANTITY or q > MAX_QUANTITY:
        raise ValueError(
            f"quantity must be between {MIN_QUANTITY} and {MAX_QUANTITY}"
        )
    return q


def reorder(
    existing_ids: Iterable[str], new_order: list[str]
) -> list[tuple[str, int]]:
    """Return ``[(id, position), ...]`` reflecting ``new_order``.

    ``existing_ids`` and ``new_order`` must contain the same ids;
    missing / extra / duplicate ids raise ``ValueError``. Positions
    are 1-indexed in the returned list.
    """
    existing = list(existing_ids)
    if len(new_order) != len(existing):
        raise ValueError("new_order length mismatch")
    if len(set(new_order)) != len(new_order):
        raise ValueError("new_order contains duplicates")
    if set(new_order) != set(existing):
        raise ValueError("new_order must contain exactly the existing ids")
    return [(bid, idx + 1) for idx, bid in enumerate(new_order)]


def next_position(existing_positions: Iterable[int]) -> int:
    """Position for a freshly appended button."""
    positions = list(existing_positions)
    if not positions:
        return 1
    return max(positions) + 1


def assert_capacity(current_count: int) -> None:
    if current_count >= MAX_BUTTONS_PER_ORG:
        raise ValueError(
            f"quick-button grid full ({MAX_BUTTONS_PER_ORG} max)"
        )
