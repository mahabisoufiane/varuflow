"""Expense tracking service (Item 43).

Pure + DB-bound split. Pure helpers (no ORM imports) cover input
validation, the approval state machine, analytics aggregation, and
CSV export; DB-bound helpers seed default categories on first use
and compute a mobile-friendly receipt upload descriptor.
"""
from __future__ import annotations

import csv
import enum
import io
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Iterable


# ═══════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════


# Receipt MIME allow-list. Anything else is rejected at the upload
# boundary — prevents tenants from uploading executables or SVGs
# (XSS surface) under the "receipt" label.
ALLOWED_RECEIPT_MIMES: tuple[str, ...] = (
    "image/jpeg",
    "image/png",
    "image/heic",  # iPhone default; converted server-side in a follow-up
    "image/webp",
    "application/pdf",
)

# Max receipt size. 10 MiB — covers a multi-page scanned PDF but
# rejects a photo dump. Enforced both client-side (Next.js route)
# and server-side (router validator) so a bypass at one layer does
# not open a 100 MB hole.
MAX_RECEIPT_BYTES = 10 * 1024 * 1024

# Default seed categories for a newly provisioned org. Matches the
# SIE4 account ranges most common for Swedish SMB accounting
# (5xxx = sales/marketing, 6xxx = admin costs, 7xxx = personnel).
DEFAULT_CATEGORY_SEEDS: tuple[tuple[str, str, str | None, bool], ...] = (
    ("Travel",   "#2563eb", "5810", False),
    ("Office",   "#10b981", "6110", False),
    ("Meals",    "#f59e0b", "5831", False),
    ("Software", "#8b5cf6", "6540", False),
    # Generic "Other" — the fallback for any upload without a picked
    # category. ``is_default = True`` wires the partial unique index.
    ("Other",    "#64748b", "6990", True),
)


# SIE4 account fallback when a category has no mapping or the
# expense has no category at all (e.g. category was deleted after
# the expense was logged).
SIE_FALLBACK_ACCOUNT = "6990"


# Simple ISO 4217 currency guard — three uppercase ASCII letters.
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


class ApprovalError(ValueError):
    """Raised when an approval state transition is not permitted."""


class ReceiptError(ValueError):
    """Raised when a receipt fails upload-time validation."""


@dataclass
class CategoryTotal:
    category_id: uuid.UUID | None
    category_name: str
    category_color: str
    total: Decimal
    count: int

    def to_dict(self) -> dict:
        return {
            "category_id": (None if self.category_id is None else str(self.category_id)),
            "category_name": self.category_name,
            "category_color": self.category_color,
            "total": str(self.total.quantize(Decimal("0.01"))),
            "count": self.count,
        }


# ═══════════════════════════════════════════════════════════════════
# Pure validators
# ═══════════════════════════════════════════════════════════════════


def validate_amount(value) -> Decimal:
    """Normalise a monetary input to a positive two-decimal Decimal.

    Rejects non-numeric inputs, negative amounts, and zero. The
    2-decimal quantisation keeps SEK-like currencies clean; for
    exotic currencies with more digits the caller can override.
    """
    try:
        amount = Decimal(str(value)) if not isinstance(value, Decimal) else value
    except (InvalidOperation, TypeError):
        raise ValueError("invalid_amount")
    if amount <= 0:
        raise ValueError("amount_must_be_positive")
    return amount.quantize(Decimal("0.01"))


def validate_currency(value: str) -> str:
    if not isinstance(value, str) or not _CURRENCY_RE.match(value):
        raise ValueError("invalid_currency")
    return value


def validate_receipt(mime: str | None, size: int | None) -> None:
    """Reject receipts that are too large or have a blocked MIME."""
    if mime is not None and mime not in ALLOWED_RECEIPT_MIMES:
        raise ReceiptError(f"receipt_mime_rejected:{mime}")
    if size is not None:
        if size <= 0:
            raise ReceiptError("receipt_empty")
        if size > MAX_RECEIPT_BYTES:
            raise ReceiptError("receipt_too_large")


# ═══════════════════════════════════════════════════════════════════
# Approval state machine (pure)
# ═══════════════════════════════════════════════════════════════════


