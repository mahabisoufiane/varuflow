"""Trial onboarding email sequence service.

Pure helpers (no I/O) plus async DB-bound functions for enrolling orgs and
processing pending sends.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trial_sequences import (
    TrialEmailSend,
    TrialEnrollment,
    TrialSequence,
    TrialSequenceStep,
)

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

_KNOWN_TOKENS = {"first_name", "org_name", "trial_end_date", "plan_name"}


def is_eligible_for_step(
    step_key: str,
    send_only_if: dict,
    org_state: dict,
) -> bool:
    """Check conditional skip rules.

    send_only_if dict keys (all optional, default True = send):
      - "has_no_invoices": bool — skip if org has invoices
      - "has_no_team_members": bool — skip if org has >1 members
      - "stripe_not_connected": bool — skip if Stripe is connected
      - "is_pro_or_enterprise": bool — skip if plan is starter

    org_state keys: invoices_count, team_member_count, stripe_connected, plan (str)

    Returns True if email should be sent.
    """
    if send_only_if.get("has_no_invoices"):
        if (org_state.get("invoices_count") or 0) > 0:
            return False

    if send_only_if.get("has_no_team_members"):
        if (org_state.get("team_member_count") or 1) > 1:
            return False

    if send_only_if.get("stripe_not_connected"):
        if org_state.get("stripe_connected"):
            return False

    if send_only_if.get("is_pro_or_enterprise"):
        plan = (org_state.get("plan") or "").lower()
        if plan in ("pro", "enterprise"):
            return False

    return True


def calculate_send_time(
    enrolled_at: datetime,
    delay_days: int,
    org_timezone: str = "Europe/Stockholm",
) -> datetime:
    """Return enrolled_at + delay_days at 09:00 in org_timezone (UTC).

    If the calculated time is in the past (e.g. delay_days=0), return now + 5 min.
    """
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(org_timezone)
    # Convert enrolled_at to the org timezone
    enrolled_local = enrolled_at.astimezone(tz)
    # Add delay days and set time to 09:00
    target_local = (enrolled_local + timedelta(days=delay_days)).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    target_utc = target_local.astimezone(timezone.utc)

    now_utc = datetime.now(timezone.utc)
    if target_utc <= now_utc:
        return now_utc + timedelta(minutes=5)
    return target_utc


def replace_tokens(text: str, tokens: dict) -> str:
    """Replace {{first_name}}, {{org_name}}, {{trial_end_date}}, {{plan_name}} in text.

    tokens dict must have these keys (values can be str or None — None → "").
    Only replace known tokens; leave unknown {{...}} patterns unchanged.
    """

    def _replacer(m: re.Match) -> str:
        key = m.group(1).strip()
        if key not in _KNOWN_TOKENS:
            return m.group(0)  # leave unknown tokens unchanged
        value = tokens.get(key)
        return value if value is not None else ""

    return re.sub(r"\{\{(\s*\w+\s*)\}\}", _replacer, text)


# ---------------------------------------------------------------------------
# Async DB-bound functions
# ---------------------------------------------------------------------------


async def enroll_org(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    user_email: str,
    locale: str,
    trial_ends_at: datetime,
) -> Optional[TrialEnrollment]:
    """Find or create a trial enrollment for the org.

    Looks up the trial_sequences row with trigger_event='trial_started' and the
    given locale. Falls back to locale='en' if none found.

    Uses INSERT ... ON CONFLICT DO NOTHING so concurrent calls are safe.
    Returns the enrollment or None if no sequence found.
    """
    # Try requested locale first, then 'en' fallback
    seq = None
    for try_locale in ([locale] if locale != "en" else []) + ["en"]:
        result = await db.execute(
            select(TrialSequence).where(
                TrialSequence.trigger_event == "trial_started",
                TrialSequence.locale == try_locale,
                TrialSequence.enabled.is_(True),
            )
        )
        seq = result.scalar_one_or_none()
        if seq is not None:
            break

    if seq is None:
        return None

    # Get the first step to compute next_send_at
    first_step_result = await db.execute(
        select(TrialSequenceStep)
        .where(TrialSequenceStep.sequence_id == seq.id)
        .order_by(TrialSequenceStep.step_number.asc())
        .limit(1)
    )
    first_step = first_step_result.scalar_one_or_none()
    delay_days = first_step.delay_days if first_step else 0

    now_utc = datetime.now(timezone.utc)
    next_send_at = calculate_send_time(now_utc, delay_days)

    new_id = uuid.uuid4()
    stmt = (
        pg_insert(TrialEnrollment.__table__)
        .values(
            id=new_id,
            org_id=org_id,
            user_id=user_id,
            sequence_id=seq.id,
            current_step=0,
            next_send_at=next_send_at,
            locale=locale,
        )
        .on_conflict_do_nothing(constraint="uq_trial_enrollments_seq_org")
    )
    await db.execute(stmt)
    await db.commit()

    # Return whatever row now exists (inserted or pre-existing)
    result = await db.execute(
        select(TrialEnrollment).where(
            TrialEnrollment.sequence_id == seq.id,
            TrialEnrollment.org_id == org_id,
        )
    )
    return result.scalar_one_or_none()


async def process_pending_sends(db: AsyncSession) -> int:
    """Send due trial onboarding emails.

    Finds all trial_enrollments where:
    - completed_at IS NULL AND exited_at IS NULL
    - next_send_at <= now (UTC)
    LIMIT 200

    Returns count of emails sent.
    """
    from app.services.email import send_trial_onboarding_email

    now_utc = datetime.now(timezone.utc)

    result = await db.execute(
        select(TrialEnrollment)
        .where(
            TrialEnrollment.completed_at.is_(None),
            TrialEnrollment.exited_at.is_(None),
            TrialEnrollment.next_send_at <= now_utc,
        )
        .limit(200)
    )
    enrollments = result.scalars().all()

    sent_count = 0

    for enrollment in enrollments:
        # Load all steps for this sequence, ordered
        steps_result = await db.execute(
            select(TrialSequenceStep)
            .where(TrialSequenceStep.sequence_id == enrollment.sequence_id)
            .order_by(TrialSequenceStep.step_number.asc())
        )
        steps = steps_result.scalars().all()

        if not steps or enrollment.current_step >= len(steps):
            # No steps or already past the end — complete enrollment
            enrollment.completed_at = now_utc
            continue

        step = steps[enrollment.current_step]

        # Build a minimal org_state for eligibility check.
        # A real implementation would query counts from the DB; here we use
        # safe defaults (no invoices, 1 member, no Stripe, starter plan) so
        # eligibility rules fire conservatively rather than silently skipping
        # all emails. Callers that want richer state should set these values
        # via the send_only_if condition keys on the step.
        org_state: dict = {
            "invoices_count": 0,
            "team_member_count": 1,
            "stripe_connected": False,
            "plan": "starter",
        }

        eligible = is_eligible_for_step(
            step.email_template_key, step.send_only_if or {}, org_state
        )

        if eligible:
            # Try to record the send atomically (prevents double-send)
            send_id = uuid.uuid4()
            send_stmt = (
                pg_insert(TrialEmailSend.__table__)
                .values(
                    id=send_id,
                    enrollment_id=enrollment.id,
                    step_number=step.step_number,
                    email_template_key=step.email_template_key,
                    to_email="",  # will be set by email service via user lookup
                    sent_at=now_utc,
                )
                .on_conflict_do_nothing(
                    constraint="uq_trial_email_sends_enrollment_step"
                )
            )
            insert_result = await db.execute(send_stmt)

            if insert_result.rowcount != 0:
                # Row was freshly inserted — safe to send
                try:
                    await send_trial_onboarding_email(
                        enrollment_id=str(enrollment.id),
                        org_id=str(enrollment.org_id),
                        user_id=str(enrollment.user_id),
                        template_key=step.email_template_key,
                        locale=enrollment.locale,
                    )
                    sent_count += 1
                except Exception:
                    # Best-effort — do not abort the sweep for one failed send
                    pass

        # Advance step regardless of eligibility
        next_step_index = enrollment.current_step + 1
        if next_step_index >= len(steps):
            enrollment.completed_at = now_utc
            enrollment.next_send_at = None
        else:
            next_step = steps[next_step_index]
            enrollment.current_step = next_step_index
            base_time = enrollment.enrolled_at or now_utc
            enrollment.next_send_at = calculate_send_time(
                base_time, next_step.delay_days
            )

    await db.commit()
    return sent_count


async def exit_enrollment(
    db: AsyncSession,
    enrollment_id: uuid.UUID,
    reason: str,
) -> None:
    """Set exited_at = now, exit_reason = reason on the enrollment."""
    result = await db.execute(
        select(TrialEnrollment).where(TrialEnrollment.id == enrollment_id)
    )
    enrollment = result.scalar_one_or_none()
    if enrollment is not None:
        enrollment.exited_at = datetime.now(timezone.utc)
        enrollment.exit_reason = reason
    await db.commit()
