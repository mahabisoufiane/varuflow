"""POS device authentication — PIN-based login for tablet POS terminals.

Issues a JWT with type="pos_device" that the POS standalone app uses for
all subsequent /api/pos/* requests. In development mode any 4+ digit PIN
authenticates as the dev user. In production each OrganizationMember has
an optional pos_pin hash stored on their row.
"""
import os
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.organization import Organization, OrganizationMember, OrgRole

router = APIRouter(
    prefix="/api/pos/auth",
    tags=["pos-auth"],
    # No plan gate here — this IS the login endpoint; plan is enforced on
    # /api/pos/sessions and /api/pos/sales after the device has a token.
)

_ALGORITHM = "HS256"
_TOKEN_EXPIRY_HOURS = 720  # 30 days — POS devices stay logged in


class PinRequest(BaseModel):
    pin: str = Field(..., min_length=6, max_length=6)
    org_id: uuid.UUID | None = None


class PinResponse(BaseModel):
    token: str
    org_name: str
    role: str


@router.post("/pin", response_model=PinResponse)
async def authenticate_pos_device(
    body: PinRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate a POS device using a numeric PIN.

    In development mode (ENV=development), any valid 4-6 digit PIN
    authenticates as the first OWNER of the first org. This allows the
    standalone POS app to work without Supabase.
    """
    is_dev = os.getenv("ENV", "development") == "development"

    if is_dev:
        # Dev shortcut: accept any PIN, return token for first org owner
        result = await db.execute(
            select(OrganizationMember)
            .where(OrganizationMember.role == OrgRole.OWNER)
            .limit(1)
        )
        member = result.scalar_one_or_none()
        if not member:
            raise HTTPException(status_code=404, detail="No organization found — create one first")

        org_result = await db.execute(
            select(Organization).where(Organization.id == member.org_id)
        )
        org = org_result.scalar_one()

        payload = {
            "sub": str(member.user_id),
            "org_id": str(member.org_id),
            "member_id": str(member.id),
            "role": member.role.value,
            "type": "pos_device",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=_TOKEN_EXPIRY_HOURS),
        }
        token = jwt.encode(payload, settings.AUTH_JWT_SECRET, algorithm=_ALGORITHM)
        return PinResponse(token=token, org_name=org.name, role=member.role.value)

    # Production: verify PIN against member's stored hash
    # Search all members across all orgs that have a pos_pin_hash set.
    # If org_id is supplied, scope the search to that org only.
    from passlib.context import CryptContext
    _ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

    query = (
        select(OrganizationMember)
        .where(OrganizationMember.pos_pin_hash.isnot(None))
    )
    if body.org_id is not None:
        query = query.where(OrganizationMember.org_id == body.org_id)

    result = await db.execute(query)
    members = result.scalars().all()

    matched: OrganizationMember | None = None
    for m in members:
        if m.pos_pin_hash and _ctx.verify(body.pin, m.pos_pin_hash):
            matched = m
            break

    if matched is None:
        # Constant-time dummy verify to prevent timing-based member enumeration
        _ctx.verify(body.pin, "$2b$12$KIXAqrFMBMl3TQP8A0.qiu0Q8HwDQXq1JvxU1/VkU5X7RxFkm.Abe")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid PIN")

    org_result = await db.execute(
        select(Organization).where(Organization.id == matched.org_id)
    )
    org = org_result.scalar_one()

    payload = {
        "sub": str(matched.user_id),
        "org_id": str(matched.org_id),
        "member_id": str(matched.id),
        "role": matched.role.value,
        "type": "pos_device",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=_TOKEN_EXPIRY_HOURS),
    }
    token = jwt.encode(payload, settings.AUTH_JWT_SECRET, algorithm=_ALGORITHM)
    return PinResponse(token=token, org_name=org.name, role=matched.role.value)


# ── PIN management (org admin only) ──────────────────────────────────────────

class SetPinRequest(BaseModel):
    member_id: uuid.UUID
    pin: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


@router.post("/set-pin", status_code=204)
async def set_member_pin(
    body: SetPinRequest,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(__import__("app.middleware.auth", fromlist=["get_current_member"]).get_current_member),
):
    """Set a 6-digit POS PIN for an org member. Caller must be OWNER or ADMIN."""
    from passlib.context import CryptContext
    _ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

    _user_dict, caller = ctx
    if caller.role not in (OrgRole.OWNER, OrgRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only OWNER or ADMIN can set PINs")

    target = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.id == body.member_id,
            OrganizationMember.org_id == caller.org_id,
        )
    )
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")

    target.pos_pin_hash = _ctx.hash(body.pin)
    await db.commit()


@router.delete("/set-pin/{member_id}", status_code=204)
async def clear_member_pin(
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: tuple = Depends(__import__("app.middleware.auth", fromlist=["get_current_member"]).get_current_member),
):
    """Remove POS PIN access for a member. Caller must be OWNER or ADMIN."""
    _user_dict, caller = ctx
    if caller.role not in (OrgRole.OWNER, OrgRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only OWNER or ADMIN can clear PINs")

    target = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.id == member_id,
            OrganizationMember.org_id == caller.org_id,
        )
    )
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")

    target.pos_pin_hash = None
    await db.commit()
