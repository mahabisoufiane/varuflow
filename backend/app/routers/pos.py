"""Point-of-Sale: sessions, sales, barcode lookup, receipt PDF."""
import uuid
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
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
from app.models.inventory import Product, StockLevel, StockMovement, StockMovementType, Warehouse
from app.models.pos import PosPaymentMethod, PosSession, PosSessionStatus, PosSale, PosSaleItem

router = APIRouter(prefix="/api/pos", tags=["pos"])

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


class SaleItemIn(BaseModel):
    product_id: uuid.UUID | None = None
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal = Decimal("25.00")


class SaleIn(BaseModel):
    session_id: uuid.UUID
    items: list[SaleItemIn]
    payment_method: PosPaymentMethod = PosPaymentMethod.CASH
    amount_tendered: Decimal | None = None


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
    query = select(Product).where(Product.org_id == org_id, Product.is_active == True)
    if q:
        query = query.where(Product.name.ilike(f"%{q}%") | Product.sku.ilike(f"%{q}%"))
    query = query.order_by(Product.name).limit(100)
    result = await db.execute(query)
    products = result.scalars().all()

    out = []
    for p in products:
        stock = await db.scalar(
            select(func.coalesce(func.sum(StockLevel.quantity), 0)).where(StockLevel.product_id == p.id)
        )
        out.append(ProductLookup(
            id=p.id, name=p.name, sku=p.sku, barcode=p.barcode,
            sell_price=p.sell_price, tax_rate=p.tax_rate, unit=p.unit,
            stock=int(stock or 0),
        ))
    return out


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
            sale_count=len(s.sales),
            total_revenue=sum(sale.total for sale in s.sales),
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

    # Check no existing open session
    existing = await db.scalar(
        select(PosSession).where(
            PosSession.org_id == org_id,
            PosSession.status == PosSessionStatus.OPEN,
        )
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
    result = await db.execute(
        select(PosSession)
        .options(selectinload(PosSession.sales))
        .where(PosSession.id == session_id, PosSession.org_id == org_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = PosSessionStatus.CLOSED
    session.closed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(session)
    return SessionOut(
        id=session.id, status=session.status,
        opened_at=session.opened_at, closed_at=session.closed_at,
        sale_count=len(session.sales),
        total_revenue=sum(s.total for s in session.sales),
    )


# ── Sales ─────────────────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}/sales", response_model=list[SaleOut])
async def list_sales(
    session_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    result = await db.execute(
        select(PosSale)
        .options(selectinload(PosSale.items))
        .where(PosSale.session_id == session_id, PosSale.org_id == org_id)
        .order_by(PosSale.created_at.desc())
    )
    return result.scalars().all()


@router.post("/sales", response_model=SaleOut, status_code=status.HTTP_201_CREATED)
async def create_sale(
    body: SaleIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)

    # Validate session
    session = await db.scalar(
        select(PosSession).where(
            PosSession.id == body.session_id,
            PosSession.org_id == org_id,
            PosSession.status == PosSessionStatus.OPEN,
        )
    )
    if not session:
        raise HTTPException(status_code=404, detail="Open POS session not found")

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
    if body.payment_method == PosPaymentMethod.CASH and body.amount_tendered:
        change = (body.amount_tendered - total).quantize(Decimal("0.01"))

    # Sale number
    count = await db.scalar(select(func.count()).where(PosSale.org_id == org_id)) or 0
    sale_number = f"POS-{datetime.utcnow().strftime('%Y%m%d')}-{count + 1:04d}"

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
        items=sale_items,
    )
    db.add(sale)

    # Deduct stock for each product
    for item in body.items:
        if item.product_id:
            # Find default warehouse (first one)
            wh = await db.scalar(
                select(Warehouse).where(Warehouse.org_id == org_id, Warehouse.is_active == True)
                .order_by(Warehouse.created_at)
            )
            if wh:
                movement = StockMovement(
                    org_id=org_id,
                    product_id=item.product_id,
                    warehouse_id=wh.id,
                    type=StockMovementType.OUT,
                    quantity=int(item.quantity),
                    reference=sale_number,
                    note="POS sale",
                )
                db.add(movement)
                # Update stock level
                sl = await db.scalar(
                    select(StockLevel).where(
                        StockLevel.product_id == item.product_id,
                        StockLevel.warehouse_id == wh.id,
                    )
                )
                if sl:
                    sl.quantity = max(0, sl.quantity - int(item.quantity))

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
        Paragraph(org_name, bold_center),
        Paragraph(f"Receipt {sale.sale_number}", center),
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
    elements.append(Paragraph(f"Paid by: {sale.payment_method}", small))
    elements.append(Spacer(1, 4*mm))
    elements.append(Paragraph("Thank you!", center))

    doc.build(elements)
    return buffer.getvalue()
