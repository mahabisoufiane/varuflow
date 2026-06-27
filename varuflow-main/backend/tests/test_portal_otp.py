"""Item 51 — Portal OTP (Two-Factor Auth for Customer Portal).

Pure + source-contract tests matching the Items 28–50 style: unit-test
the side-effect-free helpers directly, then assert that the router,
model, migration, and email wiring are present in source.
"""
from __future__ import annotations

import pathlib
import time
from datetime import datetime, timedelta, timezone

import pytest

from app.services import portal_otp as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(relpath: str) -> str:
    _p = _BACKEND_ROOT / relpath
    if _p.is_file():
        return _p.read_text()
    # Path was split into a feature package (e.g. routers/invoicing/);
    # concatenate its modules so source-string assertions still hold.
    _pkg = _p.with_suffix("")
    if _pkg.is_dir():
        return "".join(_f.read_text() for _f in sorted(_pkg.rglob("*.py")))
    return _p.read_text()


ROUTER_SRC = _read("app/features/portal/portal.py")
MODEL_SRC = _read("app/features/portal/portal_otp.py")
SERVICE_SRC = _read("app/services/portal_otp.py")
EMAIL_SRC = _read("app/services/email.py")

_V62 = _BACKEND_ROOT / "migrations" / "versions" / "d2e4f6a8b0c3_v62_portal_otp.py"
MIGRATION_SRC = _V62.read_text() if _V62.exists() else ""


# ── Required 10 tests ──────────────────────────────────────────────────────


def test_otp_issue():
    """OTP issue endpoint + pure generator produce a 6-digit code and hash."""
    assert '@router.post("/auth/otp/request"' in ROUTER_SRC
    assert "async def request_portal_otp" in ROUTER_SRC
    issued = svc.issue_otp()
    assert len(issued.code) == 6 and issued.code.isdigit()
    assert issued.code_hash != issued.code
    assert len(issued.code_hash) == 64  # sha256 hex


def test_otp_verify():
    """verify_code returns True for the right code, False otherwise."""
    assert '@router.post("/auth/otp/verify"' in ROUTER_SRC
    assert "async def verify_portal_otp" in ROUTER_SRC
    issued = svc.issue_otp()
    assert svc.verify_code(issued.code, issued.code_hash) is True
    assert svc.verify_code("000000", issued.code_hash) is False


def test_otp_expiry():
    """Codes are valid 5 min and expire past that window."""
    assert svc.OTP_TTL_SECONDS == 300
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert svc.is_expired(past) is True
    future = datetime.now(timezone.utc) + timedelta(seconds=60)
    assert svc.is_expired(future) is False


def test_otp_replay_protection():
    """Router consumes the token on success so it cannot be re-used."""
    # Verify path flips consumed=True + used_at before minting the JWT.
    assert "token_row.consumed = True" in ROUTER_SRC
    assert "token_row.used_at = now" in ROUTER_SRC
    # Replay query excludes consumed rows.
    assert "PortalOtpToken.consumed == False" in ROUTER_SRC


def test_otp_hashed_at_rest():
    """The raw code must never be persisted — only the sha256 hash."""
    assert "code_hash" in MODEL_SRC
    assert "hashlib.sha256" in SERVICE_SRC
    # Model has no plain `code` column.
    assert 'mapped_column(String(' in MODEL_SRC
    assert ' code: Mapped[str] ' not in MODEL_SRC


def test_otp_max_attempts():
    """5 wrong guesses consume the token."""
    assert svc.OTP_MAX_ATTEMPTS == 5
    assert svc.attempts_exhausted(5) is True
    assert svc.attempts_exhausted(4) is False
    assert "attempts_exhausted" in ROUTER_SRC
    assert "token_row.attempts += 1" in ROUTER_SRC


def test_otp_resend_cooldown():
    """60-sec cooldown between re-issues."""
    assert svc.OTP_RESEND_COOLDOWN_SECONDS == 60
    recent = datetime.now(timezone.utc) - timedelta(seconds=10)
    assert svc.can_resend(recent) is False
    old = datetime.now(timezone.utc) - timedelta(seconds=120)
    assert svc.can_resend(old) is True
    assert "can_resend" in ROUTER_SRC


def test_otp_constant_time_compare():
    """verify_code uses hmac.compare_digest to avoid timing leaks."""
    assert "hmac.compare_digest" in SERVICE_SRC


def test_otp_audit_logged():
    """All mutation paths log_action()."""
    assert 'action="portal_otp.sent"' in ROUTER_SRC
    assert 'action="portal_otp.verified"' in ROUTER_SRC
    assert 'action="portal_otp.failed"' in ROUTER_SRC


def test_otp_email_enumeration_defense():
    """OTP request returns sent even when no customer matches."""
    # The early return with status="sent" when customers list is empty.
    assert 'OtpRequestResponse(status="sent")' in ROUTER_SRC
    assert "email_norm" in ROUTER_SRC


# ── Invariants ─────────────────────────────────────────────────────────────


def test_migration_v62_chains_from_v61():
    assert MIGRATION_SRC, "v62 migration missing"
    assert 'revision = "d2e4f6a8b0c3"' in MIGRATION_SRC
    assert 'down_revision = "c1d3e5f7a9b2"' in MIGRATION_SRC
    assert "portal_otp_tokens" in MIGRATION_SRC


def test_model_registered():
    assert "class PortalOtpToken(Base):" in MODEL_SRC
    assert '__tablename__ = "portal_otp_tokens"' in MODEL_SRC


def test_email_helper_wired():
    assert "async def send_portal_otp_email" in EMAIL_SRC
    assert "send_portal_otp_email" in ROUTER_SRC


def test_generate_code_pure():
    seen = {svc.generate_code() for _ in range(50)}
    # With 50 draws from 10**6 space, collision probability is negligible;
    # if we're getting a tight cluster something is wrong.
    assert len(seen) > 40
    for code in seen:
        assert len(code) == 6 and code.isdigit()


def test_verify_rejects_wrong_length():
    """Router validates code shape before DB lookup."""
    assert 'not code.isdigit() or len(code) != otp_svc.OTP_DIGITS' in ROUTER_SRC
