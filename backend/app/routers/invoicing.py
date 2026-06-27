"""Invoicing module: customers, invoices, payments, aging report, PDF."""
import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO
from typing import Optional
from xml.sax.saxutils import escape as _xml_escape

log = logging.getLogger(__name__)


# ── Per-invoice outbound-email cooldown ───────────────────────────────────────
#
# In-process throttle keyed by (org_id, invoice_id, kind) to stop an
# authenticated but abusive session from spamming the same customer with
# repeated `/send` or `/payment-link` emails. A 60-second window is more
# than enough to cover UI double-clicks and retry-after-error scenarios
# while capping abuse at roughly 1 email/minute/invoice.
#
# Single-process only (good enough: Railway runs one worker per instance
# and abusive bursts are per-session). For multi-worker we'd move this
# to Postgres with an UPSERT check; flagged for later if we scale out.
import time as _time_mod
_EMAIL_COOLDOWN_SECS = 60
_invoice_email_cooldown: dict[tuple[str, str, str], float] = {}


def _check_invoice_email_cooldown(org_id: uuid.UUID, invoice_id: uuid.UUID, kind: str) -> None:
    key = (str(org_id), str(invoice_id), kind)
    now = _time_mod.monotonic()
    prev = _invoice_email_cooldown.get(key, 0.0)
    if now - prev < _EMAIL_COOLDOWN_SECS:
        retry = int(_EMAIL_COOLDOWN_SECS - (now - prev)) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {retry}s before resending this invoice.",
        )
    _invoice_email_cooldown[key] = now
    # Bound memory: if the dict gets big, evict entries older than the
    # cooldown window. Happens at O(N) but only when we're over 10k keys,
    # which is already pathological.
    if len(_invoice_email_cooldown) > 10_000:
        cutoff = now - _EMAIL_COOLDOWN_SECS * 2
        for k in [k for k, t in _invoice_email_cooldown.items() if t < cutoff]:
            _invoice_email_cooldown.pop(k, None)


def _pdf_esc(v) -> str:
    """Escape a user-supplied string for safe embedding in a ReportLab
    Paragraph. ReportLab parses its input as mini-XML, so raw ``<``/``&`` in
    customer data (company name, address, invoice description, notes, …)
    either breaks rendering or lets the data alter the document's markup.
    Always wrap untrusted text with this helper before ``Paragraph(...)``.
    """
    return _xml_escape("" if v is None else str(v))

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.idempotency import IdempotencyKey
from app.models.invoicing import (
    Customer,
    Invoice,
    InvoiceLineItem,
    InvoiceStatus,
    Payment,
    PaymentMethod,
)
from app.schemas.invoicing import (
    AgingBucket,
    AgingReport,
    CustomerCreate,
    CustomerOut,
    CustomerUpdate,
    InvoiceCreate,
    InvoiceOut,
    InvoiceStatusUpdate,
    InvoiceSummary,
    PaymentCreate,
    PaymentOut,
)
from app.services.plan_limits import RESOURCE_INVOICES_PER_MONTH, LimitExceededError, check_limit

router = APIRouter(prefix="/api/invoicing", tags=["invoicing"])

NAVY = colors.HexColor("#1a2332")
LIGHT_GRAY = colors.HexColor("#f3f4f6")


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _invoice_number(org_id: uuid.UUID, sequence: int) -> str:
    year = datetime.now(timezone.utc).year
    return f"INV-{year}-{sequence:04d}"


# ── Customers ─────────────────────────────────────────────────────────────────

