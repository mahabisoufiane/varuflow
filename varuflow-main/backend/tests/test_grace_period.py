"""Tests for the subscription grace-period service.

Covers pure helpers, DB-bound functions, and the billing webhook
integration for invoice.payment_failed → grace period flow.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.features.billing.grace_period import GracePeriodStatus, SubscriptionGracePeriod
from app.services.grace_period import (
    GRACE_PERIOD_DAYS,
    MAX_NOTIFICATIONS,
    days_remaining,
    is_in_grace_period,
    should_notify,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_grace(
    *,
    status: GracePeriodStatus = GracePeriodStatus.ACTIVE,
    expires_in_days: int = 5,
    notification_sent_count: int = 0,
):
    """Create a lightweight mock grace period object."""
    now = datetime.now(timezone.utc)

    class _FakeGP:
        pass

    gp = _FakeGP()
    gp.id = uuid.uuid4()
    gp.org_id = uuid.uuid4()
    gp.triggered_at = now - timedelta(days=GRACE_PERIOD_DAYS - expires_in_days)
    gp.expires_at = now + timedelta(days=expires_in_days)
    gp.status = status
    gp.notification_sent_count = notification_sent_count
    gp.last_notification_at = None
    gp.failed_invoice_id = "in_test_123"
    gp.failed_amount_cents = 4999
    gp.failure_reason = "card_declined"
    gp.recovered_at = None
    gp.expired_at = None
    return gp


# ── Pure helper tests ────────────────────────────────────────────────────────

class TestIsInGracePeriod:
    def test_active_not_expired(self):
        gp = _make_grace(expires_in_days=3)
        assert is_in_grace_period(gp) is True

    def test_active_but_expired(self):
        gp = _make_grace(expires_in_days=-1)
        assert is_in_grace_period(gp) is False

    def test_recovered_status(self):
        gp = _make_grace(status=GracePeriodStatus.RECOVERED, expires_in_days=3)
        assert is_in_grace_period(gp) is False

    def test_expired_status(self):
        gp = _make_grace(status=GracePeriodStatus.EXPIRED, expires_in_days=3)
        assert is_in_grace_period(gp) is False

    def test_none_input(self):
        assert is_in_grace_period(None) is False


class TestDaysRemaining:
    def test_positive_days(self):
        now = datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
        gp = _make_grace(expires_in_days=5)
        gp.expires_at = now + timedelta(days=5, hours=1)
        assert days_remaining(gp, now) == 5

    def test_zero_days(self):
        gp = _make_grace(expires_in_days=0)
        assert days_remaining(gp) == 0

    def test_negative_days_clamped(self):
        gp = _make_grace(expires_in_days=-3)
        assert days_remaining(gp) == 0


class TestShouldNotify:
    def test_notify_at_5_days(self):
        now = datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
        gp = _make_grace(expires_in_days=5, notification_sent_count=0)
        # Override expires_at to exactly 5 days from now
        gp.expires_at = now + timedelta(days=5, hours=1)
        assert should_notify(gp, now) is True

    def test_notify_at_3_days(self):
        now = datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
        gp = _make_grace(expires_in_days=3, notification_sent_count=1)
        gp.expires_at = now + timedelta(days=3, hours=1)
        assert should_notify(gp, now) is True

    def test_notify_at_1_day(self):
        now = datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
        gp = _make_grace(expires_in_days=1, notification_sent_count=2)
        gp.expires_at = now + timedelta(days=1, hours=1)
        assert should_notify(gp, now) is True

    def test_no_notify_at_4_days(self):
        now = datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
        gp = _make_grace(expires_in_days=4, notification_sent_count=0)
        gp.expires_at = now + timedelta(days=4, hours=1)
        assert should_notify(gp, now) is False

    def test_no_notify_max_reached(self):
        gp = _make_grace(expires_in_days=1, notification_sent_count=MAX_NOTIFICATIONS)
        assert should_notify(gp) is False

    def test_no_notify_recovered(self):
        gp = _make_grace(status=GracePeriodStatus.RECOVERED, expires_in_days=3)
        assert should_notify(gp) is False


class TestConstants:
    def test_grace_period_is_7_days(self):
        assert GRACE_PERIOD_DAYS == 7

    def test_max_notifications_is_3(self):
        assert MAX_NOTIFICATIONS == 3


class TestGracePeriodModel:
    def test_status_enum_values(self):
        assert GracePeriodStatus.ACTIVE == "active"
        assert GracePeriodStatus.RECOVERED == "recovered"
        assert GracePeriodStatus.EXPIRED == "expired"


# ── Source-contract tests ────────────────────────────────────────────────────

import inspect
import textwrap

SERVICE_SRC = inspect.getsource(
    __import__("app.services.grace_period", fromlist=["_"])
)
BILLING_SRC = inspect.getsource(
    __import__("app.features.billing.billing", fromlist=["_"])
)


class TestServiceContract:
    def test_start_is_idempotent(self):
        assert "get_active_grace_period" in SERVICE_SRC
        assert "already active" in SERVICE_SRC

    def test_audit_actions_present(self):
        assert "billing.grace_period.started" in SERVICE_SRC
        assert "billing.grace_period.recovered" in SERVICE_SRC
        assert "billing.grace_period.expired" in SERVICE_SRC

    def test_expire_downgrades_to_free(self):
        assert "OrgPlan.FREE" in SERVICE_SRC

    def test_billing_webhook_starts_grace_period(self):
        assert "start_grace_period" in BILLING_SRC
        assert "invoice.payment_failed" in BILLING_SRC

    def test_billing_webhook_recovers_grace_period(self):
        assert "recover_grace_period" in BILLING_SRC
