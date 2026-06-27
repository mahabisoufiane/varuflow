"""HR Employees router: profiles, contracts, emergency contacts."""
from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module, require_role
from .employee_contracts import EmployeeContract
from .models import EmployeeEmergencyContact, EmployeeProfile
from app.features.auth.organization import OrgRole
from app.features.bookings.models import Staff

log = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_module("hr"))])

# Manager-level guard for the sensitive sub-resources (profiles with decrypted
# national_id / bank_account, contracts, emergency contacts). Applied per-route
# so the plain employee LIST (GET /api/hr/employees) stays available to any
# HR-module member — the rostering / shift pages depend on it. Regular members
# get names + basic profile; only ADMIN+ sees PII and contracts.
_MANAGER_ONLY = [Depends(require_role(OrgRole.ADMIN))]


# ── Schemas ──────────────────────────────────────────────────────────────────

class ProfileUpsert(BaseModel):
    full_legal_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    department: Optional[str] = None
    status: Optional[str] = None
    reports_to_staff_id: Optional[uuid.UUID] = None
    job_title: Optional[str] = None
    employment_type: str = "full_time"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    national_id: Optional[str] = None
    bank_account: Optional[str] = None
    bank_name: Optional[str] = None
    address: Optional[str] = None


class ContractCreate(BaseModel):
    contract_type: str
    title: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    salary: Optional[Decimal] = None
    currency: str = "SEK"
    hours_per_week: Optional[Decimal] = None
    file_url: Optional[str] = None
    notes: Optional[str] = None
    probation_end_date: Optional[date] = None
    notice_period_days: Optional[int] = None


class ContractUpdate(BaseModel):
    contract_type: Optional[str] = None
    title: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    salary: Optional[Decimal] = None
    currency: Optional[str] = None
    hours_per_week: Optional[Decimal] = None
    file_url: Optional[str] = None
    notes: Optional[str] = None
    probation_end_date: Optional[date] = None
    notice_period_days: Optional[int] = None