@router.get("/customers", response_model=list[CustomerOut])
async def list_customers(
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    q = select(Customer).where(Customer.org_id == org_id)
    if search:
        like = f"%{search}%"
        q = q.where(
            Customer.company_name.ilike(like) | Customer.email.ilike(like)
        )
    if is_active is not None:
        q = q.where(Customer.is_active == is_active)
    q = q.order_by(Customer.company_name).limit(limit).offset(offset)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/customers", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
async def create_customer(
    body: CustomerCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    customer = Customer(org_id=org_id, **body.model_dump())
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.get("/customers/{customer_id}", response_model=CustomerOut)
async def get_customer(
    customer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    c = await db.scalar(
        select(Customer).where(Customer.id == customer_id, Customer.org_id == org_id)
    )
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return c


@router.put("/customers/{customer_id}", response_model=CustomerOut)
async def update_customer(
    customer_id: uuid.UUID,
    body: CustomerUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    c = await db.scalar(
        select(Customer).where(Customer.id == customer_id, Customer.org_id == org_id)
    )
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    # Partial-update semantics: only overwrite columns the client actually
    # supplied. Without exclude_unset, `CustomerUpdate`'s schema defaults
    # (payment_terms_days=30, email/phone/etc. -> None) silently overwrite
    # every unspecified field — so a PUT that only wants to rename the
    # customer wipes their contact info and resets payment terms to 30.
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    await db.commit()
    await db.refresh(c)
    return c


@router.delete("/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_customer(
    customer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    c = await db.scalar(
        select(Customer).where(Customer.id == customer_id, Customer.org_id == org_id)
    )
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    c.is_active = False
    await db.commit()


# ── Invoices ──────────────────────────────────────────────────────────────────

@router.get("/invoices", response_model=list[InvoiceSummary])
async def list_invoices(
    status: Optional[InvoiceStatus] = Query(None),
    customer_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    q = (
        select(Invoice)
        .options(selectinload(Invoice.customer))
        .where(Invoice.org_id == org_id)
    )
    if status:
        q = q.where(Invoice.status == status)
    if customer_id:
        q = q.where(Invoice.customer_id == customer_id)
    q = q.order_by(Invoice.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/invoices", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    body: InvoiceCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    idempotency_key: Optional[str] = Header(
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
                    select(Invoice)
                    .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
                    .where(Invoice.id == uuid.UUID(existing.target_id), Invoice.org_id == org_id)
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
    from app.models.invoicing import Invoice as _Invoice
    from app.models.organization import Organization as _OrgPlan
    _now = datetime.now(timezone.utc)
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
        from app.models.inventory import Product as _Product
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
    from app.models.organization import Organization as _Org
    await db.execute(
        select(_Org.id).where(_Org.id == org_id).with_for_update()
    )
    year = datetime.now(timezone.utc).year
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
                select(Invoice).where(
                    Invoice.id == body.parent_invoice_id,
                    Invoice.org_id == org_id,
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
        select(Invoice)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id, Invoice.org_id == org_id)
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
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.org_id == org_id)
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
    inv.status = body.status
    await db.commit()

    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id)
    )
    return result.scalar_one()


@router.delete("/invoices/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    # Lock the invoice row so a concurrent PATCH /status cannot flip it out
    # of DRAFT between our check and the DELETE.
    inv = await db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.org_id == org_id)
        .with_for_update()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status != InvoiceStatus.DRAFT:
        raise HTTPException(status_code=422, detail="Only DRAFT invoices can be deleted")
    await db.delete(inv)
    await db.commit()


# ── Payments ──────────────────────────────────────────────────────────────────

@router.get("/invoices/{invoice_id}/payments")
async def list_payments(
    invoice_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    inv = await db.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == org_id)
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    base = select(Payment).where(Payment.invoice_id == invoice_id)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    result = await db.execute(
        base.order_by(Payment.payment_date)
        .offset((page - 1) * limit)
        .limit(limit)
    )
    items = result.scalars().all()
    total_pages = max(1, -(-total // limit))
    return {
        "items": items,
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


@router.post(
    "/invoices/{invoice_id}/payments",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
)
async def record_payment(
    invoice_id: uuid.UUID,
    body: PaymentCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    # Lock the invoice row to serialise concurrent payment inserts and prevent
    # two racing requests from both exceeding the balance.
    inv = await db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.org_id == org_id)
        .with_for_update()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status == InvoiceStatus.DRAFT:
        raise HTTPException(status_code=422, detail="Cannot record payment on a DRAFT invoice")

    # Sanity-check the payment date. Pydantic only enforces the type, so
    # without these guards an operator typo ("2099-12-31") or a client
    # bug can flip an invoice to PAID in a VAT period that hasn't
    # happened yet (analytics exports and reconciliations will then
    # disagree with the cashbook), and a pre-issue payment date breaks
    # the chronology required by Swedish bokföringslagen 5 kap. 6 §.
    today = date.today()
    if body.payment_date > today:
        raise HTTPException(
            status_code=422,
            detail="Payment date cannot be in the future.",
        )
    if body.payment_date < inv.issue_date:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Payment date {body.payment_date} is before the invoice "
                f"issue date {inv.issue_date}."
            ),
        )

    # Check existing payments BEFORE inserting the new one so we can reject
    # over-payments that would drive the outstanding balance negative.
    existing_paid_result = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.invoice_id == invoice_id
        )
    )
    existing_paid = Decimal(str(existing_paid_result or 0))
    new_total = existing_paid + body.amount
    if new_total > inv.total_sek:
        remaining = inv.total_sek - existing_paid
        raise HTTPException(
            status_code=422,
            detail=(
                f"Payment exceeds invoice balance "
                f"({remaining} SEK remaining). "
                "Record a credit note instead."
            ),
        )

    payment = Payment(
        org_id=org_id,
        invoice_id=invoice_id,
        **body.model_dump(),
    )
    db.add(payment)

    # Auto-mark PAID if payment covers full amount
    if new_total >= inv.total_sek:
        inv.status = InvoiceStatus.PAID

    await db.commit()
    await db.refresh(payment)
    return payment


# ── Aging report ──────────────────────────────────────────────────────────────

@router.get("/aging", response_model=AgingReport)
async def aging_report(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    today = date.today()

    # Cap the report at a sane upper bound so a tenant with tens of thousands
    # of outstanding invoices cannot OOM the API process.
    AGING_MAX_INVOICES = 5000

    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer))
        .where(
            Invoice.org_id == org_id,
            Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE]),
        )
        .order_by(Invoice.due_date.asc())
        .limit(AGING_MAX_INVOICES)
    )
    invoices = result.scalars().all()

    # Sum payments per invoice in a single grouped query so the aging bucket
    # reflects the true outstanding balance (gross − paid) rather than the
    # invoice gross. Partially-paid invoices were previously inflating totals.
    paid_by_invoice: dict[uuid.UUID, Decimal] = {}
    if invoices:
        inv_ids = [inv.id for inv in invoices]
        pay_rows = await db.execute(
            select(Payment.invoice_id, func.coalesce(func.sum(Payment.amount), 0))
            .where(Payment.invoice_id.in_(inv_ids))
            .group_by(Payment.invoice_id)
        )
        for inv_id, total in pay_rows.all():
            paid_by_invoice[inv_id] = Decimal(str(total or 0))

    buckets: dict[str, list[AgingBucket]] = {
        "current": [],
        "days_1_30": [],
        "days_31_60": [],
        "days_61_90": [],
        "days_90_plus": [],
    }
    total_outstanding = Decimal("0.00")

    for inv in invoices:
        paid = paid_by_invoice.get(inv.id, Decimal("0"))
        outstanding = inv.total_sek - paid
        # Skip fully-paid invoices that haven't been marked PAID yet (edge
        # case — should be rare now that record_payment auto-marks PAID).
        if outstanding <= 0:
            continue
        days_overdue = (today - inv.due_date).days
        bucket = AgingBucket(
            customer=inv.customer.company_name,
            invoice_number=inv.invoice_number,
            invoice_id=inv.id,
            total_sek=outstanding,
            due_date=inv.due_date,
            days_overdue=max(0, days_overdue),
        )
        total_outstanding += outstanding
        if days_overdue <= 0:
            buckets["current"].append(bucket)
        elif days_overdue <= 30:
            buckets["days_1_30"].append(bucket)
        elif days_overdue <= 60:
            buckets["days_31_60"].append(bucket)
        elif days_overdue <= 90:
            buckets["days_61_90"].append(bucket)
        else:
            buckets["days_90_plus"].append(bucket)

    return AgingReport(**buckets, total_outstanding=total_outstanding)


