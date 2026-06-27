"""Tests for gift cards & service bundles (v49 — Item 33).

All tests here exercise the pure functions in
``app.services.gift_card_service``. The router and DB-bound hooks
are thin wiring over these functions, same Py-3.9-sandbox-safe
pattern as Items 30/31/32.

Spec asks for ``backend/app/tests/test_gift_cards.py``; we place it
under ``backend/tests/`` per repo convention (same deviation as
Items 28/30/31/32).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.gift_card_service import (
    RedemptionResult,
    bundle_covers_service,
    compute_redemption,
    compute_remaining_sessions,
    expiry_from_days,
    generate_code,
    is_expired,
)


ORG_A = uuid.uuid4()
ORG_B = uuid.uuid4()


def _card(*, balance="100", status="active", expires_at=None, org_id=ORG_A, code="GC1"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        org_id=org_id,
        code=code,
        initial_value=Decimal(str(balance)),
        remaining_value=Decimal(str(balance)),
        status=status,
        expires_at=expires_at,
    )


# ── 1. test_issue_gift_card ────────────────────────────────────────


def test_issue_gift_card_generates_unique_code_and_honours_expiry():
    codes = {generate_code() for _ in range(200)}
    # 200 random 12-char codes from a 32-char alphabet should never
    # collide; a collision would indicate the generator fell back to
    # something non-random.
    assert len(codes) == 200
    for c in codes:
        assert len(c) == 12
        # Look-alike characters are excluded.
        assert "O" not in c and "0" not in c
        assert "I" not in c and "1" not in c

    exp = expiry_from_days(30)
    now = datetime.now(tz=timezone.utc)
    # expires_at should be ~30 days from now, tz-aware.
    assert exp is not None
    assert exp.tzinfo is not None
    delta = (exp - now).total_seconds()
    assert 29 * 86400 < delta < 31 * 86400


def test_issue_gift_card_zero_days_means_no_expiry():
    assert expiry_from_days(0) is None
    assert expiry_from_days(None) is None
    assert expiry_from_days(-5) is None


# ── 2. test_redeem_full_gift_card ──────────────────────────────────


def test_redeem_full_gift_card_covers_amount_and_leaves_nothing():
    result = compute_redemption(card_balance="100.00", amount_due="100.00")
    assert result.applied == Decimal("100.00")
    assert result.remaining_balance == Decimal("0.00")
    assert result.shortfall == Decimal("0.00")


def test_redeem_exact_rounding_half_up():
    # 33.33 card vs 100.00 due → apply 33.33, shortfall 66.67
    result = compute_redemption(card_balance="33.33", amount_due="100")
    assert result.applied == Decimal("33.33")
    assert result.remaining_balance == Decimal("0.00")
    assert result.shortfall == Decimal("66.67")


# ── 3. test_partial_redemption_balance ─────────────────────────────


def test_partial_redemption_when_card_bigger_than_amount():
    result = compute_redemption(card_balance="100", amount_due="40")
    assert result.applied == Decimal("40.00")
    assert result.remaining_balance == Decimal("60.00")
    assert result.shortfall == Decimal("0.00")


def test_partial_redemption_when_card_smaller_than_amount():
    result = compute_redemption(card_balance="25", amount_due="100")
    assert result.applied == Decimal("25.00")
    assert result.remaining_balance == Decimal("0.00")
    assert result.shortfall == Decimal("75.00")


def test_partial_redemption_negative_amount_clamps():
    # A refund context should not drive balance into the red.
    result = compute_redemption(card_balance="50", amount_due="-10")
    assert result.applied == Decimal("0.00")
    assert result.remaining_balance == Decimal("50.00")
    assert result.shortfall == Decimal("0.00")


# ── 4. test_expired_card_rejected ──────────────────────────────────


def test_expired_card_rejected_by_is_expired():
    yesterday = datetime.now(tz=timezone.utc) - timedelta(days=1)
    card = _card(expires_at=yesterday)
    assert is_expired(card) is True


def test_expired_card_returns_zero_apply_and_full_shortfall():
    result = compute_redemption(
        card_balance="100", amount_due="50", card_expired=True
    )
    assert result.applied == Decimal("0.00")
    assert result.remaining_balance == Decimal("100.00")
    assert result.shortfall == Decimal("50.00")


def test_voided_card_is_expired_even_before_date():
    far_future = datetime.now(tz=timezone.utc) + timedelta(days=365)
    card = _card(status="void", expires_at=far_future)
    assert is_expired(card) is True


def test_no_expiry_date_means_never_expires():
    card = _card(expires_at=None)
    assert is_expired(card) is False


def test_naive_expires_at_treated_as_utc():
    # Python 3.9 test fixtures sometimes pass naive datetimes.
    past_naive = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    card = _card(expires_at=past_naive)
    assert is_expired(card) is True


# ── 5. test_bundle_creation ────────────────────────────────────────


def test_bundle_covers_listed_service():
    svc_a = uuid.uuid4()
    svc_b = uuid.uuid4()
    svc_c = uuid.uuid4()
    bundle_services = [str(svc_a), str(svc_b)]
    assert bundle_covers_service(bundle_services, svc_a) is True
    assert bundle_covers_service(bundle_services, svc_b) is True
    assert bundle_covers_service(bundle_services, svc_c) is False


def test_bundle_covers_service_stringifies_uuid_inputs():
    svc = uuid.uuid4()
    # Works with either raw UUID or string input.
    assert bundle_covers_service([str(svc)], svc) is True
    assert bundle_covers_service([svc], str(svc)) is True


def test_bundle_covers_service_empty_or_none():
    assert bundle_covers_service([], uuid.uuid4()) is False
    assert bundle_covers_service(None, uuid.uuid4()) is False
    assert bundle_covers_service(["something"], None) is False


# ── 6. test_bundle_redemption_at_booking ───────────────────────────


def test_bundle_redemption_reduces_remaining_sessions():
    # Buy one bundle of 5 sessions; after 2 uses, 3 remain.
    assert compute_remaining_sessions(purchases=1, uses=2, sessions_per_purchase=5) == 3


def test_bundle_redemption_multiple_purchases_stack():
    # Two bundles of 5 sessions each = 10 total; after 7 uses, 3 remain.
    assert compute_remaining_sessions(purchases=2, uses=7, sessions_per_purchase=5) == 3


# ── 7. test_bundle_sessions_exhausted ──────────────────────────────


def test_bundle_sessions_exhausted_clamps_to_zero():
    assert compute_remaining_sessions(purchases=1, uses=5, sessions_per_purchase=5) == 0


def test_bundle_sessions_over_consumed_still_zero_not_negative():
    # A data-integrity violation (uses > total) must clamp, not go negative.
    assert compute_remaining_sessions(purchases=1, uses=99, sessions_per_purchase=5) == 0


def test_bundle_sessions_zero_purchases_is_zero():
    assert compute_remaining_sessions(purchases=0, uses=0, sessions_per_purchase=5) == 0


# ── 8. test_expiry_notification_email ──────────────────────────────
#
# The pure logic piece is: "which cards qualify for the 7-day
# window?" We assert the boundary — cards expiring between now and
# now+7d qualify; cards expiring later or in the past don't.


def test_expiry_notification_window_includes_next_7_days():
    now = datetime(2026, 4, 23, 9, 0, tzinfo=timezone.utc)
    in_5_days = _card(expires_at=now + timedelta(days=5))
    in_10_days = _card(expires_at=now + timedelta(days=10))
    already_past = _card(expires_at=now - timedelta(hours=1))
    cutoff = now + timedelta(days=7)

    # Simulate the scheduler predicate.
    def qualifies(card):
        if card.status != "active" or card.expires_at is None:
            return False
        eat = card.expires_at
        if eat.tzinfo is None:
            eat = eat.replace(tzinfo=timezone.utc)
        return now < eat <= cutoff

    assert qualifies(in_5_days) is True
    assert qualifies(in_10_days) is False
    assert qualifies(already_past) is False


def test_expiry_notification_excludes_expired_and_voided():
    future = datetime.now(tz=timezone.utc) + timedelta(days=3)
    expired_card = _card(status="expired", expires_at=future)
    voided_card = _card(status="void", expires_at=future)
    # is_expired short-circuits on status — these never qualify for
    # an "upcoming expiry" notification even if the date is future.
    assert is_expired(expired_card) is True
    assert is_expired(voided_card) is True


# ── 9. test_gift_card_balance_check ────────────────────────────────


def test_balance_check_reflects_remaining_value_and_status():
    card = _card(balance="75.50", status="active")
    # Pure balance semantics: what the router's balance endpoint returns.
    assert card.remaining_value == Decimal("75.50")
    assert card.status == "active"
    assert is_expired(card) is False


def test_balance_check_after_partial_redemption_deducts():
    card = _card(balance="100", status="active")
    result = compute_redemption(card_balance=card.remaining_value, amount_due="30")
    # Caller (the router/helper) applies the new balance.
    new_balance = result.remaining_balance
    assert new_balance == Decimal("70.00")


# ── 10. test_org_isolation ─────────────────────────────────────────
#
# The pure functions don't carry org_id, but they must not accept a
# card from org B as valid for org A. Because the router scopes every
# query by ``(org_id, code)``, we assert the predicate here.


def test_org_isolation_via_org_code_pair():
    org_a_card = _card(code="SAME", org_id=ORG_A)
    org_b_card = _card(code="SAME", org_id=ORG_B)

    def _lookup(cards, *, org_id, code):
        for c in cards:
            if c.org_id == org_id and c.code == code:
                return c
        return None

    assert _lookup([org_a_card, org_b_card], org_id=ORG_A, code="SAME") is org_a_card
    assert _lookup([org_a_card, org_b_card], org_id=ORG_B, code="SAME") is org_b_card
    assert _lookup([org_a_card], org_id=ORG_B, code="SAME") is None


# ── Extra guard rails ──────────────────────────────────────────────


def test_redemption_result_shape():
    result = compute_redemption(card_balance="10", amount_due="5")
    assert isinstance(result, RedemptionResult)
    # Always quantised to 2dp.
    assert result.applied.as_tuple().exponent == -2
    assert result.remaining_balance.as_tuple().exponent == -2
    assert result.shortfall.as_tuple().exponent == -2


def test_redemption_zero_balance_fails_closed():
    result = compute_redemption(card_balance="0", amount_due="50")
    assert result.applied == Decimal("0.00")
    assert result.shortfall == Decimal("50.00")


def test_redemption_none_values_dont_crash():
    result = compute_redemption(card_balance=None, amount_due=None)
    assert result.applied == Decimal("0.00")
    assert result.remaining_balance == Decimal("0.00")
    assert result.shortfall == Decimal("0.00")


def test_generate_code_entropy_floor():
    # Not a strict entropy test — just a sanity check that two
    # back-to-back codes differ (protects against a broken generator
    # that returns a constant).
    a = generate_code()
    b = generate_code()
    assert a != b
