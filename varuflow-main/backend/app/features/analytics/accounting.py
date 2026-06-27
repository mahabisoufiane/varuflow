"""Swedish accounting exports.

Endpoint:
  POST /api/accounting/sie4-export?year=YYYY  (owner only)

Produces a SIE4 file — the de-facto Swedish bookkeeping interchange
format (SIE 4B, "transaktioner") that every mainstream accounting
package (Fortnox, Visma, Bokio, Björn Lundén, …) can import. The file
covers every invoice issued in the requested fiscal year and is
encoded as CP437 per SIE spec §5.2; we emit text/plain but with a
``.se`` filename matching the SIE convention.

Accounts used (BAS 2024):
  1510  Kundfordringar                 (receivables, debit)
  2610  Utgående moms 25%              (output VAT, credit)
  3000  Försäljning inom Sverige       (revenue, credit)

Each invoice becomes one verification (#VER) with three #TRANS lines —
one per account — and the ledger balance of every #VER is zero.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module, require_role
from app.features.invoicing.models import Customer, Invoice, InvoiceStatus
from app.features.auth.organization import Organization, OrgRole
from app.services.audit import log_action

# Ledger is manager-level finance data — gate at ADMIN. Members never see it.
router = APIRouter(prefix="/api/accounting", tags=["accounting"], dependencies=[Depends(require_module("finance")), Depends(require_role(OrgRole.ADMIN))])
log = logging.getLogger(__name__)

# BAS chart account numbers + human-readable labels that go into #KONTO.
ACCOUNT_RECEIVABLES = ("1510", "Kundfordringar")
ACCOUNT_OUTPUT_VAT  = ("2610", "Utgående moms 25%")
ACCOUNT_REVENUE     = ("3000", "Försäljning inom Sverige")

# SIE invoice statuses we include. DRAFT is a work-in-progress and must
# not hit the ledger; CANCELLED (if ever set) likewise. Everything that
# has been SENT, PAID or fallen OVERDUE is a real receivable.
_EXPORTABLE_STATUSES = (
    InvoiceStatus.SENT,
    InvoiceStatus.PAID,
    InvoiceStatus.OVERDUE,
)


def _normalize_orgnr(raw: str | None) -> str:
    """Format a Swedish org number as ``XXXXXX-XXXX``.

    Accepts the stored value in any common form (``5560001234``,
    ``556000-1234``, ``SE556000123401``) and falls back to a zero
    placeholder when the org has no number on file — SIE requires the
    field to be present even if the value is unknown.
    """
    if not raw:
        return "000000-0000"
    s = raw.strip().upper()
    # Strip a leading country code (``SE``) before digit extraction —
    # some orgs store the VAT form ``SE556000123401`` where the trailing
    # ``01`` is the VAT check suffix, not part of the org number.
    if s.startswith("SE"):
        s = s[2:]
    digits = re.sub(r"\D", "", s)
    # VAT form leaves 12 digits: the real orgnr is the first 10.
    if len(digits) == 12:
        digits = digits[:10]
    if len(digits) != 10:
        return "000000-0000"
    return f"{digits[:6]}-{digits[6:]}"


def _sie_escape(value: str) -> str:
    r"""Escape a string for SIE: wrap in quotes, escape ``"`` and ``\``."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _fmt_amount(value: Decimal, *, sign: int = 1) -> str:
    """Format a monetary amount with two decimals and a dot separator.

    SIE uses the international decimal point (``.``), not the Swedish
    comma — this surprises some readers but is mandated by the spec.
    """
    q = (Decimal(value) * sign).quantize(Decimal("0.01"))
    return f"{q:.2f}"


