"""Email sequence router: CRUD for sequences, steps, and enrollments."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.email_sequences import (
    EmailSequence,
    EmailSequenceEnrollment,
    EmailSequenceStep,
)

log = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_module("crm"))])


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class SequenceCreate(BaseModel):
    name: str
    trigger_type: Optional[str] = None
    trigger_value: Optional[str] = None
    is_active: bool = True


class SequenceUpdate(BaseModel):
    name: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_value: Optional[str] = None
    is_active: Optional[bool] = None


class StepCreate(BaseModel):
    step_number: int
    delay_days: int = 0
    subject: str
    body_html: str


class StepUpdate(BaseModel):
    delay_days: Optional[int] = None
    subject: Optional[str] = None
    body_html: Optional[str] = None


class EnrollBody(BaseModel):
    customer_ids: Optional[list[uuid.UUID]] = None
    emails: Optional[list[str]] = None


# ── Serializers ──────────────────────────────────────────────────────────────

def _step_out(s: EmailSequenceStep) -> dict:
    return {
        "id": str(s.id),
        "step_number": s.step_number,
        "delay_days": s.delay_days,
        "subject": s.subject,
        "body_html": s.body_html,
        "created_at": s.created_at.isoformat(),
    }


def _seq_out(s: EmailSequence, include_steps: bool = False, enrollment_count: int = 0) -> dict:
    out = {
        "id": str(s.id),
        "name": s.name,
        "trigger_type": s.trigger_type,
        "trigger_value": s.trigger_value,
        "is_active": s.is_active,
        "enrollment_count": enrollment_count,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }
    if include_steps:
        out["steps"] = [_step_out(st) for st in s.steps]
    return out


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/api/crm/sequences")
async def list_sequences(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        result = await db.execute(
            select(EmailSequence)
            .where(EmailSequence.org_id == org_id)
            .order_by(EmailSequence.created_at.desc())
        )
        sequences = result.scalars().all()
        # Enrollment counts
        counts_result = await db.execute(
            select(EmailSequenceEnrollment.sequence_id, func.count())
            .where(EmailSequenceEnrollment.org_id == org_id)
            .group_by(EmailSequenceEnrollment.sequence_id)
        )
        counts = {str(row[0]): row[1] for row in counts_result.all()}
        return [_seq_out(s, enrollment_count=counts.get(str(s.id), 0)) for s in sequences]
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_sequences failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/crm/sequences", status_code=201)
async def create_sequence(
    body: SequenceCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        seq = EmailSequence(
            id=uuid.uuid4(),
            org_id=org_id,
            name=body.name,
            trigger_type=body.trigger_type,
            trigger_value=body.trigger_value,
            is_active=body.is_active,
        )
        db.add(seq)
        await db.commit()
        await db.refresh(seq)
        return _seq_out(seq)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_sequence failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/crm/sequences/{seq_id}")
async def get_sequence(
    seq_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        result = await db.execute(
            select(EmailSequence)
            .where(and_(EmailSequence.id == seq_id, EmailSequence.org_id == org_id))
            .options(selectinload(EmailSequence.steps))
        )
        seq = result.scalars().first()
        if not seq:
            raise HTTPException(status_code=404, detail="Sequence not found")
        count_result = await db.execute(
            select(func.count()).where(EmailSequenceEnrollment.sequence_id == seq_id)
        )
        count = count_result.scalar() or 0
        return _seq_out(seq, include_steps=True, enrollment_count=count)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_sequence failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/crm/sequences/{seq_id}")
async def update_sequence(
    seq_id: uuid.UUID,
    body: SequenceUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        result = await db.execute(
            select(EmailSequence).where(and_(EmailSequence.id == seq_id, EmailSequence.org_id == org_id))
        )
        seq = result.scalars().first()
        if not seq:
            raise HTTPException(status_code=404, detail="Sequence not found")
        if body.name is not None:
            seq.name = body.name
        if body.trigger_type is not None:
            seq.trigger_type = body.trigger_type
        if body.trigger_value is not None:
            seq.trigger_value = body.trigger_value
        if body.is_active is not None:
            seq.is_active = body.is_active
        await db.commit()
        await db.refresh(seq)
        return _seq_out(seq)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_sequence failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/crm/sequences/{seq_id}", status_code=204)
async def delete_sequence(
    seq_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        result = await db.execute(
            select(EmailSequence).where(and_(EmailSequence.id == seq_id, EmailSequence.org_id == org_id))
        )
        seq = result.scalars().first()
        if not seq:
            raise HTTPException(status_code=404, detail="Sequence not found")
        await db.delete(seq)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_sequence failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/crm/sequences/{seq_id}/steps", status_code=201)
async def add_step(
    seq_id: uuid.UUID,
    body: StepCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        result = await db.execute(
            select(EmailSequence).where(and_(EmailSequence.id == seq_id, EmailSequence.org_id == org_id))
        )
        if not result.scalars().first():
            raise HTTPException(status_code=404, detail="Sequence not found")
        step = EmailSequenceStep(
            id=uuid.uuid4(),
            sequence_id=seq_id,
            step_number=body.step_number,
            delay_days=body.delay_days,
            subject=body.subject,
            body_html=body.body_html,
        )
        db.add(step)
        await db.commit()
        await db.refresh(step)
        return _step_out(step)
    except HTTPException:
        raise
    except Exception as e:
        log.error("add_step failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/crm/sequences/{seq_id}/steps/{step_id}")
async def update_step(
    seq_id: uuid.UUID,
    step_id: uuid.UUID,
    body: StepUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        result = await db.execute(
            select(EmailSequenceStep)
            .join(EmailSequence, EmailSequenceStep.sequence_id == EmailSequence.id)
            .where(and_(EmailSequenceStep.id == step_id, EmailSequence.id == seq_id, EmailSequence.org_id == org_id))
        )
        step = result.scalars().first()
        if not step:
            raise HTTPException(status_code=404, detail="Step not found")
        if body.delay_days is not None:
            step.delay_days = body.delay_days
        if body.subject is not None:
            step.subject = body.subject
        if body.body_html is not None:
            step.body_html = body.body_html
        await db.commit()
        await db.refresh(step)
        return _step_out(step)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_step failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/crm/sequences/{seq_id}/steps/{step_id}", status_code=204)
async def delete_step(
    seq_id: uuid.UUID,
    step_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        result = await db.execute(
            select(EmailSequenceStep)
            .join(EmailSequence, EmailSequenceStep.sequence_id == EmailSequence.id)
            .where(and_(EmailSequenceStep.id == step_id, EmailSequence.id == seq_id, EmailSequence.org_id == org_id))
        )
        step = result.scalars().first()
        if not step:
            raise HTTPException(status_code=404, detail="Step not found")
        await db.delete(step)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_step failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/crm/sequences/{seq_id}/enroll", status_code=201)
async def enroll_manually(
    seq_id: uuid.UUID,
    body: EnrollBody,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        result = await db.execute(
            select(EmailSequence)
            .where(and_(EmailSequence.id == seq_id, EmailSequence.org_id == org_id))
            .options(selectinload(EmailSequence.steps))
        )
        seq = result.scalars().first()
        if not seq:
            raise HTTPException(status_code=404, detail="Sequence not found")

        now = datetime.now(timezone.utc)
        first_step = seq.steps[0] if seq.steps else None
        send_at = now + timedelta(days=first_step.delay_days) if first_step else now

        enrolled = 0
        emails_to_enroll: list[tuple[Optional[uuid.UUID], str]] = []

        if body.customer_ids:
            from app.models.invoicing import Customer
            cust_result = await db.execute(
                select(Customer.id, Customer.email).where(Customer.id.in_(body.customer_ids))
            )
            for cid, email in cust_result.all():
                if email:
                    emails_to_enroll.append((cid, email))

        if body.emails:
            for email in body.emails:
                emails_to_enroll.append((None, email))

        for customer_id, email in emails_to_enroll:
            stmt = (
                pg_insert(EmailSequenceEnrollment)
                .values(
                    id=uuid.uuid4(),
                    sequence_id=seq_id,
                    org_id=org_id,
                    customer_id=customer_id,
                    email=email,
                    status="active",
                    current_step=0,
                    next_send_at=send_at,
                    enrolled_at=now,
                )
                .on_conflict_do_nothing(constraint="uq_seq_enrollment_customer")
            )
            result2 = await db.execute(stmt)
            enrolled += result2.rowcount

        await db.commit()
        return {"enrolled": enrolled}
    except HTTPException:
        raise
    except Exception as e:
        log.error("enroll_manually failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/crm/sequences/{seq_id}/enrollments")
async def list_enrollments(
    seq_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        result = await db.execute(
            select(EmailSequenceEnrollment)
            .where(
                and_(
                    EmailSequenceEnrollment.sequence_id == seq_id,
                    EmailSequenceEnrollment.org_id == org_id,
                )
            )
            .order_by(EmailSequenceEnrollment.enrolled_at.desc())
            .limit(200)
        )
        enrollments = result.scalars().all()
        return [
            {
                "id": str(e.id),
                "email": e.email,
                "customer_id": str(e.customer_id) if e.customer_id else None,
                "status": e.status,
                "current_step": e.current_step,
                "next_send_at": e.next_send_at.isoformat() if e.next_send_at else None,
                "enrolled_at": e.enrolled_at.isoformat(),
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
            }
            for e in enrollments
        ]
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_enrollments failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")
