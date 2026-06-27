"""Item 99 — Expense budgets."""
from __future__ import annotations

import pathlib
from datetime import date
from decimal import Decimal

import pytest

from app.services import expense_budget as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(p: str) -> str:
    _p = _BACKEND_ROOT / p
    if _p.is_file():
        return _p.read_text()
    # Path was split into a feature package (e.g. routers/invoicing/);
    # concatenate its modules so source-string assertions still hold.
    _pkg = _p.with_suffix("")
    if _pkg.is_dir():
        return "".join(_f.read_text() for _f in sorted(_pkg.rglob("*.py")))
    return _p.read_text()


SERVICE_SRC   = _read("app/services/expense_budget.py")
ROUTER_SRC    = _read("app/features/expenses/expense_budgets.py")
MIGRATION_SRC = _read("migrations/versions/c8d0e2f4a9b2_v97_expense_budgets.py")
MODEL_SRC     = _read("app/features/expenses/expense_budget.py")
MAIN_SRC      = _read("app/main.py")


# ══════════════════════════════════════════════════════════════════════
# Pure service — validators
# ══════════════════════════════════════════════════════════════════════


def test_validate_period_accepts_all():
    for p in svc.PERIODS:
        assert svc.validate_period(p.lower()) == p


def test_validate_period_rejects_unknown():
    with pytest.raises(ValueError):
        svc.validate_period("weekly")


def test_validate_period_rejects_non_string():
    with pytest.raises(ValueError):
        svc.validate_period(7)  # type: ignore[arg-type]


def test_validate_cap_quantises_banker():
    # Banker's rounding.
    assert svc.validate_cap("12.355") == Decimal("12.36")


def test_validate_cap_rejects_below_min():
    with pytest.raises(ValueError):
        svc.validate_cap("0.00")


def test_validate_cap_rejects_over_max():
    with pytest.raises(ValueError):
        svc.validate_cap("10000000000.00")


def test_validate_cap_rejects_non_numeric():
    with pytest.raises(ValueError):
        svc.validate_cap("nope")


def test_validate_cap_rejects_bool():
    with pytest.raises(ValueError):
        svc.validate_cap(True)


def test_validate_threshold_accepts_range():
    assert svc.validate_threshold_pct(1) == 1
    assert svc.validate_threshold_pct(100) == 100
    assert svc.validate_threshold_pct(80) == 80


def test_validate_threshold_rejects_out_of_range():
    with pytest.raises(ValueError):
        svc.validate_threshold_pct(0)
    with pytest.raises(ValueError):
        svc.validate_threshold_pct(101)


def test_validate_threshold_rejects_bool():
    with pytest.raises(ValueError):
        svc.validate_threshold_pct(True)  # type: ignore[arg-type]


def test_validate_threshold_rejects_non_int():
    with pytest.raises(ValueError):
        svc.validate_threshold_pct("80")  # type: ignore[arg-type]


def test_validate_currency_uppercases():
    assert svc.validate_currency("eur") == "EUR"


def test_validate_currency_rejects_non_iso():
    with pytest.raises(ValueError):
        svc.validate_currency("EU")
    with pytest.raises(ValueError):
        svc.validate_currency("EU1")
    with pytest.raises(ValueError):
        svc.validate_currency(None)  # type: ignore[arg-type]


def test_validate_note_none_passes_through():
    assert svc.validate_note(None) is None


def test_validate_note_blank_becomes_none():
    assert svc.validate_note("   ") is None


def test_validate_note_rejects_non_string():
    with pytest.raises(ValueError):
        svc.validate_note(42)  # type: ignore[arg-type]


def test_validate_note_rejects_overlong():
    with pytest.raises(ValueError):
        svc.validate_note("x" * (svc.MAX_NOTE + 1))


def test_validate_note_at_max_length():
    s = "x" * svc.MAX_NOTE
    assert svc.validate_note(s) == s


# ══════════════════════════════════════════════════════════════════════
# Pure service — window math
# ══════════════════════════════════════════════════════════════════════


def test_normalize_month():
    assert svc.normalize_period_start(
        period="MONTH", anchor=date(2026, 4, 24),
    ) == date(2026, 4, 1)