# ── Send by email ─────────────────────────────────────────────────────────────

@router.post("/invoices/{invoice_id}/send", status_code=status.HTTP_200_OK)
async def send_invoice_email(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Send the invoice PDF to the customer's email via Resend."""
    from app.services.email import send_invoice_email as _send
    from app.models.organization import Organization

    org_id = _org(ctx)
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id, Invoice.org_id == org_id)
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
    from app.services.email import send_invoice_email as _send
    from app.models.organization import Organization

    org_id = _org(ctx)
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id, Invoice.org_id == org_id)
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
        select(Invoice)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id, Invoice.org_id == org_id)
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


def _tax_subtotals_by_rate(inv: Invoice) -> list[tuple[Decimal, Decimal, Decimal]]:
    """Group invoice lines by `tax_rate` and return one subtotal per rate.

    Returns a list of ``(rate, taxable_amount, tax_amount)`` tuples ordered
    by rate. Peppol BIS 3.0 validators enforce
    ``TaxableAmount * Percent / 100 == TaxAmount`` per ``<TaxSubtotal>`` and
    require one entry per distinct rate. Hardcoding a single 25% category
    breaks on every non-25% line item (Swedish 12% food, 6% books;
    Norwegian 15% food) and the receiver silently rejects the submission.
    """
    buckets: dict[Decimal, list[Decimal]] = {}
    for li in inv.line_items:
        rate = Decimal(li.tax_rate)
        taxable = Decimal(li.line_total)
        tax_amt = (taxable * rate / Decimal(100)).quantize(Decimal("0.01"))
        bucket = buckets.setdefault(rate, [Decimal("0.00"), Decimal("0.00")])
        bucket[0] += taxable
        bucket[1] += tax_amt
    return [(rate, vals[0], vals[1]) for rate, vals in sorted(buckets.items())]


def _generate_invoice_pdf(inv: Invoice) -> bytes:
    """Render the invoice as a branded A4 PDF using ReportLab.

    The function header was previously lost during a refactor, leaving this
    body as unreachable dead code inside `_tax_subtotals_by_rate`. Every
    call site (/invoices/{id}/pdf, /invoices/{id}/send, the portal PDF
    download) then raised NameError → 500 to the customer.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("T", parent=styles["Heading1"], textColor=NAVY, fontSize=18, spaceAfter=4)
    sub_style = ParagraphStyle("S", parent=styles["Normal"], textColor=colors.gray, fontSize=9)
    label_style = ParagraphStyle("L", parent=styles["Normal"], textColor=NAVY, fontSize=9, fontName="Helvetica-Bold")
    body_style = ParagraphStyle("B", parent=styles["Normal"], fontSize=9)

    c = inv.customer
    elements = []

    # Header
    elements.append(Paragraph(f"Invoice {_pdf_esc(inv.invoice_number)}", title_style))
    elements.append(Paragraph(
        f"Issued: {_pdf_esc(inv.issue_date)} · Due: {_pdf_esc(inv.due_date)} · Status: {_pdf_esc(inv.status)}",
        sub_style,
    ))
    elements.append(Spacer(1, 8 * mm))

    # Bill to
    elements.append(Paragraph("Bill To", label_style))
    elements.append(Paragraph(_pdf_esc(c.company_name), body_style))
    if c.org_number:
        elements.append(Paragraph(f"Org nr: {_pdf_esc(c.org_number)}", body_style))
    if c.vat_number:
        elements.append(Paragraph(f"VAT: {_pdf_esc(c.vat_number)}", body_style))
    if c.address:
        elements.append(Paragraph(_pdf_esc(c.address), body_style))
    if c.email:
        elements.append(Paragraph(_pdf_esc(c.email), body_style))
    elements.append(Spacer(1, 8 * mm))

    # Line items table
    # Table cells are rendered as literal strings (not XML-parsed) so we
    # don't escape `li.description` here; escaping would show "&amp;" etc.
    col_widths = [85 * mm, 20 * mm, 25 * mm, 20 * mm, 30 * mm]
    table_data = [["Description", "Qty", "Unit price", "VAT %", "Total (SEK)"]]
    for li in inv.line_items:
        table_data.append([
            li.description,
            str(li.quantity),
            f"{li.unit_price:.2f}",
            f"{li.tax_rate:.0f}%",
            f"{li.line_total:.2f}",
        ])

    # Subtotal / VAT / Total rows
    table_data.append(["", "", "", "Subtotal", f"{inv.subtotal:.2f}"])
    table_data.append(["", "", "", "VAT", f"{inv.vat_amount:.2f}"])
    table_data.append(["", "", "", "Total (SEK)", f"{inv.total_sek:.2f}"])

    inv_type = getattr(inv, "invoice_type", "standard")
    dep_amt = getattr(inv, "deposit_amount", None)
    has_deposit_offset = inv_type == "final" and dep_amt and Decimal(str(dep_amt)) > 0
    if has_deposit_offset:
        dep = Decimal(str(dep_amt))
        total_due = (inv.total_sek - dep).quantize(Decimal("0.01"))
        table_data.append(["", "", "", "Less deposit paid", f"-{dep:.2f}"])
        table_data.append(["", "", "", "Total due (SEK)", f"{total_due:.2f}"])

    n_summary = 5 if has_deposit_offset else 3
    bg_end = -(n_summary + 1)
    n = len(table_data)
    table = Table(table_data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, bg_end), [colors.white, LIGHT_GRAY]),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        # Summary rows bold
        ("FONTNAME", (3, n - n_summary), (-1, n - 1), "Helvetica-Bold"),
        ("LINEABOVE", (3, n - n_summary), (-1, n - n_summary), 0.5, colors.lightgrey),
        ("LINEABOVE", (3, n - 1), (-1, n - 1), 1, NAVY),
        ("GRID", (0, 0), (-1, bg_end), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ]))
    elements.append(table)

    if inv.notes:
        elements.append(Spacer(1, 8 * mm))
        elements.append(Paragraph("Notes", label_style))
        elements.append(Paragraph(_pdf_esc(inv.notes), body_style))

    doc.build(elements)
    return buffer.getvalue()


# ── Peppol UBL 2.1 XML export ─────────────────────────────────────────────────

@router.get("/invoices/{invoice_id}/peppol")
async def download_peppol_xml(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Export invoice as Peppol BIS Billing 3.0 (UBL 2.1) XML."""
    from app.models.organization import Organization

    org_id = _org(ctx)
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id, Invoice.org_id == org_id)
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


