"""Item 97 — Recurring expense templates."""
from __future__ import annotations

import pathlib
from datetime import date
from decimal import Decimal

import pytest

from app.services import recurring_expense as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(p: str) -> str:
    return (_BACKEND_ROOT / p).read_text()


SERVICE_SRC   = _read("app/services/recurring_expense.py")
ROUTER_SRC    = _read("app/routers/recurring_expenses.py")
MIGRATION_SRC = _read("migrations/versions/a4b6c8d0e2f7_v95_recurring_expenses.py")
MODEL_SRC     = _read("app/models/recurring_expense.py")
MAIN_SRC      = _read("app/main.py")


# ── validate_title ──────────────────────────────────────────────────────


def test_title_trims_and_returns():
    assert svc.validate_title("  Rent  ") == "Rent"


def test_title_rejects_empty():
    with pytest.raises(ValueError):
        svc.validate_title("")
    with pytest.raises(ValueError):
        svc.validate_title("   ")


def test_title_rejects_non_string():
    with pytest.raises(ValueError):
        svc.validate_title(42)  # type: ignore[arg-type]


def test_title_rejects_over_limit():
    with pytest.raises(ValueError):
        svc.validate_title("x" * (svc.MAX_TITLE_LEN + 1))


def test_title_accepts_at_max_length():
    s = "x" * svc.MAX_TITLE_LEN
    assert svc.validate_title(s) == s


# ── validate_description ────────────────────────────────────────────────


def test_description_none_passes_through():
    assert svc.validate_description(None) is None


def test_description_blank_becomes_none():
    assert svc.validate_description("   ") is None


def test_description_rejects_non_string():
    with pytest.raises(ValueError):
        svc.validate_description(42)  # type: ignore[arg-type]


def test_description_rejects_overlong():
    with pytest.raises(ValueError):
        svc.validate_description("x" * (svc.MAX_DESCRIPTION + 1))


# ── validate_amount ─────────────────────────────────────────────────────


def test_amount_accepts_string_and_quantises():
    # Default Decimal rounding is ROUND_HALF_EVEN (banker's rounding).
    assert svc.validate_amount("12.355") == Decimal("12.36")
    assert svc.validate_amount("1") == Decimal("1.00")


def test_amount_rejects_below_min():
    with pytest.raises(ValueError):
        svc.validate_amount("0.00")


def test_amount_rejects_over_max():
    with pytest.raises(ValueError):
        svc.validate_amount("10000000000.00")


def test_amount_rejects_non_decimal():
    with pytest.raises(ValueError):
        svc.validate_amount("not a number")


# ── validate_currency ───────────────────────────────────────────────────


def test_currency_upper_cases_and_validates():
    assert svc.validate_currency("sek") == "SEK"
    assert svc.validate_currency(" EUR ") == "EUR"


def test_currency_rejects_length_or_non_alpha():
    for bad in ("US", "USDD", "US1", 42, None):
        with pytest.raises(ValueError):
            svc.validate_currency(bad)  # type: ignore[arg-type]


# ── validate_cadence + validate_interval ────────────────────────────────


@pytest.mark.parametrize("c", ["DAILY", "daily", "WEEKLY", "Monthly", "yearly"])
def test_cadence_accepts_all_known(c):
    assert svc.validate_cadence(c) in svc.CADENCES


def test_cadence_rejects_unknown():
    with pytest.raises(ValueError):
        svc.validate_cadence("HOURLY")
    with pytest.raises(ValueError):
        svc.validate_cadence(1)  # type: ignore[arg-type]


def test_interval_accepts_sane_range():
    assert svc.validate_interval(1) == 1
    assert svc.validate_interval(svc.MAX_INTERVAL) == svc.MAX_INTERVAL


def test_interval_rejects_zero_negative_too_large_bool():
    for bad in (0, -1, svc.MAX_INTERVAL + 1, True):
        with pytest.raises(ValueError):
            svc.validate_interval(bad)


# ── validate_dates ──────────────────────────────────────────────────────


def test_dates_ok():
    s, e = svc.validate_dates(
        start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
    )
    assert s == date(2026, 1, 1) and e == date(2026, 12, 31)


def test_dates_allow_null_end():
    s, e = svc.validate_dates(start_date=date(2026, 1, 1), end_date=None)
    assert e is None


def test_dates_reject_reverse():
    with pytest.raises(ValueError):
        svc.validate_dates(
            start_date=date(2026, 6, 1), end_date=date(2026, 1, 1),
        )


def test_dates_reject_non_date():
    with pytest.raises(ValueError):
        svc.validate_dates(
            start_date="2026-01-01", end_date=None,  # type: ignore[arg-type]
        )


# ── advance (cadence math) ──────────────────────────────────────────────


def test_advance_daily():
    assert svc.advance(
        from_date=date(2026, 1, 1), cadence="DAILY", interval=1,
    ) == date(2026, 1, 2)


def test_advance_weekly_three():
    assert svc.advance(
        from_date=date(2026, 1, 1), cadence="WEEKLY", interval=3,
    ) == date(2026, 1, 22)


def test_advance_monthly_clamps_short_month():
    # Jan 31 + 1 month = Feb 28 (2026 is not a leap year).
    assert svc.advance(
        from_date=date(2026, 1, 31), cadence="MONTHLY", interval=1,
    ) == date(2026, 2, 28)


def test_advance_monthly_leap_year():
    assert svc.advance(
        from_date=date(2024, 1, 31), cadence="MONTHLY", interval=1,
    ) == date(2024, 2, 29)


def test_advance_yearly():
    assert svc.advance(
        from_date=date(2026, 2, 29 - 1), cadence="YEARLY", interval=1,
    ) == date(2027, 2, 28)


def test_advance_monthly_rolls_year():
    assert svc.advance(
        from_date=date(2026, 12, 15), cadence="MONTHLY", interval=1,
    ) == date(2027, 1, 15)


# ── compute_next_due ────────────────────────────────────────────────────


def test_next_due_first_occurrence_is_start_date():
    nd = svc.compute_next_due(
        start_date=date(2026, 4, 1), cadence="MONTHLY", interval=1,
        last_generated=None, end_date=None,
    )
    assert nd == date(2026, 4, 1)


def test_next_due_after_generation_advances():
    nd = svc.compute_next_due(
        start_date=date(2026, 4, 1), cadence="MONTHLY", interval=1,
        last_generated=date(2026, 4, 1), end_date=None,
    )
    assert nd == date(2026, 5, 1)


def test_next_due_respects_end_date():
    nd = svc.compute_next_due(
        start_date=date(2026, 4, 1), cadence="MONTHLY", interval=1,
        last_generated=date(2026, 12, 1), end_date=date(2026, 12, 31),
    )
    assert nd is None


def test_next_due_end_date_equals_next_occurrence_allowed():
    nd = svc.compute_next_due(
        start_date=date(2026, 1, 1), cadence="MONTHLY", interval=1,
        last_generated=date(2026, 1, 1), end_date=date(2026, 2, 1),
    )
    assert nd == date(2026, 2, 1)


# ── is_due ──────────────────────────────────────────────────────────────


def test_is_due_true_on_or_before_today():
    assert svc.is_due(next_due_date=date(2026, 4, 24), today=date(2026, 4, 24))
    assert svc.is_due(next_due_date=date(2026, 4, 23), today=date(2026, 4, 24))


def test_is_due_false_after_today():
    assert not svc.is_due(
        next_due_date=date(2026, 4, 25), today=date(2026, 4, 24),
    )


# ── plan_occurrences ────────────────────────────────────────────────────


def test_plan_occurrences_monthly():
    dates = svc.plan_occurrences(
        start_date=date(2026, 1, 31), cadence="MONTHLY", interval=1,
        end_date=None, count=3,
    )
    assert dates == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 28)]


def test_plan_occurrences_stops_at_end_date():
    dates = svc.plan_occurrences(
        start_date=date(2026, 1, 1), cadence="MONTHLY", interval=1,
        end_date=date(2026, 3, 15), count=12,
    )
    assert dates == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]


def test_plan_occurrences_rejects_negative_count():
    with pytest.raises(ValueError):
        svc.plan_occurrences(
            start_date=date(2026, 1, 1), cadence="DAILY", interval=1,
            end_date=None, count=-1,
        )


def test_plan_occurrences_zero_count_empty():
    assert svc.plan_occurrences(
        start_date=date(2026, 1, 1), cadence="DAILY", interval=1,
        end_date=None, count=0,
    ) == []


# ── Constants ───────────────────────────────────────────────────────────


def test_constants_sane():
    assert svc.CADENCES == ("DAILY", "WEEKLY", "MONTHLY", "YEARLY")
    assert svc.MIN_INTERVAL == 1
    assert svc.MAX_INTERVAL == 365
    assert svc.MIN_TITLE_LEN == 1
    assert svc.MAX_TITLE_LEN == 120


# ── Migration source contract ──────────────────────────────────────────


def test_migration_chain_from_v94():
    assert 'down_revision = "f2a4b6c8d0e5"' in MIGRATION_SRC
    assert 'revision = "a4b6c8d0e2f7"' in MIGRATION_SRC


def test_migration_creates_template_table_and_enum():
    assert '"recurring_expense_templates"' in MIGRATION_SRC
    assert '"recurring_expense_cadence"' in MIGRATION_SRC
    for c in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
        assert f'"{c}"' in MIGRATION_SRC


def test_migration_cascades_on_org():
    assert 'ForeignKey("organizations.id", ondelete="CASCADE")' in MIGRATION_SRC


def test_migration_has_hot_scheduler_index():
    assert "ix_recurring_expense_templates_active_due" in MIGRATION_SRC
    assert '["is_active", "next_due_date"]' in MIGRATION_SRC


def test_migration_category_and_supplier_are_set_null():
    # Deleting a category or supplier must not cascade into the
    # template — we just null the link.
    assert 'ForeignKey("expense_categories.id", ondelete="SET NULL")' in MIGRATION_SRC
    assert 'ForeignKey("suppliers.id", ondelete="SET NULL")' in MIGRATION_SRC


# ── Model source contract ──────────────────────────────────────────────


def test_model_tablename_and_fields():
    assert '__tablename__ = "recurring_expense_templates"' in MODEL_SRC
    for f in (
        "org_id", "title", "amount", "currency", "cadence",
        "interval_count", "start_date", "end_date", "next_due_date",
        "last_generated_at", "last_generated_expense_id",
        "generated_count", "is_active",
    ):
        assert f in MODEL_SRC


def test_model_has_enum_class():
    assert "class RecurringExpenseCadence" in MODEL_SRC


# ── Router source contract ─────────────────────────────────────────────


def test_router_prefix_and_all_endpoints():
    assert 'prefix="/api/recurring-expenses"' in ROUTER_SRC
    for path in (
        '@router.get("", ',
        '@router.post(\n    "",',
        '@router.get("/{template_id}"',
        '@router.patch("/{template_id}"',
        '@router.delete("/{template_id}"',
        '@router.post("/{template_id}/generate"',
        '@router.post("/{template_id}/pause"',
        '@router.post("/{template_id}/resume"',
        '@router.get("/{template_id}/preview"',
    ):
        assert path in ROUTER_SRC, f"missing: {path!r}"


def test_router_tenant_scopes_and_404s():
    assert "row.org_id != org_id" in ROUTER_SRC
    assert "RecurringExpenseTemplate.org_id == member.org_id" in ROUTER_SRC
    assert '"Template not found"' in ROUTER_SRC


def test_router_belongs_checks():
    assert "_assert_category_belongs" in ROUTER_SRC
    assert "_assert_supplier_belongs" in ROUTER_SRC
    assert '"Category not found"' in ROUTER_SRC
    assert '"Supplier not found"' in ROUTER_SRC


def test_router_uses_pure_service():
    for n in (
        "svc_97.validate_title",
        "svc_97.validate_amount",
        "svc_97.validate_cadence",
        "svc_97.validate_interval",
        "svc_97.validate_dates",
        "svc_97.compute_next_due",
        "svc_97.plan_occurrences",
    ):
        assert n in ROUTER_SRC


def test_router_emits_six_audit_actions():
    for a in (
        '"recurring_expense.created"',
        '"recurring_expense.updated"',
        '"recurring_expense.deleted"',
        '"recurring_expense.generated"',
        '"recurring_expense.paused"',
        '"recurring_expense.resumed"',
    ):
        assert a in ROUTER_SRC, f"missing audit: {a}"
    assert ROUTER_SRC.count("request=request") >= 6


def test_router_generate_creates_draft_expense():
    # Minted expenses must start as DRAFT so the approval flow kicks
    # in normally.
    assert "status=ExpenseStatus.DRAFT" in ROUTER_SRC


def test_router_generate_auto_deactivates_on_schedule_end():
    # When the next computed due overruns end_date, the template is
    # paused so the scheduler stops picking it up.
    assert "row.is_active = False" in ROUTER_SRC


def test_router_pause_and_resume_are_idempotent():
    assert "if row.is_active:" in ROUTER_SRC
    assert "if not row.is_active:" in ROUTER_SRC


def test_router_resume_rejects_ended_schedule():
    assert '"schedule has ended — cannot resume"' in ROUTER_SRC


def test_router_registered_in_main():
    assert "recurring_expenses.router" in MAIN_SRC
    assert "recurring_expenses," in MAIN_SRC
