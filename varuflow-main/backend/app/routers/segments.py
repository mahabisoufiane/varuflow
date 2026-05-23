"""Customer-segmentation router (Item 39, v54).

Endpoints under ``/api/segments``:

CRUD:

* ``GET    /``                         — list segments for the org.
* ``POST   /``                         — create AUTO or MANUAL segment.
* ``GET    /{id}``                     — detail.
* ``PATCH  /{id}``                     — rename / edit rules.
* ``DELETE /{id}``                     — remove.

Membership:

* ``GET    /{id}/members``             — customer list.
* ``POST   /{id}/members``             — add customer to MANUAL.
* ``DELETE /{id}/members/{customer_id}`` — remove from MANUAL.

Operational:

* ``POST   /{id}/refresh``             — recompute AUTO membership.
* ``GET    /{id}/export.csv``          — stream membership as CSV.

All mutations call :func:`log_action`. AUTO segments' membership is
normally refreshed nightly by the scheduler; the ``refresh`` endpoint
exposes a manual trigger for owners tweaking rules in the UI.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.invoicing import Customer
from app.models.segments import Segment, SegmentMember, SegmentType
from app.services import segmentation_engine as svc
from app.services.audit import log_action

router = APIRouter(prefix="/api/segments", tags=["segments"])


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


async def _load_segment(
    db: AsyncSession, *, segment_id: uuid.UUID, org_id: uuid.UUID,
) -> Segment:
    seg = await db.scalar(
        select(Segment).where(
            Segment.id == segment_id, Segment.org_id == org_id,
        )
    )
    if seg is None:
        raise HTTPException(status_code=404, detail="segment_not_found")
    return seg


# ═══════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════


class SegmentCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    type: SegmentType
    rules: dict[str, Any] = Field(default_factory=dict)


class SegmentUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    rules: dict[str, Any] | None = None


class SegmentOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: str | None
    type: SegmentType
    rules: dict[str, Any]
    customer_count: int
    last_computed_at: datetime | None
    created_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberIn(BaseModel):
    customer_id: uuid.UUID


class MemberOut(BaseModel):
    customer_id: uuid.UUID
    company_name: str
    email: str | None
    added_at: datetime


# ═══════════════════════════════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════════════════════════════


@router.get("", response_model=list[SegmentOut])
async def list_segments(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    type_filter: SegmentType | None = Query(None, alias="type"),
):
    org_id = _org(ctx)
    stmt = (
        select(Segment)
        .where(Segment.org_id == org_id)
        .order_by(Segment.created_at.desc())
    )
    if type_filter is not None:
        stmt = stmt.where(Segment.type == type_filter)
    rows = (await db.execute(stmt)).scalars().all()
    return rows


@router.get("/{segment_id}", response_model=SegmentOut)
async def get_segment(
    segment_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    return await _load_segment(db, segment_id=segment_id, org_id=_org(ctx))


@router.post("", response_model=SegmentOut, status_code=201)
async def create_segment(
    body: SegmentCreateIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)

    # Rules must validate up-front — a malformed kind or predicate
    # would silently match nobody otherwise, and the owner would
    # never notice the typo.
    try:
        svc.validate_rules(body.rules or {})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    seg = Segment(
        id=uuid.uuid4(),
        org_id=org_id,
        name=body.name.strip(),
        description=body.description,
        type=body.type,
        rules=body.rules or {},
        customer_count=0,
        created_by=_actor(ctx),
    )
    db.add(seg)
    try:
        await db.flush()
    except Exception as e:  # integrity error on (org_id, name) unique
        raise HTTPException(status_code=409, detail="segment_name_taken") from e

    # Compute initial membership synchronously for AUTO so the UI
    # shows a useful count immediately after create.
    if seg.type == SegmentType.AUTO:
        await svc.refresh_segment(db, seg)

    await log_action(
        db,
        action="segment.created",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="segment",
        target_id=str(seg.id),
        request=request,
        extra={"type": seg.type.value, "name": seg.name},
    )
    await db.commit()
    return await _load_segment(db, segment_id=seg.id, org_id=org_id)


@router.patch("/{segment_id}", response_model=SegmentOut)
async def update_segment(
    segment_id: uuid.UUID,
    body: SegmentUpdateIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    seg = await _load_segment(db, segment_id=segment_id, org_id=org_id)

    changes: dict[str, Any] = {}
    if body.name is not None and body.name.strip() != seg.name:
        seg.name = body.name.strip()
        changes["name"] = seg.name
    if body.description is not None:
        seg.description = body.description
        changes["description"] = True
    if body.rules is not None:
        try:
            svc.validate_rules(body.rules)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        seg.rules = body.rules
        changes["rules"] = True
        # Rules changed → recompute immediately for AUTO segments so
        # the owner's next list call shows the new count without
        # waiting for the nightly sweep.
        if seg.type == SegmentType.AUTO:
            await svc.refresh_segment(db, seg)

    await log_action(
        db,
        action="segment.updated",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="segment",
        target_id=str(seg.id),
        request=request,
        extra=changes,
    )
    await db.commit()
    return await _load_segment(db, segment_id=seg.id, org_id=org_id)


@router.delete("/{segment_id}", status_code=204)
async def delete_segment(
    segment_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    seg = await _load_segment(db, segment_id=segment_id, org_id=org_id)
    await db.delete(seg)
    await log_action(
        db,
        action="segment.deleted",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="segment",
        target_id=str(segment_id),
        request=request,
    )
    await db.commit()
    return Response(status_code=204)


# ═══════════════════════════════════════════════════════════════════
# Membership
# ═══════════════════════════════════════════════════════════════════


@router.get("/{segment_id}/members", response_model=list[MemberOut])
async def list_members(
    segment_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    await _load_segment(db, segment_id=segment_id, org_id=org_id)
    rows = await db.execute(
        select(
            Customer.id, Customer.company_name, Customer.email,
            SegmentMember.added_at,
        )
        .join(SegmentMember, SegmentMember.customer_id == Customer.id)
        .where(SegmentMember.segment_id == segment_id)
        .order_by(Customer.company_name.asc())
    )
    return [
        MemberOut(
            customer_id=r.id,
            company_name=r.company_name,
            email=r.email,
            added_at=r.added_at,
        )
        for r in rows.all()
    ]


@router.post("/{segment_id}/members", response_model=MemberOut, status_code=201)
async def add_member(
    segment_id: uuid.UUID,
    body: MemberIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    seg = await _load_segment(db, segment_id=segment_id, org_id=org_id)
    if seg.type != SegmentType.MANUAL:
        raise HTTPException(
            status_code=409, detail="cannot_manually_edit_auto_segment",
        )
    customer = await db.scalar(
        select(Customer).where(
            Customer.id == body.customer_id, Customer.org_id == org_id,
        )
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="customer_not_found")

    # Idempotent: already-a-member returns 200-equivalent via upsert.
    existing = await db.scalar(
        select(SegmentMember).where(
            SegmentMember.segment_id == segment_id,
            SegmentMember.customer_id == body.customer_id,
        )
    )
    if existing is None:
        member = SegmentMember(
            segment_id=segment_id, customer_id=body.customer_id,
        )
        db.add(member)
        seg.customer_count = (seg.customer_count or 0) + 1
        await db.flush()
        added_at = member.added_at
    else:
        added_at = existing.added_at

    await log_action(
        db,
        action="segment.member_added",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="segment",
        target_id=str(segment_id),
        request=request,
        extra={"customer_id": str(body.customer_id)},
    )
    await db.commit()
    return MemberOut(
        customer_id=customer.id,
        company_name=customer.company_name,
        email=customer.email,
        added_at=added_at,
    )


@router.delete("/{segment_id}/members/{customer_id}", status_code=204)
async def remove_member(
    segment_id: uuid.UUID,
    customer_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    seg = await _load_segment(db, segment_id=segment_id, org_id=org_id)
    if seg.type != SegmentType.MANUAL:
        raise HTTPException(
            status_code=409, detail="cannot_manually_edit_auto_segment",
        )
    existing = await db.scalar(
        select(SegmentMember).where(
            SegmentMember.segment_id == segment_id,
            SegmentMember.customer_id == customer_id,
        )
    )
    if existing is None:
        raise HTTPException(status_code=404, detail="member_not_found")
    await db.delete(existing)
    seg.customer_count = max(0, (seg.customer_count or 0) - 1)
    await log_action(
        db,
        action="segment.member_removed",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="segment",
        target_id=str(segment_id),
        request=request,
        extra={"customer_id": str(customer_id)},
    )
    await db.commit()
    return Response(status_code=204)


# ═══════════════════════════════════════════════════════════════════
# Operational
# ═══════════════════════════════════════════════════════════════════


@router.post("/{segment_id}/refresh", response_model=SegmentOut)
async def refresh_segment(
    segment_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    seg = await _load_segment(db, segment_id=segment_id, org_id=org_id)
    count = await svc.refresh_segment(db, seg)
    await log_action(
        db,
        action="segment.refreshed",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="segment",
        target_id=str(segment_id),
        request=request,
        extra={"customer_count": count},
    )
    await db.commit()
    return await _load_segment(db, segment_id=segment_id, org_id=org_id)


@router.get("/{segment_id}/export.csv")
async def export_segment_csv(
    segment_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Stream segment membership as CSV."""
    org_id = _org(ctx)
    seg = await _load_segment(db, segment_id=segment_id, org_id=org_id)
    rows = await db.execute(
        select(
            Customer.id, Customer.company_name, Customer.email,
        )
        .join(SegmentMember, SegmentMember.customer_id == Customer.id)
        .where(SegmentMember.segment_id == segment_id)
        .order_by(Customer.company_name.asc())
    )
    csv_rows = [
        (str(r.id), r.company_name or "", r.email or "")
        for r in rows.all()
    ]
    body = svc.build_segment_csv(csv_rows)

    await log_action(
        db,
        action="segment.exported",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="segment",
        target_id=str(segment_id),
        request=request,
        extra={"rows": len(csv_rows)},
    )
    await db.commit()

    safe_name = "".join(c if c.isalnum() else "_" for c in (seg.name or "segment"))[:60]
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}.csv"',
        },
    )
