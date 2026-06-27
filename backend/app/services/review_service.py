"""Review service helpers (Item 49).

Pure, stdlib-only helpers: token hashing, rating classification, CSV
export, TTL math. No DB, no FastAPI, no Pydantic. The router composes
these with SQLAlchemy queries.
"""
from __future__ import annotations

import csv
import hashlib
import io
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


# ═══════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════

# How long a review-request magic link stays valid. 30 days matches
# Trustpilot / Google-review norms — any shorter and legitimate late
# responders churn; any longer and stale links become a phishing surface.
REVIEW_TOKEN_TTL_DAYS = 30

# Rating at or below this threshold is "low" and triggers a follow-up
# badge in the staff dashboard. 3-stars is the industry default for
# "needs attention" — 2-stars is too strict, 4-stars is too lenient.
LOW_RATING_THRESHOLD = 3

# Raw token entropy. 32 bytes → 43-char urlsafe string. Matches the
# supplier-portal token and the Supabase magic-link budget.
_RAW_TOKEN_BYTES = 32

# How many review requests a single booking can generate. Guards
# against double-tap completions spamming the customer.
MAX_REQUESTS_PER_SOURCE = 1

# Export cap so a noisy org can't OOM the worker.
EXPORT_ROW_CAP = 10_000


# ═══════════════════════════════════════════════════════════════════
# Token helpers (mirror supplier_portal_service)
# ═══════════════════════════════════════════════════════════════════


def generate_token() -> str:
    """Return a freshly minted raw magic-link token."""
    return secrets.token_urlsafe(_RAW_TOKEN_BYTES)


def hash_token(raw: str) -> str:
    """SHA-256 hex digest of the raw token. Deterministic."""
    if not isinstance(raw, str):
        raise ValueError("raw_token_must_be_string")
    if not raw:
        raise ValueError("raw_token_empty")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_expiry(now: datetime | None = None) -> datetime:
    """Canonical expiry = now + :data:`REVIEW_TOKEN_TTL_DAYS`."""
    if now is None:
        now = datetime.now(timezone.utc)
    return now + timedelta(days=REVIEW_TOKEN_TTL_DAYS)


def is_token_expired(expires_at: datetime, now: datetime | None = None) -> bool:
    """True if ``now`` is past ``expires_at``. Naive datetimes are
    coerced to UTC so a buggy caller can't falsely report "not expired"."""
    if now is None:
        now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now > expires_at


# ═══════════════════════════════════════════════════════════════════
# Rating classification (pure)
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class RatingFlag:
    """Explains why a rating needs follow-up."""
    low: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        return {"low": self.low, "reasons": list(self.reasons)}


def classify_rating(rating: int, comment: str | None = None) -> RatingFlag:
    """Flag ratings that warrant operator follow-up.

    Currently flags ratings at or below :data:`LOW_RATING_THRESHOLD`,
    and separately flags any low rating that also carries a written
    comment (so ops can prioritise responding to customers who took
    the time to explain)."""
    r = int(rating)
    reasons: list[str] = []
    if r <= LOW_RATING_THRESHOLD:
        reasons.append("low_rating")
        if comment and comment.strip():
            reasons.append("low_rating_with_comment")
    return RatingFlag(low=bool(reasons), reasons=tuple(reasons))


def validate_rating(rating: int) -> int:
    """Coerce to int and enforce the 1..5 bound. Raises ``ValueError``
    on out-of-range input so the router can convert to a 422."""
    try:
        r = int(rating)
    except (TypeError, ValueError) as exc:
        raise ValueError("rating_must_be_integer") from exc
    if r < 1 or r > 5:
        raise ValueError("rating_out_of_range")
    return r


# ═══════════════════════════════════════════════════════════════════
# CSV export (pure)
# ═══════════════════════════════════════════════════════════════════


CSV_HEADERS = (
    "created_at",
    "rating",
    "comment",
    "is_public",
    "source_type",
    "source_id",
    "customer_id",
    "low_flag",
)


@dataclass
class ExportRow:
    created_at: datetime
    rating: int
    comment: str | None
    is_public: bool
    source_type: str
    source_id: str
    customer_id: str | None
    low_flag: bool

    def as_tuple(self) -> tuple:
        return (
            self.created_at.isoformat(),
            self.rating,
            self.comment or "",
            "yes" if self.is_public else "",
            self.source_type,
            self.source_id,
            self.customer_id or "",
            "yes" if self.low_flag else "",
        )


def render_csv(rows: list[ExportRow]) -> str:
    """Render rows to RFC-4180 CSV. Round-trips cleanly in Excel /
    Sheets / Numbers because we use ``csv.writer`` with
    ``QUOTE_MINIMAL`` rather than hand-rolling escapes."""
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    w.writerow(CSV_HEADERS)
    for r in rows[:EXPORT_ROW_CAP]:
        w.writerow(r.as_tuple())
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════
# Aggregates (pure)
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ReviewSummary:
    """Rating histogram + average for the dashboard header."""
    total: int
    average: float
    low_count: int
    histogram: dict[int, int]

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "average": self.average,
            "low_count": self.low_count,
            "histogram": dict(self.histogram),
        }


def summarise(ratings: list[int]) -> ReviewSummary:
    """Build the dashboard summary from a flat list of ratings.

    ``average`` is rounded to 2 decimals so the UI doesn't have to
    worry about float repr quirks. ``histogram`` always has keys 1..5
    (zero-filled) so the frontend can render a static bar chart
    without missing-key guards."""
    hist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    total = 0
    sum_ratings = 0
    low = 0
    for r in ratings:
        try:
            r = int(r)
        except (TypeError, ValueError):
            continue
        if r < 1 or r > 5:
            continue
        hist[r] += 1
        total += 1
        sum_ratings += r
        if r <= LOW_RATING_THRESHOLD:
            low += 1
    avg = round(sum_ratings / total, 2) if total else 0.0
    return ReviewSummary(total=total, average=avg, low_count=low, histogram=hist)
