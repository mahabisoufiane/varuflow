"""Operational P&L report — reads from invoices/payments, POs, expenses, payroll.

This is distinct from /api/accounting/reports/pnl which uses double-entry
journal lines.  This report works for any org regardless of whether the
accounting module is configured.

GET /api/reports/pnl         — JSON P&L with comparison + 12-month series
GET /api/reports/pnl/pdf     — PDF download
GET /api/reports/pnl/csv     — CSV download
"""
from __future__ import annotations

import csv
import io
import logging
import uuid
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import and_, case, cast, func, select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member

log = logging.getLogger(__name__)
router = APIRouter(tags=["pnl"])

ZERO = Decimal("0")


# ─── Pydantic output schemas ───────────────────────────────────────────────────

class PeriodSlice(BaseModel):
    from_date: date
    to_date: date
    label: str
    revenue: Decimal
    cogs: Decimal
    gross_profit: Decimal
    gross_margin_pct: Decimal
    operating_expenses: Decimal
    staff_costs: Decimal
    ebitda: Decimal
    net_profit: Decimal


class MonthPoint(BaseModel):
    month: str          # "2026-01"
    revenue: Decimal
    expenses: Decimal   # cogs + opex + staff
    profit: Decimal


class PnLResponse(BaseModel):
    current: PeriodSlice
    previous: Optional[PeriodSlice]
    monthly_series: list[MonthPoint]   # trailing 12 months


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _period_label(from_d: date, to_d: date) -> str:
    if from_d.day == 1 and to_d == date(to_d.year, to_d.month, monthrange(to_d.year, to_d.month)[1]):
        if from_d.year == to_d.year and from_d.month == to_d.month:
            return from_d.strftime("%B %Y")
    if from_d.year == to_d.year:
        return f"{from_d.strftime('%d %b')} – {to_d.strftime('%d %b %Y')}"
    return f"{from_d.isoformat()} – {to_d.isoformat()}"


def _prev_period(from_d: date, to_d: date) -> tuple[date, date]:
    """Shift backward by the same duration."""
    delta = (to_d - from_d).days + 1
    prev_to = from_d - timedelta(days=1)
    prev_from = prev_to - timedelta(days=delta - 1)
    return prev_from, prev_to


def _period_from_params(
    period: str,
    year: int,
    month: Optional[int],
    quarter: Optional[int],
    from_date: Optional[date],
    to_date: Optional[date],
) -> tuple[date, date]:
    if period == "custom":
        if not from_date or not to_date:
            raise HTTPException(422, "'from_date' and 'to_date' required for custom period")
        return from_date, to_date

    if period == "month":
        m = month or datetime.now().month
        last_day = monthrange(year, m)[1]
        return date(year, m, 1), date(year, m, last_day)

    if period == "quarter":
        q = quarter or ((datetime.now().month - 1) // 3 + 1)
        start_month = (q - 1) * 3 + 1
        end_month = start_month + 2
        last_day = monthrange(year, end_month)[1]
        return date(year, start_month, 1), date(year, end_month, last_day)

    # year
    return date(year, 1, 1), date(year, 12, 31)


# ─── Database queries ──────────────────────────────────────────────────────────

async def _revenue(db: AsyncSession, org_id: uuid.UUID, from_d: date, to_d: date) -> Decimal:
    """Sum of payments received in the period."""
    from app.models.invoicing import Payment, Invoice
    row = (await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .where(
            Invoice.org_id == org_id,
            Payment.payment_date >= from_d,
            Payment.payment_date <= to_d,
        )
    )).scalar_one()
    return Decimal(str(row)).quantize(Decimal("0.01"))


async def _cogs(db: AsyncSession, org_id: uuid.UUID, from_d: date, to_d: date) -> Decimal:
    """Sum of received purchase orders in the period (by created_at as proxy)."""
    from app.models.inventory import PurchaseOrder, PurchaseOrderStatus
    row = (await db.execute(
        select(func.coalesce(func.sum(PurchaseOrder.total), 0))
        .where(
            PurchaseOrder.org_id == org_id,
            PurchaseOrder.status == PurchaseOrderStatus.RECEIVED,
            func.date(PurchaseOrder.created_at) >= from_d,
            func.date(PurchaseOrder.created_at) <= to_d,
        )
    )).scalar_one()
    return Decimal(str(row)).quantize(Decimal("0.01"))


