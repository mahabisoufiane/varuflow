"""Scenario planning — what-if cash flow projections."""
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.ceo import Scenario
from app.models.organization import OrgPlan

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ceo/scenarios", tags=["scenario_planning"])


def _require_pro(plan: OrgPlan) -> None:
    if plan not in (OrgPlan.PRO, OrgPlan.ENTERPRISE):
        raise HTTPException(status_code=403, detail="PRO plan required")


# ── Pydantic ──────────────────────────────────────────────────────────────────

class AdjustmentItem(BaseModel):
    id: str = ""
    label: str
    category: str          # "revenue" | "expense" | "one_time_inflow" | "one_time_outflow"
    monthly_change: float  # positive = net gain for cash, negative = net loss
    start_month_offset: int = 0   # 0 = starts now, 1 = next month
    end_month_offset: Optional[int] = None  # None = runs to end of horizon


class ScenarioIn(BaseModel):
    name: str
    description: Optional[str] = None
    horizon_months: int = 3
    adjustments: list[AdjustmentItem] = []


class ScenarioPatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    horizon_months: Optional[int] = None
    adjustments: Optional[list[AdjustmentItem]] = None


# ── Base forecast helper (shared logic with ceo_dashboard, duplicated here to
#    avoid circular imports — extract to service if needed) ───────────────────

async def _base_forecast(db: AsyncSession, org_id: str, horizon_days: int) -> tuple[float, dict[date, float], float]:
    """Return (current_balance, inflows_by_date, daily_burn)."""
    today = date.today()

    bank = await db.execute(
        text("SELECT COALESCE(SUM(amount), 0) FROM bank_transactions WHERE org_id=:oid").bindparams(oid=org_id)
    )
    current_balance = float(bank.scalar() or 0)
    if current_balance == 0:
        inv = await db.execute(
            text("SELECT COALESCE(SUM(paid_amount),0) FROM invoices WHERE org_id=:oid AND status='paid' AND issued_date >= now()-interval '12 months'").bindparams(oid=org_id)
        )
        exp = await db.execute(
            text("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE org_id=:oid AND status='approved' AND date >= now()-interval '12 months'").bindparams(oid=org_id)
        )
        current_balance = float(inv.scalar() or 0) - float(exp.scalar() or 0)

    inf_rows = await db.execute(
        text("""
            SELECT due_date, COALESCE(outstanding_amount, total_amount - COALESCE(paid_amount,0)) AS expected
            FROM invoices
            WHERE org_id=:oid AND status IN ('sent','overdue')
              AND due_date BETWEEN :today AND :horizon
        """).bindparams(oid=org_id, today=today, horizon=today + timedelta(days=horizon_days))
    )
    inflows: dict[date, float] = {}
    for r in inf_rows:
        d = r[0] if isinstance(r[0], date) else r[0].date()
        inflows[d] = inflows.get(d, 0.0) + float(r[1] or 0)

    burn = await db.execute(
        text("SELECT COALESCE(SUM(amount),0)/90.0 FROM expenses WHERE org_id=:oid AND status='approved' AND date >= now()-interval '3 months'")
        .bindparams(oid=org_id)
    )
    daily_burn = float(burn.scalar() or 0)

    return current_balance, inflows, daily_burn