def test_normalize_quarter():
    # Q2 = April
    assert svc.normalize_period_start(
        period="QUARTER", anchor=date(2026, 5, 15),
    ) == date(2026, 4, 1)
    # Q1 = January
    assert svc.normalize_period_start(
        period="QUARTER", anchor=date(2026, 2, 28),
    ) == date(2026, 1, 1)
    # Q3 = July
    assert svc.normalize_period_start(
        period="QUARTER", anchor=date(2026, 9, 30),
    ) == date(2026, 7, 1)
    # Q4 = October
    assert svc.normalize_period_start(
        period="QUARTER", anchor=date(2026, 12, 31),
    ) == date(2026, 10, 1)


def test_normalize_year():
    assert svc.normalize_period_start(
        period="YEAR", anchor=date(2026, 7, 4),
    ) == date(2026, 1, 1)


def test_normalize_rejects_non_date():
    with pytest.raises(ValueError):
        svc.normalize_period_start(
            period="MONTH", anchor="2026-04-01",  # type: ignore[arg-type]
        )


def test_period_end_month():
    assert svc.period_end(
        period="MONTH", period_start=date(2026, 4, 1),
    ) == date(2026, 4, 30)
    # February leap year
    assert svc.period_end(
        period="MONTH", period_start=date(2024, 2, 1),
    ) == date(2024, 2, 29)
    # February non-leap
    assert svc.period_end(
        period="MONTH", period_start=date(2026, 2, 1),
    ) == date(2026, 2, 28)


def test_period_end_quarter():
    assert svc.period_end(
        period="QUARTER", period_start=date(2026, 4, 1),
    ) == date(2026, 6, 30)
    assert svc.period_end(
        period="QUARTER", period_start=date(2026, 10, 1),
    ) == date(2026, 12, 31)
    # Q1 leap
    assert svc.period_end(
        period="QUARTER", period_start=date(2024, 1, 1),
    ) == date(2024, 3, 31)


def test_period_end_year():
    assert svc.period_end(
        period="YEAR", period_start=date(2026, 1, 1),
    ) == date(2026, 12, 31)


def test_period_end_rejects_non_date():
    with pytest.raises(ValueError):
        svc.period_end(
            period="MONTH", period_start="2026-04-01",  # type: ignore[arg-type]
        )


def test_contains_truthy_at_boundaries():
    assert svc.contains(
        period="MONTH", period_start=date(2026, 4, 1), day=date(2026, 4, 1),
    )
    assert svc.contains(
        period="MONTH", period_start=date(2026, 4, 1), day=date(2026, 4, 30),
    )


def test_contains_false_outside():
    assert not svc.contains(
        period="MONTH", period_start=date(2026, 4, 1), day=date(2026, 3, 31),
    )
    assert not svc.contains(
        period="MONTH", period_start=date(2026, 4, 1), day=date(2026, 5, 1),
    )


# ══════════════════════════════════════════════════════════════════════
# Pure service — assess
# ══════════════════════════════════════════════════════════════════════


def test_assess_ok():
    a = svc.assess(cap=Decimal("1000"), spent=Decimal("500"), threshold_pct=80)
    assert a.level == svc.LEVEL_OK
    assert a.spent == Decimal("500.00")
    assert a.remaining == Decimal("500.00")
    assert a.pct_used == 50
    assert a.over_by == Decimal("0.00")


def test_assess_warning_at_threshold():
    a = svc.assess(cap=Decimal("1000"), spent=Decimal("800"), threshold_pct=80)
    assert a.level == svc.LEVEL_WARNING
    assert a.pct_used == 80
    assert a.remaining == Decimal("200.00")


def test_assess_still_warning_at_99pct():
    # Floor-pct keeps 99.9% below 100 until the final cent.
    a = svc.assess(
        cap=Decimal("1000"), spent=Decimal("999.99"), threshold_pct=80,
    )
    assert a.level == svc.LEVEL_WARNING
    assert a.pct_used == 99
    assert a.over_by == Decimal("0.00")


def test_assess_over_at_exact_cap():
    a = svc.assess(cap=Decimal("1000"), spent=Decimal("1000"), threshold_pct=80)
    assert a.level == svc.LEVEL_OVER
    assert a.remaining == Decimal("0.00")
    assert a.over_by == Decimal("0.00")


def test_assess_over_beyond_cap():
    a = svc.assess(cap=Decimal("1000"), spent=Decimal("1250.50"), threshold_pct=80)
    assert a.level == svc.LEVEL_OVER
    assert a.over_by == Decimal("250.50")
    assert a.remaining == Decimal("-250.50")
    assert a.pct_used == 125


