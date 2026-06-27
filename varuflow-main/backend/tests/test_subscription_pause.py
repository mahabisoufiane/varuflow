"""Tests for subscription pause & resume (Item 50).

Pure + source-contract style, matching Items 28-49.

Required test names (spec):

* test_pause_subscription
* test_read_only_during_pause
* test_auto_resume_after_90_days
* test_manual_resume
* test_reminder_email_sent
* test_data_preserved_during_pause
* test_pause_history_recorded
* test_org_isolation
* test_audit_log
* test_cannot_pause_free_plan
"""
from __future__ import annotations

import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from app.services import subscription_pause as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"


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


BILLING_SRC = _read("routers/billing.py")
SERVICE_SRC = _read("services/subscription_pause.py")
MIDDLEWARE_SRC = _read("middleware/pause_guard.py")
MAIN_SRC = _read("main.py")
MODEL_SRC = _read("models/organization.py")
SCHEDULER_SRC = _read("services/scheduler.py")
EMAIL_SRC = _read("services/email.py")

_MIGRATIONS_DIR = _BACKEND_ROOT.parent / "migrations" / "versions"
_V61 = _MIGRATIONS_DIR / "c1d3e5f7a9b2_v61_subscription_pause.py"
MIGRATION_SRC = _V61.read_text() if _V61.exists() else ""


# ═══════════════════════════════════════════════════════════════════
# 1. test_pause_subscription
# ═══════════════════════════════════════════════════════════════════


def test_pause_subscription():
    # Pause endpoint exists, role-gated, accepts days + reason.
    assert '@router.post("/pause"' in BILLING_SRC
    assert "async def pause_subscription" in BILLING_SRC
    assert "class PauseCreate(BaseModel):" in BILLING_SRC
    assert "days: int" in BILLING_SRC
    assert "member.role not in (OrgRole.OWNER, OrgRole.ADMIN)" in BILLING_SRC
    # Sets pause state directly on org.
    assert "org.is_paused = True" in BILLING_SRC
    assert "org.paused_at = now" in BILLING_SRC
    # Creates a history row.
    assert "pause_row = SubscriptionPause(" in BILLING_SRC


# ═══════════════════════════════════════════════════════════════════
# 2. test_read_only_during_pause
# ═══════════════════════════════════════════════════════════════════


def test_read_only_during_pause():
    # Middleware exists and is registered in main.py.
    assert "class PauseWriteGuardMiddleware(BaseHTTPMiddleware)" in MIDDLEWARE_SRC
    assert "from app.middleware.pause_guard import PauseWriteGuardMiddleware" in MAIN_SRC
    assert "app.add_middleware(PauseWriteGuardMiddleware)" in MAIN_SRC
    # Blocks mutating methods; safe methods and resume path stay alive.
    assert '_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}' in MIDDLEWARE_SRC
    assert '"/api/billing/resume"' in MIDDLEWARE_SRC
    assert '"/api/billing/webhook"' in MIDDLEWARE_SRC
    assert "status_code=423" in MIDDLEWARE_SRC
    assert '"SUBSCRIPTION_PAUSED"' in MIDDLEWARE_SRC
    # Reads the hot flag on the organization row.
    assert "org.is_paused" in MIDDLEWARE_SRC


# ═══════════════════════════════════════════════════════════════════
# 3. test_auto_resume_after_90_days
# ═══════════════════════════════════════════════════════════════════


def test_auto_resume_after_90_days():
    # 90-day ceiling enforced at the service layer.
    assert svc.MAX_PAUSE_DAYS == 90
    with pytest.raises(ValueError):
        svc.validate_pause_duration(91)
    # Auto-resume predicate is timezone-safe and strictly past-due.
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    ends = now - timedelta(seconds=1)
    assert svc.should_auto_resume(ends, now=now) is True
    # Exactly at the boundary counts as "resume".
    assert svc.should_auto_resume(now, now=now) is True
    # Not yet elapsed — still paused.
    future = now + timedelta(days=1)
    assert svc.should_auto_resume(future, now=now) is False
    # Scheduler sweep handles the auto-resume path.
    assert "async def _subscription_pause_sweep" in SCHEDULER_SRC
    assert "should_auto_resume" in SCHEDULER_SRC
    assert '"auto_resume"' in SCHEDULER_SRC


