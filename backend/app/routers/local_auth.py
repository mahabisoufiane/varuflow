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
from app.services.audit import log_action
from app.middleware.rate_limit import per_ip_rate_limit
from app.models.auth import AuthUser
from sqlalchemy import select

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/local-auth", tags=["local-auth"])
_bearer = HTTPBearer(auto_error=False)

# Item 29: sustained per-IP cap for credential endpoints on top of the
# middleware's 5/min burst cap. 20 attempts per 15 minutes catches a
# slow-drip attack that deliberately stays under the 5/min threshold
# (e.g. one attempt every 13 seconds = 4.6/min).
_login_sustained = per_ip_rate_limit("local_auth.login", 20, 900)
_password_sustained = per_ip_rate_limit("local_auth.password", 10, 3600)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _client_ip(request: Request) -> str:
    # Only trust X-Forwarded-For when the app is actually behind a known
    # proxy (Railway, Render, etc.) — otherwise an attacker hitting the
    # backend directly could forge the IP used for login lockout /
    # audit trails. Matches rate_limit.py + services.audit.
    from app.config import settings
    if settings.TRUST_PROXY:
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

    # Guard against malformed JWTs. `decode_access_token` validates the
    # signature and the `type` claim, but a token with no `sub` (or one
    # whose `sub` isn't a valid UUID) used to surface as KeyError /
    # asyncpg DataError => 500. Treat both as 401 so a crafted token
    # can't spam our error-rate logs and Sentry.
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    try:
        import uuid as _uuid
        user_id = _uuid.UUID(str(sub))
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = await db.scalar(
        select(AuthUser).where(AuthUser.id == user_id)
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    # Item 24: reject tokens whose ``ver`` claim has been invalidated by a
    # later password reset / TOTP disable. Runs AFTER the DB lookup so we
    # can compare against the live ``session_version`` without a second
    # query. A pre-v44 token (no claim) falls through — see the helper
    # docstring for the legacy-pass rationale.
    from app.middleware.auth import verify_session_version
    verify_session_version(payload, user)
    return user


# --------------------------------------------------------------------------- #
# Signup
# --------------------------------------------------------------------------- #

@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    # Generic response returned on both success AND duplicate email to prevent
    # account enumeration. Only response differences are by design (message text).
    _GENERIC_OK = SignupResponse(
        message="Account created. Check your email to verify your address.",
    )
    try:
        user, verification_token = await auth_service.create_user(body.email, body.password, db)
    except ValueError as exc:
        if str(exc) == "EMAIL_TAKEN":
            # Respond identically to a successful signup to prevent email enumeration.
            # No user_id is leaked because the attacker doesn't have one to correlate.
            return _GENERIC_OK
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    try:
        await auth_email.send_verification_email(user.email, verification_token)
    except Exception:
        log.exception("Failed to send verification email | user_id=%s", user.id)
        # Don't fail the signup — user can re-request later

    # Return the same shape as the EMAIL_TAKEN branch (no user_id) so the
    # response body is byte-identical between a fresh signup and a duplicate
    # — preserving the enumeration guarantee documented on _GENERIC_OK.
    return _GENERIC_OK


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

@router.post("/login", dependencies=[Depends(_login_sustained)])
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    ip = _client_ip(request)
    ua = request.headers.get("User-Agent")
    # Item 30 — structured security event on every login attempt so ops
    # can compute auth-failure rates in the log aggregator without
    # querying AuthLoginAttempt. Emitted AFTER the try/except branches
    # below so the outcome ("success"/"failure") reflects the real code
    # path rather than a best-guess pre-check.
    from app.services.observability import log_security_event

    try:
        _, access_token, refresh_token = await auth_service.authenticate_user(
            body.email, body.password, body.totp_code, db, ip, ua
        )
    except ValueError as exc:
        code = str(exc)
        log_security_event(
            "auth.login_failed",
            outcome="failure" if not code.startswith("ACCOUNT_LOCKED") else "denied",
            ip_address=ip,
            # body.email is logged as a login *identifier*, not PII — it's
            # already in AuthLoginAttempt and is required to tie a failure
            # burst to a specific targeted account. The redactor leaves
            # "email" alone; if you add a credential-bearing field above,
            # the redactor WILL strip it.
            extra={"reason": code, "email": body.email},
        )
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
    log_security_event(
        "auth.login_succeeded",
        ip_address=ip,
        extra={"email": body.email},
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
    request: Request,
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
    # v43 / Item 23: stamp the enforcement timestamp inside the same
    # transaction as the audit row. ``totp_enable_confirm`` already set
    # ``totp_enabled=True`` + committed; re-load and patch in a second
    # commit. Nullable column + additive write means no migration risk.
    from datetime import datetime, timezone as _tz
    user = await db.get(AuthUser, current_user.id)
    if user and user.totp_enforced_at is None:
        user.totp_enforced_at = datetime.now(_tz.utc)
    # Security-sensitive: pair with auth.mfa_disabled so the audit trail
    # captures the full MFA lifecycle for compliance and incident review.
    await log_action(
        db,
        action="auth.mfa_enabled",
        actor_user_id=current_user.id,
        target_type="auth_user",
        target_id=str(current_user.id),
        request=request,
    )
    await db.commit()
    return {"message": "TOTP authentication is now enabled on your account."}


@router.post("/mfa/disable", status_code=status.HTTP_200_OK)
async def mfa_disable(
    body: TOTPDisableRequest,
    request: Request,
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
    # v43 / Item 23: clear the enforcement timestamp so a future re-enable
    # records a fresh activation time rather than resurrecting a stale one.
    user = await db.get(AuthUser, current_user.id)
    if user:
        user.totp_enforced_at = None
    # Security-sensitive: record that MFA was turned off so the user can spot
    # an attacker who compromised the password-only path.
    await log_action(
        db,
        action="auth.mfa_disabled",
        actor_user_id=current_user.id,
        target_type="auth_user",
        target_id=str(current_user.id),
        request=request,
    )
    await db.commit()
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
    body: PasswordResetConfirmSchema, request: Request, db: AsyncSession = Depends(get_db)
):
    try:
        user_id = await auth_service.confirm_password_reset(body.token, body.new_password, db)
    except ValueError as exc:
        code = str(exc)
        if code == "TOKEN_EXPIRED":
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Reset link has expired. Request a new one.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token.")
    # Security-sensitive: record successful password changes so a compromised
    # account's real owner can see unauthorised resets in their audit trail.
    if user_id is not None:
        await log_action(
            db,
            action="auth.password_reset",
            actor_user_id=user_id,
            target_type="auth_user",
            target_id=str(user_id),
            request=request,
        )
        await db.commit()
    return {"message": "Password updated successfully. You can now sign in."}


# --------------------------------------------------------------------------- #
# BankID — Swedish e-identification
# --------------------------------------------------------------------------- #
#
# Flow:
#   1. POST /bankid/init                    — open a BankID order
#   2. GET  /bankid/collect?orderRef=...    — poll until complete / failed
#
# The collect endpoint both relays the BankID status AND, on success,
# provisions / looks up the local account and returns the standard
# {access_token, refresh_token} pair.
#
# Rationale for an in-memory order store: BankID orders live ~30 s and
# we only need (qr_start_token, qr_start_secret, start_time) during
# the polling window. A DB table would work on multi-instance
# deployments — we'll migrate to Redis on the first horizontally-
# scaled environment.

import asyncio as _asyncio
import secrets as _secrets
import time as _time
from datetime import UTC as _UTC, datetime as _dt, timedelta as _td

from pydantic import BaseModel as _BaseModel, Field as _Field

from app.models.auth import AuthRefreshToken as _AuthRefreshToken
from app.services import bankid as _bankid
from app.services.auth_service import (
    _hash_password as _hash_pw,
    _hash_token as _hash_tok,
    _mint_access_token as _mint_access,
    _secure_token as _secure_tok,
    _REFRESH_TOKEN_EXPIRE_DAYS as _REFRESH_DAYS,
)

# orderRef -> {qr_start_token, qr_start_secret, start_time, claimed}
# ``claimed`` flips to True once a successful collect has issued tokens
# so a stolen orderRef can't be re-submitted by a racing client. We
# purge expired entries lazily on each access; BankID itself invalidates
# orders after 5 minutes.
_ORDER_TTL_S = 300  # 5 minutes — matches BankID server-side order expiry
_order_store: dict[str, dict] = {}
_order_store_lock = _asyncio.Lock()


async def _purge_expired_orders() -> None:
    cutoff = _time.time() - _ORDER_TTL_S
    async with _order_store_lock:
        dead = [k for k, v in _order_store.items() if v.get("start_time", 0) < cutoff]
        for k in dead:
            _order_store.pop(k, None)


class _BankIDInitResponse(_BaseModel):
    order_ref: str
    auto_start_token: str
    qr_data: str            # pre-computed t=0 frame
    qr_refresh_ms: int = 1000


class _BankIDCollectResponse(_BaseModel):
    status: str             # "pending" | "complete" | "failed"
    hint_code: str | None = None
    qr_data: str | None = None   # next QR frame during pending
    access_token: str | None = None
    refresh_token: str | None = None


@router.post("/bankid/init", response_model=_BankIDInitResponse)
async def bankid_init(request: Request, db: AsyncSession = Depends(get_db)):
    """Open a BankID auth order and return the ids the UI needs to drive
    the QR flicker + autostart on mobile."""
    from app.config import settings
    if not settings.BANKID_CLIENT_CERT_PATH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BankID is not configured on this environment.",
        )
    ip = _client_ip(request)
    try:
        body = await _bankid.init_auth(end_user_ip=ip)
    except _bankid.BankIDError as e:
        log.warning("bankid init failed ip=%s err=%s", ip, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="BankID service error",
        ) from e

    order_ref = body["orderRef"]
    qr_start_token = body["qrStartToken"]
    qr_start_secret = body["qrStartSecret"]
    auto_start_token = body["autoStartToken"]
    start_time = _time.time()

    await _purge_expired_orders()
    async with _order_store_lock:
        _order_store[order_ref] = {
            "qr_start_token": qr_start_token,
            "qr_start_secret": qr_start_secret,
            "start_time": start_time,
            "claimed": False,
            "ip": ip,
        }

    qr_data = _bankid.build_qr_data(
        qr_start_token=qr_start_token,
        qr_start_secret=qr_start_secret,
        start_time=start_time,
    )
    return _BankIDInitResponse(
        order_ref=order_ref,
        auto_start_token=auto_start_token,
        qr_data=qr_data,
    )


@router.get("/bankid/collect", response_model=_BankIDCollectResponse)
async def bankid_collect(
    orderRef: str,                                          # noqa: N803 — matches BankID field
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Poll BankID. On ``complete``, provision or look up the local
    account and mint Varuflow tokens."""
    from app.config import settings
    if not settings.BANKID_CLIENT_CERT_PATH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BankID is not configured on this environment.",
        )

    async with _order_store_lock:
        order = _order_store.get(orderRef)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown order")
    if order["claimed"]:
        # Replay protection — once tokens are issued the order ref is dead.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order already completed",
        )

    try:
        body = await _bankid.collect(order_ref=orderRef)
    except _bankid.BankIDError as e:
        log.warning("bankid collect failed order=%s err=%s", orderRef, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="BankID service error",
        ) from e

    status_s = body.get("status")
    hint_code = body.get("hintCode")

    if status_s == "pending":
        qr_data = _bankid.build_qr_data(
            qr_start_token=order["qr_start_token"],
            qr_start_secret=order["qr_start_secret"],
            start_time=order["start_time"],
        )
        return _BankIDCollectResponse(
            status="pending", hint_code=hint_code, qr_data=qr_data,
        )

    if status_s == "failed":
        async with _order_store_lock:
            _order_store.pop(orderRef, None)
        return _BankIDCollectResponse(status="failed", hint_code=hint_code)

    if status_s != "complete":
        # Unknown status — fail-closed rather than mint tokens.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unexpected BankID status",
        )

    # ── status == "complete" ──────────────────────────────────────────
    user_info = body.get("completionData", {}).get("user", {}) or {}
    raw_pnr = user_info.get("personalNumber")
    given_name = (user_info.get("givenName") or "").strip()
    surname = (user_info.get("surname") or "").strip()
    if not raw_pnr:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="BankID did not return a personalNumber",
        )
    try:
        pnr_hash = _bankid.hash_personnummer(raw_pnr)
    except _bankid.BankIDError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid personalNumber",
        ) from e

    # Look up existing account by personnummer hash first, then mint a
    # fresh one if this is a first-time BankID login. New accounts use
    # a synthetic email so unique constraints hold — BankID does not
    # return an email and we don't want to prompt the user for one
    # mid-auth flow.
    user = await db.scalar(
        select(AuthUser).where(AuthUser.personalnummer_hash == pnr_hash)
    )
    newly_created = False
    if user is None:
        synthetic_email = f"bankid+{pnr_hash[:16]}@users.varuflow.se"
        user = AuthUser(
            email=synthetic_email,
            # Password must be non-null per schema; hash a 64-byte random
            # value the user will never see. They can set a real password
            # later via /password/reset from their Varuflow email address
            # once we collect it during onboarding.
            hashed_password=_hash_pw(_secrets.token_hex(32)),
            is_email_verified=True,     # identity proven by BankID
            personalnummer_hash=pnr_hash,
        )
        db.add(user)
        await db.flush()
        newly_created = True

    # Mint tokens using the same pattern as the password login path so
    # /refresh and /me work identically for BankID-authenticated users.
    access_token = _mint_access(user)
    refresh_raw = _secure_tok()
    db.add(_AuthRefreshToken(
        user_id=user.id,
        token_hash=_hash_tok(refresh_raw),
        expires_at=_dt.now(_UTC) + _td(days=_REFRESH_DAYS),
        ip_address=order.get("ip"),
        user_agent=request.headers.get("User-Agent"),
    ))

    await log_action(
        db,
        action="BANKID_LOGIN",
        actor_user_id=user.id,
        target_type="auth_user",
        target_id=str(user.id),
        request=request,
        extra={
            "new_user": newly_created,
            "given_name": given_name or None,
            "surname": surname or None,
            "pnr_fragment": _bankid._mask_pnr(raw_pnr),
        },
    )
    await db.commit()

    async with _order_store_lock:
        if orderRef in _order_store:
            _order_store[orderRef]["claimed"] = True

    return _BankIDCollectResponse(
        status="complete",
        hint_code=hint_code,
        access_token=access_token,
        refresh_token=refresh_raw,
    )