def test_assess_clamps_pct_to_999():
    a = svc.assess(cap=Decimal("1"), spent=Decimal("10000"), threshold_pct=80)
    assert a.pct_used == 999
    assert a.level == svc.LEVEL_OVER


def test_assess_zero_spent_is_ok():
    a = svc.assess(cap=Decimal("1000"), spent=Decimal("0"), threshold_pct=80)
    assert a.level == svc.LEVEL_OK
    assert a.pct_used == 0


def test_assess_rejects_non_decimal():
    with pytest.raises(ValueError):
        svc.assess(cap=1000, spent=Decimal("0"), threshold_pct=80)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        svc.assess(cap=Decimal("1000"), spent=0, threshold_pct=80)  # type: ignore[arg-type]


def test_assess_rejects_zero_cap():
    with pytest.raises(ValueError):
        svc.assess(cap=Decimal("0"), spent=Decimal("0"), threshold_pct=80)


def test_assess_rejects_invalid_threshold():
    with pytest.raises(ValueError):
        svc.assess(cap=Decimal("100"), spent=Decimal("10"), threshold_pct=0)
    with pytest.raises(ValueError):
        svc.assess(cap=Decimal("100"), spent=Decimal("10"), threshold_pct=101)


def test_constants_sane():
    assert svc.MIN_CAP == Decimal("0.01")
    assert svc.MAX_CAP == Decimal("9999999999.99")
    assert svc.MIN_THRESHOLD_PCT == 1
    assert svc.MAX_THRESHOLD_PCT == 100
    assert svc.MAX_NOTE == 2_000
    assert svc.PERIODS == ("MONTH", "QUARTER", "YEAR")
    assert svc.LEVEL_OK == "OK"
    assert svc.LEVEL_WARNING == "WARNING"
    assert svc.LEVEL_OVER == "OVER"


# ══════════════════════════════════════════════════════════════════════
# Migration source contract
# ══════════════════════════════════════════════════════════════════════


def test_migration_chains_from_v96():
    assert 'revision = "c8d0e2f4a9b2"' in MIGRATION_SRC
    assert 'down_revision = "b6c8d0e2f4a9"' in MIGRATION_SRC


def test_migration_creates_table():
    assert '"expense_budgets"' in MIGRATION_SRC


def test_migration_creates_enum_with_three_values():
    for v in ("MONTH", "QUARTER", "YEAR"):
        assert f'"{v}"' in MIGRATION_SRC
    assert 'name="expense_budget_period"' in MIGRATION_SRC


def test_migration_org_cascade():
    assert 'organizations.id"' in MIGRATION_SRC
    # Both org and category use CASCADE (delete the org/category ⇒
    # the budget row is meaningless, so cascade is correct).
    assert MIGRATION_SRC.count('ondelete="CASCADE"') >= 2


def test_migration_category_cascade():
    assert 'expense_categories.id"' in MIGRATION_SRC


def test_migration_unique_composite_index():
    assert "ux_expense_budgets_org_cat_period_start" in MIGRATION_SRC
    assert "unique=True" in MIGRATION_SRC


def test_migration_org_id_index():
    assert "ix_expense_budgets_org_id" in MIGRATION_SRC


def test_migration_downgrade_clean():
    assert "drop_table(\"expense_budgets\")" in MIGRATION_SRC
    assert 'Enum(name="expense_budget_period").drop' in MIGRATION_SRC


# ══════════════════════════════════════════════════════════════════════
# Model source contract
# ══════════════════════════════════════════════════════════════════════


def test_model_tablename():
    assert '__tablename__ = "expense_budgets"' in MODEL_SRC


def test_model_has_required_columns():
    for col in (
        "org_id", "category_id", "period", "period_start",
        "amount_cap", "currency", "alert_threshold_pct", "note",
        "created_by_user_id", "created_at", "updated_at",
    ):
        assert f"{col}:" in MODEL_SRC, f"missing column {col!r}"


def test_model_has_enum_class():
    assert "class ExpenseBudgetPeriod" in MODEL_SRC
    for v in ("MONTH", "QUARTER", "YEAR"):
        assert f'{v} = "{v}"' in MODEL_SRC


def test_model_indexes_match_migration():
    assert '"ix_expense_budgets_org_id"' in MODEL_SRC
    assert '"ux_expense_budgets_org_cat_period_start"' in MODEL_SRC
    assert "unique=True" in MODEL_SRC


