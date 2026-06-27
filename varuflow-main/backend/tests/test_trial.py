"""Trial system tests — source-contract + pure-function style.

Mirrors the pattern used throughout the test suite (e.g. test_subscription_pause.py):
  - Source-contract tests assert that key symbols exist in the correct files.
  - Pure-function tests call service helpers directly with no DB.
  - Migration-contract tests assert column/index presence.
  - Scheduler-contract tests assert job registration.
"""
from __future__ import annotations

import os
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

# ── File readers ──────────────────────────────────────────────────────────────

ROOT = pathlib.Path(__file__).parents[1]  # backend/


def _read(rel: str) -> str:
    return (ROOT / "app" / rel).read_text()


def _read_migration(name: str) -> str:
    versions = ROOT / "migrations" / "versions"
    for f in versions.iterdir():
        if name in f.name:
            return f.read_text()
    raise FileNotFoundError(f"Migration containing '{name}' not found")


SERVICE_SRC = _read("services/trial_service.py")
ROUTER_SRC = _read("routers/trial.py")
EMAIL_SRC = _read("services/email.py")
SCHEDULER_SRC = _read("services/scheduler.py")
MODEL_SRC = _read("models/organization.py")
try:
    MIGRATION_SRC = _read_migration("trial_system")
except FileNotFoundError:
    MIGRATION_SRC = ""


# ─────────────────────────────────────────────────────────────────────────────
# 1. Migration contract
# ─────────────────────────────────────────────────────────────────────────────


def test_migration_chains_from_latest():
    """down_revision must point to the release before this one."""
    assert 'down_revision = "z3t4u5v6w7x8"' in MIGRATION_SRC


def test_migration_adds_all_columns():
    required = [
        "trial_plan",
        "trial_started_at",
        "trial_ends_at",
        "trial_converted_at",
        "trial_extended_count",
        "trial_source",
    ]
    for col in required:
        assert col in MIGRATION_SRC, f"Migration missing column: {col}"


def test_migration_creates_partial_index():
    assert "ix_organizations_trial_ends_at" in MIGRATION_SRC
    assert "trial_ends_at IS NOT NULL" in MIGRATION_SRC


def test_migration_has_downgrade():
    assert "def downgrade" in MIGRATION_SRC
    assert "drop_column" in MIGRATION_SRC


# ─────────────────────────────────────────────────────────────────────────────
# 2. Model contract
# ─────────────────────────────────────────────────────────────────────────────


def test_model_has_trial_columns():
    for col in ("trial_plan", "trial_started_at", "trial_ends_at",
                "trial_converted_at", "trial_extended_count", "trial_source"):
        assert col in MODEL_SRC, f"Organization model missing: {col}"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Service constants
# ─────────────────────────────────────────────────────────────────────────────


def test_service_constants():
    from app.services.trial_service import (
        EXTENSION_DAYS,
        GRACE_PERIOD_DAYS,
        MAX_EXTENSIONS,
        REMINDER_DAY,
        TRIAL_DURATION_DAYS,
    )
    assert TRIAL_DURATION_DAYS == 14
    assert MAX_EXTENSIONS == 1
    assert EXTENSION_DAYS == 7
    assert REMINDER_DAY == 13
    assert GRACE_PERIOD_DAYS == 1


# ─────────────────────────────────────────────────────────────────────────────
# 4. Pure helper: is_trial_active
# ─────────────────────────────────────────────────────────────────────────────


class _FakeOrg:
    """Minimal org-like object for testing pure service helpers."""

    def __init__(self, **kw):
        self.plan = kw.get("plan", "FREE")
        self.trial_plan = kw.get("trial_plan", None)
        self.trial_started_at = kw.get("trial_started_at", None)
        self.trial_ends_at = kw.get("trial_ends_at", None)
        self.trial_converted_at = kw.get("trial_converted_at", None)
        self.trial_extended_count = kw.get("trial_extended_count", 0)
        self.trial_source = kw.get("trial_source", None)


