"""Tests for the upsell trigger engine.

Run with:
    cd backend && python -m pytest tests/test_upsells.py -v --noconftest

All tests are pure Python — they import app/services/upsells.py directly
(no FastAPI, no DB, no conftest needed) via importlib isolation.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module loading
# ---------------------------------------------------------------------------

BACKEND = Path(__file__).parent.parent / "app"


def _load_upsells():
    spec_path = BACKEND / "services" / "upsells.py"
    spec = importlib.util.spec_from_file_location("upsells_mod", spec_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["upsells_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


# Load once at module scope — the module is pure Python, safe to reuse
_mod = _load_upsells()

OrgData = _mod.OrgData
UserData = _mod.UserData
UpsellContext = _mod.UpsellContext
ALL_TRIGGERS = _mod.ALL_TRIGGERS
evaluate_triggers = _mod.evaluate_triggers
is_user_eligible = _mod.is_user_eligible
format_message = _mod.format_message
format_cta = _mod.format_cta

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOW = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def _free_org(**kwargs) -> OrgData:
    defaults = dict(
        id="org-1",
        plan="FREE",
        created_at=NOW - timedelta(days=60),
        is_on_trial=False,
        trial_ends_at=None,
        subscription_interval=None,
        subscription_started_at=None,
    )
    defaults.update(kwargs)
    return OrgData(**defaults)


def _pro_org(**kwargs) -> OrgData:
    defaults = dict(
        id="org-2",
        plan="PRO",
        created_at=NOW - timedelta(days=60),
        is_on_trial=False,
        trial_ends_at=None,
        subscription_interval="month",
        subscription_started_at=NOW - timedelta(days=40),
    )
    defaults.update(kwargs)
    return OrgData(**defaults)


def _owner(**kwargs) -> UserData:
    return UserData(id="user-1", role="OWNER", **kwargs)


def _admin(**kwargs) -> UserData:
    return UserData(id="user-2", role="ADMIN", **kwargs)


def _member(**kwargs) -> UserData:
    return UserData(id="user-3", role="MEMBER", **kwargs)


def _empty_ctx(**kwargs) -> UpsellContext:
    defaults = dict(
        product_count=0,
        customer_count=0,
        user_count=0,
        invoice_count_this_month=0,
        warehouse_count=0,
        invoices_paid_total=0,
        dunning_sent_count=0,
        days_since_signup=0,
        trial_days_remaining=0,
        locked_feature_attempted=None,
        recent_upsell_events=[],
        weekly_prompt_count=0,
        days_since_subscription=0,
    )
    defaults.update(kwargs)
    return UpsellContext(**defaults)


# ---------------------------------------------------------------------------
# 1. ALL_TRIGGERS structure
# ---------------------------------------------------------------------------

class TestAllTriggersStructure:

    def test_ten_triggers_defined(self):
        assert len(ALL_TRIGGERS) == 10

    def test_all_trigger_ids_unique(self):
        ids = [t.id for t in ALL_TRIGGERS]
        assert len(ids) == len(set(ids))

    def test_all_required_fields_present(self):
        for t in ALL_TRIGGERS:
            assert t.id
            assert t.name
            assert t.message_template
            assert t.cta
            assert t.target_tier in ("PRO", "ENTERPRISE")
            assert t.placement in ("modal", "banner", "toast", "inline")
            assert isinstance(t.frequency_cap_days, int)
            assert isinstance(t.priority, int)

    def test_expected_trigger_ids_present(self):
        ids = {t.id for t in ALL_TRIGGERS}
        for expected in (
            "limit_approaching",
            "limit_hit",
            "locked_feature_clicked",
            "success_milestone",
            "pain_pattern_detected",
            "lifecycle_day",
            "ai_feature_glimpse",
            "competitive_fomo",
            "mobile_specific",
            "trial_lifecycle",
        ):
            assert expected in ids, f"Missing trigger: {expected}"


# ---------------------------------------------------------------------------
# 2. is_user_eligible — anti-annoyance rules
# ---------------------------------------------------------------------------

class TestIsUserEligible:

    def _trigger(self, id_: str):
        return next(t for t in ALL_TRIGGERS if t.id == id_)

    def test_member_role_always_ineligible(self):
        t = self._trigger("limit_approaching")
        ctx = _empty_ctx()
        assert not is_user_eligible(_member(), t, ctx, NOW)

    def test_owner_eligible_with_clean_state(self):
        t = self._trigger("limit_approaching")
        ctx = _empty_ctx()
        assert is_user_eligible(_owner(), t, ctx, NOW)

    def test_admin_eligible_with_clean_state(self):
        t = self._trigger("pain_pattern_detected")
        ctx = _empty_ctx()
        assert is_user_eligible(_admin(), t, ctx, NOW)

    def test_weekly_cap_blocks_at_3(self):
        t = self._trigger("lifecycle_day")
        ctx = _empty_ctx(weekly_prompt_count=3)
        assert not is_user_eligible(_owner(), t, ctx, NOW)

    def test_weekly_cap_allows_at_2(self):
        t = self._trigger("lifecycle_day")
        ctx = _empty_ctx(weekly_prompt_count=2)
        assert is_user_eligible(_owner(), t, ctx, NOW)

    def test_frequency_cap_blocks_within_window(self):
        t = self._trigger("limit_approaching")  # frequency_cap_days = 3
        ctx = _empty_ctx(recent_upsell_events=[
            {"trigger_id": "limit_approaching", "shown_at": NOW - timedelta(days=2), "dismissed_at": None}
        ])
        assert not is_user_eligible(_owner(), t, ctx, NOW)

    def test_frequency_cap_allows_after_window(self):
        t = self._trigger("limit_approaching")  # frequency_cap_days = 3
        ctx = _empty_ctx(recent_upsell_events=[
            {"trigger_id": "limit_approaching", "shown_at": NOW - timedelta(days=4), "dismissed_at": None}
        ])
        assert is_user_eligible(_owner(), t, ctx, NOW)

    def test_dismissed_cooldown_blocks_within_7_days(self):
        t = self._trigger("success_milestone")
        ctx = _empty_ctx(recent_upsell_events=[
            {
                "trigger_id": "success_milestone",
                "shown_at": NOW - timedelta(days=10),
                "dismissed_at": NOW - timedelta(days=3),
            }
        ])
        assert not is_user_eligible(_owner(), t, ctx, NOW)

    def test_dismissed_cooldown_allows_after_7_days(self):
        t = self._trigger("success_milestone")
        ctx = _empty_ctx(recent_upsell_events=[
            {
                "trigger_id": "success_milestone",
                "shown_at": NOW - timedelta(days=20),
                "dismissed_at": NOW - timedelta(days=8),
            }
        ])
        assert is_user_eligible(_owner(), t, ctx, NOW)

    def test_different_trigger_id_in_events_does_not_block(self):
        t = self._trigger("limit_approaching")
        ctx = _empty_ctx(recent_upsell_events=[
            {"trigger_id": "success_milestone", "shown_at": NOW - timedelta(minutes=5), "dismissed_at": None}
        ])
        assert is_user_eligible(_owner(), t, ctx, NOW)

    def test_iso_string_shown_at_parsed_correctly(self):
        """shown_at can arrive as ISO string from JSON serialization."""
        t = self._trigger("limit_approaching")  # cap = 3 days
        ctx = _empty_ctx(recent_upsell_events=[
            {"trigger_id": "limit_approaching", "shown_at": (NOW - timedelta(days=1)).isoformat(), "dismissed_at": None}
        ])
        assert not is_user_eligible(_owner(), t, ctx, NOW)


# ---------------------------------------------------------------------------
# 3. evaluate_triggers — per-trigger conditions
# ---------------------------------------------------------------------------

class TestLimitApproachingTrigger:

    def test_fires_when_products_at_80_percent(self):
        # 80 products on FREE plan (limit = 100)
        ctx = _empty_ctx(product_count=80, days_since_signup=100)
        results = evaluate_triggers(_free_org(), _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "limit_approaching" in ids

    def test_does_not_fire_below_threshold(self):
        ctx = _empty_ctx(product_count=75, days_since_signup=100)
        results = evaluate_triggers(_free_org(), _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "limit_approaching" not in ids

    def test_does_not_fire_when_already_at_limit(self):
        # at limit → limit_hit fires instead
        ctx = _empty_ctx(product_count=100, days_since_signup=100)
        results = evaluate_triggers(_free_org(), _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "limit_approaching" not in ids

    def test_fires_for_customers_nearing_limit(self):
        ctx = _empty_ctx(customer_count=160, days_since_signup=100)  # 160/200 = 80%
        results = evaluate_triggers(_free_org(), _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "limit_approaching" in ids


class TestLimitHitTrigger:

    def test_fires_when_products_at_limit(self):
        ctx = _empty_ctx(product_count=100, days_since_signup=100)
        results = evaluate_triggers(_free_org(), _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "limit_hit" in ids

    def test_does_not_fire_below_limit(self):
        ctx = _empty_ctx(product_count=99, days_since_signup=100)
        results = evaluate_triggers(_free_org(), _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "limit_hit" not in ids


class TestLockedFeatureTrigger:

    def test_fires_when_feature_attempted(self):
        ctx = _empty_ctx(locked_feature_attempted="advanced_reporting")
        results = evaluate_triggers(_free_org(), _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "locked_feature_clicked" in ids

    def test_does_not_fire_when_no_feature_attempted(self):
        ctx = _empty_ctx()
        results = evaluate_triggers(_free_org(), _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "locked_feature_clicked" not in ids


class TestSuccessMilestoneTrigger:

    def test_fires_at_10_paid_invoices_on_free(self):
        ctx = _empty_ctx(invoices_paid_total=10)
        results = evaluate_triggers(_free_org(), _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "success_milestone" in ids

    def test_does_not_fire_below_10(self):
        ctx = _empty_ctx(invoices_paid_total=9)
        results = evaluate_triggers(_free_org(), _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "success_milestone" not in ids

    def test_does_not_fire_on_pro_plan(self):
        ctx = _empty_ctx(invoices_paid_total=50)
        results = evaluate_triggers(_pro_org(), _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "success_milestone" not in ids


class TestPainPatternTrigger:

    def test_fires_with_3_dunning_on_free(self):
        ctx = _empty_ctx(dunning_sent_count=3)
        results = evaluate_triggers(_free_org(), _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "pain_pattern_detected" in ids

    def test_does_not_fire_with_2_dunning(self):
        ctx = _empty_ctx(dunning_sent_count=2)
        results = evaluate_triggers(_free_org(), _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "pain_pattern_detected" not in ids


class TestLifecycleDayTrigger:

    def test_fires_on_day_3(self):
        ctx = _empty_ctx(days_since_signup=3)
        results = evaluate_triggers(_free_org(), _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "lifecycle_day" in ids

    def test_fires_on_day_7(self):
        ctx = _empty_ctx(days_since_signup=7)
        results = evaluate_triggers(_free_org(), _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "lifecycle_day" in ids

    def test_fires_on_day_14(self):
        ctx = _empty_ctx(days_since_signup=14)
        results = evaluate_triggers(_free_org(), _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "lifecycle_day" in ids

    def test_does_not_fire_on_day_5(self):
        ctx = _empty_ctx(days_since_signup=5)
        results = evaluate_triggers(_free_org(), _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "lifecycle_day" not in ids


class TestTrialLifecycleTrigger:

    def test_fires_when_trial_ends_in_3_days(self):
        org = _free_org(
            is_on_trial=True,
            trial_ends_at=NOW + timedelta(days=3),
        )
        ctx = _empty_ctx(trial_days_remaining=3)
        results = evaluate_triggers(org, _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "trial_lifecycle" in ids

    def test_does_not_fire_when_not_on_trial(self):
        org = _free_org(is_on_trial=False)
        ctx = _empty_ctx(trial_days_remaining=3)
        results = evaluate_triggers(org, _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "trial_lifecycle" not in ids

    def test_does_not_fire_when_more_than_7_days_remaining(self):
        org = _free_org(
            is_on_trial=True,
            trial_ends_at=NOW + timedelta(days=10),
        )
        ctx = _empty_ctx(trial_days_remaining=10)
        results = evaluate_triggers(org, _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert "trial_lifecycle" not in ids


# ---------------------------------------------------------------------------
# 4. evaluate_triggers — anti-annoyance rules applied globally
# ---------------------------------------------------------------------------

class TestGlobalAntiAnnoyance:

    def test_member_gets_empty_list(self):
        ctx = _empty_ctx(product_count=100, invoices_paid_total=10, dunning_sent_count=3)
        results = evaluate_triggers(_free_org(), _member(), ctx, NOW)
        assert results == []

    def test_trial_user_only_gets_trial_trigger(self):
        org = _free_org(
            is_on_trial=True,
            trial_ends_at=NOW + timedelta(days=3),
        )
        ctx = _empty_ctx(
            trial_days_remaining=3,
            product_count=100,       # would trigger limit_hit
            invoices_paid_total=15,  # would trigger success_milestone
        )
        results = evaluate_triggers(org, _owner(), ctx, NOW)
        ids = [t.id for t in results]
        assert all(i == "trial_lifecycle" for i in ids)
        assert "trial_lifecycle" in ids

    def test_yearly_subscriber_30_day_block(self):
        org = _pro_org(
            subscription_interval="year",
            subscription_started_at=NOW - timedelta(days=10),
        )
        ctx = _empty_ctx(product_count=1900, days_since_subscription=10)  # 95% → approaching
        results = evaluate_triggers(org, _owner(), ctx, NOW)
        assert results == []

    def test_yearly_subscriber_after_30_days_can_see_upsells(self):
        org = OrgData(
            id="org-y",
            plan="FREE",
            created_at=NOW - timedelta(days=90),
            is_on_trial=False,
            trial_ends_at=None,
            subscription_interval="year",
            subscription_started_at=NOW - timedelta(days=40),
        )
        ctx = _empty_ctx(product_count=100, days_since_subscription=40)
        results = evaluate_triggers(org, _owner(), ctx, NOW)
        # limit_hit should fire
        ids = [t.id for t in results]
        assert "limit_hit" in ids

    def test_at_most_one_modal_in_results(self):
        ctx = _empty_ctx(
            product_count=100,        # limit_hit → modal
            locked_feature_attempted="analytics",  # locked_feature_clicked → modal
        )
        results = evaluate_triggers(_free_org(), _owner(), ctx, NOW)
        modal_triggers = [t for t in results if t.placement == "modal"]
        assert len(modal_triggers) <= 1

    def test_results_ordered_by_priority(self):
        ctx = _empty_ctx(
            product_count=100,
            invoices_paid_total=10,
            dunning_sent_count=3,
            days_since_signup=7,
            customer_count=5,
        )
        results = evaluate_triggers(_free_org(), _owner(), ctx, NOW)
        priorities = [t.priority for t in results]
        assert priorities == sorted(priorities)

    def test_empty_context_returns_nothing(self):
        ctx = _empty_ctx()
        results = evaluate_triggers(_free_org(), _owner(), ctx, NOW)
        assert results == []


# ---------------------------------------------------------------------------
# 5. format_message and format_cta
# ---------------------------------------------------------------------------

class TestFormatMessage:

    def _t(self, id_: str):
        return next(t for t in ALL_TRIGGERS if t.id == id_)

    def test_interpolates_plan(self):
        t = self._t("limit_approaching")
        msg = format_message(t, {"plan": "FREE", "resource": "products", "count": "80", "limit": "100"})
        assert "FREE" in msg
        assert "products" in msg

    def test_interpolates_days_for_trial(self):
        t = self._t("trial_lifecycle")
        msg = format_message(t, {"days": "3"})
        assert "3" in msg

    def test_missing_key_preserved_as_placeholder(self):
        t = self._t("limit_approaching")
        msg = format_message(t, {})  # no variables → {plan} etc. left intact
        assert "{plan}" in msg or "plan" in msg

    def test_format_cta_interpolates_feature(self):
        t = self._t("locked_feature_clicked")
        cta = format_cta(t, {"feature": "Advanced Reports"})
        assert "Advanced Reports" in cta


# ---------------------------------------------------------------------------
# 6. Router source contract (file exists + structure)
# ---------------------------------------------------------------------------

class TestUpsellsRouterSource:

    def _src(self):
        return (Path(__file__).parent.parent / "app" / "routers" / "upsells.py").read_text()

    def test_router_file_exists(self):
        assert (Path(__file__).parent.parent / "app" / "routers" / "upsells.py").exists()

    def test_has_pending_endpoint(self):
        assert "/pending" in self._src()

    def test_has_shown_endpoint(self):
        assert '"/shown"' in self._src() or "'/shown'" in self._src()

    def test_has_clicked_endpoint(self):
        assert '"/clicked"' in self._src() or "'/clicked'" in self._src()

    def test_has_dismissed_endpoint(self):
        assert '"/dismissed"' in self._src() or "'/dismissed'" in self._src()

    def test_auth_dependency_used(self):
        assert "get_current_member" in self._src()

    def test_no_wildcard_cors(self):
        assert 'allow_origins=["*"]' not in self._src()


# ---------------------------------------------------------------------------
# 7. Service source contract
# ---------------------------------------------------------------------------

class TestUpsellsServiceSource:

    def _src(self):
        return (Path(__file__).parent.parent / "app" / "services" / "upsells.py").read_text()

    def test_file_exists(self):
        assert (Path(__file__).parent.parent / "app" / "services" / "upsells.py").exists()

    def test_member_guard_present(self):
        assert '"MEMBER"' in self._src()

    def test_max_weekly_prompts_defined(self):
        src = self._src()
        assert "_MAX_WEEKLY_PROMPTS" in src

    def test_dismiss_cooldown_defined(self):
        src = self._src()
        assert "_DISMISS_COOLDOWN_DAYS" in src
        assert "7" in src

    def test_evaluate_triggers_defined(self):
        assert "def evaluate_triggers" in self._src()

    def test_is_user_eligible_defined(self):
        assert "def is_user_eligible" in self._src()

    def test_format_message_defined(self):
        assert "def format_message" in self._src()


# ---------------------------------------------------------------------------
# 8. Frontend source contracts
# ---------------------------------------------------------------------------

FRONTEND = Path(__file__).parent.parent.parent / "frontend" / "src"


class TestFrontendUpsellComponents:

    def test_use_upsells_hook_exists(self):
        assert (FRONTEND / "hooks" / "useUpsells.ts").exists()

    def test_upsell_modal_exists(self):
        assert (FRONTEND / "components" / "upsells" / "UpsellModal.tsx").exists()

    def test_upsell_banner_exists(self):
        assert (FRONTEND / "components" / "upsells" / "UpsellBanner.tsx").exists()

    def test_upsell_toast_exists(self):
        assert (FRONTEND / "components" / "upsells" / "UpsellToast.tsx").exists()

    def test_upgrade_prompt_inline_exists(self):
        assert (FRONTEND / "components" / "upsells" / "UpgradePromptInline.tsx").exists()

    def test_hook_exports_record_shown(self):
        src = (FRONTEND / "hooks" / "useUpsells.ts").read_text()
        assert "recordShown" in src

    def test_hook_exports_record_clicked(self):
        src = (FRONTEND / "hooks" / "useUpsells.ts").read_text()
        assert "recordClicked" in src

    def test_hook_exports_record_dismissed(self):
        src = (FRONTEND / "hooks" / "useUpsells.ts").read_text()
        assert "recordDismissed" in src

    def test_modal_session_cap_present(self):
        src = (FRONTEND / "hooks" / "useUpsells.ts").read_text()
        assert "sessionStorage" in src

    def test_banner_mount_cap_present(self):
        src = (FRONTEND / "hooks" / "useUpsells.ts").read_text()
        assert "bannerShownThisMount" in src or "bannerIncluded" in src

    def test_posthog_track_called_on_shown(self):
        src = (FRONTEND / "hooks" / "useUpsells.ts").read_text()
        assert "upsell_shown" in src

    def test_posthog_track_called_on_clicked(self):
        src = (FRONTEND / "hooks" / "useUpsells.ts").read_text()
        assert "upsell_clicked" in src

    def test_posthog_track_called_on_dismissed(self):
        src = (FRONTEND / "hooks" / "useUpsells.ts").read_text()
        assert "upsell_dismissed" in src

    def test_hook_never_throws_try_catch(self):
        src = (FRONTEND / "hooks" / "useUpsells.ts").read_text()
        assert "} catch" in src

    def test_hook_uses_env_api_url(self):
        src = (FRONTEND / "hooks" / "useUpsells.ts").read_text()
        assert "NEXT_PUBLIC_API_URL" in src

    def test_hook_does_not_hardcode_api_url(self):
        src = (FRONTEND / "hooks" / "useUpsells.ts").read_text()
        assert "varuflow-production" not in src
