"""Pure helpers for supplier tags (Item 77).

Tag names normalize whitespace and cap at 32 chars; colors are
validated as 7-char hex (``#RRGGBB``) and lower-cased.
"""
from __future__ import annotations

import re

MAX_TAGS_PER_SUPPLIER: int = 20
MAX_NAME_LEN: int = 32
MIN_NAME_LEN: int = 1

_HEX6 = re.compile(r"^#[0-9a-fA-F]{6}$")
# Reasonable printable range; we collapse inner whitespace and strip.
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def normalize_name(raw: object) -> str:
    """Trim, collapse whitespace, reject controls/empty/too-long."""
    if not isinstance(raw, str):
        raise ValueError("tag name must be a string")
    if _CONTROL.search(raw):
        raise ValueError("tag name contains control characters")
    # Collapse internal whitespace to single spaces so "  Preferred  "
    # and "Preferred" produce the same canonical name.
    cleaned = " ".join(raw.split())
    if len(cleaned) < MIN_NAME_LEN:
        raise ValueError("tag name must not be empty")
    if len(cleaned) > MAX_NAME_LEN:
        raise ValueError(
            f"tag name exceeds {MAX_NAME_LEN} characters"
        )
    return cleaned


def normalize_color(raw: object) -> str:
    """Return a lower-case ``#rrggbb`` string or raise."""
    if not isinstance(raw, str):
        raise ValueError("color must be a string")
    candidate = raw.strip()
    if not _HEX6.match(candidate):
        raise ValueError(
            "color must be a 7-character hex string like '#2d6a4f'"
        )
    return candidate.lower()


def keys_equal(a: str, b: str) -> bool:
    """Case-insensitive equality check used for uniqueness checks."""
    return normalize_name(a).casefold() == normalize_name(b).casefold()


def assert_under_limit(*, current_count: int) -> None:
    if current_count < 0:
        raise ValueError("current_count cannot be negative")
    if current_count >= MAX_TAGS_PER_SUPPLIER:
        raise ValueError(
            f"supplier already has {MAX_TAGS_PER_SUPPLIER} tags "
            "(limit reached)"
        )
