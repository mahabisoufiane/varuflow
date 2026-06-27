"""Staff commission router (v48 — Item 32).

Endpoint map
------------
Rules
    POST  /api/commissions/rules                 — create
    GET   /api/commissions/rules                 — list (filter staff_id)
    DELETE /api/commissions/rules/{id}           — soft-disable
Runs
    POST  /api/commissions/runs                  — create a new period run
    GET   /api/commissions/runs                  — list
    GET   /api/commissions/runs/{id}             — detail + entries
    POST  /api/commissions/runs/{id}/lock        — freeze (no more edits)
Entries
    GET   /api/commissions/entries/me            — staff self-view
    GET   /api/commissions/entries               — admin list (all staff)
Exports
    GET   /api/commissions/runs/{id}/export.csv  — CSV download
    GET   /api/commissions/runs/{id}/export.pdf  — PDF (reportlab)

Every mutation calls ``log_action`` per the project-wide rule. The
staff self-view endpoint uses ``get_current_member`` like every other
endpoint — the "staff" in this module is the **booking** ``Staff``
row (Item 31), not an auth user. A staff member is expected to sign
in as an OrganizationMember (MEMBER role) whose identity is mapped
to a staff row via ``?staff_id=...`` in their profile link. That
mapping layer lands in a later item; for now the self-view endpoint
accepts an explicit ``staff_id`` and lets the caller's org scope the
query.
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.commissions import CommissionEntry, CommissionRule, CommissionRun
from app.services.audit import log_action
from app.services.commission_calculator import render_run_csv as _calc_render_run_csv, summarise_run

router = APIRouter(prefix="/api/commissions", tags=["commissions"])


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Schemas ─────────────────────────────────────────────────────────


class RuleCreate(BaseModel):
    staff_id: uuid.UUID
    rule_type: str = Field(..., pattern="^(flat|pct|tiered)$")
    value: Decimal
    applies_to: str = Field(default="all", pattern="^(all|service|product|category)$")
    min_threshold: Decimal | None = None


class RuleOut(BaseModel):
    id: uuid.UUID
    staff_id: uuid.UUID
    rule_type: str
    value: Decimal
    applies_to: str
    min_threshold: Decimal | None
    is_active: bool

    model_config = {"from_attributes": True}


class RunCreate(BaseModel):
    period_start: date
    period_end: date


class RunOut(BaseModel):
    id: uuid.UUID
    period_start: date
    period_end: date
    status: str
    total_paid: Decimal
    created_at: datetime
    locked_at: datetime | None

    model_config = {"from_attributes": True}


class EntryOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID | None
    staff_id: uuid.UUID
    source_type: str
    source_id: str
    base_amount: Decimal
    commission_amount: Decimal
    rule_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunDetailOut(BaseModel):
    run: RunOut
    entries: list[EntryOut]
    total: Decimal
    per_staff: dict[str, Decimal]


# ── Rules ───────────────────────────────────────────────────────────


@router.post("/rules", response_model=RuleOut, status_code=201)
async def create_rule(
    body: RuleCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = CommissionRule(
        id=uuid.uuid4(),
        org_id=member.org_id,
        staff_id=body.staff_id,
        rule_type=body.rule_type,
        value=body.value,
        applies_to=body.applies_to,
        min_threshold=body.min_threshold,
    )
    db.add(row)
    await db.flush()
    await log_action(
        db,
        action="commission.rule_created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="commission_rule",
        target_id=str(row.id),
        request=request,
        extra={
            "staff_id": str(body.staff_id),
            "rule_type": body.rule_type,
            "value": str(body.value),
        },
    )
    await db.commit()
    return row


@router.get("/rules", response_model=list[RuleOut])
async def list_rules(
    staff_id: uuid.UUID | None = None,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    q = select(CommissionRule).where(CommissionRule.org_id == member.org_id)
    if staff_id is not None:
        q = q.where(CommissionRule.staff_id == staff_id)
    rows = (await db.execute(q)).scalars().all()
    return list(rows)


@router.delete("/rules/{rule_id}", response_model=RuleOut)
async def disable_rule(
    rule_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = ctx
    row = await db.get(CommissionRule, rule_id)
    if not row or row.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="rule not found")
    row.is_active = False
    await log_action(
        db,
        action="commission.rule_disabled",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="commission_rule",
        target_id=str(row.id),
        request=request,
    )
    await db.commit()
    return row


# ── Runs ────────────────────────────────────────────────────────────


@router.post("/runs", response_model=RunOut, status_code=201)
async def create_run(
    body: RunCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create an ``open`` run for the period and sweep unassigned entries.

    Every ``CommissionEntry`` in the same org whose ``created_at``
    falls inside the period AND whose ``run_id`` is NULL gets attached
    to the new run. Subsequent runs for overlapping periods will not
    re-sweep — an entry belongs to exactly one run once attached.
    """
    user, member = ctx
    if body.period_end < body.period_start:
        raise HTTPException(status_code=422, detail="period_end before period_start")
    run = CommissionRun(
        id=uuid.uuid4(),
        org_id=member.org_id,
        period_start=body.period_start,
        period_end=body.period_end,
        status="open",
    )
    db.add(run)
    await db.flush()
    # Sweep unassigned entries into this run.
    unassigned = (
        await db.execute(
            select(CommissionEntry).where(
                CommissionEntry.org_id == member.org_id,
                CommissionEntry.run_id.is_(None),
                CommissionEntry.created_at >= datetime.combine(body.period_start, datetime.min.time(), tzinfo=timezone.utc),
                CommissionEntry.created_at <= datetime.combine(body.period_end, datetime.max.time(), tzinfo=timezone.utc),
            )
        )
    ).scalars().all()
    for entry in unassigned:
        entry.run_id = run.id
    await log_action(
        db,
        action="commission.run_created",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="commission_run",
        target_id=str(run.id),
        request=request,
        extra={"period_start": body.period_start.isoformat(), "period_end": body.period_end.isoformat(), "entries_attached": len(unassigned)},
    )
    await db.commit()
    return run


