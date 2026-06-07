"""AI Cash Flow Prediction router.

Combines outstanding invoice collection forecasts (weighted by each customer's
historical payment delay), recurring expense commitments, and user scenarios
to project a 90-day cash position with best/expected/worst bands.
"""
import logging
import math
import uuid
from datetime import date, datetime, timedelta, timezone
from statistics import mean, stdev
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.cashflow_scenario import CashFlowScenario
from app.models.invoicing import Invoice, Payment

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cashflow-prediction", tags=["cashflow-prediction"], dependencies=[Depends(require_module("finance"))])


# ── Engine ────────────────────────────────────────────────────────────────────

async def _customer_avg_delay(org_id: uuid.UUID, db: AsyncSession) -> dict[str, float]:
    """Return {customer_id: avg_days_late} for the past 12 months."""
    cutoff = date.today() - timedelta(days=365)
    result = await db.execute(
        select(
            Invoice.customer_id,
            Invoice.due_date,
            Payment.payment_date,
        )
        .join(Payment, Payment.invoice_id == Invoice.id)
        .where(
            Invoice.org_id == org_id,
            Invoice.issue_date >= cutoff,
            Invoice.status == "paid",
        )
    )
    rows = result.all()

    by_customer: dict[str, list[float]] = {}
    for customer_id, due_date, payment_date in rows:
        delay = (payment_date - due_date).days
        key = str(customer_id)
        by_customer.setdefault(key, []).append(float(delay))

    return {k: mean(v) for k, v in by_customer.items()}


async def _open_invoices(org_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(Invoice)
        .where(
            Invoice.org_id == org_id,
            Invoice.status.in_(["sent", "overdue"]),
        )
    )
    return [
        {
            "id": str(inv.id),
            "customer_id": str(inv.customer_id),
            "due_date": inv.due_date,
            "amount": float(inv.total_sek),
        }
        for inv in result.scalars().all()
    ]


async def _active_scenarios(org_id: uuid.UUID, db: AsyncSession) -> list[CashFlowScenario]:
    result = await db.execute(
        select(CashFlowScenario)
        .where(CashFlowScenario.org_id == org_id, CashFlowScenario.is_active.is_(True))
    )
    return result.scalars().all()


def _build_projection(
    open_invoices: list[dict],
    avg_delay: dict[str, float],
    scenarios: list[CashFlowScenario],
    days: int = 90,
    alert_threshold: float = 0.0,
) -> dict:
    today = date.today()
    horizon = today + timedelta(days=days)

    # Day-by-day balance map: {date_str: {best, expected, worst}}
    daily: dict[str, dict] = {}
    for d in range(days + 1):
        dt = today + timedelta(days=d)
        daily[dt.isoformat()] = {"best": 0.0, "expected": 0.0, "worst": 0.0}

    # Scenario impact: spread monthly_delta evenly across days of their months
    for sc in scenarios:
        for m in range(sc.months_duration):
            for d in range(28):  # approximate month as 28 days
                dt = today + timedelta(days=m * 30 + d)
                if dt > horizon:
                    break
                day_delta = float(sc.monthly_delta) / 28
                if dt.isoformat() in daily:
                    daily[dt.isoformat()]["best"] += day_delta
                    daily[dt.isoformat()]["expected"] += day_delta
                    daily[dt.isoformat()]["worst"] += day_delta

    # Outstanding inflows from open invoices
    recommendations: list[dict] = []
    for inv in open_invoices:
        cid = str(inv["customer_id"])
        delay = avg_delay.get(cid, 7.0)  # default 7-day delay

        best_dt = inv["due_date"]                           # pays on due date
        expected_dt = inv["due_date"] + timedelta(days=max(0, delay))
        worst_dt = inv["due_date"] + timedelta(days=max(0, delay * 2))

        for band, pay_dt in [("best", best_dt), ("expected", expected_dt), ("worst", worst_dt)]:
            if today <= pay_dt <= horizon:
                key = pay_dt.isoformat()
                if key in daily:
                    daily[key][band] += inv["amount"]

        # Recommend collection for invoices expected beyond 30 days
        if expected_dt > today + timedelta(days=30):
            recommendations.append({
                "invoice_id": inv["id"],
                "customer_id": cid,
                "amount": inv["amount"],
                "due_date": inv["due_date"].isoformat(),
                "expected_payment": expected_dt.isoformat(),
                "avg_delay_days": round(delay, 1),
            })

    recommendations.sort(key=lambda r: r["amount"], reverse=True)

    # Accumulate daily into running totals
    running = {"best": 0.0, "expected": 0.0, "worst": 0.0}
    points: list[dict] = []
    for d in range(days + 1):
        dt = (today + timedelta(days=d)).isoformat()
        for band in ("best", "expected", "worst"):
            running[band] += daily.get(dt, {}).get(band, 0.0)
        points.append({"date": dt, **{k: round(v, 2) for k, v in running.items()}})

    # Alerts: first date expected balance drops below threshold
    alert = None
    for p in points:
        if p["expected"] < alert_threshold:
            alert = {"date": p["date"], "projected_balance": p["expected"]}
            break

    # 30/60/90-day snapshots
    snap_30 = next((p for p in points if p["date"] == (today + timedelta(days=30)).isoformat()), None)
    snap_60 = next((p for p in points if p["date"] == (today + timedelta(days=60)).isoformat()), None)
    snap_90 = points[-1]

    return {
        "projection": points,
        "snapshots": {"day_30": snap_30, "day_60": snap_60, "day_90": snap_90},
        "alert": alert,
        "recommendations": recommendations[:5],
    }


