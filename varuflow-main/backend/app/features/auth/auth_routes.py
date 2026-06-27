"""Auth & onboarding endpoints.

POST /api/auth/onboarding  — create org for a newly verified user
GET  /api/auth/me          — return current user + org info
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member, get_current_user
from app.middleware.rate_limit import per_ip_rate_limit
from app.features.auth.modules import MemberModule
from app.features.auth.organization import OrgPlan, OrgRole, Organization, OrganizationMember
from app.services.plan_limits import PLAN_MODULES

router = APIRouter(prefix="/api/auth", tags=["auth"])

_onboarding_limit = per_ip_rate_limit("auth.onboarding", 5, 3600)


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
    allowed_modules: list[str]
    plan_modules: list[str]


# ---- Endpoints ----

@router.post("/onboarding", response_model=MemberOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(_onboarding_limit)])
async def complete_onboarding(
    body: OnboardingRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an organization for a newly signed-up user.

    Idempotent: if the user already has an org, returns it without creating a new one.

    Race-safety: the unique constraint on `organization_members` is
    `(org_id, user_id)` — NOT `user_id` alone (a user is allowed to belong
    to multiple orgs). Two concurrent onboarding calls for the same user
    would therefore both pass the `existing` check, each create a fresh
    org with a different org_id, and both commit without an IntegrityError
    — leaving the user as owner of two empty orgs. Serialise with a
    transaction-scoped Postgres advisory lock keyed on the user_id so only
    one onboarding per user can be in flight at a time. SQLite (tests)
    ignores this silently.
    """
    try:
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:u))")
            .bindparams(u=f"onboarding:{current_user['user_id']}")
        )
    except Exception:
        # Non-Postgres (e.g. test SQLite) — fall through without the lock
        pass

    # Check if user already completed onboarding.
    #
    # A single user can belong to MULTIPLE orgs (the unique constraint is
    # (org_id, user_id) — see docstring). Without a limit + deterministic
    # ordering, the `db.scalar()` would raise MultipleResultsFound and
    # 500 the endpoint for anyone invited to more than one org. Prefer
    # the user's OWNER membership (their own org) and fall back to the
    # earliest-created one — matches the idempotent-return intent and
    # never surprises the client by switching to a different org across
    # calls.
    from app.features.auth.organization import OrgRole as _OrgRole
    existing = await db.scalar(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == current_user["user_id"])
        .order_by(
            (OrganizationMember.role != _OrgRole.OWNER).asc(),
            OrganizationMember.created_at.asc(),
        )
        .limit(1)
    )
    if existing:
        org = await db.get(Organization, existing.org_id)
        plan_key = org.plan.value if hasattr(org.plan, "value") else str(org.plan)
        plan_mods = PLAN_MODULES.get(plan_key, frozenset())
        return MemberOut(
            user_id=current_user["user_id"],
            email=current_user["email"],
            role=existing.role,
            organization=OrganizationOut.model_validate(org),
            allowed_modules=["*"] if "*" in plan_mods else sorted(plan_mods),
            plan_modules=["*"] if "*" in plan_mods else sorted(plan_mods),
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
    try:
        await db.commit()
    except IntegrityError:
        # A concurrent onboarding won the race — roll back and return the
        # membership that was committed first so the user does not end up
        # with two organisations.
        await db.rollback()
        # See comment on the idempotent check at the top of this function —
        # prefer the user's OWNER membership, fall back to earliest-created,
        # and cap to one row so a user who already belongs to multiple
        # orgs cannot trip MultipleResultsFound here.
        existing = await db.scalar(
            select(OrganizationMember)
            .where(OrganizationMember.user_id == current_user["user_id"])
            .order_by(
                (OrganizationMember.role != _OrgRole.OWNER).asc(),
                OrganizationMember.created_at.asc(),
            )
            .limit(1)
        )
        if existing:
            org = await db.get(Organization, existing.org_id)
            plan_key = org.plan.value if hasattr(org.plan, "value") else str(org.plan)
            plan_mods = PLAN_MODULES.get(plan_key, frozenset())
            return MemberOut(
                user_id=current_user["user_id"],
                email=current_user["email"],
                role=existing.role,
                organization=OrganizationOut.model_validate(org),
                allowed_modules=["*"] if "*" in plan_mods else sorted(plan_mods),
                plan_modules=["*"] if "*" in plan_mods else sorted(plan_mods),
            )
        # Genuinely unknown integrity failure — surface it
        raise HTTPException(status_code=500, detail="Onboarding failed — please retry")
    await db.refresh(org)

    plan_key = org.plan.value if hasattr(org.plan, "value") else str(org.plan)
    plan_mods = PLAN_MODULES.get(plan_key, frozenset())
    return MemberOut(
        user_id=current_user["user_id"],
        email=current_user["email"],
        role=OrgRole.OWNER,
        organization=OrganizationOut.model_validate(org),
        allowed_modules=["*"] if "*" in plan_mods else sorted(plan_mods),
        plan_modules=["*"] if "*" in plan_mods else sorted(plan_mods),
    )


class OrgUpdateRequest(BaseModel):
    company_name: str | None = Field(None, min_length=1, max_length=255)
    org_number: str | None = Field(None, max_length=20)
    vat_number: str | None = Field(None, max_length=30)
    address: str | None = Field(None, max_length=500)


@router.put("/org", response_model=OrganizationOut)
async def update_org(
    body: OrgUpdateRequest,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Update organization details. Only OWNER role allowed.

    Partial update: only fields explicitly present in the request body are
    written. Previously this endpoint unconditionally overwrote
    `org_number`, `vat_number` and `address` with `None` whenever the
    client omitted them — silently wiping invoice-critical data that
    appears on every invoice PDF and on Peppol/EHF exports.
    """
    _, member = ctx
    if member.role.value != "OWNER":
        raise HTTPException(status_code=403, detail="Only owners can update organization details")
    org = await db.get(Organization, member.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    data = body.model_dump(exclude_unset=True)
    if "company_name" in data:
        name = data["company_name"]
        if not name or not name.strip():
            raise HTTPException(status_code=422, detail="company_name cannot be empty")
        org.name = name
    if "org_number" in data:
        org.org_number = data["org_number"]
    if "vat_number" in data:
        org.vat_number = data["vat_number"]
    if "address" in data:
        org.address = data["address"]
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

    plan_key = org.plan.value if hasattr(org.plan, "value") else str(org.plan)
    plan_modules = PLAN_MODULES.get(plan_key, frozenset())

    if "*" in plan_modules:
        allowed_modules = ["*"]
    elif member.role in (OrgRole.OWNER, OrgRole.ADMIN):
        allowed_modules = sorted(plan_modules)
    elif getattr(member, "module_access_mode", "ALL") == "ALL":
        allowed_modules = sorted(plan_modules)
    else:
        rows = await db.execute(
            select(MemberModule.module_key).where(
                MemberModule.member_id == member.id
            )
        )
        user_modules = {r[0] for r in rows.all()}
        allowed_modules = sorted(plan_modules & user_modules)

    return MemberOut(
        user_id=current_user["user_id"],
        email=current_user["email"],
        role=member.role,
        organization=OrganizationOut.model_validate(org),
        allowed_modules=allowed_modules,
        plan_modules=sorted(plan_modules) if "*" not in plan_modules else ["*"],
    )
