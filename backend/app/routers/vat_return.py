"""VAT Return Filing

Derives VAT figures from invoice line items and approved expenses.
Supports three country formats:

  SE  — Skatteverket momsdeklaration (SRU XML)
  NO  — Skatteetaten Mva-melding (XML)
  GCC — UAE / KSA FTA VAT return (XML)

Endpoints:
  GET  /api/accounting/vat-return                       compute return (json/xml/pdf)
  GET  /api/accounting/vat-return/periods               list saved periods
  POST /api/accounting/vat-return/periods               lock & save a period
  PATCH /api/accounting/vat-return/periods/{id}/file    mark as filed
  GET  /api/accounting/vat-return/audit-trail           transactions included in a period
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.expenses import Expense, ExpenseStatus
from app.models.invoicing import Invoice, InvoiceLineItem, InvoiceStatus

router = APIRouter(prefix="/api/accounting", tags=["vat"])
log = logging.getLogger(__name__)


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ─── Schemas ───────────────────────────────────────────────────────────────

class VatBox(BaseModel):
    label: str
    description: str
    amount: Decimal


class VatReturnOut(BaseModel):
    country: str
    from_date: date
    to_date: date
    boxes: list[VatBox]
    net_vat_payable: Decimal


class VatPeriodOut(BaseModel):
    id: uuid.UUID
    country: str
    from_date: date
    to_date: date
    status: str
    net_vat_payable: Decimal
    filed_at: Optional[datetime]
    reference: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PeriodCreate(BaseModel):
    country: str = Field(..., pattern="^(SE|NO|AE|GCC)$")
    from_date: date
    to_date: date


class FilePeriodIn(BaseModel):
    reference: Optional[str] = None


class AuditTrailLine(BaseModel):
    source: str          # INVOICE | EXPENSE
    id: uuid.UUID
    date: date
    reference: str       # invoice_number or description
    taxable_amount: Decimal
    vat_amount: Decimal
    tax_rate: Optional[Decimal]


class AuditTrailOut(BaseModel):
    country: str
    from_date: date
    to_date: date
    invoices: list[AuditTrailLine]
    expenses: list[AuditTrailLine]
    total_output_vat: Decimal
    total_input_vat: Decimal


# ─── VAT computation ────────────────────────────────────────────────────────

async def _compute_se(
    db: AsyncSession, org_id: uuid.UUID, from_date: date, to_date: date
) -> VatReturnOut:
    """Swedish Skatteverket momsdeklaration boxes."""
    rows = (
        await db.execute(
            select(
                InvoiceLineItem.tax_rate,
                func.coalesce(func.sum(InvoiceLineItem.line_total - InvoiceLineItem.line_total / (1 + InvoiceLineItem.tax_rate / 100) * (InvoiceLineItem.tax_rate / 100)), 0).label("subtotal"),
                func.coalesce(func.sum(
                    InvoiceLineItem.line_total / (1 + InvoiceLineItem.tax_rate / 100) * (InvoiceLineItem.tax_rate / 100)
                ), 0).label("vat"),
            )
            .join(Invoice, InvoiceLineItem.invoice_id == Invoice.id)
            .where(
                Invoice.org_id == org_id,
                Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.PAID, InvoiceStatus.OVERDUE]),
                Invoice.issue_date >= from_date,
                Invoice.issue_date <= to_date,
            )
            .group_by(InvoiceLineItem.tax_rate)
        )
    ).all()

    # Build by-rate buckets
    sales_25 = Decimal("0"); sales_12 = Decimal("0"); sales_6 = Decimal("0")
    vat_out  = Decimal("0")
    for row in rows:
        rate = int(row.tax_rate)
        sub  = Decimal(str(row.subtotal))
        vat  = Decimal(str(row.vat))
        if rate == 25: sales_25 += sub
        elif rate == 12: sales_12 += sub
        elif rate == 6:  sales_6  += sub
        vat_out += vat

    # Input VAT from approved expenses
    exp_rows = (
        await db.execute(
            select(func.coalesce(func.sum(Expense.amount), 0).label("total"))
            .where(
                Expense.org_id == org_id,
                Expense.status == ExpenseStatus.APPROVED,
                Expense.expense_date >= from_date,
                Expense.expense_date <= to_date,
            )
        )
    ).scalar_one()
    # Assume expenses include 25% VAT (conservative: input_vat = total * 25/125)
    input_vat = Decimal(str(exp_rows)) * Decimal("25") / Decimal("125")
    net = vat_out - input_vat

    boxes = [
        VatBox(label="Box 05", description="Taxable sales at 25%",   amount=sales_25.quantize(Decimal("0.01"))),
        VatBox(label="Box 06", description="Taxable sales at 12%",   amount=sales_12.quantize(Decimal("0.01"))),
        VatBox(label="Box 07", description="Taxable sales at 6%",    amount=sales_6.quantize(Decimal("0.01"))),
        VatBox(label="Box 10", description="Output VAT",             amount=vat_out.quantize(Decimal("0.01"))),
        VatBox(label="Box 48", description="Deductible input VAT",   amount=input_vat.quantize(Decimal("0.01"))),
        VatBox(label="Box 49", description="Net VAT payable",        amount=net.quantize(Decimal("0.01"))),
    ]
    return VatReturnOut(country="SE", from_date=from_date, to_date=to_date, boxes=boxes, net_vat_payable=net)


async def _compute_no(
    db: AsyncSession, org_id: uuid.UUID, from_date: date, to_date: date
) -> VatReturnOut:
    """Norwegian Skatteetaten Mva-melding."""
    rows = (
        await db.execute(
            select(
                InvoiceLineItem.tax_rate,
                func.coalesce(func.sum(InvoiceLineItem.quantity * InvoiceLineItem.unit_price), 0).label("subtotal"),
                func.coalesce(func.sum(InvoiceLineItem.line_total - InvoiceLineItem.quantity * InvoiceLineItem.unit_price), 0).label("vat"),
            )
            .join(Invoice, InvoiceLineItem.invoice_id == Invoice.id)
            .where(
                Invoice.org_id == org_id,
                Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.PAID, InvoiceStatus.OVERDUE]),
                Invoice.issue_date >= from_date,
                Invoice.issue_date <= to_date,
            )
            .group_by(InvoiceLineItem.tax_rate)
        )
    ).all()

    sales_25 = Decimal("0"); sales_15 = Decimal("0"); sales_12 = Decimal("0")
    mva_out  = Decimal("0")
    for row in rows:
        rate = int(row.tax_rate)
        sub  = Decimal(str(row.subtotal))
        vat  = Decimal(str(row.vat))
        if rate == 25: sales_25 += sub
        elif rate == 15: sales_15 += sub
        elif rate == 12: sales_12 += sub
        mva_out += vat

    exp_total = (
        await db.execute(
            select(func.coalesce(func.sum(Expense.amount), 0))
            .where(
                Expense.org_id == org_id,
                Expense.status == ExpenseStatus.APPROVED,
                Expense.expense_date >= from_date,
                Expense.expense_date <= to_date,
            )
        )
    ).scalar_one()
    input_mva = Decimal(str(exp_total)) * Decimal("25") / Decimal("125")
    net = mva_out - input_mva

    boxes = [
        VatBox(label="Post 3001", description="Salg 25% (standard rate)",    amount=sales_25.quantize(Decimal("0.01"))),
        VatBox(label="Post 3002", description="Salg 15% (food)",             amount=sales_15.quantize(Decimal("0.01"))),
        VatBox(label="Post 3003", description="Salg 12% (transport/accom.)", amount=sales_12.quantize(Decimal("0.01"))),
        VatBox(label="Post 3020", description="Output MVA collected",        amount=mva_out.quantize(Decimal("0.01"))),
        VatBox(label="Post 3510", description="Input MVA deductible",        amount=input_mva.quantize(Decimal("0.01"))),
        VatBox(label="Post 3700", description="Net MVA payable",             amount=net.quantize(Decimal("0.01"))),
    ]
    return VatReturnOut(country="NO", from_date=from_date, to_date=to_date, boxes=boxes, net_vat_payable=net)


async def _compute_gcc(
    db: AsyncSession, org_id: uuid.UUID, from_date: date, to_date: date
) -> VatReturnOut:
    """GCC VAT return (UAE/KSA, standard 5%)."""
    rows = (
        await db.execute(
            select(
                InvoiceLineItem.tax_rate,
                func.coalesce(func.sum(InvoiceLineItem.quantity * InvoiceLineItem.unit_price), 0).label("subtotal"),
                func.coalesce(func.sum(InvoiceLineItem.line_total - InvoiceLineItem.quantity * InvoiceLineItem.unit_price), 0).label("vat"),
            )
            .join(Invoice, InvoiceLineItem.invoice_id == Invoice.id)
            .where(
                Invoice.org_id == org_id,
                Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.PAID, InvoiceStatus.OVERDUE]),
                Invoice.issue_date >= from_date,
                Invoice.issue_date <= to_date,
            )
            .group_by(InvoiceLineItem.tax_rate)
        )
    ).all()

    std_supplies = Decimal("0"); zero_supplies = Decimal("0"); exempt = Decimal("0")
    output_vat   = Decimal("0")
    for row in rows:
        rate = int(row.tax_rate)
        sub  = Decimal(str(row.subtotal))
        vat  = Decimal(str(row.vat))
        if rate == 5:    std_supplies += sub; output_vat += vat
        elif rate == 0:  zero_supplies += sub
        else:            exempt += sub

    exp_total = (
        await db.execute(
            select(func.coalesce(func.sum(Expense.amount), 0))
            .where(
                Expense.org_id == org_id,
                Expense.status == ExpenseStatus.APPROVED,
                Expense.expense_date >= from_date,
                Expense.expense_date <= to_date,
            )
        )
    ).scalar_one()
    input_vat = Decimal(str(exp_total)) * Decimal("5") / Decimal("105")
    net = output_vat - input_vat

    boxes = [
        VatBox(label="1a",  description="Standard rated supplies (5%)",         amount=std_supplies.quantize(Decimal("0.01"))),
        VatBox(label="1b",  description="Output VAT @ 5%",                      amount=output_vat.quantize(Decimal("0.01"))),
        VatBox(label="2",   description="Zero rated supplies",                  amount=zero_supplies.quantize(Decimal("0.01"))),
        VatBox(label="3",   description="Exempt supplies",                      amount=exempt.quantize(Decimal("0.01"))),
        VatBox(label="10a", description="Recoverable input VAT",                amount=input_vat.quantize(Decimal("0.01"))),
        VatBox(label="12",  description="Net VAT payable",                      amount=net.quantize(Decimal("0.01"))),
    ]
    return VatReturnOut(country="GCC", from_date=from_date, to_date=to_date, boxes=boxes, net_vat_payable=net)


# ─── XML generators ─────────────────────────────────────────────────────────

def _to_se_xml(v: VatReturnOut) -> bytes:
    root = ET.Element("Blankett", {"andamalsid": "MOMS"})
    period = ET.SubElement(root, "Period")
    ET.SubElement(period, "Fran").text = str(v.from_date)
    ET.SubElement(period, "Till").text = str(v.to_date)
    boxes_el = ET.SubElement(root, "Uppgifter")
    for box in v.boxes:
        b = ET.SubElement(boxes_el, "Uppgift")
        ET.SubElement(b, "Faltnamn").text = box.label
        ET.SubElement(b, "Varde").text = str(box.amount)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _to_no_xml(v: VatReturnOut) -> bytes:
    root = ET.Element("mvamelding", {"xmlns": "urn:no:skatteetaten:fastsetting:avgift:mva:skattemeldingformerverdiavgift:v1.0"})
    ET.SubElement(root, "skattleggingsperiode").text = f"{v.from_date}/{v.to_date}"
    mva = ET.SubElement(root, "mvaSpesifikasjonslinje")
    for box in v.boxes:
        linje = ET.SubElement(mva, "spesifikasjonslinje")
        ET.SubElement(linje, "mvaKode").text = box.label
        ET.SubElement(linje, "beloep").text = str(box.amount)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _to_gcc_xml(v: VatReturnOut) -> bytes:
    root = ET.Element("VATReturn")
    ET.SubElement(root, "TaxPeriodFrom").text = str(v.from_date)
    ET.SubElement(root, "TaxPeriodTo").text = str(v.to_date)
    boxes_el = ET.SubElement(root, "Boxes")
    for box in v.boxes:
        b = ET.SubElement(boxes_el, "Box")
        ET.SubElement(b, "ID").text = box.label
        ET.SubElement(b, "Description").text = box.description
        ET.SubElement(b, "Amount").text = str(box.amount)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


# ─── Endpoint ───────────────────────────────────────────────────────────────

@router.get("/vat-return")
async def vat_return(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    country: str = Query("SE"),
    format: str = Query("json"),
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Generate a VAT return for the given period.

    country: SE (Skatteverket), NO (Skatteetaten), AE (UAE FTA Form 201), GCC (alias for AE)
    format: json | xml
    """
    try:
        org_id = _org(ctx)
        country = country.upper()
        if country not in ("SE", "NO", "AE", "GCC"):
            raise HTTPException(status_code=422, detail="country must be SE, NO, AE, or GCC")

        if country == "SE":
            vat = await _compute_se(db, org_id, from_date, to_date)
        elif country == "NO":
            vat = await _compute_no(db, org_id, from_date, to_date)
        else:
            # AE and GCC both use UAE FTA / GCC standard 5% rate
            vat = await _compute_gcc(db, org_id, from_date, to_date)
            vat.country = country  # preserve caller's label

        if format.lower() == "xml":
            if country == "SE":
                xml_bytes = _to_se_xml(vat)
                filename = f"momsdeklaration_{from_date}_{to_date}.xml"
            elif country == "NO":
                xml_bytes = _to_no_xml(vat)
                filename = f"mva_melding_{from_date}_{to_date}.xml"
            else:
                xml_bytes = _to_gcc_xml(vat)
                filename = f"uae_vat_return_{from_date}_{to_date}.xml"
            return Response(
                content=xml_bytes,
                media_type="application/xml",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        return vat
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"vat_return failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── PDF renderer ─────────────────────────────────────────────────────────────

def _render_vat_pdf(v: VatReturnOut) -> bytes:
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    NAVY  = colors.HexColor("#1a2332")
    LGRAY = colors.HexColor("#f3f4f6")
    GREEN = colors.HexColor("#16a34a")
    RED   = colors.HexColor("#dc2626")
    MGRAY = colors.HexColor("#6b7280")

    COUNTRY_TITLES = {
        "SE": "Momsdeklaration — Skatteverket",
        "NO": "MVA-melding — Skatteetaten",
        "AE": "VAT Return Form 201 — FTA UAE",
        "GCC": "GCC VAT Return",
    }

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    title_s = ParagraphStyle("T", parent=styles["Heading1"], textColor=NAVY, fontSize=16, spaceAfter=2)
    sub_s   = ParagraphStyle("S", parent=styles["Normal"], textColor=MGRAY, fontSize=9, spaceAfter=6)
    disc_s  = ParagraphStyle("D", parent=styles["Normal"], textColor=MGRAY, fontSize=7,
                              spaceAfter=8, backColor=LGRAY, borderPad=4)

    elems = []
    elems.append(Paragraph(COUNTRY_TITLES.get(v.country, "VAT Return"), title_s))
    elems.append(Paragraph(f"{v.from_date} to {v.to_date}", sub_s))
    elems.append(Paragraph(
        "This is a management estimate generated from Varuflow data. "
        "Verify figures with your accountant before submission.",
        disc_s,
    ))
    elems.append(Spacer(1, 4*mm))

    rows = [["Box", "Description", "Amount"]]
    for box in v.boxes:
        rows.append([box.label, box.description, f"{box.amount:,.2f}"])

    col_widths = [25*mm, 110*mm, 40*mm]
    tbl = Table(rows, colWidths=col_widths)
    n = len(rows)
    tbl.setStyle(TableStyle([
        ("FONTNAME",  (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",  (0, 0), (-1, 0), 10),
        ("BACKGROUND",(0, 0), (-1, 0), LGRAY),
        ("TEXTCOLOR", (0, 0), (-1, 0), NAVY),
        ("FONTSIZE",  (0, 1), (-1, -1), 9),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#fafafa")]),
        ("FONTNAME",  (0, n-1), (-1, n-1), "Helvetica-Bold"),
        ("LINEABOVE", (0, n-1), (-1, n-1), 1, NAVY),
        ("TEXTCOLOR", (2, n-1), (2, n-1), GREEN if v.net_vat_payable >= 0 else RED),
        ("ALIGN",     (2, 0),  (2, -1), "RIGHT"),
        ("VALIGN",    (0, 0),  (-1, -1), "MIDDLE"),
    ]))
    elems.append(tbl)
    doc.build(elems)
    return buf.getvalue()


# ─── PDF endpoint ─────────────────────────────────────────────────────────────

@router.get("/vat-return/pdf")
async def vat_return_pdf(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    country: str = Query("SE"),
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        org_id = _org(ctx)
        country = country.upper()
        if country not in ("SE", "NO", "AE", "GCC"):
            raise HTTPException(422, "country must be SE, NO, AE, or GCC")
        if country == "SE":    vat = await _compute_se(db, org_id, from_date, to_date)
        elif country == "NO":  vat = await _compute_no(db, org_id, from_date, to_date)
        else:
            vat = await _compute_gcc(db, org_id, from_date, to_date)
            vat.country = country
        pdf = _render_vat_pdf(vat)
        filename = f"vat_return_{country}_{from_date}_{to_date}.pdf"
        return Response(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"vat_return_pdf failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── Periods — CRUD ───────────────────────────────────────────────────────────

@router.get("/vat-return/periods", response_model=list[VatPeriodOut])
async def list_vat_periods(
    country: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        from app.models.vat_period import VatPeriod
        org_id = _org(ctx)
        q = select(VatPeriod).where(VatPeriod.org_id == org_id)
        if country:
            q = q.where(VatPeriod.country == country.upper())
        q = q.order_by(VatPeriod.from_date.desc())
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_vat_periods failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/vat-return/periods", response_model=VatPeriodOut, status_code=201)
async def create_vat_period(
    body: PeriodCreate,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Lock and snapshot a VAT return for the given period. Idempotent — returns existing if already saved."""
    try:
        from app.models.vat_period import VatPeriod
        org_id = _org(ctx)
        country = body.country.upper()

        # Check if period already saved
        existing = (await db.execute(
            select(VatPeriod).where(
                VatPeriod.org_id == org_id,
                VatPeriod.country == country,
                VatPeriod.from_date == body.from_date,
                VatPeriod.to_date == body.to_date,
            )
        )).scalar_one_or_none()
        if existing:
            return existing

        # Compute fresh
        if country == "SE":    vat = await _compute_se(db, org_id, body.from_date, body.to_date)
        elif country == "NO":  vat = await _compute_no(db, org_id, body.from_date, body.to_date)
        else:
            vat = await _compute_gcc(db, org_id, body.from_date, body.to_date)
            vat.country = country

        snapshot = json.dumps([b.model_dump(mode="json") for b in vat.boxes])
        period = VatPeriod(
            org_id=org_id,
            country=country,
            from_date=body.from_date,
            to_date=body.to_date,
            status="UNFILED",
            net_vat_payable=vat.net_vat_payable,
            snapshot_json=snapshot,
            created_at=datetime.now(timezone.utc),
        )
        db.add(period)
        await db.commit()
        await db.refresh(period)
        return period
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_vat_period failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/vat-return/periods/{period_id}/file", response_model=VatPeriodOut)
async def file_vat_period(
    period_id: uuid.UUID,
    body: FilePeriodIn,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Mark a saved period as FILED. Optionally record the submission reference number."""
    try:
        from app.models.vat_period import VatPeriod
        org_id = _org(ctx)
        period = (await db.execute(
            select(VatPeriod).where(VatPeriod.id == period_id, VatPeriod.org_id == org_id)
        )).scalar_one_or_none()
        if not period:
            raise HTTPException(404, "VAT period not found")
        period.status = "FILED"
        period.filed_at = datetime.now(timezone.utc)
        if body.reference:
            period.reference = body.reference
        await db.commit()
        await db.refresh(period)
        return period
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"file_vat_period failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── Audit trail ──────────────────────────────────────────────────────────────

@router.get("/vat-return/audit-trail", response_model=AuditTrailOut)
async def vat_audit_trail(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    country: str = Query("SE"),
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Return every invoice line and expense included in the VAT return for auditing."""
    try:
        org_id = _org(ctx)
        country = country.upper()
        std_rate = Decimal("5") if country in ("AE", "GCC") else Decimal("25")

        # Invoice lines
        line_rows = (await db.execute(
            select(
                InvoiceLineItem.id,
                Invoice.issue_date,
                Invoice.invoice_number,
                InvoiceLineItem.tax_rate,
                InvoiceLineItem.quantity,
                InvoiceLineItem.unit_price,
                InvoiceLineItem.line_total,
            )
            .join(Invoice, InvoiceLineItem.invoice_id == Invoice.id)
            .where(
                Invoice.org_id == org_id,
                Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.PAID, InvoiceStatus.OVERDUE]),
                Invoice.issue_date >= from_date,
                Invoice.issue_date <= to_date,
            )
            .order_by(Invoice.issue_date)
        )).all()

        invoice_lines: list[AuditTrailLine] = []
        total_output = Decimal("0")
        for r in line_rows:
            subtotal = (Decimal(str(r.quantity)) * Decimal(str(r.unit_price))).quantize(Decimal("0.01"))
            vat = (Decimal(str(r.line_total)) - subtotal).quantize(Decimal("0.01"))
            total_output += vat
            invoice_lines.append(AuditTrailLine(
                source="INVOICE",
                id=r.id,
                date=r.issue_date,
                reference=r.invoice_number or "—",
                taxable_amount=subtotal,
                vat_amount=vat,
                tax_rate=Decimal(str(r.tax_rate)) if r.tax_rate is not None else None,
            ))

        # Expenses
        exp_rows = (await db.execute(
            select(Expense.id, Expense.expense_date, Expense.description, Expense.amount)
            .where(
                Expense.org_id == org_id,
                Expense.status == ExpenseStatus.APPROVED,
                Expense.expense_date >= from_date,
                Expense.expense_date <= to_date,
            )
            .order_by(Expense.expense_date)
        )).all()

        exp_lines: list[AuditTrailLine] = []
        total_input = Decimal("0")
        for r in exp_rows:
            gross = Decimal(str(r.amount))
            vat = (gross * std_rate / (100 + std_rate)).quantize(Decimal("0.01"))
            taxable = (gross - vat).quantize(Decimal("0.01"))
            total_input += vat
            exp_lines.append(AuditTrailLine(
                source="EXPENSE",
                id=r.id,
                date=r.expense_date,
                reference=r.description or "Expense",
                taxable_amount=taxable,
                vat_amount=vat,
                tax_rate=std_rate,
            ))

        return AuditTrailOut(
            country=country,
            from_date=from_date,
            to_date=to_date,
            invoices=invoice_lines,
            expenses=exp_lines,
            total_output_vat=total_output.quantize(Decimal("0.01")),
            total_input_vat=total_input.quantize(Decimal("0.01")),
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"vat_audit_trail failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