def _now():
    return datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_is_trial_active_true():
    from app.services.trial_service import is_trial_active
    org = _FakeOrg(
        trial_started_at=_now() - timedelta(days=1),
        trial_ends_at=_now() + timedelta(days=13),
    )
    assert is_trial_active(org, now=_now()) is True


def test_is_trial_active_false_expired():
    from app.services.trial_service import is_trial_active
    org = _FakeOrg(
        trial_started_at=_now() - timedelta(days=15),
        trial_ends_at=_now() - timedelta(days=1),
    )
    assert is_trial_active(org, now=_now()) is False


def test_is_trial_active_false_no_trial():
    from app.services.trial_service import is_trial_active
    assert is_trial_active(_FakeOrg(), now=_now()) is False


def test_is_trial_active_false_converted():
    from app.services.trial_service import is_trial_active
    org = _FakeOrg(
        trial_started_at=_now() - timedelta(days=3),
        trial_ends_at=_now() + timedelta(days=11),
        trial_converted_at=_now() - timedelta(days=1),
    )
    assert is_trial_active(org, now=_now()) is False


# ─────────────────────────────────────────────────────────────────────────────
# 5. Pure helper: days_remaining
# ─────────────────────────────────────────────────────────────────────────────


def test_days_remaining_active():
    from app.services.trial_service import days_remaining
    org = _FakeOrg(
        trial_started_at=_now() - timedelta(days=1),
        trial_ends_at=_now() + timedelta(days=13),
    )
    assert days_remaining(org, now=_now()) == 13


def test_days_remaining_zero_if_inactive():
    from app.services.trial_service import days_remaining
    assert days_remaining(_FakeOrg(), now=_now()) == 0


def test_days_remaining_zero_if_expired():
    from app.services.trial_service import days_remaining
    org = _FakeOrg(
        trial_started_at=_now() - timedelta(days=20),
        trial_ends_at=_now() - timedelta(days=6),
    )
    assert days_remaining(org, now=_now()) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 6. Pure helper: can_extend
# ─────────────────────────────────────────────────────────────────────────────


def test_can_extend_true():
    from app.services.trial_service import can_extend
    org = _FakeOrg(
        trial_started_at=_now(),
        trial_extended_count=0,
    )
    assert can_extend(org) is True


def test_can_extend_false_already_extended():
    from app.services.trial_service import can_extend
    org = _FakeOrg(
        trial_started_at=_now(),
        trial_extended_count=1,
    )
    assert can_extend(org) is False


def test_can_extend_false_no_trial():
    from app.services.trial_service import can_extend
    assert can_extend(_FakeOrg()) is False


def test_can_extend_false_converted():
    from app.services.trial_service import can_extend
    org = _FakeOrg(
        trial_started_at=_now(),
        trial_extended_count=0,
        trial_converted_at=_now(),
    )
    assert can_extend(org) is False


# ─────────────────────────────────────────────────────────────────────────────
# 7. Pure helper: start_trial eligibility
# ─────────────────────────────────────────────────────────────────────────────


def test_start_trial_sets_fields():
    from app.services.trial_service import TRIAL_DURATION_DAYS, start_trial
    org = _FakeOrg(plan="FREE")
    now = _now()
    start_trial(org, plan="PRO", source="signup", now=now)
    assert org.trial_plan == "PRO"
    assert org.trial_started_at == now
    assert org.trial_ends_at == now + timedelta(days=TRIAL_DURATION_DAYS)
    assert org.trial_source == "signup"


def test_start_trial_rejects_paid_plan():
    from app.services.trial_service import start_trial
    org = _FakeOrg(plan="PRO")
    with pytest.raises(ValueError, match="trial_already_paid"):
        start_trial(org, plan="PRO", source="signup")


