"""Point-of-Sale: sessions, sales, barcode lookup, receipt PDF."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from typing import Optional
from xml.sax.saxutils import escape as _xml_escape


def _esc(v) -> str:
    """Escape user-supplied text before embedding in a ReportLab Paragraph
    (which parses its input as mini-XML)."""
    return _xml_escape("" if v is None else str(v))

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import A6
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.inventory import Product, StockLevel, StockMovement, StockMovementType, Warehouse
from app.models.pos import PosPaymentMethod, PosSession, PosSessionStatus, PosSale, PosSaleItem

router = APIRouter(prefix="/api/pos", tags=["pos"], dependencies=[Depends(require_module("pos"))])

NAVY = colors.HexColor("#1a2332")


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Schemas ────────────────────────────────────────────────────────────────────

class ProductLookup(BaseModel):
    id: uuid.UUID
    name: str
    sku: str
    barcode: str | None
    sell_price: Decimal
    tax_rate: Decimal
    unit: str
    stock: int
    model_config = {"from_attributes": True}


class SessionOut(BaseModel):
    id: uuid.UUID
    status: PosSessionStatus
    opened_at: datetime
    closed_at: datetime | None
    sale_count: int
    total_revenue: Decimal
    model_config = {"from_attributes": True}


def _session_net_revenue(sales) -> Decimal:
    """Sum sale totals EXCLUDING refunded sales.

    Used by every SessionOut producer so the dashboard figure matches the
    Z-report PDF (which also filters `is_refunded`). Previously the list,
    close and retrieve endpoints returned gross revenue that disagreed
    with the printed end-of-day report — a Swedish kassalag compliance
    problem because the cashier reconciles cash drawer against the
    dashboard number.
    """
    return sum((s.total for s in sales if not s.is_refunded), Decimal("0"))


def _session_net_sale_count(sales) -> int:
    """Count sales EXCLUDING refunded ones.

    Pairs with `_session_net_revenue` so `sale_count` and `total_revenue`
    in SessionOut describe the same set of rows. Previously SessionOut
    returned `len(sales)` (gross) alongside the net revenue, so the
    sessions list would show e.g. "20 sales / 48 000 SEK" while the
    Z-report PDF for the same session showed "18 sales / 48 000 SEK"
    — the cashier couldn't reconcile the two figures, and the weekly
    digest (which already excludes refunded sales from both its count
    and revenue) disagreed with the dashboard on the same numbers.
    """
    return sum(1 for s in sales if not s.is_refunded)


class SaleItemIn(BaseModel):
    product_id: uuid.UUID | None = None
    # Cap matches invoicing.InvoiceLineItemCreate so the same overflow
    # guarantees apply: description fits description varchar, quantity *
    # unit_price cannot overflow line_total Numeric(14,2).
    description: str = Field(..., min_length=1, max_length=500)
    quantity: Decimal = Field(..., gt=0, le=Decimal("1000000"), decimal_places=3)
    unit_price: Decimal = Field(..., ge=0, le=Decimal("1000000"), decimal_places=2)
    tax_rate: Decimal = Field(Decimal("25.00"), ge=0, le=100)


class SaleIn(BaseModel):
    session_id: uuid.UUID
    # Hard cap on line count: a POS sale with more than 500 items is not
    # plausible for a human at a till and would otherwise let a caller
    # pin a worker on PDF generation / stock-level batched locks.
    items: list[SaleItemIn] = Field(..., min_length=1, max_length=500)
    payment_method: PosPaymentMethod = PosPaymentMethod.CASH
    amount_tendered: Decimal | None = Field(default=None, ge=0, le=Decimal("10000000"))
    customer_id: uuid.UUID | None = None


class SaleItemOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID | None
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal
    line_total: Decimal
    model_config = {"from_attributes": True}


class SaleOut(BaseModel):
    id: uuid.UUID
    sale_number: str
    subtotal: Decimal
    vat_amount: Decimal
    total: Decimal
    payment_method: PosPaymentMethod
    amount_tendered: Decimal | None
    change_due: Decimal | None
    customer_id: uuid.UUID | None
    is_refunded: bool
    refunded_at: datetime | None
    created_at: datetime
    items: list[SaleItemOut]
    model_config = {"from_attributes": True}


# ── Barcode / product lookup ───────────────────────────────────────────────────

@router.get("/lookup", response_model=ProductLookup)
async def lookup_product(
    barcode: Optional[str] = Query(None),
    sku: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Look up a product by barcode, SKU, or name search for the POS."""
    org_id = _org(ctx)
    query = select(Product).where(Product.org_id == org_id, Product.is_active == True)

    if barcode:
        query = query.where(Product.barcode == barcode)
    elif sku:
        query = query.where(Product.sku == sku)
    elif q:
        query = query.where(Product.name.ilike(f"%{q}%") | Product.sku.ilike(f"%{q}%"))
    else:
        raise HTTPException(status_code=400, detail="Provide barcode, sku, or q")

    result = await db.execute(query.limit(1))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Total stock across all warehouses
    stock_result = await db.scalar(
        select(func.coalesce(func.sum(StockLevel.quantity), 0))
        .where(StockLevel.product_id == product.id)
    )

    return ProductLookup(
        id=product.id,
        name=product.name,
        sku=product.sku,
        barcode=product.barcode,
        sell_price=product.sell_price,
        tax_rate=product.tax_rate,
        unit=product.unit,
        stock=int(stock_result or 0),
    )


