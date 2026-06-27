"""Pricing Experiments router — A/B test invoice price changes."""
import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.growth import PricingExperiment

logger = logging.getLogger(__name__)
router = APIRouter(tags=["pricing-experiments"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ExperimentCreate(BaseModel):
    name: str
    description: str | None = None
    control_label: str = "Control (current prices)"
    variant_label: str = "Variant (+10%)"
    control_price_pct_change: float = 0.0
    variant_price_pct_change: float = 0.10
    start_date: date | None = None
    end_date: date | None = None

class ExperimentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    control_label: str | None = None
    variant_label: str | None = None
    control_price_pct_change: float | None = None
    variant_price_pct_change: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None

class AssignCustomers(BaseModel):
    control_ids: list[str] = []
    variant_ids: list[str] = []


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/api/growth/experiments")
async def list_experiments(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        rows = (await db.execute(
            select(PricingExperiment)
            .where(PricingExperiment.org_id == org_id)
            .order_by(PricingExperiment.created_at.desc())
        )).scalars().all()
        return [_exp_dict(e) for e in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_experiments failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/growth/experiments", status_code=201)
async def create_experiment(
    body: ExperimentCreate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        exp = PricingExperiment(
            org_id=org_id,
            name=body.name,
            description=body.description,
            control_label=body.control_label,
            variant_label=body.variant_label,
            control_price_pct_change=Decimal(str(body.control_price_pct_change)),
            variant_price_pct_change=Decimal(str(body.variant_price_pct_change)),
            start_date=body.start_date,
            end_date=body.end_date,
        )
        db.add(exp)
        await db.commit()
        await db.refresh(exp)
        return _exp_dict(exp)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_experiment failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/growth/experiments/{exp_id}")
async def update_experiment(
    exp_id: str,
    body: ExperimentUpdate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        exp = (await db.execute(
            select(PricingExperiment).where(PricingExperiment.id == exp_id, PricingExperiment.org_id == org_id)
        )).scalar_one_or_none()
        if not exp:
            raise HTTPException(status_code=404, detail="Experiment not found")
        data = body.model_dump(exclude_none=True)
        for field, val in data.items():
            if field in ("control_price_pct_change", "variant_price_pct_change"):
                val = Decimal(str(val))
            setattr(exp, field, val)
        await db.commit()
        await db.refresh(exp)
        return _exp_dict(exp)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_experiment failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/growth/experiments/{exp_id}/assign")
async def assign_customers(
    exp_id: str,
    body: AssignCustomers,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Assign customer lists to control/variant groups."""
    try:
        org_id = member["org_id"]
        exp = (await db.execute(
            select(PricingExperiment).where(PricingExperiment.id == exp_id, PricingExperiment.org_id == org_id)
        )).scalar_one_or_none()
        if not exp:
            raise HTTPException(status_code=404, detail="Experiment not found")
        exp.assigned_control_ids = body.control_ids
        exp.assigned_variant_ids = body.variant_ids
        await db.commit()
        await db.refresh(exp)
        return _exp_dict(exp)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"assign_customers failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/growth/experiments/{exp_id}/results")
async def experiment_results(
    exp_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Compute revenue per customer for control vs variant groups."""
    try:
        org_id = member["org_id"]
        exp = (await db.execute(
            select(PricingExperiment).where(PricingExperiment.id == exp_id, PricingExperiment.org_id == org_id)
        )).scalar_one_or_none()
        if not exp:
            raise HTTPException(status_code=404, detail="Experiment not found")

        control_ids = exp.assigned_control_ids or []
        variant_ids = exp.assigned_variant_ids or []

        async def _revenue_for(customer_ids: list[str]) -> dict:
            if not customer_ids:
                return {"avg_invoice_value": 0, "total_revenue": 0, "invoice_count": 0, "customer_count": 0}
            result = await db.execute(text("""
                SELECT
                    COUNT(*) FILTER (WHERE i.status NOT IN ('draft','cancelled')) AS invoice_count,
                    COALESCE(SUM(i.total_amount) FILTER (WHERE i.status NOT IN ('draft','cancelled')), 0) AS total_revenue,
                    COALESCE(AVG(i.total_amount) FILTER (WHERE i.status NOT IN ('draft','cancelled')), 0) AS avg_invoice_value
                FROM invoices i
                WHERE i.org_id = :org_id
                  AND i.customer_id = ANY(:ids)
                  AND (:start_date::date IS NULL OR i.issue_date >= :start_date)
                  AND (:end_date::date IS NULL OR i.issue_date <= :end_date)
            """), {
                "org_id": org_id, "ids": customer_ids,
                "start_date": str(exp.start_date) if exp.start_date else None,
                "end_date": str(exp.end_date) if exp.end_date else None,
            })
            row = result.fetchone()
            return {
                "avg_invoice_value": float(row.avg_invoice_value or 0),
                "total_revenue": float(row.total_revenue or 0),
                "invoice_count": int(row.invoice_count or 0),
                "customer_count": len(customer_ids),
            }

        control_stats = await _revenue_for(control_ids)
        variant_stats = await _revenue_for(variant_ids)

        # Revenue lift
        ctrl_avg = control_stats["avg_invoice_value"]
        var_avg = variant_stats["avg_invoice_value"]
        lift_pct = ((var_avg - ctrl_avg) / ctrl_avg * 100) if ctrl_avg > 0 else 0

        return {
            "experiment": _exp_dict(exp),
            "control": control_stats,
            "variant": variant_stats,
            "lift_pct": round(lift_pct, 2),
            "expected_lift_pct": float(exp.variant_price_pct_change - exp.control_price_pct_change) * 100,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"experiment_results failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/growth/experiments/{exp_id}", status_code=204)
async def delete_experiment(
    exp_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        exp = (await db.execute(
            select(PricingExperiment).where(PricingExperiment.id == exp_id, PricingExperiment.org_id == org_id)
        )).scalar_one_or_none()
        if not exp:
            raise HTTPException(status_code=404, detail="Experiment not found")
        await db.delete(exp)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_experiment failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Customers list for assigning ──────────────────────────────────────────────

@router.get("/api/growth/experiments/customers-pool")
async def customers_pool(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return active customers for assignment to experiment groups."""
    try:
        org_id = member["org_id"]
        rows = await db.execute(text("""
            SELECT id, name, COALESCE(email,'') AS email
            FROM customers
            WHERE org_id = :org_id
            ORDER BY name
            LIMIT 500
        """), {"org_id": org_id})
        return [{"id": str(r.id), "name": r.name, "email": r.email} for r in rows.fetchall()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"customers_pool failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


def _exp_dict(e: PricingExperiment) -> dict:
    return {
        "id": str(e.id), "name": e.name, "description": e.description,
        "status": e.status,
        "control_label": e.control_label, "variant_label": e.variant_label,
        "control_price_pct_change": float(e.control_price_pct_change),
        "variant_price_pct_change": float(e.variant_price_pct_change),
        "assigned_control_ids": e.assigned_control_ids or [],
        "assigned_variant_ids": e.assigned_variant_ids or [],
        "start_date": e.start_date.isoformat() if e.start_date else None,
        "end_date": e.end_date.isoformat() if e.end_date else None,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }
