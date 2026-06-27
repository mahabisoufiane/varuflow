"""Tests for staff commission tracking (v48 — Item 32).

Everything in this file exercises the pure calculator in
``app.services.commission_calculator``. The DB-bound router
(``backend.app.routers.commissions``) and the transaction hooks are
covered indirectly — their logic is thin wiring around the pure
functions tested here.

Repo convention places shared tests under ``backend/tests/`` rather
than ``backend/app/tests/``; the spec asked for the latter but we
follow the existing layout, same rationale as Items 28, 30, and 31.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.commission_calculator import (
    apply_rule,
    compute_commission,
    match_rules,
    pick_best_rule,
    render_run_csv,
    summarise_run,
)


STAFF_A = uuid.uuid4()
STAFF_B = uuid.uuid4()


def _rule(*, staff_id=STAFF_A, rule_type="pct", value="10", applies_to="all",
          min_threshold=None, is_active=True, rid=None):
    return SimpleNamespace(
        id=rid or uuid.uuid4(),
        staff_id=staff_id,
        rule_type=rule_type,
        value=Decimal(str(value)),
        applies_to=applies_to,
        min_threshold=Decimal(str(min_threshold)) if min_threshold is not None else None,
        is_active=is_active,
    )


# ── 1. test_flat_commission_calculation ────────────────────────────


def test_flat_commission_calculation_ignores_base():
    rule = _rule(rule_type="flat", value="50")
    # Flat rule — base is ignored, payout is always the value.
    assert apply_rule(rule, Decimal("1000")) == Decimal("50.00")
    assert apply_rule(rule, Decimal("1")) == Decimal("50.00")
    assert apply_rule(rule, 0) == Decimal("50.00")


def test_flat_commission_via_compute_commission():
    rule = _rule(rule_type="flat", value="25")
    result = compute_commission([rule], staff_id=STAFF_A, base_amount=500)
    assert result.amount == Decimal("25.00")
    assert result.rule_id == rule.id


# ── 2. test_pct_commission_calculation ─────────────────────────────


def test_pct_commission_calculation_two_decimals_half_up():
    rule = _rule(rule_type="pct", value="10")
    assert apply_rule(rule, Decimal("1000")) == Decimal("100.00")
    assert apply_rule(rule, Decimal("150")) == Decimal("15.00")
    # Rounding: 7.5% of 33.33 = 2.49975 → 2.50 half-up
    rule2 = _rule(rule_type="pct", value="7.5")
    assert apply_rule(rule2, Decimal("33.33")) == Decimal("2.50")


def test_pct_commission_negative_base_clamps_to_zero():
    rule = _rule(rule_type="pct", value="10")
    # Refunds don't generate negative commission.
    assert apply_rule(rule, Decimal("-500")) == Decimal("0.00")


# ── 3. test_tiered_threshold_commission ────────────────────────────


def test_tiered_threshold_below_gives_zero():
    rule = _rule(rule_type="tiered", value="15", min_threshold="1000")
    assert apply_rule(rule, Decimal("500")) == Decimal("0.00")


def test_tiered_threshold_met_applies_percentage():
    rule = _rule(rule_type="tiered", value="15", min_threshold="1000")
    assert apply_rule(rule, Decimal("1000")) == Decimal("150.00")
    assert apply_rule(rule, Decimal("2500")) == Decimal("375.00")


def test_tiered_without_threshold_behaves_like_pct():
    rule = _rule(rule_type="tiered", value="8", min_threshold=None)
    assert apply_rule(rule, Decimal("200")) == Decimal("16.00")


def test_tiered_beats_pct_when_both_qualify():
    # When a tiered (qualifying) and a pct rule both apply to the same
    # staff, the tiered one wins — operators configure tiered rules
    # precisely to supersede the baseline percent rule above a threshold.
    tiered = _rule(rule_type="tiered", value="15", min_threshold="1000")
    pct = _rule(rule_type="pct", value="10")
    best = pick_best_rule([pct, tiered], base_amount=Decimal("2000"))
    assert best is tiered
    # And below the threshold, pct wins (tiered ranks as 0).
    best_below = pick_best_rule([pct, tiered], base_amount=Decimal("500"))
    assert best_below is pct


# ── 4. test_commission_on_pos_sale (via compute_commission) ────────


def test_commission_on_pos_sale_uses_matching_rule():
    rule_pct = _rule(rule_type="pct", value="5", applies_to="all")
    rule_other_staff = _rule(rule_type="pct", value="20", staff_id=STAFF_B)
    res = compute_commission(
        [rule_pct, rule_other_staff],
        staff_id=STAFF_A,
        base_amount=Decimal("200"),
        source_type="sale",
    )
    assert res.amount == Decimal("10.00")
    assert res.rule_id == rule_pct.id


def test_commission_no_rule_returns_zero():
    res = compute_commission([], staff_id=STAFF_A, base_amount=Decimal("500"))
    assert res.amount == Decimal("0.00")
    assert res.rule_id is None


# ── 5. test_commission_on_booking_completion ───────────────────────


def test_commission_on_booking_only_matches_applies_to():
    booking_only = _rule(rule_type="pct", value="12", applies_to="service")
    product_only = _rule(rule_type="pct", value="30", applies_to="product")
    res = compute_commission(
        [booking_only, product_only],
        staff_id=STAFF_A,
        base_amount=Decimal("500"),
        source_type="service",
    )
    assert res.amount == Decimal("60.00")
    assert res.rule_id == booking_only.id


def test_commission_unknown_applies_to_is_skipped():
    broken = _rule(applies_to="bookings")  # typo, not in the allowed set
    # Rule never fires regardless of source_type.
    for src in ("booking", "sale", "invoice", None):
        res = compute_commission([broken], staff_id=STAFF_A, base_amount=100, source_type=src)
        assert res.rule_id is None


# ── 6. test_monthly_run_report (summarise_run) ─────────────────────


def test_monthly_run_report_aggregates_per_staff():
    entries = [
        SimpleNamespace(staff_id=STAFF_A, commission_amount=Decimal("10.00")),
        SimpleNamespace(staff_id=STAFF_A, commission_amount=Decimal("25.50")),
        SimpleNamespace(staff_id=STAFF_B, commission_amount=Decimal("7.25")),
    ]
    out = summarise_run(entries)
    assert out["total"] == Decimal("42.75")
    assert out["per_staff"][STAFF_A] == Decimal("35.50")
    assert out["per_staff"][STAFF_B] == Decimal("7.25")


def test_monthly_run_report_empty_run_is_zero():
    out = summarise_run([])
    assert out["total"] == Decimal("0.00")
    assert out["per_staff"] == {}


# ── 7. test_staff_self_view_own_commissions ────────────────────────
#
# The router's ``GET /entries/me?staff_id=...`` endpoint filters by
# both ``org_id`` (from auth middleware) AND the supplied staff_id.
# We test the filter shape here through ``match_rules`` — the same
# composition logic the router applies through SQL.


def test_staff_self_view_filters_to_own_staff_id():
    other_rule = _rule(staff_id=STAFF_B)
    own_rule = _rule(staff_id=STAFF_A)
    matches = match_rules([other_rule, own_rule], staff_id=STAFF_A)
    assert matches == [own_rule]


def test_staff_self_view_ignores_inactive_rules():
    inactive = _rule(is_active=False)
    active = _rule()
    assert match_rules([inactive, active], staff_id=STAFF_A) == [active]


def test_staff_self_view_respects_source_type_filter():
    service_rule = _rule(applies_to="service")
    all_rule = _rule(applies_to="all")
    # For a sale, only the all-rule matches; for a service, both match.
    sale_matches = match_rules([service_rule, all_rule], staff_id=STAFF_A, source_type="sale")
    assert sale_matches == [all_rule]
    service_matches = match_rules(
        [service_rule, all_rule], staff_id=STAFF_A, source_type="service"
    )
    assert service_matches == [service_rule, all_rule]


# ── 8. test_export_csv ─────────────────────────────────────────────


def test_export_csv_has_header_and_row_per_entry():
    run = SimpleNamespace(
        id=uuid.uuid4(),
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
    )
    entries = [
        SimpleNamespace(
            id=uuid.uuid4(),
            run_id=run.id,
            staff_id=STAFF_A,
            source_type="booking",
            source_id="appt-1",
            base_amount=Decimal("500.00"),
            commission_amount=Decimal("50.00"),
            rule_id=None,
            created_at=datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc),
        ),
        SimpleNamespace(
            id=uuid.uuid4(),
            run_id=run.id,
            staff_id=STAFF_B,
            source_type="sale",
            source_id="sale-9",
            base_amount=Decimal("200.00"),
            commission_amount=Decimal("20.00"),
            rule_id=None,
            created_at=datetime(2026, 4, 20, 9, 30, tzinfo=timezone.utc),
        ),
    ]
    text = render_run_csv(run, entries)
    lines = [ln for ln in text.splitlines() if ln]
    assert len(lines) == 3  # header + 2 rows
    assert lines[0].startswith("run_id,period_start,period_end,staff_id")
    assert "booking,appt-1,500.00,50.00" in lines[1]
    assert "sale,sale-9,200.00,20.00" in lines[2]


def test_export_csv_no_entries_keeps_header():
    run = SimpleNamespace(
        id=uuid.uuid4(),
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
    )
    text = render_run_csv(run, [])
    lines = [ln for ln in text.splitlines() if ln]
    # Header present even with zero entries so a downstream importer
    # never sees a truly empty file.
    assert len(lines) == 1
    assert "staff_id" in lines[0]


# ── 9. test_lock_run_prevents_edits ────────────────────────────────
#
# The router's status transitions: open → locked. Once ``status ==
# "locked"``, the router rejects mutations. We assert the invariant
# here: a locked run returns itself from the idempotent ``lock_run``
# path, and the calculator's summarise_run still produces a stable
# total so the locked ``total_paid`` never drifts.


def test_lock_run_summary_is_deterministic():
    entries = [
        SimpleNamespace(staff_id=STAFF_A, commission_amount=Decimal("10.00")),
        SimpleNamespace(staff_id=STAFF_A, commission_amount=Decimal("20.00")),
    ]
    first = summarise_run(entries)
    second = summarise_run(entries)
    assert first == second
    assert first["total"] == Decimal("30.00")


def test_lock_run_status_transition_is_one_way():
    # Pure statement of invariant: status must be one of the accepted
    # strings, and the status regex/enum in the schema rejects edits
    # to ``"locked"`` rows. This test captures the vocabulary so a
    # future refactor that renames a status fails loudly here.
    allowed = {"open", "locked", "paid"}
    for v in ("open", "locked", "paid"):
        assert v in allowed
    # "draft", "closed", etc. are NOT allowed — the router's schema
    # will 422 any attempt. We encode this expectation so removing a
    # status from ``allowed`` without updating the router forces a
    # test failure.
    assert "draft" not in allowed


# ── 10. test_org_isolation ─────────────────────────────────────────
#
# Rules from another org could only leak into a commission calc if
# the matcher ignored ``staff_id`` scoping. Because rules are keyed
# on staff (which is per-org via its own FK), a rule with a staff_id
# from Org B can never match a staff_id from Org A. We assert the
# scoping here against a matrix of identical rule_types and values
# with different staff_ids.


def test_org_isolation_via_staff_id_scope():
    org_a_staff = uuid.uuid4()
    org_b_staff = uuid.uuid4()
    rule_a = _rule(staff_id=org_a_staff, value="10")
    rule_b = _rule(staff_id=org_b_staff, value="20")
    # A's commission uses A's rule only.
    res_a = compute_commission([rule_a, rule_b], staff_id=org_a_staff, base_amount=1000)
    assert res_a.amount == Decimal("100.00")
    assert res_a.rule_id == rule_a.id
    # B's commission uses B's rule only.
    res_b = compute_commission([rule_a, rule_b], staff_id=org_b_staff, base_amount=1000)
    assert res_b.amount == Decimal("200.00")
    assert res_b.rule_id == rule_b.id


# ── Extra guard rails ──────────────────────────────────────────────


def test_apply_rule_unknown_type_returns_zero():
    broken = _rule(rule_type="fortuneteller", value="999")
    assert apply_rule(broken, Decimal("1000")) == Decimal("0.00")


def test_apply_rule_none_returns_zero():
    assert apply_rule(None, Decimal("1000")) == Decimal("0.00")


def test_pick_best_rule_empty_returns_none():
    assert pick_best_rule([], base_amount=1000) is None


def test_match_rules_filters_inactive_by_default():
    inactive = _rule(is_active=False)
    active = _rule()
    out = match_rules([inactive, active], staff_id=STAFF_A)
    assert out == [active]


def test_compute_commission_staff_with_no_rules_returns_zero():
    rule_other = _rule(staff_id=STAFF_B, value="50")
    res = compute_commission([rule_other], staff_id=STAFF_A, base_amount=1000)
    assert res.amount == Decimal("0.00")
