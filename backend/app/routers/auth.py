"""Auth & onboarding endpoints.

POST /api/auth/onboarding  — create org for a newly verified user
GET  /api/auth/me          — return current user + org info
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member, get_current_user
from app.models.organization import OrgPlan, OrgRole, Organization, OrganizationMember

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---- Schemas ----

class OnboardingRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    org_number: str | None = Field(None, max_length=20)
    vat_number: str | None = Field(None, max_length=30)
    address: str | None = Field(None, max_length=500)


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    org_number: str | None
    vat_number: str | None
    address: str | None
    plan: OrgPlan

    model_config = {"from_attributes": True}


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    role: OrgRole
    organization: OrganizationOut


# ---- Endpoints ----

@router.post("/onboarding", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
async def complete_onboarding(
    body: OnboardingRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an organization for a newly signed-up user.

    Idempotent: if the user already has an org, returns it without creating a new one.
    """
    # Check if user already completed onboarding
    existing = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.user_id == current_user["user_id"]
        )
    )
    if existing:
        org = await db.get(Organization, existing.org_id)
        return MemberOut(
            user_id=current_user["user_id"],
            email=current_user["email"],
            role=existing.role,
            organization=OrganizationOut.model_validate(org),
        )

    # Create org + owner membership
    org = Organization(
        name=body.company_name,
        org_number=body.org_number,
        vat_number=body.vat_number,
        address=body.address,
        plan=OrgPlan.FREE,
    )
    db.add(org)
    await db.flush()  # get org.id before creating member

    member = OrganizationMember(
        org_id=org.id,
        user_id=current_user["user_id"],
        role=OrgRole.OWNER,
    )
    db.add(member)
    await db.commit()
    await db.refresh(org)

    return MemberOut(
        user_id=current_user["user_id"],
        email=current_user["email"],
        role=OrgRole.OWNER,
        organization=OrganizationOut.model_validate(org),
    )


class OrgUpdateRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    org_number: str | None = Field(None, max_length=20)
    vat_number: str | None = Field(None, max_length=30)
    address: str | None = Field(None, max_length=500)


@router.put("/org", response_model=OrganizationOut)
async def update_org(
    body: OrgUpdateRequest,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Update organization details. Only OWNER role allowed."""
    _, member = ctx
    if member.role.value != "OWNER":
        raise HTTPException(status_code=403, detail="Only owners can update organization details")
    org = await db.get(Organization, member.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    org.name = body.company_name
    org.org_number = body.org_number
    org.vat_number = body.vat_number
    org.address = body.address
    await db.commit()
    await db.refresh(org)
    return org


@router.get("/me", response_model=MemberOut)
async def get_me(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return the current user's profile and organization."""
    current_user, member = ctx
    org = await db.get(Organization, member.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return MemberOut(
        user_id=current_user["user_id"],
        email=current_user["email"],
        role=member.role,
        organization=OrganizationOut.model_validate(org),
    )