@router.get("/products", response_model=list[ProductLookup])
async def list_pos_products(
    q: Optional[str] = Query(None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """List products for the POS product grid."""
    org_id = _org(ctx)
    # Aggregate stock across warehouses in the same query via LEFT JOIN +
    # GROUP BY. The previous implementation issued one extra SELECT per
    # product to compute the sum, so a 100-row POS grid fired 101
    # round-trips per refresh — a typical till reloads on every navigation,
    # so under real usage this pinned the DB and made the grid visibly
    # sluggish. Filtering StockLevel by the same org_id is belt-and-braces
    # (products are already org-scoped) but also lets the planner use the
    # StockLevel(org_id, product_id) index directly.
    stock_sum = func.coalesce(func.sum(StockLevel.quantity), 0).label("stock")
    query = (
        select(Product, stock_sum)
        .outerjoin(
            StockLevel,
            (StockLevel.product_id == Product.id) & (StockLevel.org_id == org_id),
        )
        .where(Product.org_id == org_id, Product.is_active == True)  # noqa: E712
    )
    if q:
        query = query.where(Product.name.ilike(f"%{q}%") | Product.sku.ilike(f"%{q}%"))
    query = (
        query.group_by(Product.id)
        .order_by(Product.name)
        .limit(100)
    )
    rows = (await db.execute(query)).all()

    return [
        ProductLookup(
            id=p.id, name=p.name, sku=p.sku, barcode=p.barcode,
            sell_price=p.sell_price, tax_rate=p.tax_rate, unit=p.unit,
            stock=int(stock or 0),
        )
        for p, stock in rows
    ]


# ── Sessions ──────────────────────────────────────────────────────────────────

@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    result = await db.execute(
        select(PosSession)
        .options(selectinload(PosSession.sales))
        .where(PosSession.org_id == org_id)
        .order_by(PosSession.opened_at.desc())
        .limit(50)
    )
    sessions = result.scalars().all()
    return [
        SessionOut(
            id=s.id, status=s.status,
            opened_at=s.opened_at, closed_at=s.closed_at,
            sale_count=_session_net_sale_count(s.sales),
            total_revenue=_session_net_revenue(s.sales),
        )
        for s in sessions
    ]


@router.post("/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def open_session(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    current_user, member = ctx
    org_id = _org(ctx)

    # Acquire an org-scoped row lock so two concurrent open_session requests
    # cannot both pass the "no existing session" check and create duplicates.
    from app.models.organization import Organization as _Organization
    await db.scalar(
        select(_Organization).where(_Organization.id == org_id).with_for_update()
    )

    # Check no existing open session. `.limit(1)` is defensive: the lock
    # above prevents NEW duplicate-open rows from being created, but does
    # nothing about pre-existing data anomalies (older versions of the
    # app didn't hold the org lock, and manual DB edits happen). If two
    # OPEN PosSession rows already exist for the same org, an unbounded
    # `db.scalar()` raises MultipleResultsFound → 500 and the till
    # cannot be opened at all until support intervenes.
    existing = await db.scalar(
        select(PosSession).where(
            PosSession.org_id == org_id,
            PosSession.status == PosSessionStatus.OPEN,
        )
        .order_by(PosSession.opened_at.asc())
        .limit(1)
    )
    if existing:
        return SessionOut(
            id=existing.id, status=existing.status,
            opened_at=existing.opened_at, closed_at=existing.closed_at,
            sale_count=0, total_revenue=Decimal("0"),
        )

    session = PosSession(
        org_id=org_id,
        cashier_user_id=current_user["user_id"],
        status=PosSessionStatus.OPEN,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionOut(
        id=session.id, status=session.status,
        opened_at=session.opened_at, closed_at=session.closed_at,
        sale_count=0, total_revenue=Decimal("0"),
    )


@router.patch("/sessions/{session_id}/close", response_model=SessionOut)
async def close_session(
    session_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    # Lock the session row so two concurrent closes can't both overwrite
    # closed_at (and disagree on the final Z-report timestamp).
    result = await db.execute(
        select(PosSession)
        .options(selectinload(PosSession.sales))
        .where(PosSession.id == session_id, PosSession.org_id == org_id)
        .with_for_update()
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    # Idempotent: if already closed, return the current state instead of
    # bumping closed_at (would otherwise shift the Z-report cutover).
    if session.status == PosSessionStatus.CLOSED:
        return SessionOut(
            id=session.id, status=session.status,
            opened_at=session.opened_at, closed_at=session.closed_at,
            sale_count=_session_net_sale_count(session.sales),
            total_revenue=_session_net_revenue(session.sales),
        )
    session.status = PosSessionStatus.CLOSED
    session.closed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return SessionOut(
        id=session.id, status=session.status,
        opened_at=session.opened_at, closed_at=session.closed_at,
        sale_count=_session_net_sale_count(session.sales),
        total_revenue=_session_net_revenue(session.sales),
    )


# ── Sales ─────────────────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/sales", response_model=list[SaleOut])
async def list_sales(
    session_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    result = await db.execute(
        select(PosSale)
        .options(selectinload(PosSale.items))
        .where(PosSale.session_id == session_id, PosSale.org_id == org_id)
        .order_by(PosSale.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.post("/sales", response_model=SaleOut, status_code=status.HTTP_201_CREATED)
async def create_sale(
    body: SaleIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)

    # Validate session. Lock the session row FOR UPDATE so a concurrent
    # PATCH /sessions/{id}/close cannot flip it to CLOSED between our
    # check and the sale commit. Without the lock, a sale can be inserted
    # with session_id pointing to what is — by commit time — a CLOSED
    # session, corrupting the Z-report and leaving an orphaned sale
    # outside the session's accounting window.
    session = await db.scalar(
        select(PosSession).where(
            PosSession.id == body.session_id,
            PosSession.org_id == org_id,
            PosSession.status == PosSessionStatus.OPEN,
        ).with_for_update()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Open POS session not found")

    # Cross-tenant guard: validate every product_id and the optional
    # customer_id belongs to the caller's organisation before we start
    # building the sale. Foreign keys on pos_sale_items.product_id and
    # stock_movements.product_id only enforce "row exists" — not "row
    # belongs to my org". Without this check, a caller in Org A could
    # submit a product_id owned by Org B and pollute Org A's sale + stock
    # history with another tenant's product references (and vice-versa
    # when those stock_movements are counted in Org A's analytics).
    referenced_product_ids = {i.product_id for i in body.items if i.product_id is not None}
    if referenced_product_ids:
        valid = await db.scalars(
            select(Product.id).where(
                Product.id.in_(referenced_product_ids),
                Product.org_id == org_id,
            )
        )
        valid_ids = set(valid.all())
        missing = referenced_product_ids - valid_ids
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"Product(s) not found in your organisation: {', '.join(str(m) for m in list(missing)[:5])}",
            )

    if body.customer_id is not None:
        from app.models.invoicing import Customer as _Customer
        cust_ok = await db.scalar(
            select(_Customer.id).where(
                _Customer.id == body.customer_id,
                _Customer.org_id == org_id,
            )
        )
        if not cust_ok:
            raise HTTPException(status_code=404, detail="Customer not found")

    # Build line items + totals
    subtotal = Decimal("0.00")
    vat_total = Decimal("0.00")
    sale_items = []

    for item in body.items:
        line_total = (item.quantity * item.unit_price).quantize(Decimal("0.01"))
        vat = (line_total * item.tax_rate / 100).quantize(Decimal("0.01"))
        subtotal += line_total
        vat_total += vat
        sale_items.append(PosSaleItem(
            product_id=item.product_id,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
            tax_rate=item.tax_rate,
            line_total=line_total,
        ))

    total = (subtotal + vat_total).quantize(Decimal("0.01"))
    change = None
    if body.payment_method == PosPaymentMethod.CASH:
        # Cash sales MUST specify how much the customer handed over, and
        # that amount must cover the total. The previous check was
        # `if body.amount_tendered:` which silently accepted two broken
        # cases:
        #   • amount_tendered omitted  → change left as None, but the
        #     sale is still committed as PAID; the till's cash drawer
        #     reconciliation then has no record of what was received,
        #     so the Z-report cannot tie out against the physical drawer.
        #   • amount_tendered < total → `change` becomes negative, the
        #     receipt prints "Change: -50.00" and the sale is committed
        #     as closed — the customer walks out having underpaid and
        #     the books don't flag it. Also corrupts daily cash totals
        #     and VAT reporting (BFL 4 kap. § records a sale that was
        #     never fully collected).
        if body.amount_tendered is None:
            raise HTTPException(
                status_code=422,
                detail="Cash sales require amount_tendered.",
            )
        if body.amount_tendered < total:
            raise HTTPException(
                status_code=422,
                detail=f"Amount tendered ({body.amount_tendered}) is less than total ({total}).",
            )
        change = (body.amount_tendered - total).quantize(Decimal("0.01"))

    # Sale number.
    #
    # Serialize on the Organization row before reading the max so two
    # concurrent checkouts at the same till don't both mint POS-YYYYMMDD-(N+1).
    # Using MAX(sale_number) rather than COUNT(*) so a refunded/deleted
    # sale cannot reuse its number — required for accounting traceability.
    from app.models.organization import Organization as _Org
    await db.execute(
        select(_Org.id).where(_Org.id == org_id).with_for_update()
    )
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    day_prefix = f"POS-{today_str}-"
    max_sale = await db.scalar(
        select(func.max(PosSale.sale_number))
        .where(
            PosSale.org_id == org_id,
            PosSale.sale_number.like(f"{day_prefix}%"),
        )
    )
    next_seq = 1
    if max_sale:
        try:
            next_seq = int(max_sale.rsplit("-", 1)[-1]) + 1
        except (ValueError, IndexError):
            next_seq = 1
    sale_number = f"{day_prefix}{next_seq:04d}"

    sale = PosSale(
        org_id=org_id,
        session_id=body.session_id,
        sale_number=sale_number,
        subtotal=subtotal,
        vat_amount=vat_total,
        total=total,
        payment_method=body.payment_method,
        amount_tendered=body.amount_tendered,
        change_due=change,
        customer_id=body.customer_id,
        items=sale_items,
    )
    db.add(sale)

    # Deduct stock for each product. Fetch the default warehouse once
    # before the loop — otherwise we'd issue N+1 warehouse lookups per sale.
    # If no active warehouse exists we must refuse the sale rather than
    # silently commit it with no StockMovement rows: the customer walks
    # out with inventory while the books still show it on hand, which
    # corrupts stock counts, low-stock alerts and the Z-report. Matches
    # the guard used in refund_sale and inventory.update_po_status.
    default_wh = await db.scalar(
        select(Warehouse)
        .where(Warehouse.org_id == org_id, Warehouse.is_active == True)  # noqa: E712
        .order_by(Warehouse.created_at)
    )
    if default_wh is None and any(i.product_id for i in body.items):
        raise HTTPException(
            status_code=422,
            detail="Cannot record sale: no active warehouse exists to deduct stock from.",
        )
    if default_wh:
        # Batch-lock all StockLevel rows for the products in this sale in
        # one ordered query — avoids the per-line SELECT FOR UPDATE round-
        # trip (previously O(N) per sale) and prevents cross-sale deadlocks
        # by acquiring locks in product_id order.
        product_ids = sorted({i.product_id for i in body.items if i.product_id})
        sl_map: dict[uuid.UUID, StockLevel] = {}
        if product_ids:
            sl_rows = (
                await db.scalars(
                    select(StockLevel)
                    .where(
                        StockLevel.warehouse_id == default_wh.id,
                        StockLevel.product_id.in_(product_ids),
                    )
                    .order_by(StockLevel.product_id)
                    .with_for_update()
                )
            ).all()
            sl_map = {sl.product_id: sl for sl in sl_rows}

        for item in body.items:
            if item.product_id:
                movement = StockMovement(
                    org_id=org_id,
                    product_id=item.product_id,
                    warehouse_id=default_wh.id,
                    type=StockMovementType.OUT,
                    quantity=int(item.quantity),
                    reference=sale_number,
                    note="POS sale",
                )
                db.add(movement)
                sl = sl_map.get(item.product_id)
                if sl is None:
                    # No StockLevel row has ever existed for this
                    # (product, warehouse). Auto-create at quantity=0
                    # so the decrement below still fires — otherwise
                    # the OUT movement is written but StockLevel stays
                    # missing, and SUM(IN) - SUM(OUT) no longer equals
                    # StockLevel.quantity, breaking the reconciliation
                    # invariant that the rest of this block relies on.
                    # Matches the pattern used in refund_sale,
                    # inventory.create_movement and update_po_status.
                    sl = StockLevel(
                        org_id=org_id,
                        product_id=item.product_id,
                        warehouse_id=default_wh.id,
                        quantity=0,
                    )
                    db.add(sl)
                    await db.flush()
                    sl_map[item.product_id] = sl
                # Allow the stock level to go negative on oversell.
                # Clamping to 0 with max() silently hid the problem:
                # SUM(IN) - SUM(OUT) would no longer equal StockLevel.
                # quantity, breaking inventory reconciliation and the
                # audit trail. A negative value surfaces the real
                # operational issue (the till accepted a sale against
                # stock we didn't have recorded) in low-stock alerts
                # and the dashboard so the owner can investigate —
                # typically an unrecorded IN movement or an ADJUSTMENT
                # miss — instead of carrying a silent discrepancy.
                sl.quantity = sl.quantity - int(item.quantity)

    await db.commit()

    result = await db.execute(
        select(PosSale).options(selectinload(PosSale.items)).where(PosSale.id == sale.id)
    )
    return result.scalar_one()


# ── Receipt PDF ───────────────────────────────────────────────────────────────

@router.get("/sales/{sale_id}/receipt")
async def download_receipt(
    sale_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    from app.models.organization import Organization

    result = await db.execute(
        select(PosSale).options(selectinload(PosSale.items))
        .where(PosSale.id == sale_id, PosSale.org_id == org_id)
    )
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")

    org = await db.get(Organization, org_id)
    pdf = _generate_receipt(sale, org.name if org else "Varuflow")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="receipt-{sale.sale_number}.pdf"'},
    )


def _generate_receipt(sale: PosSale, org_name: str) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A6,
        leftMargin=10*mm, rightMargin=10*mm, topMargin=10*mm, bottomMargin=10*mm)

    styles = getSampleStyleSheet()
    center = ParagraphStyle("C", parent=styles["Normal"], alignment=1, fontSize=9)
    bold_center = ParagraphStyle("BC", parent=styles["Normal"], alignment=1, fontSize=10, fontName="Helvetica-Bold")
    small = ParagraphStyle("S", parent=styles["Normal"], fontSize=7, textColor=colors.gray)

    elements = [
        Paragraph(_esc(org_name), bold_center),
        Paragraph(f"Receipt {_esc(sale.sale_number)}", center),
        Paragraph(sale.created_at.strftime("%Y-%m-%d %H:%M"), small),
        Spacer(1, 4*mm),
    ]

    w = [55*mm, 15*mm, 25*mm]
    rows = [["Item", "Qty", "Total (SEK)"]]
    for item in sale.items:
        rows.append([item.description, str(item.quantity), f"{item.line_total:.2f}"])

    rows.append(["", "Subtotal", f"{sale.subtotal:.2f}"])
    rows.append(["", "VAT", f"{sale.vat_amount:.2f}"])
    rows.append(["", "TOTAL", f"{sale.total:.2f}"])
    if sale.change_due is not None:
        rows.append(["", "Change", f"{sale.change_due:.2f}"])

    n = len(rows)
    t = Table(rows, colWidths=w)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("FONTNAME", (1, n-3), (-1, n-1), "Helvetica-Bold"),
        ("LINEABOVE", (1, n-3), (-1, n-3), 0.5, colors.lightgrey),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 4*mm))
    # `sale.payment_method` is a `PosPaymentMethod(str, enum.Enum)`. Its
    # default `__str__` returns `"PosPaymentMethod.CASH"` (the enum repr),
    # not `"CASH"` — so the customer receipt was printing
    # "Paid by: PosPaymentMethod.CASH". Render the enum's `.value` so
    # the tape says "Paid by: CASH".
    _pm = sale.payment_method
    _pm_str = _pm.value if hasattr(_pm, "value") else str(_pm)
    elements.append(Paragraph(f"Paid by: {_esc(_pm_str)}", small))
    elements.append(Spacer(1, 4*mm))
    elements.append(Paragraph("Thank you!", center))

    doc.build(elements)
    return buffer.getvalue()


# ── Refund ────────────────────────────────────────────────────────────────────

@router.post("/sales/{sale_id}/refund", response_model=SaleOut)
async def refund_sale(
    sale_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Mark a sale as refunded and restore stock levels."""
    org_id = _org(ctx)

    # Lock the sale row so two concurrent refund requests cannot both observe
    # is_refunded=False and both restore stock (doubling the StockLevel bump).
    result = await db.execute(
        select(PosSale).options(selectinload(PosSale.items))
        .where(PosSale.id == sale_id, PosSale.org_id == org_id)
        .with_for_update(of=PosSale)
    )
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    if sale.is_refunded:
        raise HTTPException(status_code=409, detail="Sale already refunded")

    sale.is_refunded = True
    sale.refunded_at = datetime.now(timezone.utc)

    # Restore stock to the SAME warehouse each item was deducted from at
    # sale time. Looking up the "earliest active warehouse" here would
    # silently bump a different warehouse if:
    #   • the org has multiple warehouses
    #   • the originally-debited warehouse was later deactivated, or
    #   • a newer warehouse was inserted with an earlier created_at via
    #     a timestamp override.
    # In those cases the StockMovement audit trail shows OUT from
    # warehouse A and IN to warehouse B for the same sale_number,
    # which breaks `SUM(IN) - SUM(OUT) = StockLevel` reconciliation and
    # leaves phantom negative stock in A forever. Recover the per-item
    # warehouse from the sale's original OUT movement (keyed by
    # reference = sale_number, the deterministic tag written in
    # create_sale). Fall back to the current default warehouse only
    # when we cannot find the original row — e.g. a manually-edited
    # history — and refuse the refund entirely if no active warehouse
    # exists (the sale transition is one-way, so a missed restore can
    # never be recovered without DB surgery).
    out_rows = await db.scalars(
        select(StockMovement).where(
            StockMovement.org_id == org_id,
            StockMovement.reference == sale.sale_number,
            StockMovement.type == StockMovementType.OUT,
        )
    )
    original_wh_by_product: dict[uuid.UUID, uuid.UUID] = {}
    for mv in out_rows:
        # A product can only appear once per sale in create_sale, but
        # keep the last-seen mapping defensively so repeated lines are
        # handled deterministically.
        original_wh_by_product[mv.product_id] = mv.warehouse_id

    fallback_wh = await db.scalar(
        select(Warehouse).where(Warehouse.org_id == org_id, Warehouse.is_active == True)  # noqa: E712
        .order_by(Warehouse.created_at)
    )
    if fallback_wh is None and any(
        i.product_id and i.product_id not in original_wh_by_product
        for i in sale.items
    ):
        raise HTTPException(
            status_code=422,
            detail="Cannot refund sale: no active warehouse exists to restore stock into.",
        )

    for item in sale.items:
        if item.product_id:
            wh_id = original_wh_by_product.get(item.product_id)
            if wh_id is None:
                # No original OUT movement found — fall back to the
                # default active warehouse so the refund still completes.
                wh_id = fallback_wh.id
            db.add(StockMovement(
                org_id=org_id,
                product_id=item.product_id,
                warehouse_id=wh_id,
                type=StockMovementType.IN,
                quantity=int(item.quantity),
                reference=sale.sale_number,
                note="POS refund",
            ))
            sl = await db.scalar(
                select(StockLevel).where(
                    StockLevel.product_id == item.product_id,
                    StockLevel.warehouse_id == wh_id,
                ).with_for_update()
            )
            if sl is None:
                # The original sale was against a warehouse that no
                # longer has a StockLevel row for this product (row
                # deleted, manual cleanup, or the sale went negative and
                # someone zeroed it out). Create the row here so the
                # IN StockMovement we just recorded is reflected in the
                # on-hand quantity — otherwise StockMovement shows
                # "+5 units" while StockLevel stays unchanged, breaking
                # `SUM(IN)-SUM(OUT) = StockLevel.quantity` reconciliation
                # permanently for that product/warehouse.
                sl = StockLevel(
                    org_id=org_id,
                    product_id=item.product_id,
                    warehouse_id=wh_id,
                    quantity=0,
                )
                db.add(sl)
                await db.flush()
            sl.quantity += int(item.quantity)

    await db.commit()

    result = await db.execute(
        select(PosSale).options(selectinload(PosSale.items)).where(PosSale.id == sale.id)
    )
    return result.scalar_one()


# ── Z-Report PDF ──────────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/zreport")
async def download_zreport(
    session_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Generate a Z-report PDF for a closed POS session."""
    org_id = _org(ctx)
    from app.models.organization import Organization

    result = await db.execute(
        select(PosSession)
        .options(selectinload(PosSession.sales).selectinload(PosSale.items))
        .where(PosSession.id == session_id, PosSession.org_id == org_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    # A Z-report is legally the end-of-day close record (Swedish kassalag).
    # Generating one for an open session would show moving totals that never
    # match a real accounting snapshot — refuse until the session is closed.
    if session.status != PosSessionStatus.CLOSED:
        raise HTTPException(
            status_code=409,
            detail="Z-report is only available after the session is closed",
        )

    org = await db.get(Organization, org_id)
    pdf = _generate_zreport(session, org.name if org else "Varuflow")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="zreport-{session_id}.pdf"'},
    )


def _generate_zreport(session: PosSession, org_name: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Normal"], fontSize=16, fontName="Helvetica-Bold", textColor=NAVY)
    h2 = ParagraphStyle("H2", parent=styles["Normal"], fontSize=11, fontName="Helvetica-Bold", textColor=NAVY)
    small = ParagraphStyle("S", parent=styles["Normal"], fontSize=8, textColor=colors.gray)

    sales = [s for s in session.sales if not s.is_refunded]
    refunds = [s for s in session.sales if s.is_refunded]

    # Gross = every sale that was rung up this session, including those
    # later refunded. Net = gross − refunds, which is what the customer-
    # receipt tape and the bokföringslagen (BFL) daily Z-total must
    # reconcile against. The previous code set `total_revenue` from the
    # already-refund-filtered `sales` list and then subtracted
    # `total_refunds` again — a double-subtraction that understated daily
    # revenue for every session that contained a refund and silently
    # mis-reported VAT liability. VAT is the sum on non-refunded sales
    # (the refund reverses the VAT collected on the original sale).
    total_revenue = sum((s.total for s in session.sales), Decimal("0"))
    total_vat = sum((s.vat_amount for s in sales), Decimal("0"))
    total_refunds = sum((s.total for s in refunds), Decimal("0"))
    net_revenue = total_revenue - total_refunds

    # Payment method breakdown. Key by the enum's `.value` so the
    # Z-report prints "CASH" / "CARD" / "SWISH" — not the raw Python
    # enum repr `"PosPaymentMethod.CASH"` that results from rendering a
    # `PosPaymentMethod(str, enum.Enum)` member via `str()` in a
    # ReportLab table cell. Same fix applied to the customer receipt
    # below.
    by_method: dict[str, Decimal] = {}
    for s in sales:
        _pm = s.payment_method
        _pm_str = _pm.value if hasattr(_pm, "value") else str(_pm)
        by_method[_pm_str] = by_method.get(_pm_str, Decimal("0")) + s.total

    opened = session.opened_at.strftime("%Y-%m-%d %H:%M") if session.opened_at else "—"
    closed = session.closed_at.strftime("%Y-%m-%d %H:%M") if session.closed_at else "Open"

    elements = [
        Paragraph(_esc(org_name), h1),
        Paragraph("Z-Report / End of Day", h2),
        Spacer(1, 3*mm),
        Paragraph(f"Session: {session.id}", small),
        Paragraph(f"Opened: {_esc(opened)}  |  Closed: {_esc(closed)}", small),
        Spacer(1, 6*mm),
        Paragraph("Summary", h2),
        Spacer(1, 2*mm),
    ]

    summary_rows = [
        ["Metric", "Amount (SEK)"],
        ["Total sales", f"{total_revenue:,.2f}"],
        ["Total VAT", f"{total_vat:,.2f}"],
        ["Refunds", f"-{total_refunds:,.2f}"],
        ["Net revenue", f"{net_revenue:,.2f}"],
        ["Sale count", str(len(sales))],
        ["Refund count", str(len(refunds))],
    ]
    t = Table(summary_rows, colWidths=[80*mm, 60*mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.5, colors.black),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6*mm))

    if by_method:
        elements.append(Paragraph("Payment methods", h2))
        elements.append(Spacer(1, 2*mm))
        pm_rows = [["Method", "Amount (SEK)"]] + [
            [m, f"{v:,.2f}"] for m, v in by_method.items()
        ]
        pt = Table(pm_rows, colWidths=[80*mm, 60*mm])
        pt.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(pt)
        elements.append(Spacer(1, 6*mm))

    elements.append(Paragraph(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC", small))

    doc.build(elements)
    return buffer.getvalue()
