"""Product activity timeline router (Item 82).

Endpoint under ``/api/product-activity``:

    GET /{product_id}?limit=&offset=&category=

Pure read over the ``audit_log`` — surfaces every event touching a
product (notes, tags, batches, stock movements, purchase orders,
sales) as a unified chronological feed. Reads are themselves
**not** audited — the audit log must not tail itself.
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
from .models import Product
from app.services import product_activity as svc_82
from app.middleware.plan_check import require_module

router = APIRouter(
    prefix="/api/product-activity", tags=["product-activity"],
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
    product_id: uuid.UUID
    total:      int
    limit:      int
    offset:     int
    entries:    list[TimelineEntryOut]


async def _load_product(
    db: AsyncSession, *, product_id: uuid.UUID, org_id: uuid.UUID,
) -> Product:
    row = await db.scalar(
        select(Product).where(Product.id == product_id)
    )
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Product not found")
    return row


@router.get("/{product_id}", response_model=TimelineOut)
async def get_product_timeline(
    product_id: uuid.UUID,
    limit:    int | None = Query(default=None, ge=1, le=svc_82.MAX_PAGE_LIMIT),
    offset:   int | None = Query(default=None, ge=0),
    category: str | None = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    await _load_product(
        db, product_id=product_id, org_id=member.org_id,
    )

    try:
        limit_v, offset_v = svc_82.normalize_page(
            limit=limit, offset=offset,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Pull a bounded superset — every row under this org with one of
    # the known action names, in reverse chronological order. Filter
    # to the one product in Python so the same SQL works whether the
    # product id lives in ``target_id`` or in ``extra->>product_id``.
    actions = list(svc_82.known_actions())
    pid_str = str(product_id)
    stmt = (
        select(AuditLogEntry)
        .where(
            AuditLogEntry.org_id == member.org_id,
            AuditLogEntry.action.in_(actions),
            or_(
                AuditLogEntry.target_id == pid_str,
                AuditLogEntry.extra["product_id"].astext == pid_str,
            ),
        )
        .order_by(AuditLogEntry.created_at.desc(), AuditLogEntry.id.desc())
        # Hard upper bound — even if someone stuffs a million writes
        # on one product we only ever pull ``MAX_PAGE_LIMIT * 20``
        # rows into Python. That's plenty for sane UIs and caps
        # memory / query cost.
        .limit(svc_82.MAX_PAGE_LIMIT * 20)
    )
    db_rows = (await db.scalars(stmt)).all()

    audit_rows = [
        svc_82.AuditRow(
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

    timeline = svc_82.build_timeline(
        product_id=pid_str,
        rows=audit_rows,
        limit=limit_v,
        offset=offset_v,
    )

    entries = timeline.entries
    if category is not None:
        entries = [e for e in entries if e.category == category]

    return TimelineOut(
        product_id=product_id,
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
