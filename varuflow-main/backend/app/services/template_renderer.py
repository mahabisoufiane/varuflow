"""Template renderer service for custom invoice templates (Item 42).

Pure + DB-bound split:

* Pure layer (no ORM imports — exercised directly in tests):
  - :func:`validate_hex_color` — guard for the color inputs.
  - :func:`normalise_font_family` — clamp to a known ReportLab-safe
    family so a stored typo doesn't break PDF generation.
  - :func:`build_preview_html` — HTML preview fragment rendered by
    the settings UI. Keeps rendering logic in one place so the live
    preview and the PDF can't drift.
  - :func:`template_to_dict` — serialisation that the router and the
    PDF generator both consume.

* DB layer (lazy imports): :func:`get_default_template` and
  :func:`resolve_template_for_invoice` fetch the row the PDF
  generator needs, falling back to a synthesised "house default"
  so a tenant that never configured a template still renders.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from typing import Any


# ═══════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════


# ReportLab-safe font families. A stored value outside this set is
# clamped back to Helvetica so the renderer never raises on PDF
# generation — a data error in the settings page is less harmful than
# a 500 on every invoice download.
SUPPORTED_FONTS: tuple[str, ...] = (
    "Helvetica",
    "Times-Roman",
    "Courier",
)

# House defaults applied when an org has no saved template. Matches
# the legacy PO PDF palette so the un-customised invoice looks the
# same as before Item 42 shipped.
HOUSE_DEFAULT: dict[str, Any] = {
    "id": None,
    "name": "Default",
    "is_default": True,
    "logo_url": None,
    "primary_color": "#1a2332",
    "accent_color": "#2563eb",
    "font_family": "Helvetica",
    "show_bank_details": True,
    "show_qr_code": False,
    "footer_text": None,
    "header_text": None,
    "is_active": True,
}


_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


# ═══════════════════════════════════════════════════════════════════
# Pure helpers
# ═══════════════════════════════════════════════════════════════════


def validate_hex_color(value: str) -> str:
    """Return ``value`` if it is a 7-character ``#RRGGBB`` hex code,
    else raise ``ValueError``. The PDF layer uses
    ``colors.HexColor`` which is strict; the router pre-validates so
    the bad input is rejected at the HTTP boundary, not deep inside
    the renderer."""
    if not isinstance(value, str) or not _HEX_RE.match(value):
        raise ValueError(f"invalid_hex_color:{value!r}")
    return value


def normalise_font_family(value: str | None) -> str:
    """Clamp ``value`` to a supported font family."""
    if value and value in SUPPORTED_FONTS:
        return value
    return "Helvetica"


def template_to_dict(tpl: Any) -> dict[str, Any]:
    """Serialise an ``InvoiceTemplate`` ORM row (or a dict) to the
    canonical wire shape. Accepts either so tests can feed plain
    dicts and the router can feed the ORM row."""
    if isinstance(tpl, dict):
        src = tpl
    else:
        src = {
            "id": getattr(tpl, "id", None),
            "name": tpl.name,
            "is_default": bool(tpl.is_default),
            "logo_url": tpl.logo_url,
            "primary_color": tpl.primary_color,
            "accent_color": tpl.accent_color,
            "font_family": tpl.font_family,
            "show_bank_details": bool(tpl.show_bank_details),
            "show_qr_code": bool(tpl.show_qr_code),
            "footer_text": tpl.footer_text,
            "header_text": tpl.header_text,
            "is_active": bool(tpl.is_active),
        }
    return {
        "id": (None if src.get("id") is None else str(src["id"])),
        "name": src["name"],
        "is_default": bool(src.get("is_default", False)),
        "logo_url": src.get("logo_url"),
        "primary_color": src.get("primary_color", "#1a2332"),
        "accent_color": src.get("accent_color", "#2563eb"),
        "font_family": normalise_font_family(src.get("font_family")),
        "show_bank_details": bool(src.get("show_bank_details", True)),
        "show_qr_code": bool(src.get("show_qr_code", False)),
        "footer_text": src.get("footer_text"),
        "header_text": src.get("header_text"),
        "is_active": bool(src.get("is_active", True)),
    }


def build_preview_html(
    template: dict[str, Any],
    *,
    org_name: str = "Example AB",
    invoice_number: str = "INV-000123",
) -> str:
    """Render a stand-alone HTML preview of the invoice template.

    Used by the settings page to show a live preview without
    round-tripping through the PDF renderer. The styling uses inline
    CSS so the fragment can be dropped into an iframe srcdoc and
    rendered without any external stylesheet.
    """
    t = template
    primary = escape(t.get("primary_color") or "#1a2332")
    accent = escape(t.get("accent_color") or "#2563eb")
    font = escape(normalise_font_family(t.get("font_family")))
    logo_html = (
        f'<img src="{escape(t["logo_url"])}" alt="logo" '
        f'style="max-height:56px;max-width:200px;" />'
        if t.get("logo_url") else ""
    )
    header_html = (
        f'<div class="header-note">{escape(t["header_text"])}</div>'
        if t.get("header_text") else ""
    )
    footer_html = (
        f'<div class="footer-note">{escape(t["footer_text"])}</div>'
        if t.get("footer_text") else ""
    )
    bank_html = (
        '<div class="bank"><strong>Bank</strong><br/>'
        'Bankgiro: 123-4567<br/>IBAN: SE00 0000 0000 0000</div>'
        if t.get("show_bank_details") else ""
    )
    qr_html = (
        '<div class="qr" aria-label="Swish QR code">[QR]</div>'
        if t.get("show_qr_code") else ""
    )
    return (
        f'<!DOCTYPE html><html><body style="font-family:{font},sans-serif;'
        f'color:#111;margin:0;padding:24px;">'
        f'<div style="border-top:6px solid {primary};padding-top:16px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'{logo_html}'
        f'<div style="text-align:right;">'
        f'<div style="color:{primary};font-size:22px;font-weight:600;">'
        f'{escape(org_name)}</div>'
        f'<div style="color:#666;">Invoice {escape(invoice_number)}</div>'
        f'</div></div>'
        f'{header_html}'
        f'<hr style="border:none;border-top:2px solid {accent};margin:16px 0;"/>'
        f'<div>Preview body — line items render here.</div>'
        f'{bank_html}{qr_html}{footer_html}'
        f'</div></body></html>'
    )


# ═══════════════════════════════════════════════════════════════════
# DB-bound layer (lazy ORM imports)
# ═══════════════════════════════════════════════════════════════════


async def get_default_template(db, *, org_id: uuid.UUID) -> dict[str, Any]:
    """Return the tenant's default template as a dict, or the house
    default if none is configured. Always safe to call — even a
    freshly-provisioned org without any templates gets a renderable
    payload back.
    """
    from sqlalchemy import select

    from app.features.invoicing.model_invoice_templates import InvoiceTemplate

    row = await db.scalar(
        select(InvoiceTemplate).where(
            InvoiceTemplate.org_id == org_id,
            InvoiceTemplate.is_default == True,  # noqa: E712
            InvoiceTemplate.is_active == True,  # noqa: E712
        )
    )
    if row is None:
        return dict(HOUSE_DEFAULT)
    return template_to_dict(row)


async def resolve_template_for_invoice(
    db,
    *,
    org_id: uuid.UUID,
    template_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Resolve which template to apply when rendering an invoice.

    If ``template_id`` is supplied and belongs to the org, return it.
    Otherwise fall back to :func:`get_default_template`. This keeps
    the PDF generator free of fallback logic — by the time it gets
    called, the caller has already resolved what to render.
    """
    from sqlalchemy import select

    from app.features.invoicing.model_invoice_templates import InvoiceTemplate

    if template_id is not None:
        row = await db.scalar(
            select(InvoiceTemplate).where(
                InvoiceTemplate.id == template_id,
                InvoiceTemplate.org_id == org_id,
                InvoiceTemplate.is_active == True,  # noqa: E712
            )
        )
        if row is not None:
            return template_to_dict(row)
    return await get_default_template(db, org_id=org_id)


async def clear_default(
    db, *, org_id: uuid.UUID, except_id: uuid.UUID | None = None,
) -> None:
    """Unset ``is_default`` on every other template in the org.

    Called in the transaction that promotes a different template to
    default so the partial unique index never rejects the insert.
    Runs before the target row is updated to ``is_default=True``.
    """
    from sqlalchemy import update

    from app.features.invoicing.model_invoice_templates import InvoiceTemplate

    stmt = (
        update(InvoiceTemplate)
        .where(
            InvoiceTemplate.org_id == org_id,
            InvoiceTemplate.is_default == True,  # noqa: E712
        )
        .values(is_default=False)
    )
    if except_id is not None:
        stmt = stmt.where(InvoiceTemplate.id != except_id)
    await db.execute(stmt)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