async def _opex(db: AsyncSession, org_id: uuid.UUID, from_d: date, to_d: date) -> Decimal:
    """Sum of approved expenses in the period."""
    from app.models.expenses import Expense, ExpenseStatus
    row = (await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0))
        .where(
            Expense.org_id == org_id,
            Expense.status == ExpenseStatus.APPROVED,
            Expense.expense_date >= from_d,
            Expense.expense_date <= to_d,
        )
    )).scalar_one()
    return Decimal(str(row)).quantize(Decimal("0.01"))


async def _staff_costs(db: AsyncSession, org_id: uuid.UUID, from_d: date, to_d: date) -> Decimal:
    """Sum of employer cost from approved/paid payroll runs overlapping the period."""
    from app.models.payroll import PayrollRun
    row = (await db.execute(
        select(func.coalesce(func.sum(PayrollRun.total_employer_cost), 0))
        .where(
            PayrollRun.org_id == org_id,
            PayrollRun.status.in_(["APPROVED", "PAID"]),
            PayrollRun.period_start <= to_d,
            PayrollRun.period_end >= from_d,
        )
    )).scalar_one()
    return Decimal(str(row)).quantize(Decimal("0.01"))


def _build_slice(from_d: date, to_d: date, rev: Decimal, cogs: Decimal, opex: Decimal, staff: Decimal) -> PeriodSlice:
    gross = rev - cogs
    gross_margin = (gross / rev * 100).quantize(Decimal("0.01")) if rev > ZERO else ZERO
    ebitda = gross - opex - staff
    return PeriodSlice(
        from_date=from_d,
        to_date=to_d,
        label=_period_label(from_d, to_d),
        revenue=rev,
        cogs=cogs,
        gross_profit=gross,
        gross_margin_pct=gross_margin,
        operating_expenses=opex,
        staff_costs=staff,
        ebitda=ebitda,
        net_profit=ebitda,
    )


async def _query_slice(db: AsyncSession, org_id: uuid.UUID, from_d: date, to_d: date) -> PeriodSlice:
    rev, cogs, opex, staff = await _revenue(db, org_id, from_d, to_d), \
                              await _cogs(db, org_id, from_d, to_d), \
                              await _opex(db, org_id, from_d, to_d), \
                              await _staff_costs(db, org_id, from_d, to_d)
    return _build_slice(from_d, to_d, rev, cogs, opex, staff)


async def _monthly_series(db: AsyncSession, org_id: uuid.UUID) -> list[MonthPoint]:
    """Trailing 12 months, one data point per month."""
    today = date.today()
    points: list[MonthPoint] = []
    for i in range(11, -1, -1):
        # go back i months
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        last = monthrange(y, m)[1]
        fd, td = date(y, m, 1), date(y, m, last)
        rev  = await _revenue(db, org_id, fd, td)
        cogs = await _cogs(db, org_id, fd, td)
        opex = await _opex(db, org_id, fd, td)
        staff = await _staff_costs(db, org_id, fd, td)
        total_exp = cogs + opex + staff
        points.append(MonthPoint(
            month=f"{y}-{m:02d}",
            revenue=rev,
            expenses=total_exp,
            profit=rev - total_exp,
        ))
    return points


# ─── Main endpoint ─────────────────────────────────────────────────────────────

