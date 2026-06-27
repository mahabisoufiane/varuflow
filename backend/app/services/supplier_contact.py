"""Pure helpers for supplier contacts (Item 78).

Validates name / role / email / phone without touching the DB
so the router stays thin and the tests stay fast.
"""
from __future__ import annotations

import re

MAX_CONTACTS_PER_SUPPLIER: int = 50
MAX_NAME_LEN: int = 128
MAX_ROLE_LEN: int = 64
MAX_EMAIL_LEN: int = 254   # RFC 5321
MAX_PHONE_LEN: int = 32

# Loose email regex — matches what the RFC actually requires most
# businesses to accept: one @, a dot in the domain, no whitespace,
# no control chars. Strict RFC 5322 parsing is left to Resend.
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
# Phone: digits, spaces, dashes, parens, + as first char. The
# WhatsApp/SMS side does E.164 normalisation later; here we just
# fence off obviously-invalid values.
_PHONE_RE = re.compile(r"^[+(]?[0-9][0-9 ()\-\.]{2,31}$")
_CONTROL  = re.compile(r"[\x00-\x1f\x7f]")


def normalize_name(raw: object) -> str:
    if not isinstance(raw, str):
        raise ValueError("contact name must be a string")
    if _CONTROL.search(raw):
        raise ValueError("contact name contains control characters")
    cleaned = " ".join(raw.split())
    if not cleaned:
        raise ValueError("contact name must not be empty")
    if len(cleaned) > MAX_NAME_LEN:
        raise ValueError(f"contact name exceeds {MAX_NAME_LEN} characters")
    return cleaned


def normalize_role(raw: object) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError("role must be a string or null")
    cleaned = " ".join(raw.split())
    if not cleaned:
        return None
    if _CONTROL.search(cleaned):
        raise ValueError("role contains control characters")
    if len(cleaned) > MAX_ROLE_LEN:
        raise ValueError(f"role exceeds {MAX_ROLE_LEN} characters")
    return cleaned


def normalize_email(raw: object) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError("email must be a string or null")
    cleaned = raw.strip().lower()
    if not cleaned:
        return None
    if len(cleaned) > MAX_EMAIL_LEN:
        raise ValueError(f"email exceeds {MAX_EMAIL_LEN} characters")
    if not _EMAIL_RE.match(cleaned):
        raise ValueError("email is not a valid address")
    return cleaned


def normalize_phone(raw: object) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError("phone must be a string or null")
    cleaned = raw.strip()
    if not cleaned:
        return None
    if len(cleaned) > MAX_PHONE_LEN:
        raise ValueError(f"phone exceeds {MAX_PHONE_LEN} characters")
    if not _PHONE_RE.match(cleaned):
        raise ValueError("phone is not a valid number")
    return cleaned


def assert_has_channel(*, email: str | None, phone: str | None) -> None:
    """A contact must have at least one reachable channel."""
    if not email and not phone:
        raise ValueError(
            "contact must have at least one of email or phone"
        )


def assert_under_limit(*, current_count: int) -> None:
    if current_count < 0:
        raise ValueError("current_count cannot be negative")
    if current_count >= MAX_CONTACTS_PER_SUPPLIER:
        raise ValueError(
            f"supplier already has {MAX_CONTACTS_PER_SUPPLIER} contacts "
            "(limit reached)"
        )