# ═══════════════════════════════════════════════════════════════════
# 4. test_manual_resume
# ═══════════════════════════════════════════════════════════════════


def test_manual_resume():
    assert '@router.post("/resume"' in BILLING_SRC
    assert "async def resume_subscription" in BILLING_SRC
    # Idempotent — calling resume when not paused returns 409.
    assert "if not org.is_paused:" in BILLING_SRC
    # Clears pause state on org.
    assert "org.is_paused = False" in BILLING_SRC
    # Resume command builder hands Stripe an empty pause_collection.
    cmd = svc.build_resume_command("sub_123")
    assert cmd.pause_collection == {}
    assert cmd.subscription_id == "sub_123"
    # Closes the open history row with the resume reason.
    assert 'active_row.resume_reason = "manual"' in BILLING_SRC


# ═══════════════════════════════════════════════════════════════════
# 5. test_reminder_email_sent
# ═══════════════════════════════════════════════════════════════════


def test_reminder_email_sent():
    # 7-day window.
    assert svc.REMINDER_DAYS_BEFORE == 7
    # Predicate
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    # 5 days out → due.
    assert svc.is_reminder_due(now + timedelta(days=5), None, now=now) is True
    # 10 days out → not yet.
    assert svc.is_reminder_due(now + timedelta(days=10), None, now=now) is False
    # Already sent — never re-send.
    assert (
        svc.is_reminder_due(
            now + timedelta(days=3), reminder_sent_at=now, now=now
        )
        is False
    )
    # Already elapsed — don't send (auto-resume handles it).
    assert svc.is_reminder_due(now - timedelta(days=1), None, now=now) is False

    # Email function exists.
    assert "async def send_subscription_pause_reminder_email" in EMAIL_SRC
    # Scheduler calls it.
    assert "send_subscription_pause_reminder_email" in SCHEDULER_SRC
    # Sweep marks reminder_sent_at after sending.
    assert "org.pause_reminder_sent_at = now" in SCHEDULER_SRC


# ═══════════════════════════════════════════════════════════════════
# 6. test_data_preserved_during_pause
# ═══════════════════════════════════════════════════════════════════


def test_data_preserved_during_pause():
    # Migration adds columns but does NOT drop or alter data columns.
    # The pause flag is a plain boolean — no CASCADE DELETE on the
    # organization row, no data table is touched.
    assert 'add_column(\n        "organizations"' in MIGRATION_SRC
    assert '"is_paused"' in MIGRATION_SRC
    # No destructive statements in upgrade() path.
    assert "drop_column" not in MIGRATION_SRC.split("def downgrade")[0]
    assert "drop_table" not in MIGRATION_SRC.split("def downgrade")[0]
    # History table preserves pause windows even after resume — ended_at
    # is nullable, not a column drop.
    assert 'sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True)' in MIGRATION_SRC


# ═══════════════════════════════════════════════════════════════════
# 7. test_pause_history_recorded
# ═══════════════════════════════════════════════════════════════════


def test_pause_history_recorded():
    # History table model.
    assert "class SubscriptionPause(Base):" in MODEL_SRC
    assert '__tablename__ = "subscription_pauses"' in MODEL_SRC
    # Router inserts a row on pause.
    assert "pause_row = SubscriptionPause(" in BILLING_SRC
    assert "db.add(pause_row)" in BILLING_SRC
    # History listing endpoint exposes prior pauses.
    assert '@router.get("/pause/history", response_model=list[PauseHistoryOut])' in BILLING_SRC
    # Partial index on open pauses.
    assert "ix_subscription_pauses_active" in MIGRATION_SRC


# ═══════════════════════════════════════════════════════════════════
# 8. test_org_isolation
# ═══════════════════════════════════════════════════════════════════


def test_org_isolation():
    # Every authed endpoint filters by org_id from ctx, never trusts
    # client input.
    assert "org_id = _org(ctx)" in BILLING_SRC
    assert "SubscriptionPause.org_id == org_id" in BILLING_SRC
    # Owner/Admin gate on mutating endpoints.
    assert "member.role not in (OrgRole.OWNER, OrgRole.ADMIN)" in BILLING_SRC


