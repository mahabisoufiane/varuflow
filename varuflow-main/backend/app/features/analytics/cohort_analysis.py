"""Cohort Analysis router.

Groups customers by their first invoice month and tracks revenue,
invoice count, and retention across months since acquisition.
"""
import logging
import uuid
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.features.invoicing.models import Customer, Invoice

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cohort-analysis", tags=["cohort-analysis"], dependencies=[Depends(require_module("analytics"))])


async def _build_cohort(
    org_id: uuid.UUID,
    metric: str,
    months: int,
    db: AsyncSession,
) -> dict:
    """
    Returns cohort data:
      - cohorts: list of cohort months (YYYY-MM)
      - columns: 0..N months since acquisition
      - matrix: {cohort_month: {month_offset: value}}
      - avg_ltv_curve: [sum_at_offset_0, sum_at_offset_1, ...]
    """
    # Step 1: find each customer's first invoice month (cohort assignment)
    first_invoice_q = (
        select(
            Invoice.customer_id,
            func.date_trunc("month", func.min(Invoice.issue_date)).label("cohort_month"),
        )
        .where(Invoice.org_id == org_id, Invoice.status.in_(["paid", "sent", "overdue", "draft"]))
        .group_by(Invoice.customer_id)
    )

    # Step 2: for each invoice, determine month_offset from customer cohort
    sql = text("""
        WITH cohorts AS (
            SELECT customer_id, date_trunc('month', MIN(issue_date)) AS cohort_month
            FROM invoices
            WHERE org_id = :org_id AND status != 'DRAFT'
            GROUP BY customer_id
        ),
        tagged AS (
            SELECT
                c.cohort_month,
                date_trunc('month', i.issue_date) AS activity_month,
                EXTRACT(epoch FROM date_trunc('month', i.issue_date) - c.cohort_month)::int / 2592000 AS month_offset,
                i.customer_id,
                i.total_sek,
                i.id AS invoice_id
            FROM invoices i
            JOIN cohorts c ON c.customer_id = i.customer_id
            WHERE i.org_id = :org_id AND i.status != 'DRAFT'
        )
        SELECT
            TO_CHAR(cohort_month, 'YYYY-MM') AS cohort,
            month_offset::int AS month_offset,
            COUNT(DISTINCT customer_id) AS customer_count,
            COALESCE(SUM(total_sek), 0) AS revenue,
            COUNT(invoice_id) AS invoice_count
        FROM tagged
        WHERE month_offset >= 0 AND month_offset < :months
        GROUP BY cohort_month, month_offset
        ORDER BY cohort_month, month_offset
    """)
    result = await db.execute(sql, {"org_id": str(org_id), "months": months})
    rows = result.mappings().all()

    # Also get cohort size (distinct customers per cohort month)
    size_sql = text("""
        SELECT TO_CHAR(date_trunc('month', first_date), 'YYYY-MM') AS cohort,
               COUNT(DISTINCT customer_id) AS cohort_size
        FROM invoices
        WHERE org_id = :org_id AND status != 'DRAFT'
        GROUP BY date_trunc('month', issue_date)
        HAVING date_trunc('month', MIN(issue_date)) = date_trunc('month', issue_date)
    """)
    # Simpler: use the first_invoice aggregation
    size_sql2 = text("""
        SELECT TO_CHAR(date_trunc('month', first_date), 'YYYY-MM') AS cohort,
               COUNT(DISTINCT customer_id) AS cohort_size
        FROM (
            SELECT customer_id, MIN(issue_date) AS first_date
            FROM invoices WHERE org_id = :org_id AND status != 'DRAFT'
            GROUP BY customer_id
        ) sub
        GROUP BY date_trunc('month', first_date)
    """)
    size_result = await db.execute(size_sql2, {"org_id": str(org_id)})
    cohort_sizes = {r["cohort"]: r["cohort_size"] for r in size_result.mappings().all()}

    # Build matrix
    cohort_months = sorted({r["cohort"] for r in rows})
    matrix: dict[str, dict[int, float]] = {c: {} for c in cohort_months}
    retention_matrix: dict[str, dict[int, float]] = {c: {} for c in cohort_months}

    for r in rows:
        cohort = r["cohort"]
        offset = int(r["month_offset"])
        if metric == "revenue":
            value = float(r["revenue"])
        elif metric == "invoice_count":
            value = float(r["invoice_count"])
        else:  # retention_rate
            cs = cohort_sizes.get(cohort, 1)
            value = round(float(r["customer_count"]) / cs * 100, 1)
        matrix[cohort][offset] = round(value, 2)

    # Max offset seen
    max_offset = max((r["month_offset"] for r in rows), default=0)

    # LTV curve: average metric at each offset across all cohorts
    ltv_curve = []
    for offset in range(max_offset + 1):
        values = [matrix[c].get(offset, None) for c in cohort_months]
        non_null = [v for v in values if v is not None]
        ltv_curve.append(round(sum(non_null) / len(non_null), 2) if non_null else 0)

    # Best cohort: highest cumulative revenue/metric
    best_cohort = None
    best_total = -1
    for c in cohort_months:
        total = sum(matrix[c].values())
        if total > best_total:
            best_total = total
            best_cohort = c

    return {
        "cohorts": cohort_months,
        "columns": list(range(max_offset + 1)),
        "matrix": {c: {str(k): v for k, v in offsets.items()} for c, offsets in matrix.items()},
        "cohort_sizes": cohort_sizes,
        "avg_ltv_curve": ltv_curve,
        "metric": metric,
        "best_cohort": best_cohort,
        "best_cohort_total": round(best_total, 2) if best_cohort else 0,
    }


@router.get("")
async def get_cohort_analysis(
    metric: str = Query("revenue", pattern="^(revenue|invoice_count|retention_rate)$"),
    months: int = Query(12, ge=1, le=36),
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return cohort grid with metric values per (cohort_month × month_offset)."""
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        data = await _build_cohort(org_id, metric, months, db)
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"cohort_analysis failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/ltv-summary")
async def ltv_summary(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Quick summary: avg LTV by 3-month, 6-month, 12-month milestones."""
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        data = await _build_cohort(org_id, "revenue", 13, db)
        curve = data["avg_ltv_curve"]

        def cumulative_by(n: int) -> float:
            return round(sum(curve[:n]), 2) if len(curve) >= n else round(sum(curve), 2)

        return {
            "ltv_3m": cumulative_by(3),
            "ltv_6m": cumulative_by(6),
            "ltv_12m": cumulative_by(12),
            "best_cohort": data["best_cohort"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ltv_summary failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")