def _generate_peppol_xml(inv: Invoice, org) -> bytes:
    """Generate a Peppol BIS Billing 3.0 compliant UBL 2.1 XML invoice."""
    c = inv.customer
    org_name = org.name if org else "Varuflow"
    org_vat = org.vat_number if org and org.vat_number else "SE000000000001"

    lines_xml = ""
    for idx, li in enumerate(inv.line_items, start=1):
        lines_xml += f"""
    <cac:InvoiceLine>
      <cbc:ID>{idx}</cbc:ID>
      <cbc:InvoicedQuantity unitCode="C62">{li.quantity}</cbc:InvoicedQuantity>
      <cbc:LineExtensionAmount currencyID="SEK">{li.line_total:.2f}</cbc:LineExtensionAmount>
      <cac:Item>
        <cbc:Name>{_xml_escape(li.description)}</cbc:Name>
        <cac:ClassifiedTaxCategory>
          <cbc:ID>S</cbc:ID>
          <cbc:Percent>{li.tax_rate:.2f}</cbc:Percent>
          <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
        </cac:ClassifiedTaxCategory>
      </cac:Item>
      <cac:Price>
        <cbc:PriceAmount currencyID="SEK">{li.unit_price:.2f}</cbc:PriceAmount>
      </cac:Price>
    </cac:InvoiceLine>"""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ubl:Invoice xmlns:ubl="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
  xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
  xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0</cbc:CustomizationID>
  <cbc:ProfileID>urn:fdc:peppol.eu:2017:poacc:billing:01:1.0</cbc:ProfileID>
  <cbc:ID>{_xml_escape(inv.invoice_number)}</cbc:ID>
  <cbc:IssueDate>{inv.issue_date}</cbc:IssueDate>
  <cbc:DueDate>{inv.due_date}</cbc:DueDate>
  <cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>SEK</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cac:PartyName><cbc:Name>{_xml_escape(org_name)}</cbc:Name></cac:PartyName>
      <cac:PartyTaxScheme>
        <cbc:CompanyID>{_xml_escape(org_vat)}</cbc:CompanyID>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:PartyTaxScheme>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty>
    <cac:Party>
      <cac:PartyName><cbc:Name>{_xml_escape(c.company_name)}</cbc:Name></cac:PartyName>
      {f'<cac:PartyTaxScheme><cbc:CompanyID>{_xml_escape(c.vat_number)}</cbc:CompanyID><cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:PartyTaxScheme>' if c.vat_number else ''}
    </cac:Party>
  </cac:AccountingCustomerParty>
  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="SEK">{inv.vat_amount:.2f}</cbc:TaxAmount>
    {''.join(f'''<cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="SEK">{taxable:.2f}</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="SEK">{tax_amt:.2f}</cbc:TaxAmount>
      <cac:TaxCategory>
        <cbc:ID>S</cbc:ID>
        <cbc:Percent>{rate:.2f}</cbc:Percent>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:TaxCategory>
    </cac:TaxSubtotal>''' for rate, taxable, tax_amt in _tax_subtotals_by_rate(inv))}
  </cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="SEK">{inv.subtotal:.2f}</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="SEK">{inv.subtotal:.2f}</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="SEK">{inv.total_sek:.2f}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="SEK">{inv.total_sek:.2f}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  {lines_xml}
