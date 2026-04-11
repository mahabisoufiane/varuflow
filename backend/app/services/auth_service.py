"""Auth business logic — all crypto and DB operations for the standalone auth system.

Responsibilities:
  - Password hashing / verification (bcrypt, cost factor 12)
  - Secure random token generation (secrets.token_hex)
  - JWT access token minting + verification (RS256 not available here, HS256 with
    a strong secret is used — swap to RS256 by changing _ALGORITHM and loading a key pair)
  - Refresh token lifecycle (create, validate, revoke, rotate)
  - Account lockout after 5 failed attempts (15-minute window)
  - TOTP provisioning and verification (pyotp, TOTP window ±1 step)
  - Email verification token lifecycle
  - Password reset token lifecycle (1-hour expiry)
"""
import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pyotp
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.auth import AuthLoginAttempt, AuthRefreshToken, AuthUser

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Crypto primitives
# --------------------------------------------------------------------------- #

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

_ACCESS_TOKEN_EXPIRE_MINUTES = 15
_REFRESH_TOKEN_EXPIRE_DAYS = 7
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15
_EMAIL_VERIFY_EXPIRE_HOURS = 24
_PASSWORD_RESET_EXPIRE_HOURS = 1
_ALGORITHM = "HS256"


def _hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def _verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


def _secure_token() -> str:
    """Return a 64-character cryptographically secure hex token."""
    return secrets.token_hex(32)


def _hash_token(token: str) -> str:
    """SHA-256 hash for storing refresh tokens in DB (never store raw)."""
    return hashlib.sha256(token.encode()).hexdigest()


