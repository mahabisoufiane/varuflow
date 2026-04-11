"""Pydantic v2 schemas for the standalone auth system."""
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Signup ────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class SignupResponse(BaseModel):
    message: str
    user_id: uuid.UUID


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
    refresh_token: str = Field(..., min_length=1)


# ── Logout ────────────────────────────────────────────────────────────────────

class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


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
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


# ── Current User ──────────────────────────────────────────────────────────────

class AuthUserOut(BaseModel):
    id: uuid.UUID
    email: str
    is_email_verified: bool
    totp_enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}