</ubl:Invoice>"""
    return xml.encode("utf-8")


# ── Stripe payment link ────────────────────────────────────────────────────────

class PaymentLinkOut(BaseModel):
    url: str
    status: str


@router.post("/invoices/{invoice_id}/payment-link", response_model=PaymentLinkOut)
async def create_payment_link(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout session and email the payment link to the customer."""
    from app.config import settings
    from app.services.email import send_payment_link_email

    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured — add STRIPE_SECRET_KEY")

    org_id = _org(ctx)
    try:
        # Lock the invoice row so two concurrent /payment-link calls can't
        # both create a Stripe Checkout session and both overwrite the
        # stored id — the orphaned session would never get its status
        # updated via webhook against this invoice.
        result = await db.execute(
            select(Invoice)
            .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
            .where(Invoice.id == invoice_id, Invoice.org_id == org_id)
            .with_for_update()
        )
        inv = result.scalar_one_or_none()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if inv.status == InvoiceStatus.PAID:
            raise HTTPException(status_code=422, detail="Invoice is already paid")
        # Block payment links on DRAFT invoices. A DRAFT is a work-in-progress
        # document — line items, totals and due dates can still be edited by
        # the seller. Emailing a customer a Stripe checkout URL for an
        # unfinished invoice lets them pay against a figure the org hasn't
        # formally issued, and any later edit to the invoice would leave the
        # collected amount disagreeing with the bookkept total (a BFL
        # audit-trail violation). Force the seller to mark it SENT first.
        if inv.status == InvoiceStatus.DRAFT:
            raise HTTPException(
                status_code=422,
                detail="Cannot create a payment link for a DRAFT invoice — mark it Sent first",
            )
        if not inv.customer.email:
            raise HTTPException(status_code=422, detail="Customer has no email address")

        # Reuse an existing pending link if we already created one — avoids
        # generating multiple Stripe sessions for the same invoice on
        # repeated clicks and gives a consistent URL if the customer already
        # received it by email.
        #
        # Stripe Checkout sessions auto-expire 24 h after creation. Without
        # verifying the session is still "open" we would keep handing the
        # customer the same dead URL for days after the first click, and
        # they'd land on a Stripe error page with no recourse. Round-trip
        # to Stripe to confirm the session is still usable; if it expired,
        # fall through and mint a fresh one.
        if inv.stripe_payment_link_url and inv.stripe_payment_link_status == "pending":
            import stripe as _stripe_early
            _stripe_early.api_key = settings.STRIPE_SECRET_KEY
            try:
                existing = _stripe_early.checkout.Session.retrieve(inv.stripe_checkout_session_id)
                existing_status = (existing or {}).get("status")
                if existing_status == "open":
                    return PaymentLinkOut(url=inv.stripe_payment_link_url, status="pending")
                if existing_status == "complete":
                    # The customer has already completed this checkout —
                    # either the webhook has already fired (in which case
                    # inv.status == PAID would have short-circuited above)
                    # or it is in-flight and about to arrive. Either way
                    # minting a fresh Stripe session here would generate
                    # a SECOND payment URL for the same invoice and
                    # invite the customer to pay a second time. Return
                    # the existing URL with a "paid" marker so the UI
                    # can surface "awaiting confirmation" instead of a
                    # "pay now" button. Persist the marker so later
                    # clicks short-circuit without another Stripe call.
                    inv.stripe_payment_link_status = "paid"
                    await db.commit()
                    return PaymentLinkOut(url=inv.stripe_payment_link_url, status="paid")
                # Otherwise the session is "expired" (or an unknown state);
                # mark it and fall through to create a new session below.
                inv.stripe_payment_link_status = "expired"
            except Exception as e:
                # If Stripe is briefly unreachable, returning the cached URL
                # is still safer than 502'ing the user — a short window of
                # potentially-stale links is acceptable for transient errors.
                log.warning(
                    "payment_link session retrieve failed | org_id=%s | invoice=%s | err=%s",
                    org_id, invoice_id, str(e),
                )
                return PaymentLinkOut(url=inv.stripe_payment_link_url, status="pending")

        # Outbound-email throttle — stop an abusive session from triggering
        # a flood of Stripe session creations + customer emails.
        _check_invoice_email_cooldown(org_id, invoice_id, "payment_link")

        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY

        # Charge the REMAINING balance, not the full invoice total. If the
        # customer already made a partial payment via /payments (e.g. a
        # manually recorded bank transfer), the prior code would bill the
        # full gross again via Stripe, and the subsequent
        # stripe_invoice_webhook would insert a full-amount Payment row
        # on top of the existing partial. Result: total recorded payments
        # > invoice total, a Swedish bokföringslagen audit violation and
        # a confused customer double-charged. Compute remaining here and
        # reject if nothing is owed (covers the race where a last manual
        # payment closed the balance between the PAID-status check above
        # and this point — we hold the row lock but payments may have
        # been recorded inside the same transaction window by an earlier
        # call that already committed).
        existing_paid_result = await db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.invoice_id == invoice_id
            )
        )
        existing_paid = Decimal(str(existing_paid_result or 0))
        remaining = inv.total_sek - existing_paid
        if remaining <= 0:
            raise HTTPException(
                status_code=422,
                detail="Invoice is already fully paid — no payment link needed.",
            )
        amount_ore = int(remaining * 100)  # SEK → öre, remaining balance only
        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                currency="sek",
                line_items=[{
                    "price_data": {
                        "currency": "sek",
                        "unit_amount": amount_ore,
                        "product_data": {
                            "name": f"Invoice {inv.invoice_number}",
                            "description": f"Due {inv.due_date}",
                        },
                    },
                    "quantity": 1,
                }],
                customer_email=inv.customer.email,
                metadata={"invoice_id": str(inv.id), "org_id": str(org_id)},
                success_url=f"{settings.PORTAL_BASE_URL}/invoices/{inv.id}?paid=1",
                cancel_url=f"{settings.PORTAL_BASE_URL}/invoices/{inv.id}",
            )
        except stripe.error.StripeError as e:
            log.error(
                "payment_link stripe_error | org_id=%s | invoice=%s | err=%s",
                org_id, invoice_id, str(e),
            )
            raise HTTPException(status_code=502, detail="Payment provider temporarily unavailable")

        inv.stripe_checkout_session_id = session.id
        inv.stripe_payment_link_url = session.url
        inv.stripe_payment_link_status = "pending"
        await db.commit()

        # Email the payment link (best-effort — don't fail the request if
        # email delivery has a hiccup; the link is still saved).
        try:
            # Fetch the org for the "From" header. Deferred until here so
            # we don't pay for the lookup when the customer has no email.
            from app.models.organization import Organization as _Organization
            _org_row = await db.get(_Organization, org_id)
            _org_name = _org_row.name if _org_row else "Varuflow"
            await send_payment_link_email(
                to_email=inv.customer.email,
                customer_name=inv.customer.company_name,
                invoice_number=inv.invoice_number,
                # Show the REMAINING balance the link actually charges —
                # not `inv.total_sek`. A partially-paid invoice would
                # otherwise tell the customer "Pay 10 000 SEK" while the
                # Stripe session only bills the outstanding 3 000 SEK,
                # confusing the customer and breaking reconciliation
                # with their own accounts-payable records.
                total_sek=f"{remaining:.2f}",
                due_date=str(inv.due_date),
                payment_url=session.url,
                org_name=_org_name,
            )
        except Exception as e:
            log.warning(
                "payment_link email failed | org_id=%s | invoice=%s | err=%s",
                org_id, invoice_id, str(e),
            )

        return PaymentLinkOut(url=session.url, status="pending")
    except HTTPException:
        raise
    except Exception as e:
        log.error("payment_link failed | org_id=%s | invoice=%s | err=%s", org_id, invoice_id, str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/invoices/{invoice_id}/payment-link", response_model=PaymentLinkOut)
async def get_payment_link(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == org_id)
    )
    inv = result.scalar_one_or_none()
    if not inv or not inv.stripe_payment_link_url:
        raise HTTPException(status_code=404, detail="No payment link found")
    return PaymentLinkOut(url=inv.stripe_payment_link_url, status=inv.stripe_payment_link_status or "pending")


