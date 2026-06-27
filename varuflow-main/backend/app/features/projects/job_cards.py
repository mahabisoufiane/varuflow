"""Job Cards router — field-service work orders."""
import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .job_cards_models import JobCard, JobCardPart, JobCardLabour, JobCardPhoto
from app.features.invoicing.models import Invoice, InvoiceLineItem, Customer
from app.middleware.plan_check import require_module

log = logging.getLogger(__name__)
router = APIRouter(tags=["job-cards"], dependencies=[Depends(require_module("manufacturing"))])


# ── Schemas ────────────────────────────────────────────────────────────────────

class JobCardIn(BaseModel):
    title: str
    description: Optional[str] = None
    customer_id: Optional[str] = None
    assigned_staff_id: Optional[str] = None
    site_address: Optional[str] = None
    scheduled_date: Optional[date] = None
    estimated_hours: Optional[float] = None
    currency: str = "SEK"
    notes: Optional[str] = None

class JobCardPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    customer_id: Optional[str] = None
    assigned_staff_id: Optional[str] = None
    site_address: Optional[str] = None
    scheduled_date: Optional[date] = None
    estimated_hours: Optional[float] = None
    status: Optional[str] = None
    currency: Optional[str] = None
    notes: Optional[str] = None
    customer_signature_url: Optional[str] = None

