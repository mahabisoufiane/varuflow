"""Balance Sheet — point-in-time management approximation.

This report derives a balance sheet from operational Varuflow data.
It is NOT a certified audit statement. It is a management estimate.

GET /api/reports/balance-sheet?as_of=YYYY-MM-DD   — JSON
GET /api/reports/balance-sheet/pdf?as_of=YYYY-MM-DD — PDF download
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module

log = logging.getLogger(__name__)
router = APIRouter(tags=["balance_sheet"], dependencies=[Depends(require_module("finance"))])

ZERO = Decimal("0")


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class LineItem(BaseModel):
    label: str
    amount: Decimal
    note: Optional[str] = None


class Section(BaseModel):
    title: str
    lines: list[LineItem]
    total: Decimal


class BalanceSheetResponse(BaseModel):
    as_of: date
    generated_at: datetime
    assets: Section
    liabilities: Section
    equity: Section
    total_assets: Decimal
    total_liabilities_and_equity: Decimal
    balanced: bool          # True when assets == liabilities + equity (within 1 SEK rounding)
    disclaimer: str


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _q(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"))


# ─── Asset collectors ─────────────────────────────────────────────────────────

async def _cash(db: AsyncSession, org_id: uuid.UUID, as_of: date) -> tuple[Decimal, str]:
    """
    Cash approximation = total payments received up to as_of
                       - approved expenses up to as_of
                       - payroll costs up to as_of
                       - received PO costs up to as_of
    """
    from app.features.invoicing.models import Payment, Invoice
    from app.features.expenses.models import Expense, ExpenseStatus
    from app.features.inventory.models import PurchaseOrder, PurchaseOrderStatus
    from app.features.hr.payroll_models import PayrollRun

    inflows = (await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .where(Invoice.org_id == org_id, Payment.payment_date <= as_of)
    )).scalar_one()

    outflows_exp = (await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0))
        .where(
            Expense.org_id == org_id,
            Expense.status == ExpenseStatus.APPROVED,
            Expense.expense_date <= as_of,
        )
    )).scalar_one()

    outflows_po = (await db.execute(
        select(func.coalesce(func.sum(PurchaseOrder.total), 0))
        .where(
            PurchaseOrder.org_id == org_id,
            PurchaseOrder.status == PurchaseOrderStatus.RECEIVED,
            func.date(PurchaseOrder.created_at) <= as_of,
        )
    )).scalar_one()

    outflows_payroll = (await db.execute(
        select(func.coalesce(func.sum(PayrollRun.total_employer_cost), 0))
        .where(
            PayrollRun.org_id == org_id,
            PayrollRun.status.in_(["APPROVED", "PAID"]),
            PayrollRun.period_end <= as_of,
        )
    )).scalar_one()

    cash = (
        Decimal(str(inflows))
        - Decimal(str(outflows_exp))
        - Decimal(str(outflows_po))
        - Decimal(str(outflows_payroll))
    )
    return _q(cash), "Payments received less operating costs paid to date"


async def _accounts_receivable(db: AsyncSession, org_id: uuid.UUID, as_of: date) -> tuple[Decimal, Decimal]:
    """Returns (gross_receivable, credit_note_provision)."""
    from app.features.invoicing.models import Invoice
    from app.features.invoicing.credit_note import CreditNote, CreditNoteStatus

    gross = (await db.execute(
        select(func.coalesce(func.sum(Invoice.total_sek), 0))
        .where(
            Invoice.org_id == org_id,
            Invoice.status.in_(["SENT", "OVERDUE"]),
            Invoice.issue_date <= as_of,
        )
    )).scalar_one()

    # ISSUED credit notes reduce receivables
    cn = (await db.execute(
        select(func.coalesce(func.sum(CreditNote.total), 0))
        .where(
            CreditNote.org_id == org_id,
            CreditNote.status == CreditNoteStatus.ISSUED,
            CreditNote.issue_date <= as_of,
        )
    )).scalar_one()

    return _q(Decimal(str(gross))), _q(Decimal(str(cn)))


async def _inventory_value(db: AsyncSession, org_id: uuid.UUID) -> Decimal:
    from app.features.inventory.models import StockLevel, Product
    row = (await db.execute(
        select(func.coalesce(func.sum(StockLevel.quantity * Product.purchase_price), 0))
        .join(Product, StockLevel.product_id == Product.id)
        .where(
            StockLevel.org_id == org_id,
            Product.purchase_price.isnot(None),
            StockLevel.quantity > 0,
        )
    )).scalar_one()
    return _q(Decimal(str(row)))


async def _fixed_assets_nbv(db: AsyncSession, org_id: uuid.UUID) -> Decimal:
    from app.features.expenses.fixed_assets_models import FixedAsset
    row = (await db.execute(
        select(func.coalesce(func.sum(FixedAsset.current_book_value), 0))
        .where(
            FixedAsset.org_id == org_id,
            FixedAsset.is_disposed.is_(False),
        )
    )).scalar_one()
    return _q(Decimal(str(row)))


# ─── Liability collectors ──────────────────────────────────────────────────────

async def _accounts_payable(db: AsyncSession, org_id: uuid.UUID, as_of: date) -> Decimal:
    from app.features.purchases.payable_invoice import PayableInvoice
    row = (await db.execute(
        select(func.coalesce(func.sum(PayableInvoice.total), 0))
        .where(
            PayableInvoice.org_id == org_id,
            PayableInvoice.status.in_(["APPROVED", "DRAFT"]),
        )
    )).scalar_one()
    return _q(Decimal(str(row)))


async def _credit_notes_payable(db: AsyncSession, org_id: uuid.UUID, as_of: date) -> Decimal:
    """ISSUED credit notes = liabilities owed back to customers."""
    from app.features.invoicing.credit_note import CreditNote, CreditNoteStatus
    row = (await db.execute(
        select(func.coalesce(func.sum(CreditNote.total), 0))
        .where(
            CreditNote.org_id == org_id,
            CreditNote.status == CreditNoteStatus.ISSUED,
            CreditNote.issue_date <= as_of,
        )
    )).scalar_one()
    return _q(Decimal(str(row)))


# ─── Builder ──────────────────────────────────────────────────────────────────

async def _build(db: AsyncSession, org_id: uuid.UUID, as_of: date) -> BalanceSheetResponse:
    cash, cash_note = await _cash(db, org_id, as_of)
    ar_gross, cn_provision = await _accounts_receivable(db, org_id, as_of)
    ar_net = ar_gross - cn_provision
    inventory = await _inventory_value(db, org_id)
    fixed_assets = await _fixed_assets_nbv(db, org_id)

    ap = await _accounts_payable(db, org_id, as_of)
    cn_payable = await _credit_notes_payable(db, org_id, as_of)

    # Assets
    asset_lines: list[LineItem] = [
        LineItem(label="Cash & Cash Equivalents", amount=cash, note=cash_note),
        LineItem(label="Accounts Receivable (gross)", amount=ar_gross),
        LineItem(label="Less: Credit Note Provision", amount=-cn_provision),
        LineItem(label="Net Accounts Receivable", amount=ar_net),
        LineItem(label="Inventory (at cost)", amount=inventory, note="Stock on hand × purchase price"),
        LineItem(label="Fixed Assets (net book value)", amount=fixed_assets, note="Active assets after depreciation"),
    ]
    total_assets = _q(cash + ar_net + inventory + fixed_assets)
    assets = Section(title="Assets", lines=asset_lines, total=total_assets)

    # Liabilities
    liab_lines: list[LineItem] = [
        LineItem(label="Accounts Payable", amount=ap, note="Open supplier invoices (draft + approved)"),
        LineItem(label="Credit Notes Outstanding", amount=cn_payable, note="Issued credit notes owed to customers"),
    ]
    total_liabilities = _q(ap + cn_payable)
    liabilities = Section(title="Liabilities", lines=liab_lines, total=total_liabilities)

    # Equity — residual (accounting identity)
    retained = _q(total_assets - total_liabilities)
    equity_lines: list[LineItem] = [
        LineItem(label="Retained Earnings (approximation)", amount=retained,
                 note="Assets minus Liabilities — management estimate only"),
    ]
    total_equity = retained
    equity = Section(title="Equity", lines=equity_lines, total=total_equity)

    total_le = _q(total_liabilities + total_equity)
    balanced = abs(total_assets - total_le) < Decimal("1.00")

    return BalanceSheetResponse(
        as_of=as_of,
        generated_at=datetime.now(timezone.utc),
        assets=assets,
        liabilities=liabilities,
        equity=equity,
        total_assets=total_assets,
        total_liabilities_and_equity=total_le,
        balanced=balanced,
        disclaimer=(
            "This is a management approximation generated from Varuflow operational data. "
            "It does not constitute a certified audit statement or a formal statutory balance sheet. "
            "Cash is estimated from payment records and operational outflows. "
            "Consult your accountant for certified financial statements."
        ),
    )


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/api/reports/balance-sheet", response_model=BalanceSheetResponse)
async def get_balance_sheet(
    as_of: Optional[date] = Query(None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org(ctx)
        snapshot_date = as_of or date.today()
        return await _build(db, org_id, snapshot_date)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_balance_sheet failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/reports/balance-sheet/pdf")
async def balance_sheet_pdf(
    as_of: Optional[date] = Query(None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org(ctx)
        snapshot_date = as_of or date.today()
        bs = await _build(db, org_id, snapshot_date)
        pdf_bytes = _render_pdf(bs)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="balance-sheet-{snapshot_date}.pdf"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("balance_sheet_pdf failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── PDF renderer ─────────────────────────────────────────────────────────────

def _render_pdf(bs: BalanceSheetResponse) -> bytes:
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    NAVY = colors.HexColor("#1a2332")
    LGRAY = colors.HexColor("#f3f4f6")
    GREEN = colors.HexColor("#16a34a")
    RED = colors.HexColor("#dc2626")
    MGRAY = colors.HexColor("#6b7280")

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    title_s = ParagraphStyle("T", parent=styles["Heading1"], textColor=NAVY, fontSize=18, spaceAfter=2)
    sub_s   = ParagraphStyle("S", parent=styles["Normal"], textColor=MGRAY, fontSize=9, spaceAfter=4)
    disc_s  = ParagraphStyle("D", parent=styles["Normal"], textColor=MGRAY, fontSize=7, spaceAfter=8,
                              borderPad=4, borderColor=LGRAY, backColor=LGRAY,
                              borderRadius=3)
    sec_s   = ParagraphStyle("SEC", parent=styles["Heading3"], textColor=NAVY, fontSize=11, spaceBefore=8, spaceAfter=2)

    def fmt(v: Decimal) -> str:
        if v < 0:
            return f"({abs(v):,.2f})"
        return f"{v:,.2f}"

    elems = []
    elems.append(Paragraph("Balance Sheet", title_s))
    elems.append(Paragraph(f"As at {bs.as_of}  ·  Generated {bs.generated_at.strftime('%Y-%m-%d %H:%M')} UTC", sub_s))
    elems.append(Paragraph(bs.disclaimer, disc_s))
    elems.append(Spacer(1, 4*mm))

    col_widths = [110*mm, 60*mm]

    def section_table(sec: Section, total_label: str, highlight_color) -> Table:
        rows = [[sec.title, "SEK"]]
        for line in sec.lines:
            rows.append([line.label, fmt(line.amount)])
        rows.append([total_label, fmt(sec.total)])

        tbl = Table(rows, colWidths=col_widths)
        n = len(rows)
        tbl.setStyle(TableStyle([
            # Header row
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, 0), 10),
            ("TEXTCOLOR",   (0, 0), (-1, 0), NAVY),
            ("BACKGROUND",  (0, 0), (-1, 0), LGRAY),
            ("TOPPADDING",  (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("FONTSIZE",    (0, 1), (-1, -2), 9),
            ("TEXTCOLOR",   (0, 1), (-1, -2), colors.HexColor("#374151")),
            # Total row
            ("FONTNAME",    (0, n-1), (-1, n-1), "Helvetica-Bold"),
            ("FONTSIZE",    (0, n-1), (-1, n-1), 10),
            ("LINEABOVE",   (0, n-1), (-1, n-1), 1, NAVY),
            ("TEXTCOLOR",   (1, n-1), (1, n-1), highlight_color),
            ("ALIGN",       (1, 0), (1, -1), "RIGHT"),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ]))
        return tbl

    elems.append(section_table(bs.assets, "Total Assets", GREEN if bs.total_assets >= 0 else RED))
    elems.append(Spacer(1, 6*mm))
    elems.append(section_table(bs.liabilities, "Total Liabilities", RED if bs.liabilities.total > 0 else GREEN))
    elems.append(Spacer(1, 6*mm))
    elems.append(section_table(bs.equity, "Total Equity", GREEN if bs.equity.total >= 0 else RED))
    elems.append(Spacer(1, 6*mm))

    # Summary balance check
    summary_rows = [
        ["Total Assets", fmt(bs.total_assets)],
        ["Total Liabilities + Equity", fmt(bs.total_liabilities_and_equity)],
    ]
    stbl = Table(summary_rows, colWidths=col_widths)
    stbl.setStyle(TableStyle([
        ("FONTNAME",  (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",  (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), NAVY),
        ("BACKGROUND",(0, 0), (-1, -1), LGRAY),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ALIGN",     (1, 0), (1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.lightgrey),
    ]))
    elems.append(stbl)

    doc.build(elems)
    return buf.getvalue()