@router.get("/runs", response_model=list[RunOut])
async def list_runs(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    rows = (
        await db.execute(
            select(CommissionRun)
            .where(CommissionRun.org_id == member.org_id)
            .order_by(CommissionRun.period_start.desc())
            .limit(100)
        )
    ).scalars().all()
    return list(rows)


@router.get("/runs/{run_id}", response_model=RunDetailOut)
async def run_detail(
    run_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    run = await db.get(CommissionRun, run_id)
    if not run or run.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="run not found")
    entries = (
        await db.execute(
            select(CommissionEntry).where(CommissionEntry.run_id == run_id)
        )
    ).scalars().all()
    summary = summarise_run(entries)
    return RunDetailOut(
        run=run,
        entries=list(entries),
        total=summary["total"],
        per_staff={str(k): v for k, v in summary["per_staff"].items() if k is not None},
    )


@router.post("/runs/{run_id}/lock", response_model=RunOut)
async def lock_run(
    run_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Freeze a run so entries can no longer be added or removed.

    Idempotent — locking an already-locked run returns the row
    unchanged rather than erroring, so a retry from a flaky client
    never corrupts ``locked_at``.
    """
    user, member = ctx
    run = await db.get(CommissionRun, run_id)
    if not run or run.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="run not found")
    if run.status == "locked":
        return run
    entries = (
        await db.execute(
            select(CommissionEntry).where(CommissionEntry.run_id == run.id)
        )
    ).scalars().all()
    summary = summarise_run(entries)
    run.status = "locked"
    run.total_paid = summary["total"]
    run.locked_at = datetime.now(tz=timezone.utc)
    await log_action(
        db,
        action="commission.run_locked",
        org_id=member.org_id,
        actor_user_id=user["user_id"],
        target_type="commission_run",
        target_id=str(run.id),
        request=request,
        extra={"total_paid": str(summary["total"]), "entry_count": len(entries)},
    )
    await db.commit()
    return run


# ── Entries ─────────────────────────────────────────────────────────


@router.get("/entries", response_model=list[EntryOut])
async def list_entries(
    staff_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    q = select(CommissionEntry).where(CommissionEntry.org_id == member.org_id)
    if staff_id is not None:
        q = q.where(CommissionEntry.staff_id == staff_id)
    if run_id is not None:
        q = q.where(CommissionEntry.run_id == run_id)
    q = q.order_by(CommissionEntry.created_at.desc()).limit(1000)
    rows = (await db.execute(q)).scalars().all()
    return list(rows)


@router.get("/entries/me", response_model=list[EntryOut])
async def my_entries(
    staff_id: uuid.UUID = Query(..., description="The caller's linked staff.id"),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Staff self-view.

    Filters strictly on the caller's ``org_id`` + the supplied
    ``staff_id``. Cross-org queries are impossible because the org
    predicate comes from the auth middleware — a caller in Org A who
    supplies a staff_id owned by Org B sees an empty list, never Org
    B's data.
    """
    _, member = ctx
    q = (
        select(CommissionEntry)
        .where(
            CommissionEntry.org_id == member.org_id,
            CommissionEntry.staff_id == staff_id,
        )
        .order_by(CommissionEntry.created_at.desc())
        .limit(500)
    )
    rows = (await db.execute(q)).scalars().all()
    return list(rows)


# ── Exports ─────────────────────────────────────────────────────────


async def _entries_for_run(db: AsyncSession, run: CommissionRun) -> list[CommissionEntry]:
    return list(
        (
            await db.execute(
                select(CommissionEntry)
                .where(CommissionEntry.run_id == run.id)
                .order_by(CommissionEntry.staff_id.asc(), CommissionEntry.created_at.asc())
            )
        )
        .scalars()
        .all()
    )


def render_run_csv(run: CommissionRun, entries: Iterable[CommissionEntry]) -> str:
    """Router-level alias for the pure calculator's CSV renderer."""
    return _calc_render_run_csv(run, entries)


@router.get("/runs/{run_id}/export.csv")
async def export_run_csv(
    run_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    run = await db.get(CommissionRun, run_id)
    if not run or run.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="run not found")
    entries = await _entries_for_run(db, run)
    csv_bytes = render_run_csv(run, entries).encode("utf-8")
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="commission_run_{run_id}.csv"',
        },
    )


