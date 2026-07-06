"""GDPR Consent Management router.

Tracks per-customer consent for marketing, data processing, cookies, etc.
Also manages Data Subject Access Requests (DSARs).

Endpoints:
  GET    /api/gdpr/consent                  List consents for org (filter by customer/type/status)
  POST   /api/gdpr/consent                  Record a new consent
  GET    /api/gdpr/consent/{customer_id}    All consents for a specific customer
  DELETE /api/gdpr/consent/{id}             Withdraw a consent
  GET    /api/gdpr/consent/expiring         Consents older than 2 years needing revalidation

  GET    /api/gdpr/dsar                     List DSARs
  POST   /api/gdpr/dsar                     Submit a new DSAR
  GET    /api/gdpr/dsar/{id}                DSAR detail
  PATCH  /api/gdpr/dsar/{id}                Update DSAR status / notes
  GET    /api/gdpr/dsar/{id}/package        Download DSAR response package (JSON)

  GET    /api/gdpr/consent-summary          Counts per consent type / status
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .consent import ConsentAuditLog, ConsentRecord, DsarRequest
from app.features.invoicing.models import Customer, Invoice, Payment
from app.middleware.plan_check import require_module

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gdpr", tags=["gdpr_consent"], dependencies=[Depends(require_module("settings"))])


CONSENT_TYPES = {
    "marketing_email", "sms_marketing", "whatsapp",
    "data_processing", "analytics_cookies",
}
DSAR_TYPES = {"access", "deletion", "rectification", "portability", "restriction"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_org(member) -> uuid.UUID:
    # Accepts the OrganizationMember ORM object (tuple-unpacked ctx) or the
    # dict-style MemberCtx — subscripting the ORM object raised TypeError.
    org = getattr(member, "org_id", None)
    if org is None:
        org = member["org_id"]
    return org if isinstance(org, uuid.UUID) else uuid.UUID(str(org))


async def _write_log(
    db: AsyncSession,
    org_id: uuid.UUID,
    event_type: str,
    customer_id: uuid.UUID | None = None,
    consent_record_id: uuid.UUID | None = None,
    consent_type: str | None = None,
    actor: str | None = None,
    ip_address: str | None = None,
    extra: dict | None = None,
) -> None:
    entry = ConsentAuditLog(
        org_id=org_id,
        customer_id=customer_id,
        consent_record_id=consent_record_id,
        event_type=event_type,
        consent_type=consent_type,
        actor=actor,
        ip_address=ip_address,
        extra=extra,
    )
    db.add(entry)


# ── Schemas ───────────────────────────────────────────────────────────────────

class ConsentIn(BaseModel):
    customer_id: str
    consent_type: str
    collected_via: str = "staff"  # staff / portal / form / import
    ip_address: Optional[str] = None
    notes: Optional[str] = None
    expires_in_days: Optional[int] = 730  # default 2 years


class ConsentOut(BaseModel):
    id: str
    customer_id: str
    consent_type: str
    status: str
    collected_via: str
    notes: Optional[str]
    consented_at: str
    expires_at: Optional[str]


class DsarIn(BaseModel):
    customer_id: Optional[str] = None
    request_type: str = "access"
    requester_name: str
    requester_email: str
    description: Optional[str] = None


class DsarPatchIn(BaseModel):
    status: Optional[str] = None
    response_notes: Optional[str] = None


class DsarOut(BaseModel):
    id: str
    customer_id: Optional[str]
    request_type: str
    requester_name: str
    requester_email: str
    description: Optional[str]
    status: str
    response_notes: Optional[str]
    due_at: Optional[str]
    completed_at: Optional[str]
    created_at: str


def _consent_out(c: ConsentRecord) -> ConsentOut:
    return ConsentOut(
        id=str(c.id),
        customer_id=str(c.customer_id),
        consent_type=c.consent_type,
        status=c.status,
        collected_via=c.collected_via,
        notes=c.notes,
        consented_at=c.consented_at.isoformat() if c.consented_at else "",
        expires_at=c.expires_at.isoformat() if c.expires_at else None,
    )


def _dsar_out(d: DsarRequest) -> DsarOut:
    return DsarOut(
        id=str(d.id),
        customer_id=str(d.customer_id) if d.customer_id else None,
        request_type=d.request_type,
        requester_name=d.requester_name,
        requester_email=d.requester_email,
        description=d.description,
        status=d.status,
        response_notes=d.response_notes,
        due_at=d.due_at.isoformat() if d.due_at else None,
        completed_at=d.completed_at.isoformat() if d.completed_at else None,
        created_at=d.created_at.isoformat(),
    )


# ── Consent endpoints ─────────────────────────────────────────────────────────

@router.get("/consent-summary")
async def consent_summary(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Counts per consent type and status — for dashboard widgets."""
    _, member = ctx
    org_id = _get_org(member)
    try:
        rows = await db.execute(
            select(ConsentRecord.consent_type, ConsentRecord.status, func.count(ConsentRecord.id))
            .where(ConsentRecord.org_id == org_id)
            .group_by(ConsentRecord.consent_type, ConsentRecord.status)
        )
        breakdown = [{"consent_type": r[0], "status": r[1], "count": r[2]} for r in rows]
        return {"breakdown": breakdown}
    except Exception as e:
        log.error("consent_summary failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/consent/expiring")
