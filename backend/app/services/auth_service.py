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

# Precomputed hash of a fixed dummy password used to equalise the
# "user not found" and "user exists with wrong password" code paths.
# Without this, bcrypt only runs when the user exists, and the ~300 ms
# timing difference lets an attacker enumerate registered emails.
# The plaintext is irrelevant \u2014 what matters is that _verify_password
# always performs one bcrypt comparison on every login attempt.
_DUMMY_BCRYPT_HASH = _pwd_ctx.hash("dummy-password-for-timing-equalisation")

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
        # Item 24: embed the user's current ``session_version`` so the
        # auth middleware can retire every outstanding token by simply
        # incrementing the column on a password reset. A missing claim
        # is treated as legacy-pass (see middleware/auth.verify_session_version)
        # — tokens minted before v44 keep working until they expire.
        "ver": user.session_version,
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

async def create_user(email: str, password: str, db: AsyncSession) -> tuple[AuthUser, str]:
    """Create a new user and return (user, raw_verification_token).

    Only the SHA-256 hash of the verification token is persisted, so a DB
    leak cannot be used to verify arbitrary accounts. The caller is
    responsible for emailing the raw token (which is never stored again).

    Re-signup recovery: if the email already exists but was never
    verified, we rotate the verification token and return it so the
    caller re-sends the email. Without this path, a user who lost the
    original verification email (inbox filtered it, Resend outage,
    24 h token expiry) had no way forward — login refused
    (EMAIL_NOT_VERIFIED), a second signup silently no-op'd, and there
    is no resend endpoint. Verified accounts still raise EMAIL_TAKEN
    so a signup attempt on someone else's live account can't be used
    to probe for password changes or lock them out.

    The new password from the retry signup is DISCARDED. Overwriting
    the stored hash here would let an attacker who knows the victim's
    email replace the password of any unverified account; the real
    email owner would then receive a verification link that — when
    clicked — activates an account whose password belongs to the
    attacker. The legitimate user who mistyped their original password
    can reach the forgot-password flow after verifying (or re-use the
    correct password they intended originally, since we never revealed
    which branch ran).
    """
    email = email.lower().strip()
    existing = await db.scalar(
        select(AuthUser).where(AuthUser.email == email).with_for_update()
    )
    if existing:
        if existing.is_email_verified:
            # Real conflict with a live account — preserve the
            # enumeration-resistant response at the router layer.
            raise ValueError("EMAIL_TAKEN")
        # Unverified existing account — rotate the verification token
        # only. Do NOT touch hashed_password (see docstring).
        token = _secure_token()
        existing.email_verification_token = _hash_token(token)
        existing.email_verification_sent_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(existing)
        log.info("User re-verification issued | user_id=%s", existing.id)
        return existing, token

    token = _secure_token()
    user = AuthUser(
        email=email,
        hashed_password=_hash_password(password),
        email_verification_token=_hash_token(token),
        email_verification_sent_at=datetime.now(UTC),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    log.info("User created | user_id=%s", user.id)
    return user, token


# --------------------------------------------------------------------------- #
# Email Verification
# --------------------------------------------------------------------------- #

async def verify_email(token: str, db: AsyncSession) -> AuthUser:
    token_hash = _hash_token(token)
    # FOR UPDATE so two concurrent clicks on the same magic link serialize —
    # the second transaction reloads after the first commits, sees the token
    # cleared, and raises INVALID_TOKEN cleanly instead of producing a
    # lost-update on is_email_verified or a spurious "verified twice" race.
    user = await db.scalar(
        select(AuthUser)
        .where(AuthUser.email_verification_token == token_hash)
        .with_for_update()
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
        # Run one dummy bcrypt verify so the response time matches the
        # "user exists, wrong password" branch. Without this, an attacker
        # can enumerate registered emails by measuring request latency
        # (bcrypt(cost=12) adds ~300 ms).
        _verify_password(password, _DUMMY_BCRYPT_HASH)
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
            # Count a wrong TOTP as a failed attempt so an attacker who has
            # the password cannot brute-force 6-digit codes indefinitely.
            # Shares the same counter + lockout threshold as bad passwords.
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= _MAX_FAILED_ATTEMPTS:
                user.locked_until = datetime.now(UTC) + timedelta(minutes=_LOCKOUT_MINUTES)
                log.warning("Account locked (TOTP) | user_id=%s | ip=%s", user.id, ip)
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
    # Lock the refresh-token row so two concurrent refreshes can't both
    # observe `revoked=False` and both mint a new token pair — which would
    # also defeat the reuse-detection trap below (the loser would think the
    # winner's revoke was a theft).
    rt = await db.scalar(
        select(AuthRefreshToken)
        .where(AuthRefreshToken.token_hash == token_hash)
        .with_for_update()
    )

    if not rt:
        raise ValueError("INVALID_REFRESH_TOKEN")

    # Reuse detection: a revoked token being presented again means either the
    # legitimate user is replaying an old token, or an attacker has stolen one.
    # Either way, the safe response is to revoke the entire session family so
    # the attacker loses access and the user is forced to re-authenticate.
    if rt.revoked:
        log.warning(  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
            "Refresh token reuse detected — revoking all tokens | user_id=%s",
            rt.user_id,
        )
        family = await db.scalars(
            select(AuthRefreshToken).where(
                AuthRefreshToken.user_id == rt.user_id,
                AuthRefreshToken.revoked.is_(False),
            )
        )
        for sibling in family:
            sibling.revoked = True
        await db.commit()
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
    """Disable TOTP. Requires current password + valid TOTP code.

    Mirrors the authenticate_user() lockout logic so a stolen access token
    cannot be used to brute-force the 6-digit TOTP (~10^6 codes) against
    this endpoint without triggering the same 5-attempts / 15-minute
    lockout that protects the login path.
    """
    user = await db.get(AuthUser, user_id)
    if not user:
        raise ValueError("USER_NOT_FOUND")
    if not user.totp_enabled:
        raise ValueError("TOTP_NOT_ENABLED")

    # Honour an existing lockout — an attacker who burned the counter on
    # /login shouldn't be able to retry on /mfa/disable.
    if user.locked_until:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=UTC)
        if datetime.now(UTC) < locked_until:
            raise ValueError("INVALID_PASSWORD")

    if not _verify_password(password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= _MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now(UTC) + timedelta(minutes=_LOCKOUT_MINUTES)
            log.warning("Account locked (mfa_disable/password) | user_id=%s", user_id)  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
        await db.commit()
        raise ValueError("INVALID_PASSWORD")

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(totp_code, valid_window=1):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= _MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now(UTC) + timedelta(minutes=_LOCKOUT_MINUTES)
            log.warning("Account locked (mfa_disable/totp) | user_id=%s", user_id)
        await db.commit()
        raise ValueError("INVALID_TOTP")

    user.totp_enabled = False
    user.totp_secret = None
    user.totp_provisioning_uri = None
    # Reset the counter on success so a legitimate user with a prior
    # typo isn't punished on their next login.
    user.failed_login_attempts = 0
    user.locked_until = None
    # Item 24: bump session_version to kill every live access token.
    # Disabling MFA lowers the security posture of the account, so we
    # force a re-login everywhere to ensure the user is physically
    # present for the change rather than a stolen token triggering it.
    user.session_version = (user.session_version or 1) + 1
    await db.commit()
    log.info("TOTP disabled | user_id=%s", user_id)


# --------------------------------------------------------------------------- #
# Password Reset
# --------------------------------------------------------------------------- #

async def initiate_password_reset(email: str, db: AsyncSession) -> str | None:
    """Generate a reset token. Returns the token (caller sends email).

    Returns None if the email doesn't exist — caller must NOT reveal this to the client.

    Security:
      • Only the SHA-256 hash is persisted; a DB leak cannot be used to reset
        live passwords. The raw token is returned once and never again.
      • 1-hour TTL.
      • Creating a new reset invalidates any previously-issued token for the
        same account (single-use rotation).
    """
    user = await db.scalar(select(AuthUser).where(AuthUser.email == email.lower().strip()))
    if not user:
        return None

    # Per-user throttle: if we issued a reset token less than 60 seconds ago
    # and it's still valid, silently no-op. Prevents an attacker who knows
    # a victim's email from flooding their inbox with reset links.
    now = datetime.now(UTC)
    if user.password_reset_expires_at is not None:
        expires_at = user.password_reset_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        issued_at = expires_at - timedelta(hours=_PASSWORD_RESET_EXPIRE_HOURS)
        if issued_at > now - timedelta(seconds=60):
            return None

    token = _secure_token()
    user.password_reset_token = _hash_token(token)
    user.password_reset_expires_at = now + timedelta(
        hours=_PASSWORD_RESET_EXPIRE_HOURS
    )
    await db.commit()
    return token


async def confirm_password_reset(
    token: str, new_password: str, db: AsyncSession
) -> uuid.UUID:
    """Consume the reset token and rotate the password. Returns the user's id
    so the router can attribute an audit-log entry to them.
    """
    token_hash = _hash_token(token)
    # FOR UPDATE so two concurrent confirms for the same token serialize.
    # Without the lock both transactions could observe a non-null
    # password_reset_token and both commit their own new password — the
    # second write silently overwrites the first. Matches the pattern
    # used in verify_email() above.
    user = await db.scalar(
        select(AuthUser)
        .where(AuthUser.password_reset_token == token_hash)
        .with_for_update()
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
    # A successful reset clears any prior lockout so the user can log in
    # immediately after resetting their password.
    user.failed_login_attempts = 0
    user.locked_until = None
    # Item 24: bump session_version so every access token minted before
    # this reset (including one already stolen by whoever triggered the
    # reset flow) is rejected on the next request — even though the TTL
    # hasn't expired. Refresh-token revocation below handles the long
    # tail; session_version handles the short tail.
    user.session_version = (user.session_version or 1) + 1

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
    log.info("Password reset complete | user_id=%s", user.id)  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
    return user.id
