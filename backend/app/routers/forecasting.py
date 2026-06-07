"""Inventory forecasting router (Item 41).

Endpoints under ``/api/analytics/forecasting``:

* ``GET  /``                           — full forecast table per product.
* ``GET  /at-risk``                    — products projected to stock out.
* ``GET  /{product_id}``               — single-product detail.
* ``POST /{product_id}/compare``       — forecast vs actual window.
* ``GET  /export.csv``                 — forecast export as CSV.

All endpoints require PRO+ plan (feature gate — the forecaster is a
paying-tier product). Read-only by design; the single mutation is
the CSV export, which audits as ``forecast.exported`` so the owner
can trace who pulled data out of the system.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_plan, require_module
from app.models.organization import OrgPlan
from app.services import forecasting_engine as svc
from app.services.audit import log_action

router = APIRouter(
    prefix="/api/analytics/forecasting",
    tags=["analytics", "forecasting"],
    dependencies=[Depends(require_module("analytics"))],
)


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _actor(ctx: tuple) -> uuid.UUID | None:
    user, _ = ctx
    uid = user.get("user_id")
    if isinstance(uid, uuid.UUID):
        return uid
    try:
        return uuid.UUID(str(uid))
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════


class ForecastOut(BaseModel):
    product_id: uuid.UUID
    name: str
    sku: str
    on_hand: int
    reorder_level: int
    avg_daily_demand: float
    days_until_stockout: float | None
    forecast_30: int
    forecast_60: int
    forecast_90: int
    trend: str
    at_risk: bool


class ForecastReport(BaseModel):
    generated_at: datetime
    horizon_days: list[int]
    at_risk_days: int
    lookback_days: int
    rows: list[ForecastOut]
    at_risk_count: int


class CompareIn(BaseModel):
    # Window start. The end is "now" — forecast-vs-actual is always
    # "how did we do in the X days leading up to today".
    lookback_days: int = Field(default=30, ge=1, le=365)


class CompareRow(BaseModel):
    product_id: uuid.UUID
    forecast: int
    actual: int
    variance: int
    variance_pct: float


# ═══════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════


@router.get("", response_model=ForecastReport)
async def forecast_report(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan: None = Depends(require_plan(OrgPlan.PRO)),
    at_risk_days: int = Query(default=svc.DEFAULT_AT_RISK_DAYS, ge=1, le=365),
    lookback_days: int = Query(default=svc.DEFAULT_LOOKBACK_DAYS, ge=1, le=365),
):
    org_id = _org(ctx)
    rows = await svc.gather_product_metrics(
        db,
        org_id=org_id,
        lookback_days=lookback_days,
        at_risk_days=at_risk_days,
    )
    at_risk_count = sum(1 for r in rows if r.at_risk)
    return ForecastReport(
        generated_at=svc.now_utc(),
        horizon_days=list(svc.DEFAULT_HORIZONS),
        at_risk_days=at_risk_days,
        lookback_days=lookback_days,
        rows=[ForecastOut(**r.to_dict()) for r in rows],
        at_risk_count=at_risk_count,
    )


@router.get("/at-risk", response_model=list[ForecastOut])
async def at_risk_list(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan: None = Depends(require_plan(OrgPlan.PRO)),
    at_risk_days: int = Query(default=svc.DEFAULT_AT_RISK_DAYS, ge=1, le=365),
    lookback_days: int = Query(default=svc.DEFAULT_LOOKBACK_DAYS, ge=1, le=365),
):
    org_id = _org(ctx)
    rows = await svc.gather_product_metrics(
        db,
        org_id=org_id,
        lookback_days=lookback_days,
        at_risk_days=at_risk_days,
    )
    at_risk = svc.at_risk_products(rows, horizon_days=at_risk_days)
    return [ForecastOut(**r.to_dict()) for r in at_risk]


@router.get("/export.csv")
async def forecast_export_csv(
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan: None = Depends(require_plan(OrgPlan.PRO)),
    at_risk_days: int = Query(default=svc.DEFAULT_AT_RISK_DAYS, ge=1, le=365),
    lookback_days: int = Query(default=svc.DEFAULT_LOOKBACK_DAYS, ge=1, le=365),
):
    org_id = _org(ctx)
    rows = await svc.gather_product_metrics(
        db,
        org_id=org_id,
        lookback_days=lookback_days,
        at_risk_days=at_risk_days,
    )
    body = svc.build_forecast_csv(rows)

    await log_action(
        db,
        action="forecast.exported",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="forecast",
        target_id=None,
        request=request,
        extra={"rows": len(rows), "at_risk": sum(1 for r in rows if r.at_risk)},
    )
    await db.commit()

    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="forecast.csv"',
        },
    )


@router.get("/{product_id}", response_model=ForecastOut)
async def forecast_product(
    product_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan: None = Depends(require_plan(OrgPlan.PRO)),
    lookback_days: int = Query(default=svc.DEFAULT_LOOKBACK_DAYS, ge=1, le=365),
):
    org_id = _org(ctx)
    rows = await svc.gather_product_metrics(
        db, org_id=org_id, lookback_days=lookback_days,
    )
    for r in rows:
        if r.product_id == product_id:
            return ForecastOut(**r.to_dict())
    raise HTTPException(status_code=404, detail="product_not_found")


@router.post("/{product_id}/compare", response_model=CompareRow)
async def compare_product(
    product_id: uuid.UUID,
    body: CompareIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan: None = Depends(require_plan(OrgPlan.PRO)),
):
    """Compare the forecast made ``lookback_days`` ago against the
    consumption actually observed in the window.

    Re-computes the forecast as-of the start of the window using only
    data older than the window, then tallies real OUT movements
    inside the window. The variance / variance_pct signal helps the
    operator judge whether the forecaster is biased high or low and
    tighten the ``at_risk_days`` threshold accordingly.
    """
    org_id = _org(ctx)
    to_ts = svc.now_utc()
    from_ts = to_ts - timedelta(days=body.lookback_days)

    # Forecast-as-of-the-start-of-the-window. Re-using the same
    # gather helper but with ``now=from_ts`` gives a proper hindcast.
    as_of = await svc.gather_product_metrics(
        db, org_id=org_id, now=from_ts, lookback_days=body.lookback_days,
    )
    forecast_qty = 0
    for r in as_of:
        if r.product_id == product_id:
            # Forecast consumption = avg_daily * lookback_days, rounded
            # to the nearest integer so the comparison has the same
            # unit as the actual integer movement tally.
            forecast_qty = int(round(r.avg_daily_demand * body.lookback_days))
            break
    else:
        raise HTTPException(status_code=404, detail="product_not_found")

    actuals = await svc.compute_post_period_actuals(
        db,
        org_id=org_id,
        product_ids=[product_id],
        from_ts=from_ts,
        to_ts=to_ts,
    )
    actual_qty = int(actuals.get(product_id, 0))
    cmp_rows = svc.compare_forecast_vs_actual([(product_id, forecast_qty, actual_qty)])
    return CompareRow(**cmp_rows[0].to_dict())
