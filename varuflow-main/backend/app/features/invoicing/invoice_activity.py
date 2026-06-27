"""Invoice activity timeline router (Item 88).

Endpoint under ``/api/invoice-activity``:

    GET /{invoice_id}?limit=&offset=&category=

Pure read over the ``audit_log`` — surfaces every event touching
an invoice (notes, tags, installment plan changes, bulk discounts)
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
from app.features.invoicing.models import Invoice
from app.services import invoice_activity as svc_88
from app.middleware.plan_check import require_module

router = APIRouter(
    prefix="/api/invoice-activity", tags=["invoice-activity"],
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
    invoice_id: uuid.UUID
    total:      int
    limit:      int
    offset:     int
    entries:    list[TimelineEntryOut]


async def _load_invoice(
    db: AsyncSession, *, invoice_id: uuid.UUID, org_id: uuid.UUID,
) -> Invoice:
    row = await db.scalar(
        select(Invoice).where(Invoice.id == invoice_id)
    )
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return row


@router.get("/{invoice_id}", response_model=TimelineOut)
async def get_invoice_timeline(
    invoice_id: uuid.UUID,
    limit:    int | None = Query(default=None, ge=1, le=svc_88.MAX_PAGE_LIMIT),
    offset:   int | None = Query(default=None, ge=0),
    category: str | None = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    await _load_invoice(
        db, invoice_id=invoice_id, org_id=member.org_id,
    )

    try:
        limit_v, offset_v = svc_88.normalize_page(
            limit=limit, offset=offset,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Pull a bounded superset — every row under this org with one of
    # the known action names, in reverse chronological order. Filter
    # to the one invoice in Python so the same SQL works whether the
    # invoice id lives in ``target_id`` or in ``extra->>invoice_id``.
    actions = list(svc_88.known_actions())
    iid_str = str(invoice_id)
    stmt = (
        select(AuditLogEntry)
        .where(
            AuditLogEntry.org_id == member.org_id,
            AuditLogEntry.action.in_(actions),
            or_(
                AuditLogEntry.target_id == iid_str,
                AuditLogEntry.extra["invoice_id"].astext == iid_str,
            ),
        )
        .order_by(AuditLogEntry.created_at.desc(), AuditLogEntry.id.desc())
        # Hard upper bound — even if someone stuffs a million writes
        # on one invoice we only ever pull ``MAX_PAGE_LIMIT * 20``
        # rows into Python. That's plenty for sane UIs and caps
        # memory / query cost.
        .limit(svc_88.MAX_PAGE_LIMIT * 20)
    )
    db_rows = (await db.scalars(stmt)).all()

    audit_rows = [
        svc_88.AuditRow(
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

    timeline = svc_88.build_timeline(
        invoice_id=iid_str,
        rows=audit_rows,
        limit=limit_v,
        offset=offset_v,
    )

    entries = timeline.entries
    if category is not None:
        entries = [e for e in entries if e.category == category]

    return TimelineOut(
        invoice_id=invoice_id,
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
