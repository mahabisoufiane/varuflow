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
from app.middleware.plan_check import require_module
from app.models.organization import Organization, OrganizationMember, OrgRole

router = APIRouter(
    prefix="/api/pos/auth",
    tags=["pos-auth"],
    dependencies=[Depends(require_module("pos"))],
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
    # For now, raise 501 until pos_pin column is added via migration
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Production POS PIN auth requires pos_pin column — run migration first",
    )