# ── Stripe webhook (invoice payment) ──────────────────────────────────────────

@router.post("/webhooks/stripe", status_code=200)
async def stripe_invoice_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Stripe payment.succeeded → auto-mark invoice as PAID."""
    from app.config import settings
    from app.routers.billing import StripeProcessedEvent
    from sqlalchemy.exc import IntegrityError

    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    payload = await request.body()
    # DoS guard — real Stripe events are well under 256 KB
    if len(payload) > 256 * 1024:
        raise HTTPException(status_code=413, detail="Payload too large")
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payload")

    event_id = event.get("id") or ""
    if not event_id:
        raise HTTPException(status_code=400, detail="Missing event id")

    # Idempotency: insert-first with ON CONFLICT DO NOTHING so two concurrent
    # deliveries of the same event_id cannot both pass the check and both
    # mark the invoice PAID. Only the INSERT that actually wrote the row
    # proceeds; the loser returns duplicate=True without side effects.
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    ins = (
        pg_insert(StripeProcessedEvent.__table__)
        .values(event_id=event_id)
        .on_conflict_do_nothing(index_elements=["event_id"])
    )
    result = await db.execute(ins)
    if result.rowcount == 0:
        await db.commit()
        return {"received": True, "duplicate": True}

    processing_ok = True
    try:
        if event["type"] == "checkout.session.completed":
            session_obj = event["data"]["object"]
            invoice_id_str = session_obj.get("metadata", {}).get("invoice_id")
            if invoice_id_str:
                try:
                    inv_id = uuid.UUID(invoice_id_str)
                except ValueError:
                    inv_id = None
                if inv_id:
                    # Row-lock the invoice so concurrent webhook deliveries
                    # for the same invoice (e.g. checkout.session.completed
                    # followed closely by payment_intent.succeeded) can't
                    # both double-mark or double-insert payments.
                    inv = await db.scalar(
                        select(Invoice)
                        .where(Invoice.id == inv_id)
                        .with_for_update()
                    )
                    if inv and inv.status != InvoiceStatus.PAID:
                        inv.status = InvoiceStatus.PAID
                        inv.stripe_payment_link_status = "paid"
                        # Record the payment so it appears in /payments and
                        # the aging report reflects the collected amount.
                        # Bokföringslagen requires a trackable payment row;
                        # silently flipping status leaves an accounting gap.
                        amount_ore = session_obj.get("amount_total")
                        paid_amount = (
                            Decimal(str(amount_ore)) / Decimal("100")
                            if amount_ore is not None
                            else inv.total_sek
                        )
                        db.add(
                            Payment(
                                org_id=inv.org_id,
                                invoice_id=inv.id,
                                amount=paid_amount,
                                payment_date=date.today(),
                                # Stripe payments are card transactions and
                                # `PaymentMethod` only has BANK_TRANSFER /
                                # CARD / CASH / OTHER — "stripe" is not a
                                # valid enum value. The webhook previously
                                # passed `payment_method=...` and `note=...`
                                # which aren't columns on Payment, causing
                                # a silent TypeError that the outer except
                                # swallowed — invoices never actually got
                                # marked PAID in production. Use the real
                                # column names + a valid enum + reference.
                                method=PaymentMethod.CARD,
                                reference=f"stripe:{event_id}"[:255],
                            )
                        )
                    elif inv and inv.status == InvoiceStatus.PAID:
                        # Already paid — ensure the payment_link status
                        # stays consistent but don't insert a second Payment.
                        inv.stripe_payment_link_status = "paid"
    except Exception:
        # Do NOT swallow silently-and-commit: if we persist the
        # StripeProcessedEvent marker while the invoice update failed,
        # Stripe will treat the event as delivered (we returned 200) and
        # never retry, so the invoice stays UNPAID forever even though the
        # customer was charged. Instead roll back BOTH the idempotency row
        # and any partial invoice writes, and surface a 500 so Stripe
        # retries the event within its replay window.
        import logging
        logging.getLogger(__name__).exception(
            "stripe invoice webhook: processing error | event_id=%s", event_id,
        )
        processing_ok = False

    if not processing_ok:
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="Webhook processing failed; will be retried"
        )

    # Commit both the idempotency row and any invoice update together.
    try:
        await db.commit()
    except IntegrityError:
        # Defence-in-depth: another race we didn't catch above.
        await db.rollback()

    return {"received": True}


# ── Norwegian EHF 3.0 XML export ─────────────────────────────────────────────

@router.get("/invoices/{invoice_id}/ehf")
async def download_ehf_xml(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Export invoice as Norwegian EHF Billing 3.0 (Peppol BIS/PEPPOL-BIS-3 for Norway)."""
    from app.models.organization import Organization

    org_id = _org(ctx)
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id, Invoice.org_id == org_id)
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