# ═══════════════════════════════════════════════════════════════════
# 9. test_audit_log
# ═══════════════════════════════════════════════════════════════════


def test_audit_log():
    assert '"billing.pause"' in BILLING_SRC
    assert '"billing.resume"' in BILLING_SRC
    # Both mutations pass target type for audit trail.
    assert 'target_type="organization"' in BILLING_SRC
    assert 'org_id=org_id' in BILLING_SRC


# ═══════════════════════════════════════════════════════════════════
# 10. test_cannot_pause_free_plan
# ═══════════════════════════════════════════════════════════════════


def test_cannot_pause_free_plan():
    # Pure plan-eligibility check.
    assert svc.can_pause_plan("FREE") is False
    assert svc.can_pause_plan("free") is False
    assert svc.can_pause_plan("") is False
    assert svc.can_pause_plan(None) is False  # type: ignore[arg-type]
    assert svc.can_pause_plan("PRO") is True
    assert svc.can_pause_plan("ENTERPRISE") is True
    # Pause endpoint is gated to Owner/Admin roles.
    assert "member.role not in (OrgRole.OWNER, OrgRole.ADMIN)" in BILLING_SRC


# ═══════════════════════════════════════════════════════════════════
# Invariants
# ═══════════════════════════════════════════════════════════════════


def test_migration_chains_from_v60():
    assert 'revision = "c1d3e5f7a9b2"' in MIGRATION_SRC
    assert 'down_revision = "b9c2d4e6f8a1"' in MIGRATION_SRC


def test_organization_columns_added():
    # All five new columns are declared on the Organization model.
    for col in (
        "is_paused:",
        "paused_at:",
        "pause_ends_at:",
        "pause_reminder_sent_at:",
        "stripe_subscription_id:",
    ):
        assert col in MODEL_SRC, f"missing column {col}"
    # And the migration creates each one.
    for col in (
        '"is_paused"',
        '"paused_at"',
        '"pause_ends_at"',
        '"pause_reminder_sent_at"',
        '"stripe_subscription_id"',
    ):
        assert col in MIGRATION_SRC, f"missing migration column {col}"


def test_validate_pause_duration_pure():
    # Boundary
    assert svc.validate_pause_duration(1) == 1
    assert svc.validate_pause_duration(90) == 90
    with pytest.raises(ValueError):
        svc.validate_pause_duration(0)
    with pytest.raises(ValueError):
        svc.validate_pause_duration(91)
    with pytest.raises(ValueError):
        svc.validate_pause_duration("abc")  # type: ignore[arg-type]


def test_compute_pause_end_pure():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert svc.compute_pause_end(30, now=now) == now + timedelta(days=30)
    # Naive input is coerced to UTC.
    naive = datetime(2026, 1, 1)
    end = svc.compute_pause_end(7, now=naive)
    assert end.tzinfo is not None
    assert end.tzinfo.utcoffset(end) == timedelta(0)


def test_build_pause_command_pure():
    cmd = svc.build_pause_command("sub_abc")
    # Stripe-specific shape: behavior=void so no invoices generated.
    assert cmd.subscription_id == "sub_abc"
    assert cmd.pause_collection == {"behavior": "void"}
    with pytest.raises(ValueError):
        svc.build_pause_command("")


def test_scheduler_job_registered():
    assert "_LOCK_SUBSCRIPTION_PAUSE_SWEEP = 811_024" in SCHEDULER_SRC
    assert "async def _subscription_pause_sweep" in SCHEDULER_SRC
    assert 'id="subscription_pause_sweep"' in SCHEDULER_SRC
    assert 'CronTrigger(hour=10, minute=0, timezone="Europe/Stockholm")' in SCHEDULER_SRC


def test_pause_status_endpoint():
    # Status endpoint is GET (always safe, even when paused).
    assert '@router.get("/pause/status", response_model=PauseStatusOut)' in BILLING_SRC
    assert "days_remaining" in BILLING_SRC