class PartIn(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float = 0.0
    product_id: Optional[str] = None

class LabourIn(BaseModel):
    staff_name: Optional[str] = None
    staff_id: Optional[str] = None
    hours: float
    hourly_rate: float = 0.0
    notes: Optional[str] = None

class PhotoIn(BaseModel):
    url: str
    caption: Optional[str] = None
    photo_type: str = "before"  # before | after

class SignatureIn(BaseModel):
    signature_url: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _card_dict(c: JobCard) -> dict:
    return {
        "id": str(c.id),
        "org_id": str(c.org_id),
        "job_number": c.job_number,
        "customer_id": str(c.customer_id) if c.customer_id else None,
        "assigned_staff_id": str(c.assigned_staff_id) if c.assigned_staff_id else None,
        "title": c.title,
        "description": c.description,
        "site_address": c.site_address,
        "scheduled_date": c.scheduled_date.isoformat() if c.scheduled_date else None,
        "estimated_hours": float(c.estimated_hours) if c.estimated_hours else None,
        "status": c.status,
        "customer_signature_url": c.customer_signature_url,
        "signed_at": c.signed_at.isoformat() if c.signed_at else None,
        "invoice_id": str(c.invoice_id) if c.invoice_id else None,
        "currency": c.currency,
        "notes": c.notes,
        "created_at": c.created_at.isoformat(),
        "parts": [
            {"id": str(p.id), "description": p.description, "quantity": float(p.quantity),
             "unit_price": float(p.unit_price), "product_id": str(p.product_id) if p.product_id else None}
            for p in (c.parts or [])
        ],
        "labour": [
            {"id": str(l.id), "staff_name": l.staff_name, "staff_id": str(l.staff_id) if l.staff_id else None,
             "hours": float(l.hours), "hourly_rate": float(l.hourly_rate), "notes": l.notes}
            for l in (c.labour or [])
        ],
        "photos": [
            {"id": str(ph.id), "url": ph.url, "caption": ph.caption, "photo_type": ph.photo_type}
            for ph in (c.photos or [])
        ],
    }


async def _next_job_number(org_id: uuid.UUID, db: AsyncSession) -> str:
    row = await db.execute(
        text("SELECT MAX(job_number) FROM job_cards WHERE org_id = :oid"),
        {"oid": str(org_id)},
    )
    last = row.scalar()
    if last:
        try:
            seq = int(last.split("-")[-1]) + 1
        except (ValueError, AttributeError):
            seq = 1
    else:
        seq = 1
    return f"JOB-{seq:05d}"


async def _next_invoice_number(org_id: uuid.UUID, db: AsyncSession) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"INV-{year}-"
    row = await db.execute(
        text("SELECT MAX(invoice_number) FROM invoices WHERE org_id = :oid AND invoice_number LIKE :prefix"),
        {"oid": str(org_id), "prefix": f"{prefix}%"},
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


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/api/job-cards")
async def list_job_cards(
    status: Optional[str] = None,
    customer_id: Optional[str] = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        user, member = await get_current_member(request, db)
        org_id = member.org_id
        q = select(JobCard).where(JobCard.org_id == org_id)
        if status:
            q = q.where(JobCard.status == status)
        if customer_id:
            q = q.where(JobCard.customer_id == uuid.UUID(customer_id))
        q = q.order_by(JobCard.created_at.desc())
        rows = (await db.execute(q)).scalars().all()
        for c in rows:
            await db.refresh(c, ["parts", "labour", "photos"])
        # Enrich with customer_name
        cids = {c.customer_id for c in rows if c.customer_id}
        cust_map: dict = {}
        if cids:
            cr = await db.execute(select(Customer).where(Customer.id.in_(cids)))
            for cust in cr.scalars().all():
                cust_map[cust.id] = cust.company_name
        return [{**_card_dict(c), "customer_name": cust_map.get(c.customer_id)} for c in rows]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_job_cards failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/job-cards", status_code=201)
async def create_job_card(body: JobCardIn, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        user, member = await get_current_member(request, db)
        org_id = member.org_id
        job_number = await _next_job_number(org_id, db)
        c = JobCard(
            id=uuid.uuid4(), org_id=org_id, job_number=job_number,
            customer_id=uuid.UUID(body.customer_id) if body.customer_id else None,
            assigned_staff_id=uuid.UUID(body.assigned_staff_id) if body.assigned_staff_id else None,
            title=body.title, description=body.description,
            site_address=body.site_address,
            scheduled_date=body.scheduled_date,
            estimated_hours=Decimal(str(body.estimated_hours)) if body.estimated_hours is not None else None,
            currency=body.currency, notes=body.notes,
        )
        db.add(c)
        await db.commit()
        await db.refresh(c, ["parts", "labour", "photos"])
        return _card_dict(c)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"create_job_card failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/job-cards/{card_id}")
async def get_job_card(card_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        user, member = await get_current_member(request, db)
        org_id = member.org_id
        c = (await db.execute(select(JobCard).where(JobCard.id == uuid.UUID(card_id), JobCard.org_id == org_id))).scalar_one_or_none()
        if not c:
            raise HTTPException(status_code=404, detail="Job card not found")
        await db.refresh(c, ["parts", "labour", "photos"])
        cust_name = None
        if c.customer_id:
            cust = (await db.execute(select(Customer).where(Customer.id == c.customer_id))).scalar_one_or_none()
            cust_name = cust.company_name if cust else None
        return {**_card_dict(c), "customer_name": cust_name}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_job_card failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/job-cards/{card_id}")
async def update_job_card(card_id: str, body: JobCardPatch, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        user, member = await get_current_member(request, db)
        org_id = member.org_id
        c = (await db.execute(select(JobCard).where(JobCard.id == uuid.UUID(card_id), JobCard.org_id == org_id))).scalar_one_or_none()
        if not c:
            raise HTTPException(status_code=404, detail="Job card not found")
        updates = body.model_dump(exclude_unset=True)
        for field, val in updates.items():
            if field in ("customer_id", "assigned_staff_id"):
                setattr(c, field, uuid.UUID(val) if val else None)
            elif field == "estimated_hours":
                setattr(c, field, Decimal(str(val)) if val is not None else None)
            else:
                setattr(c, field, val)
        await db.commit()
        await db.refresh(c, ["parts", "labour", "photos"])
        return _card_dict(c)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"update_job_card failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Parts ──────────────────────────────────────────────────────────────────────

@router.post("/api/job-cards/{card_id}/parts", status_code=201)
async def add_part(card_id: str, body: PartIn, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        user, member = await get_current_member(request, db)
        org_id = member.org_id
        c = (await db.execute(select(JobCard).where(JobCard.id == uuid.UUID(card_id), JobCard.org_id == org_id))).scalar_one_or_none()
        if not c:
            raise HTTPException(status_code=404, detail="Job card not found")
        p = JobCardPart(
            id=uuid.uuid4(), job_card_id=c.id,
            product_id=uuid.UUID(body.product_id) if body.product_id else None,
            description=body.description,
            quantity=Decimal(str(body.quantity)), unit_price=Decimal(str(body.unit_price)),
        )
        db.add(p)
        await db.commit()
        await db.refresh(c, ["parts", "labour", "photos"])
        return _card_dict(c)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"add_part failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/job-cards/{card_id}/parts/{part_id}", status_code=204)
async def delete_part(card_id: str, part_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        user, member = await get_current_member(request, db)
        org_id = member.org_id
        c = (await db.execute(select(JobCard).where(JobCard.id == uuid.UUID(card_id), JobCard.org_id == org_id))).scalar_one_or_none()
        if not c:
            raise HTTPException(status_code=404, detail="Job card not found")
        p = (await db.execute(select(JobCardPart).where(JobCardPart.id == uuid.UUID(part_id), JobCardPart.job_card_id == c.id))).scalar_one_or_none()
        if not p:
            raise HTTPException(status_code=404, detail="Part not found")
        await db.delete(p)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"delete_part failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Labour ─────────────────────────────────────────────────────────────────────

@router.post("/api/job-cards/{card_id}/labour", status_code=201)
async def add_labour(card_id: str, body: LabourIn, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        user, member = await get_current_member(request, db)
        org_id = member.org_id
        c = (await db.execute(select(JobCard).where(JobCard.id == uuid.UUID(card_id), JobCard.org_id == org_id))).scalar_one_or_none()
        if not c:
            raise HTTPException(status_code=404, detail="Job card not found")
        l = JobCardLabour(
            id=uuid.uuid4(), job_card_id=c.id,
            staff_id=uuid.UUID(body.staff_id) if body.staff_id else None,
            staff_name=body.staff_name, hours=Decimal(str(body.hours)),
            hourly_rate=Decimal(str(body.hourly_rate)), notes=body.notes,
        )
        db.add(l)
        await db.commit()
        await db.refresh(c, ["parts", "labour", "photos"])
        return _card_dict(c)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"add_labour failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/job-cards/{card_id}/labour/{labour_id}", status_code=204)
async def delete_labour(card_id: str, labour_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        user, member = await get_current_member(request, db)
        org_id = member.org_id
        c = (await db.execute(select(JobCard).where(JobCard.id == uuid.UUID(card_id), JobCard.org_id == org_id))).scalar_one_or_none()
        if not c:
            raise HTTPException(status_code=404, detail="Job card not found")
        l = (await db.execute(select(JobCardLabour).where(JobCardLabour.id == uuid.UUID(labour_id), JobCardLabour.job_card_id == c.id))).scalar_one_or_none()
        if not l:
            raise HTTPException(status_code=404, detail="Labour entry not found")
        await db.delete(l)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"delete_labour failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Photos ─────────────────────────────────────────────────────────────────────

@router.post("/api/job-cards/{card_id}/photos", status_code=201)
async def add_photo(card_id: str, body: PhotoIn, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        user, member = await get_current_member(request, db)
        org_id = member.org_id
        c = (await db.execute(select(JobCard).where(JobCard.id == uuid.UUID(card_id), JobCard.org_id == org_id))).scalar_one_or_none()
        if not c:
            raise HTTPException(status_code=404, detail="Job card not found")
        ph = JobCardPhoto(
            id=uuid.uuid4(), job_card_id=c.id, url=body.url,
            caption=body.caption, photo_type=body.photo_type,
        )
        db.add(ph)
        await db.commit()
        await db.refresh(c, ["parts", "labour", "photos"])
        return _card_dict(c)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"add_photo failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Signature ──────────────────────────────────────────────────────────────────

@router.post("/api/job-cards/{card_id}/sign")
async def sign_job_card(card_id: str, body: SignatureIn, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        user, member = await get_current_member(request, db)
        org_id = member.org_id
        c = (await db.execute(select(JobCard).where(JobCard.id == uuid.UUID(card_id), JobCard.org_id == org_id))).scalar_one_or_none()
        if not c:
            raise HTTPException(status_code=404, detail="Job card not found")
        c.customer_signature_url = body.signature_url
        c.signed_at = datetime.now(timezone.utc)
        if c.status == "in_progress":
            c.status = "completed"
        await db.commit()
        await db.refresh(c, ["parts", "labour", "photos"])
        return _card_dict(c)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"sign_job_card failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Convert to invoice ─────────────────────────────────────────────────────────

@router.post("/api/job-cards/{card_id}/invoice", status_code=201)
async def invoice_job_card(card_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Auto-generate a DRAFT invoice from parts + labour on a completed job card."""
    try:
        user, member = await get_current_member(request, db)
        org_id = member.org_id
        c = (await db.execute(select(JobCard).where(JobCard.id == uuid.UUID(card_id), JobCard.org_id == org_id))).scalar_one_or_none()
        if not c:
            raise HTTPException(status_code=404, detail="Job card not found")
        if c.status not in ("completed", "invoiced"):
            raise HTTPException(status_code=409, detail="Job must be completed before invoicing")
        if c.invoice_id:
            raise HTTPException(status_code=409, detail="Invoice already exists for this job")
        if not c.customer_id:
            raise HTTPException(status_code=422, detail="Job card has no customer — set one before invoicing")
        await db.refresh(c, ["parts", "labour", "photos"])
        inv_number = await _next_invoice_number(org_id, db)
        today = date.today()
        tax_rate = Decimal("25")
        # Build lines
        lines = []
        subtotal = Decimal("0")
        for p in c.parts:
            total = (p.quantity * p.unit_price).quantize(Decimal("0.01"))
            lines.append({"description": f"Part: {p.description}", "quantity": p.quantity, "unit_price": p.unit_price, "line_total": total})
            subtotal += total
        for l in c.labour:
            total = (l.hours * l.hourly_rate).quantize(Decimal("0.01"))
            name = l.staff_name or "Labour"
            lines.append({"description": f"Labour: {name} — {float(l.hours):.2f} hrs", "quantity": l.hours, "unit_price": l.hourly_rate, "line_total": total})
            subtotal += total
        vat = (subtotal * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
        total_val = subtotal + vat
        invoice = Invoice(
            id=uuid.uuid4(), org_id=org_id, customer_id=c.customer_id,
            invoice_number=inv_number, issue_date=today, due_date=today,
            subtotal=subtotal, vat_amount=vat, total_sek=total_val,
            notes=f"Job card {c.job_number}: {c.title}",
        )
        db.add(invoice)
        await db.flush()
        for ln in lines:
            db.add(InvoiceLineItem(
                id=uuid.uuid4(), invoice_id=invoice.id,
                description=ln["description"], quantity=ln["quantity"],
                unit_price=ln["unit_price"], tax_rate=tax_rate, line_total=ln["line_total"],
            ))
        c.invoice_id = invoice.id
        c.status = "invoiced"
        await db.commit()
        return {"invoice_id": str(invoice.id), "invoice_number": inv_number, "total_sek": float(total_val)}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log.error(f"invoice_job_card failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