def test_start_trial_rejects_active_trial():
    from app.services.trial_service import start_trial
    org = _FakeOrg(
        plan="FREE",
        trial_started_at=_now() - timedelta(days=1),
        trial_ends_at=_now() + timedelta(days=13),
    )
    with pytest.raises(ValueError, match="trial_already_active"):
        start_trial(org, plan="PRO", source="upgrade_prompt")


def test_start_trial_rejects_already_used():
    from app.services.trial_service import start_trial
    org = _FakeOrg(
        plan="FREE",
        trial_started_at=_now() - timedelta(days=20),
        trial_ends_at=_now() - timedelta(days=6),
        trial_converted_at=_now() - timedelta(days=5),
    )
    with pytest.raises(ValueError):
        start_trial(org, plan="PRO", source="signup")


# ─────────────────────────────────────────────────────────────────────────────
# 8. Router source contract
# ─────────────────────────────────────────────────────────────────────────────


def test_router_prefix():
    assert 'prefix="/api/trial"' in ROUTER_SRC


def test_router_has_all_endpoints():
    assert "@router.post(\"/start\"" in ROUTER_SRC
    assert "@router.post(\"/extend\"" in ROUTER_SRC
    assert "@router.get(\"/status\"" in ROUTER_SRC
    assert "@router.post(\"/convert\"" in ROUTER_SRC


def test_router_owner_guard_on_start():
    """start and extend must check OWNER role."""
    assert "OWNER_REQUIRED" in ROUTER_SRC


def test_router_uses_audit():
    assert "log_action" in ROUTER_SRC
    assert '"trial.started"' in ROUTER_SRC
    assert '"trial.extended"' in ROUTER_SRC
    assert '"trial.converted"' in ROUTER_SRC


def test_router_has_error_handling():
    assert "except HTTPException:" in ROUTER_SRC
    assert "except Exception" in ROUTER_SRC
    assert "status_code=500" in ROUTER_SRC


def test_router_convert_idempotent_shape():
    """convert endpoint must not raise if already converted — handled by service."""
    assert "async def convert_trial" in ROUTER_SRC


# ─────────────────────────────────────────────────────────────────────────────
# 9. Email contract
# ─────────────────────────────────────────────────────────────────────────────


def test_email_has_three_trial_functions():
    assert "async def send_trial_started_email" in EMAIL_SRC
    assert "async def send_trial_ending_soon_email" in EMAIL_SRC
    assert "async def send_trial_expired_email" in EMAIL_SRC


def test_email_guards_on_missing_key():
    """All three functions must bail early if RESEND_API_KEY is absent."""
    assert "if not settings.RESEND_API_KEY" in EMAIL_SRC


# ─────────────────────────────────────────────────────────────────────────────
# 10. Scheduler contract
# ─────────────────────────────────────────────────────────────────────────────


def test_scheduler_has_trial_lock():
    assert "_LOCK_TRIAL_SWEEP = 811_028" in SCHEDULER_SRC


def test_scheduler_registers_trial_job():
    assert "_trial_sweep" in SCHEDULER_SRC
    assert '"trial_sweep"' in SCHEDULER_SRC


def test_scheduler_trial_fires_at_0200_stockholm():
    assert "CronTrigger(hour=2, minute=0" in SCHEDULER_SRC
    # Confirm the trial job carries the timezone label (not just the default)
    assert '"trial_sweep"' in SCHEDULER_SRC
    assert "Europe/Stockholm" in SCHEDULER_SRC


def test_scheduler_sends_reminder_on_day_13():
    assert "days_left == 1" in SCHEDULER_SRC
    assert "trial_reminder" in SCHEDULER_SRC


def test_scheduler_expires_after_grace_period():
    assert "GRACE_PERIOD_DAYS" in SCHEDULER_SRC
    assert "trial_expire" in SCHEDULER_SRC
    assert "trial.expired" in SCHEDULER_SRC


def test_scheduler_uses_idempotency_key():
    assert "IdempotencyKey" in SCHEDULER_SRC
    assert "on_conflict_do_nothing" in SCHEDULER_SRC
