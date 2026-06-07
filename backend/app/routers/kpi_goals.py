"""KPI Goal tracking — CRUD + live progress computation."""
import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.ceo import KpiGoal

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ceo/goals", tags=["kpi_goals"], dependencies=[Depends(require_module("analytics"))])

# ── Supported metric keys ──────────────────────────────────────────────────────

METRIC_KEYS = {
    "revenue_total":        "Total Revenue (invoiced)",
    "revenue_collected":    "Revenue Collected",
    "new_customers":        "New Customers Acquired",
    "gross_margin_pct":     "Gross Margin %",
    "invoice_paid_rate":    "Invoice Paid-on-Time Rate %",
    "outstanding_ar":       "Outstanding AR (lower = better)",
    "expense_total":        "Total Expenses (lower = better)",
    "invoices_sent":        "Invoices Sent",
}


async def _compute_progress(db: AsyncSession, org_id: str, metric_key: str,
                             period_start: date, period_end: date) -> float:
    """Return current actual value for the given metric over the period."""
    bd = {"oid": org_id, "f": period_start, "t": period_end}

    if metric_key == "revenue_total":
        r = await db.execute(
            text("SELECT COALESCE(SUM(total_amount),0) FROM invoices WHERE org_id=:oid AND status NOT IN ('draft','cancelled') AND issued_date BETWEEN :f AND :t").bindparams(**bd)
        )
        return float(r.scalar() or 0)

    if metric_key == "revenue_collected":
        r = await db.execute(
            text("SELECT COALESCE(SUM(paid_amount),0) FROM invoices WHERE org_id=:oid AND status='paid' AND issued_date BETWEEN :f AND :t").bindparams(**bd)
        )
        return float(r.scalar() or 0)

    if metric_key == "new_customers":
        r = await db.execute(
            text("SELECT COUNT(*) FROM customers WHERE org_id=:oid AND created_at::date BETWEEN :f AND :t AND deleted_at IS NULL").bindparams(**bd)
        )
        return float(r.scalar() or 0)

    if metric_key == "gross_margin_pct":
        rev = await db.execute(
            text("SELECT COALESCE(SUM(subtotal),0) FROM invoices WHERE org_id=:oid AND status NOT IN ('draft','cancelled') AND issued_date BETWEEN :f AND :t").bindparams(**bd)
        )
        exp = await db.execute(
            text("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE org_id=:oid AND date BETWEEN :f AND :t").bindparams(**bd)
        )
        s = float(rev.scalar() or 0)
        e = float(exp.scalar() or 0)
        return round((s - e) / s * 100, 2) if s else 0.0

    if metric_key == "invoice_paid_rate":
        total = await db.execute(
            text("SELECT COUNT(*) FROM invoices WHERE org_id=:oid AND status NOT IN ('draft','cancelled') AND issued_date BETWEEN :f AND :t").bindparams(**bd)
        )
        paid = await db.execute(
            text("SELECT COUNT(*) FROM invoices WHERE org_id=:oid AND status='paid' AND issued_date BETWEEN :f AND :t").bindparams(**bd)
        )
        t_cnt = float(total.scalar() or 0)
        p_cnt = float(paid.scalar() or 0)
        return round(p_cnt / t_cnt * 100, 1) if t_cnt else 0.0

    if metric_key == "outstanding_ar":
        r = await db.execute(
            text("SELECT COALESCE(SUM(outstanding_amount),0) FROM invoices WHERE org_id=:oid AND status IN ('sent','overdue')").bindparams(oid=org_id)
        )
        return float(r.scalar() or 0)

    if metric_key == "expense_total":
        r = await db.execute(
            text("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE org_id=:oid AND date BETWEEN :f AND :t").bindparams(**bd)
        )
        return float(r.scalar() or 0)

    if metric_key == "invoices_sent":
        r = await db.execute(
            text("SELECT COUNT(*) FROM invoices WHERE org_id=:oid AND status NOT IN ('draft','cancelled') AND issued_date BETWEEN :f AND :t").bindparams(**bd)
        )
        return float(r.scalar() or 0)

    return 0.0


