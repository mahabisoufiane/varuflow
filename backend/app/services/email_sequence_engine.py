"""Email sequence drip engine.

Sends due steps for active enrollments and auto-enrolls segment members.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_sequences import (
    EmailSequence,
    EmailSequenceEnrollment,
    EmailSequenceStep,
)

logger = logging.getLogger(__name__)

STAGE_WEIGHTS: dict[str, float] = {
    "prospect": 0.10,
    "qualified": 0.25,
    "proposal": 0.60,
    "won": 1.00,
    "lost": 0.00,
}


async def send_due_steps(db: AsyncSession) -> int:
    """Send the next step for every active enrollment whose next_send_at is due.

    Returns the number of emails sent.
    """
    from app.services.email import send_campaign_email

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(EmailSequenceEnrollment)
        .where(
            and_(
                EmailSequenceEnrollment.status == "active",
                EmailSequenceEnrollment.next_send_at <= now,
            )
        )
        .limit(500)
    )
    enrollments = result.scalars().all()
    sent = 0

    for enrollment in enrollments:
        try:
            steps_result = await db.execute(
                select(EmailSequenceStep)
                .where(EmailSequenceStep.sequence_id == enrollment.sequence_id)
                .order_by(EmailSequenceStep.step_number)
            )
            steps = steps_result.scalars().all()
            if not steps:
                enrollment.status = "completed"
                enrollment.completed_at = now
                continue

            current_idx = enrollment.current_step
            if current_idx >= len(steps):
                enrollment.status = "completed"
                enrollment.completed_at = now
                continue

            step = steps[current_idx]
            ok = await send_campaign_email(
                to_email=enrollment.email,
                subject=step.subject,
                body_html=step.body_html,
                org_name="",
            )
            if ok:
                sent += 1
                enrollment.current_step = current_idx + 1
                next_idx = current_idx + 1
                if next_idx < len(steps):
                    next_step = steps[next_idx]
                    enrollment.next_send_at = now + timedelta(days=next_step.delay_days)
                else:
                    enrollment.status = "completed"
                    enrollment.completed_at = now
                    enrollment.next_send_at = None
        except Exception:
            logger.exception("email_sequence_engine: failed enrollment=%s", enrollment.id)

    await db.commit()
    return sent


async def enroll_segment_sequences(db: AsyncSession) -> int:
    """Enroll segment members into sequences with trigger_type='segment'.

    Returns the number of new enrollments created.
    """
    from app.models.segments import SegmentMember
    from app.models.invoicing import Customer

    result = await db.execute(
        select(EmailSequence).where(
            and_(
                EmailSequence.trigger_type == "segment",
                EmailSequence.is_active.is_(True),
            )
        )
    )
    sequences = result.scalars().all()
    enrolled = 0

    for seq in sequences:
        try:
            segment_id = uuid.UUID(seq.trigger_value) if seq.trigger_value else None
            if not segment_id:
                continue

            members_result = await db.execute(
                select(SegmentMember.customer_id)
                .where(SegmentMember.segment_id == segment_id)
            )
            customer_ids = [row[0] for row in members_result.all()]
            if not customer_ids:
                continue

            customers_result = await db.execute(
                select(Customer.id, Customer.email)
                .where(Customer.id.in_(customer_ids))
            )
            customers = customers_result.all()

            now = datetime.now(timezone.utc)
            steps_result = await db.execute(
                select(EmailSequenceStep)
                .where(EmailSequenceStep.sequence_id == seq.id)
                .order_by(EmailSequenceStep.step_number)
                .limit(1)
            )
            first_step = steps_result.scalars().first()
            first_send_at = now + timedelta(days=first_step.delay_days) if first_step else now

            for customer_id, email in customers:
                if not email:
                    continue
                stmt = (
                    pg_insert(EmailSequenceEnrollment)
                    .values(
                        id=uuid.uuid4(),
                        sequence_id=seq.id,
                        org_id=seq.org_id,
                        customer_id=customer_id,
                        email=email,
                        status="active",
                        current_step=0,
                        next_send_at=first_send_at,
                        enrolled_at=now,
                    )
                    .on_conflict_do_nothing(constraint="uq_seq_enrollment_customer")
                )
                result2 = await db.execute(stmt)
                enrolled += result2.rowcount

        except Exception:
            logger.exception("email_sequence_engine: enroll_segment failed seq=%s", seq.id)

    await db.commit()
    return enrolled
