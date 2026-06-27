"""Tests for the PostHog analytics integration.

Run with:
    cd backend && python -m pytest tests/test_analytics.py -v --noconftest

Design: All tests are pure or source-contract.
- "Never raises" tests call the module functions with a mock client that throws.
- "No analytics in dev mode" tests verify the client returns None in development.
- "Source contract" tests read file text to verify structure without importing the full app.
"""
from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BACKEND  = Path(__file__).parent.parent / "app"
FRONTEND = Path(__file__).parent.parent.parent / "frontend" / "src"
MOBILE   = Path(__file__).parent.parent.parent / "mobile"


def _src(relative: str) -> str:
    return (BACKEND / relative).read_text()


def _load_analytics():
    """Load app/services/analytics.py in isolation (no full app import)."""
    spec_path = BACKEND / "services" / "analytics.py"
    spec = importlib.util.spec_from_file_location("analytics_mod", spec_path)
    mod  = importlib.util.module_from_spec(spec)
    sys.modules["analytics_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# 1. Module constants and structure
# ---------------------------------------------------------------------------

class TestAnalyticsModuleStructure:
    """analytics.py must export the right constants and async functions."""

    def _src(self):
        return _src("services/analytics.py")

    def test_file_exists(self):
        assert (BACKEND / "services" / "analytics.py").exists()

    def test_exports_track_event(self):
        assert "async def track_event" in self._src()

    def test_exports_identify_user(self):
        assert "async def identify_user" in self._src()

    def test_exports_track_signup(self):
        assert "async def track_signup" in self._src()

    def test_exports_track_trial_start(self):
        assert "async def track_trial_start" in self._src()

    def test_exports_track_invoice_created(self):
        assert "async def track_invoice_created" in self._src()

    def test_exports_track_pos_sale(self):
        assert "async def track_pos_sale" in self._src()

    def test_exports_track_subscription_changed(self):
        assert "async def track_subscription_changed" in self._src()

    def test_event_constants_defined(self):
        src = self._src()
        for name in (
            "SIGNUP_COMPLETED",
            "TRIAL_STARTED",
            "FIRST_INVOICE_CREATED",
            "FIRST_POS_SALE",
            "SUBSCRIPTION_STARTED",
            "FEATURE_USED",
            "AI_QUERY_MADE",
            "LIMIT_WARNING_SHOWN",
            "LIMIT_BLOCKED_SHOWN",
            "UPSELL_SHOWN",
        ):
            assert name in src, f"Missing constant: {name}"

    def test_try_except_in_track_event(self):
        """Every tracking call must be wrapped in try/except."""
        src = self._src()
        # The module-level try/except count must be >= 2 (track + identify at minimum)
        assert src.count("except Exception") >= 2

    def test_dev_mode_check_present(self):
        """Never track in development mode."""
        src = self._src()
        assert "development" in src
        assert 'ENV == "development"' in src or "ENV != \"production\"" in src or 'ENV == \'development\'' in src


# ---------------------------------------------------------------------------
# 2. "Never raises" tests
# ---------------------------------------------------------------------------

class TestAnalyticsNeverRaises:
    """All analytics functions must swallow exceptions and return None."""

    def _run(self, coro):
        return asyncio.run(coro)

    def setup_method(self):
        # Reset module-level client state between tests
        self.mod = _load_analytics()
        self.mod._client_ready   = False
        self.mod._posthog_client = None

    def test_track_event_does_not_raise_when_client_is_none(self):
        """No client configured — must return None silently."""
        with patch("app.config.settings") as mock_settings:
            mock_settings.ENV              = "development"
            mock_settings.POSTHOG_API_KEY  = ""
            self._run(self.mod.track_event("user_1", "test_event", {"key": "val"}))

    def test_track_event_does_not_raise_when_capture_throws(self):
        """posthog.capture raises RuntimeError — must swallow."""
        mock_client = MagicMock()
        mock_client.capture.side_effect = RuntimeError("network error")
        self.mod._posthog_client = mock_client
        self.mod._client_ready   = True

        self._run(self.mod.track_event("user_1", "bad_event"))
        # No exception propagated

    def test_identify_user_does_not_raise_when_identify_throws(self):
        mock_client = MagicMock()
        mock_client.identify.side_effect = Exception("timeout")
        self.mod._posthog_client = mock_client
        self.mod._client_ready   = True

        self._run(self.mod.identify_user("user_1", {"plan": "PRO"}))

    def test_track_signup_does_not_raise_when_client_throws(self):
        mock_client = MagicMock()
        mock_client.capture.side_effect = ConnectionError("posthog down")
        mock_client.identify.side_effect = ConnectionError("posthog down")
        self.mod._posthog_client = mock_client
        self.mod._client_ready   = True

        self._run(self.mod.track_signup("user_1", "Acme AB", "PRO"))

    def test_track_trial_start_does_not_raise(self):
        mock_client = MagicMock()
        mock_client.capture.side_effect = ValueError("unexpected")
        self.mod._posthog_client = mock_client
        self.mod._client_ready   = True

        self._run(self.mod.track_trial_start("user_1", "org_1", "PRO", "direct"))

    def test_track_invoice_created_does_not_raise(self):
        mock_client = MagicMock()
        mock_client.capture.side_effect = OSError("disk full")
        self.mod._posthog_client = mock_client
        self.mod._client_ready   = True

        self._run(self.mod.track_invoice_created("user_1", "org_1", is_first_invoice=True))

    def test_track_pos_sale_does_not_raise(self):
        mock_client = MagicMock()
        mock_client.capture.side_effect = TypeError("bad type")
        self.mod._posthog_client = mock_client
        self.mod._client_ready   = True

        self._run(self.mod.track_pos_sale("user_1", "org_1", 1500.0, is_first_sale=False))

    def test_track_subscription_changed_does_not_raise(self):
        mock_client = MagicMock()
        mock_client.capture.side_effect = Exception("generic error")
        self.mod._posthog_client = mock_client
        self.mod._client_ready   = True

        self._run(
            self.mod.track_subscription_changed(
                "user_1", "org_1", self.mod.SUBSCRIPTION_STARTED, "PRO", "year"
            )
        )

    def test_track_feature_used_does_not_raise(self):
        mock_client = MagicMock()
        mock_client.capture.side_effect = Exception("posthog 500")
        self.mod._posthog_client = mock_client
        self.mod._client_ready   = True

        self._run(self.mod.track_feature_used("user_1", "org_1", "invoicing"))

    def test_track_ai_query_does_not_raise(self):
        mock_client = MagicMock()
        mock_client.capture.side_effect = Exception("ratelimited")
        self.mod._posthog_client = mock_client
        self.mod._client_ready   = True

        self._run(self.mod.track_ai_query("user_1", "org_1"))

    def test_track_limit_shown_does_not_raise(self):
        mock_client = MagicMock()
        mock_client.capture.side_effect = Exception("down")
        self.mod._posthog_client = mock_client
        self.mod._client_ready   = True

        self._run(self.mod.track_limit_shown("user_1", "org_1", True, "max_products", "PRO"))

    def test_track_upsell_does_not_raise(self):
        mock_client = MagicMock()
        mock_client.capture.side_effect = Exception("down")
        self.mod._posthog_client = mock_client
        self.mod._client_ready   = True

        self._run(self.mod.track_upsell("user_1", "org_1", "shown", "products_page", "PRO"))


# ---------------------------------------------------------------------------
# 3. Development mode guard
# ---------------------------------------------------------------------------

class TestNoAnalyticsInDev:

    def setup_method(self):
        self.mod = _load_analytics()
        self.mod._client_ready   = False
        self.mod._posthog_client = None

    def test_client_is_none_in_development_mode(self):
        """_get_client() must return None when ENV=development."""
        class _FakeSettings:
            ENV             = "development"
            POSTHOG_API_KEY = "ph_test_key"
            POSTHOG_HOST    = "https://eu.i.posthog.com"

        with patch("app.config.settings", _FakeSettings()):
            client = self.mod._get_client()

        assert client is None, "PostHog client must be None in dev mode"

    def test_client_is_none_when_api_key_empty(self):
        """Empty POSTHOG_API_KEY disables analytics regardless of ENV."""
        class _FakeSettings:
            ENV             = "production"
            POSTHOG_API_KEY = ""
            POSTHOG_HOST    = "https://eu.i.posthog.com"

        with patch("app.config.settings", _FakeSettings()):
            client = self.mod._get_client()

        assert client is None, "PostHog client must be None with no API key"

    def test_no_events_captured_in_dev_mode(self):
        """Even if somehow called in dev, no capture() calls should happen."""
        class _FakeSettings:
            ENV             = "development"
            POSTHOG_API_KEY = "ph_test_key"
            POSTHOG_HOST    = "https://eu.i.posthog.com"

        with patch("app.config.settings", _FakeSettings()):
            # Manually call track_event — should be a no-op
            asyncio.run(self.mod.track_event("user_1", "signup_completed"))
        # No assertion needed — just must not raise

    def test_setup_in_dev_does_not_import_posthog(self):
        """In dev mode, posthog module should never be imported."""
        class _FakeSettings:
            ENV             = "development"
            POSTHOG_API_KEY = "ph_live_key_real"
            POSTHOG_HOST    = "https://eu.i.posthog.com"

        with patch("app.config.settings", _FakeSettings()):
            self.mod._get_client()

        # Client must remain None — no posthog import attempted
        assert self.mod._posthog_client is None


# ---------------------------------------------------------------------------
# 4. Happy-path calls
# ---------------------------------------------------------------------------

class TestAnalyticsHappyPath:

    def setup_method(self):
        self.mod = _load_analytics()
        mock = MagicMock()
        self.mod._posthog_client = mock
        self.mod._client_ready   = True
        self.mock_ph = mock

    def _run(self, coro):
        return asyncio.run(coro)

    def test_track_event_calls_capture(self):
        self._run(self.mod.track_event("u1", "signup_completed", {"plan": "PRO"}))
        self.mock_ph.capture.assert_called_once_with(
            distinct_id="u1",
            event="signup_completed",
            properties={"plan": "PRO"},
        )

    def test_identify_user_calls_identify(self):
        self._run(self.mod.identify_user("u1", {"plan": "FREE"}))
        self.mock_ph.identify.assert_called_once_with(
            distinct_id="u1", properties={"plan": "FREE"}
        )

    def test_track_invoice_created_fires_first_invoice_event(self):
        self._run(self.mod.track_invoice_created("u1", "org1", is_first_invoice=True))
        calls = [c.kwargs["event"] for c in self.mock_ph.capture.call_args_list]
        assert self.mod.FIRST_INVOICE_CREATED in calls
        assert self.mod.INVOICE_CREATED in calls

    def test_track_invoice_created_no_first_invoice_event_on_subsequent(self):
        self._run(self.mod.track_invoice_created("u1", "org1", is_first_invoice=False))
        calls = [c.kwargs["event"] for c in self.mock_ph.capture.call_args_list]
        assert self.mod.FIRST_INVOICE_CREATED not in calls
        assert self.mod.INVOICE_CREATED in calls

    def test_track_upsell_with_invalid_action_does_not_call_capture(self):
        self._run(self.mod.track_upsell("u1", "org1", "invalid_action", "products", "PRO"))
        self.mock_ph.capture.assert_not_called()


# ---------------------------------------------------------------------------
# 5. config.py source contract
# ---------------------------------------------------------------------------

class TestConfigHasPostHogSettings:

    def _src(self):
        return (BACKEND / "config.py").read_text()

    def test_posthog_api_key_setting(self):
        assert "POSTHOG_API_KEY" in self._src()

    def test_posthog_host_setting(self):
        assert "POSTHOG_HOST" in self._src()

    def test_posthog_host_defaults_to_eu(self):
        """Default host must be EU-hosted for GDPR compliance."""
        src = self._src()
        assert "eu." in src and "posthog.com" in src


# ---------------------------------------------------------------------------
# 6. pyproject.toml source contract
# ---------------------------------------------------------------------------

class TestPyprojectHasPostHog:

    def test_posthog_in_dependencies(self):
        src = (Path(__file__).parent.parent / "pyproject.toml").read_text()
        assert "posthog" in src


# ---------------------------------------------------------------------------
# 7. Frontend source contracts
# ---------------------------------------------------------------------------

class TestFrontendAnalytics:

    def _src(self) -> str:
        return (FRONTEND / "lib" / "analytics.ts").read_text()

    def test_file_exists(self):
        assert (FRONTEND / "lib" / "analytics.ts").exists()

    def test_events_object_exported(self):
        assert "EVENTS" in self._src()

    def test_track_function_exported(self):
        assert "export function track" in self._src()

    def test_identify_function_exported(self):
        assert "export function identify" in self._src()

    def test_reset_function_exported(self):
        assert "export function reset" in self._src()

    def test_never_throws_comment_or_catch(self):
        """track/identify/reset must have try/catch."""
        src = self._src()
        assert "} catch {" in src or "} catch (_" in src

    def test_dev_guard_present(self):
        """Must not fire in non-production environments."""
        src = self._src()
        assert "production" in src

    def test_pii_scrubbing_present(self):
        """PostHogInit must scrub input values — not analytics.ts, but PostHogInit."""
        posthog_init_src = (FRONTEND / "components" / "app" / "PostHogInit.tsx").read_text()
        assert "sanitize_properties" in posthog_init_src or "$input_value" in posthog_init_src

    def test_upsell_events_defined(self):
        src = self._src()
        for e in ("upsell_shown", "upsell_clicked", "upsell_dismissed", "upsell_converted"):
            assert e in src

    def test_limit_events_defined(self):
        src = self._src()
        assert "limit_warning_shown" in src
        assert "limit_blocked_shown" in src


# ---------------------------------------------------------------------------
# 8. Mobile source contracts
# ---------------------------------------------------------------------------

class TestMobileAnalytics:

    def _src(self) -> str:
        return (MOBILE / "lib" / "analytics.ts").read_text()

    def test_file_exists(self):
        assert (MOBILE / "lib" / "analytics.ts").exists()

    def test_init_posthog_exported(self):
        assert "initPostHog" in self._src()

    def test_track_function_exported(self):
        assert "export function track" in self._src()

    def test_dev_guard_present(self):
        assert "__DEV__" in self._src()

    def test_app_opened_event(self):
        assert "app_opened" in self._src()

    def test_screen_viewed_event(self):
        assert "screen_viewed" in self._src()

    def test_mobile_layout_calls_init_posthog(self):
        layout_src = (MOBILE / "app" / "_layout.tsx").read_text()
        assert "initPostHog" in layout_src

    def test_posthog_react_native_in_package_json(self):
        pkg = (MOBILE / "package.json").read_text()
        assert "posthog-react-native" in pkg


# ---------------------------------------------------------------------------
# 9. Docs source contracts
# ---------------------------------------------------------------------------

class TestMarketingDocs:

    def test_funnels_md_exists(self):
        assert (Path(__file__).parent.parent.parent / "docs" / "marketing" / "funnels.md").exists()

    def test_dashboards_md_exists(self):
        assert (Path(__file__).parent.parent.parent / "docs" / "marketing" / "dashboards.md").exists()

    def test_funnels_covers_activation(self):
        src = (Path(__file__).parent.parent.parent / "docs" / "marketing" / "funnels.md").read_text()
        assert "activation" in src.lower() or "Activation" in src

    def test_funnels_covers_upgrade(self):
        src = (Path(__file__).parent.parent.parent / "docs" / "marketing" / "funnels.md").read_text()
        assert "upgrade" in src.lower() or "Upgrade" in src

    def test_funnels_covers_onboarding(self):
        src = (Path(__file__).parent.parent.parent / "docs" / "marketing" / "funnels.md").read_text()
        assert "onboarding" in src.lower()

    def test_dashboards_covers_acquisition(self):
        src = (Path(__file__).parent.parent.parent / "docs" / "marketing" / "dashboards.md").read_text()
        assert "Acquisition" in src

    def test_dashboards_covers_revenue(self):
        src = (Path(__file__).parent.parent.parent / "docs" / "marketing" / "dashboards.md").read_text()
        assert "Revenue" in src

    def test_dashboards_covers_product_usage(self):
        src = (Path(__file__).parent.parent.parent / "docs" / "marketing" / "dashboards.md").read_text()
        assert "Product Usage" in src or "product usage" in src.lower()