async def expiring_consents(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return consents that expire within the next 30 days or have already expired."""
    _, member = ctx
    org_id = _get_org(member)
    try:
        cutoff = _now() + timedelta(days=30)
        rows = await db.execute(
            select(ConsentRecord)
            .where(
                ConsentRecord.org_id == org_id,
                ConsentRecord.status == "given",
                ConsentRecord.expires_at <= cutoff,
            )
            .order_by(ConsentRecord.expires_at.asc())
            .limit(200)
        )
        records = rows.scalars().all()
        return {"items": [_consent_out(r) for r in records]}
    except Exception as e:
        log.error("expiring_consents failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/consent/{customer_id}")
async def get_customer_consents(
    customer_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """All consent records for a specific customer."""
    _, member = ctx
    org_id = _get_org(member)
    try:
        # Verify customer belongs to org
        cust = await db.execute(
            select(Customer).where(Customer.id == customer_id, Customer.org_id == org_id)
        )
        if not cust.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Customer not found")

        rows = await db.execute(
            select(ConsentRecord)
            .where(ConsentRecord.org_id == org_id, ConsentRecord.customer_id == customer_id)
            .order_by(ConsentRecord.consented_at.desc())
        )
        records = rows.scalars().all()
        return {"items": [_consent_out(r) for r in records]}
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_customer_consents failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/consent")
async def list_consents(
    consent_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of consent records for the org."""
    _, member = ctx
    org_id = _get_org(member)
    try:
        q = select(ConsentRecord).where(ConsentRecord.org_id == org_id)
        if consent_type:
            q = q.where(ConsentRecord.consent_type == consent_type)
        if status:
            q = q.where(ConsentRecord.status == status)
        offset = (page - 1) * limit
        rows = await db.execute(q.order_by(ConsentRecord.consented_at.desc()).limit(limit).offset(offset))
        records = rows.scalars().all()

        count_q = select(func.count(ConsentRecord.id)).where(ConsentRecord.org_id == org_id)
        if consent_type:
            count_q = count_q.where(ConsentRecord.consent_type == consent_type)
        if status:
            count_q = count_q.where(ConsentRecord.status == status)
        total = (await db.execute(count_q)).scalar_one() or 0

        return {"items": [_consent_out(r) for r in records], "total": total}
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_consents failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/consent", status_code=201)
async def record_consent(
    body: ConsentIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    org_id = _get_org(member)
    try:
        if body.consent_type not in CONSENT_TYPES:
            raise HTTPException(status_code=422, detail=f"Unknown consent_type. Valid: {sorted(CONSENT_TYPES)}")

        customer_id = uuid.UUID(body.customer_id)
        # Verify customer belongs to org
        cust = await db.execute(
            select(Customer).where(Customer.id == customer_id, Customer.org_id == org_id)
        )
        if not cust.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Customer not found")

        expires_at = None
        if body.expires_in_days:
            expires_at = _now() + timedelta(days=body.expires_in_days)

        record = ConsentRecord(
            org_id=org_id,
            customer_id=customer_id,
            consent_type=body.consent_type,
            status="given",
            collected_via=body.collected_via,
            ip_address=body.ip_address,
            notes=body.notes,
            expires_at=expires_at,
        )
        db.add(record)
        await db.flush()

        await _write_log(
            db, org_id,
            event_type="consent_given",
            customer_id=customer_id,
            consent_record_id=record.id,
            consent_type=body.consent_type,
            actor=str(member.get("email", "staff")),
            ip_address=body.ip_address,
        )
        await db.commit()
        await db.refresh(record)
        return _consent_out(record)
    except HTTPException:
        raise
    except Exception as e:
        log.error("record_consent failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/consent/{consent_id}", status_code=204)
async def withdraw_consent(
    consent_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Withdraw a previously given consent (marks as withdrawn, does NOT delete)."""
    _, member = ctx
    org_id = _get_org(member)
    try:
        row = await db.execute(
            select(ConsentRecord).where(ConsentRecord.id == consent_id, ConsentRecord.org_id == org_id)
        )
        record = row.scalar_one_or_none()
        if not record:
            raise HTTPException(status_code=404, detail="Consent record not found")
        if record.status == "withdrawn":
            raise HTTPException(status_code=409, detail="Consent already withdrawn")

        record.status = "withdrawn"
        await _write_log(
            db, org_id,
            event_type="consent_withdrawn",
            customer_id=record.customer_id,
            consent_record_id=record.id,
            consent_type=record.consent_type,
            actor=str(member.get("email", "staff")),
        )
        await db.commit()
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        log.error("withdraw_consent failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── DSAR endpoints ────────────────────────────────────────────────────────────

@router.get("/dsar")
async def list_dsar(
    status: Optional[str] = Query(None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    org_id = _get_org(member)
    try:
        q = select(DsarRequest).where(DsarRequest.org_id == org_id)
        if status:
            q = q.where(DsarRequest.status == status)
        rows = await db.execute(q.order_by(DsarRequest.created_at.desc()).limit(200))
        items = rows.scalars().all()
        return {"items": [_dsar_out(d) for d in items]}
    except Exception as e:
        log.error("list_dsar failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/dsar", status_code=201)
async def create_dsar(
    body: DsarIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    org_id = _get_org(member)
    try:
        if body.request_type not in DSAR_TYPES:
            raise HTTPException(status_code=422, detail=f"Unknown request_type. Valid: {sorted(DSAR_TYPES)}")

        customer_id = uuid.UUID(body.customer_id) if body.customer_id else None
        # GDPR requires response within 30 days (Art. 12)
        due_at = _now() + timedelta(days=30)

        dsar = DsarRequest(
            org_id=org_id,
            customer_id=customer_id,
            request_type=body.request_type,
            requester_name=body.requester_name,
            requester_email=body.requester_email,
            description=body.description,
            status="pending",
            due_at=due_at,
        )
        db.add(dsar)
        await db.flush()

        await _write_log(
            db, org_id,
            event_type="dsar_submitted",
            customer_id=customer_id,
            actor=body.requester_email,
            extra={"request_type": body.request_type},
        )
        await db.commit()
        await db.refresh(dsar)
        return _dsar_out(dsar)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_dsar failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/dsar/{dsar_id}")
async def get_dsar(
    dsar_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    org_id = _get_org(member)
    try:
        row = await db.execute(
            select(DsarRequest).where(DsarRequest.id == dsar_id, DsarRequest.org_id == org_id)
        )
        dsar = row.scalar_one_or_none()
        if not dsar:
            raise HTTPException(status_code=404, detail="DSAR not found")
        return _dsar_out(dsar)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_dsar failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/dsar/{dsar_id}")
async def update_dsar(
    dsar_id: uuid.UUID,
    body: DsarPatchIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    org_id = _get_org(member)
    try:
        row = await db.execute(
            select(DsarRequest).where(DsarRequest.id == dsar_id, DsarRequest.org_id == org_id)
        )
        dsar = row.scalar_one_or_none()
        if not dsar:
            raise HTTPException(status_code=404, detail="DSAR not found")

        if body.status:
            dsar.status = body.status
            if body.status == "completed":
                dsar.completed_at = _now()
                await _write_log(db, org_id, "dsar_completed", customer_id=dsar.customer_id,
                                 extra={"dsar_id": str(dsar_id)})
        if body.response_notes is not None:
            dsar.response_notes = body.response_notes

        await db.commit()
        await db.refresh(dsar)
        return _dsar_out(dsar)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_dsar failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/dsar/{dsar_id}/package")
async def download_dsar_package(
    dsar_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Compile all data held on the subject and return as JSON download."""
    _, member = ctx
    org_id = _get_org(member)
    try:
        row = await db.execute(
            select(DsarRequest).where(DsarRequest.id == dsar_id, DsarRequest.org_id == org_id)
        )
        dsar = row.scalar_one_or_none()
        if not dsar:
            raise HTTPException(status_code=404, detail="DSAR not found")

        package: dict = {
            "dsar_id": str(dsar_id),
            "request_type": dsar.request_type,
            "requester_name": dsar.requester_name,
            "requester_email": dsar.requester_email,
            "generated_at": _now().isoformat(),
        }

        if dsar.customer_id:
            customer_id = dsar.customer_id
            # Fetch customer data
            cust_row = await db.execute(
                select(Customer).where(Customer.id == customer_id, Customer.org_id == org_id)
            )
            cust = cust_row.scalar_one_or_none()
            if cust:
                package["customer"] = {
                    "id": str(cust.id),
                    "company_name": cust.company_name,
                    "email": cust.email,
                    "phone": cust.phone,
                    "address": cust.address,
                    "org_number": cust.org_number,
                }

            # Fetch invoices
            inv_rows = await db.execute(
                select(Invoice).where(Invoice.customer_id == customer_id, Invoice.org_id == org_id)
            )
            invoices = inv_rows.scalars().all()
            package["invoices"] = [
                {
                    "id": str(i.id),
                    "invoice_number": i.invoice_number,
                    "issue_date": str(i.issue_date),
                    "total_sek": str(i.total_sek),
                    "status": str(i.status),
                }
                for i in invoices
            ]

            # Fetch consent records
            consent_rows = await db.execute(
                select(ConsentRecord).where(
                    ConsentRecord.customer_id == customer_id,
                    ConsentRecord.org_id == org_id,
                )
            )
            consents = consent_rows.scalars().all()
            package["consents"] = [
                {
                    "consent_type": c.consent_type,
                    "status": c.status,
                    "collected_via": c.collected_via,
                    "consented_at": c.consented_at.isoformat() if c.consented_at else None,
                }
                for c in consents
            ]

        body_bytes = json.dumps(package, indent=2, default=str).encode("utf-8")
        filename = f"dsar-{dsar_id}-{_now().strftime('%Y%m%d')}.json"
        await _write_log(db, org_id, "dsar_package_downloaded",
                         customer_id=dsar.customer_id,
                         extra={"dsar_id": str(dsar_id)})
        await db.commit()

        return Response(
            content=body_bytes,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("dsar_package failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
