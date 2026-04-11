"""Team management: list members, invite by email, remove, change role.

Plan-gated member limits
────────────────────────
FREE  → 3 members (including the owner)
PRO   → 20 members

The limit is enforced with a SELECT … FOR UPDATE on the org row so two
simultaneous invites cannot both pass the count check and both insert.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.organization import OrgPlan, OrgRole, Organization, OrganizationMember

router = APIRouter(prefix="/api/team", tags=["team"])

# ── Plan limits ────────────────────────────────────────────────────────────────

PLAN_MEMBER_LIMITS: dict[OrgPlan, int] = {
    OrgPlan.FREE: 3,
    OrgPlan.PRO:  20,
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _require_owner_or_admin(member: OrganizationMember) -> None:
    """Owners AND admins can invite/remove members (per CLAUDE.md spec)."""
    if member.role not in (OrgRole.OWNER, OrgRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can manage team members",
        )


def _require_owner(member: OrganizationMember) -> None:
    """Only owners can change roles or remove members."""
    if member.role != OrgRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can perform this action",
        )


# ── Schemas ────────────────────────────────────────────────────────────────────

class MemberOut(BaseModel):
    id:         uuid.UUID
    user_id:    uuid.UUID
    role:       OrgRole
    email:      str | None = None
    created_at: str

    model_config = {"from_attributes": True}


class InviteRequest(BaseModel):
    email: str
    role:  OrgRole = OrgRole.MEMBER

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address")
        return v.lower().strip()


class RoleUpdate(BaseModel):
    role: OrgRole


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=list[MemberOut])
async def list_members(
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
):
    _, member = ctx
    result = await db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.org_id == member.org_id)
        .order_by(OrganizationMember.created_at)
    )
    members = result.scalars().all()
    return [
        MemberOut(
            id=m.id,
            user_id=m.user_id,
            role=m.role,
            created_at=m.created_at.isoformat() if m.created_at else "",
        )
        for m in members
    ]


@router.post("/invite", status_code=status.HTTP_201_CREATED)
async def invite_member(
    body: InviteRequest,
    ctx:  tuple = Depends(get_current_member),
    db:   AsyncSession = Depends(get_db),
):
    """Invite a user by email via Supabase admin API. Creates auth user if needed.

    Enforces plan-based member limits with SELECT … FOR UPDATE so that two
    concurrent invites cannot both pass the count check simultaneously.
    """
    import httpx

    current_user, member = ctx
    _require_owner_or_admin(member)

    # ── Enforce plan member limit (race-condition safe) ───────────────────────
    # Lock the org row for the duration of this transaction so a concurrent
    # invite cannot read the same count and both successfully insert.
    org = await db.scalar(
        select(Organization)
        .where(Organization.id == member.org_id)
        .with_for_update()          # row-level lock until commit/rollback
    )
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    limit = PLAN_MEMBER_LIMITS.get(org.plan, 1)
    current_count = await db.scalar(
        select(func.count())
        .select_from(OrganizationMember)
        .where(OrganizationMember.org_id == member.org_id)
    )
    if (current_count or 0) >= limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Team member limit reached ({limit} members on {org.plan.value} plan). "
                "Upgrade to PRO to add more members."
            ),
        )

    # ── Create / look up user in Supabase ─────────────────────────────────────
    supabase_url = settings.SUPABASE_URL.rstrip("/")
    headers = {
        "apikey":        settings.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
        "Content-Type":  "application/json",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        invite_res = await client.post(
            f"{supabase_url}/auth/v1/admin/users",
            headers=headers,
            json={
                "email":         body.email,
                "email_confirm": True,
                "password":      _temp_password(),
            },
        )

    if invite_res.status_code not in (200, 201, 422):
        raise HTTPException(status_code=502, detail="Failed to create user in auth provider")

    if invite_res.status_code == 422:
        raise HTTPException(
            status_code=409,
            detail="A user with this email already exists. Ask them to log in and you can add them.",
        )

    invited_user_id = uuid.UUID(invite_res.json()["id"])

    # ── Guard: not already a member ───────────────────────────────────────────
    existing = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.org_id  == member.org_id,
            OrganizationMember.user_id == invited_user_id,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="User is already a member of this organization")

    # ── Insert (still inside the FOR UPDATE transaction) ─────────────────────
    db.add(OrganizationMember(
        org_id=member.org_id,
        user_id=invited_user_id,
        role=body.role,
    ))
    await db.commit()
    return {"status": "invited", "email": body.email}


@router.patch("/{member_id}/role", response_model=MemberOut)
async def update_role(
    member_id: uuid.UUID,
    body:      RoleUpdate,
    ctx:       tuple = Depends(get_current_member),
    db:        AsyncSession = Depends(get_db),
):
    current_user, caller = ctx
    _require_owner(caller)

    target = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.id     == member_id,
            OrganizationMember.org_id == caller.org_id,
        )
    )
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")
    if target.user_id == current_user["user_id"]:
        raise HTTPException(status_code=422, detail="Cannot change your own role")

    target.role = body.role
    await db.commit()
    await db.refresh(target)
    return MemberOut(
        id=target.id,
        user_id=target.user_id,
        role=target.role,
        created_at=target.created_at.isoformat() if target.created_at else "",
    )


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    member_id: uuid.UUID,
    ctx:       tuple = Depends(get_current_member),
    db:        AsyncSession = Depends(get_db),
):
    current_user, caller = ctx
    _require_owner(caller)

    target = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.id     == member_id,
            OrganizationMember.org_id == caller.org_id,
        )
    )
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")
    if target.user_id == current_user["user_id"]:
        raise HTTPException(status_code=422, detail="Cannot remove yourself")

    await db.delete(target)
    await db.commit()


# ── Internal helper ────────────────────────────────────────────────────────────

def _temp_password() -> str:
    """Generate a random temporary password for invited users.

    The user is expected to use 'Forgot password' — this value is never shown
    to anyone, it just satisfies Supabase's password complexity requirement.
    """
    import secrets
    import string
    chars = string.ascii_letters + string.digits + "!@#$"
    return "".join(secrets.choice(chars) for _ in range(20))
