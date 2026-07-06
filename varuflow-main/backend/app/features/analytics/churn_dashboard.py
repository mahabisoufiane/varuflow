"""Churn Dashboard router — identify lost customers and MRR impact."""
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)
router = APIRouter(tags=["churn-dashboard"], dependencies=[Depends(require_module("analytics"))])

_CHURN_REASONS = [
    "price_too_high", "switched_to_competitor", "no_longer_needed",
    "poor_service", "missing_features", "went_out_of_business", "other",
]

_CHURN_REASON_LABELS = {
    "price_too_high": "Price too high",
    "switched_to_competitor": "Switched to competitor",
    "no_longer_needed": "No longer needed",
    "poor_service": "Poor service",
    "missing_features": "Missing features",
    "went_out_of_business": "Went out of business",
    "other": "Other",
}


class MarkChurned(BaseModel):
    customer_id: str
    churn_reason: str | None = None
    churned_at: str | None = None  # ISO date string, defaults to now


class UpdateChurnScore(BaseModel):
    customer_id: str
    score: float  # 0–100


# ── Overview ──────────────────────────────────────────────────────────────────

@router.get("/api/growth/churn/overview")
async def churn_overview(
    months: int = 12,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns:
    - Explicitly churned customers (marked via mark-churned)
    - Inferred churned: active customers with no invoice in >90 days
    - MRR lost, churn rate, churn reasons breakdown
    """
    try:
        org_id = member["org_id"]
        cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)
        inactivity_threshold = datetime.now(timezone.utc) - timedelta(days=90)

        # Explicitly marked churned customers
        explicit = await db.execute(text("""
            SELECT
                c.id, c.company_name, c.email, c.churned_at, c.churn_reason, c.churn_score,
                COALESCE(
                    (SELECT SUM(i.total_sek)
                     FROM invoices i
                     WHERE i.customer_id = c.id
                       AND i.org_id = :org_id
                       AND i.status = 'PAID'
                       AND i.issue_date >= NOW() - INTERVAL '12 months'),
                    0
                ) AS revenue_last_12m,
                (SELECT MAX(i.issue_date) FROM invoices i WHERE i.customer_id = c.id AND i.org_id = :org_id) AS last_invoice_date
            FROM customers c
            WHERE c.org_id = :org_id
              AND c.churned_at IS NOT NULL
              AND c.churned_at >= :cutoff
            ORDER BY c.churned_at DESC
            LIMIT 200
        """), {"org_id": org_id, "cutoff": cutoff})
        explicit_rows = explicit.fetchall()

        # Inferred at-risk / implicit churn (no paid invoice in 90+ days, still "active")
        implicit = await db.execute(text("""
            SELECT
                c.id, c.company_name, c.email, c.churn_score,
                MAX(i.issue_date) AS last_invoice_date,
                COALESCE(SUM(CASE WHEN i.issue_date >= NOW() - INTERVAL '12 months' AND i.status='PAID' THEN i.total_sek ELSE 0 END), 0) AS revenue_last_12m
            FROM customers c
            LEFT JOIN invoices i ON i.customer_id = c.id AND i.org_id = c.org_id
            WHERE c.org_id = :org_id
              AND c.churned_at IS NULL
              AND (c.deleted_at IS NULL OR c.deleted_at > NOW())
            GROUP BY c.id, c.company_name, c.email, c.churn_score
            HAVING MAX(i.issue_date) < :threshold OR MAX(i.issue_date) IS NULL
            ORDER BY last_invoice_date ASC NULLS FIRST
            LIMIT 100
        """), {"org_id": org_id, "threshold": inactivity_threshold})
        implicit_rows = implicit.fetchall()

        # Monthly churn counts
        monthly = await db.execute(text("""
            SELECT
                TO_CHAR(churned_at, 'YYYY-MM') AS month,
                COUNT(*) AS churned_count
            FROM customers
            WHERE org_id = :org_id
              AND churned_at >= :cutoff
            GROUP BY 1
            ORDER BY 1
        """), {"org_id": org_id, "cutoff": cutoff})
        monthly_rows = monthly.fetchall()

        # Churn reason breakdown
        reasons = await db.execute(text("""
            SELECT churn_reason, COUNT(*) AS n
            FROM customers
            WHERE org_id = :org_id AND churned_at IS NOT NULL AND churn_reason IS NOT NULL
            GROUP BY churn_reason
            ORDER BY n DESC
        """), {"org_id": org_id})
        reason_rows = reasons.fetchall()

        # Total active customers for churn rate
        total_active = await db.execute(text("""
            SELECT COUNT(*) FROM customers
            WHERE org_id = :org_id AND churned_at IS NULL AND (deleted_at IS NULL OR deleted_at > NOW())
        """), {"org_id": org_id})
        total_count = total_active.scalar() or 1

        explicit_list = [
            {
                "id": str(r.id), "name": r.name, "email": r.email or "",
                "churned_at": r.churned_at.isoformat() if r.churned_at else None,
                "churn_reason": r.churn_reason,
                "churn_reason_label": _CHURN_REASON_LABELS.get(r.churn_reason or "", r.churn_reason or "Unknown"),
                "churn_score": float(r.churn_score) if r.churn_score else None,
                "revenue_lost_12m": float(r.revenue_last_12m),
                "last_invoice_date": r.last_invoice_date.isoformat() if r.last_invoice_date else None,
                "type": "explicit",
            }
            for r in explicit_rows
        ]
        implicit_list = [
            {
                "id": str(r.id), "name": r.name, "email": r.email or "",
                "churned_at": None,
                "churn_reason": None,
                "churn_score": float(r.churn_score) if r.churn_score else None,
                "revenue_lost_12m": float(r.revenue_last_12m),
                "last_invoice_date": r.last_invoice_date.isoformat() if r.last_invoice_date else None,
                "type": "inferred",
                "days_inactive": (datetime.now(timezone.utc).date() - r.last_invoice_date).days if r.last_invoice_date else None,
            }
            for r in implicit_rows
        ]

        total_revenue_lost = sum(c["revenue_lost_12m"] for c in explicit_list)
        churn_rate = round(len(explicit_list) / (total_count + len(explicit_list)) * 100, 2)

        return {
            "churned_customers": explicit_list,
            "at_risk_customers": implicit_list,
            "monthly_churn": [{"month": r.month, "count": r.churned_count} for r in monthly_rows],
            "reasons_breakdown": [
                {
                    "reason": r.churn_reason,
                    "label": _CHURN_REASON_LABELS.get(r.churn_reason or "", r.churn_reason or ""),
                    "count": r.n,
                }
                for r in reason_rows
            ],
            "summary": {
                "total_churned": len(explicit_list),
                "total_at_risk": len(implicit_list),
                "total_revenue_lost": total_revenue_lost,
                "churn_rate_pct": churn_rate,
                "active_customers": total_count,
                "period_months": months,
            },
            "reason_options": [
                {"value": k, "label": v} for k, v in _CHURN_REASON_LABELS.items()
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"churn_overview failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/growth/churn/mark-churned")
async def mark_churned(
    body: MarkChurned,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Explicitly mark a customer as churned."""
    try:
        org_id = member["org_id"]
        if body.churn_reason and body.churn_reason not in _CHURN_REASONS:
            raise HTTPException(status_code=422, detail=f"Invalid churn reason. Must be one of: {_CHURN_REASONS}")

        churned_at = datetime.now(timezone.utc)
        if body.churned_at:
            try:
                churned_at = datetime.fromisoformat(body.churned_at.replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(status_code=422, detail="Invalid churned_at date format")

        result = await db.execute(text("""
            UPDATE customers
            SET churned_at = :churned_at, churn_reason = :reason, is_active = false
            WHERE id = :id AND org_id = :org_id
            RETURNING id, name
        """), {
            "churned_at": churned_at, "reason": body.churn_reason,
            "id": body.customer_id, "org_id": org_id,
        })
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Customer not found")
        await db.commit()
        return {"id": str(row.id), "name": row.name, "churned_at": churned_at.isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"mark_churned failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/growth/churn/unmark-churned")
async def unmark_churned(
    customer_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Re-activate a customer (they came back)."""
    try:
        org_id = member["org_id"]
        result = await db.execute(text("""
            UPDATE customers
            SET churned_at = NULL, churn_reason = NULL, is_active = true
            WHERE id = :id AND org_id = :org_id
            RETURNING id, name
        """), {"id": customer_id, "org_id": org_id})
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Customer not found")
        await db.commit()
        return {"id": str(row.id), "name": row.name, "reactivated": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"unmark_churned failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/growth/churn/risk-scores")
async def churn_risk_scores(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """
    Compute heuristic churn risk scores for non-churned customers.
    Score 0–100: higher = more at risk.
    Factors: days since last invoice, YoY revenue decline, invoice frequency drop.
    """
    try:
        org_id = member["org_id"]
        rows = await db.execute(text("""
            WITH customer_stats AS (
                SELECT
                    c.id, c.company_name, c.email,
                    MAX(i.issue_date) AS last_invoice_date,
                    COUNT(CASE WHEN i.issue_date >= NOW() - INTERVAL '12 months' THEN 1 END) AS invoices_l12m,
                    COUNT(CASE WHEN i.issue_date BETWEEN NOW() - INTERVAL '24 months' AND NOW() - INTERVAL '12 months' THEN 1 END) AS invoices_prev_12m,
                    COALESCE(SUM(CASE WHEN i.issue_date >= NOW() - INTERVAL '12 months' AND i.status='PAID' THEN i.total_sek ELSE 0 END), 0) AS rev_l12m,
                    COALESCE(SUM(CASE WHEN i.issue_date BETWEEN NOW() - INTERVAL '24 months' AND NOW() - INTERVAL '12 months' AND i.status='PAID' THEN i.total_sek ELSE 0 END), 0) AS rev_prev_12m
                FROM customers c
                LEFT JOIN invoices i ON i.customer_id = c.id AND i.org_id = c.org_id AND i.status != 'DRAFT'
                WHERE c.org_id = :org_id
                  AND c.churned_at IS NULL
                  AND (c.deleted_at IS NULL OR c.deleted_at > NOW())
                GROUP BY c.id, c.company_name, c.email
            )
            SELECT *,
                EXTRACT(DAY FROM NOW() - last_invoice_date::timestamptz)::int AS days_inactive
            FROM customer_stats
            WHERE last_invoice_date IS NOT NULL
            ORDER BY days_inactive DESC NULLS LAST
            LIMIT 200
        """), {"org_id": org_id})

        results = []
        for r in rows.fetchall():
            days = r.days_inactive or 0
            # Recency score (0-50): 50 = 180+ days inactive
            recency_score = min(50, days / 180 * 50)
            # Frequency drop score (0-30)
            freq_drop = 0
            if r.invoices_prev_12m > 0:
                freq_drop = max(0, (r.invoices_prev_12m - r.invoices_l12m) / r.invoices_prev_12m * 30)
            elif r.invoices_l12m == 0:
                freq_drop = 15
            # Revenue drop score (0-20)
            rev_drop = 0
            if r.rev_prev_12m > 0:
                rev_drop = max(0, (float(r.rev_prev_12m) - float(r.rev_l12m)) / float(r.rev_prev_12m) * 20)
            score = round(min(100, recency_score + freq_drop + rev_drop), 1)
            results.append({
                "id": str(r.id), "name": r.name, "email": r.email or "",
                "churn_score": score,
                "days_inactive": days,
                "invoices_l12m": r.invoices_l12m,
                "invoices_prev_12m": r.invoices_prev_12m,
                "rev_l12m": float(r.rev_l12m),
                "rev_prev_12m": float(r.rev_prev_12m),
                "risk_level": "high" if score >= 65 else "medium" if score >= 35 else "low",
            })
        results.sort(key=lambda x: -x["churn_score"])
        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"churn_risk_scores failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")
