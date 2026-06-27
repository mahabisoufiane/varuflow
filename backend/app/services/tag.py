"""Pure helpers for the tag manager (Item 60).

Router owns I/O; these helpers sanitise the inputs and own the
slug-generation rule so it's testable in isolation.
"""
from __future__ import annotations

import re
from typing import Iterable

# Keep in sync with :mod:`app.services.custom_field`. Tags attach to
# the same three entity types.
ALLOWED_ENTITY_TYPES: frozenset[str] = frozenset({"product", "customer", "invoice"})

MAX_NAME_LENGTH: int = 64
MAX_SLUG_LENGTH: int = 64
MIN_NAME_LENGTH: int = 1

_SLUG_SAFE = re.compile(r"[^a-z0-9]+")
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def slugify(name: str) -> str:
    """Lowercase, dash-separated, strip non-[a-z0-9]. Never returns ``""``.

    Raises :class:`ValueError` if ``name`` is blank or produces an
    empty slug (e.g. "!!!" after stripping).
    """
    if not name or not name.strip():
        raise ValueError("name must be non-empty")
    s = _SLUG_SAFE.sub("-", name.strip().lower()).strip("-")
    if not s:
        raise ValueError("name must contain letters or digits")
    if len(s) > MAX_SLUG_LENGTH:
        s = s[:MAX_SLUG_LENGTH].rstrip("-")
    return s


def normalise_name(raw: str | None) -> str:
    if raw is None:
        return ""
    return " ".join(raw.strip().split())


def validate_name(name: str) -> None:
    if not name or len(name) < MIN_NAME_LENGTH:
        raise ValueError("name too short")
    if len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"name too long ({MAX_NAME_LENGTH} chars max)")


def validate_color(color: str | None) -> str | None:
    if color is None or color == "":
        return None
    c = color.strip()
    if not _HEX_COLOR.match(c):
        raise ValueError("color must be 7-char hex (e.g. #1E90FF)")
    return c.lower()


def validate_entity_type(entity_type: str) -> None:
    if entity_type not in ALLOWED_ENTITY_TYPES:
        raise ValueError(
            f"entity_type must be one of {sorted(ALLOWED_ENTITY_TYPES)}"
        )


def dedupe_tag_ids(ids: Iterable) -> list:
    """Preserve first-occurrence order, drop repeats."""
    seen: set = set()
    out = []
    for i in ids:
        if i in seen:
            continue
        seen.add(i)
        out.append(i)
    return out
