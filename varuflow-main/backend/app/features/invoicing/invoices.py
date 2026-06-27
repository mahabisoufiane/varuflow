"""Invoicing routes: invoices, send, deposit receipt, PDF/Peppol/EHF download."""
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Response,
    status,
)
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db, scoped_select
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_role
from app.features.portal.idempotency import IdempotencyKey
from app.features.auth.organization import OrgRole
from .models import (
    Customer,
    Invoice,
    InvoiceLineItem,
    InvoiceStatus,
)
from .schemas import (
    InvoiceCreate,
    InvoiceOut,
    InvoiceStatusUpdate,
    InvoiceSummary,
)
from app.services.audit import log_action
from app.services.plan_limits import (
    RESOURCE_INVOICES_PER_MONTH,
    LimitExceededError,
    check_limit,
)

from ._shared import (
    _check_invoice_email_cooldown,
    _generate_ehf_xml,
    _generate_invoice_pdf,
    _generate_peppol_xml,
    _invoice_number,
    _org,
)

log = logging.getLogger(__name__)
router = APIRouter()


# ── Invoices ──────────────────────────────────────────────────────────────────

@router.get("/invoices", response_model=list[InvoiceSummary])
async def list_invoices(
    status: InvoiceStatus | None = Query(None),
    customer_id: uuid.UUID | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        q = (
            scoped_select(Invoice, org_id)
            .options(selectinload(Invoice.customer))
        )
        if status:
            q = q.where(Invoice.status == status)
        if customer_id:
            q = q.where(Invoice.customer_id == customer_id)
        q = q.order_by(Invoice.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(q)
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_invoices failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/invoices", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    body: InvoiceCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        description="Client-supplied retry key. If provided, a second POST with the same key returns the originally-created invoice instead of creating a duplicate.",
        max_length=255,
    ),
):
    org_id = _org(ctx)

    # ── Idempotency: return existing resource if this key was already used ───
    # Acquire the slot FIRST (INSERT ON CONFLICT DO NOTHING). Only the
    # request that actually wrote the row proceeds to mint a new invoice
    # number — otherwise two concurrent POSTs with the same key would both
    # consume an invoice number before the loser's second INSERT hit the
    # uniqueness constraint.
    key_norm = None
    if idempotency_key:
        key_norm = idempotency_key.strip() or None
    if key_norm:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        slot = await db.execute(
            pg_insert(IdempotencyKey.__table__)
            .values(
                org_id=org_id,
                endpoint="create_invoice",
                key=key_norm,
                target_id="pending",
            )
            .on_conflict_do_nothing(index_elements=["org_id", "endpoint", "key"])
        )
        if slot.rowcount == 0:
            # Another request already owns this key — return its invoice.
            existing = await db.scalar(
                select(IdempotencyKey).where(
                    IdempotencyKey.org_id == org_id,
                    IdempotencyKey.endpoint == "create_invoice",
                    IdempotencyKey.key == key_norm,
                )
            )
            if existing and existing.target_id != "pending":
                prior = await db.execute(
                    scoped_select(Invoice, org_id)
                    .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
                    .where(Invoice.id == uuid.UUID(existing.target_id))
                )
                inv_prior = prior.scalar_one_or_none()
                if inv_prior:
                    return inv_prior
            # Either the winner is still mid-flight ("pending") or its
            # invoice was deleted; treat as a conflict the client should
            # retry with a fresh key.
            raise HTTPException(
                status_code=409,
                detail="Idempotency key is in use or refers to a missing invoice — please retry",
            )

    # ── Plan limit: max invoices per month ────────────────────────────────────
    from .models import Invoice as _Invoice
    from app.features.auth.organization import Organization as _OrgPlan
    _now = datetime.now(UTC)
    _month_start = _now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    _inv_this_month = await db.scalar(
        select(func.count()).select_from(_Invoice).where(
            _Invoice.org_id == org_id,
            _Invoice.created_at >= _month_start,
        )
    ) or 0
    _org_obj = await db.get(_OrgPlan, org_id)
    if _org_obj:
        try:
            check_limit(_org_obj.plan, RESOURCE_INVOICES_PER_MONTH, _inv_this_month)
        except LimitExceededError as _exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PLAN_LIMIT_EXCEEDED",
                    "resource": RESOURCE_INVOICES_PER_MONTH,
                    "current_plan": _org_obj.plan.value,
                    "limit": _exc.limit,
                    "current": _exc.current,
                },
            )
    # ──────────────────────────────────────────────────────────────────────────
    # Verify customer belongs to org
    customer = await db.scalar(
        select(Customer).where(Customer.id == body.customer_id, Customer.org_id == org_id)
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    # `DELETE /customers/{id}` is a soft-delete that flips is_active=False —
    # the UI surfaces this as "Delete customer". Without this guard the
    # backend happily mints a new invoice against an archived customer
    # every time the client forgets to filter the customer picker, which
    # then shows up on the customer's portal, in reminders, and in the
    # VAT report. The merchant must explicitly PUT is_active=true first.
    if not customer.is_active:
        raise HTTPException(
            status_code=422,
            detail="Customer is archived — reactivate before creating new invoices.",
        )

    # Validate every product_id referenced in line items belongs to this org.
    # Invoice schemas allow product_id=None (free-text lines) — only verify
    # the subset that supplied one.
    referenced_product_ids = {li.product_id for li in body.items if li.product_id is not None}
    if referenced_product_ids:
        from app.features.inventory.models import Product as _Product
        rows = await db.execute(
            select(_Product.id).where(
                _Product.id.in_(referenced_product_ids),
                _Product.org_id == org_id,
            )
        )
        valid_ids = {r[0] for r in rows.all()}
        missing = referenced_product_ids - valid_ids
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"Product(s) not found in your organisation: {', '.join(str(m) for m in list(missing)[:5])}",
            )

    # Generate invoice number from max-existing-sequence.
    #
    # Serialize on the Organization row before reading so two concurrent
    # create_invoice calls don't both observe the same max and both write
    # INV-YYYY-(N+1). DB-level UNIQUE(org_id, invoice_number) (migration
    # v15) is the ultimate safety net, but the row lock avoids wasteful
    # IntegrityError retries on the hot path.
    #
    # Using MAX(sequence) instead of COUNT(*) is REQUIRED by Swedish
    # bokföringslagen (BFL): invoice numbers must be gap-free and never
    # reusable. A COUNT-based scheme reused a number whenever a DRAFT
    # invoice was deleted, violating the law and tripping the UNIQUE
    # constraint when the old number was already live.
    from app.features.auth.organization import Organization as _Org
    await db.execute(
        select(_Org.id).where(_Org.id == org_id).with_for_update()
    )
    year = datetime.now(UTC).year
    year_prefix = f"INV-{year}-"
    max_row = await db.scalar(
        select(func.max(Invoice.invoice_number))
        .where(
            Invoice.org_id == org_id,
            Invoice.invoice_number.like(f"{year_prefix}%"),
        )
    )
    next_seq = 1
    if max_row:
        try:
            next_seq = int(max_row.rsplit("-", 1)[-1]) + 1
        except (ValueError, IndexError):
            next_seq = 1
    inv_number = _invoice_number(org_id, next_seq)

    # Compute totals
    subtotal = Decimal("0.00")
    vat_amount = Decimal("0.00")
    line_items = []
    for li in body.items:
        line_total = (li.quantity * li.unit_price).quantize(Decimal("0.01"))
        vat = (line_total * li.tax_rate / 100).quantize(Decimal("0.01"))
        subtotal += line_total
        vat_amount += vat
        line_items.append(
            InvoiceLineItem(
                product_id=li.product_id,
                description=li.description,
                quantity=li.quantity,
                unit_price=li.unit_price,
                tax_rate=li.tax_rate,
                line_total=line_total,
            )
        )

    invoice = Invoice(
        org_id=org_id,
        customer_id=body.customer_id,
        invoice_number=inv_number,
        issue_date=body.issue_date,
        due_date=body.due_date,
        status=InvoiceStatus.DRAFT,
        subtotal=subtotal,
        vat_amount=vat_amount,
        total_sek=(subtotal + vat_amount).quantize(Decimal("0.01")),
        notes=body.notes,
        line_items=line_items,
        invoice_type=body.invoice_type,
        parent_invoice_id=body.parent_invoice_id,
    )

    # Deposit: the invoice itself IS the deposit; record its total as deposit_amount
    if body.invoice_type == "deposit":
        invoice.deposit_amount = (subtotal + vat_amount).quantize(Decimal("0.01"))
    elif body.invoice_type == "final":
        # Use explicitly provided deposit_amount, or look it up from parent invoice
        if body.deposit_amount is not None:
            invoice.deposit_amount = Decimal(str(body.deposit_amount)).quantize(Decimal("0.01"))
        elif body.parent_invoice_id:
            parent_inv = await db.scalar(
                scoped_select(Invoice, org_id).where(
                    Invoice.id == body.parent_invoice_id,
                )
            )
            if parent_inv and parent_inv.deposit_amount:
                invoice.deposit_amount = parent_inv.deposit_amount
    db.add(invoice)
    await db.commit()

    # Backfill the idempotency slot's target_id now that we have one.
    if key_norm:
        from sqlalchemy import update as _update
        await db.execute(
            _update(IdempotencyKey)
            .where(
                IdempotencyKey.org_id == org_id,
                IdempotencyKey.endpoint == "create_invoice",
                IdempotencyKey.key == key_norm,
            )
            .values(target_id=str(invoice.id))
        )
        await db.commit()

    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(Invoice.id == invoice.id)
    )
    return result.scalar_one()


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
async def get_invoice(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    result = await db.execute(
        scoped_select(Invoice, org_id)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


@router.patch("/invoices/{invoice_id}/status", response_model=InvoiceOut)
async def update_invoice_status(
    invoice_id: uuid.UUID,
    body: InvoiceStatusUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    # Lock the invoice row so two concurrent PATCHes can't both read the
    # same current status and both succeed (e.g. DRAFT → SENT and
    # DRAFT → PAID simultaneously, bypassing the transition guard).
    inv = await db.scalar(
        scoped_select(Invoice, org_id)
        .where(Invoice.id == invoice_id)
        .with_for_update()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    allowed: dict[InvoiceStatus, list[InvoiceStatus]] = {
        InvoiceStatus.DRAFT: [InvoiceStatus.SENT],
        InvoiceStatus.SENT: [InvoiceStatus.PAID, InvoiceStatus.OVERDUE],
        InvoiceStatus.OVERDUE: [InvoiceStatus.PAID],
        InvoiceStatus.PAID: [],
    }
    if body.status not in allowed[inv.status]:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot transition from {inv.status} to {body.status}",
        )
    previous_status = inv.status
    transitioning_to_overdue = (
        inv.status == InvoiceStatus.SENT and body.status == InvoiceStatus.OVERDUE
    )
    inv.status = body.status
    await db.commit()

    _, member = ctx
    await log_action(
        db,
        action="invoice.status_updated",
        org_id=org_id,
        actor_user_id=member.user_id,
        target_type="invoice",
        target_id=str(invoice_id),
        extra={"from": previous_status.value if hasattr(previous_status, "value") else str(previous_status),
               "to": body.status.value if hasattr(body.status, "value") else str(body.status)},
    )
    await db.commit()

    # Kick off dunning stage 1 on manual SENT→OVERDUE transition.
    # The nightly sweep handles batch dunning; this covers manual overrides.
    if transitioning_to_overdue:
        try:
            from datetime import date as _date

            from app.features.auth.organization import Organization as _Org
            from app.services.dunning import (
                dispatch_dunning_channels,
                record_dunning_event,
                stage_for_days_overdue,
            )
            days_ov = ((_date.today() - inv.due_date.date()) if inv.due_date else 0).days if inv.due_date else 0
            stage = stage_for_days_overdue(days_ov, inv.dunning_stage or 0) or 1
            customer = await db.scalar(select(Customer).where(Customer.id == inv.customer_id))
            org_obj = await db.get(_Org, org_id)
            inserted = await record_dunning_event(db, org_id=org_id, invoice=inv, stage=stage, trigger="manual_status_change")
            if inserted and customer and org_obj:
                await dispatch_dunning_channels(db, invoice=inv, customer=customer, org=org_obj, stage=stage, days_overdue=days_ov, trigger="manual_status_change")
            await db.commit()
        except Exception as dun_err:
            log.error("dunning dispatch failed on manual overdue", extra={"invoice_id": str(invoice_id), "error": str(dun_err)})

    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id)
    )
    return result.scalar_one()


@router.delete(
    "/invoices/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    # RBAC (M6): hard-deleting a numbered financial document is a
    # destructive, org-shared action — restrict to ADMIN+ rather than any
    # authenticated MEMBER. Matches the codebase's "finance is ADMIN"
    # precedent (accounting/payroll/reconciliation routers are all
    # require_role(ADMIN)). Test fixtures run as OWNER (rank 2 > ADMIN),
    # so this does not affect the existing suite.
    dependencies=[Depends(require_role(OrgRole.ADMIN))],
)
async def delete_invoice(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    # Lock the invoice row so a concurrent PATCH /status cannot flip it out
    # of DRAFT between our check and the DELETE.
    inv = await db.scalar(
        scoped_select(Invoice, org_id)
        .where(Invoice.id == invoice_id)
        .with_for_update()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status != InvoiceStatus.DRAFT:
        raise HTTPException(status_code=422, detail="Only DRAFT invoices can be deleted")
    await db.delete(inv)
    await db.commit()



# ── Send by email ─────────────────────────────────────────────────────────────

@router.post("/invoices/{invoice_id}/send", status_code=status.HTTP_200_OK)
async def send_invoice_email(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Send the invoice PDF to the customer's email via Resend."""
    from app.features.auth.organization import Organization
    from app.services.email import send_invoice_email as _send

    org_id = _org(ctx)
    result = await db.execute(
        scoped_select(Invoice, org_id)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not inv.customer.email:
        raise HTTPException(status_code=422, detail="Customer has no email address")
    if inv.status == InvoiceStatus.DRAFT:
        raise HTTPException(status_code=422, detail="Cannot send a DRAFT invoice — mark it Sent first")

    # Rate-limit repeated sends of the same invoice so an abusive session
    # can't spam the customer's inbox.
    _check_invoice_email_cooldown(org_id, invoice_id, "send")

    org = await db.get(Organization, org_id)
    pdf_bytes = _generate_invoice_pdf(inv)

    sent = await _send(
        to_email=inv.customer.email,
        customer_name=inv.customer.company_name,
        invoice_number=inv.invoice_number,
        total_sek=f"{inv.total_sek:.2f}",
        due_date=str(inv.due_date),
        pdf_bytes=pdf_bytes,
        org_name=org.name if org else "Varuflow",
    )

    if not sent:
        return {"status": "skipped", "reason": "Resend not configured — add RESEND_API_KEY to backend .env"}
    return {"status": "sent", "to": inv.customer.email}


# ── Deposit receipt ───────────────────────────────────────────────────────────

@router.post("/invoices/{invoice_id}/deposit-receipt", status_code=status.HTTP_200_OK)
async def send_deposit_receipt(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Email a deposit payment receipt to the customer."""
    from app.features.auth.organization import Organization
    from app.services.email import send_invoice_email as _send

    org_id = _org(ctx)
    result = await db.execute(
        scoped_select(Invoice, org_id)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if getattr(inv, "invoice_type", "standard") != "deposit":
        raise HTTPException(status_code=422, detail="This endpoint is only for deposit invoices")
    if inv.status not in (InvoiceStatus.PAID,):
        raise HTTPException(status_code=422, detail="Deposit must be marked PAID before sending a receipt")
    if not inv.customer.email:
        raise HTTPException(status_code=422, detail="Customer has no email address")

    _check_invoice_email_cooldown(org_id, invoice_id, "deposit-receipt")

    org = await db.get(Organization, org_id)
    pdf_bytes = _generate_invoice_pdf(inv)
    sent = await _send(
        to_email=inv.customer.email,
        customer_name=inv.customer.company_name,
        invoice_number=f"{inv.invoice_number} (Deposit Receipt)",
        total_sek=f"{inv.total_sek:.2f}",
        due_date=str(inv.due_date),
        pdf_bytes=pdf_bytes,
        org_name=org.name if org else "Varuflow",
    )
    if not sent:
        return {"status": "skipped", "reason": "Resend not configured"}
    return {"status": "sent", "to": inv.customer.email}



# ── PDF ───────────────────────────────────────────────────────────────────────

@router.get("/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    _, member = ctx
    result = await db.execute(
        scoped_select(Invoice, org_id)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    pdf_bytes = _generate_invoice_pdf(inv)
    filename = f"{inv.invoice_number}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )



# ── Peppol UBL 2.1 XML export ─────────────────────────────────────────────────

@router.get("/invoices/{invoice_id}/peppol")
async def download_peppol_xml(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Export invoice as Peppol BIS Billing 3.0 (UBL 2.1) XML."""
    from app.features.auth.organization import Organization

    org_id = _org(ctx)
    result = await db.execute(
        scoped_select(Invoice, org_id)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    org = await db.get(Organization, org_id)
    xml_bytes = _generate_peppol_xml(inv, org)
    filename = f"{inv.invoice_number}-peppol.xml"
    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )



# ── Norwegian EHF 3.0 XML export ─────────────────────────────────────────────

@router.get("/invoices/{invoice_id}/ehf")
async def download_ehf_xml(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Export invoice as Norwegian EHF Billing 3.0 (Peppol BIS/PEPPOL-BIS-3 for Norway)."""
    from app.features.auth.organization import Organization

    org_id = _org(ctx)
    result = await db.execute(
        scoped_select(Invoice, org_id)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    org = await db.get(Organization, org_id)
    xml_bytes = _generate_ehf_xml(inv, org)
    filename = f"{inv.invoice_number}-ehf.xml"
    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Bulk discount ─────────────────────────────────────────────────────────────

class _BulkDiscountBody(BaseModel):
    kind: str
    value: Decimal
    selected_ids: list[str] | None = None


@router.post(
    "/invoices/{invoice_id}/bulk-discount",
    status_code=200,
)
async def bulk_discount_invoice(
    invoice_id: uuid.UUID,
    body: _BulkDiscountBody,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    from app.services.bulk_discount import (
        LineIn,
        apply_bulk_discount,
        compute_totals,
    )

    _, member = ctx
    org_id = _org(ctx)
    result = await db.execute(
        scoped_select(Invoice, org_id)
        .options(selectinload(Invoice.line_items))
        .where(Invoice.org_id == org_id)
        .where(Invoice.id == invoice_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status != InvoiceStatus.DRAFT:
        raise HTTPException(status_code=409, detail="can only discount DRAFT invoices")
    if not inv.line_items:
        raise HTTPException(status_code=422, detail="invoice has no lines")

    lines_in = [
        LineIn(
            id=str(row.id),
            quantity=row.quantity,
            unit_price=row.unit_price,
            tax_rate=row.tax_rate,
        )
        for row in inv.line_items
    ]
    selected = set(body.selected_ids) if body.selected_ids is not None else None
    try:
        lines_out = apply_bulk_discount(
            lines_in, kind=body.kind, value=body.value, selected_ids=selected
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    line_map = {row.id: row for row in inv.line_items}
    for o in lines_out:
        row = line_map[uuid.UUID(o.id)]
        row.unit_price = o.unit_price
        row.line_total = o.line_total

    totals = compute_totals(lines_in, lines_out)
    inv.subtotal = totals.subtotal
    inv.vat_amount = totals.vat_amount
    inv.total_sek = totals.total
    await db.commit()

    await log_action(
        db,
        action="invoice.bulk_discount_applied",
        org_id=org_id,
        actor_user_id=member.user_id,
        target_type="invoice",
        target_id=str(invoice_id),
        extra={"kind": body.kind, "value": str(body.value)},
    )
    await db.commit()
    return {"ok": True, "lines_updated": sum(1 for o in lines_out if o.changed)}

