"""Pydantic v2 schemas for the standalone auth system."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# NIST SP 800-63B recommends 8+ chars with composition rules optional when
# combined with a breach-list check. We require 10 chars + an uppercase + a
# digit + a trivial denylist (top passwords). This is pragmatic B2B hygiene
# without demanding symbols (which often produce worse real-world passwords).
_WEAK_PASSWORDS = {
    "password",  "password1",  "welcome123", "qwerty",     "12345678",
    "123456789", "1234567890", "varuflow",   "varuflow1",  "admin1234",
    "letmein",   "abc12345",   "passw0rd",   "p@ssw0rd",   "iloveyou",
}


def _validate_password(v: str) -> str:
    if len(v) < 10:
        raise ValueError("Password must be at least 10 characters")
    # bcrypt silently truncates input at 72 bytes — anything past that is
    # NOT part of the hash. With multibyte characters (emojis, accented
    # letters, Cyrillic, …) a 30-character password can already exceed
    # 72 bytes. If we accept it, a user can log back in with just the
    # first 72 bytes of their password — equivalent to a silent password
    # downgrade. Reject early with a clear message instead.
    if len(v.encode("utf-8")) > 72:
        raise ValueError(
            "Password is too long for secure hashing. "
            "Please use 72 bytes or fewer (multibyte characters count as 2–4 bytes)."
        )
    if not any(c.isupper() for c in v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(c.islower() for c in v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in v):
        raise ValueError("Password must contain at least one digit")
    if v.lower() in _WEAK_PASSWORDS:
        raise ValueError("This password is too common — choose a stronger one")
    return v


# ── Signup ────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=10, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password(v)


class SignupResponse(BaseModel):
    message: str
    # user_id is intentionally optional — on duplicate‐email signup we return
    # the same success shape WITHOUT a user_id so an attacker can't enumerate
    # registered emails from the response body.
    user_id: Optional[uuid.UUID] = None


# ── Email Verification ─────────────────────────────────────────────────────────

class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=64, max_length=64)


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)
    totp_code: str | None = Field(None, min_length=6, max_length=8)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes in seconds


class MFARequiredResponse(BaseModel):
    mfa_required: bool = True
    message: str = "TOTP code required"


# ── Refresh ───────────────────────────────────────────────────────────────────

class RefreshRequest(BaseModel):
    # Cap refresh_token at 512 chars. `_secure_token()` produces a
    # URL-safe 32-byte random string (≈43 chars), so 512 is ample even
    # if we ever widen the token format. Without an upper bound an
    # abusive client could POST a multi-megabyte string — starlette
    # doesn't enforce a default body-size limit, the rate-limiter only
    # caps request count (30/min), and every request still has to JSON-
    # decode + hash the payload before we can reject it at the DB.
    refresh_token: str = Field(..., min_length=1, max_length=512)


# ── Logout ────────────────────────────────────────────────────────────────────

class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1, max_length=512)


# ── TOTP / MFA ────────────────────────────────────────────────────────────────

class TOTPEnableResponse(BaseModel):
    provisioning_uri: str
    message: str = "Scan the QR code with your authenticator app, then confirm with a TOTP code"


class TOTPConfirmRequest(BaseModel):
    totp_code: str = Field(..., min_length=6, max_length=8)


class TOTPDisableRequest(BaseModel):
    totp_code: str = Field(..., min_length=6, max_length=8)
    password: str = Field(..., min_length=1, max_length=128)


# ── Password Reset ────────────────────────────────────────────────────────────

class PasswordResetRequestSchema(BaseModel):
    email: EmailStr


class PasswordResetConfirmSchema(BaseModel):
    token: str = Field(..., min_length=64, max_length=64)
    new_password: str = Field(..., min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        # Apply the same strength + bcrypt 72-byte guard used at signup.
        # Without this, a reset could set a weak/denylisted password, or
        # a multibyte >72-byte password that bcrypt silently truncates
        # — the exact silent-downgrade the signup validator prevents.
        return _validate_password(v)


# ── Current User ──────────────────────────────────────────────────────────────

class AuthUserOut(BaseModel):
    id: uuid.UUID
    email: str
    is_email_verified: bool
    totp_enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}
