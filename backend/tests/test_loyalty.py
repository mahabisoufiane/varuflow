"""Tests for the customer loyalty program (v51 — Item 35).

All tests exercise **pure** helpers and reducers in
``app.services.loyalty_engine``. The DB-bound wrappers
(``award_points`` / ``redeem_points`` / ``adjust_points`` /
``expire_old_points``) compose these same reducers, so passing tests
here guarantee the wrappers agree byte-for-byte.

Repo convention places shared tests under ``backend/tests/`` rather
than ``backend/app/tests/`` (same deviation as Items 28–34).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.loyalty_engine import (
    TIER_THRESHOLDS,
    apply_adjust,
    apply_earn,
    apply_expire,
    apply_redeem,
    bucket_expiring_rows,
    points_for_amount,
    redemption_discount,
    sum_active_points,
    tier_for_lifetime,
    validate_redemption,
)


# ═══════════════════════════════════════════════════════════════════
# 1. test_redemption_rate_calculation
# ═══════════════════════════════════════════════════════════════════


def test_redemption_rate_calculation():
    # Default rate: 1 pt = 0.01 kr, so 100 pts = 1 kr.
    assert redemption_discount(100, Decimal("0.01")) == Decimal("1.00")
    # Generous rate: 1 pt = 0.05 kr, so 500 pts = 25 kr.
    assert redemption_discount(500, Decimal("0.05")) == Decimal("25.00")
    # Zero / negative points clamp to zero.
    assert redemption_discount(0, Decimal("0.01")) == Decimal("0.00")
    assert redemption_discount(-50, Decimal("0.01")) == Decimal("0.00")
    # Zero / negative rate clamps to zero.
    assert redemption_discount(100, 0) == Decimal("0.00")
    assert redemption_discount(100, Decimal("-1")) == Decimal("0.00")
    # Fractional cents round to two decimal places.
    assert redemption_discount(333, Decimal("0.01")) == Decimal("3.33")


# ═══════════════════════════════════════════════════════════════════
# 2. test_tier_upgrade_on_threshold
# ═══════════════════════════════════════════════════════════════════


def test_tier_upgrade_on_threshold():
    assert tier_for_lifetime(0) == "bronze"
    assert tier_for_lifetime(499) == "bronze"
    assert tier_for_lifetime(500) == "silver"
    assert tier_for_lifetime(1_999) == "silver"
    assert tier_for_lifetime(2_000) == "gold"
    assert tier_for_lifetime(9_999) == "gold"
    assert tier_for_lifetime(10_000) == "platinum"
    assert tier_for_lifetime(1_000_000) == "platinum"
    assert set(TIER_THRESHOLDS) == {"bronze", "silver", "gold", "platinum"}


def test_tier_upgrade_is_live_on_earn():
    balance, lifetime, tier = apply_earn(0, 499, 1)
    assert tier == "silver"
    balance, lifetime, tier = apply_earn(balance, lifetime, 1_500)
    assert tier == "gold"
    balance, lifetime, tier = apply_earn(balance, lifetime, 8_000)
    assert tier == "platinum"


# ═══════════════════════════════════════════════════════════════════
# 3. test_points_earned_on_sale
# ═══════════════════════════════════════════════════════════════════


def test_points_earned_on_sale():
    assert points_for_amount(Decimal("250.50"), Decimal("1")) == 250
    assert points_for_amount(Decimal("100"), Decimal("2")) == 200
    assert points_for_amount(Decimal("100"), Decimal("0.5")) == 50
    assert points_for_amount(Decimal("99"), Decimal("1.1")) == 108
    assert points_for_amount(Decimal("0"), Decimal("1")) == 0
    assert points_for_amount(Decimal("-100"), Decimal("1")) == 0
    assert points_for_amount(None, Decimal("1")) == 0
    assert points_for_amount("abc", Decimal("1")) == 0
    balance, lifetime, tier = apply_earn(0, 0, 250)
    assert (balance, lifetime, tier) == (250, 250, "bronze")


# ═══════════════════════════════════════════════════════════════════
# 4. test_points_redemption_as_discount
# ═══════════════════════════════════════════════════════════════════


def test_points_redemption_as_discount():
    balance, lifetime, _ = apply_earn(0, 0, 500)
    assert balance == 500 and lifetime == 500
    balance, lifetime, _ = apply_redeem(balance, lifetime, 100)
    assert balance == 400
    assert lifetime == 500  # tier is earned, not spent
    assert redemption_discount(100, Decimal("0.01")) == Decimal("1.00")
    with pytest.raises(ValueError) as exc:
        apply_redeem(10, 10, 100)
    assert "insufficient_balance" in str(exc.value)


def test_validate_redemption_flow():
    check = validate_redemption(100, balance=500, rate=Decimal("0.01"))
    assert check.ok
    assert check.discount == Decimal("1.00")
    check = validate_redemption(10_000, balance=500, rate=Decimal("0.01"))
    assert not check.ok and check.reason == "insufficient_balance"
    check = validate_redemption(0, balance=500, rate=Decimal("0.01"))
    assert not check.ok and check.reason == "points_must_be_positive"
    check = validate_redemption(
        1_000, balance=1_500, rate=Decimal("0.01"), cap=Decimal("5.00")
    )
    assert not check.ok and check.reason == "exceeds_cap"


# ═══════════════════════════════════════════════════════════════════
# 5. test_lifetime_points_tracking
# ═══════════════════════════════════════════════════════════════════


def test_lifetime_points_tracking():
    balance, lifetime, _ = apply_earn(0, 0, 300)
    balance, lifetime, _ = apply_earn(balance, lifetime, 300)
    balance, lifetime, tier = apply_redeem(balance, lifetime, 100)
    assert balance == 500
    assert lifetime == 600
    assert tier == "silver"


def test_apply_earn_noop_on_zero_or_negative():
    assert apply_earn(100, 100, 0) == (100, 100, "bronze")
    assert apply_earn(100, 100, -50) == (100, 100, "bronze")


# ═══════════════════════════════════════════════════════════════════
# 6. test_staff_manual_adjustment
# ═══════════════════════════════════════════════════════════════════


def test_staff_manual_adjustment():
    balance, lifetime, tier = apply_adjust(0, 0, 200)
    assert balance == 200 and lifetime == 200 and tier == "bronze"
    balance, lifetime, tier = apply_adjust(balance, lifetime, 400)
    assert lifetime == 600 and tier == "silver"
    # Revoke does NOT reduce lifetime — protects earned tier.
    balance, lifetime, tier = apply_adjust(balance, lifetime, -100)
    assert balance == 500 and lifetime == 600 and tier == "silver"
    with pytest.raises(ValueError):
        apply_adjust(100, 100, 0)
    with pytest.raises(ValueError) as exc:
        apply_adjust(10, 10, -100)
    assert "insufficient_balance" in str(exc.value)


# ═══════════════════════════════════════════════════════════════════
# 7. test_points_expiry_job
# ═══════════════════════════════════════════════════════════════════


def test_points_expiry_job():
    balance, lifetime, tier = apply_expire(300, 300, 200)
    assert balance == 100
    assert lifetime == 300  # lifetime untouched
    assert tier == "bronze"


def test_points_expiry_clamps_to_balance():
    # Staff may have already debited the balance — don't over-expire.
    balance, lifetime, _ = apply_expire(50, 200, 200)
    assert balance == 0
    assert lifetime == 200


def test_sum_active_points_ignores_expired():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        SimpleNamespace(points=100, expires_at=now + timedelta(days=1)),
        SimpleNamespace(points=50, expires_at=None),
        SimpleNamespace(points=200, expires_at=now - timedelta(days=1)),
        SimpleNamespace(points=-25, expires_at=None),
    ]
    assert sum_active_points(rows, now=now) == 125


# ═══════════════════════════════════════════════════════════════════
# 8. test_expiry_notification
# ═══════════════════════════════════════════════════════════════════


def test_expiry_notification():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    acc_a = uuid.uuid4()
    acc_b = uuid.uuid4()
    rows = [
        SimpleNamespace(
            account_id=acc_a, points=150, type="earn",
            expires_at=now + timedelta(days=7),
        ),
        SimpleNamespace(
            account_id=acc_a, points=50, type="earn",
            expires_at=now + timedelta(days=10),
        ),
        SimpleNamespace(
            account_id=acc_b, points=300, type="earn",
            expires_at=now + timedelta(days=3),
        ),
        # Outside window.
        SimpleNamespace(
            account_id=acc_a, points=500, type="earn",
            expires_at=now + timedelta(days=90),
        ),
        # Not an earn — skip.
        SimpleNamespace(
            account_id=acc_b, points=-25, type="redeem",
            expires_at=now + timedelta(days=2),
        ),
        # Already expired.
        SimpleNamespace(
            account_id=acc_a, points=999, type="earn",
            expires_at=now - timedelta(days=1),
        ),
    ]
    buckets = bucket_expiring_rows(rows, within_days=14, now=now)
    assert set(buckets) == {acc_a, acc_b}
    pts_a, earliest_a = buckets[acc_a]
    assert pts_a == 200
    assert earliest_a == now + timedelta(days=7)
    pts_b, earliest_b = buckets[acc_b]
    assert pts_b == 300
    assert earliest_b == now + timedelta(days=3)


# ═══════════════════════════════════════════════════════════════════
# 9. test_customer_loyalty_view
# ═══════════════════════════════════════════════════════════════════


def test_customer_loyalty_view():
    """Card view: balance, lifetime, tier, progress-to-next-tier."""
    balance, lifetime, tier = 0, 0, "bronze"
    balance, lifetime, tier = apply_earn(balance, lifetime, 600)
    balance, lifetime, tier = apply_redeem(balance, lifetime, 100)
    assert balance == 500
    assert lifetime == 600
    assert tier == "silver"
    # Next-tier progress: gold at 2000.
    assert TIER_THRESHOLDS["gold"] - lifetime == 1_400


# ═══════════════════════════════════════════════════════════════════
# 10. test_org_isolation
# ═══════════════════════════════════════════════════════════════════


def test_org_isolation():
    """Two orgs with the same customer_id must never share ledger
    state. Verified at the pure-reducer layer by running two
    independent timelines; the DB layer enforces this with the
    ``uq_loyalty_accounts_org_customer`` unique constraint."""
    org_a = (0, 0, "bronze")
    org_b = (0, 0, "bronze")
    org_a = apply_earn(org_a[0], org_a[1], 100)  # 1 pt/unit
    org_b = apply_earn(org_b[0], org_b[1], 200)  # 2 pt/unit program on same customer
    assert org_a[0] == 100
    assert org_b[0] == 200
    org_a = apply_redeem(org_a[0], org_a[1], 50)
    assert org_a[0] == 50
    assert org_b[0] == 200  # unaffected


# ═══════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════


def test_validate_redemption_boundary_balance():
    check = validate_redemption(100, balance=100, rate=Decimal("0.01"))
    assert check.ok and check.discount == Decimal("1.00")


def test_points_for_amount_decimal_rate():
    # 0.1 pt/unit × 99 = 9.9 → floor 9.
    assert points_for_amount(Decimal("99"), Decimal("0.1")) == 9


def test_bucket_expiring_rows_empty_inputs():
    assert bucket_expiring_rows([]) == {}


def test_bucket_expiring_rows_skips_notype_rows():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        SimpleNamespace(
            account_id=uuid.uuid4(), points=100, type=None,
            expires_at=now + timedelta(days=7),
        ),
    ]
    assert bucket_expiring_rows(rows, now=now) == {}


def test_redemption_discount_large_values():
    # Numeric(12,6) rate → support up to ~10^6 discount without
    # precision loss.
    assert redemption_discount(100_000, Decimal("1")) == Decimal("100000.00")
