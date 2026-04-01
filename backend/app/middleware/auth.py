"""JWT authentication dependency for FastAPI routes.

Verifies Supabase-issued JWTs and resolves the current user + org context.
In local dev (SUPABASE_JWT_SECRET is empty) the token is decoded without
signature verification so the app works without a live Supabase project.
"""
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.organization import Organization, OrganizationMember

_bearer = HTTPBearer(auto_error=True)


def _decode_token(token: str) -> dict:
    """Decode and optionally verify a Supabase JWT."""
    if settings.SUPABASE_JWT_SECRET:
        return jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    # No secret configured — dev mode, skip signature verification
    return jwt.decode(
        token,
        "",
        algorithms=["HS256"],
        options={"verify_signature": False, "verify_aud": False},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Return basic user info from the JWT payload."""
    try:
        payload = _decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    return {
        "user_id": uuid.UUID(user_id),
        "email": payload.get("email", ""),
    }


async def get_current_member(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[dict, OrganizationMember]:
    """Return user info + their OrganizationMember row.

    Raises 404 if the user hasn't completed onboarding yet.
    """
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == current_user["user_id"]
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found. Complete onboarding first.",
        )
    return current_user, member