# ── Schemas ───────────────────────────────────────────────────────────────────

class ScenarioCreateIn(BaseModel):
    name: str
    description: Optional[str] = None
    monthly_delta: float
    months_duration: int = 12


class ScenarioUpdateIn(BaseModel):
    name: Optional[str] = None
    monthly_delta: Optional[float] = None
    months_duration: Optional[int] = None
    is_active: Optional[bool] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/forecast")
async def get_forecast(
    days: int = Query(90, ge=30, le=365),
    alert_threshold: float = Query(0.0),
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return 30/60/90-day cash flow projection with best/expected/worst bands."""
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        avg_delay, open_invoices, scenarios = await _customer_avg_delay(org_id, db), [], []
        open_invoices = await _open_invoices(org_id, db)
        scenarios = await _active_scenarios(org_id, db)
        result = _build_projection(open_invoices, avg_delay, scenarios, days, alert_threshold)
        result["open_invoice_count"] = len(open_invoices)
        result["open_invoice_total"] = round(sum(i["amount"] for i in open_invoices), 2)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"cashflow forecast failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/customer-behavior")
async def customer_behavior(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Per-customer average payment delay over the last 12 months."""
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        delays = await _customer_avg_delay(org_id, db)
        items = [
            {"customer_id": cid, "avg_days_late": round(delay, 1)}
            for cid, delay in sorted(delays.items(), key=lambda x: x[1], reverse=True)
        ]
        return {"items": items}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"customer_behavior failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/scenarios")
async def list_scenarios(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        result = await db.execute(
            select(CashFlowScenario)
            .where(CashFlowScenario.org_id == org_id)
            .order_by(CashFlowScenario.created_at.desc())
        )
        scenarios = result.scalars().all()
        return {
            "items": [
                {"id": str(s.id), "name": s.name, "description": s.description,
                 "monthly_delta": float(s.monthly_delta), "months_duration": s.months_duration,
                 "is_active": s.is_active}
                for s in scenarios
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_scenarios failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/scenarios", status_code=201)
async def create_scenario(
    body: ScenarioCreateIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        user_id = uuid.UUID(str(member["user_id"]))
        sc = CashFlowScenario(
            id=uuid.uuid4(), org_id=org_id, created_by=user_id,
            name=body.name, description=body.description,
            monthly_delta=body.monthly_delta, months_duration=body.months_duration,
        )
        db.add(sc)
        await db.commit()
        await db.refresh(sc)
        return {"id": str(sc.id), "name": sc.name}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"create_scenario failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/scenarios/{scenario_id}")
async def update_scenario(
    scenario_id: uuid.UUID,
    body: ScenarioUpdateIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        sc = await db.get(CashFlowScenario, scenario_id)
        if not sc or sc.org_id != org_id:
            raise HTTPException(status_code=404, detail="Scenario not found")
        for field, val in body.model_dump(exclude_unset=True).items():
            setattr(sc, field, val)
        await db.commit()
        return {"id": str(sc.id), "name": sc.name}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"update_scenario failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/scenarios/{scenario_id}", status_code=204)
async def delete_scenario(
    scenario_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        sc = await db.get(CashFlowScenario, scenario_id)
        if not sc or sc.org_id != org_id:
            raise HTTPException(status_code=404, detail="Scenario not found")
        await db.delete(sc)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"delete_scenario failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")
