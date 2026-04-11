"""Standalone auth endpoints (local accounts — independent of Supabase).

Prefix: /api/local-auth

POST   /signup              — register with email + password
POST   /verify-email        — confirm email verification token
POST   /login               — password login → JWT + refresh token
POST   /refresh             — exchange refresh token for new access token
POST   /logout              — revoke refresh token
GET    /me                  — return current user profile
POST   /mfa/enable          — start TOTP setup (returns provisioning URI)
POST   /mfa/confirm         — activate TOTP after user scans QR
POST   /mfa/disable         — turn off TOTP
POST   /password/reset      — request password reset email
POST   /password/confirm    — set new password with reset token
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import (
    AuthUserOut,
    LoginRequest,
    LogoutRequest,
    MFARequiredResponse,
    PasswordResetConfirmSchema,
    PasswordResetRequestSchema,
    RefreshRequest,
    SignupRequest,
    SignupResponse,
    TOTPConfirmRequest,
    TOTPDisableRequest,
    TOTPEnableResponse,
    TokenResponse,
    VerifyEmailRequest,
)
from app.services import auth_email, auth_service
from app.models.auth import AuthUser
from sqlalchemy import select

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/local-auth", tags=["local-auth"])
_bearer = HTTPBearer(auto_error=False)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _get_current_auth_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: AsyncSession = Depends(get_db),
) -> AuthUser:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = auth_service.decode_access_token(credentials.credentials)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc

    user = await db.scalar(
        select(AuthUser).where(AuthUser.id == payload["sub"])
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# --------------------------------------------------------------------------- #
# Signup
# --------------------------------------------------------------------------- #

@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = await auth_service.create_user(body.email, body.password, db)
    except ValueError as exc:
        if str(exc) == "EMAIL_TAKEN":
            # Respond identically to a successful signup to prevent email enumeration
            raise HTTPException(
                status_code=status.HTTP_201_CREATED,
                detail="If this email is not registered, a verification link has been sent.",
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    try:
        await auth_email.send_verification_email(user.email, user.email_verification_token)
    except Exception:
        log.exception("Failed to send verification email | user_id=%s", user.id)
        # Don't fail the signup — user can re-request later

    return SignupResponse(
        message="Account created. Check your email to verify your address.",
        user_id=user.id,
    )


# --------------------------------------------------------------------------- #
# Email Verification
# --------------------------------------------------------------------------- #

@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(body: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    try:
        await auth_service.verify_email(body.token, db)
    except ValueError as exc:
        code = str(exc)
        if code == "TOKEN_EXPIRED":
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Verification link has expired. Request a new one.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification token.")
    return {"message": "Email verified. You can now sign in."}


# --------------------------------------------------------------------------- #
# Login
# --------------------------------------------------------------------------- #

@router.post("/login")
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    ip = _client_ip(request)
    ua = request.headers.get("User-Agent")
    try:
        _, access_token, refresh_token = await auth_service.authenticate_user(
            body.email, body.password, body.totp_code, db, ip, ua
        )
    except ValueError as exc:
        code = str(exc)
        if code == "MFA_REQUIRED":
            return MFARequiredResponse()
        if code.startswith("ACCOUNT_LOCKED:"):
            minutes = code.split(":")[1]
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account locked. Try again in {minutes} minute(s).",
            )
        if code == "EMAIL_NOT_VERIFIED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please verify your email before signing in.",
            )
        # INVALID_CREDENTIALS, USER_NOT_FOUND, INVALID_TOTP → same response
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email, password, or TOTP code.",
        )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


# --------------------------------------------------------------------------- #
# Refresh
# --------------------------------------------------------------------------- #

@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        new_access, new_refresh = await auth_service.refresh_access_token(
            body.refresh_token, db
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token."
        ) from exc
    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


# --------------------------------------------------------------------------- #
# Logout
# --------------------------------------------------------------------------- #

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.revoke_refresh_token(body.refresh_token, db)


# --------------------------------------------------------------------------- #
# Current User
# --------------------------------------------------------------------------- #

@router.get("/me", response_model=AuthUserOut)
async def get_me(current_user: AuthUser = Depends(_get_current_auth_user)):
    return current_user


# --------------------------------------------------------------------------- #
# TOTP / MFA
# --------------------------------------------------------------------------- #

@router.post("/mfa/enable", response_model=TOTPEnableResponse)
async def mfa_enable(
    current_user: AuthUser = Depends(_get_current_auth_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        secret, uri = await auth_service.totp_enable_initiate(current_user.id, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return TOTPEnableResponse(provisioning_uri=uri)


@router.post("/mfa/confirm", status_code=status.HTTP_200_OK)
async def mfa_confirm(
    body: TOTPConfirmRequest,
    current_user: AuthUser = Depends(_get_current_auth_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await auth_service.totp_enable_confirm(current_user.id, body.totp_code, db)
    except ValueError as exc:
        code = str(exc)
        if code == "INVALID_TOTP":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TOTP code.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code)
    return {"message": "TOTP authentication is now enabled on your account."}


@router.post("/mfa/disable", status_code=status.HTTP_200_OK)
async def mfa_disable(
    body: TOTPDisableRequest,
    current_user: AuthUser = Depends(_get_current_auth_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await auth_service.totp_disable(current_user.id, body.password, body.totp_code, db)
    except ValueError as exc:
        code = str(exc)
        if code in ("INVALID_PASSWORD", "INVALID_TOTP"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password or TOTP code."
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code)
    return {"message": "TOTP authentication has been disabled."}


# --------------------------------------------------------------------------- #
# Password Reset
# --------------------------------------------------------------------------- #

@router.post("/password/reset", status_code=status.HTTP_200_OK)
async def password_reset_request(
    body: PasswordResetRequestSchema, db: AsyncSession = Depends(get_db)
):
    token = await auth_service.initiate_password_reset(body.email, db)
    if token:
        try:
            await auth_email.send_password_reset_email(body.email, token)
        except Exception:
            log.exception("Failed to send password reset email | email=%s", body.email)
    # Always respond identically — don't reveal whether the email exists
    return {"message": "If an account with that email exists, a reset link has been sent."}


@router.post("/password/confirm", status_code=status.HTTP_200_OK)
async def password_reset_confirm(
    body: PasswordResetConfirmSchema, db: AsyncSession = Depends(get_db)
):
    try:
        await auth_service.confirm_password_reset(body.token, body.new_password, db)
    except ValueError as exc:
        code = str(exc)
        if code == "TOKEN_EXPIRED":
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Reset link has expired. Request a new one.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token.")
    return {"message": "Password updated successfully. You can now sign in."}
