"""Pure helpers for expense notes (Item 94).

Mirror of supplier_note (Item 76) / customer_note (Item 71) /
the rest of the note family. No DB access — body validation,
mention extraction, and the per-expense pin-limit guard only.
"""
from __future__ import annotations

import re

MIN_BODY_LENGTH: int = 1
MAX_BODY_LENGTH: int = 10_000
MAX_PINNED_PER_EXPENSE: int = 5

# Mentions follow the same shape as the other note families. The
# leading @ must be at start-of-string or preceded by a non-word
# character so an email address (``foo@bar.com``) never counts as a
# mention.
_MENTION_RE = re.compile(r"(?:^|\W)@([a-zA-Z0-9_][a-zA-Z0-9_.-]{0,31})")


def validate_body(raw: str) -> str:
    if raw is None:
        raise ValueError("body is required")
    if not isinstance(raw, str):
        raise ValueError("body must be a string")
    # Strip trailing whitespace only — preserve internal formatting.
    v = raw.strip()
    if len(v) < MIN_BODY_LENGTH:
        raise ValueError("body is required")
    if len(v) > MAX_BODY_LENGTH:
        raise ValueError(f"body too long ({MAX_BODY_LENGTH} chars max)")
    return v


def extract_mentions(body: str) -> list[str]:
    """Return the de-duplicated list of mention handles, in order."""
    if not body:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _MENTION_RE.finditer(body):
        handle = m.group(1).lower()
        if handle in seen:
            continue
        seen.add(handle)
        out.append(handle)
    return out


def assert_pin_limit(*, current_pinned: int) -> None:
    """Reject a pin that would push the count over the per-expense cap.

    ``current_pinned`` is the count *excluding* the row being pinned.
    """
    if current_pinned < 0:
        raise ValueError("current_pinned cannot be negative")
    if current_pinned >= MAX_PINNED_PER_EXPENSE:
        raise ValueError(
            f"pin limit reached ({MAX_PINNED_PER_EXPENSE} notes per expense)"
        )