@router.get("/api/reports/pnl", response_model=PnLResponse)
async def get_pnl(
    period: str = Query("month", pattern="^(month|quarter|year|custom)$"),
    year: int = Query(default_factory=lambda: date.today().year),
    month: Optional[int] = Query(None, ge=1, le=12),
    quarter: Optional[int] = Query(None, ge=1, le=4),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    compare: bool = Query(True),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org(ctx)
        from_d, to_d = _period_from_params(period, year, month, quarter, from_date, to_date)
        current = await _query_slice(db, org_id, from_d, to_d)
        previous: Optional[PeriodSlice] = None
        if compare:
            pf, pt = _prev_period(from_d, to_d)
            previous = await _query_slice(db, org_id, pf, pt)
        series = await _monthly_series(db, org_id)
        return PnLResponse(current=current, previous=previous, monthly_series=series)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_pnl failed: %s", e, extra={"org_id": str(ctx[1] if ctx else "")})
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── CSV export ────────────────────────────────────────────────────────────────

@router.get("/api/reports/pnl/csv")
async def pnl_csv(
    period: str = Query("month", pattern="^(month|quarter|year|custom)$"),
    year: int = Query(default_factory=lambda: date.today().year),
    month: Optional[int] = Query(None, ge=1, le=12),
    quarter: Optional[int] = Query(None, ge=1, le=4),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org(ctx)
        from_d, to_d = _period_from_params(period, year, month, quarter, from_date, to_date)
        s = await _query_slice(db, org_id, from_d, to_d)

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Metric", "Amount (SEK)"])
        w.writerow(["Period", s.label])
        w.writerow([])
        w.writerow(["Revenue", str(s.revenue)])
        w.writerow(["Cost of Goods Sold (COGS)", str(s.cogs)])
        w.writerow(["Gross Profit", str(s.gross_profit)])
        w.writerow(["Gross Margin %", str(s.gross_margin_pct)])
        w.writerow([])
        w.writerow(["Operating Expenses", str(s.operating_expenses)])
        w.writerow(["Staff Costs (Employer)", str(s.staff_costs)])
        w.writerow([])
        w.writerow(["EBITDA", str(s.ebitda)])
        w.writerow(["Net Profit", str(s.net_profit)])

        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="pnl-{from_d}-{to_d}.csv"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("pnl_csv failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


# ─── PDF export ────────────────────────────────────────────────────────────────

@router.get("/api/reports/pnl/pdf")
async def pnl_pdf(
    period: str = Query("month", pattern="^(month|quarter|year|custom)$"),
    year: int = Query(default_factory=lambda: date.today().year),
    month: Optional[int] = Query(None, ge=1, le=12),
    quarter: Optional[int] = Query(None, ge=1, le=4),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org(ctx)
        from_d, to_d = _period_from_params(period, year, month, quarter, from_date, to_date)
        s = await _query_slice(db, org_id, from_d, to_d)
        pdf_bytes = _render_pdf(s)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="pnl-{from_d}-{to_d}.pdf"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("pnl_pdf failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


def _render_pdf(s: PeriodSlice) -> bytes:
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

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    title_s = ParagraphStyle("T", parent=styles["Heading1"], textColor=NAVY, fontSize=18, spaceAfter=2)
    sub_s   = ParagraphStyle("S", parent=styles["Normal"], textColor=colors.gray, fontSize=9, spaceAfter=8)
    label_s = ParagraphStyle("L", parent=styles["Normal"], textColor=NAVY, fontSize=9, fontName="Helvetica-Bold")

    elems = []
    elems.append(Paragraph("Profit &amp; Loss Statement", title_s))
    elems.append(Paragraph(f"{s.label}  ·  {s.from_date} to {s.to_date}", sub_s))
    elems.append(Spacer(1, 4*mm))

    def fmt(v: Decimal) -> str:
        return f"{v:,.2f} SEK"

    rows = [
        ["Revenue",                        "", fmt(s.revenue),               ""],
        ["Cost of Goods Sold",             "", f"({fmt(s.cogs)})",           ""],
        ["Gross Profit",                   "", fmt(s.gross_profit),          f"{s.gross_margin_pct}%"],
        ["", "", "", ""],
        ["Operating Expenses",             "", f"({fmt(s.operating_expenses)})", ""],
        ["Staff Costs (Employer)",         "", f"({fmt(s.staff_costs)})",    ""],
        ["EBITDA",                         "", fmt(s.ebitda),                ""],
        ["", "", "", ""],
        ["Net Profit",                     "", fmt(s.net_profit),            ""],
    ]

    col_widths = [100*mm, 10*mm, 55*mm, 25*mm]
    tbl = Table(rows, colWidths=col_widths)
    n = len(rows)
    tbl.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LGRAY]),
        # Gross profit row (idx 2) bold with line above
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("LINEABOVE", (0, 2), (-1, 2), 0.5, colors.lightgrey),
        # EBITDA row (idx 6) bold
        ("FONTNAME", (0, 6), (-1, 6), "Helvetica-Bold"),
        ("LINEABOVE", (0, 6), (-1, 6), 0.5, colors.lightgrey),
        # Net profit row (last non-empty) bold with navy top line
        ("FONTNAME", (0, n-1), (-1, n-1), "Helvetica-Bold"),
        ("LINEABOVE", (0, n-1), (-1, n-1), 1, NAVY),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # Color net profit green or red
        ("TEXTCOLOR", (2, n-1), (2, n-1),
         GREEN if s.net_profit >= 0 else RED),
    ]))
    elems.append(tbl)

    doc.build(elems)
    return buf.getvalue()
