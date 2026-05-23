"""Pure helpers for custom fields (Item 59).

The router owns I/O; these helpers normalise + validate the payloads
and cast raw DB strings into Python types on read.

Five supported field types:

* ``text``    — free text, length-capped.
* ``number``  — integer or decimal, stored as the canonical string.
* ``boolean`` — serialises as ``"true"`` / ``"false"``.
* ``date``    — ISO-8601 ``YYYY-MM-DD``.
* ``select``  — value must be one of ``definition.options``.

Validation is defensive against bad operator input: a misconfigured
``select`` definition with no options rejects every value, and
``number`` rejects NaN / Infinity so analytics can't choke on a bad
row later.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

ALLOWED_ENTITY_TYPES: frozenset[str] = frozenset({"product", "customer", "invoice"})
ALLOWED_FIELD_TYPES: frozenset[str] = frozenset({
    "text", "number", "boolean", "date", "select",
})

MAX_NAME_LENGTH: int = 64
MAX_LABEL_LENGTH: int = 128
MAX_TEXT_VALUE_LENGTH: int = 2000

# Snake-case, starts with letter, 2–64 chars. Keeps queries on
# ``name`` safe when logged and predictable for search indexing.
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


@dataclass(frozen=True)
class DefinitionInput:
    """Subset of :class:`CustomFieldDefinition` used by :func:`validate_definition`."""
    entity_type:   str
    name:          str
    label:         str
    field_type:    str
    is_required:   bool
    options:       list[str] | None


def normalise_name(raw: str | None) -> str:
    if raw is None:
        return ""
    return raw.strip().lower()


def validate_definition(d: DefinitionInput) -> None:
    """Raise ``ValueError`` if the definition is malformed."""
    if d.entity_type not in ALLOWED_ENTITY_TYPES:
        raise ValueError(
            f"entity_type must be one of {sorted(ALLOWED_ENTITY_TYPES)}"
        )
    if d.field_type not in ALLOWED_FIELD_TYPES:
        raise ValueError(
            f"field_type must be one of {sorted(ALLOWED_FIELD_TYPES)}"
        )
    name = d.name or ""
    if not _NAME_RE.match(name):
        raise ValueError(
            "name must be snake_case, start with a letter, 2-64 chars"
        )
    if not d.label or len(d.label) > MAX_LABEL_LENGTH:
        raise ValueError(f"label must be 1..{MAX_LABEL_LENGTH} chars")

    if d.field_type == "select":
        if not d.options or not isinstance(d.options, list):
            raise ValueError("select field requires a non-empty options list")
        if any(not isinstance(o, str) or not o for o in d.options):
            raise ValueError("select options must all be non-empty strings")
        if len(set(d.options)) != len(d.options):
            raise ValueError("select options must be unique")
    elif d.options:
        # Options on a non-select field are silently dropped by the
        # router, but flag it so the operator notices.
        raise ValueError(f"options are only valid for field_type=select")


def coerce_value(field_type: str, raw: Any, *,
                 options: Iterable[str] | None = None,
                 required: bool = False) -> str | None:
    """Validate ``raw`` and return the canonical string for storage.

    ``None`` or empty string means "clear the field" — only allowed
    when ``required`` is False.
    """
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        if required:
            raise ValueError("value is required")
        return None

    if field_type == "text":
        s = str(raw).strip()
        if len(s) > MAX_TEXT_VALUE_LENGTH:
            raise ValueError(
                f"text value exceeds {MAX_TEXT_VALUE_LENGTH} chars"
            )
        return s

    if field_type == "number":
        try:
            d = Decimal(str(raw).strip())
        except (InvalidOperation, ValueError):
            raise ValueError("value must be numeric")
        if d.is_nan() or d.is_infinite():
            raise ValueError("value must be a finite number")
        # Canonical form — strip trailing zeros so "1.0" and "1.00"
        # compare equal on read.
        return format(d.normalize(), "f") if d == d.to_integral_value() else str(d.normalize())

    if field_type == "boolean":
        if isinstance(raw, bool):
            return "true" if raw else "false"
        s = str(raw).strip().lower()
        if s in ("true", "1", "yes", "y"):
            return "true"
        if s in ("false", "0", "no", "n"):
            return "false"
        raise ValueError("value must be boolean")

    if field_type == "date":
        s = str(raw).strip()
        try:
            date.fromisoformat(s)
        except ValueError:
            raise ValueError("value must be ISO-8601 date (YYYY-MM-DD)")
        return s

    if field_type == "select":
        s = str(raw).strip()
        allowed = list(options or [])
        if not allowed:
            raise ValueError("select field has no options configured")
        if s not in allowed:
            raise ValueError(f"value must be one of {allowed}")
        return s

    raise ValueError(f"unknown field_type: {field_type}")


def cast_for_read(field_type: str, stored: str | None) -> Any:
    """Inverse of :func:`coerce_value` for building API responses."""
    if stored is None:
        return None
    if field_type == "number":
        try:
            d = Decimal(stored)
        except InvalidOperation:
            return None
        return int(d) if d == d.to_integral_value() else float(d)
    if field_type == "boolean":
        return stored == "true"
    # text / date / select are returned as-is. Date stays a string so
    # the frontend can format for the user's locale.
    return stored
