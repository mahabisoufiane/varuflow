"""Document storage service (Item 44).

Pure + DB-bound split. Pure helpers cover input validation, the
expiry-alert threshold check, tag normalisation, and search-scope
assembly; DB helpers handle listing + GDPR-compliant deletion.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable


# ═══════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════


# Document categories the UI exposes out-of-the-box. Stored as a
# plain string column so orgs can add their own categories without
# a migration; validator enforces the known set at the HTTP
# boundary but the DB stays permissive.
ALLOWED_CATEGORIES: tuple[str, ...] = (
    "contract",
    "certificate",
    "compliance",
    "insurance",
    "legal",
    "other",
)

# MIME allow-list. Same threat model as receipts (Item 43) —
# reject SVGs (XSS surface) and executables.
ALLOWED_MIME_TYPES: tuple[str, ...] = (
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/webp",
    "text/plain",
)

# Max document size. 25 MiB — generous enough for a multi-page
# scanned contract but small enough that a tenant uploading huge
# binaries doesn't fill the object store in a day.
MAX_FILE_BYTES = 25 * 1024 * 1024

# Maximum number of tags per document. Keeps the UI sane and
# prevents a single oversized document from dominating the tag
# cloud on the list page.
MAX_TAGS = 20

# Days-before-expiry threshold for the "expiring soon" alert. The
# list page highlights rows falling inside this window in red.
EXPIRY_ALERT_DAYS = 30

# Linked-entity whitelist. Keeps the polymorphic link honest —
# a crafted client can't store "drop_table" as a type.
ALLOWED_LINKED_TYPES: tuple[str, ...] = (
    "supplier",
    "customer",
    "product",
)


class DocumentValidationError(ValueError):
    """Raised when a document input fails validation."""


# ═══════════════════════════════════════════════════════════════════
# Pure validators
# ═══════════════════════════════════════════════════════════════════


def validate_category(value: str) -> str:
    """Clamp an input category to the known set. Unknown values fall
    back to ``other`` rather than raising so a follow-up that adds a
    category at the UI doesn't break documents logged under the old
    name."""
    if not isinstance(value, str):
        return "other"
    normalised = value.strip().lower()
    if normalised in ALLOWED_CATEGORIES:
        return normalised
    return "other"


def validate_mime(mime: str) -> str:
    if mime not in ALLOWED_MIME_TYPES:
        raise DocumentValidationError(f"mime_rejected:{mime}")
    return mime


def validate_size(size: int) -> int:
    if size <= 0:
        raise DocumentValidationError("file_empty")
    if size > MAX_FILE_BYTES:
        raise DocumentValidationError("file_too_large")
    return size


def normalise_tags(tags: Iterable[str]) -> list[str]:
    """Strip, lower-case, deduplicate, and cap the tag list."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in tags or []:
        if not isinstance(raw, str):
            continue
        cleaned = raw.strip().lower()
        if not cleaned or cleaned in seen:
            continue
        if len(cleaned) > 60:
            cleaned = cleaned[:60]
        seen.add(cleaned)
        out.append(cleaned)
        if len(out) >= MAX_TAGS:
            break
    return out


def validate_linked_type(value: str | None) -> str | None:
    if value is None:
        return None
    if value not in ALLOWED_LINKED_TYPES:
        raise DocumentValidationError(f"linked_type_rejected:{value}")
    return value


# ═══════════════════════════════════════════════════════════════════
# Expiry alert (pure)
# ═══════════════════════════════════════════════════════════════════


@dataclass
class ExpiryStatus:
    days_until: int | None   # None → no expiry configured
    expired: bool
    alert: bool              # expired or within EXPIRY_ALERT_DAYS

    def to_dict(self) -> dict:
        return {
            "days_until": self.days_until,
            "expired": self.expired,
            "alert": self.alert,
        }


def expiry_status(
    expires_at: datetime | None,
    *,
    now: datetime | None = None,
    threshold_days: int = EXPIRY_ALERT_DAYS,
) -> ExpiryStatus:
    """Classify a document's expiry state relative to ``now``.

    ``None`` expiry → ``alert=False`` and ``days_until=None`` so
    evergreen documents never trip the alert.
    """
    if expires_at is None:
        return ExpiryStatus(days_until=None, expired=False, alert=False)
    moment = now or datetime.now(timezone.utc)
    # Normalise naive timestamps to UTC so the subtraction always
    # produces a timedelta instead of raising.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    delta = expires_at - moment
    days = int(delta.total_seconds() // 86400)
    expired = delta.total_seconds() <= 0
    alert = expired or days <= threshold_days
    return ExpiryStatus(days_until=days, expired=expired, alert=alert)


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def matches_tag_query(row_tags: list[str], query_tags: list[str]) -> bool:
    """Pure equivalent of a tag-containment filter. Returns True iff
    every query tag is present in the row tags."""
    rs = {t.lower() for t in (row_tags or [])}
    return all(q.lower() in rs for q in query_tags)


# ═══════════════════════════════════════════════════════════════════
# DB-bound layer
# ═══════════════════════════════════════════════════════════════════


async def gdpr_purge_documents(
    db, *, org_id: uuid.UUID,
) -> int:
    """Hard-delete every document row for ``org_id``.

    Called from the GDPR erasure flow. Document content is customer-
    uploaded and does NOT fall under bokföringslagen — unlike
    invoices, there's no retention obligation, so a true purge is
    both legal and correct here.

    Returns the row count so the erasure log can report it.
    """
    from sqlalchemy import delete, func as _f, select as _select

    from app.features.projects.documents_models import Document

    # Count first so the caller can emit a single log line with
    # the number of purged rows.
    count = await db.scalar(
        _select(_f.count(Document.id)).where(Document.org_id == org_id)
    ) or 0
    await db.execute(delete(Document).where(Document.org_id == org_id))
    return int(count)
