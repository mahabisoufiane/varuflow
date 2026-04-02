"""Team management: list members, invite by email, remove, change role."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.organization import OrgRole, OrganizationMember

router = APIRouter(prefix="/api/team", tags=["team"])


def _ctx(ctx: tuple):
    current_user, member = ctx
    return current_user, member


def _require_owner(member: OrganizationMember):
    if member.role.value != "OWNER":
        raise HTTPException(status_code=403, detail="Only owners can manage team members")


# ── Schemas ────────────────────────────────────────────────────────────────────

class MemberOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    role: OrgRole
    email: str | None = None
    created_at: str

    model_config = {"from_attributes": True}


class InviteRequest(BaseModel):
    email: str
    role: OrgRole = OrgRole.MEMBER

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email")
        return v.lower().strip()


class RoleUpdate(BaseModel):
    role: OrgRole


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=list[MemberOut])
async def list_members(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _, member = ctx
    result = await db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.org_id == member.org_id)
        .order_by(OrganizationMember.created_at)
    )
    members = result.scalars().all()
    # Format created_at as ISO string
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
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Invite a user by email via Supabase admin API. Creates auth user if needed."""
    current_user, member = ctx
    _require_owner(member)

    import httpx

    # Create / invite the user via Supabase admin
    supabase_url = settings.SUPABASE_URL.rstrip("/")
    headers = {
        "apikey": settings.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        # Check if user already exists by listing users (simple invite approach)
        invite_res = await client.post(
            f"{supabase_url}/auth/v1/admin/users",
            headers=headers,
            json={
                "email": body.email,
                "email_confirm": True,
                "password": _temp_password(),
            },
        )

    if invite_res.status_code not in (200, 201, 422):
        raise HTTPException(status_code=502, detail="Failed to create user in auth provider")

    data = invite_res.json()
    # 422 means user already exists — get their ID a different way
    if invite_res.status_code == 422:
        raise HTTPException(
            status_code=409,
            detail="A user with this email already exists. Ask them to log in and you can add them.",
        )

    invited_user_id = uuid.UUID(data["id"])

    # Check not already a member
    existing = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.org_id == member.org_id,
            OrganizationMember.user_id == invited_user_id,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="User is already a member of this organization")

    new_member = OrganizationMember(
        org_id=member.org_id,
        user_id=invited_user_id,
        role=body.role,
    )
    db.add(new_member)
    await db.commit()
    return {"status": "invited", "email": body.email}


@router.patch("/{member_id}/role", response_model=MemberOut)
async def update_role(
    member_id: uuid.UUID,
    body: RoleUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    current_user, caller = ctx
    _require_owner(caller)

    target = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.id == member_id,
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
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    current_user, caller = ctx
    _require_owner(caller)

    target = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.id == member_id,
            OrganizationMember.org_id == caller.org_id,
        )
    )
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")
    if target.user_id == current_user["user_id"]:
        raise HTTPException(status_code=422, detail="Cannot remove yourself")

    await db.delete(target)
    await db.commit()


def _temp_password() -> str:
    import secrets, string
    chars = string.ascii_letters + string.digits + "!@#$"
    return "".join(secrets.choice(chars) for _ in range(16))
