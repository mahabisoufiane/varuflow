"""Tests for the hard plan limits enforcement system.

Run with:
    cd backend && python -m pytest tests/test_plan_limits.py -v --noconftest

All tests are pure source-contract or pure-function — no DB fixtures needed.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Source helpers
# ---------------------------------------------------------------------------

BACKEND = Path(__file__).parent.parent / "app"


def _src(relative: str) -> str:
    return (BACKEND / relative).read_text()


# ---------------------------------------------------------------------------
# 1. plan_limits.py — module constants
# ---------------------------------------------------------------------------

class TestPlanLimitsModule:
    """The pure plan_limits service must expose the right constants and structure."""

    def _import(self):
        spec_path = BACKEND / "services" / "plan_limits.py"
        spec = importlib.util.spec_from_file_location("plan_limits", spec_path)
        mod = importlib.util.module_from_spec(spec)
        import sys as _sys
        _sys.modules["plan_limits"] = mod
        spec.loader.exec_module(mod)
        return mod

    def setup_method(self):
        self.pl = self._import()

    # ── PLAN_LIMITS dict ──────────────────────────────────────────────────────

    def test_free_plan_limits_present(self):
        assert "FREE" in self.pl.PLAN_LIMITS

    def test_pro_plan_limits_present(self):
        assert "PRO" in self.pl.PLAN_LIMITS

    def test_enterprise_plan_limits_present(self):
        assert "ENTERPRISE" in self.pl.PLAN_LIMITS

    def test_free_max_users(self):
        assert self.pl.PLAN_LIMITS["FREE"]["max_users"] == 3

    def test_pro_max_users(self):
        assert self.pl.PLAN_LIMITS["PRO"]["max_users"] == 20

    def test_enterprise_max_users_unlimited(self):
        assert self.pl.PLAN_LIMITS["ENTERPRISE"]["max_users"] == -1

    def test_free_max_products(self):
        assert self.pl.PLAN_LIMITS["FREE"]["max_products"] == 500

    def test_pro_max_products(self):
        assert self.pl.PLAN_LIMITS["PRO"]["max_products"] == 5_000

    def test_free_ai_calls_zero(self):
        """FREE plan has no AI call allowance — value is 0, not -1."""
        assert self.pl.PLAN_LIMITS["FREE"]["ai_calls_per_day"] == 0

    def test_pro_ai_calls(self):
        assert self.pl.PLAN_LIMITS["PRO"]["ai_calls_per_day"] == 100

    def test_enterprise_ai_calls_unlimited(self):
        assert self.pl.PLAN_LIMITS["ENTERPRISE"]["ai_calls_per_day"] == -1

    def test_warning_threshold_is_80_pct(self):
        assert self.pl.WARNING_THRESHOLD == 0.80

    # ── get_limit ─────────────────────────────────────────────────────────────

    def test_get_limit_returns_none_for_enterprise(self):
        """Enterprise → None (unlimited) for any resource."""
        # Use a fake Plan-like object with .value attribute
        class _P:
            value = "ENTERPRISE"
        assert self.pl.get_limit(_P(), "max_products") is None

    def test_get_limit_returns_int_for_free(self):
        class _P:
            value = "FREE"
        assert self.pl.get_limit(_P(), "max_users") == 3

    def test_get_limit_returns_int_for_pro(self):
        class _P:
            value = "PRO"
        assert self.pl.get_limit(_P(), "max_warehouses") == 5

    # ── is_feature_unlocked ───────────────────────────────────────────────────

    def test_loyalty_unlocked_on_free(self):
        class _P:
            value = "FREE"
        assert self.pl.is_feature_unlocked(_P(), "loyalty") is True

    def test_api_webhooks_locked_on_free(self):
        class _P:
            value = "FREE"
        assert self.pl.is_feature_unlocked(_P(), "api_webhooks") is False

    def test_api_webhooks_locked_on_pro(self):
        class _P:
            value = "PRO"
        assert self.pl.is_feature_unlocked(_P(), "api_webhooks") is False

    def test_api_webhooks_unlocked_on_enterprise(self):
        class _P:
            value = "ENTERPRISE"
        assert self.pl.is_feature_unlocked(_P(), "api_webhooks") is True

    def test_ai_chat_locked_on_free(self):
        class _P:
            value = "FREE"
        assert self.pl.is_feature_unlocked(_P(), "ai_chat") is False

    def test_ai_chat_unlocked_on_pro(self):
        class _P:
            value = "PRO"
        assert self.pl.is_feature_unlocked(_P(), "ai_chat") is True

    # ── check_limit ───────────────────────────────────────────────────────────

    def test_check_limit_allowed_below_threshold(self):
        """50 of 500 products = 10% — should be allowed, no exception."""
        class _P:
            value = "FREE"
        result = self.pl.check_limit(_P(), "max_products", 50)
        assert result.allowed is True
        assert result.percentage_used == pytest.approx(0.10)

    def test_check_limit_raises_approaching_at_80_pct(self):
        """400 of 500 products = 80% — ApproachingLimitError."""
        class _P:
            value = "FREE"
        with pytest.raises(self.pl.ApproachingLimitError) as exc_info:
            self.pl.check_limit(_P(), "max_products", 400)
        assert exc_info.value.current == 400
        assert exc_info.value.limit == 500

    def test_check_limit_raises_exceeded_at_100_pct(self):
        """500 of 500 products = 100% — LimitExceededError."""
        class _P:
            value = "FREE"
        with pytest.raises(self.pl.LimitExceededError) as exc_info:
            self.pl.check_limit(_P(), "max_products", 500)
        assert exc_info.value.current == 500
        assert exc_info.value.limit == 500

    def test_check_limit_raises_exceeded_over_100_pct(self):
        """More than limit — LimitExceededError."""
        class _P:
            value = "FREE"
        with pytest.raises(self.pl.LimitExceededError):
            self.pl.check_limit(_P(), "max_products", 600)

    def test_check_limit_unlimited_plan_never_raises(self):
        """Enterprise: unlimited — no exception regardless of count."""
        class _P:
            value = "ENTERPRISE"
        result = self.pl.check_limit(_P(), "max_products", 999_999)
        assert result.allowed is True
        assert result.percentage_used == 0.0

    def test_check_limit_zero_resource_raises_exceeded_when_nonzero(self):
        """ai_calls_per_day = 0 on FREE — any call should raise LimitExceededError."""
        class _P:
            value = "FREE"
        with pytest.raises(self.pl.LimitExceededError):
            self.pl.check_limit(_P(), "ai_calls_per_day", 1)

    def test_check_limit_zero_resource_ok_when_zero(self):
        """ai_calls_per_day = 0 on FREE, current = 0 — still allowed (not yet exceeded)."""
        class _P:
            value = "FREE"
        result = self.pl.check_limit(_P(), "ai_calls_per_day", 0)
        assert result.allowed is True


# ---------------------------------------------------------------------------
# 2. plan_check.py — source contract
# ---------------------------------------------------------------------------

class TestPlanCheckSource:
    """plan_check.py must export the two new dependency factories."""

    def _src(self):
        return _src("middleware/plan_check.py")

    def test_require_feature_defined(self):
        assert "def require_feature" in self._src()

    def test_check_resource_limit_defined(self):
        assert "def check_resource_limit" in self._src()

    def test_require_feature_raises_403_with_code(self):
        src = self._src()
        assert "FEATURE_NOT_AVAILABLE" in src

    def test_check_resource_limit_raises_403_with_code(self):
        src = self._src()
        assert "PLAN_LIMIT_EXCEEDED" in src

    def test_structured_detail_has_suggested_upgrade_url(self):
        src = self._src()
        assert "suggested_upgrade_url" in src

    def test_imports_plan_limits(self):
        src = self._src()
        assert "from app.services.plan_limits import" in src


# ---------------------------------------------------------------------------
# 3. Router enforcement — source contracts
# ---------------------------------------------------------------------------

class TestInventoryRouterLimits:
    def test_imports_plan_limits(self):
        src = _src("routers/inventory.py")
        assert "from app.services.plan_limits import" in src

    def test_product_create_checks_max_products(self):
        src = _src("routers/inventory.py")
        assert "RESOURCE_PRODUCTS" in src

    def test_warehouse_create_checks_max_warehouses(self):
        src = _src("routers/inventory.py")
        assert "RESOURCE_WAREHOUSES" in src

    def test_limit_exceeded_error_raised_as_403(self):
        src = _src("routers/inventory.py")
        assert "PLAN_LIMIT_EXCEEDED" in src


class TestInvoicingRouterLimits:
    def test_imports_plan_limits(self):
        src = _src("routers/invoicing.py")
        assert "from app.services.plan_limits import" in src

    def test_invoice_create_checks_monthly_limit(self):
        src = _src("routers/invoicing.py")
        assert "RESOURCE_INVOICES_PER_MONTH" in src

    def test_structured_403_in_invoicing(self):
        src = _src("routers/invoicing.py")
        assert "PLAN_LIMIT_EXCEEDED" in src


class TestTeamRouterLimits:
    def test_imports_plan_limits(self):
        src = _src("routers/team.py")
        assert "from app.services.plan_limits import" in src

    def test_uses_check_limit(self):
        src = _src("routers/team.py")
        assert "check_limit(" in src

    def test_structured_403_in_team(self):
        src = _src("routers/team.py")
        assert "PLAN_LIMIT_EXCEEDED" in src


class TestIntegrationsAiLimits:
    def test_imports_plan_limits(self):
        src = _src("routers/integrations.py")
        assert "from app.services.plan_limits import" in src

    def test_ai_call_limit_helper_defined(self):
        src = _src("routers/integrations.py")
        assert "_check_ai_call_limit" in src

    def test_ai_call_limit_called_in_chat_endpoint(self):
        src = _src("routers/integrations.py")
        # The call must appear after the /ai/chat endpoint definition
        chat_pos = src.find('"/ai/chat"')
        limit_call_pos = src.find("_check_ai_call_limit(", chat_pos)
        assert chat_pos != -1
        assert limit_call_pos != -1

    def test_daily_counter_dict_defined(self):
        src = _src("routers/integrations.py")
        assert "_ai_call_counts" in src


# ---------------------------------------------------------------------------
# 4. Frontend source contracts
# ---------------------------------------------------------------------------

FRONTEND = Path(__file__).parent.parent.parent / "frontend" / "src"


class TestFrontendPlanLimits:
    def _src(self):
        return (FRONTEND / "lib" / "plan-limits.ts").read_text()

    def test_file_exists(self):
        assert (FRONTEND / "lib" / "plan-limits.ts").exists()

    def test_plan_limits_dict_has_three_tiers(self):
        src = self._src()
        for tier in ("FREE", "PRO", "ENTERPRISE"):
            assert tier in src

    def test_use_plan_limits_hook_exported(self):
        src = self._src()
        assert "usePlanLimits" in src

    def test_is_feature_unlocked_exported(self):
        src = self._src()
        assert "isFeatureUnlocked" in src

    def test_is_limit_exceeded_exported(self):
        src = self._src()
        assert "isLimitExceeded" in src

    def test_is_approaching_limit_exported(self):
        src = self._src()
        assert "isApproachingLimit" in src


class TestFrontendUIComponents:
    def test_limit_warning_banner_exists(self):
        assert (FRONTEND / "components" / "ui" / "LimitWarningBanner.tsx").exists()

    def test_limit_blocked_modal_exists(self):
        assert (FRONTEND / "components" / "ui" / "LimitBlockedModal.tsx").exists()

    def test_locked_feature_card_exists(self):
        assert (FRONTEND / "components" / "ui" / "LockedFeatureCard.tsx").exists()

    def test_warning_banner_has_upgrade_link(self):
        src = (FRONTEND / "components" / "ui" / "LimitWarningBanner.tsx").read_text()
        assert "upgradeUrl" in src or "billing" in src

    def test_blocked_modal_has_upgrade_button(self):
        src = (FRONTEND / "components" / "ui" / "LimitBlockedModal.tsx").read_text()
        assert "Upgrade" in src

    def test_locked_feature_card_has_lock_icon(self):
        src = (FRONTEND / "components" / "ui" / "LockedFeatureCard.tsx").read_text()
        assert "Lock" in src