# ══════════════════════════════════════════════════════════════════════
# Router source contract
# ══════════════════════════════════════════════════════════════════════


def test_router_prefix():
    assert 'prefix="/api/expense-budgets"' in ROUTER_SRC


def test_router_has_all_endpoints():
    assert '@router.get("", response_model=list[BudgetOut])' in ROUTER_SRC
    assert '@router.get("/summary"' in ROUTER_SRC
    assert '@router.post("", response_model=BudgetOut' in ROUTER_SRC
    assert '@router.get("/{budget_id}", response_model=BudgetOut)' in ROUTER_SRC
    assert '@router.get("/{budget_id}/status"' in ROUTER_SRC
    assert '@router.patch("/{budget_id}"' in ROUTER_SRC
    assert '@router.delete("/{budget_id}"' in ROUTER_SRC


def test_router_audit_actions():
    for action in (
        "expense_budget.created",
        "expense_budget.updated",
        "expense_budget.deleted",
    ):
        assert action in ROUTER_SRC, f"missing audit action {action!r}"


def test_router_log_action_exclusively_on_writes():
    # 3 write endpoints → 3 log_action invocations. Reads emit none.
    assert ROUTER_SRC.count("log_action(") == 3


def test_router_log_action_uses_request():
    count_la = ROUTER_SRC.count("log_action(")
    count_rq = ROUTER_SRC.count("request=request")
    assert count_rq >= count_la


def test_router_tenant_scope_at_load():
    assert "row.org_id != org_id" in ROUTER_SRC
    assert '"Budget not found"' in ROUTER_SRC


def test_router_category_belongs_check():
    assert "_assert_category_belongs" in ROUTER_SRC
    assert '"Category not found"' in ROUTER_SRC


def test_router_duplicate_gives_409():
    assert "IntegrityError" in ROUTER_SRC
    assert '"budget already exists' in ROUTER_SRC


def test_router_uses_pure_service():
    for fn in (
        "svc_99.validate_period",
        "svc_99.validate_cap",
        "svc_99.validate_threshold_pct",
        "svc_99.validate_currency",
        "svc_99.validate_note",
        "svc_99.normalize_period_start",
        "svc_99.period_end",
        "svc_99.contains",
        "svc_99.assess",
    ):
        assert fn in ROUTER_SRC, f"missing service call {fn!r}"


def test_router_spend_excludes_rejected():
    # Spend rollup must filter out REJECTED so the UI only counts
    # draft + approved.
    assert "Expense.status != ExpenseStatus.REJECTED" in ROUTER_SRC


def test_router_normalizes_period_start_on_create():
    # Callers may send an arbitrary day-of-month; we snap to the
    # canonical window start before insert so the unique index works.
    assert "normalize_period_start" in ROUTER_SRC


def test_router_summary_filters_to_active_windows():
    # The summary endpoint uses svc_99.contains to skip budgets
    # whose window doesn't cover ``on``.
    assert "svc_99.contains(" in ROUTER_SRC


def test_router_patch_only_mutates_cap_threshold_note():
    # The PATCH request body model must expose only these three
    # fields — changing period / category / start after the fact
    # would break the unique key. Sanity-check the Pydantic model.
    assert "class BudgetUpdate(BaseModel):" in ROUTER_SRC
    # Grab the model block and check its fields.
    start = ROUTER_SRC.index("class BudgetUpdate(BaseModel):")
    end = ROUTER_SRC.index("class BudgetOut(BaseModel):")
    update_block = ROUTER_SRC[start:end]
    assert "amount_cap:" in update_block
    assert "alert_threshold_pct:" in update_block
    assert "note:" in update_block
    # Guard against future additions that would re-open the
    # period/category surface:
    for forbidden in ("period:", "period_start:", "category_id:", "currency:"):
        assert forbidden not in update_block, (
            f"PATCH must not expose {forbidden!r} — it would break "
            "the unique (org, category, period, period_start) index"
        )


# ══════════════════════════════════════════════════════════════════════
# main.py registration
# ══════════════════════════════════════════════════════════════════════


def test_main_imports_router():
    # expense_budgets is registered via expenses_router (vertical-slice architecture)
    feat_src = _read("app/features/expenses/router.py")
    assert "expense_budgets" in feat_src


def test_main_includes_router():
    assert "expenses_router" in MAIN_SRC
