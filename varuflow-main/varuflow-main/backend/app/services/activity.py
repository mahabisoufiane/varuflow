"""Pure helpers for the activity feed (Item 62).

The feed's shape rules (action format, entity_type whitelist, summary
length, cursor encoding) are defined here so they're trivially
unit-testable. The router stays thin.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

# ``action`` is a dot-separated identifier like ``invoice.sent``.
# We keep it lowercase snake.dot so it's stable and easy to filter
# with prefix queries (``invoice.%``).
_ACTION_RE = re.compile(r"^[a-z][a-z0-9_]{0,23}(\.[a-z][a-z0-9_]{0,23}){1,2}$")

# Entities we surface in the feed. Kept broader than tags/custom
# fields because ``appointment`` and ``note`` are first-class here.
ALLOWED_ENTITY_TYPES: frozenset[str] = frozenset({
    "product", "customer", "invoice", "appointment", "payment",
    "expense", "note", "review", "booking",
})

MAX_ACTION_LENGTH: int = 64
MAX_SUMMARY_LENGTH: int = 255
MAX_METADATA_KEYS: int = 20
MAX_METADATA_VALUE_LENGTH: int = 500
MAX_LIMIT: int = 100
DEFAULT_LIMIT: int = 50


def validate_action(action: str) -> str:
    if not isinstance(action, str):
        raise ValueError("action must be a string")
    if len(action) > MAX_ACTION_LENGTH:
        raise ValueError(f"action too long ({MAX_ACTION_LENGTH} chars max)")
    if not _ACTION_RE.match(action):
        raise ValueError(
            "action must be lowercase dotted identifier like 'invoice.sent'"
        )
    return action


def validate_entity_type(entity_type: str | None) -> str | None:
    if entity_type is None or entity_type == "":
        return None
    if entity_type not in ALLOWED_ENTITY_TYPES:
        raise ValueError(
            f"entity_type must be one of {sorted(ALLOWED_ENTITY_TYPES)}"
        )
    return entity_type


def validate_summary(summary: str) -> str:
    if not isinstance(summary, str):
        raise ValueError("summary must be a string")
    s = summary.strip()
    if not s:
        raise ValueError("summary is required")
    if len(s) > MAX_SUMMARY_LENGTH:
        raise ValueError(
            f"summary too long ({MAX_SUMMARY_LENGTH} chars max)"
        )
    return s


def validate_metadata(metadata: Any) -> dict:
    """Accept only flat dicts of scalar values, capped in size."""
    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")
    if len(metadata) > MAX_METADATA_KEYS:
        raise ValueError(f"metadata has too many keys ({MAX_METADATA_KEYS} max)")
    out: dict = {}
    for k, v in metadata.items():
        if not isinstance(k, str) or not k:
            raise ValueError("metadata keys must be non-empty strings")
        if isinstance(v, bool):
            out[k] = v
        elif isinstance(v, (int, float)):
            out[k] = v
        elif v is None:
            out[k] = None
        elif isinstance(v, str):
            if len(v) > MAX_METADATA_VALUE_LENGTH:
                raise ValueError(
                    "metadata value exceeds "
                    f"{MAX_METADATA_VALUE_LENGTH} chars"
                )
            out[k] = v
        else:
            raise ValueError(
                "metadata values must be str/number/bool/null"
            )
    return out


def clamp_limit(limit: Any) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    try:
        n = int(limit)
    except (TypeError, ValueError):
        raise ValueError("limit must be an integer")
    if n < 1:
        raise ValueError("limit must be >= 1")
    if n > MAX_LIMIT:
        return MAX_LIMIT
    return n


# Cursor encoding: base64url(JSON({"t": iso, "id": uuid}))
# Keyset pagination: rows with created_at < t OR (created_at == t AND id < id)


def encode_cursor(created_at: datetime, event_id: uuid.UUID | str) -> str:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    payload = json.dumps(
        {"t": created_at.astimezone(timezone.utc).isoformat(), "id": str(event_id)},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    if not isinstance(cursor, str) or not cursor:
        raise ValueError("cursor is required")
    # re-pad base64
    pad = "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(cursor + pad)
        data = json.loads(raw.decode("utf-8"))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        raise ValueError("invalid cursor")
    if not isinstance(data, dict) or "t" not in data or "id" not in data:
        raise ValueError("invalid cursor")
    try:
        t = datetime.fromisoformat(data["t"])
        eid = uuid.UUID(data["id"])
    except (TypeError, ValueError):
        raise ValueError("invalid cursor")
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t, eid
