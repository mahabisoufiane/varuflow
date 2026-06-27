"""Auto-reorder router (v38 — Item 16).

Three endpoints:

* ``POST /api/auto-reorder/run`` — OWNER-only manual trigger.
* ``GET  /api/auto-reorder/runs`` — last 30 run-history rows.
* ``GET  /api/auto-reorder/preview`` — dry-run: what *would* be ordered.

The preview endpoint is deliberately permissive (any member) so
inventory managers can sanity-check the formula before asking an owner
to flip the org-level switch. Actual run creation is OWNER-only because
draft POs surface to the supplier-facing approval queue.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .auto_reorder_models import AutoReorderRun
from app.features.auth.organization import OrgRole
from app.services.audit import log_action
from app.services.auto_reorder import (
    AutoReorderResult,
    preview_auto_reorder,
    run_auto_reorder,
)
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/auto-reorder", tags=["auto-reorder"], dependencies=[Depends(require_module("inventory"))])


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Schemas ────────────────────────────────────────────────────────────────

class PurchaseOrderSummaryOut(BaseModel):
    po_id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    items_count: int
    total_sek: Decimal


class AutoReorderResultOut(BaseModel):
    products_checked: int
    purchase_orders_created: int
    products_skipped: int
    pos_created: list[PurchaseOrderSummaryOut]
    errors: list[str]


class AutoReorderRunOut(BaseModel):
    id: uuid.UUID
    run_at: datetime
    triggered_by: str
    products_checked: int
    purchase_orders_created: int
    products_skipped: int
    status: str
    error_message: str | None

    model_config = {"from_attributes": True}


class PreviewLineOut(BaseModel):
    product_id: uuid.UUID
    product_name: str
    sku: str
    current_stock: int
    reorder_level: int
    suggested_qty: int
    preferred_supplier_id: uuid.UUID | None
    preferred_supplier_name: str | None
    estimated_cost_sek: Decimal


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/run", response_model=AutoReorderResultOut)
async def trigger_auto_reorder(
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Manual trigger — OWNER only."""
    _, member = ctx
    if member.role != OrgRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only org owners can trigger auto-reorder.",
        )

    org_id = member.org_id
    result: AutoReorderResult = await run_auto_reorder(
        org_id, db, triggered_by="manual"
    )

    await log_action(
        db,
        action="auto_reorder.manually_triggered",
        org_id=org_id,
        actor_user_id=member.user_id,
        target_type="organization",
        target_id=str(org_id),
        request=request,
        extra={
            "purchase_orders_created": result.purchase_orders_created,
            "products_checked": result.products_checked,
            "products_skipped": result.products_skipped,
        },
    )
    await db.commit()

    return AutoReorderResultOut(
        products_checked=result.products_checked,
        purchase_orders_created=result.purchase_orders_created,
        products_skipped=result.products_skipped,
        pos_created=[
            PurchaseOrderSummaryOut(
                po_id=s.po_id,
                supplier_id=s.supplier_id,
                supplier_name=s.supplier_name,
                items_count=s.items_count,
                total_sek=s.total_sek,
            )
            for s in result.pos_created
        ],
        errors=list(result.errors),
    )


@router.get("/runs", response_model=list[AutoReorderRunOut])
async def list_runs(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Last 30 runs for the caller's org, newest first."""
    org_id = _org(ctx)
    rows = await db.execute(
        select(AutoReorderRun)
        .where(AutoReorderRun.org_id == org_id)
        .order_by(AutoReorderRun.run_at.desc())
        .limit(30)
    )
    return rows.scalars().all()


@router.get("/preview", response_model=list[PreviewLineOut])
async def preview(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Dry-run — never creates anything. Any member can call."""
    org_id = _org(ctx)
    lines = await preview_auto_reorder(db, org_id)
    return [
        PreviewLineOut(
            product_id=l.product_id,
            product_name=l.product_name,
            sku=l.sku,
            current_stock=l.current_stock,
            reorder_level=l.reorder_level,
            suggested_qty=l.suggested_qty,
            preferred_supplier_id=l.preferred_supplier_id,
            preferred_supplier_name=l.preferred_supplier_name,
            estimated_cost_sek=l.estimated_cost_sek,
        )
        for l in lines
    ]


# ── Org settings ──────────────────────────────────────────────────────────

class AutoReorderSettingsIn(BaseModel):
    auto_reorder_enabled: bool | None = None
    auto_reorder_time: str | None = None  # "HH:MM"
    auto_reorder_days: str | None = None
    auto_reorder_notify_email: str | None = None


class AutoReorderSettingsOut(BaseModel):
    auto_reorder_enabled: bool
    auto_reorder_time: str
    auto_reorder_days: str
    auto_reorder_notify_email: str | None


@router.get("/settings", response_model=AutoReorderSettingsOut)
async def get_settings(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    from app.features.auth.organization import Organization

    org = await db.get(Organization, _org(ctx))
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return AutoReorderSettingsOut(
        auto_reorder_enabled=bool(org.auto_reorder_enabled),
        auto_reorder_time=org.auto_reorder_time.strftime("%H:%M"),
        auto_reorder_days=org.auto_reorder_days,
        auto_reorder_notify_email=org.auto_reorder_notify_email,
    )


@router.put("/settings", response_model=AutoReorderSettingsOut)
async def update_settings(
    body: AutoReorderSettingsIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    from datetime import time

    from app.features.auth.organization import Organization

    _, member = ctx
    if member.role != OrgRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only org owners can change auto-reorder settings.",
        )
    org = await db.get(Organization, member.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    if body.auto_reorder_enabled is not None:
        org.auto_reorder_enabled = bool(body.auto_reorder_enabled)
    if body.auto_reorder_time is not None:
        try:
            hh, mm = body.auto_reorder_time.split(":", 1)
            org.auto_reorder_time = time(int(hh), int(mm))
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400, detail="auto_reorder_time must be HH:MM"
            )
    if body.auto_reorder_days is not None:
        # Accept any comma-separated subset of MON..SUN (case-insensitive).
        allowed = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}
        parts = [
            p.strip().upper()
            for p in body.auto_reorder_days.split(",")
            if p.strip()
        ]
        if not parts or any(p not in allowed for p in parts):
            raise HTTPException(
                status_code=400,
                detail="auto_reorder_days must be comma-separated MON..SUN",
            )
        org.auto_reorder_days = ",".join(parts)
    if body.auto_reorder_notify_email is not None:
        org.auto_reorder_notify_email = (
            body.auto_reorder_notify_email.strip() or None
        )

    await log_action(
        db,
        action="auto_reorder.settings_updated",
        org_id=member.org_id,
        actor_user_id=member.user_id,
        target_type="organization",
        target_id=str(member.org_id),
        request=request,
        extra={
            "enabled": org.auto_reorder_enabled,
            "time": org.auto_reorder_time.strftime("%H:%M"),
            "days": org.auto_reorder_days,
        },
    )
    await db.commit()
    await db.refresh(org)

    return AutoReorderSettingsOut(
        auto_reorder_enabled=bool(org.auto_reorder_enabled),
        auto_reorder_time=org.auto_reorder_time.strftime("%H:%M"),
        auto_reorder_days=org.auto_reorder_days,
        auto_reorder_notify_email=org.auto_reorder_notify_email,
    )
