from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.leads import Lead, LeadScoreEvent
from app.models.invoicing import Customer
from app.models.crm import Deal

log = logging.getLogger(__name__)
router = APIRouter(tags=["leads"], dependencies=[Depends(require_module("crm"))])

LEAD_STATUSES = ["new", "contacted", "qualified", "converted", "dead"]

SCORE_POINTS: dict[str, int] = {
    "email_opened":    5,
    "link_clicked":   10,
    "page_visit":     10,
    "form_submitted": 20,
    "meeting_booked": 30,
    "demo_completed": 40,
}


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class LeadCreate(BaseModel):
    name: str
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    assigned_to: Optional[str] = None


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    assigned_to: Optional[str] = None
    last_contacted_at: Optional[datetime] = None


class ConvertIn(BaseModel):
    deal_title: Optional[str] = None
    deal_value: Optional[float] = None


class ScoreIn(BaseModel):
    event_type: str
    note: Optional[str] = None


class CsvRowIn(BaseModel):
    name: str
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _lead_out(lead: Lead) -> dict:
    return {
        "id": str(lead.id),
        "org_id": str(lead.org_id),
        "name": lead.name,
        "company": lead.company,
        "email": lead.email,
        "phone": lead.phone,
        "source": lead.source,
        "status": lead.status,
        "assigned_to": str(lead.assigned_to) if lead.assigned_to else None,
        "score": lead.score,
        "notes": lead.notes,
        "lead_form_submission_id": str(lead.lead_form_submission_id) if lead.lead_form_submission_id else None,
        "converted_customer_id": str(lead.converted_customer_id) if lead.converted_customer_id else None,
        "converted_deal_id": str(lead.converted_deal_id) if lead.converted_deal_id else None,
        "converted_at": lead.converted_at.isoformat() if lead.converted_at else None,
        "last_contacted_at": lead.last_contacted_at.isoformat() if lead.last_contacted_at else None,
        "created_at": lead.created_at.isoformat(),
        "updated_at": lead.updated_at.isoformat(),
        "score_events": [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "points": e.points,
                "note": e.note,
                "created_at": e.created_at.isoformat(),
            }
            for e in (lead.score_events or [])
        ],
    }


# ── List / Create ─────────────────────────────────────────────────────────────

