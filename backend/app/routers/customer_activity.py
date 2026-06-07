"""Customer activity timeline router (Item 75).

Endpoint under ``/api/customer-activity``:

    GET /{customer_id}?limit=&offset=&category=

Pure read over the ``audit_log`` — surfaces every event touching a
customer (notes, tags, contacts, credit notes, statements viewed,
invoices, payments) as a unified chronological feed. Reads are
themselves **not** audited — the audit log must not tail itself.
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
from app.models.audit import AuditLogEntry
from app.models.invoicing import Customer
from app.services import customer_activity as svc_75
from app.middleware.plan_check import require_module

router = APIRouter(
    prefix="/api/customer-activity", tags=["customer-activity"],
    dependencies=[Depends(require_module("invoicing"))],
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
    customer_id: uuid.UUID
    total:       int
    limit:       int
    offset:      int
    entries:     list[TimelineEntryOut]


async def _load_customer(
    db: AsyncSession, *, customer_id: uuid.UUID, org_id: uuid.UUID,
) -> Customer:
    row = await db.scalar(
        select(Customer).where(Customer.id == customer_id)
    )
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Customer not found")
    return row


@router.get("/{customer_id}", response_model=TimelineOut)
async def get_customer_timeline(
    customer_id: uuid.UUID,
    limit:    int | None = Query(default=None, ge=1, le=svc_75.MAX_PAGE_LIMIT),
    offset:   int | None = Query(default=None, ge=0),
    category: str | None = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    await _load_customer(
        db, customer_id=customer_id, org_id=member.org_id,
    )

    try:
        limit_v, offset_v = svc_75.normalize_page(
            limit=limit, offset=offset,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Pull a bounded superset — every row under this org with one of
    # the known action names, in reverse chronological order. Filter
    # to the one customer in Python so the same SQL works whether the
    # customer id lives in ``target_id`` or in ``extra->>customer_id``.
    actions = list(svc_75.known_actions())
    cid_str = str(customer_id)
    stmt = (
        select(AuditLogEntry)
        .where(
            AuditLogEntry.org_id == member.org_id,
            AuditLogEntry.action.in_(actions),
            or_(
                AuditLogEntry.target_id == cid_str,
                AuditLogEntry.extra["customer_id"].astext == cid_str,
            ),
        )
        .order_by(AuditLogEntry.created_at.desc(), AuditLogEntry.id.desc())
        # Hard upper bound — even if someone stuffs a million writes
        # on one customer we only ever pull ``MAX_PAGE_LIMIT * 20``
        # rows into Python. That's plenty for sane UIs and caps
        # memory / query cost.
        .limit(svc_75.MAX_PAGE_LIMIT * 20)
    )
    db_rows = (await db.scalars(stmt)).all()

    audit_rows = [
        svc_75.AuditRow(
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

    timeline = svc_75.build_timeline(
        customer_id=cid_str,
        rows=audit_rows,
        limit=limit_v,
        offset=offset_v,
    )

    entries = timeline.entries
    if category is not None:
        entries = [e for e in entries if e.category == category]

    return TimelineOut(
        customer_id=customer_id,
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
