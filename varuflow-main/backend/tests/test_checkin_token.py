"""Item 58 — Self-service booking check-in tokens.

Pure + source-contract tests. Follows Items 51-57 style.
"""
from __future__ import annotations

import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from app.services import checkin_token as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(p: str) -> str:
    _p = _BACKEND_ROOT / p
    if _p.is_file():
        return _p.read_text()
    # Path was split into a feature package (e.g. routers/invoicing/);
    # concatenate its modules so source-string assertions still hold.
    _pkg = _p.with_suffix("")
    if _pkg.is_dir():
        return "".join(_f.read_text() for _f in sorted(_pkg.rglob("*.py")))
    return _p.read_text()


MIGRATION_SRC = _read(
    "migrations/versions/c7e9a1b3d5f8_v67_checkin_tokens.py"
)
MODEL_SRC = _read("app/models/checkin_token.py")
SERVICE_SRC = _read("app/services/checkin_token.py")
ROUTER_SRC = _read("app/features/bookings/bookings.py")
MAIN_SRC = _read("app/main.py")


UTC = timezone.utc


def _dt(h: int = 12, m: int = 0, *, day: int = 15) -> datetime:
    return datetime(2026, 5, day, h, m, tzinfo=UTC)


# ── Pure service ──────────────────────────────────────────────────────────


def test_mint_token_returns_plaintext_hash_and_expiry():
    now = _dt(12)
    m = svc.mint_token(now=now, ttl=timedelta(hours=1))
    assert len(m.plaintext) >= 40  # urlsafe base64 of 32 bytes
    assert len(m.token_hash) == svc.TOKEN_HASH_HEX_LEN
    assert m.expires_at == now + timedelta(hours=1)


def test_mint_token_produces_unique_values():
    now = _dt(12)
    a = svc.mint_token(now=now)
    b = svc.mint_token(now=now)
    assert a.plaintext != b.plaintext
    assert a.token_hash != b.token_hash


def test_mint_token_rejects_nonpositive_ttl():
    with pytest.raises(ValueError):
        svc.mint_token(now=_dt(12), ttl=timedelta(0))
    with pytest.raises(ValueError):
        svc.mint_token(now=_dt(12), ttl=timedelta(seconds=-1))


def test_hash_token_is_stable_and_rejects_empty():
    h1 = svc.hash_token("abc")
    h2 = svc.hash_token("abc")
    h3 = svc.hash_token("abd")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == svc.TOKEN_HASH_HEX_LEN
    with pytest.raises(ValueError):
        svc.hash_token("")


def test_verify_hash_matches_constant_time():
    m = svc.mint_token(now=_dt(12))
    assert svc.verify_hash_matches(m.plaintext, m.token_hash)
    assert not svc.verify_hash_matches(m.plaintext + "x", m.token_hash)
    assert not svc.verify_hash_matches("", m.token_hash)
    assert not svc.verify_hash_matches(m.plaintext, "")
    # Wrong-length hash rejected outright
    assert not svc.verify_hash_matches(m.plaintext, "deadbeef")


def _state(*, appt_start=None, appt_end=None, used_at=None, expires_at=None):
    appt_start = appt_start or _dt(12)
    appt_end = appt_end or _dt(13)
    expires_at = expires_at or _dt(14)
    return svc.CheckinState(
        expires_at=expires_at,
        used_at=used_at,
        appointment_start=appt_start,
        appointment_end=appt_end,
    )


def test_is_valid_now_happy_path():
    ok, reason = svc.is_valid_now(_state(), _dt(12, 10))
    assert (ok, reason) == (True, "ok")


def test_is_valid_now_rejects_already_used():
    s = _state(used_at=_dt(12, 5))
    assert svc.is_valid_now(s, _dt(12, 10)) == (False, "already_used")


def test_is_valid_now_rejects_expired():
    s = _state(expires_at=_dt(11))
    assert svc.is_valid_now(s, _dt(12)) == (False, "expired")


def test_is_valid_now_rejects_too_early():
    # Booking tomorrow, trying today — outside EARLY_CHECKIN_WINDOW.
    s = _state(appt_start=_dt(12, day=16), appt_end=_dt(13, day=16),
               expires_at=_dt(14, day=16))
    assert svc.is_valid_now(s, _dt(12))[1] == "too_early"


def test_is_valid_now_rejects_too_late():
    # Appt finished 3 h ago, past LATE_CHECKIN_WINDOW (2 h).
    s = _state(appt_start=_dt(9), appt_end=_dt(10))
    assert svc.is_valid_now(s, _dt(12, 30))[1] == "too_late"


# ── Migration + model ─────────────────────────────────────────────────────


def test_migration_v67_chains_from_v66():
    assert 'revision = "c7e9a1b3d5f8"' in MIGRATION_SRC
    assert 'down_revision = "b6d8f0a2c4e7"' in MIGRATION_SRC
    assert "appointment_checkin_tokens" in MIGRATION_SRC
    assert "token_hash" in MIGRATION_SRC
    # The token hash must be uniquely indexed so a collision can
    # never let one ticket collide with another.
    assert "unique=True" in MIGRATION_SRC
    # Appointments gain a customer-facing timestamp.
    assert "checked_in_at" in MIGRATION_SRC


def test_model_stores_only_hash_not_plaintext():
    assert "token_hash" in MODEL_SRC
    # No column holds the plaintext token — only the hash.
    assert "plaintext:" not in MODEL_SRC
    assert "String(64)" in MODEL_SRC
    assert "used_at" in MODEL_SRC


# ── Router source-contract ────────────────────────────────────────────────


def test_router_mint_and_public_redeem_registered():
    assert '@router.post(\n    "/appointments/{appointment_id}/checkin-token"' in ROUTER_SRC
    assert 'public_checkin_router = APIRouter(' in ROUTER_SRC
    assert '@public_checkin_router.post("/checkin"' in ROUTER_SRC
    # public_checkin_router is wired directly as _bookings_public_checkin_router in main.py
    assert "_bookings_public_checkin_router" in MAIN_SRC
    assert "bookings_router" in MAIN_SRC


def test_router_mint_is_tenant_scoped_and_logged():
    assert "appt.org_id != member.org_id" in ROUTER_SRC
    assert '"appointment.checkin_token_minted"' in ROUTER_SRC


def test_router_redeem_is_generic_on_failure():
    # All failure paths return the same 404 + "Invalid or expired token"
    # so a timing/response attacker can't tell which state a token is
    # in. Expect at least 4 raises (unknown, mismatch, no appt, bad
    # window).
    assert ROUTER_SRC.count('Invalid or expired token') >= 4


def test_router_redeem_logs_success_and_rejection():
    assert '"appointment.checked_in"' in ROUTER_SRC
    assert '"appointment.checkin_rejected"' in ROUTER_SRC


def test_router_redeem_uses_constant_time_verify():
    assert "verify_hash_matches" in ROUTER_SRC
    assert "is_valid_now" in ROUTER_SRC


def test_router_mint_rejects_cancelled_or_no_show():
    assert '"cancelled"' in ROUTER_SRC
    assert '"no_show"' in ROUTER_SRC
    assert "Cannot mint token for" in ROUTER_SRC