def _build_sie4(
    *,
    org: Organization,
    invoices: list[Invoice],
    customers_by_id: dict,
    year: int,
) -> str:
    buf = StringIO()
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    w = buf.write

    # ── Header ────────────────────────────────────────────────────────
    # #FLAGGA 0  → file not previously imported. Readers flip to 1 on
    # import to detect double-import.
    w("#FLAGGA 0\n")
    w(f"#PROGRAM {_sie_escape('Varuflow')} {_sie_escape('1.0')}\n")
    w("#FORMAT PC8\n")
    w(f"#GEN {today}\n")
    w("#SIETYP 4\n")
    w(f"#ORGNR {_normalize_orgnr(org.org_number)}\n")
    w(f"#FNAMN {_sie_escape(org.name or 'Varuflow')}\n")
    # Fiscal year spans — required by SIE for type 4B
    w(f"#RAR 0 {year}0101 {year}1231\n")

    # ── Chart of accounts ─────────────────────────────────────────────
    for number, label in (ACCOUNT_RECEIVABLES, ACCOUNT_OUTPUT_VAT, ACCOUNT_REVENUE):
        w(f"#KONTO {number} {_sie_escape(label)}\n")

    # ── Verifications ─────────────────────────────────────────────────
    for idx, inv in enumerate(invoices, start=1):
        issue = inv.issue_date.strftime("%Y%m%d")
        customer = customers_by_id.get(inv.customer_id)
        memo = _sie_escape(
            f"{inv.invoice_number} — "
            f"{(customer.company_name if customer else 'Kund')}"
        )
        # Verification series "A" is the default sales journal — no
        # reason to split series since Varuflow only emits sales right
        # now (purchase bookkeeping lives on the other side of the
        # Fortnox/Bokio sync).
        w(f'#VER A {idx} {issue} {memo}\n')
        w("{\n")
        # 1510 Kundfordringar     — debit (customer owes us)
        w(f'  #TRANS {ACCOUNT_RECEIVABLES[0]} {{}} {_fmt_amount(inv.total_sek)}\n')
        # 3000 Försäljning        — credit (revenue booked, negative)
        w(f'  #TRANS {ACCOUNT_REVENUE[0]} {{}} {_fmt_amount(inv.subtotal, sign=-1)}\n')
        # 2610 Utgående moms      — credit (VAT liability, negative)
        w(f'  #TRANS {ACCOUNT_OUTPUT_VAT[0]} {{}} {_fmt_amount(inv.vat_amount, sign=-1)}\n')
        w("}\n")

    return buf.getvalue()


@router.post("/sie4-export")
async def export_sie4(
    request: Request,
    year: int = Query(..., ge=2000, le=2100),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Stream a SIE4 text file for every invoice issued in ``year``."""
    _, member = ctx
    if member.role != OrgRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")

    org = await db.get(Organization, member.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Pull every exportable invoice in the fiscal year. We filter by
    # issue_date rather than created_at because SIE semantics hinge on
    # when the revenue hit the ledger, not when the row was inserted.
    year_start = datetime(year, 1, 1).date()
    year_end = datetime(year, 12, 31).date()
    rows = (await db.execute(
        select(Invoice)
        .where(
            Invoice.org_id == member.org_id,
            Invoice.issue_date >= year_start,
            Invoice.issue_date <= year_end,
            Invoice.status.in_(_EXPORTABLE_STATUSES),
        )
        .order_by(Invoice.issue_date.asc(), Invoice.invoice_number.asc())
        .options(selectinload(Invoice.customer))
    )).scalars().all()
    customers_by_id = {inv.customer_id: inv.customer for inv in rows if inv.customer}

    body = _build_sie4(
        org=org,
        invoices=list(rows),
        customers_by_id=customers_by_id,
        year=year,
    )

    await log_action(
        db,
        action="SIE4_EXPORT",
        org_id=member.org_id,
        actor_user_id=member.user_id,
        target_type="organization",
        target_id=str(member.org_id),
        request=request,
        extra={"year": year, "invoice_count": len(rows)},
    )
    await db.commit()

    filename = f"varuflow-SIE4-{year}.se"
    # SIE spec mandates CP437; we encode and hand back raw bytes so
    # importers that sniff the encoding don't get tripped up. The
    # content-type stays text/plain since SIE has no registered MIME.
    payload = body.encode("cp437", errors="replace")
    return Response(
        content=payload,
        media_type="text/plain; charset=cp437",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
