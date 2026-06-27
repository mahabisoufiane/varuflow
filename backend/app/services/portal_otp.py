"""Pure helpers for portal OTP (Item 51).

Kept side-effect-free so they can be unit-tested without a database
or FastAPI. All I/O lives in the router.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

OTP_DIGITS = 6
OTP_TTL_SECONDS = 300  # 5 minutes
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 60


@dataclass(frozen=True)
class IssuedOtp:
    code: str
    code_hash: str
    expires_at: datetime


def _now(now: datetime | None = None) -> datetime:
    return now or datetime.now(timezone.utc)


def generate_code() -> str:
    """Return a zero-padded numeric OTP of length ``OTP_DIGITS``."""
    upper = 10 ** OTP_DIGITS
    n = secrets.randbelow(upper)
    return str(n).zfill(OTP_DIGITS)


def hash_code(code: str) -> str:
    """SHA-256 hex digest of the code. Never store the raw code."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def verify_code(code: str, code_hash: str) -> bool:
    """Constant-time comparison against the stored hash."""
    return hmac.compare_digest(hash_code(code), code_hash)


def issue_otp(now: datetime | None = None) -> IssuedOtp:
    now = _now(now)
    code = generate_code()
    return IssuedOtp(
        code=code,
        code_hash=hash_code(code),
        expires_at=now + timedelta(seconds=OTP_TTL_SECONDS),
    )


def is_expired(expires_at: datetime, now: datetime | None = None) -> bool:
    return _now(now) >= expires_at


def can_resend(last_created_at: datetime, now: datetime | None = None) -> bool:
    """True once the 60-sec cooldown since the last issue has elapsed."""
    return (_now(now) - last_created_at).total_seconds() >= OTP_RESEND_COOLDOWN_SECONDS


def attempts_exhausted(attempts: int) -> bool:
    return attempts >= OTP_MAX_ATTEMPTS
