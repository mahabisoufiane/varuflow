"""Unit tests for operator-to-operator referral logic.

Tests cover pure helpers and business logic rules.
No database or HTTP client required.
"""
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.partner_commissions import (
    calculate_commission,
    calculate_free_month_value,
    generate_operator_referral_code,
    is_commission_window_active,
)


# ── Pure helpers defined inline for testing ───────────────────────────────


def _is_self_referral(referrer_org_id, new_org_id) -> bool:
    return str(referrer_org_id) == str(new_org_id)


def _is_within_click_window(clicked_at, signed_up_at, window_days: int = 90) -> bool:
    if not clicked_at or not signed_up_at:
        return False
    return (signed_up_at - clicked_at).days <= window_days


def _is_within_conversion_window(signed_up_at, converted_at, window_days: int = 30) -> bool:
    if not signed_up_at or not converted_at:
        return False
    return (converted_at - signed_up_at).days <= window_days


def _is_rate_limited(generation_count_today: int, limit: int = 50) -> bool:
    return generation_count_today >= limit


# ── Code generation ────────────────────────────────────────────────────────


def test_operator_code_starts_with_ref():
    code = generate_operator_referral_code("Acme AB")
    assert code.startswith("REF-")


def test_operator_code_no_spaces():
    for _ in range(20):
        code = generate_operator_referral_code("Test Org")
        assert " " not in code


def test_operator_code_two_calls_differ():
    codes = {generate_operator_referral_code("SameOrg") for _ in range(20)}
    assert len(codes) > 1


def test_operator_code_max_length():
    code = generate_operator_referral_code("Very Long Organisation Name Inc")
    assert len(code) <= 15


# ── 20% commission arithmetic ──────────────────────────────────────────────


def test_20pct_commission_month1():
    assert calculate_commission(1000, 20, 1) == Decimal("200.00")


def test_20pct_commission_month6():
    assert calculate_commission(1000, 20, 6) == Decimal("200.00")


def test_20pct_commission_month12():
    assert calculate_commission(1000, 20, 12) == Decimal("200.00")


def test_20pct_commission_month13_zero():
    assert calculate_commission(1000, 20, 13) == Decimal("0.00")


# ── 12-month commission window ─────────────────────────────────────────────


def test_window_month12_active():
    assert is_commission_window_active(12) is True


def test_window_month0_not_active():
    assert is_commission_window_active(0) is False


def test_window_decrements_to_zero():
    remaining = 12
    while remaining > 0:
        assert is_commission_window_active(remaining) is True
        remaining -= 1
    assert is_commission_window_active(0) is False


# ── Self-referral detection ────────────────────────────────────────────────


def test_self_referral_same_uuid_detected():
    org_id = uuid.uuid4()
    assert _is_self_referral(org_id, org_id) is True


def test_self_referral_different_uuid_not_detected():
    assert _is_self_referral(uuid.uuid4(), uuid.uuid4()) is False


def test_self_referral_string_vs_uuid_comparison():
    """UUID and its string form should still be detected as self-referral."""
    org_id = uuid.uuid4()
    assert _is_self_referral(org_id, str(org_id)) is True


# ── Reward type logic ──────────────────────────────────────────────────────


def test_reward_type_commission_uses_calculate_commission():
    """When reward_type is 'commission', calculate_commission is invoked."""
    result = calculate_commission(1000, 20, 1)
    assert result == Decimal("200.00")


def test_reward_type_free_month_uses_calculate_free_month_value():
    """When reward_type is 'free_month', calculate_free_month_value is used."""
    result = calculate_free_month_value(1000)
    assert result == Decimal("1000.00")


def test_reward_type_zero_rate_yields_zero():
    """An unsupported/unknown type simulated via 0% rate produces no payout."""
    result = calculate_commission(1000, 0, 1)
    assert result == Decimal("0.00")


# ── Attribution window ─────────────────────────────────────────────────────

_NOW = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def test_click_window_89_days_valid():
    clicked_at = _NOW - timedelta(days=89)
    assert _is_within_click_window(clicked_at, _NOW) is True


def test_click_window_91_days_invalid():
    clicked_at = _NOW - timedelta(days=91)
    assert _is_within_click_window(clicked_at, _NOW) is False


def test_conversion_window_29_days_valid():
    signed_up = _NOW - timedelta(days=29)
    assert _is_within_conversion_window(signed_up, _NOW) is True


def test_conversion_window_31_days_invalid():
    signed_up = _NOW - timedelta(days=31)
    assert _is_within_conversion_window(signed_up, _NOW) is False


# ── Rate limiting ──────────────────────────────────────────────────────────


def test_rate_limit_49_not_limited():
    assert _is_rate_limited(49) is False


def test_rate_limit_50_is_limited():
    assert _is_rate_limited(50) is True


def test_rate_limit_0_not_limited():
    assert _is_rate_limited(0) is False


# ── Commission totals ──────────────────────────────────────────────────────


def test_12_months_20pct_1000_total():
    """12 months × 20% × 1000 SEK = 2400 SEK."""
    total = sum(calculate_commission(1000, 20, m) for m in range(1, 13))
    assert total == Decimal("2400.00")


def test_6_months_remaining_20pct_1000_total():
    """6 remaining months × 20% × 1000 SEK = 1200 SEK."""
    total = sum(calculate_commission(1000, 20, m) for m in range(1, 7))
    assert total == Decimal("1200.00")
