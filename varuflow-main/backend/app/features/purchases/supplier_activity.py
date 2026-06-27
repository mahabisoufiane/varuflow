"""Supplier activity timeline router (Item 79).

Endpoint under ``/api/supplier-activity``:

    GET /{supplier_id}?limit=&offset=&category=

Pure read over the ``audit_log`` — surfaces every event touching a
supplier (notes, tags, contacts, purchase orders, lead-time updates)
as a unified chronological feed. Reads are themselves **not**
audited — the audit log must not tail itself.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.features.compliance.audit_models import AuditLogEntry
from app.features.inventory.models import Supplier
from app.services import supplier_activity as svc_79
from app.middleware.plan_check import require_module

router = APIRouter(
    prefix="/api/supplier-activity", tags=["supplier-activity"],
    dependencies=[Depends(require_module("inventory"))],
)

log = logging.getLogger(__name__)


class TimelineEntryOut(BaseModel):
    id:            uuid.UUID
    action:        str
    category:      str
    actor_user_id: uuid.UUID | None
    target_type:   str | None
    target_id:     str | None
    extra:         dict
    created_at:    datetime


class TimelineOut(BaseModel):
    supplier_id: uuid.UUID
    total:       int
    limit:       int
    offset:      int
    entries:     list[TimelineEntryOut]


async def _load_supplier(
    db: AsyncSession, *, supplier_id: uuid.UUID, org_id: uuid.UUID,
) -> Supplier:
    row = await db.scalar(
        select(Supplier).where(Supplier.id == supplier_id)
    )
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return row


@router.get("/{supplier_id}", response_model=TimelineOut)
async def get_supplier_timeline(
    supplier_id: uuid.UUID,
    limit:    int | None = Query(default=None, ge=1, le=svc_79.MAX_PAGE_LIMIT),
    offset:   int | None = Query(default=None, ge=0),
    category: str | None = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    await _load_supplier(
        db, supplier_id=supplier_id, org_id=member.org_id,
    )

    try:
        limit_v, offset_v = svc_79.normalize_page(
            limit=limit, offset=offset,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Pull a bounded superset — every row under this org with one of
    # the known action names, in reverse chronological order. Filter
    # to the one supplier in Python so the same SQL works whether the
    # supplier id lives in ``target_id`` or in ``extra->>supplier_id``.
    actions = list(svc_79.known_actions())
    sid_str = str(supplier_id)
    stmt = (
        select(AuditLogEntry)
        .where(
            AuditLogEntry.org_id == member.org_id,
            AuditLogEntry.action.in_(actions),
            or_(
                AuditLogEntry.target_id == sid_str,
                AuditLogEntry.extra["supplier_id"].astext == sid_str,
            ),
        )
        .order_by(AuditLogEntry.created_at.desc(), AuditLogEntry.id.desc())
        # Hard upper bound — even if someone stuffs a million writes
        # on one supplier we only ever pull ``MAX_PAGE_LIMIT * 20``
        # rows into Python. That's plenty for sane UIs and caps
        # memory / query cost.
        .limit(svc_79.MAX_PAGE_LIMIT * 20)
    )
    db_rows = (await db.scalars(stmt)).all()

    audit_rows = [
        svc_79.AuditRow(
            id=str(r.id),
            action=r.action,
            actor_user_id=(str(r.actor_user_id) if r.actor_user_id else None),
            target_type=r.target_type,
            target_id=r.target_id,
            extra=r.extra,
            created_at=r.created_at,
        )
        for r in db_rows
    ]

    timeline = svc_79.build_timeline(
        supplier_id=sid_str,
        rows=audit_rows,
        limit=limit_v,
        offset=offset_v,
    )

    entries = timeline.entries
    if category is not None:
        entries = [e for e in entries if e.category == category]

    return TimelineOut(
        supplier_id=supplier_id,
        total=timeline.total,
        limit=limit_v,
        offset=offset_v,
        entries=[
            TimelineEntryOut(
                id=uuid.UUID(e.id),
                action=e.action,
                category=e.category,
                actor_user_id=(
                    uuid.UUID(e.actor_user_id) if e.actor_user_id else None
                ),
                target_type=e.target_type,
                target_id=e.target_id,
                extra=e.extra,
                created_at=e.created_at,
            )
            for e in entries
        ],
    )
