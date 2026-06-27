"""GDPR data-subject endpoints (Art. 15 export + Art. 17 erasure).

Both endpoints are restricted to organization OWNERs — the authoritative
data controller for the tenant. Members / admins cannot export or delete
on behalf of the organization.

Endpoints:
  GET    /api/gdpr/export       Download a JSON dump of all org-scoped data
  DELETE /api/gdpr/organization Hard-delete the org and cascade-delete all
                                 rows that reference it. Requires a typed
                                 confirmation header to avoid accidents.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import zipfile
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from .audit_models import AuditLogEntry
from app.features.invoicing.models import (
    Customer,
    Invoice,
    InvoiceLineItem,
    Payment,
)
from app.features.inventory.models import (
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    StockLevel,
    StockMovement,
    Supplier,
    Warehouse,
)
from app.features.auth.organization import (
    Organization,
    OrganizationMember,
    OrgRole,
)
from app.services.audit import log_action

router = APIRouter(prefix="/api/gdpr", tags=["gdpr"], dependencies=[Depends(require_module("settings"))])

log = logging.getLogger(__name__)


def _require_owner(ctx: tuple) -> OrganizationMember:
    _, member = ctx
    if member.role != OrgRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the organization owner may perform GDPR actions",
        )
    return member


def _serialize(obj: Any) -> Any:
    """Recursively convert SQLAlchemy rows to JSON-safe primitives."""
    if hasattr(obj, "__table__"):
        return {
            c.name: _serialize(getattr(obj, c.name))
            for c in obj.__table__.columns
            # Never export OAuth / API tokens in a GDPR data dump. These
            # are credentials the org uses to call third-party APIs, not
            # data-subject personal data under Art. 15. Leaking them in
            # an emailed/downloaded JSON dump (Resend logs, user inbox,
            # email-scanner SaaS, etc.) hands an attacker a live session
            # against Fortnox or Stripe for the tenant. Matches the
            # anonymisation scrub performed in delete_organization().
            if c.name not in _SECRET_COLUMNS
        }
    if isinstance(obj, datetime):
        return obj.astimezone(timezone.utc).isoformat()
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    return obj


# Column names (across any model) that must be stripped from the GDPR export.
_SECRET_COLUMNS: frozenset[str] = frozenset({
    "fortnox_access_token",
    "fortnox_refresh_token",
    "fortnox_token_expiry",
    "stripe_customer_id",
})


async def _rows(db: AsyncSession, model, org_id) -> list[dict]:
    # Per-table cap on GDPR exports. A tenant with years of stock_movements
    # can legitimately have hundreds of thousands of rows; materialising
    # the full set in memory and json.dumps'ing it would OOM the worker.
    # 100k rows per table is generous (≈25 MB JSON per table at typical
    # row sizes) and covers every real Nordic-wholesaler dataset we've
    # seen. Tenants needing more data can request a full DB dump via
    # support \u2014 that path is out-of-band and streamed.
    result = await db.scalars(select(model).where(model.org_id == org_id).limit(100_001))
    rows = list(result.all())
    if len(rows) > 100_000:
        log.warning(
            "gdpr_export truncated | org_id=%s | model=%s | rows=%d",
            org_id, model.__tablename__, len(rows),
        )
        rows = rows[:100_000]
    return [_serialize(row) for row in rows]


async def _child_rows(db: AsyncSession, child_model, parent_model, org_id) -> list[dict]:
    """Fetch rows of a child model that has no org_id column, scoped via
    its parent's org_id. Used for invoice_line_items and purchase_order_items.
    """
    # Figure out the FK column connecting child → parent
    parent_table = parent_model.__tablename__
    fk_col = None
    for col in child_model.__table__.columns:
        for fk in col.foreign_keys:
            if fk.column.table.name == parent_table:
                fk_col = col
                break
        if fk_col is not None:
            break
    if fk_col is None:
        return []
    stmt = (
        select(child_model)
        .join(parent_model, getattr(child_model, fk_col.name) == parent_model.id)
        .where(parent_model.org_id == org_id)
        .limit(100_001)
    )
    result = await db.scalars(stmt)
    rows = list(result.all())
    if len(rows) > 100_000:
        log.warning(
            "gdpr_export child truncated | org_id=%s | model=%s | rows=%d",
            org_id, child_model.__tablename__, len(rows),
        )
        rows = rows[:100_000]
    return [_serialize(row) for row in rows]


@router.get("/export")
async def export_org_data(
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    """Return a JSON dump of every row scoped to the caller's organization.

    Use-case: GDPR Art. 15 right-of-access + Art. 20 data portability.
    """
    _, member = ctx
    try:
        _require_owner(ctx)
        org_id = member.org_id

        org = await db.get(Organization, org_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "organization": _serialize(org),
            "members":      await _rows(db, OrganizationMember, org_id),
            "customers":    await _rows(db, Customer,           org_id),
            "invoices":     await _rows(db, Invoice,            org_id),
            "invoice_line_items": await _child_rows(db, InvoiceLineItem, Invoice, org_id),
            "payments":     await _rows(db, Payment,            org_id),
            "products":     await _rows(db, Product,            org_id),
            "suppliers":    await _rows(db, Supplier,           org_id),
            "warehouses":   await _rows(db, Warehouse,          org_id),
            "stock_levels": await _rows(db, StockLevel,         org_id),
            "stock_movements":   await _rows(db, StockMovement, org_id),
            "purchase_orders":   await _rows(db, PurchaseOrder, org_id),
            "purchase_order_items": await _child_rows(db, PurchaseOrderItem, PurchaseOrder, org_id),
        }

        # Security-sensitive: exporting the org's full PII payload is a
        # privileged owner action. Record it so incident response can
        # correlate an export with a later data-leak claim.
        await log_action(
            db,
            action="gdpr.export",
            org_id=org_id,
            actor_user_id=member.user_id,
            target_type="organization",
            target_id=str(org_id),
            request=request,
        )
        await db.commit()

        body = json.dumps(payload, indent=2, default=str).encode("utf-8")
        filename = f"varuflow-export-{org_id}-{datetime.now(timezone.utc):%Y%m%d}.json"
        return Response(
            content=body,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("gdpr_export failed: %s", e, extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/organization", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
    x_confirm_delete: str | None = Header(default=None, alias="X-Confirm-Delete"),
):
    """GDPR Art. 17 erasure with Swedish bokföringslagen carve-out.

    Bookkeeping records (invoices, line items, payments, stock movements)
    MUST be retained for 7 years under Swedish law (BFL 7 kap. 2 §) and
    the equivalent statutes in NO / DK / FI. A hard cascade-delete would
    violate those statutes, so this endpoint performs a *logical* erasure:

      • Organization → name/org_number/vat_number/address replaced with
        placeholders; `is_active=False`; all Fortnox tokens cleared.
      • Customers    → company_name/org_number/vat_number/email/phone/
                        address replaced with placeholders; `is_active=False`.
      • Members      → removed (so the humans lose access). Rows remain
                        addressable via foreign keys but contain no PII.
      • Invoices / line items / payments → retained as-is. They reference
        the anonymised customer and organization rows.

    Requires the header `X-Confirm-Delete: DELETE` to prevent accidents.
    """
    try:
        _require_owner(ctx)
        _, member = ctx
        org_id = member.org_id

        if x_confirm_delete != "DELETE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Set header 'X-Confirm-Delete: DELETE' to confirm",
            )

        org = await db.get(Organization, org_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        log.warning(
            "gdpr_anonymise org_id=%s owner_user_id=%s",
            org_id, member.user_id,
        )

        # Anonymise the organization itself
        org.name                  = f"Deleted organization {org_id}"
        org.org_number            = None
        org.vat_number            = None
        org.address               = None
        org.fortnox_access_token  = None
        org.fortnox_refresh_token = None
        org.fortnox_token_expiry  = None
        org.is_active             = False

        # Cancel any live Stripe subscription BEFORE clearing the
        # stripe_customer_id — otherwise the org vanishes from our side
        # while Stripe keeps auto-renewing the PRO plan every month,
        # billing an owner who has no account left and no way to reach
        # the customer portal to cancel (their membership row was
        # deleted below). Failure to cancel must NOT block the erasure
        # (GDPR takes precedence) — log and continue so the owner can
        # still get their data removed even if Stripe is unreachable.
        stripe_customer_id = org.stripe_customer_id
        if stripe_customer_id:
            from app.config import settings as _settings
            if _settings.STRIPE_SECRET_KEY:
                try:
                    import stripe as _stripe
                    _stripe.api_key = _settings.STRIPE_SECRET_KEY
                    subs = _stripe.Subscription.list(
                        customer=stripe_customer_id, status="all", limit=100
                    )
                    for sub in subs.auto_paging_iter():
                        if sub.get("status") in ("active", "past_due", "trialing", "unpaid"):
                            _stripe.Subscription.delete(sub["id"])
                            log.warning(
                                "gdpr_anonymise cancelled stripe subscription",
                                extra={"org_id": str(org_id), "subscription_id": sub["id"]},
                            )
                except Exception as e:  # pragma: no cover — best-effort
                    log.error(
                        "gdpr_anonymise: stripe cancel failed (continuing erasure)",
                        extra={"org_id": str(org_id), "error": str(e)},
                    )
            # Clear the customer id so the anonymised row no longer
            # correlates to a Stripe PII record.
            org.stripe_customer_id = None

        # Anonymise all customer PII. Invoices continue to reference these
        # rows but no longer contain identifiable data.
        customers = (await db.scalars(select(Customer).where(Customer.org_id == org_id))).all()
        for c in customers:
            c.company_name = f"Deleted customer {c.id}"
            c.org_number   = None
            c.vat_number   = None
            c.email        = None
            c.phone        = None
            c.address      = None
            c.is_active    = False

        # Remove all members so the humans immediately lose access.
        members = (
            await db.scalars(select(OrganizationMember).where(OrganizationMember.org_id == org_id))
        ).all()
        for m in members:
            await db.delete(m)

        # Purge uploaded business documents. These are customer-
        # uploaded content and — unlike invoices under BFL 7 yr —
        # carry no retention obligation, so a true hard-delete is
        # both legal and correct. (Item 44.)
        from app.services import document_service as _docsvc
        documents_purged = await _docsvc.gdpr_purge_documents(db, org_id=org_id)

        await log_action(
            db,
            action="gdpr.org_anonymise",
            org_id=org_id,
            actor_user_id=member.user_id,
            target_type="organization",
            target_id=str(org_id),
            request=request,
            extra={
                "customers_anonymised": len(customers),
                "members_removed": len(members),
                "documents_purged": documents_purged,
            },
        )

        await db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except Exception as e:
        log.error("gdpr_anonymise failed: %s", e, extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Bokföringslagen compliance export ─────────────────────────────────────────
#
# Swedish bookkeeping law (bokföringslagen, BFL 7 kap. 2 §) requires
# verifications to be retained for 7 years. Tenants need a single
# machine-readable bundle they can hand to an auditor or archive
# offline. This endpoint assembles:
#   1. Every invoice as a PDF (reusing the invoice router's renderer)
#   2. The full audit trail as CSV
#   3. A condensed ledger.json summarising each invoice
# into a single ZIP archive. Owner-only — same data-controller rules as
# the rest of /api/gdpr.


@router.post("/bokforing-export")
async def bokforing_export(
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Generate a full bokföringslagen compliance ZIP for the caller's org.

    The ZIP contains:
      • ``invoices/INV-YYYY-NNNN.pdf`` for every invoice
      • ``audit_log.csv`` with the entire audit trail for the org
      • ``ledger.json`` — one object per invoice (id, date, amount, vat,
        currency, customer_name, status)

    Owner-only. Logs ``BOKFORING_EXPORT`` in the audit trail.
    """
    _, member = ctx
    try:
        _require_owner(ctx)
        org_id = member.org_id

        # Local import avoids a circular import: invoicing imports gdpr-free
        # helpers, gdpr does not otherwise reach into the invoicing router.
        from app.features.invoicing.router import _generate_invoice_pdf  # noqa: WPS433
        from sqlalchemy.orm import selectinload

        org = await db.get(Organization, org_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        # Load every invoice with the relations the PDF generator needs.
        invoices_result = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
            .where(Invoice.org_id == org_id)
            .order_by(Invoice.issue_date.asc(), Invoice.invoice_number.asc())
        )
        invoices: list[Invoice] = list(invoices_result.scalars().all())

        # Full audit log for the org.
        audit_result = await db.execute(
            select(AuditLogEntry)
            .where(AuditLogEntry.org_id == org_id)
            .order_by(AuditLogEntry.created_at.asc())
        )
        audit_rows = list(audit_result.scalars().all())

        # Assemble the ZIP in memory. A large-tenant bokföring bundle (7
        # years × thousands of invoices) can hit hundreds of MB; the
        # ReportLab rendering is the dominant cost, not the ZIP packing.
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            # 1. Invoice PDFs
            seen_pdf_names: set[str] = set()
            for inv in invoices:
                try:
                    pdf_bytes = _generate_invoice_pdf(inv)
                except Exception:  # pragma: no cover — per-invoice render failure
                    log.exception(
                        "bokforing_export: pdf render failed for invoice %s", inv.id
                    )
                    continue
                # Invoice numbers are unique per (org, invoice_number) by DB
                # constraint (v15), but defensively namespace duplicates.
                name = f"invoices/{inv.invoice_number}.pdf"
                if name in seen_pdf_names:
                    name = f"invoices/{inv.invoice_number}-{str(inv.id)[:8]}.pdf"
                seen_pdf_names.add(name)
                zf.writestr(name, pdf_bytes)

            # 2. audit_log.csv — every column stringified, extra JSON-encoded
            csv_buf = io.StringIO()
            writer = csv.writer(csv_buf)
            writer.writerow([
                "created_at", "action", "actor_user_id",
                "target_type", "target_id", "ip_address", "extra",
            ])
            for row in audit_rows:
                writer.writerow([
                    row.created_at.astimezone(timezone.utc).isoformat()
                    if row.created_at else "",
                    row.action or "",
                    str(row.actor_user_id) if row.actor_user_id else "",
                    row.target_type or "",
                    row.target_id or "",
                    row.ip_address or "",
                    json.dumps(row.extra or {}, default=str, ensure_ascii=False),
                ])
            zf.writestr("audit_log.csv", csv_buf.getvalue())

            # 3. ledger.json — condensed per-invoice summary
            ledger = [
                {
                    "invoice_id": str(inv.id),
                    "invoice_number": inv.invoice_number,
                    "date": inv.issue_date.isoformat() if inv.issue_date else None,
                    "due_date": inv.due_date.isoformat() if inv.due_date else None,
                    "amount": str(inv.total_sek),
                    "subtotal": str(inv.subtotal),
                    "vat": str(inv.vat_amount),
                    "currency": "SEK",
                    "customer_name": inv.customer.company_name if inv.customer else None,
                    "status": inv.status.value if hasattr(inv.status, "value") else str(inv.status),
                }
                for inv in invoices
            ]
            zf.writestr(
                "ledger.json",
                json.dumps(ledger, indent=2, ensure_ascii=False, default=str),
            )

            # Small manifest so auditors know what they're looking at.
            zf.writestr(
                "README.txt",
                (
                    "Varuflow bokföringslagen compliance export\n"
                    f"Organization: {org.name}\n"
                    f"Organization ID: {org_id}\n"
                    f"Generated: {datetime.now(timezone.utc).isoformat()}\n"
                    f"Invoices: {len(invoices)}\n"
                    f"Audit log rows: {len(audit_rows)}\n"
                    "\n"
                    "Retention note: Swedish BFL 7 kap. 2 § requires these\n"
                    "records to be kept for 7 years after the fiscal year end.\n"
                ),
            )

        zip_bytes = buf.getvalue()
        year = datetime.now(timezone.utc).year
        filename = f"varuflow-bokforing-{org_id}-{year}.zip"

        await log_action(
            db,
            action="BOKFORING_EXPORT",
            org_id=org_id,
            actor_user_id=member.user_id,
            target_type="organization",
            target_id=str(org_id),
            request=request,
            extra={
                "invoice_count": len(invoices),
                "audit_rows": len(audit_rows),
                "size_bytes": len(zip_bytes),
                "year": year,
            },
        )
        await db.commit()

        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("bokforing_export failed: %s", e, extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