class _Status(str, enum.Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


def can_transition(current: str, target: str) -> bool:
    """Return True iff the approval state transition is legal.

    DRAFT → APPROVED | REJECTED  — reviewer acts on a pending row.
    REJECTED → DRAFT             — submitter resubmits after edit.
    APPROVED → *                 — locked (edits require unlock
                                   which is an owner-only action
                                   that routes through the delete
                                   flow, not a state flip).
    DRAFT → DRAFT, etc.          — no-ops are allowed so idempotent
                                   retries don't raise.
    """
    if current == target:
        return True
    if current == _Status.DRAFT.value and target in (
        _Status.APPROVED.value, _Status.REJECTED.value,
    ):
        return True
    if current == _Status.REJECTED.value and target == _Status.DRAFT.value:
        return True
    return False


def assert_transition(current: str, target: str) -> None:
    if not can_transition(current, target):
        raise ApprovalError(f"invalid_transition:{current}->{target}")


# ═══════════════════════════════════════════════════════════════════
# Analytics (pure)
# ═══════════════════════════════════════════════════════════════════


def group_by_category(
    rows: Iterable[dict],
) -> list[CategoryTotal]:
    """Aggregate ``rows`` (each with category_id, category_name,
    category_color, amount) into a ranked list of ``CategoryTotal``.

    Missing/None category_id buckets under "Uncategorised" so the
    analytics breakdown is always complete. Output sorted by total
    descending — the UI displays biggest-spender first.
    """
    buckets: dict[str | None, CategoryTotal] = {}
    for r in rows:
        cid = r.get("category_id")
        key = str(cid) if cid is not None else None
        if key not in buckets:
            buckets[key] = CategoryTotal(
                category_id=cid,
                category_name=r.get("category_name") or "Uncategorised",
                category_color=r.get("category_color") or "#9ca3af",
                total=Decimal("0"),
                count=0,
            )
        bucket = buckets[key]
        bucket.total += Decimal(str(r["amount"]))
        bucket.count += 1
    out = list(buckets.values())
    out.sort(key=lambda b: (b.total, b.count), reverse=True)
    return out


def build_expenses_csv(rows: Iterable[dict]) -> str:
    """Render expenses as an accounting-friendly CSV."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id",
        "expense_date",
        "category",
        "description",
        "amount",
        "currency",
        "status",
        "created_by",
        "receipt_url",
        "sie_account",
    ])
    for r in rows:
        writer.writerow([
            str(r.get("id", "")),
            str(r.get("expense_date", "")),
            r.get("category_name") or "Uncategorised",
            r.get("description") or "",
            str(Decimal(str(r.get("amount", 0))).quantize(Decimal("0.01"))),
            r.get("currency", "SEK"),
            r.get("status", ""),
            str(r.get("created_by") or ""),
            r.get("receipt_url") or "",
            r.get("sie_account") or SIE_FALLBACK_ACCOUNT,
        ])
    return buf.getvalue()


def sie_account_for(row: dict) -> str:
    """Pick the SIE4 account for an expense row, falling back to
    ``SIE_FALLBACK_ACCOUNT`` when the category has no mapping."""
    return row.get("sie_account") or SIE_FALLBACK_ACCOUNT


# ═══════════════════════════════════════════════════════════════════
# DB-bound layer
# ═══════════════════════════════════════════════════════════════════


async def create_default_categories(
    db, *, org_id: uuid.UUID,
) -> list:
    """Ensure the org has the seed categories.

    Idempotent — re-calling on an org that already has a category
    set simply returns the existing rows. Used by the first POST
    /expenses or /expense-categories call so a tenant that never
    configured a taxonomy still sees sensible defaults.
    """
    from sqlalchemy import select

    from app.models.expenses import ExpenseCategory

    existing = (
        await db.execute(
            select(ExpenseCategory).where(ExpenseCategory.org_id == org_id)
        )
    ).scalars().all()
    if existing:
        return list(existing)

    rows = []
    for name, color, sie, is_default in DEFAULT_CATEGORY_SEEDS:
        cat = ExpenseCategory(
            id=uuid.uuid4(),
            org_id=org_id,
            name=name,
            color=color,
            sie_account=sie,
            is_default=is_default,
        )
        db.add(cat)
        rows.append(cat)
    await db.flush()
    return rows


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
