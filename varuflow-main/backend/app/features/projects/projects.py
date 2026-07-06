import uuid
import logging
from decimal import Decimal
from datetime import date, datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from .models import (
    Project, ProjectTask, ProjectMilestone, ProjectExpense,
    ProjectTimeEntry, ProjectRetainer,
)
from app.features.invoicing.models import Invoice, InvoiceLineItem, Customer

log = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_module("hr"))])

# ── Invoice number helper (mirrors invoicing router) ──────────────────────────

async def _next_invoice_number(org_id: uuid.UUID, db: AsyncSession) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"INV-{year}-"
    row = await db.execute(
        text(
            "SELECT MAX(invoice_number) FROM invoices "
            "WHERE org_id = :org_id AND invoice_number LIKE :prefix"
        ),
        {"org_id": str(org_id), "prefix": f"{prefix}%"},
    )
    max_num = row.scalar()
    if max_num:
        try:
            seq = int(max_num.split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"

# ── Schemas ───────────────────────────────────────────────────────────────────

class ProjectIn(BaseModel):
    name: str
    description: Optional[str] = None
    customer_id: Optional[str] = None
    status: str = "active"
    project_type: str = "time_material"
    budget: Optional[float] = None
    default_hourly_rate: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class ProjectPatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    customer_id: Optional[str] = None
    status: Optional[str] = None
    project_type: Optional[str] = None
    budget: Optional[float] = None
    default_hourly_rate: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class TaskIn(BaseModel):
    title: str
    description: Optional[str] = None
    assignee_name: Optional[str] = None
    status: str = "todo"
    priority: str = "medium"
    due_date: Optional[date] = None

class TaskPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_name: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None

class MilestoneIn(BaseModel):
    title: str
    due_date: Optional[date] = None

class MilestonePatch(BaseModel):
    title: Optional[str] = None
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None

class ExpenseIn(BaseModel):
    description: str
    amount: float
    currency: str = "SEK"
    incurred_date: date
    receipt_url: Optional[str] = None

class TimeEntryIn(BaseModel):
    project_id: str
    operator_name: Optional[str] = None
    entry_date: date
    description: Optional[str] = None
    hours: float
    hourly_rate: float
    billable: bool = True

class TimeEntryPatch(BaseModel):
    operator_name: Optional[str] = None
    entry_date: Optional[date] = None
    description: Optional[str] = None
    hours: Optional[float] = None
    hourly_rate: Optional[float] = None
    billable: Optional[bool] = None

class GenerateInvoiceIn(BaseModel):
    entry_ids: List[str]
    customer_id: str
    tax_rate: float = 25.0

class RetainerIn(BaseModel):
    project_id: str
    customer_id: str
    name: str
    monthly_fee: float
    monthly_cap_hours: Optional[float] = None
    billing_day: int = 1

class RetainerPatch(BaseModel):
    name: Optional[str] = None
    monthly_fee: Optional[float] = None
    monthly_cap_hours: Optional[float] = None
    billing_day: Optional[int] = None
    is_active: Optional[bool] = None

# ── Serializers ───────────────────────────────────────────────────────────────

def _proj(p: Project, customer_name: Optional[str] = None) -> dict:
    return {
        "id": str(p.id),
        "org_id": str(p.org_id),
        "customer_id": str(p.customer_id) if p.customer_id else None,
        "customer_name": customer_name,
        "name": p.name,
        "description": p.description,
        "status": p.status,
        "project_type": p.project_type,
        "budget": float(p.budget) if p.budget else None,
        "default_hourly_rate": float(p.default_hourly_rate) if p.default_hourly_rate else None,
        "start_date": p.start_date.isoformat() if p.start_date else None,
        "end_date": p.end_date.isoformat() if p.end_date else None,
        "created_at": p.created_at.isoformat(),
    }

def _task(t: ProjectTask) -> dict:
    return {
        "id": str(t.id),
        "project_id": str(t.project_id),
        "title": t.title,
        "description": t.description,
        "assignee_name": t.assignee_name,
        "status": t.status,
        "priority": t.priority,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "created_at": t.created_at.isoformat(),
    }

def _milestone(m: ProjectMilestone) -> dict:
    return {
        "id": str(m.id),
        "project_id": str(m.project_id),
        "title": m.title,
        "due_date": m.due_date.isoformat() if m.due_date else None,
        "completed_at": m.completed_at.isoformat() if m.completed_at else None,
        "created_at": m.created_at.isoformat(),
    }

def _expense(e: ProjectExpense) -> dict:
    return {
        "id": str(e.id),
        "project_id": str(e.project_id),
        "description": e.description,
        "amount": float(e.amount),
        "currency": e.currency,
        "incurred_date": e.incurred_date.isoformat(),
        "receipt_url": e.receipt_url,
        "created_at": e.created_at.isoformat(),
    }

def _time_entry(e: ProjectTimeEntry) -> dict:
    return {
        "id": str(e.id),
        "project_id": str(e.project_id),
        "operator_name": e.operator_name,
        "entry_date": e.entry_date.isoformat(),
        "description": e.description,
        "hours": float(e.hours),
        "hourly_rate": float(e.hourly_rate),
        "billable": e.billable,
        "invoiced": e.invoiced,
        "invoice_id": str(e.invoice_id) if e.invoice_id else None,
        "created_at": e.created_at.isoformat(),
    }

def _retainer(r: ProjectRetainer) -> dict:
    return {
        "id": str(r.id),
        "project_id": str(r.project_id),
        "customer_id": str(r.customer_id),
        "name": r.name,
        "monthly_fee": float(r.monthly_fee),
        "monthly_cap_hours": float(r.monthly_cap_hours) if r.monthly_cap_hours else None,
        "billing_day": r.billing_day,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat(),
    }

# ── Projects list + create (static routes first to avoid {id} ambiguity) ─────

@router.get("/api/projects")
async def list_projects(request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(
            select(Project).where(Project.org_id == org_id).order_by(Project.created_at.desc())
        )
        projects = result.scalars().all()
        cids = {p.customer_id for p in projects if p.customer_id}
        cust_map = {}
        if cids:
            cr = await db.execute(select(Customer).where(Customer.id.in_(cids)))
            for c in cr.scalars().all():
                cust_map[c.id] = c.company_name
        return [_proj(p, cust_map.get(p.customer_id)) for p in projects]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_projects failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/projects", status_code=201)
async def create_project(body: ProjectIn, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        p = Project(
            id=uuid.uuid4(), org_id=org_id,
            customer_id=uuid.UUID(body.customer_id) if body.customer_id else None,
            name=body.name, description=body.description,
            status=body.status, project_type=body.project_type,
            budget=Decimal(str(body.budget)) if body.budget is not None else None,
            default_hourly_rate=Decimal(str(body.default_hourly_rate)) if body.default_hourly_rate is not None else None,
            start_date=body.start_date, end_date=body.end_date,
        )
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return _proj(p)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"create_project failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ── Time Entries (must be defined BEFORE /api/projects/{project_id}) ─────────

@router.get("/api/projects/time-entries")
async def list_time_entries(
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    project_id: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    invoiced: Optional[bool] = None,
    billable: Optional[bool] = None,
):
    try:
        user, member = ctx
        org_id = member.org_id
        q = select(ProjectTimeEntry).where(ProjectTimeEntry.org_id == org_id)
        if project_id:
            q = q.where(ProjectTimeEntry.project_id == uuid.UUID(project_id))
        if from_date:
            q = q.where(ProjectTimeEntry.entry_date >= from_date)
        if to_date:
            q = q.where(ProjectTimeEntry.entry_date <= to_date)
        if invoiced is not None:
            q = q.where(ProjectTimeEntry.invoiced == invoiced)
        if billable is not None:
            q = q.where(ProjectTimeEntry.billable == billable)
        q = q.order_by(ProjectTimeEntry.entry_date.desc())
        result = await db.execute(q)
        entries = result.scalars().all()
        pids = {e.project_id for e in entries}
        proj_map = {}
        if pids:
            pr = await db.execute(select(Project).where(Project.id.in_(pids)))
            for p in pr.scalars().all():
                proj_map[p.id] = p.name
        return [{**_time_entry(e), "project_name": proj_map.get(e.project_id)} for e in entries]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_time_entries failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/projects/time-entries/generate-invoice", status_code=201)
async def generate_invoice_from_entries(body: GenerateInvoiceIn, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        cust_r = await db.execute(select(Customer).where(Customer.id == uuid.UUID(body.customer_id), Customer.org_id == org_id))
        customer = cust_r.scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        eids = [uuid.UUID(eid) for eid in body.entry_ids]
        entries_r = await db.execute(
            select(ProjectTimeEntry).where(
                ProjectTimeEntry.id.in_(eids),
                ProjectTimeEntry.org_id == org_id,
                ProjectTimeEntry.invoiced == False,  # noqa: E712
            )
        )
        entries = entries_r.scalars().all()
        if not entries:
            raise HTTPException(status_code=422, detail="No uninvoiced entries found for given IDs")
        subtotal = sum(e.hours * e.hourly_rate for e in entries)
        tax_rate = Decimal(str(body.tax_rate))
        vat_amount = (subtotal * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
        total = subtotal + vat_amount
        await db.execute(text("SELECT id FROM organizations WHERE id = :oid FOR UPDATE"), {"oid": str(org_id)})
        inv_number = await _next_invoice_number(org_id, db)
        today = date.today()
        invoice = Invoice(
            id=uuid.uuid4(), org_id=org_id, customer_id=customer.id,
            invoice_number=inv_number, issue_date=today, due_date=today,
            subtotal=subtotal.quantize(Decimal("0.01")),
            vat_amount=vat_amount, total_sek=total.quantize(Decimal("0.01")),
            notes=f"Time billing — {len(entries)} entries",
        )
        db.add(invoice)
        await db.flush()
        proj_r = await db.execute(select(Project).where(Project.id.in_({e.project_id for e in entries})))
        proj_map = {p.id: p.name for p in proj_r.scalars().all()}
        by_proj: dict = {}
        for e in entries:
            by_proj.setdefault(e.project_id, []).append(e)
        for pid, group in by_proj.items():
            hrs = sum(e.hours for e in group)
            rate = group[0].hourly_rate
            line_total = (hrs * rate).quantize(Decimal("0.01"))
            line = InvoiceLineItem(
                id=uuid.uuid4(), invoice_id=invoice.id,
                description=f"{proj_map.get(pid, str(pid)[:8])} — {float(hrs):.2f} hrs",
                quantity=hrs.quantize(Decimal("0.01")), unit_price=rate.quantize(Decimal("0.01")),
                tax_rate=tax_rate, line_total=line_total,
            )
            db.add(line)
        for e in entries:
            e.invoiced = True
            e.invoice_id = invoice.id
        await db.commit()
        await db.refresh(invoice)
        return {
            "invoice_id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
            "subtotal": float(invoice.subtotal),
            "vat_amount": float(invoice.vat_amount),
            "total_sek": float(invoice.total_sek),
            "entry_count": len(entries),
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"generate_invoice_from_entries failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/projects/time-entries", status_code=201)
async def create_time_entry(body: TimeEntryIn, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(Project).where(Project.id == uuid.UUID(body.project_id), Project.org_id == org_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Project not found")
        e = ProjectTimeEntry(
            id=uuid.uuid4(), org_id=org_id, project_id=uuid.UUID(body.project_id),
            operator_name=body.operator_name, entry_date=body.entry_date,
            description=body.description, hours=Decimal(str(body.hours)),
            hourly_rate=Decimal(str(body.hourly_rate)), billable=body.billable,
        )
        db.add(e)
        await db.commit()
        await db.refresh(e)
        return _time_entry(e)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"create_time_entry failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/projects/time-entries/{entry_id}")
async def update_time_entry(entry_id: str, body: TimeEntryPatch, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(ProjectTimeEntry).where(ProjectTimeEntry.id == uuid.UUID(entry_id), ProjectTimeEntry.org_id == org_id))
        e = result.scalar_one_or_none()
        if not e:
            raise HTTPException(status_code=404, detail="Time entry not found")
        if e.invoiced:
            raise HTTPException(status_code=422, detail="Cannot edit an invoiced time entry")
        for field, val in body.model_dump(exclude_unset=True).items():
            if field in ("hours", "hourly_rate"):
                setattr(e, field, Decimal(str(val)) if val is not None else val)
            else:
                setattr(e, field, val)
        await db.commit()
        await db.refresh(e)
        return _time_entry(e)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"update_time_entry failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/projects/time-entries/{entry_id}", status_code=204)
async def delete_time_entry(entry_id: str, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(ProjectTimeEntry).where(ProjectTimeEntry.id == uuid.UUID(entry_id), ProjectTimeEntry.org_id == org_id))
        e = result.scalar_one_or_none()
        if not e:
            raise HTTPException(status_code=404, detail="Time entry not found")
        if e.invoiced:
            raise HTTPException(status_code=422, detail="Cannot delete an invoiced time entry")
        await db.delete(e)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"delete_time_entry failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ── Timesheet approval endpoints ───────────────────────────────────────────────

@router.get("/api/projects/time-entries/pending-approval")
async def list_pending_time_entries(request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        role = getattr(member, "role", None) or "MEMBER"
        if role not in ("OWNER", "ADMIN"):
            raise HTTPException(status_code=403, detail="Manager access required")
        result = await db.execute(
            select(ProjectTimeEntry)
            .where(ProjectTimeEntry.org_id == org_id, ProjectTimeEntry.approval_status == "pending")
            .order_by(ProjectTimeEntry.entry_date.desc())
        )
        entries = result.scalars().all()
        return [_time_entry(e) for e in entries]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_pending_time_entries failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/projects/time-entries/{entry_id}/approve")
async def approve_time_entry(entry_id: str, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        role = getattr(member, "role", None) or "MEMBER"
        if role not in ("OWNER", "ADMIN"):
            raise HTTPException(status_code=403, detail="Only managers can approve")
        result = await db.execute(select(ProjectTimeEntry).where(ProjectTimeEntry.id == uuid.UUID(entry_id), ProjectTimeEntry.org_id == org_id))
        e = result.scalar_one_or_none()
        if not e:
            raise HTTPException(status_code=404, detail="Time entry not found")
        if e.approval_status != "pending":
            raise HTTPException(status_code=409, detail="Already reviewed")
        e.approval_status = "approved"
        e.approved_by = uuid.UUID(user["user_id"]) if "user_id" in user else None
        e.approved_at = datetime.now(timezone.utc)
        await db.commit()
        return {"status": "approved"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"approve_time_entry failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/projects/time-entries/{entry_id}/reject")
async def reject_time_entry(entry_id: str, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        role = getattr(member, "role", None) or "MEMBER"
        if role not in ("OWNER", "ADMIN"):
            raise HTTPException(status_code=403, detail="Only managers can reject")
        result = await db.execute(select(ProjectTimeEntry).where(ProjectTimeEntry.id == uuid.UUID(entry_id), ProjectTimeEntry.org_id == org_id))
        e = result.scalar_one_or_none()
        if not e:
            raise HTTPException(status_code=404, detail="Time entry not found")
        if e.approval_status != "pending":
            raise HTTPException(status_code=409, detail="Already reviewed")
        e.approval_status = "rejected"
        e.approved_by = uuid.UUID(user["user_id"]) if "user_id" in user else None
        e.approved_at = datetime.now(timezone.utc)
        await db.commit()
        return {"status": "rejected"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"reject_time_entry failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Retainers (must be defined BEFORE /api/projects/{project_id}) ────────────

@router.get("/api/projects/retainers")
async def list_retainers(request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(ProjectRetainer).where(ProjectRetainer.org_id == org_id).order_by(ProjectRetainer.created_at.desc()))
        retainers = result.scalars().all()
        cids = {r.customer_id for r in retainers}
        cust_map = {}
        if cids:
            cr = await db.execute(select(Customer).where(Customer.id.in_(cids)))
            for c in cr.scalars().all():
                cust_map[c.id] = c.company_name
        proj_ids = {r.project_id for r in retainers}
        proj_map = {}
        if proj_ids:
            pr = await db.execute(select(Project).where(Project.id.in_(proj_ids)))
            for p in pr.scalars().all():
                proj_map[p.id] = p.name
        return [{**_retainer(r), "customer_name": cust_map.get(r.customer_id), "project_name": proj_map.get(r.project_id)} for r in retainers]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_retainers failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/projects/retainers", status_code=201)
async def create_retainer(body: RetainerIn, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(Project).where(Project.id == uuid.UUID(body.project_id), Project.org_id == org_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Project not found")
        cust_r = await db.execute(select(Customer).where(Customer.id == uuid.UUID(body.customer_id), Customer.org_id == org_id))
        if not cust_r.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Customer not found")
        r = ProjectRetainer(
            id=uuid.uuid4(), org_id=org_id,
            project_id=uuid.UUID(body.project_id), customer_id=uuid.UUID(body.customer_id),
            name=body.name, monthly_fee=Decimal(str(body.monthly_fee)),
            monthly_cap_hours=Decimal(str(body.monthly_cap_hours)) if body.monthly_cap_hours is not None else None,
            billing_day=body.billing_day,
        )
        db.add(r)
        await db.commit()
        await db.refresh(r)
        return _retainer(r)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"create_retainer failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/projects/retainers/{retainer_id}")
async def update_retainer(retainer_id: str, body: RetainerPatch, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(ProjectRetainer).where(ProjectRetainer.id == uuid.UUID(retainer_id), ProjectRetainer.org_id == org_id))
        r = result.scalar_one_or_none()
        if not r:
            raise HTTPException(status_code=404, detail="Retainer not found")
        for field, val in body.model_dump(exclude_unset=True).items():
            if field in ("monthly_fee", "monthly_cap_hours"):
                setattr(r, field, Decimal(str(val)) if val is not None else None)
            else:
                setattr(r, field, val)
        await db.commit()
        await db.refresh(r)
        return _retainer(r)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"update_retainer failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/projects/retainers/{retainer_id}", status_code=204)
async def delete_retainer(retainer_id: str, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(ProjectRetainer).where(ProjectRetainer.id == uuid.UUID(retainer_id), ProjectRetainer.org_id == org_id))
        r = result.scalar_one_or_none()
        if not r:
            raise HTTPException(status_code=404, detail="Retainer not found")
        await db.delete(r)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"delete_retainer failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/projects/retainers/{retainer_id}/bill", status_code=201)
async def bill_retainer(retainer_id: str, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(ProjectRetainer).where(ProjectRetainer.id == uuid.UUID(retainer_id), ProjectRetainer.org_id == org_id))
        r = result.scalar_one_or_none()
        if not r:
            raise HTTPException(status_code=404, detail="Retainer not found")
        if not r.is_active:
            raise HTTPException(status_code=422, detail="Retainer is not active")
        await db.execute(text("SELECT id FROM organizations WHERE id = :oid FOR UPDATE"), {"oid": str(org_id)})
        inv_number = await _next_invoice_number(org_id, db)
        today = date.today()
        subtotal = r.monthly_fee
        vat_amount = (subtotal * Decimal("0.25")).quantize(Decimal("0.01"))
        total = subtotal + vat_amount
        invoice = Invoice(
            id=uuid.uuid4(), org_id=org_id, customer_id=r.customer_id,
            invoice_number=inv_number, issue_date=today, due_date=today,
            subtotal=subtotal, vat_amount=vat_amount, total_sek=total,
            notes=f"Monthly retainer: {r.name}",
        )
        db.add(invoice)
        await db.flush()
        cap_note = f" (cap: {float(r.monthly_cap_hours):.1f}h/month)" if r.monthly_cap_hours else ""
        line = InvoiceLineItem(
            id=uuid.uuid4(), invoice_id=invoice.id,
            description=f"Monthly retainer — {r.name}{cap_note}",
            quantity=Decimal("1.00"), unit_price=subtotal,
            tax_rate=Decimal("25.00"), line_total=subtotal,
        )
        db.add(line)
        await db.commit()
        await db.refresh(invoice)
        return {
            "invoice_id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
            "total_sek": float(invoice.total_sek),
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"bill_retainer failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ── Project detail + mutations (dynamic {project_id} routes last) ─────────────

@router.get("/api/projects/{project_id}")
async def get_project(project_id: str, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(Project).where(Project.id == uuid.UUID(project_id), Project.org_id == org_id))
        p = result.scalar_one_or_none()
        if not p:
            raise HTTPException(status_code=404, detail="Project not found")
        tasks_r = await db.execute(select(ProjectTask).where(ProjectTask.project_id == p.id).order_by(ProjectTask.created_at))
        milestones_r = await db.execute(select(ProjectMilestone).where(ProjectMilestone.project_id == p.id).order_by(ProjectMilestone.due_date))
        expenses_r = await db.execute(select(ProjectExpense).where(ProjectExpense.project_id == p.id).order_by(ProjectExpense.incurred_date))
        return {
            **_proj(p),
            "tasks": [_task(t) for t in tasks_r.scalars().all()],
            "milestones": [_milestone(m) for m in milestones_r.scalars().all()],
            "expenses": [_expense(e) for e in expenses_r.scalars().all()],
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_project failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/projects/{project_id}")
async def update_project(project_id: str, body: ProjectPatch, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(Project).where(Project.id == uuid.UUID(project_id), Project.org_id == org_id))
        p = result.scalar_one_or_none()
        if not p:
            raise HTTPException(status_code=404, detail="Project not found")
        for field, val in body.model_dump(exclude_unset=True).items():
            if field == "customer_id":
                setattr(p, field, uuid.UUID(val) if val else None)
            elif field in ("budget", "default_hourly_rate"):
                setattr(p, field, Decimal(str(val)) if val is not None else None)
            else:
                setattr(p, field, val)
        await db.commit()
        await db.refresh(p)
        return _proj(p)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"update_project failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/projects/{project_id}", status_code=204)
async def delete_project(project_id: str, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(Project).where(Project.id == uuid.UUID(project_id), Project.org_id == org_id))
        p = result.scalar_one_or_none()
        if not p:
            raise HTTPException(status_code=404, detail="Project not found")
        await db.delete(p)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"delete_project failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/projects/{project_id}/pl")
async def project_pl(project_id: str, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(Project).where(Project.id == uuid.UUID(project_id), Project.org_id == org_id))
        p = result.scalar_one_or_none()
        if not p:
            raise HTTPException(status_code=404, detail="Project not found")
        entries_r = await db.execute(select(ProjectTimeEntry).where(ProjectTimeEntry.project_id == p.id))
        entries = entries_r.scalars().all()
        total_hours = sum(float(e.hours) for e in entries)
        billable_hours = sum(float(e.hours) for e in entries if e.billable)
        labour_cost = sum(float(e.hours) * float(e.hourly_rate) for e in entries)
        invoiced_value = sum(float(e.hours) * float(e.hourly_rate) for e in entries if e.invoiced and e.billable)
        expenses_r = await db.execute(select(ProjectExpense).where(ProjectExpense.project_id == p.id))
        total_expenses = sum(float(ex.amount) for ex in expenses_r.scalars().all())
        total_cost = labour_cost + total_expenses
        margin = invoiced_value - total_cost
        margin_pct = (margin / invoiced_value * 100) if invoiced_value > 0 else 0.0
        return {
            "project_id": str(p.id),
            "project_name": p.name,
            "budget": float(p.budget) if p.budget else None,
            "total_hours": round(total_hours, 2),
            "billable_hours": round(billable_hours, 2),
            "labour_cost": round(labour_cost, 2),
            "total_expenses": round(total_expenses, 2),
            "total_cost": round(total_cost, 2),
            "invoiced_value": round(invoiced_value, 2),
            "margin": round(margin, 2),
            "margin_pct": round(margin_pct, 1),
            "budget_remaining": round(float(p.budget) - total_cost, 2) if p.budget else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"project_pl failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ── Tasks ─────────────────────────────────────────────────────────────────────

@router.post("/api/projects/{project_id}/tasks", status_code=201)
async def create_task(project_id: str, body: TaskIn, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(Project).where(Project.id == uuid.UUID(project_id), Project.org_id == org_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Project not found")
        t = ProjectTask(
            id=uuid.uuid4(), org_id=org_id, project_id=uuid.UUID(project_id),
            title=body.title, description=body.description, assignee_name=body.assignee_name,
            status=body.status, priority=body.priority, due_date=body.due_date,
        )
        db.add(t)
        await db.commit()
        await db.refresh(t)
        return _task(t)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"create_task failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/projects/{project_id}/tasks/{task_id}")
async def update_task(project_id: str, task_id: str, body: TaskPatch, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(ProjectTask).where(ProjectTask.id == uuid.UUID(task_id), ProjectTask.org_id == org_id, ProjectTask.project_id == uuid.UUID(project_id)))
        t = result.scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=404, detail="Task not found")
        updates = body.model_dump(exclude_unset=True)
        if updates.get("status") == "done" and t.status != "done":
            updates["completed_at"] = datetime.now(timezone.utc)
        elif updates.get("status") and updates["status"] != "done":
            updates["completed_at"] = None
        for field, val in updates.items():
            setattr(t, field, val)
        await db.commit()
        await db.refresh(t)
        return _task(t)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"update_task failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/projects/{project_id}/tasks/{task_id}", status_code=204)
async def delete_task(project_id: str, task_id: str, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(ProjectTask).where(ProjectTask.id == uuid.UUID(task_id), ProjectTask.org_id == org_id))
        t = result.scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=404, detail="Task not found")
        await db.delete(t)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"delete_task failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ── Milestones ────────────────────────────────────────────────────────────────

@router.post("/api/projects/{project_id}/milestones", status_code=201)
async def create_milestone(project_id: str, body: MilestoneIn, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(Project).where(Project.id == uuid.UUID(project_id), Project.org_id == org_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Project not found")
        m = ProjectMilestone(id=uuid.uuid4(), org_id=org_id, project_id=uuid.UUID(project_id), title=body.title, due_date=body.due_date)
        db.add(m)
        await db.commit()
        await db.refresh(m)
        return _milestone(m)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"create_milestone failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/projects/{project_id}/milestones/{milestone_id}")
async def update_milestone(project_id: str, milestone_id: str, body: MilestonePatch, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(ProjectMilestone).where(ProjectMilestone.id == uuid.UUID(milestone_id), ProjectMilestone.org_id == org_id, ProjectMilestone.project_id == uuid.UUID(project_id)))
        m = result.scalar_one_or_none()
        if not m:
            raise HTTPException(status_code=404, detail="Milestone not found")
        for field, val in body.model_dump(exclude_unset=True).items():
            setattr(m, field, val)
        await db.commit()
        await db.refresh(m)
        return _milestone(m)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"update_milestone failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/projects/{project_id}/milestones/{milestone_id}", status_code=204)
async def delete_milestone(project_id: str, milestone_id: str, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(ProjectMilestone).where(ProjectMilestone.id == uuid.UUID(milestone_id), ProjectMilestone.org_id == org_id))
        m = result.scalar_one_or_none()
        if not m:
            raise HTTPException(status_code=404, detail="Milestone not found")
        await db.delete(m)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"delete_milestone failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ── Expenses ─────────────────────────────────────────────────────────────────

@router.post("/api/projects/{project_id}/expenses", status_code=201)
async def create_expense(project_id: str, body: ExpenseIn, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(Project).where(Project.id == uuid.UUID(project_id), Project.org_id == org_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Project not found")
        e = ProjectExpense(
            id=uuid.uuid4(), org_id=org_id, project_id=uuid.UUID(project_id),
            description=body.description, amount=Decimal(str(body.amount)),
            currency=body.currency, incurred_date=body.incurred_date, receipt_url=body.receipt_url,
        )
        db.add(e)
        await db.commit()
        await db.refresh(e)
        return _expense(e)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"create_expense failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/projects/{project_id}/expenses/{expense_id}", status_code=204)
async def delete_expense(project_id: str, expense_id: str, request: Request, ctx: tuple = Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        user, member = ctx
        org_id = member.org_id
        result = await db.execute(select(ProjectExpense).where(ProjectExpense.id == uuid.UUID(expense_id), ProjectExpense.org_id == org_id))
        e = result.scalar_one_or_none()
        if not e:
            raise HTTPException(status_code=404, detail="Expense not found")
        await db.delete(e)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"delete_expense failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
