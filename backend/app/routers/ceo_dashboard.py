"""CEO Dashboard — cash flow forecast, P&L summary, board report PDF generation."""
import io
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.organization import OrgPlan

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ceo", tags=["ceo"])


def _require_pro(plan: OrgPlan) -> None:
    if plan not in (OrgPlan.PRO, OrgPlan.ENTERPRISE):
        raise HTTPException(status_code=403, detail="PRO plan required")


# ── CASH FLOW FORECAST ────────────────────────────────────────────────────────

@router.get("/cash-forecast")
async def cash_forecast(
    horizon_days: int = 90,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Forward-looking cash position forecast.

    Starting balance: sum of all BankTransaction amounts for the org.
    If no bank data: paid invoice total − paid expense total (last 12 months).
    Inflows: open invoices (sent/overdue) with due_date in the forecast window.
    Outflows: trailing 3-month avg monthly expense / 30 per day (recurring burn rate).
    Returns: daily balance series + balance at 30/60/90 day marks + cashout risk flag.
    """
    try:
        _require_pro(member["plan"])
        org_id = member["org_id"]
        horizon_days = min(max(horizon_days, 7), 180)
        today = date.today()

        # ── 1. Current balance ──────────────────────────────────────────────
        bank_row = await db.execute(
            text("""
                SELECT COALESCE(SUM(amount), 0)
                FROM bank_transactions
                WHERE org_id = :oid
            """).bindparams(oid=org_id)
        )
        current_balance = float(bank_row.scalar() or 0)

        # Fallback: net from invoices − expenses if no bank data
        if current_balance == 0:
            inv_row = await db.execute(
                text("""
                    SELECT COALESCE(SUM(paid_amount), 0)
                    FROM invoices
                    WHERE org_id = :oid AND status = 'paid'
                      AND issued_date >= now() - interval '12 months'
                """).bindparams(oid=org_id)
            )
            exp_row = await db.execute(
                text("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM expenses
                    WHERE org_id = :oid AND status = 'approved'
                      AND date >= now() - interval '12 months'
                """).bindparams(oid=org_id)
            )
            current_balance = float(inv_row.scalar() or 0) - float(exp_row.scalar() or 0)

        # ── 2. Expected inflows: open invoices due in window ────────────────
        inf_rows = await db.execute(
            text("""
                SELECT due_date, COALESCE(outstanding_amount, total_amount - COALESCE(paid_amount,0)) AS expected
                FROM invoices
                WHERE org_id = :oid
                  AND status IN ('sent', 'overdue')
                  AND due_date IS NOT NULL
                  AND due_date >= :today
                  AND due_date <= :horizon
                ORDER BY due_date
            """).bindparams(oid=org_id, today=today, horizon=today + timedelta(days=horizon_days))
        )
        inflows: dict[date, float] = {}
        for r in inf_rows:
            d = r[0] if isinstance(r[0], date) else r[0].date()
            inflows[d] = inflows.get(d, 0.0) + float(r[1] or 0)

        # ── 3. Expected outflows: trailing 3-month avg daily burn ───────────
        burn_row = await db.execute(
            text("""
                SELECT COALESCE(SUM(amount), 0) / 90.0 AS daily_burn
                FROM expenses
                WHERE org_id = :oid AND status = 'approved'
                  AND date >= now() - interval '3 months'
            """).bindparams(oid=org_id)
        )
        daily_burn = float(burn_row.scalar() or 0)

        # ── 4. Build daily series ────────────────────────────────────────────
        series = []
        balance = current_balance
        low_balance = current_balance
        low_day = 0
        cashout_day: Optional[int] = None

        for day_offset in range(horizon_days + 1):
            d = today + timedelta(days=day_offset)
            inflow = inflows.get(d, 0.0)
            outflow = daily_burn
            if day_offset > 0:
                balance = balance + inflow - outflow
            if balance < low_balance:
                low_balance = balance
                low_day = day_offset
            if cashout_day is None and balance < 0:
                cashout_day = day_offset

            if day_offset % 7 == 0 or day_offset in (30, 60, 90):
                series.append({
                    "day": day_offset,
                    "date": d.isoformat(),
                    "balance": round(balance, 2),
                    "inflow": round(inflow, 2),
                    "outflow": round(outflow, 2),
                })

        # Ensure horizon endpoint is included
        if series[-1]["day"] != horizon_days:
            d = today + timedelta(days=horizon_days)
            series.append({"day": horizon_days, "date": d.isoformat(), "balance": round(balance, 2), "inflow": 0, "outflow": 0})

        b30 = next((s["balance"] for s in series if s["day"] >= 30), balance)
        b60 = next((s["balance"] for s in series if s["day"] >= 60), balance)
        b90 = next((s["balance"] for s in series if s["day"] >= 90), balance)

        # ── 5. Upcoming invoice inflows within 7 days ────────────────────────
        soon_rows = await db.execute(
            text("""
                SELECT i.invoice_number, c.name AS customer, i.due_date,
                       COALESCE(i.outstanding_amount, i.total_amount - COALESCE(i.paid_amount,0)) AS expected
                FROM invoices i
                LEFT JOIN customers c ON i.customer_id = c.id
                WHERE i.org_id = :oid AND i.status IN ('sent','overdue')
                  AND i.due_date >= :today AND i.due_date <= :soon
                ORDER BY i.due_date LIMIT 10
            """).bindparams(oid=org_id, today=today, soon=today + timedelta(days=7))
        )
        upcoming = [
            {"invoice_number": r[0], "customer": r[1], "due_date": str(r[2]), "expected": float(r[3] or 0)}
            for r in soon_rows
        ]

        return {
            "current_balance": round(current_balance, 2),
            "balance_30d": round(b30, 2),
            "balance_60d": round(b60, 2),
            "balance_90d": round(b90, 2),
            "daily_burn": round(daily_burn, 2),
            "cashout_day": cashout_day,
            "low_balance": round(low_balance, 2),
            "low_day": low_day,
            "series": series,
            "upcoming_inflows": upcoming,
            "has_bank_data": float(bank_row.scalar() or 0) != 0 if False else current_balance != 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("cash_forecast failed: %s", e)
        raise HTTPException(500, "Internal server error")


# ── CEO P&L SUMMARY (invoice + expense based, no journal required) ─────────────

@router.get("/pnl")
async def ceo_pnl(
    period: str = "ytd",   # ytd | q1 | q2 | q3 | q4 | last30 | last90 | last12m
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Simplified P&L from invoice revenue + expense data.

    Does not require double-entry journal — works for all plan tiers.
    """
    try:
        org_id = member["org_id"]
        today = date.today()

        # Resolve date range
        y = today.year
        if period == "ytd":
            from_date, to_date = date(y, 1, 1), today
        elif period == "q1":
            from_date, to_date = date(y, 1, 1), date(y, 3, 31)
        elif period == "q2":
            from_date, to_date = date(y, 4, 1), date(y, 6, 30)
        elif period == "q3":
            from_date, to_date = date(y, 7, 1), date(y, 9, 30)
        elif period == "q4":
            from_date, to_date = date(y, 10, 1), date(y, 12, 31)
        elif period == "last30":
            from_date, to_date = today - timedelta(days=30), today
        elif period == "last90":
            from_date, to_date = today - timedelta(days=90), today
        else:  # last12m
            from_date, to_date = today - timedelta(days=365), today

        # Revenue (invoiced, not just collected — accrual basis)
        rev = await db.execute(
            text("""
                SELECT
                    COALESCE(SUM(total_amount), 0) AS invoiced,
                    COALESCE(SUM(paid_amount), 0)  AS collected,
                    COALESCE(SUM(tax_amount), 0)   AS tax,
                    COALESCE(SUM(subtotal), 0)     AS subtotal
                FROM invoices
                WHERE org_id = :oid
                  AND status NOT IN ('draft', 'cancelled')
                  AND issued_date BETWEEN :f AND :t
            """).bindparams(oid=org_id, f=from_date, t=to_date)
        )
        rev_row = rev.one()
        invoiced = float(rev_row[0])
        collected = float(rev_row[1])
        tax = float(rev_row[2])
        subtotal = float(rev_row[3])

        # Revenue by month
        monthly_rev = await db.execute(
            text("""
                SELECT date_trunc('month', issued_date) AS month,
                       SUM(total_amount) AS revenue, SUM(paid_amount) AS collected
                FROM invoices
                WHERE org_id = :oid
                  AND status NOT IN ('draft', 'cancelled')
                  AND issued_date BETWEEN :f AND :t
                GROUP BY 1 ORDER BY 1
            """).bindparams(oid=org_id, f=from_date, t=to_date)
        )
        rev_by_month = [{"month": str(r[0])[:7], "revenue": float(r[1] or 0), "collected": float(r[2] or 0)} for r in monthly_rev]

        # Expenses by category
        exp = await db.execute(
            text("""
                SELECT category, COALESCE(SUM(amount), 0) AS total
                FROM expenses
                WHERE org_id = :oid AND date BETWEEN :f AND :t
                GROUP BY category ORDER BY total DESC
            """).bindparams(oid=org_id, f=from_date, t=to_date)
        )
        expense_lines = [{"category": r[0] or "Other", "total": float(r[1])} for r in exp]
        total_expenses = sum(e["total"] for e in expense_lines)

        gross_profit = subtotal - total_expenses
        gross_margin = round(gross_profit / subtotal * 100, 1) if subtotal else 0
        net_income = invoiced - tax - total_expenses

        return {
            "period": period,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "revenue": {
                "invoiced": round(invoiced, 2),
                "collected": round(collected, 2),
                "subtotal": round(subtotal, 2),
                "tax": round(tax, 2),
            },
            "expenses": {
                "total": round(total_expenses, 2),
                "lines": expense_lines,
            },
            "gross_profit": round(gross_profit, 2),
            "gross_margin_pct": gross_margin,
            "net_income": round(net_income, 2),
            "revenue_by_month": rev_by_month,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("ceo_pnl failed: %s", e)
        raise HTTPException(500, "Internal server error")


# ── BUDGET VS ACTUAL SUMMARY ─────────────────────────────────────────────────

@router.get("/budget-summary")
async def budget_summary(
    fiscal_year: Optional[int] = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """High-level budget vs actual: revenue total, expense total, net income."""
    try:
        _require_pro(member["plan"])
        org_id = member["org_id"]
        fy = fiscal_year or date.today().year

        # Get latest approved budget for fiscal year
        budget_row = await db.execute(
            text("""
                SELECT id, name FROM budgets
                WHERE org_id = :oid AND fiscal_year = :fy
                  AND status = 'approved'
                ORDER BY created_at DESC LIMIT 1
            """).bindparams(oid=org_id, fy=fy)
        )
        budget = budget_row.one_or_none()
        if not budget:
            return {"error": "no_approved_budget", "fiscal_year": fy}

        budget_id = str(budget[0])

        # Budget lines (sum per account_code across all months)
        lines = await db.execute(
            text("""
                SELECT bl.account_code, SUM(bl.amount) AS budgeted,
                       ca.account_type, ca.name AS account_name
                FROM budget_lines bl
                LEFT JOIN chart_of_accounts ca ON bl.account_code = ca.code
                WHERE bl.budget_id = :bid
                GROUP BY bl.account_code, ca.account_type, ca.name
            """).bindparams(bid=budget_id)
        )

        revenue_budget = 0.0
        cogs_budget = 0.0
        expense_budget = 0.0
        for l in lines:
            atype = (l[2] or "").lower()
            amt = float(l[1] or 0)
            if "revenue" in atype or "income" in atype:
                revenue_budget += amt
            elif "cost" in atype or "cogs" in atype:
                cogs_budget += amt
            else:
                expense_budget += amt

        # Actual from invoices + expenses
        from_date = date(fy, 1, 1)
        to_date = min(date(fy, 12, 31), date.today())

        rev_actual = await db.execute(
            text("""
                SELECT COALESCE(SUM(total_amount), 0) FROM invoices
                WHERE org_id = :oid AND status NOT IN ('draft','cancelled')
                  AND issued_date BETWEEN :f AND :t
            """).bindparams(oid=org_id, f=from_date, t=to_date)
        )
        exp_actual = await db.execute(
            text("""
                SELECT COALESCE(SUM(amount), 0) FROM expenses
                WHERE org_id = :oid AND date BETWEEN :f AND :t
            """).bindparams(oid=org_id, f=from_date, t=to_date)
        )

        revenue_actual = float(rev_actual.scalar() or 0)
        expense_actual = float(exp_actual.scalar() or 0)

        def _vs(budget: float, actual: float) -> dict:
            variance = actual - budget
            pct = round(variance / budget * 100, 1) if budget else None
            return {"budget": round(budget, 2), "actual": round(actual, 2),
                    "variance": round(variance, 2), "variance_pct": pct}

        return {
            "fiscal_year": fy,
            "budget_name": budget[1],
            "revenue": _vs(revenue_budget, revenue_actual),
            "expenses": _vs(expense_budget + cogs_budget, expense_actual),
            "net_income": _vs(revenue_budget - expense_budget - cogs_budget, revenue_actual - expense_actual),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("budget_summary failed: %s", e)
        raise HTTPException(500, "Internal server error")


# ── BOARD / INVESTOR REPORT PDF ───────────────────────────────────────────────

@router.post("/board-report")
async def generate_board_report(
    body: dict,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Generate a board/investor PDF report.

    Body: {title, period, include_sections: [pnl, cashflow, customers, kpi_goals, benchmarks]}
    """
    try:
        _require_pro(member["plan"])
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
        )

        org_id = member["org_id"]
        period = body.get("period", "ytd")
        report_title = body.get("title", "Board Report")
        include = set(body.get("include_sections", ["pnl", "customers", "kpi_goals"]))
        today = date.today()
        y = today.year

        # Resolve date range
        period_map = {
            "ytd": (date(y, 1, 1), today),
            "q1": (date(y, 1, 1), date(y, 3, 31)),
            "q2": (date(y, 4, 1), date(y, 6, 30)),
            "q3": (date(y, 7, 1), date(y, 9, 30)),
            "q4": (date(y, 10, 1), date(y, 12, 31)),
            "last12m": (today - timedelta(days=365), today),
        }
        from_date, to_date = period_map.get(period, (date(y, 1, 1), today))

        # Fetch data
        org_row = await db.execute(
            text("SELECT name FROM organizations WHERE id = :oid").bindparams(oid=org_id)
        )
        org_name = org_row.scalar() or "Your Company"

        rev_row = await db.execute(
            text("""
                SELECT COALESCE(SUM(total_amount),0), COALESCE(SUM(paid_amount),0),
                       COALESCE(SUM(subtotal),0), COALESCE(SUM(tax_amount),0)
                FROM invoices
                WHERE org_id=:oid AND status NOT IN ('draft','cancelled')
                  AND issued_date BETWEEN :f AND :t
            """).bindparams(oid=org_id, f=from_date, t=to_date)
        )
        rr = rev_row.one()
        invoiced, collected, subtotal, tax = (float(x or 0) for x in rr)

        exp_row = await db.execute(
            text("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE org_id=:oid AND date BETWEEN :f AND :t")
            .bindparams(oid=org_id, f=from_date, t=to_date)
        )
        total_exp = float(exp_row.scalar() or 0)
        gross_profit = subtotal - total_exp
        net_income = invoiced - tax - total_exp

        top_cust = await db.execute(
            text("""
                SELECT c.name, SUM(i.total_amount) AS rev
                FROM invoices i JOIN customers c ON i.customer_id=c.id
                WHERE i.org_id=:oid AND i.status NOT IN ('draft','cancelled')
                  AND i.issued_date BETWEEN :f AND :t
                GROUP BY c.id, c.name ORDER BY rev DESC LIMIT 5
            """).bindparams(oid=org_id, f=from_date, t=to_date)
        )
        customers_data = [(r[0], float(r[1] or 0)) for r in top_cust]

        goals_rows = await db.execute(
            text("""
                SELECT name, metric_key, target_value, period_label, period_start, period_end
                FROM kpi_goals WHERE org_id=:oid AND is_active=true
            """).bindparams(oid=org_id)
        )
        goals = goals_rows.fetchall()

        # Build PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        NAVY = colors.HexColor("#1a2332")
        story = []

        h1 = ParagraphStyle("H1", parent=styles["Heading1"], textColor=NAVY, fontSize=22, spaceAfter=4)
        h2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=NAVY, fontSize=14, spaceAfter=4)
        normal = styles["Normal"]
        small = ParagraphStyle("Small", parent=normal, fontSize=9, textColor=colors.grey)

        # Cover
        story.append(Paragraph(report_title, h1))
        story.append(Paragraph(org_name, ParagraphStyle("Sub", parent=normal, fontSize=13, textColor=colors.grey)))
        story.append(Paragraph(f"Period: {from_date} — {to_date}", small))
        story.append(Paragraph(f"Generated: {today}", small))
        story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=16))

        def _fmt(v: float) -> str:
            return f"{v:,.0f}"

        # KPI summary cards
        story.append(Paragraph("Key Performance Indicators", h2))
        kpi_data = [
            ["Metric", "Value"],
            ["Revenue (invoiced)", _fmt(invoiced)],
            ["Revenue (collected)", _fmt(collected)],
            ["Total Expenses", _fmt(total_exp)],
            ["Gross Profit", _fmt(gross_profit)],
            ["Net Income", _fmt(net_income)],
            ["Gross Margin %", f"{round(gross_profit/subtotal*100,1) if subtotal else 0}%"],
        ]
        t = Table(kpi_data, colWidths=[10*cm, 6*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d1d5db")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5*cm))

        # Top customers
        if "customers" in include and customers_data:
            story.append(Paragraph("Top Customers", h2))
            cust_table = [["Customer", "Revenue"]] + [[c[0], _fmt(c[1])] for c in customers_data]
            ct = Table(cust_table, colWidths=[12*cm, 4*cm])
            ct.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d1d5db")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]))
            story.append(ct)
            story.append(Spacer(1, 0.5*cm))

        # KPI goals
        if "kpi_goals" in include and goals:
            story.append(Paragraph("KPI Goals", h2))
            goals_table = [["Goal", "Metric", "Target", "Period"]]
            for g in goals:
                goals_table.append([g[0], g[1], _fmt(float(g[2])), g[3]])
            gt = Table(goals_table, colWidths=[6*cm, 4*cm, 3*cm, 3*cm])
            gt.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d1d5db")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]))
            story.append(gt)

        doc.build(story)
        buffer.seek(0)

        filename = f"board-report-{today}.pdf"
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("generate_board_report failed: %s", e)
        raise HTTPException(500, "Internal server error")
