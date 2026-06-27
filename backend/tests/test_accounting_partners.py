"""Unit tests for accounting firm partner commission logic.

Tests cover pure helpers in app.services.partner_commissions.
No database or HTTP client required.
"""
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.partner_commissions import (
    calculate_commission,
    calculate_free_month_value,
    generate_operator_referral_code,
    generate_partner_code,
    is_commission_window_active,
)


# ── calculate_commission ──────────────────────────────────────────────────


def test_commission_25pct_month1():
    assert calculate_commission(500, 25, 1) == Decimal("125.00")


def test_commission_25pct_month6():
    assert calculate_commission(1200, 25, 6) == Decimal("300.00")


def test_commission_25pct_month12_still_active():
    """Month 12 is the last active month in the window."""
    assert calculate_commission(500, 25, 12) == Decimal("125.00")


def test_commission_month13_expired():
    """Month 13 is outside the 12-month window — must return zero."""
    assert calculate_commission(500, 25, 13) == Decimal("0.00")


def test_commission_month0_invalid():
    assert calculate_commission(500, 25, 0) == Decimal("0.00")


def test_commission_zero_subscription():
    assert calculate_commission(0, 25, 1) == Decimal("0.00")


def test_commission_20pct_of_800():
    assert calculate_commission(800, 20, 1) == Decimal("160.00")


def test_commission_25pct_of_10000():
    assert calculate_commission(10000, 25, 1) == Decimal("2500.00")


def test_commission_decimal_precision_333():
    """25% of 333 = 83.25 — rounding must be exact to two places."""
    result = calculate_commission(333, 25, 1)
    assert result == Decimal("83.25")
    # Ensure it is quantised (no extra trailing digits)
    assert result == result.quantize(Decimal("0.01"))


# ── is_commission_window_active ────────────────────────────────────────────


def test_window_active_month12():
    assert is_commission_window_active(12) is True


def test_window_active_month1():
    assert is_commission_window_active(1) is True


def test_window_inactive_month0():
    assert is_commission_window_active(0) is False


def test_window_inactive_negative():
    assert is_commission_window_active(-1) is False


# ── calculate_free_month_value ─────────────────────────────────────────────


def test_free_month_value_equals_subscription():
    assert calculate_free_month_value(750) == Decimal("750.00")


def test_free_month_value_zero():
    assert calculate_free_month_value(0) == Decimal("0.00")


# ── generate_partner_code ──────────────────────────────────────────────────


def test_partner_code_starts_with_partner():
    code = generate_partner_code("Svensson & Partners AB")
    assert code.startswith("PARTNER-")


def test_partner_code_with_special_chars():
    """Special characters in firm name must not crash code generation."""
    code = generate_partner_code("Firma Ö & Å / Räkenskaps-byrån")
    assert code.startswith("PARTNER-")


def test_partner_code_single_char_name():
    code = generate_partner_code("X")
    assert code.startswith("PARTNER-")


def test_partner_code_uniqueness():
    """At least 50 of 100 generated codes must be distinct."""
    codes = {generate_partner_code("TestFirm") for _ in range(100)}
    assert len(codes) >= 50


def test_partner_code_max_length():
    code = generate_partner_code("Svensson Bokföring och Redovisning AB Extra Long Name")
    assert len(code) <= 20


# ── generate_operator_referral_code ───────────────────────────────────────


def test_operator_code_starts_with_ref():
    code = generate_operator_referral_code("Acme AB")
    assert code.startswith("REF-")


def test_operator_code_no_spaces():
    code = generate_operator_referral_code("My Company AB")
    assert " " not in code


def test_operator_code_uniqueness():
    """At least 50 of 100 generated codes must be distinct."""
    codes = {generate_operator_referral_code("SameOrg") for _ in range(100)}
    assert len(codes) >= 50


def test_operator_code_max_length():
    code = generate_operator_referral_code("Very Long Organisation Name Inc")
    assert len(code) <= 15


def test_operator_code_empty_string():
    """Empty org name must not raise."""
    code = generate_operator_referral_code("")
    assert code.startswith("REF-")


# ── Integration logic (pure) ───────────────────────────────────────────────


def test_months_remaining_12_active_then_decrement_still_active():
    months_remaining = 12
    assert is_commission_window_active(months_remaining) is True
    months_remaining -= 1
    assert is_commission_window_active(months_remaining) is True


def test_months_remaining_1_active_then_decrement_to_0_inactive():
    months_remaining = 1
    assert is_commission_window_active(months_remaining) is True
    months_remaining -= 1
    assert is_commission_window_active(months_remaining) is False


def test_sum_of_12_months_at_25pct_500():
    """Total commission over full 12-month window: 12 × 125 = 1500."""
    total = sum(calculate_commission(500, 25, m) for m in range(1, 13))
    assert total == Decimal("1500.00")


def test_sum_of_12_months_at_20pct_500():
    """Total commission over full 12-month window at 20%: 12 × 100 = 1200."""
    total = sum(calculate_commission(500, 20, m) for m in range(1, 13))
    assert total == Decimal("1200.00")


def test_expired_months_yield_zero():
    """Months 13 and 14 are truly outside the window."""
    assert calculate_commission(500, 25, 13) + calculate_commission(500, 25, 14) == Decimal("0.00")