class EmergencyContactCreate(BaseModel):
    name: str
    relationship: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class EmergencyContactUpdate(BaseModel):
    name: Optional[str] = None
    relationship: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row(obj: Any) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def _encrypt(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        from app.services.encryption import encrypt_pii
        return encrypt_pii(value)
    except Exception:
        return value


def _decrypt(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        from app.services.encryption import decrypt_pii
        return decrypt_pii(value)
    except Exception:
        return value


# ── Employees list ────────────────────────────────────────────────────────────

@router.get("/api/hr/employees")
async def list_employees(
    status: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        staff_rows = (await db.execute(
            select(Staff).where(Staff.org_id == org_id)
        )).scalars().all()
        profile_q = select(EmployeeProfile).where(EmployeeProfile.org_id == org_id)
        if status:
            profile_q = profile_q.where(EmployeeProfile.status == status)
        if department:
            profile_q = profile_q.where(EmployeeProfile.department == department)
        profiles = {
            str(p.staff_id): p
            for p in (await db.execute(profile_q)).scalars().all()
        }
        result = []
        for s in staff_rows:
            p = profiles.get(str(s.id))
            if (status or department) and p is None:
                continue
            result.append({
                "id": str(s.id),
                "name": s.name,
                "email": getattr(s, "email", None),
                "profile": _row(p) if p else None,
            })
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_employees failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Employee Profile ──────────────────────────────────────────────────────────

@router.get("/api/hr/employees/{staff_id}/profile", dependencies=_MANAGER_ONLY)
async def get_profile(
    staff_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(EmployeeProfile).where(
                and_(EmployeeProfile.org_id == org_id, EmployeeProfile.staff_id == staff_id)
            )
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Profile not found")
        data = _row(row)
        data["national_id"] = _decrypt(row.national_id)
        data["bank_account"] = _decrypt(row.bank_account)
        return data
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"get_profile failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/employees/{staff_id}/profile", dependencies=_MANAGER_ONLY)
async def upsert_profile(
    staff_id: uuid.UUID,
    body: ProfileUpsert,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(EmployeeProfile).where(
                and_(EmployeeProfile.org_id == org_id, EmployeeProfile.staff_id == staff_id)
            )
        )).scalar_one_or_none()
        if row is None:
            row = EmployeeProfile(id=uuid.uuid4(), org_id=org_id, staff_id=staff_id)
            db.add(row)
        for field, value in body.model_dump(exclude_unset=True).items():
            if field == "national_id":
                row.national_id = _encrypt(value)
            elif field == "bank_account":
                row.bank_account = _encrypt(value)
            else:
                setattr(row, field, value)
        await db.commit()
        await db.refresh(row)
        data = _row(row)
        data["national_id"] = _decrypt(row.national_id)
        data["bank_account"] = _decrypt(row.bank_account)
        return data
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"upsert_profile failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Contracts ─────────────────────────────────────────────────────────────────

@router.get("/api/hr/employees/{staff_id}/contracts", dependencies=_MANAGER_ONLY)
async def list_contracts(
    staff_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        rows = (await db.execute(
            select(EmployeeContract).where(
                and_(EmployeeContract.org_id == org_id, EmployeeContract.staff_id == staff_id)
            )
        )).scalars().all()
        return [_row(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_contracts failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/employees/{staff_id}/contracts", status_code=201, dependencies=_MANAGER_ONLY)
async def create_contract(
    staff_id: uuid.UUID,
    body: ContractCreate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = EmployeeContract(id=uuid.uuid4(), org_id=org_id, staff_id=staff_id, **body.model_dump())
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_contract failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/hr/employees/{staff_id}/contracts/{contract_id}", dependencies=_MANAGER_ONLY)
async def update_contract(
    staff_id: uuid.UUID,
    contract_id: uuid.UUID,
    body: ContractUpdate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(EmployeeContract).where(
                and_(
                    EmployeeContract.org_id == org_id,
                    EmployeeContract.staff_id == staff_id,
                    EmployeeContract.id == contract_id,
                )
            )
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Contract not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        await db.commit()
        await db.refresh(row)
        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"update_contract failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/hr/employees/{staff_id}/contracts/{contract_id}", status_code=204, dependencies=_MANAGER_ONLY)
async def delete_contract(
    staff_id: uuid.UUID,
    contract_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(EmployeeContract).where(
                and_(
                    EmployeeContract.org_id == org_id,
                    EmployeeContract.staff_id == staff_id,
                    EmployeeContract.id == contract_id,
                )
            )
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Contract not found")
        await db.delete(row)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"delete_contract failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Emergency Contacts ────────────────────────────────────────────────────────

@router.get("/api/hr/employees/{staff_id}/emergency-contacts", dependencies=_MANAGER_ONLY)
async def list_emergency_contacts(
    staff_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        rows = (await db.execute(
            select(EmployeeEmergencyContact).where(
                and_(EmployeeEmergencyContact.org_id == org_id, EmployeeEmergencyContact.staff_id == staff_id)
            )
        )).scalars().all()
        return [_row(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"list_emergency_contacts failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/employees/{staff_id}/emergency-contacts", status_code=201, dependencies=_MANAGER_ONLY)
async def create_emergency_contact(
    staff_id: uuid.UUID,
    body: EmergencyContactCreate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = EmployeeEmergencyContact(id=uuid.uuid4(), org_id=org_id, staff_id=staff_id, **body.model_dump())
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"create_emergency_contact failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/hr/employees/{staff_id}/emergency-contacts/{contact_id}", dependencies=_MANAGER_ONLY)
async def update_emergency_contact(
    staff_id: uuid.UUID,
    contact_id: uuid.UUID,
    body: EmergencyContactUpdate,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(EmployeeEmergencyContact).where(
                and_(
                    EmployeeEmergencyContact.org_id == org_id,
                    EmployeeEmergencyContact.staff_id == staff_id,
                    EmployeeEmergencyContact.id == contact_id,
                )
            )
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Emergency contact not found")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        await db.commit()
        await db.refresh(row)
        return _row(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"update_emergency_contact failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/hr/employees/{staff_id}/emergency-contacts/{contact_id}", status_code=204, dependencies=_MANAGER_ONLY)
async def delete_emergency_contact(
    staff_id: uuid.UUID,
    contact_id: uuid.UUID,
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        row = (await db.execute(
            select(EmployeeEmergencyContact).where(
                and_(
                    EmployeeEmergencyContact.org_id == org_id,
                    EmployeeEmergencyContact.staff_id == staff_id,
                    EmployeeEmergencyContact.id == contact_id,
                )
            )
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Emergency contact not found")
        await db.delete(row)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"delete_emergency_contact failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