@router.get("/api/leads")
async def list_leads(
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        q = select(Lead).where(Lead.org_id == org_id)
        if status:
            q = q.where(Lead.status == status)
        if source:
            q = q.where(Lead.source == source)
        if assigned_to:
            q = q.where(Lead.assigned_to == assigned_to)
        if search:
            term = f"%{search}%"
            q = q.where(or_(
                Lead.name.ilike(term),
                Lead.company.ilike(term),
                Lead.email.ilike(term),
            ))
        q = q.order_by(Lead.created_at.desc()).limit(limit).offset(offset)
        rows = (await db.execute(q)).scalars().all()
        return [_lead_out(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_leads failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/leads", status_code=201)
async def create_lead(
    body: LeadCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        duplicate = None
        if body.email:
            dup = (await db.execute(
                select(Lead).where(Lead.org_id == org_id, Lead.email == body.email)
            )).scalars().first()
            if dup:
                duplicate = {"id": str(dup.id), "name": dup.name}

        lead = Lead(
            org_id=org_id,
            name=body.name.strip(),
            company=body.company,
            email=body.email,
            phone=body.phone,
            source=body.source,
            notes=body.notes,
            assigned_to=UUID(body.assigned_to) if body.assigned_to else None,
        )
        db.add(lead)
        await db.commit()
        await db.refresh(lead)
        result = _lead_out(lead)
        if duplicate:
            result["duplicate_warning"] = duplicate
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_lead failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Detail / Update / Delete ──────────────────────────────────────────────────

@router.get("/api/leads/{lead_id}")
async def get_lead(
    lead_id: str,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        lead = (await db.execute(
            select(Lead).where(Lead.id == lead_id, Lead.org_id == org_id)
        )).scalars().first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        return _lead_out(lead)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_lead failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/leads/{lead_id}")
async def update_lead(
    lead_id: str,
    body: LeadUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        lead = (await db.execute(
            select(Lead).where(Lead.id == lead_id, Lead.org_id == org_id)
        )).scalars().first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        if body.name is not None:
            lead.name = body.name.strip()
        if body.company is not None:
            lead.company = body.company
        if body.email is not None:
            lead.email = body.email
        if body.phone is not None:
            lead.phone = body.phone
        if body.source is not None:
            lead.source = body.source
        if body.status is not None:
            if body.status not in LEAD_STATUSES:
                raise HTTPException(status_code=422, detail=f"Invalid status: {body.status}")
            lead.status = body.status
        if body.notes is not None:
            lead.notes = body.notes
        if body.assigned_to is not None:
            lead.assigned_to = UUID(body.assigned_to) if body.assigned_to else None
        if body.last_contacted_at is not None:
            lead.last_contacted_at = body.last_contacted_at

        lead.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(lead)
        return _lead_out(lead)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_lead failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/leads/{lead_id}", status_code=204)
async def delete_lead(
    lead_id: str,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        lead = (await db.execute(
            select(Lead).where(Lead.id == lead_id, Lead.org_id == org_id)
        )).scalars().first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        await db.delete(lead)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_lead failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Convert to Customer + Deal ────────────────────────────────────────────────

@router.post("/api/leads/{lead_id}/convert")
async def convert_lead(
    lead_id: str,
    body: ConvertIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        lead = (await db.execute(
            select(Lead).where(Lead.id == lead_id, Lead.org_id == org_id)
        )).scalars().first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        if lead.status == "converted":
            raise HTTPException(status_code=409, detail="Lead already converted")

        now = datetime.now(timezone.utc)

        # Create Customer
        customer = Customer(
            org_id=org_id,
            name=lead.company or lead.name,
            contact_name=lead.name,
            email=lead.email,
            phone=lead.phone,
        )
        db.add(customer)
        await db.flush()

        # Create Deal
        deal_title = body.deal_title or f"Deal – {lead.company or lead.name}"
        deal = Deal(
            org_id=org_id,
            customer_id=customer.id,
            title=deal_title,
            stage="lead",
            value=body.deal_value,
        )
        db.add(deal)
        await db.flush()

        # Mark lead converted
        lead.status = "converted"
        lead.converted_customer_id = customer.id
        lead.converted_deal_id = deal.id
        lead.converted_at = now
        lead.updated_at = now

        await db.commit()
        return {
            "customer_id": str(customer.id),
            "deal_id": str(deal.id),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("convert_lead failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Score event ───────────────────────────────────────────────────────────────

@router.post("/api/leads/{lead_id}/score")
async def add_score_event(
    lead_id: str,
    body: ScoreIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        lead = (await db.execute(
            select(Lead).where(Lead.id == lead_id, Lead.org_id == org_id)
        )).scalars().first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        points = SCORE_POINTS.get(body.event_type, 5)
        event = LeadScoreEvent(
            lead_id=lead.id,
            org_id=org_id,
            event_type=body.event_type,
            points=points,
            note=body.note,
        )
        db.add(event)
        lead.score = (lead.score or 0) + points
        lead.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return {"score": lead.score, "points_added": points}
    except HTTPException:
        raise
    except Exception as e:
        log.error("add_score_event failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── CSV import ────────────────────────────────────────────────────────────────

@router.post("/api/leads/import-csv", status_code=201)
async def import_leads_csv(
    rows: List[CsvRowIn],
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = ctx[1]
        created = 0
        skipped = 0
        duplicates: list[dict] = []

        for row in rows:
            if row.email:
                existing = (await db.execute(
                    select(Lead).where(Lead.org_id == org_id, Lead.email == row.email)
                )).scalars().first()
                if existing:
                    skipped += 1
                    duplicates.append({"email": row.email, "existing_id": str(existing.id)})
                    continue

            lead = Lead(
                org_id=org_id,
                name=row.name.strip(),
                company=row.company,
                email=row.email,
                phone=row.phone,
                source=row.source,
                notes=row.notes,
            )
            db.add(lead)
            created += 1

        await db.commit()
        return {"created": created, "skipped": skipped, "duplicates": duplicates}
    except HTTPException:
        raise
    except Exception as e:
        log.error("import_leads_csv failed: %s", e, extra={"org_id": str(ctx[1])})
        raise HTTPException(status_code=500, detail="Internal server error")