def _progress_pct(actual: float, target: float, lower_is_better: bool = False) -> float:
    if target == 0:
        return 0.0
    if lower_is_better:
        # For "lower is better" (expense, AR): 100% = at or below target
        return round(min(100.0, max(0.0, (2 - actual / target) * 100)), 1)
    return round(min(100.0, actual / target * 100), 1)


_LOWER_IS_BETTER = {"outstanding_ar", "expense_total"}


# ── Pydantic ──────────────────────────────────────────────────────────────────

class GoalIn(BaseModel):
    name: str
    metric_key: str
    target_value: float
    period_label: str
    period_start: date
    period_end: date
    currency: str = "SEK"

    @field_validator("metric_key")
    @classmethod
    def _valid_key(cls, v: str) -> str:
        if v not in METRIC_KEYS:
            raise ValueError(f"Unknown metric_key. Allowed: {list(METRIC_KEYS)}")
        return v


class GoalPatch(BaseModel):
    name: Optional[str] = None
    target_value: Optional[float] = None
    period_label: Optional[str] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    is_active: Optional[bool] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/metrics")
async def list_metrics(member=Depends(get_current_member)):
    """Return available metric keys with human labels."""
    return {"metrics": [{"key": k, "label": v} for k, v in METRIC_KEYS.items()]}


@router.get("")
async def list_goals(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        rows = await db.execute(
            select(KpiGoal)
            .where(KpiGoal.org_id == member["org_id"])
            .order_by(KpiGoal.period_end.desc(), KpiGoal.created_at.desc())
        )
        goals = rows.scalars().all()
        result = []
        for g in goals:
            actual = await _compute_progress(db, member["org_id"], g.metric_key, g.period_start, g.period_end)
            lower = g.metric_key in _LOWER_IS_BETTER
            pct = _progress_pct(actual, float(g.target_value), lower)
            result.append({
                "id": str(g.id),
                "name": g.name,
                "metric_key": g.metric_key,
                "metric_label": METRIC_KEYS.get(g.metric_key, g.metric_key),
                "target_value": float(g.target_value),
                "actual_value": round(actual, 2),
                "progress_pct": pct,
                "period_label": g.period_label,
                "period_start": g.period_start.isoformat(),
                "period_end": g.period_end.isoformat(),
                "currency": g.currency,
                "is_active": g.is_active,
                "lower_is_better": lower,
                "on_track": pct >= 70,
            })
        return {"goals": result}
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_goals failed: %s", e)
        raise HTTPException(500, "Internal server error")


@router.post("", status_code=201)
async def create_goal(
    body: GoalIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        g = KpiGoal(
            org_id=uuid.UUID(member["org_id"]),
            user_id=uuid.UUID(member["user_id"]),
            name=body.name,
            metric_key=body.metric_key,
            target_value=Decimal(str(body.target_value)),
            period_label=body.period_label,
            period_start=body.period_start,
            period_end=body.period_end,
            currency=body.currency,
        )
        db.add(g)
        await db.commit()
        await db.refresh(g)
        return {"id": str(g.id), "name": g.name}
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_goal failed: %s", e)
        raise HTTPException(500, "Internal server error")


@router.patch("/{goal_id}")
async def update_goal(
    goal_id: str,
    body: GoalPatch,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        g = await db.get(KpiGoal, uuid.UUID(goal_id))
        if not g or str(g.org_id) != member["org_id"]:
            raise HTTPException(404, "Goal not found")
        if body.name is not None:
            g.name = body.name
        if body.target_value is not None:
            g.target_value = Decimal(str(body.target_value))
        if body.period_label is not None:
            g.period_label = body.period_label
        if body.period_start is not None:
            g.period_start = body.period_start
        if body.period_end is not None:
            g.period_end = body.period_end
        if body.is_active is not None:
            g.is_active = body.is_active
        g.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_goal failed: %s", e)
        raise HTTPException(500, "Internal server error")


@router.delete("/{goal_id}", status_code=204)
async def delete_goal(
    goal_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        g = await db.get(KpiGoal, uuid.UUID(goal_id))
        if not g or str(g.org_id) != member["org_id"]:
            raise HTTPException(404, "Goal not found")
        await db.delete(g)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_goal failed: %s", e)
        raise HTTPException(500, "Internal server error")
