"""Expense activity timeline router (Item 96).

Endpoint under ``/api/expense-activity``:

    GET /{expense_id}?limit=&offset=&category=

Pure read over the ``audit_log`` — surfaces every event touching an
expense (notes, tags, status transitions) as a unified chronological
feed. Reads are themselves **not** audited — the audit log must not
tail itself.
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
from app.middleware.plan_check import require_module
from app.models.audit import AuditLogEntry
from app.models.expenses import Expense
from app.services import expense_activity as svc_96

router = APIRouter(
    prefix="/api/expense-activity", tags=["expense-activity"],
    dependencies=[Depends(require_module("finance"))],
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
    expense_id: uuid.UUID
    total:      int
    limit:      int
    offset:     int
    entries:    list[TimelineEntryOut]


async def _load_expense(
    db: AsyncSession, *, expense_id: uuid.UUID, org_id: uuid.UUID,
) -> Expense:
    row = await db.scalar(
        select(Expense).where(Expense.id == expense_id)
    )
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Expense not found")
    return row


@router.get("/{expense_id}", response_model=TimelineOut)
async def get_expense_timeline(
    expense_id: uuid.UUID,
    limit:    int | None = Query(default=None, ge=1, le=svc_96.MAX_PAGE_LIMIT),
    offset:   int | None = Query(default=None, ge=0),
    category: str | None = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    await _load_expense(
        db, expense_id=expense_id, org_id=member.org_id,
    )

    try:
        limit_v, offset_v = svc_96.normalize_page(
            limit=limit, offset=offset,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    actions = list(svc_96.known_actions())
    eid_str = str(expense_id)
    stmt = (
        select(AuditLogEntry)
        .where(
            AuditLogEntry.org_id == member.org_id,
            AuditLogEntry.action.in_(actions),
            or_(
                AuditLogEntry.target_id == eid_str,
                AuditLogEntry.extra["expense_id"].astext == eid_str,
            ),
        )
        .order_by(AuditLogEntry.created_at.desc(), AuditLogEntry.id.desc())
        .limit(svc_96.MAX_PAGE_LIMIT * 20)
    )
    db_rows = (await db.scalars(stmt)).all()

    audit_rows = [
        svc_96.AuditRow(
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

    timeline = svc_96.build_timeline(
        expense_id=eid_str,
        rows=audit_rows,
        limit=limit_v,
        offset=offset_v,
    )

    entries = timeline.entries
    if category is not None:
        entries = [e for e in entries if e.category == category]

    return TimelineOut(
        expense_id=expense_id,
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
