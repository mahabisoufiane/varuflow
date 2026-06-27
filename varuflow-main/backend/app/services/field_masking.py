"""Role-based field masking service.

Masking rules are stored in `field_masking_rules`. At API boundary,
call `apply_masks(value_dict, resource, role, org_id, db)` to
replace sensitive field values with masked representations.

Mask styles:
  obfuscate — replace digits/chars with ●  (amounts → "●●,●●●")
  partial   — keep first char + domain     (email → "j***@acme.com")
  hidden    — replace entirely with "—"
"""
from __future__ import annotations

import re
from typing import Any, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.compliance.models import FieldMaskingRule

# ── Masking implementations ───────────────────────────────────────────────────

def _obfuscate_amount(value: Any) -> str:
    """Turn 12 345.50 into ●●,●●●"""
    s = str(value)
    # Replace every digit with ●, keep separators for readability
    return re.sub(r"\d", "●", s)


def _partial_email(value: str) -> str:
    """j.smith@acme.com → j***@acme.com"""
    if "@" not in value:
        return "●●●@●●●.●●●"
    local, domain = value.split("@", 1)
    return f"{local[0]}***@{domain}"


def _partial_phone(value: str) -> str:
    """Keep country code, mask rest: +46 70 123 45 67 → +46 ●●● ●●● ●●●●"""
    s = str(value).strip()
    # Keep leading + and up to 3 digits (country code)
    m = re.match(r"(\+?\d{1,3})(.*)", s)
    if m:
        rest = re.sub(r"\d", "●", m.group(2))
        return m.group(1) + rest
    return re.sub(r"\d", "●", s)


def _partial_name(value: str) -> str:
    """John Doe → J*** D***"""
    parts = str(value).split()
    return " ".join(f"{p[0]}***" if p else "***" for p in parts)


MASK_FN = {
    # (resource, field): masker function
    ("invoice", "total_amount"):    _obfuscate_amount,
    ("invoice", "subtotal"):        _obfuscate_amount,
    ("invoice", "tax_amount"):      _obfuscate_amount,
    ("invoice", "paid_amount"):     _obfuscate_amount,
    ("customer", "email"):          _partial_email,
    ("customer", "phone"):          _partial_phone,
    ("customer", "name"):           _partial_name,
    ("supplier", "email"):          _partial_email,
    ("supplier", "phone"):          _partial_phone,
    ("expense", "amount"):          _obfuscate_amount,
    ("payroll", "salary"):          _obfuscate_amount,
    ("payroll", "net_pay"):         _obfuscate_amount,
}

HIDDEN = "—"


def mask_value(value: Any, resource: str, field: str, style: str) -> Any:
    """Apply a single mask to a value."""
    if value is None:
        return value
    if style == "hidden":
        return HIDDEN
    fn = MASK_FN.get((resource, field))
    if fn:
        try:
            return fn(value)
        except Exception:
            return HIDDEN
    # Fallback: obfuscate generically
    return re.sub(r"[a-zA-Z0-9]", "●", str(value))


# ── DB-backed rule lookup ─────────────────────────────────────────────────────

async def get_active_rules(
    db: AsyncSession,
    org_id: uuid.UUID,
    role: str,
    resource: str,
) -> dict[str, str]:
    """Return {field: mask_style} for active rules matching org/role/resource."""
    rows = await db.execute(
        select(FieldMaskingRule).where(
            FieldMaskingRule.org_id == org_id,
            FieldMaskingRule.role == role,
            FieldMaskingRule.resource == resource,
            FieldMaskingRule.enabled.is_(True),
        )
    )
    return {r.field: r.mask_style for r in rows.scalars()}


async def apply_masks(
    data: dict,
    resource: str,
    role: str,
    org_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    """Return a copy of `data` with masked fields substituted.
    Non-destructive: original dict is not modified."""
    rules = await get_active_rules(db, org_id, role, resource)
    if not rules:
        return data
    result = dict(data)
    for field, style in rules.items():
        if field in result:
            result[field] = mask_value(result[field], resource, field, style)
    return result


# ── Default rule presets ──────────────────────────────────────────────────────

DEFAULT_MEMBER_RULES = [
    # (role, resource, field, mask_style)
    ("member", "invoice",  "total_amount", "obfuscate"),
    ("member", "invoice",  "tax_amount",   "obfuscate"),
    ("member", "customer", "email",        "partial"),
    ("member", "customer", "phone",        "partial"),
    ("member", "payroll",  "salary",       "hidden"),
    ("member", "payroll",  "net_pay",      "hidden"),
    ("viewer", "invoice",  "total_amount", "obfuscate"),
    ("viewer", "customer", "email",        "partial"),
]
