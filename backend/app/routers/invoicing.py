"""Invoicing module: customers, invoices, payments, aging report, PDF."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.invoicing import (
    Customer,
    Invoice,
    InvoiceLineItem,
    InvoiceStatus,
    Payment,
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

router = APIRouter(prefix="/api/invoicing", tags=["invoicing"])

NAVY = colors.HexColor("#1a2332")
LIGHT_GRAY = colors.HexColor("#f3f4f6")


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _invoice_number(org_id: uuid.UUID, sequence: int) -> str:
    year = datetime.utcnow().year
    return f"INV-{year}-{sequence:04d}"


# ── Customers ─────────────────────────────────────────────────────────────────

@router.get("/customers", response_model=list[CustomerOut])
async def list_customers(
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
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
    q = q.order_by(Customer.company_name).offset(skip).limit(limit)
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
    for k, v in body.model_dump().items():
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
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
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
    q = q.order_by(Invoice.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/invoices", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    body: InvoiceCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)

    # Verify customer belongs to org
    customer = await db.scalar(
        select(Customer).where(Customer.id == body.customer_id, Customer.org_id == org_id)
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Generate invoice number from count
    count_result = await db.scalar(
        select(func.count()).where(Invoice.org_id == org_id)
    )
    inv_number = _invoice_number(org_id, (count_result or 0) + 1)

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
    )
    db.add(invoice)
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
    inv = await db.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == org_id)
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Status transitions: DRAFT→SENT→PAID, or →OVERDUE
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
    inv = await db.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == org_id)
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status != InvoiceStatus.DRAFT:
        raise HTTPException(status_code=422, detail="Only DRAFT invoices can be deleted")
    await db.delete(inv)
    await db.commit()


# ── Payments ──────────────────────────────────────────────────────────────────

@router.get("/invoices/{invoice_id}/payments", response_model=list[PaymentOut])
async def list_payments(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    inv = await db.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == org_id)
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    result = await db.execute(
        select(Payment).where(Payment.invoice_id == invoice_id).order_by(Payment.payment_date)
    )
    return result.scalars().all()


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
    inv = await db.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.org_id == org_id)
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status == InvoiceStatus.DRAFT:
        raise HTTPException(status_code=422, detail="Cannot record payment on a DRAFT invoice")

    payment = Payment(
        org_id=org_id,
        invoice_id=invoice_id,
        **body.model_dump(),
    )
    db.add(payment)

    # Auto-mark PAID if payment covers full amount
    total_paid_result = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.invoice_id == invoice_id
        )
    )
    total_paid = Decimal(str(total_paid_result)) + body.amount
    if total_paid >= inv.total_sek:
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

    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer))
        .where(
            Invoice.org_id == org_id,
            Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE]),
        )
    )
    invoices = result.scalars().all()

    buckets: dict[str, list[AgingBucket]] = {
        "current": [],
        "days_1_30": [],
        "days_31_60": [],
        "days_61_90": [],
        "days_90_plus": [],
    }
    total_outstanding = Decimal("0.00")

    for inv in invoices:
        days_overdue = (today - inv.due_date).days
        bucket = AgingBucket(
            customer=inv.customer.company_name,
            invoice_number=inv.invoice_number,
            invoice_id=inv.id,
            total_sek=inv.total_sek,
            due_date=inv.due_date,
            days_overdue=max(0, days_overdue),
        )
        total_outstanding += inv.total_sek
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


def _generate_invoice_pdf(inv: Invoice) -> bytes:
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
    elements.append(Paragraph(f"Invoice {inv.invoice_number}", title_style))
    elements.append(Paragraph(f"Issued: {inv.issue_date} · Due: {inv.due_date} · Status: {inv.status}", sub_style))
    elements.append(Spacer(1, 8 * mm))

    # Bill to
    elements.append(Paragraph("Bill To", label_style))
    elements.append(Paragraph(c.company_name, body_style))
    if c.org_number:
        elements.append(Paragraph(f"Org nr: {c.org_number}", body_style))
    if c.vat_number:
        elements.append(Paragraph(f"VAT: {c.vat_number}", body_style))
    if c.address:
        elements.append(Paragraph(c.address, body_style))
    if c.email:
        elements.append(Paragraph(c.email, body_style))
    elements.append(Spacer(1, 8 * mm))

    # Line items table
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
        ("ROWBACKGROUNDS", (0, 1), (-1, -(4)), [colors.white, LIGHT_GRAY]),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        # Summary rows bold
        ("FONTNAME", (3, n - 3), (-1, n - 1), "Helvetica-Bold"),
        ("LINEABOVE", (3, n - 3), (-1, n - 3), 0.5, colors.lightgrey),
        ("LINEABOVE", (3, n - 1), (-1, n - 1), 1, NAVY),
        ("GRID", (0, 0), (-1, -(4)), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ]))
    elements.append(table)

    if inv.notes:
        elements.append(Spacer(1, 8 * mm))
        elements.append(Paragraph("Notes", label_style))
        elements.append(Paragraph(inv.notes, body_style))

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
    <cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="SEK">{inv.subtotal:.2f}</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="SEK">{inv.vat_amount:.2f}</cbc:TaxAmount>
      <cac:TaxCategory>
        <cbc:ID>S</cbc:ID>
        <cbc:Percent>25</cbc:Percent>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:TaxCategory>
    </cac:TaxSubtotal>
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
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id, Invoice.org_id == org_id)
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status == InvoiceStatus.PAID:
        raise HTTPException(status_code=422, detail="Invoice is already paid")
    if not inv.customer.email:
        raise HTTPException(status_code=422, detail="Customer has no email address")

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY

    amount_ore = int(inv.total_sek * 100)  # SEK → öre
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

    inv.stripe_checkout_session_id = session.id
    inv.stripe_payment_link_url = session.url
    inv.stripe_payment_link_status = "pending"
    await db.commit()

    # Email the payment link
    await send_payment_link_email(
        to_email=inv.customer.email,
        customer_name=inv.customer.company_name,
        invoice_number=inv.invoice_number,
        total_sek=f"{inv.total_sek:.2f}",
        payment_url=session.url,
    )

    return PaymentLinkOut(url=session.url, status="pending")


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

    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session_obj = event["data"]["object"]
        invoice_id_str = session_obj.get("metadata", {}).get("invoice_id")
        if invoice_id_str:
            try:
                inv_id = uuid.UUID(invoice_id_str)
            except ValueError:
                return {"received": True}
            inv = await db.get(Invoice, inv_id)
            if inv:
                inv.status = InvoiceStatus.PAID
                inv.stripe_payment_link_status = "paid"
                await db.commit()

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
    """Generate Norwegian EHF Billing 3.0 XML (NOK currency, NO VAT scheme)."""
    c = inv.customer
    org_name = _xml_escape(org.name if org else "Varuflow")
    org_vat = org.vat_number if org and org.vat_number else "NO000000000MVA"
    currency = "NOK"

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
      <cbc:EndpointID schemeID="0192">{org_vat.replace('NO','').replace('MVA','').strip()}</cbc:EndpointID>
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
    <cac:TaxSubtotal>
      <cbc:TaxableAmount currencyID="{currency}">{inv.subtotal:.2f}</cbc:TaxableAmount>
      <cbc:TaxAmount currencyID="{currency}">{inv.vat_amount:.2f}</cbc:TaxAmount>
      <cac:TaxCategory>
        <cbc:ID>S</cbc:ID>
        <cbc:Percent>25.00</cbc:Percent>
        <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
      </cac:TaxCategory>
    </cac:TaxSubtotal>
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
