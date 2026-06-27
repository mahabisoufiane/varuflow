"""Team management: list members, invite by email, remove, change role.

Plan-gated member limits
────────────────────────
FREE  → 3 members (including the owner)
PRO   → 20 members

The limit is enforced with a SELECT … FOR UPDATE on the org row so two
simultaneous invites cannot both pass the count check and both insert.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_member, require_mfa_if_enforced
from app.models.organization import OrgPlan, OrgRole, Organization, OrganizationMember
from app.services.audit import log_action
from app.services.plan_limits import RESOURCE_USERS, LimitExceededError, check_limit

router = APIRouter(prefix="/api/team", tags=["team"])

# ── Plan limits ────────────────────────────────────────────────────────────────
# Kept for backwards-compat reference; actual enforcement via plan_limits service.

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
    request: Request,
    ctx:  tuple = Depends(require_mfa_if_enforced),
    db:   AsyncSession = Depends(get_db),
):
    """Invite a user by email via Supabase admin API. Creates auth user if needed.

    Enforces plan-based member limits with SELECT … FOR UPDATE so that two
    concurrent invites cannot both pass the count check simultaneously.
    """
    import httpx

    current_user, member = ctx
    _require_owner_or_admin(member)

    # Privilege-escalation guard: admins are allowed to invite MEMBERs and
    # (optionally) other ADMINs, but NOT OWNERs. Without this check an admin
    # could create a new OWNER here, then that OWNER could demote/remove the
    # original owner via PATCH /team/{id}/role — fully compromising the
    # tenant. Role changes on existing members already require OWNER via
    # `_require_owner`, so keep invites aligned with that rule.
    if body.role == OrgRole.OWNER and member.role != OrgRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an existing owner can invite another owner",
        )

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
    try:
        check_limit(org.plan, RESOURCE_USERS, current_count or 0)
    except LimitExceededError as _exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PLAN_LIMIT_EXCEEDED",
                "resource": RESOURCE_USERS,
                "current_plan": org.plan.value,
                "limit": _exc.limit,
                "current": _exc.current,
            },
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

    # Supabase returns the user object as JSON. Guard against malformed
    # responses (empty body / auth-service outage / HTML error page) so we
    # return a clean 502 instead of crashing with KeyError or ValueError.
    try:
        body_json = invite_res.json()
        invited_user_id = uuid.UUID(body_json["id"])
    except (ValueError, KeyError, TypeError):
        import logging as _logging
        _logging.getLogger(__name__).error(
            "team invite: unexpected Supabase response",
            extra={"org_id": str(member.org_id), "status": invite_res.status_code},
        )
        raise HTTPException(status_code=502, detail="Auth provider returned an unexpected response")

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
    new_member = OrganizationMember(
        org_id=member.org_id,
        user_id=invited_user_id,
        role=body.role,
    )
    db.add(new_member)
    await db.flush()  # get new_member.id before logging
    # Security-sensitive: record every successful team invite so the owner
    # can later audit who added whom with which role (CLAUDE.md audit rule).
    await log_action(
        db,
        action="team.member_invited",
        org_id=member.org_id,
        actor_user_id=uuid.UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"],
        target_type="organization_member",
        target_id=str(new_member.id),
        request=request,
        extra={"invited_email": body.email, "role": body.role.value},
    )
    await db.commit()
    return {"status": "invited", "email": body.email}


@router.patch("/{member_id}/role", response_model=MemberOut)
async def update_role(
    member_id: uuid.UUID,
    body:      RoleUpdate,
    request:   Request,
    ctx:       tuple = Depends(require_mfa_if_enforced),
    db:        AsyncSession = Depends(get_db),
):
    current_user, caller = ctx
    _require_owner(caller)

    # Lock the org row so two concurrent role changes that each demote an
    # owner can't both pass the owner_count>1 check and leave the org with
    # zero owners (unrecoverable without DB access).
    await db.execute(
        select(Organization.id)
        .where(Organization.id == caller.org_id)
        .with_for_update()
    )

    target = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.id     == member_id,
            OrganizationMember.org_id == caller.org_id,
        )
    )
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")
    # JWT claims give user_id as str; target.user_id is uuid.UUID. A
    # str-vs-UUID `==` comparison is always False in Python, which would
    # silently bypass this self-guard and let an owner of a multi-owner
    # org demote themselves directly. Coerce to UUID before comparing.
    caller_uid = current_user["user_id"]
    if isinstance(caller_uid, str):
        try:
            caller_uid = uuid.UUID(caller_uid)
        except ValueError:
            caller_uid = None
    if caller_uid is not None and target.user_id == caller_uid:
        raise HTTPException(status_code=422, detail="Cannot change your own role")

    # Prevent demoting the last remaining owner — would leave the org unable to
    # manage billing, team, or integrations.
    if target.role == OrgRole.OWNER and body.role != OrgRole.OWNER:
        owner_count = await db.scalar(
            select(func.count())
            .select_from(OrganizationMember)
            .where(
                OrganizationMember.org_id == caller.org_id,
                OrganizationMember.role == OrgRole.OWNER,
            )
        )
        if (owner_count or 0) <= 1:
            raise HTTPException(
                status_code=422,
                detail="Cannot demote the last owner. Promote another member to owner first.",
            )

    previous_role = target.role.value if hasattr(target.role, "value") else str(target.role)
    target.role = body.role
    await log_action(
        db,
        action="team.role_changed",
        org_id=caller.org_id,
        actor_user_id=uuid.UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"],
        target_type="organization_member",
        target_id=str(target.id),
        request=request,
        extra={"previous_role": previous_role, "new_role": body.role.value},
    )
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
    request:   Request,
    ctx:       tuple = Depends(require_mfa_if_enforced),
    db:        AsyncSession = Depends(get_db),
):
    current_user, caller = ctx
    _require_owner(caller)

    # Lock the org row so two concurrent owner removals can't both pass the
    # owner_count>1 check and leave the org with zero owners.
    await db.execute(
        select(Organization.id)
        .where(Organization.id == caller.org_id)
        .with_for_update()
    )

    target = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.id     == member_id,
            OrganizationMember.org_id == caller.org_id,
        )
    )
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")
    # See comment in update_role: str-vs-UUID compare is always False.
    caller_uid = current_user["user_id"]
    if isinstance(caller_uid, str):
        try:
            caller_uid = uuid.UUID(caller_uid)
        except ValueError:
            caller_uid = None
    if caller_uid is not None and target.user_id == caller_uid:
        raise HTTPException(status_code=422, detail="Cannot remove yourself")

    # Prevent removing the last remaining owner.
    if target.role == OrgRole.OWNER:
        owner_count = await db.scalar(
            select(func.count())
            .select_from(OrganizationMember)
            .where(
                OrganizationMember.org_id == caller.org_id,
                OrganizationMember.role == OrgRole.OWNER,
            )
        )
        if (owner_count or 0) <= 1:
            raise HTTPException(
                status_code=422,
                detail="Cannot remove the last owner. Promote another member to owner first.",
            )

    removed_role = target.role.value if hasattr(target.role, "value") else str(target.role)
    removed_user_id = str(target.user_id)
    await log_action(
        db,
        action="team.member_removed",
        org_id=caller.org_id,
        actor_user_id=uuid.UUID(current_user["user_id"]) if isinstance(current_user["user_id"], str) else current_user["user_id"],
        target_type="organization_member",
        target_id=str(target.id),
        request=request,
        extra={"removed_role": removed_role, "removed_user_id": removed_user_id},
    )
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
