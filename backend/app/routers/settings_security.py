"""Security & MFA status endpoint for the Settings → Security page (Item 23).

Read-only helper the frontend hits to render the enforcement banner and
the "MFA enabled / enforced since" panel. All mutations go through the
existing ``/api/auth/mfa/*`` endpoints — we deliberately do not mirror
them here so the audit surface stays centralised in ``local_auth``.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.auth import AuthUser
from app.models.organization import OrgPlan, OrgRole, OrganizationMember, Organization
from app.services.mfa_enforcement import (
    MFA_MEMBER_THRESHOLD,
    is_mfa_required_for_owner,
)

router = APIRouter(prefix="/api/settings/security", tags=["settings-security"])


class SecurityStatus(BaseModel):
    role: OrgRole
    plan: OrgPlan
    member_count: int
    mfa_enabled: bool
    mfa_required: bool
    mfa_enforced_at: datetime | None
    member_threshold: int


@router.get("/status", response_model=SecurityStatus)
async def security_status(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> SecurityStatus:
    current_user, member = ctx
    org = await db.get(Organization, member.org_id)

    member_count = await db.scalar(
        select(func.count())
        .select_from(OrganizationMember)
        .where(OrganizationMember.org_id == member.org_id)
    ) or 0
    member_count = int(member_count)

    # Only owners are gated today — non-owners always see ``mfa_required=False``
    # so the UI renders an informational panel rather than a call-to-action.
    mfa_required = (
        member.role == OrgRole.OWNER
        and org is not None
        and is_mfa_required_for_owner(org.plan, member_count)
    )

    user_id = current_user.get("user_id")
    auth_user = await db.get(AuthUser, user_id) if user_id else None

    return SecurityStatus(
        role=member.role,
        plan=org.plan if org else OrgPlan.FREE,
        member_count=member_count,
        mfa_enabled=bool(auth_user and auth_user.totp_enabled),
        mfa_required=mfa_required,
        mfa_enforced_at=(auth_user.totp_enforced_at if auth_user else None),
        member_threshold=MFA_MEMBER_THRESHOLD,
    )


# --------------------------------------------------------------------------- #
# IP allowlist CRUD (Item 25 / migration v45)
# --------------------------------------------------------------------------- #
import uuid as _uuid
from fastapi import HTTPException, Request, status as _status
from app.models.organization import OrgIpAllowlistEntry
from app.services.audit import log_action
from app.services.ip_allowlist import parse_cidr


class IpAllowlistEntryOut(BaseModel):
    id: _uuid.UUID
    cidr: str
    label: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class IpAllowlistCreate(BaseModel):
    cidr: str
    label: str | None = None


def _require_owner(member: OrganizationMember) -> None:
    """Only the owner can edit the allowlist — misconfigured entries
    lock the org out, so this is a data-controller decision."""
    if member.role != OrgRole.OWNER:
        raise HTTPException(
            status_code=_status.HTTP_403_FORBIDDEN,
            detail="Only the organization owner can manage the IP allowlist",
        )


def _require_enterprise(org: Organization | None) -> None:
    """Allowlist is an Enterprise-plan feature. Gate the WRITE paths but
    leave the READ paths open so an Enterprise → PRO downgrade (if it
    ever happens) doesn't hide existing entries from the owner who
    needs to clean them up. Downgrades today happen via support so
    this is a belt-and-braces defence."""
    if org is None or org.plan != OrgPlan.ENTERPRISE:
        raise HTTPException(
            status_code=_status.HTTP_403_FORBIDDEN,
            detail="IP allowlist is available on the Enterprise plan. Contact sales to upgrade.",
        )


@router.get("/ip-allowlist", response_model=list[IpAllowlistEntryOut])
async def list_ip_allowlist(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    rows = await db.execute(
        select(OrgIpAllowlistEntry)
        .where(OrgIpAllowlistEntry.org_id == member.org_id)
        .order_by(OrgIpAllowlistEntry.created_at.asc())
    )
    return [IpAllowlistEntryOut.model_validate(r) for r in rows.scalars().all()]


@router.post("/ip-allowlist", response_model=IpAllowlistEntryOut, status_code=_status.HTTP_201_CREATED)
async def create_ip_allowlist_entry(
    body: IpAllowlistCreate,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    current_user, member = ctx
    _require_owner(member)
    org = await db.get(Organization, member.org_id)
    _require_enterprise(org)

    # Normalise and reject garbage at the edge — a malformed CIDR
    # stored in the DB would silently skip at match time (see
    # ip_matches_allowlist) and could mask a typo that locks the owner
    # out. Surface the error now.
    try:
        normalised = parse_cidr(body.cidr)
    except ValueError as exc:
        raise HTTPException(status_code=_status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Reject duplicate entries so the UI list stays clean.
    existing = await db.scalar(
        select(OrgIpAllowlistEntry).where(
            OrgIpAllowlistEntry.org_id == member.org_id,
            OrgIpAllowlistEntry.cidr == normalised,
        )
    )
    if existing:
        raise HTTPException(status_code=_status.HTTP_409_CONFLICT, detail="CIDR already on the allowlist")

    uid = current_user.get("user_id")
    if isinstance(uid, str):
        try:
            uid = _uuid.UUID(uid)
        except ValueError:
            uid = None
    entry = OrgIpAllowlistEntry(
        org_id=member.org_id,
        cidr=normalised,
        label=(body.label or None),
        created_by=uid,
    )
    db.add(entry)
    await db.flush()
    await log_action(
        db,
        action="ip_allowlist.entry_added",
        org_id=member.org_id,
        actor_user_id=uid,
        target_type="org_ip_allowlist",
        target_id=str(entry.id),
        request=request,
        extra={"cidr": normalised, "label": body.label or ""},
    )
    await db.commit()
    await db.refresh(entry)
    return IpAllowlistEntryOut.model_validate(entry)


@router.delete("/ip-allowlist/{entry_id}", status_code=_status.HTTP_204_NO_CONTENT)
async def delete_ip_allowlist_entry(
    entry_id: _uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    current_user, member = ctx
    _require_owner(member)

    entry = await db.scalar(
        select(OrgIpAllowlistEntry).where(
            OrgIpAllowlistEntry.id == entry_id,
            OrgIpAllowlistEntry.org_id == member.org_id,
        )
    )
    if not entry:
        raise HTTPException(status_code=_status.HTTP_404_NOT_FOUND, detail="Entry not found")

    uid = current_user.get("user_id")
    if isinstance(uid, str):
        try:
            uid = _uuid.UUID(uid)
        except ValueError:
            uid = None
    removed_cidr = entry.cidr
    await log_action(
        db,
        action="ip_allowlist.entry_removed",
        org_id=member.org_id,
        actor_user_id=uid,
        target_type="org_ip_allowlist",
        target_id=str(entry.id),
        request=request,
        extra={"cidr": removed_cidr, "label": entry.label or ""},
    )
    await db.delete(entry)
    await db.commit()