@router.get("/runs/{run_id}/export.pdf")
async def export_run_pdf(
    run_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Render a minimal PDF summary via ReportLab.

    The invoicing module already bundles ReportLab as a production
    dependency so this endpoint doesn't add a new wheel. Layout is
    intentionally minimal — a title, the period, a per-staff subtotal
    table — so downstream customisation can live in one place.
    """
    _, member = ctx
    run = await db.get(CommissionRun, run_id)
    if not run or run.org_id != member.org_id:
        raise HTTPException(status_code=404, detail="run not found")
    entries = await _entries_for_run(db, run)
    summary = summarise_run(entries)

    # Lazy import — keeps the router importable on sandboxes that
    # don't have reportlab installed (CI builds for API-types codegen).
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
    from reportlab.lib.styles import getSampleStyleSheet

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=f"Commission run {run.id}")
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"<b>Commission run</b> — {run.period_start} → {run.period_end}", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Status: {run.status}", styles["Normal"]),
        Paragraph(f"Total paid: {summary['total']}", styles["Normal"]),
        Spacer(1, 12),
    ]
    table_rows = [["Staff ID", "Commission amount"]]
    for sid, amt in summary["per_staff"].items():
        table_rows.append([str(sid), str(amt)])
    story.append(Table(table_rows))
    doc.build(story)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="commission_run_{run_id}.pdf"',
        },
    )
