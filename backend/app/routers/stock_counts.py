"""Item 14 — Stock count router (``/api/stock-counts``).

Offline-first cycle counts. The mobile client stores drafts in
AsyncStorage and submits them over this API. Clients provide UUIDs for
both the count and its items so retried submissions after a flaky
connection stay idempotent: POSTing the same ``id`` twice upserts the
row rather than creating a duplicate, and submit/sync transitions guard
against re-running adjustment logic.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.inventory import Product, StockLevel, Warehouse
from app.models.stock_count import StockCount, StockCountItem, StockCountStatus
from app.services.audit import log_action
from app.services.stock_count import apply_stock_count

router = APIRouter(prefix="/api/stock-counts", tags=["stock-counts"])


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


# ── Schemas ─────────────────────────────────────────────────────────────────

class StockCountItemIn(BaseModel):
    # Optional — server generates a UUID when the client omits it.
    id: uuid.UUID | None = None
    product_id: uuid.UUID
    batch_id: uuid.UUID | None = None
    expected_qty: int = Field(0, ge=0, le=10_000_000)
    counted_qty: int = Field(0, ge=0, le=10_000_000)
    note: str | None = Field(None, max_length=2000)


class StockCountCreate(BaseModel):
    # Client-assigned to make retries idempotent on flaky mobile networks.
    id: uuid.UUID | None = None
    warehouse_id: uuid.UUID
    note: str | None = Field(None, max_length=2000)
    items: list[StockCountItemIn] = Field(default_factory=list)


class StockCountUpdate(BaseModel):
    note: str | None = Field(None, max_length=2000)
    items: list[StockCountItemIn] | None = None


class StockCountItemOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    batch_id: uuid.UUID | None
    expected_qty: int
    counted_qty: int
    variance_qty: int
    note: str | None

    model_config = {"from_attributes": True}


class StockCountOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    warehouse_id: uuid.UUID
    status: StockCountStatus
    note: str | None
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
    synced_at: datetime | None
    items: list[StockCountItemOut]

    model_config = {"from_attributes": True}


class StockCountListOut(BaseModel):
    id: uuid.UUID
    warehouse_id: uuid.UUID
    status: StockCountStatus
    created_at: datetime
    submitted_at: datetime | None
    synced_at: datetime | None
    item_count: int
    variance_total: int

    model_config = {"from_attributes": True}


class SyncSummary(BaseModel):
    adjustments: int
    matches: int
    positive: int
    negative: int


# ── Helpers ─────────────────────────────────────────────────────────────────

async def _load_count(
    db: AsyncSession, count_id: uuid.UUID, org_id: uuid.UUID
) -> StockCount:
    sc = await db.scalar(
        select(StockCount)
        .options(selectinload(StockCount.items))
        .where(StockCount.id == count_id, StockCount.org_id == org_id)
    )
    if not sc:
        raise HTTPException(status_code=404, detail="Stock count not found")
    return sc


async def _validate_warehouse(
    db: AsyncSession, warehouse_id: uuid.UUID, org_id: uuid.UUID
) -> None:
    wh = await db.scalar(
        select(Warehouse.id).where(
            Warehouse.id == warehouse_id, Warehouse.org_id == org_id
        )
    )
    if not wh:
        raise HTTPException(status_code=404, detail="Warehouse not found")


async def _validate_products(
    db: AsyncSession, product_ids: set[uuid.UUID], org_id: uuid.UUID
) -> None:
    if not product_ids:
        return
    rows = await db.execute(
        select(Product.id).where(
            Product.id.in_(product_ids), Product.org_id == org_id
        )
    )
    found = {r[0] for r in rows.all()}
    missing = product_ids - found
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Product(s) not in org: {', '.join(str(m) for m in missing)}",
        )


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=StockCountOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_stock_count(
    body: StockCountCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> StockCount:
    """Create (or upsert) a draft stock count.

    If the client supplies an id that already exists in this org we
    treat it as a resume/rehydrate: the note and items are replaced in
    place. This keeps the offline queue idempotent across retries.
    """
    org_id = _org(ctx)
    await _validate_warehouse(db, body.warehouse_id, org_id)
    await _validate_products(db, {i.product_id for i in body.items}, org_id)

    existing: StockCount | None = None
    if body.id is not None:
        existing = await db.scalar(
            select(StockCount).where(
                StockCount.id == body.id, StockCount.org_id == org_id
            )
        )
        if existing and existing.status not in (
            StockCountStatus.DRAFT,
            StockCountStatus.SUBMITTED,
        ):
            # Already reconciled — silently re-return the row rather
            # than creating a new one. Offline retries must be safe.
            return await _load_count(db, existing.id, org_id)

    if existing is None:
        sc = StockCount(
            id=body.id or uuid.uuid4(),
            org_id=org_id,
            warehouse_id=body.warehouse_id,
            created_by=_actor(ctx),
            status=StockCountStatus.DRAFT,
            note=body.note,
        )
        db.add(sc)
        await db.flush()
    else:
        sc = existing
        sc.warehouse_id = body.warehouse_id
        sc.note = body.note
        # Drop prior items so the client's local state is authoritative
        # while the count is still DRAFT/SUBMITTED.
        await db.execute(
            StockCountItem.__table__.delete().where(
                StockCountItem.stock_count_id == sc.id
            )
        )

    for item in body.items:
        db.add(
            StockCountItem(
                id=item.id or uuid.uuid4(),
                stock_count_id=sc.id,
                org_id=org_id,
                product_id=item.product_id,
                batch_id=item.batch_id,
                expected_qty=item.expected_qty,
                counted_qty=item.counted_qty,
                variance_qty=item.counted_qty - item.expected_qty,
                note=item.note,
            )
        )

    await log_action(
        db,
        action="STOCK_COUNT_CREATED",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="stock_count",
        target_id=str(sc.id),
        request=request,
        extra={"items": len(body.items), "warehouse_id": str(body.warehouse_id)},
    )
    await db.commit()
    return await _load_count(db, sc.id, org_id)


@router.get("", response_model=list[StockCountListOut])
async def list_stock_counts(
    status_filter: Optional[StockCountStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[StockCountListOut]:
    org_id = _org(ctx)
    q = (
        select(
            StockCount.id,
            StockCount.warehouse_id,
            StockCount.status,
            StockCount.created_at,
            StockCount.submitted_at,
            StockCount.synced_at,
            func.count(StockCountItem.id).label("item_count"),
            func.coalesce(func.sum(StockCountItem.variance_qty), 0).label(
                "variance_total"
            ),
        )
        .outerjoin(
            StockCountItem,
            StockCountItem.stock_count_id == StockCount.id,
        )
        .where(StockCount.org_id == org_id)
        .group_by(StockCount.id)
        .order_by(StockCount.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if status_filter is not None:
        q = q.where(StockCount.status == status_filter)
    rows = (await db.execute(q)).all()
    return [
        StockCountListOut(
            id=r.id,
            warehouse_id=r.warehouse_id,
            status=r.status,
            created_at=r.created_at,
            submitted_at=r.submitted_at,
            synced_at=r.synced_at,
            item_count=r.item_count,
            variance_total=r.variance_total,
        )
        for r in rows
    ]


@router.get("/{count_id}", response_model=StockCountOut)
async def get_stock_count(
    count_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> StockCount:
    return await _load_count(db, count_id, _org(ctx))


@router.post("/{count_id}/submit", response_model=StockCountOut)
async def submit_stock_count(
    count_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> StockCount:
    """Mark a draft count as SUBMITTED (ready for server reconciliation).

    Does NOT yet apply adjustment movements — those run in ``/sync`` so
    the offline client can submit first (the body is already on the
    server) and then kick off reconciliation in a second step that can
    safely retry without duplicating adjustments.
    """
    org_id = _org(ctx)
    sc = await _load_count(db, count_id, org_id)
    if sc.status == StockCountStatus.SYNCED:
        return sc  # idempotent no-op
    if sc.status == StockCountStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Count was cancelled")

    sc.status = StockCountStatus.SUBMITTED
    sc.submitted_at = datetime.now(timezone.utc)

    # Freshen expected_qty from current stock levels so the variance
    # is computed against the latest server-side truth, not what the
    # device cached at start-of-count.
    for item in sc.items:
        sl = await db.scalar(
            select(StockLevel.quantity).where(
                StockLevel.product_id == item.product_id,
                StockLevel.warehouse_id == sc.warehouse_id,
            )
        )
        fresh = int(sl or 0)
        item.expected_qty = fresh
        item.variance_qty = item.counted_qty - fresh

    await log_action(
        db,
        action="STOCK_COUNT_SUBMITTED",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="stock_count",
        target_id=str(sc.id),
        request=request,
        extra={"items": len(sc.items)},
    )
    await db.commit()
    return await _load_count(db, sc.id, org_id)


@router.post("/{count_id}/sync", response_model=SyncSummary)
async def sync_stock_count(
    count_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> SyncSummary:
    """Apply adjustments for a submitted count. Idempotent."""
    org_id = _org(ctx)
    sc = await _load_count(db, count_id, org_id)

    if sc.status == StockCountStatus.SYNCED:
        # Recompute a summary from stored variances so the client still
        # gets the same payload shape on a retry.
        adj = sum(1 for i in sc.items if i.variance_qty != 0)
        return SyncSummary(
            adjustments=adj,
            matches=len(sc.items) - adj,
            positive=sum(1 for i in sc.items if i.variance_qty > 0),
            negative=sum(1 for i in sc.items if i.variance_qty < 0),
        )
    if sc.status == StockCountStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Count was cancelled")
    if sc.status == StockCountStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Submit the count first")

    summary = await apply_stock_count(db, sc)
    sc.status = StockCountStatus.SYNCED
    sc.synced_at = datetime.now(timezone.utc)

    await log_action(
        db,
        action="STOCK_COUNT_SYNCED",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="stock_count",
        target_id=str(sc.id),
        request=request,
        extra=summary,
    )
    await db.commit()
    return SyncSummary(**summary)


@router.post("/{count_id}/cancel", response_model=StockCountOut)
async def cancel_stock_count(
    count_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> StockCount:
    org_id = _org(ctx)
    sc = await _load_count(db, count_id, org_id)
    if sc.status == StockCountStatus.SYNCED:
        raise HTTPException(status_code=400, detail="Already synced")
    sc.status = StockCountStatus.CANCELLED
    await log_action(
        db,
        action="STOCK_COUNT_CANCELLED",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="stock_count",
        target_id=str(sc.id),
        request=request,
    )
    await db.commit()
    return await _load_count(db, sc.id, org_id)


# ── Scheduler hook (Item 14 §10) ────────────────────────────────────────────

async def mark_stuck_counts(db: AsyncSession, *, older_than_hours: int = 24) -> int:
    """Reset counts stuck in SUBMITTED for >N hours back to DRAFT.

    Called by the APScheduler job. Returns the number of rows reset so
    the caller can log it.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
    rows = await db.execute(
        select(StockCount).where(
            StockCount.status == StockCountStatus.SUBMITTED,
            StockCount.submitted_at.is_not(None),
            StockCount.submitted_at < cutoff,
        )
    )
    stuck = rows.scalars().all()
    for sc in stuck:
        sc.status = StockCountStatus.DRAFT
    if stuck:
        await db.commit()
    return len(stuck)