def _generate_ehf_xml(inv: Invoice, org) -> bytes:
    """Generate Norwegian EHF Billing 3.0 XML for delivery to Norwegian buyers.

    Note on currency: Varuflow stores invoice totals in SEK (see
    ``Invoice.total_sek`` / ``Invoice.subtotal`` — the data model has no
    FX / multi-currency columns today). We therefore declare the XML's
    ``DocumentCurrencyCode`` as SEK so the declared currency matches the
    numbers actually emitted. EHF 3.0 allows any ISO-4217 code in the
    supplier's currency; declaring NOK while writing SEK figures would
    silently ship the buyer an invoice for 10 000 NOK (≈9 000 SEK) when
    the seller billed 10 000 SEK — an FX error of 5-15 % that breaks the
    BFL audit trail and the buyer's accounts-payable match. When we add
    NOK billing support, emit NOK currency and the NOK amount column
    together, never one without the other.
    """
    c = inv.customer
    org_name = _xml_escape(org.name if org else "Varuflow")
    # vat_number is a free-form text column — any "&", "<" or ">" would
    # otherwise produce invalid XML that Peppol validators reject, silently
    # breaking B2B delivery. Strip the country/scheme prefix BEFORE escaping
    # so the replace() pattern still matches raw text.
    raw_vat = (org.vat_number if org and org.vat_number else "NO000000000MVA")
    org_vat = _xml_escape(raw_vat)
    endpoint_id = _xml_escape(raw_vat.replace("NO", "").replace("MVA", "").strip())
    currency = "SEK"

    lines_xml = ""
    for idx, li in enumerate(inv.line_items, start=1):
        lines_xml += f"""
  <cac:InvoiceLine>
    <cbc:ID>{idx}</cbc:ID>
    <cbc:InvoicedQuantity unitCode="C62">{li.quantity}</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="{currency}">{li.line_total:.2f}</cbc:LineExtensionAmount>
    <cac:Item>
      <cbc:Name>{_xml_escape(li.description)}</cbc:Name>
      <cac:ClassifiedTaxCategory>
        <cbc:ID>S</cbc:ID>
        <cbc:Percent>{li.tax_rate:.2f}</cbc:Percent>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:ClassifiedTaxCategory>
    </cac:Item>
    <cac:Price>
      <cbc:PriceAmount currencyID="{currency}">{li.unit_price:.2f}</cbc:PriceAmount>
    </cac:Price>
  </cac:InvoiceLine>"""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
  xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
  xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0</cbc:CustomizationID>
  <cbc:ProfileID>urn:fdc:peppol.eu:2017:poacc:billing:01:1.0</cbc:ProfileID>
  <cbc:ID>{_xml_escape(inv.invoice_number)}</cbc:ID>
  <cbc:IssueDate>{inv.issue_date}</cbc:IssueDate>
  <cbc:DueDate>{inv.due_date}</cbc:DueDate>
  <cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>
  <cbc:DocumentCurrencyCode>{currency}</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty>
    <cac:Party>
      <cbc:EndpointID schemeID="0192">{endpoint_id}</cbc:EndpointID>
      <cac:PartyName><cbc:Name>{org_name}</cbc:Name></cac:PartyName>
      <cac:PartyTaxScheme>
        <cbc:CompanyID>{org_vat}</cbc:CompanyID>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:PartyTaxScheme>
    </cac:Party>
  </cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty>
    <cac:Party>
      <cac:PartyName><cbc:Name>{_xml_escape(c.company_name)}</cbc:Name></cac:PartyName>
      {f'<cac:PostalAddress><cbc:StreetName>{_xml_escape(c.address)}</cbc:StreetName><cac:Country><cbc:IdentificationCode>NO</cbc:IdentificationCode></cac:Country></cac:PostalAddress>' if c.address else ''}
      {f'<cac:PartyTaxScheme><cbc:CompanyID>{_xml_escape(c.vat_number)}</cbc:CompanyID><cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:PartyTaxScheme>' if c.vat_number else ''}
    </cac:Party>
  </cac:AccountingCustomerParty>
  <cac:TaxTotal>
    <cbc:TaxAmount currencyID="{currency}">{inv.vat_amount:.2f}</cbc:TaxAmount>
    {''.join(f'''<cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="{currency}">{taxable:.2f}</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="{currency}">{tax_amt:.2f}</cbc:TaxAmount>
      <cac:TaxCategory>
        <cbc:ID>S</cbc:ID>
        <cbc:Percent>{rate:.2f}</cbc:Percent>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:TaxCategory>
    </cac:TaxSubtotal>''' for rate, taxable, tax_amt in _tax_subtotals_by_rate(inv))}
  </cac:TaxTotal>
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="{currency}">{inv.subtotal:.2f}</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="{currency}">{inv.subtotal:.2f}</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="{currency}">{inv.total_sek:.2f}</cbc:TaxInclusiveAmount>
    <cbc:PayableAmount currencyID="{currency}">{inv.total_sek:.2f}</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
  {lines_xml}
