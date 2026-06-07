"""Dashboard Builder router.

Manages per-user widget layouts and supplies live widget data.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.dashboard_builder import DashboardLayout, ScheduledDashboard
from app.models.inventory import Product, StockLevel
from app.models.invoicing import Customer, Invoice

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard-builder", tags=["dashboard-builder"], dependencies=[Depends(require_module("analytics"))])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _period_bounds(date_range: str) -> tuple[datetime, datetime]:
    now = datetime.now(tz=timezone.utc)
    if date_range == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif date_range == "this_week":
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    elif date_range == "this_month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif date_range == "this_quarter":
        month = ((now.month - 1) // 3) * 3 + 1
        start = now.replace(month=month, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:  # this_year
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, now


async def _widget_data(widget_type: str, org_id: uuid.UUID, date_range: str, db: AsyncSession) -> dict:
    start, end = _period_bounds(date_range)

    if widget_type == "revenue":
        result = await db.execute(
            select(func.coalesce(func.sum(Invoice.total_amount), 0))
            .where(Invoice.org_id == org_id, Invoice.status == "paid",
                   Invoice.created_at >= start, Invoice.created_at <= end)
        )
        return {"value": float(result.scalar() or 0), "label": "Revenue"}

    if widget_type == "invoice_summary":
        result = await db.execute(
            select(Invoice.status, func.count(Invoice.id), func.sum(Invoice.total_amount))
            .where(Invoice.org_id == org_id, Invoice.created_at >= start, Invoice.created_at <= end)
            .group_by(Invoice.status)
        )
        rows = result.all()
        return {"items": [{"status": r[0], "count": r[1], "total": float(r[2] or 0)} for r in rows]}

    if widget_type == "stock_level":
        low_stock_result = await db.execute(
            select(func.count(StockLevel.id))
            .join(Product, Product.id == StockLevel.product_id)
            .where(StockLevel.org_id == org_id,
                   StockLevel.quantity <= Product.reorder_level,
                   StockLevel.quantity > 0)
        )
        out_result = await db.execute(
            select(func.count(StockLevel.id))
            .where(StockLevel.org_id == org_id, StockLevel.quantity == 0)
        )
        return {"low_stock": int(low_stock_result.scalar() or 0), "out_of_stock": int(out_result.scalar() or 0)}

    if widget_type == "customer_count":
        result = await db.execute(
            select(func.count(Customer.id)).where(Customer.org_id == org_id)
        )
        return {"value": int(result.scalar() or 0), "label": "Customers"}

    if widget_type == "pipeline_value":
        # Open invoices (sent/overdue) = pipeline
        result = await db.execute(
            select(func.coalesce(func.sum(Invoice.total_amount), 0))
            .where(Invoice.org_id == org_id, Invoice.status.in_(["sent", "overdue"]))
        )
        return {"value": float(result.scalar() or 0), "label": "Open Receivables"}

    return {"error": f"Unknown widget type: {widget_type}"}


# ── Schemas ───────────────────────────────────────────────────────────────────

class LayoutCreateIn(BaseModel):
    name: str
    widgets: list = []
    date_range: str = "this_month"
    shared_role: Optional[str] = None


class LayoutUpdateIn(BaseModel):
    name: Optional[str] = None
    widgets: Optional[list] = None
    date_range: Optional[str] = None
    shared_role: Optional[str] = None
    is_default: Optional[bool] = None


class ScheduleIn(BaseModel):
    recipient_emails: list[str]
    cron_expression: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/layouts")
async def list_layouts(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        user_id = uuid.UUID(str(member["user_id"]))
        result = await db.execute(
            select(DashboardLayout)
            .where(DashboardLayout.org_id == org_id)
            .where(
                (DashboardLayout.user_id == user_id) |
                (DashboardLayout.shared_role.isnot(None))
            )
            .order_by(DashboardLayout.is_default.desc(), DashboardLayout.name)
        )
        layouts = result.scalars().all()
        return {
            "items": [
                {"id": str(l.id), "name": l.name, "widgets": l.widgets,
                 "date_range": l.date_range, "is_default": l.is_default,
                 "shared_role": l.shared_role, "user_id": str(l.user_id)}
                for l in layouts
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_layouts failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/layouts", status_code=201)
async def create_layout(
    body: LayoutCreateIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        user_id = uuid.UUID(str(member["user_id"]))
        layout = DashboardLayout(
            id=uuid.uuid4(), org_id=org_id, user_id=user_id,
            name=body.name, widgets=body.widgets,
            date_range=body.date_range, shared_role=body.shared_role,
        )
        db.add(layout)
        await db.commit()
        await db.refresh(layout)
        return {"id": str(layout.id), "name": layout.name}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"create_layout failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/layouts/{layout_id}")
async def get_layout(
    layout_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        layout = await db.get(DashboardLayout, layout_id)
        if not layout or layout.org_id != org_id:
            raise HTTPException(status_code=404, detail="Layout not found")
        return {"id": str(layout.id), "name": layout.name, "widgets": layout.widgets,
                "date_range": layout.date_range, "is_default": layout.is_default, "shared_role": layout.shared_role}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_layout failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/layouts/{layout_id}")
async def update_layout(
    layout_id: uuid.UUID,
    body: LayoutUpdateIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        layout = await db.get(DashboardLayout, layout_id)
        if not layout or layout.org_id != org_id:
            raise HTTPException(status_code=404, detail="Layout not found")
        if body.name is not None:
            layout.name = body.name
        if body.widgets is not None:
            layout.widgets = body.widgets
        if body.date_range is not None:
            layout.date_range = body.date_range
        if body.shared_role is not None:
            layout.shared_role = body.shared_role
        if body.is_default is not None:
            # Clear other defaults for this user first
            if body.is_default:
                other = await db.execute(
                    select(DashboardLayout)
                    .where(DashboardLayout.org_id == org_id,
                           DashboardLayout.user_id == layout.user_id,
                           DashboardLayout.is_default.is_(True),
                           DashboardLayout.id != layout_id)
                )
                for ol in other.scalars().all():
                    ol.is_default = False
            layout.is_default = body.is_default
        await db.commit()
        return {"id": str(layout.id), "name": layout.name}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"update_layout failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/layouts/{layout_id}", status_code=204)
async def delete_layout(
    layout_id: uuid.UUID,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        layout = await db.get(DashboardLayout, layout_id)
        if not layout or layout.org_id != org_id:
            raise HTTPException(status_code=404, detail="Layout not found")
        await db.delete(layout)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"delete_layout failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/widgets/{widget_type}")
async def get_widget_data(
    widget_type: str,
    date_range: str = "this_month",
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        data = await _widget_data(widget_type, org_id, date_range, db)
        return {"widget_type": widget_type, "date_range": date_range, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_widget_data failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/layouts/{layout_id}/schedule", status_code=201)
async def schedule_dashboard(
    layout_id: uuid.UUID,
    body: ScheduleIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = uuid.UUID(str(member["org_id"]))
        layout = await db.get(DashboardLayout, layout_id)
        if not layout or layout.org_id != org_id:
            raise HTTPException(status_code=404, detail="Layout not found")
        sched = ScheduledDashboard(
            id=uuid.uuid4(), org_id=org_id, layout_id=layout_id,
            recipient_emails=body.recipient_emails, cron_expression=body.cron_expression,
        )
        db.add(sched)
        await db.commit()
        return {"id": str(sched.id), "cron_expression": sched.cron_expression}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"schedule_dashboard failed: {e}", extra={"org_id": str(member.get("org_id"))})
        raise HTTPException(status_code=500, detail="Internal server error")