def _run_projection(
    current_balance: float,
    inflows: dict[date, float],
    daily_burn: float,
    adjustments: list[dict],
    horizon_days: int,
) -> list[dict]:
    """Apply adjustments to base forecast and return weekly series."""
    today = date.today()
    series = []
    balance = current_balance

    for day_offset in range(horizon_days + 1):
        d = today + timedelta(days=day_offset)
        month_offset = day_offset // 30

        # Base inflow from open invoices
        inflow = inflows.get(d, 0.0)
        outflow = daily_burn

        # Apply scenario adjustments
        for adj in adjustments:
            start = adj.get("start_month_offset", 0)
            end = adj.get("end_month_offset") or horizon_days // 30 + 1
            if start <= month_offset <= end:
                change_per_day = adj.get("monthly_change", 0) / 30.0
                category = adj.get("category", "")
                if category in ("revenue", "one_time_inflow"):
                    inflow += max(0, change_per_day)
                elif category in ("expense", "one_time_outflow"):
                    outflow += max(0, -change_per_day)
                else:
                    # Direct cash flow change (positive = net gain)
                    if change_per_day > 0:
                        inflow += change_per_day
                    else:
                        outflow += -change_per_day

        if day_offset > 0:
            balance = balance + inflow - outflow

        if day_offset % 7 == 0 or day_offset in (30, 60, 90):
            series.append({
                "day": day_offset,
                "date": d.isoformat(),
                "balance": round(balance, 2),
            })

    return series


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("")
async def list_scenarios(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _require_pro(member["plan"])
        rows = await db.execute(
            select(Scenario)
            .where(Scenario.org_id == member["org_id"])
            .order_by(Scenario.updated_at.desc())
        )
        return {
            "scenarios": [
                {
                    "id": str(s.id),
                    "name": s.name,
                    "description": s.description,
                    "horizon_months": s.horizon_months,
                    "adjustment_count": len(s.adjustments) if isinstance(s.adjustments, list) else 0,
                    "updated_at": s.updated_at.isoformat(),
                }
                for s in rows.scalars()
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_scenarios failed: %s", e)
        raise HTTPException(500, "Internal server error")


@router.post("", status_code=201)
async def create_scenario(
    body: ScenarioIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _require_pro(member["plan"])
        s = Scenario(
            org_id=uuid.UUID(member["org_id"]),
            user_id=uuid.UUID(member["user_id"]),
            name=body.name,
            description=body.description,
            horizon_months=min(max(body.horizon_months, 1), 12),
            adjustments=[
                {**a.model_dump(), "id": a.id or str(uuid.uuid4())}
                for a in body.adjustments
            ],
        )
        db.add(s)
        await db.commit()
        await db.refresh(s)
        return {"id": str(s.id), "name": s.name}
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_scenario failed: %s", e)
        raise HTTPException(500, "Internal server error")


@router.patch("/{scenario_id}")
async def update_scenario(
    scenario_id: str,
    body: ScenarioPatch,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _require_pro(member["plan"])
        s = await db.get(Scenario, uuid.UUID(scenario_id))
        if not s or str(s.org_id) != member["org_id"]:
            raise HTTPException(404, "Scenario not found")
        if body.name is not None:
            s.name = body.name
        if body.description is not None:
            s.description = body.description
        if body.horizon_months is not None:
            s.horizon_months = min(max(body.horizon_months, 1), 12)
        if body.adjustments is not None:
            s.adjustments = [
                {**a.model_dump(), "id": a.id or str(uuid.uuid4())}
                for a in body.adjustments
            ]
        s.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_scenario failed: %s", e)
        raise HTTPException(500, "Internal server error")


@router.delete("/{scenario_id}", status_code=204)
async def delete_scenario(
    scenario_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _require_pro(member["plan"])
        s = await db.get(Scenario, uuid.UUID(scenario_id))
        if not s or str(s.org_id) != member["org_id"]:
            raise HTTPException(404, "Scenario not found")
        await db.delete(s)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_scenario failed: %s", e)
        raise HTTPException(500, "Internal server error")


@router.post("/{scenario_id}/run")
async def run_scenario(
    scenario_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Run a scenario and return both base forecast and scenario-adjusted forecast."""
    try:
        _require_pro(member["plan"])
        s = await db.get(Scenario, uuid.UUID(scenario_id))
        if not s or str(s.org_id) != member["org_id"]:
            raise HTTPException(404, "Scenario not found")

        org_id = member["org_id"]
        horizon_days = s.horizon_months * 30

        current_balance, inflows, daily_burn = await _base_forecast(db, org_id, horizon_days)

        base_series = _run_projection(current_balance, inflows, daily_burn, [], horizon_days)
        scenario_series = _run_projection(current_balance, inflows, daily_burn, s.adjustments, horizon_days)

        def _pick(series: list[dict], day: int) -> float:
            return next((p["balance"] for p in series if p["day"] >= day), series[-1]["balance"] if series else 0)

        return {
            "scenario_id": str(s.id),
            "name": s.name,
            "adjustments": s.adjustments,
            "base": {
                "series": base_series,
                "balance_30d": _pick(base_series, 30),
                "balance_60d": _pick(base_series, 60),
                "balance_90d": _pick(base_series, 90),
            },
            "scenario": {
                "series": scenario_series,
                "balance_30d": _pick(scenario_series, 30),
                "balance_60d": _pick(scenario_series, 60),
                "balance_90d": _pick(scenario_series, 90),
            },
            "delta_30d": round(_pick(scenario_series, 30) - _pick(base_series, 30), 2),
            "delta_60d": round(_pick(scenario_series, 60) - _pick(base_series, 60), 2),
            "delta_90d": round(_pick(scenario_series, 90) - _pick(base_series, 90), 2),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("run_scenario failed: %s", e)
        raise HTTPException(500, "Internal server error")
