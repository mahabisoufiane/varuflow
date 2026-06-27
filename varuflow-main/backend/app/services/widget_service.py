"""Public booking widget service (Item 46).

Pure helpers (slug generation, brand-color fallback, overlap check)
plus a small DB layer for the public lookup + email dispatch.

**No authentication is required** for the public-facing endpoints —
that's the whole point of the embeddable widget. Org isolation is
enforced by the slug → org_id resolver, and write paths are limited
to *creating* appointments against a single org's services/staff.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════


# Fallback brand color when the org has no invoice template.
DEFAULT_BRAND_COLOR = "#1a2332"

# Short-id suffix length on the slug — cuts collision risk between
# salons with similar names while keeping URLs readable.
SLUG_SUFFIX_LEN = 6

# Hex-color validator. Matches #RGB and #RRGGBB.
_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

# Simple email validation — just enough to refuse obvious garbage
# without pulling in a heavyweight lib. The confirmation email
# dispatch will fail-soft if the address is undeliverable.
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# Phone validation — accept E.164 and common national formats.
# Intentionally permissive because MENA phone numbers vary widely.
_PHONE_RE = re.compile(r"^\+?[\d\s\-\(\)]{6,30}$")

# Max name length on the booking form.
MAX_NAME = 120


class WidgetValidationError(ValueError):
    """Raised when a widget input fails validation."""


# ═══════════════════════════════════════════════════════════════════
# Pure helpers
# ═══════════════════════════════════════════════════════════════════


def slugify(text: str) -> str:
    """Lower-case, strip non-alphanumerics, collapse to dashes.

    Matches the shape of a URL slug — deterministic, idempotent,
    never raises. Empty input returns an empty string so the caller
    can decide on a fallback.
    """
    if not isinstance(text, str):
        return ""
    lowered = text.lower()
    # Keep alphanum + space + dash; drop everything else.
    cleaned = re.sub(r"[^a-z0-9\s\-]", "", lowered)
    # Collapse whitespace/dashes to single dash.
    cleaned = re.sub(r"[\s\-]+", "-", cleaned).strip("-")
    return cleaned


def org_slug(org_name: str, org_id: uuid.UUID | str) -> str:
    """Build a stable public slug from an org's name + a suffix from
    its id. The suffix disambiguates collisions between salons with
    the same display name.
    """
    base = slugify(org_name) or "salon"
    suffix = str(org_id).replace("-", "")[:SLUG_SUFFIX_LEN]
    return f"{base}-{suffix}"


def validate_brand_color(value: str | None) -> str:
    """Return a validated hex color or the default fallback."""
    if isinstance(value, str) and _HEX_COLOR_RE.match(value):
        return value
    return DEFAULT_BRAND_COLOR


def validate_name(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WidgetValidationError("name_required")
    cleaned = value.strip()
    if len(cleaned) > MAX_NAME:
        raise WidgetValidationError("name_too_long")
    return cleaned


def validate_email(value: str) -> str:
    if not isinstance(value, str) or not _EMAIL_RE.match(value.strip()):
        raise WidgetValidationError("email_invalid")
    return value.strip().lower()


def validate_phone(value: str | None) -> str | None:
    """Phone is optional — walk-ins may not leave a number."""
    if value is None or not str(value).strip():
        return None
    if not _PHONE_RE.match(str(value).strip()):
        raise WidgetValidationError("phone_invalid")
    return str(value).strip()


def slots_overlap(
    a_start: datetime, a_end: datetime,
    b_start: datetime, b_end: datetime,
) -> bool:
    """Pure half-open-interval overlap test.

    Matches the DB-level double-booking guard used by the authenticated
    bookings router (``a.start < b.end AND a.end > b.start``) so the
    public and private paths can't disagree.
    """
    return a_start < b_end and a_end > b_start


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════
# Confirmation email
# ═══════════════════════════════════════════════════════════════════


@dataclass
class BookingConfirmation:
    """Minimal payload the confirmation dispatcher needs. Kept as a
    dataclass so the pure email-body builder is trivially unit-
    testable without FastAPI / DB in scope."""
    customer_name: str
    customer_email: str
    org_name: str
    service_name: str
    staff_name: str
    start_time: datetime
    brand_color: str


def build_confirmation_html(payload: BookingConfirmation) -> str:
    """Render the confirmation HTML body.

    Uses inline styles only so every major email client renders it
    consistently. The org's brand color is applied to the header
    band and the CTA.
    """
    color = validate_brand_color(payload.brand_color)
    when = payload.start_time.strftime("%A, %d %B %Y %H:%M")
    # Escape caller-controlled fields to defuse any XSS carried from
    # the name/service/staff free-text inputs.
    from html import escape
    return (
        "<!doctype html><html><body style=\"font-family:sans-serif;"
        "max-width:520px;margin:40px auto;color:#1a202c\">"
        f"<div style=\"background:{color};color:#fff;padding:20px 24px;"
        "border-radius:8px 8px 0 0\">"
        f"<h2 style=\"margin:0\">Appointment confirmed</h2></div>"
        "<div style=\"padding:24px;border:1px solid #e2e8f0;"
        "border-top:0;border-radius:0 0 8px 8px\">"
        f"<p>Hi {escape(payload.customer_name)},</p>"
        f"<p>Your appointment at <strong>{escape(payload.org_name)}</strong>"
        " has been booked.</p>"
        f"<p><strong>Service:</strong> {escape(payload.service_name)}<br>"
        f"<strong>With:</strong> {escape(payload.staff_name)}<br>"
        f"<strong>When:</strong> {escape(when)}</p>"
        "<p style=\"font-size:13px;color:#718096\">"
        "If you need to cancel or reschedule, please contact the salon directly."
        "</p></div></body></html>"
    )


async def send_confirmation_email(payload: BookingConfirmation) -> None:
    """Dispatch the confirmation via the existing SMTP pipeline.

    Falls back to stdout logging in dev (SMTP_HOST unset) just like
    the other transactional emails.
    """
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    from app.config import settings

    html = build_confirmation_html(payload)
    subject = f"Appointment confirmed — {payload.org_name}"

    if not settings.SMTP_HOST:
        import logging
        logging.getLogger(__name__).info(
            "DEV EMAIL | to=%s | subject=%s", payload.customer_email, subject,
        )
        return

    import aiosmtplib
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = payload.customer_email
    msg.attach(MIMEText(html, "html", "utf-8"))
    kwargs: dict = {"hostname": settings.SMTP_HOST, "port": settings.SMTP_PORT}
    if settings.SMTP_USER:
        kwargs["username"] = settings.SMTP_USER
    if settings.SMTP_PASSWORD:
        kwargs["password"] = settings.SMTP_PASSWORD
    if settings.SMTP_PORT == 465:
        kwargs["use_tls"] = True
    elif settings.SMTP_PORT == 587:
        kwargs["start_tls"] = True
    try:
        await aiosmtplib.send(msg, **kwargs)
    except Exception:
        # Confirmation failures must NOT roll back the booking — the
        # customer is on-the-record; a missed email is a support
        # ticket, not a data-loss event.
        import logging
        logging.getLogger(__name__).exception("widget confirmation email failed")


# ═══════════════════════════════════════════════════════════════════
# DB-bound layer
# ═══════════════════════════════════════════════════════════════════


async def resolve_org_by_slug(db, *, slug: str):
    """Look up an org by its public slug.

    The slug is ``slugify(name) + "-" + short_id_prefix``. We cheaply
    filter to candidates whose id prefix matches, then compare the
    full slug to rule out any remaining collisions.
    """
    from sqlalchemy import select as _select

    from app.features.auth.organization import Organization

    if not isinstance(slug, str) or "-" not in slug:
        return None
    # The last ``SLUG_SUFFIX_LEN`` chars after the last ``-`` are the
    # id prefix. Split from the right to be robust to dashes in the
    # salon's display name.
    base, suffix = slug.rsplit("-", 1)
    if len(suffix) != SLUG_SUFFIX_LEN:
        return None
    # Candidate orgs whose id (hex) starts with the suffix. Matches
    # one row in practice; we double-check the full slug anyway.
    candidates = (
        await db.execute(_select(Organization))
    ).scalars().all()
    for org in candidates:
        if org_slug(org.name or "", org.id) == slug:
            return org
    return None


async def resolve_brand_color(db, *, org_id: uuid.UUID) -> str:
    """Return the org's default invoice-template primary color, or
    the fallback. Keeps the widget visually consistent with the
    invoices the same salon issues."""
    from sqlalchemy import select as _select

    try:
        from app.features.invoicing.model_invoice_templates import InvoiceTemplate
    except Exception:  # pragma: no cover — safety net
        return DEFAULT_BRAND_COLOR
    row = await db.scalar(
        _select(InvoiceTemplate)
        .where(InvoiceTemplate.org_id == org_id, InvoiceTemplate.is_default == True)  # noqa: E712
        .limit(1)
    )
    if row is None:
        return DEFAULT_BRAND_COLOR
    return validate_brand_color(getattr(row, "primary_color", None))