def _mint_access_token(user: AuthUser) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.AUTH_JWT_SECRET, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and verify an access token. Raises JWTError on failure."""
    payload = jwt.decode(token, settings.AUTH_JWT_SECRET, algorithms=[_ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Not an access token")
    return payload


# --------------------------------------------------------------------------- #
# Signup
# --------------------------------------------------------------------------- #

async def create_user(email: str, password: str, db: AsyncSession) -> AuthUser:
    email = email.lower().strip()
    existing = await db.scalar(select(AuthUser).where(AuthUser.email == email))
    if existing:
        # Constant-time response — don't reveal whether the email is taken
        raise ValueError("EMAIL_TAKEN")

    token = _secure_token()
    user = AuthUser(
        email=email,
        hashed_password=_hash_password(password),
        email_verification_token=token,
        email_verification_sent_at=datetime.now(UTC),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    log.info("User created | user_id=%s", user.id)
    return user


# --------------------------------------------------------------------------- #
# Email Verification
# --------------------------------------------------------------------------- #

async def verify_email(token: str, db: AsyncSession) -> AuthUser:
    user = await db.scalar(
        select(AuthUser).where(AuthUser.email_verification_token == token)
    )
    if not user:
        raise ValueError("INVALID_TOKEN")

    sent_at = user.email_verification_sent_at
    if sent_at is None:
        raise ValueError("INVALID_TOKEN")

    # Ensure timezone-aware comparison
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=UTC)

    if datetime.now(UTC) > sent_at + timedelta(hours=_EMAIL_VERIFY_EXPIRE_HOURS):
        raise ValueError("TOKEN_EXPIRED")

    user.is_email_verified = True
    user.email_verification_token = None
    user.email_verification_sent_at = None
    await db.commit()
    await db.refresh(user)
    return user


# --------------------------------------------------------------------------- #
# Login
# --------------------------------------------------------------------------- #

async def _log_attempt(
    db: AsyncSession,
    email: str,
    success: bool,
    ip: str,
    user_agent: str | None,
    user: AuthUser | None = None,
    reason: str | None = None,
) -> None:
    attempt = AuthLoginAttempt(
        user_id=user.id if user else None,
        email=email,
        ip_address=ip,
        user_agent=user_agent,
        success=success,
        failure_reason=reason,
    )
    db.add(attempt)
    await db.flush()


async def authenticate_user(
    email: str,
    password: str,
    totp_code: str | None,
    db: AsyncSession,
    ip: str,
    user_agent: str | None,
) -> tuple[AuthUser, str, str]:
    """Authenticate and return (user, access_token, refresh_token).

    Raises ValueError with reason codes on failure.
    """
    email = email.lower().strip()
    user = await db.scalar(select(AuthUser).where(AuthUser.email == email))

    if not user:
        # Don't reveal that the email doesn't exist
        await _log_attempt(db, email, False, ip, user_agent, reason="USER_NOT_FOUND")
        await db.commit()
        raise ValueError("INVALID_CREDENTIALS")

    # Lockout check
    if user.locked_until:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=UTC)
        if datetime.now(UTC) < locked_until:
            remaining = int((locked_until - datetime.now(UTC)).total_seconds() / 60) + 1
            await _log_attempt(db, email, False, ip, user_agent, user, "ACCOUNT_LOCKED")
            await db.commit()
            raise ValueError(f"ACCOUNT_LOCKED:{remaining}")

    # Password check
    if not _verify_password(password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= _MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now(UTC) + timedelta(minutes=_LOCKOUT_MINUTES)
            log.warning("Account locked | user_id=%s | ip=%s", user.id, ip)
        await _log_attempt(db, email, False, ip, user_agent, user, "BAD_PASSWORD")
        await db.commit()
        raise ValueError("INVALID_CREDENTIALS")

    # Email verification required
    if not user.is_email_verified:
        await _log_attempt(db, email, False, ip, user_agent, user, "EMAIL_NOT_VERIFIED")
        await db.commit()
        raise ValueError("EMAIL_NOT_VERIFIED")

    # TOTP check
    if user.totp_enabled:
        if not totp_code:
            # Signal to the client that MFA is required — not a hard failure yet
            raise ValueError("MFA_REQUIRED")
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(totp_code, valid_window=1):
            await _log_attempt(db, email, False, ip, user_agent, user, "BAD_TOTP")
            await db.commit()
            raise ValueError("INVALID_TOTP")

    # Success — reset counters
    user.failed_login_attempts = 0
    user.locked_until = None

    access_token = _mint_access_token(user)
    refresh_token_raw = _secure_token()

    rt = AuthRefreshToken(
        user_id=user.id,
        token_hash=_hash_token(refresh_token_raw),
        expires_at=datetime.now(UTC) + timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS),
        ip_address=ip,
        user_agent=user_agent,
    )
    db.add(rt)
    await _log_attempt(db, email, True, ip, user_agent, user)
    await db.commit()

    log.info("Login success | user_id=%s | ip=%s", user.id, ip)
    return user, access_token, refresh_token_raw


# --------------------------------------------------------------------------- #
# Refresh
# --------------------------------------------------------------------------- #

async def refresh_access_token(
    refresh_token_raw: str, db: AsyncSession
) -> tuple[str, str]:
    """Validate refresh token and issue a new access + refresh token pair (rotation).

    Returns (new_access_token, new_refresh_token).
    Old refresh token is revoked.
    """
    token_hash = _hash_token(refresh_token_raw)
    rt = await db.scalar(
        select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
    )

    if not rt or rt.revoked:
        raise ValueError("INVALID_REFRESH_TOKEN")

    expires_at = rt.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if datetime.now(UTC) > expires_at:
        raise ValueError("REFRESH_TOKEN_EXPIRED")

    user = await db.get(AuthUser, rt.user_id)
    if not user:
        raise ValueError("USER_NOT_FOUND")

    # Revoke old token
    rt.revoked = True

    # Issue new pair
    new_access = _mint_access_token(user)
    new_refresh_raw = _secure_token()
    new_rt = AuthRefreshToken(
        user_id=user.id,
        token_hash=_hash_token(new_refresh_raw),
        expires_at=datetime.now(UTC) + timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS),
        ip_address=rt.ip_address,
        user_agent=rt.user_agent,
    )
    db.add(new_rt)
    await db.commit()

    return new_access, new_refresh_raw


# --------------------------------------------------------------------------- #
# Logout
# --------------------------------------------------------------------------- #

async def revoke_refresh_token(refresh_token_raw: str, db: AsyncSession) -> None:
    token_hash = _hash_token(refresh_token_raw)
    rt = await db.scalar(
        select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
    )
    if rt and not rt.revoked:
        rt.revoked = True
        await db.commit()


# --------------------------------------------------------------------------- #
# TOTP / MFA
# --------------------------------------------------------------------------- #

async def totp_enable_initiate(user_id: uuid.UUID, db: AsyncSession) -> tuple[str, str]:
    """Generate a new TOTP secret. Returns (secret, provisioning_uri).

    Does NOT activate TOTP yet — caller must call totp_enable_confirm() with a valid code.
    """
    user = await db.get(AuthUser, user_id)
    if not user:
        raise ValueError("USER_NOT_FOUND")
    if user.totp_enabled:
        raise ValueError("TOTP_ALREADY_ENABLED")

    secret = pyotp.random_base32()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="Varuflow")

    # Store provisionally (not enabled until confirmed)
    user.totp_secret = secret
    user.totp_provisioning_uri = uri
    await db.commit()

    return secret, uri


async def totp_enable_confirm(
    user_id: uuid.UUID, totp_code: str, db: AsyncSession
) -> None:
    """Activate TOTP after user confirms with a valid code from their authenticator app."""
    user = await db.get(AuthUser, user_id)
    if not user or not user.totp_secret:
        raise ValueError("TOTP_NOT_INITIATED")
    if user.totp_enabled:
        raise ValueError("TOTP_ALREADY_ENABLED")

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(totp_code, valid_window=1):
        raise ValueError("INVALID_TOTP")

    user.totp_enabled = True
    await db.commit()
    log.info("TOTP enabled | user_id=%s", user_id)


async def totp_disable(
    user_id: uuid.UUID, password: str, totp_code: str, db: AsyncSession
) -> None:
    """Disable TOTP. Requires current password + valid TOTP code."""
    user = await db.get(AuthUser, user_id)
    if not user:
        raise ValueError("USER_NOT_FOUND")
    if not user.totp_enabled:
        raise ValueError("TOTP_NOT_ENABLED")
    if not _verify_password(password, user.hashed_password):
        raise ValueError("INVALID_PASSWORD")

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(totp_code, valid_window=1):
        raise ValueError("INVALID_TOTP")

    user.totp_enabled = False
    user.totp_secret = None
    user.totp_provisioning_uri = None
    await db.commit()
    log.info("TOTP disabled | user_id=%s", user_id)


# --------------------------------------------------------------------------- #
# Password Reset
# --------------------------------------------------------------------------- #

async def initiate_password_reset(email: str, db: AsyncSession) -> str | None:
    """Generate a reset token. Returns the token (caller sends email).

    Returns None if the email doesn't exist — caller must NOT reveal this to the client.
    """
    user = await db.scalar(select(AuthUser).where(AuthUser.email == email.lower().strip()))
    if not user:
        return None

    token = _secure_token()
    user.password_reset_token = token
    user.password_reset_expires_at = datetime.now(UTC) + timedelta(
        hours=_PASSWORD_RESET_EXPIRE_HOURS
    )
    await db.commit()
    return token


async def confirm_password_reset(
    token: str, new_password: str, db: AsyncSession
) -> None:
    user = await db.scalar(
        select(AuthUser).where(AuthUser.password_reset_token == token)
    )
    if not user:
        raise ValueError("INVALID_TOKEN")

    expires_at = user.password_reset_expires_at
    if expires_at is None:
        raise ValueError("INVALID_TOKEN")
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if datetime.now(UTC) > expires_at:
        raise ValueError("TOKEN_EXPIRED")

    user.hashed_password = _hash_password(new_password)
    user.password_reset_token = None
    user.password_reset_expires_at = None

    # Revoke all refresh tokens on password change
    rts = await db.scalars(
        select(AuthRefreshToken).where(
            AuthRefreshToken.user_id == user.id,
            AuthRefreshToken.revoked.is_(False),
        )
    )
    for rt in rts:
        rt.revoked = True

    await db.commit()
    log.info("Password reset complete | user_id=%s", user.id)
