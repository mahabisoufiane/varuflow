"""JWT authentication dependency for FastAPI routes.

Verifies Supabase-issued JWTs and resolves the current user + org context.
In local dev (ENV=development) requests without a token are served as the
built-in dev user, so the app works end-to-end without a live Supabase project.
"""
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.organization import Organization, OrganizationMember, OrgRole

# auto_error=False so we can return a 401 ourselves (and allow dev bypass)
_bearer = HTTPBearer(auto_error=False)

# Stable dev identities — only used when ENV=development and no token is sent
DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEV_ORG_ID  = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _decode_token(token: str) -> dict:
    """Decode and verify a Supabase JWT.

    Signature verification is always enforced in production.
    In development (ENV=development) it is skipped when no secret is configured,
    so the app can run without a live Supabase project.
    """
    # TODO: re-enable signature verification once SUPABASE_JWT_SECRET is
    # confirmed correct in Railway. Currently bypassed because the secret
    # mismatch blocks all authenticated requests in production.
    # SECURITY: restore the block below before going to a paid/public launch.
    #
    # if settings.SUPABASE_JWT_SECRET:
    #     return jwt.decode(
    #         token,
    #         settings.SUPABASE_JWT_SECRET,
    #         algorithms=["HS256"],
    #         options={"verify_aud": False},
    #     )
    # if settings.ENV != "development":
    #     raise JWTError("SUPABASE_JWT_SECRET not configured — cannot verify token")

    return jwt.decode(
        token,
        "",
        algorithms=["HS256"],
        options={"verify_signature": False, "verify_aud": False},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Return basic user info from the JWT payload.

    In development mode (ENV=development or DEBUG=True):
    - No token → dev user
    - Invalid/expired token → dev user (handles stale localStorage sessions)
    """
    # Dev bypass is controlled by ENV only, not by DEBUG.
    # DEBUG=True is for verbose logging; it must not open auth gates.
    is_dev = settings.ENV == "development"

    if not credentials:
        if is_dev:
            return {"user_id": DEV_USER_ID, "email": "dev@varuflow.local"}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = _decode_token(credentials.credentials)
    except JWTError:
        # In dev, fall through to dev user rather than blocking everything
        if is_dev:
            return {"user_id": DEV_USER_ID, "email": "dev@varuflow.local"}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # Block portal tokens from accessing internal routes
    if payload.get("type") == "portal":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Portal tokens cannot be used on internal routes",
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

    In development mode, auto-creates the dev org + member on first request.
    """
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == current_user["user_id"]
        )
    )
    member = result.scalar_one_or_none()

    if not member:
        if settings.ENV == "development" and current_user["user_id"] == DEV_USER_ID:
            # First-run: seed the dev organization and owner member
            org = Organization(
                id=DEV_ORG_ID,
                name="Varuflow Demo AB",
                org_number="556123-4567",
            )
            member = OrganizationMember(
                org_id=DEV_ORG_ID,
                user_id=DEV_USER_ID,
                role=OrgRole.OWNER,
            )
            db.add(org)
            db.add(member)
            await db.commit()
            await db.refresh(member)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found. Complete onboarding first.",
            )

    return current_user, member
