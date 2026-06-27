"""Payroll processing router.

Swedish arbetsgivaravgift (social contribution) is 31.42% of gross salary.
Income tax is pre-set per entry (preliminärskattetabell — varies per employee).

Endpoints:
  GET    /api/accounting/payroll                    list runs
  POST   /api/accounting/payroll                    create run
  GET    /api/accounting/payroll/{id}               detail with entries
  POST   /api/accounting/payroll/{id}/entries       add/update entry
  DELETE /api/accounting/payroll/{id}/entries/{eid} remove entry
  POST   /api/accounting/payroll/{id}/approve       approve + post to ledger
  GET    /api/accounting/payroll/{id}/agi-xml       AGI XML for Skatteverket
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module, require_role
from app.features.analytics.accounting_models import JournalEntry, JournalLine
from app.features.auth.organization import OrgRole
from .payroll_models import PayrollEntry, PayrollRun
from app.services.audit import log_action

# Payroll exposes salaries — manager-level data. Gate the WHOLE router at ADMIN
# (not just the write endpoints). Previously the GET handlers had no role check,
# so any finance-module MEMBER could read salary runs. The router-level guard
# closes that read gap; the per-handler _require_owner_or_admin calls remain as
# defence-in-depth.
router = APIRouter(
    prefix="/api/accounting/payroll",
    tags=["payroll"],
    dependencies=[Depends(require_module("finance")), Depends(require_role(OrgRole.ADMIN))],
)
log = logging.getLogger(__name__)

# Swedish arbetsgivaravgift rate 2024
SOCIAL_CONTRIBUTION_RATE = Decimal("0.3142")


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _actor(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return user["user_id"]


def _require_owner_or_admin(ctx: tuple) -> None:
    _, member = ctx
    if member.role not in (OrgRole.OWNER, OrgRole.ADMIN):
        raise HTTPException(status_code=403, detail="Owner or admin required")


# ─── Schemas ──────────────────────────────────────────────────────────────

class EntryIn(BaseModel):
    employee_name: str = Field(..., min_length=1, max_length=200)
    staff_id: Optional[uuid.UUID] = None
    personal_number: Optional[str] = Field(None, max_length=13)  # YYYYMMDD-XXXX
    gross_salary: Decimal = Field(..., gt=0)
    income_tax: Decimal = Field(default=Decimal("0"), ge=0)  # preliminary tax
    notes: Optional[str] = None


class EntryOut(BaseModel):
    id: uuid.UUID
    employee_name: str
    staff_id: Optional[uuid.UUID]
    gross_salary: Decimal
    income_tax: Decimal
    social_contribution: Decimal
    net_salary: Decimal
    employer_total: Decimal
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class RunOut(BaseModel):
    id: uuid.UUID
    period_start: date
    period_end: date
    status: str
    total_gross: Decimal
    total_employer_cost: Decimal
    journal_entry_id: Optional[uuid.UUID]
    approved_at: Optional[datetime]
    created_at: datetime
    entries: list[EntryOut] = []

    model_config = {"from_attributes": True}


class RunCreate(BaseModel):
    period_start: date
    period_end: date


# ─── Endpoints ────────────────────────────────────────────────────────────

@router.get("", response_model=list[RunOut])
async def list_runs(
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        org_id = _org(ctx)
        rows = (
            await db.execute(
                select(PayrollRun)
                .where(PayrollRun.org_id == org_id)
                .options(selectinload(PayrollRun.entries))
                .order_by(PayrollRun.period_start.desc())
            )
        ).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_runs failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=RunOut, status_code=201)
async def create_run(
    body: RunCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        run = PayrollRun(
            org_id=org_id,
            period_start=body.period_start,
            period_end=body.period_end,
            status="DRAFT",
            created_by=_actor(ctx),
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        await log_action(db, action="payroll.run_created", org_id=org_id,
                         actor_user_id=_actor(ctx), target_type="payroll_run",
                         target_id=run.id, request=request)
        await db.commit()
        return run
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_run failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{run_id}", response_model=RunOut)
async def get_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        org_id = _org(ctx)
        run = (
            await db.execute(
                select(PayrollRun)
                .where(PayrollRun.id == run_id, PayrollRun.org_id == org_id)
                .options(selectinload(PayrollRun.entries))
            )
        ).scalar_one_or_none()
        if not run:
            raise HTTPException(status_code=404, detail="Payroll run not found")
        return run
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_run failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{run_id}/entries", response_model=EntryOut, status_code=201)
async def add_entry(
    run_id: uuid.UUID,
    body: EntryIn,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        run = (
            await db.execute(select(PayrollRun).where(PayrollRun.id == run_id, PayrollRun.org_id == org_id))
        ).scalar_one_or_none()
        if not run:
            raise HTTPException(status_code=404, detail="Payroll run not found")
        if run.status != "DRAFT":
            raise HTTPException(status_code=409, detail="Can only add entries to a DRAFT run")

        gross = body.gross_salary
        social = (gross * SOCIAL_CONTRIBUTION_RATE).quantize(Decimal("0.01"))
        net = (gross - body.income_tax).quantize(Decimal("0.01"))
        employer_total = (gross + social).quantize(Decimal("0.01"))

        entry = PayrollEntry(
            payroll_run_id=run.id,
            employee_name=body.employee_name,
            staff_id=body.staff_id,
            personal_number=body.personal_number,
            gross_salary=gross,
            income_tax=body.income_tax,
            social_contribution=social,
            net_salary=net,
            employer_total=employer_total,
            notes=body.notes,
        )
        db.add(entry)

        # Update run totals
        run.total_gross = Decimal(str(run.total_gross)) + gross
        run.total_employer_cost = Decimal(str(run.total_employer_cost)) + employer_total

        await db.commit()
        await db.refresh(entry)
        return entry
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"add_entry failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{run_id}/entries/{entry_id}", status_code=204)
async def delete_entry(
    run_id: uuid.UUID,
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        run = (
            await db.execute(select(PayrollRun).where(PayrollRun.id == run_id, PayrollRun.org_id == org_id))
        ).scalar_one_or_none()
        if not run or run.status != "DRAFT":
            raise HTTPException(status_code=409, detail="Can only remove entries from a DRAFT run")

        ent = (
            await db.execute(select(PayrollEntry).where(PayrollEntry.id == entry_id, PayrollEntry.payroll_run_id == run_id))
        ).scalar_one_or_none()
        if not ent:
            raise HTTPException(status_code=404, detail="Entry not found")

        run.total_gross = max(Decimal("0"), Decimal(str(run.total_gross)) - Decimal(str(ent.gross_salary)))
        run.total_employer_cost = max(Decimal("0"), Decimal(str(run.total_employer_cost)) - Decimal(str(ent.employer_total)))
        await db.delete(ent)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"delete_entry failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{run_id}/approve", response_model=RunOut)
async def approve_run(
    run_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Approve payroll run and post to ledger:
    Debit 7210 Löner (gross)
    Debit 7510 Arbetsgivaravgifter (social)
    Credit 1920 Kassa och bank (net disbursed + tax + social)
    """
    try:
        _require_owner_or_admin(ctx)
        org_id = _org(ctx)
        run = (
            await db.execute(
                select(PayrollRun)
                .where(PayrollRun.id == run_id, PayrollRun.org_id == org_id)
                .options(selectinload(PayrollRun.entries))
            )
        ).scalar_one_or_none()
        if not run:
            raise HTTPException(status_code=404, detail="Payroll run not found")
        if run.status != "DRAFT":
            raise HTTPException(status_code=409, detail="Only DRAFT runs can be approved")
        if not run.entries:
            raise HTTPException(status_code=422, detail="Cannot approve an empty payroll run")

        total_gross   = Decimal(str(run.total_gross))
        total_social  = sum(Decimal(str(e.social_contribution)) for e in run.entries)
        total_bank    = total_gross + total_social  # total cash out

        entry = JournalEntry(
            org_id=org_id,
            entry_date=run.period_end,
            description=f"Payroll {run.period_start} – {run.period_end}",
            source_type="PAYROLL",
            source_id=run.id,
            is_posted=True,
            created_by=_actor(ctx),
        )
        db.add(entry)
        await db.flush()
        db.add(JournalLine(journal_entry_id=entry.id, account_code="7210", debit=total_gross, credit=Decimal("0"), memo="Löner"))
        db.add(JournalLine(journal_entry_id=entry.id, account_code="7510", debit=total_social, credit=Decimal("0"), memo="Arbetsgivaravgifter"))
        db.add(JournalLine(journal_entry_id=entry.id, account_code="1920", debit=Decimal("0"), credit=total_bank, memo="Payroll disbursement"))

        run.status = "APPROVED"
        run.approved_by = _actor(ctx)
        run.approved_at = datetime.now(timezone.utc)
        run.journal_entry_id = entry.id

        await db.commit()
        await db.refresh(run)
        await log_action(db, action="payroll.run_approved", org_id=org_id,
                         actor_user_id=_actor(ctx), target_type="payroll_run",
                         target_id=run.id, request=request)
        await db.commit()
        return run
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"approve_run failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{run_id}/agi-xml")
async def agi_xml(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(get_current_member),
):
    """Generate AGI (Arbetsgivardeklaration) XML for Skatteverket."""
    try:
        org_id = _org(ctx)
        run = (
            await db.execute(
                select(PayrollRun)
                .where(PayrollRun.id == run_id, PayrollRun.org_id == org_id)
                .options(selectinload(PayrollRun.entries))
            )
        ).scalar_one_or_none()
        if not run:
            raise HTTPException(status_code=404, detail="Payroll run not found")

        root = ET.Element("Arbetsgivardeklaration", {
            "xmlns": "urn:se:skatteverket:agi:2.0",
            "Period": f"{run.period_start.year}{run.period_start.month:02d}",
        })
        for ent in run.entries:
            ag = ET.SubElement(root, "IndividualAGI")
            ET.SubElement(ag, "Namn").text = ent.employee_name
            if ent.personal_number:
                ET.SubElement(ag, "Personnummer").text = ent.personal_number
            ET.SubElement(ag, "Lon").text = str(ent.gross_salary)
            ET.SubElement(ag, "AvdragenSkatt").text = str(ent.income_tax)
            ET.SubElement(ag, "Arbetsgivaravgift").text = str(ent.social_contribution)

        xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        return Response(
            content=xml_bytes,
            media_type="application/xml",
            headers={"Content-Disposition": f'attachment; filename="agi_{run.period_start}_{run.period_end}.xml"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"agi_xml failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