</Invoice>"""
    return xml.encode("utf-8")


def _xml_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


# ── Invoice Installment Plans ───────────────────────────────────────────────


@router.post("/invoices/{invoice_id}/installments", status_code=status.HTTP_201_CREATED)
async def create_installment_plan(
    invoice_id: uuid.UUID,
    parts: int = 4,
    interval_days: int = 30,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create an installment plan for an invoice."""
    from app.models.audit import AuditLogEntry
    from app.models.invoice_installment import InvoiceInstallment
    from app.services.invoice_installment import build_plan

    org_id = _org(ctx)
    user_id = ctx[0]

    try:
        result = await db.execute(
            select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == org_id)
        )
        inv = result.scalar_one_or_none()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")

        plan = build_plan(
            total_sek=inv.total_sek,
            parts=parts,
            start_date=inv.due_date,
            interval_days=interval_days,
        )

        rows = []
        for p in plan:
            row = InvoiceInstallment(
                org_id=org_id,
                invoice_id=invoice_id,
                sequence=p.sequence,
                amount_sek=p.amount_sek,
                due_date=p.due_date,
                status="scheduled",
            )
            db.add(row)
            rows.append(row)

        db.add(AuditLogEntry(
            org_id=org_id,
            actor_user_id=user_id,
            action="invoice_installment.plan_created",
            target_type="invoice",
            target_id=str(invoice_id),
            extra={"parts": parts, "interval_days": interval_days},
        ))

        await db.commit()
        return {"invoice_id": str(invoice_id), "installments": len(rows)}

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_installment_plan failed: {str(e)}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/installments/{installment_id}/payments", status_code=status.HTTP_200_OK)
async def record_installment_payment(
    installment_id: uuid.UUID,
    payment_sek: Decimal,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Record a payment against a single installment."""
    from app.models.audit import AuditLogEntry
    from app.models.invoice_installment import InvoiceInstallment
    from app.services.invoice_installment import apply_payment

    org_id = _org(ctx)
    user_id = ctx[0]

    try:
        result = await db.execute(
            select(InvoiceInstallment).where(
                InvoiceInstallment.id == installment_id,
                InvoiceInstallment.org_id == org_id,
            )
        )
        inst = result.scalar_one_or_none()
        if not inst:
            raise HTTPException(status_code=404, detail="Installment not found")

        new_paid, new_status = apply_payment(
            paid_amount_sek=inst.paid_amount_sek or Decimal("0.00"),
            amount_sek=inst.amount_sek,
            payment_sek=payment_sek,
        )
        inst.paid_amount_sek = new_paid
        inst.status = new_status

        db.add(AuditLogEntry(
            org_id=org_id,
            actor_user_id=user_id,
            action="invoice_installment.payment_recorded",
            target_type="invoice_installment",
            target_id=str(installment_id),
            extra={"payment_sek": str(payment_sek), "new_status": new_status},
        ))

        await db.commit()
        return {"installment_id": str(installment_id), "paid": str(new_paid), "status": new_status}

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"record_installment_payment failed: {str(e)}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/invoices/{invoice_id}/installments", status_code=status.HTTP_200_OK)
async def cancel_installment_plan(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Cancel all unpaid installments for an invoice."""
    from app.models.audit import AuditLogEntry
    from app.models.invoice_installment import InvoiceInstallment

    org_id = _org(ctx)
    user_id = ctx[0]

    try:
        result = await db.execute(
            select(InvoiceInstallment).where(
                InvoiceInstallment.invoice_id == invoice_id,
                InvoiceInstallment.org_id == org_id,
                InvoiceInstallment.status.in_(["scheduled", "partial", "overdue"]),
            )
        )
        rows = result.scalars().all()
        for row in rows:
            row.status = "cancelled"

        db.add(AuditLogEntry(
            org_id=org_id,
            actor_user_id=user_id,
            action="invoice_installment.plan_cancelled",
            target_type="invoice",
            target_id=str(invoice_id),
            extra={"cancelled_count": len(rows)},
        ))

        await db.commit()
        return {"invoice_id": str(invoice_id), "cancelled": len(rows)}

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"cancel_installment_plan failed: {str(e)}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
