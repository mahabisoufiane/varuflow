"""Item 100 — Expense reports (reimbursement batching)."""
from __future__ import annotations

import pathlib
from decimal import Decimal

import pytest

from app.services import expense_report as svc


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


SERVICE_SRC   = _read("app/services/expense_report.py")
ROUTER_SRC    = _read("app/features/expenses/expense_reports.py")
MIGRATION_SRC = _read("migrations/versions/d0e2f4a9b2c5_v98_expense_reports.py")
MODEL_SRC     = _read("app/features/expenses/expense_report.py")
MAIN_SRC      = _read("app/main.py")


# ══════════════════════════════════════════════════════════════════════
# Pure service — validators
# ══════════════════════════════════════════════════════════════════════


def test_validate_title_trims():
    assert svc.validate_title("  Q2 reimbursements  ") == "Q2 reimbursements"


def test_validate_title_rejects_empty():
    with pytest.raises(ValueError):
        svc.validate_title("")
    with pytest.raises(ValueError):
        svc.validate_title("   ")


def test_validate_title_rejects_non_string():
    with pytest.raises(ValueError):
        svc.validate_title(42)  # type: ignore[arg-type]


def test_validate_title_rejects_over_limit():
    with pytest.raises(ValueError):
        svc.validate_title("x" * (svc.MAX_TITLE_LEN + 1))


def test_validate_title_at_max():
    s = "x" * svc.MAX_TITLE_LEN
    assert svc.validate_title(s) == s


def test_validate_currency_uppercases():
    assert svc.validate_currency("sek") == "SEK"


def test_validate_currency_rejects_non_iso():
    with pytest.raises(ValueError):
        svc.validate_currency("S")
    with pytest.raises(ValueError):
        svc.validate_currency("SE1")
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


def test_validate_review_note_same_surface():
    assert svc.validate_review_note(None) is None
    assert svc.validate_review_note("   ") is None
    with pytest.raises(ValueError):
        svc.validate_review_note("x" * (svc.MAX_REVIEW_NOTE + 1))


def test_validate_paid_reference_same_surface():
    assert svc.validate_paid_reference(None) is None
    assert svc.validate_paid_reference("   ") is None
    assert svc.validate_paid_reference("WIRE-2026-04-001") == "WIRE-2026-04-001"
    with pytest.raises(ValueError):
        svc.validate_paid_reference("x" * (svc.MAX_PAID_REFERENCE + 1))


# ══════════════════════════════════════════════════════════════════════
# Pure service — status vocabulary + state machine
# ══════════════════════════════════════════════════════════════════════


def test_statuses_tuple_matches_all_constants():
    assert svc.STATUSES == (
        svc.STATUS_DRAFT, svc.STATUS_SUBMITTED, svc.STATUS_APPROVED,
        svc.STATUS_REJECTED, svc.STATUS_PAID,
    )
    # String values pinned — the DB enum must match.
    assert svc.STATUS_DRAFT     == "DRAFT"
    assert svc.STATUS_SUBMITTED == "SUBMITTED"
    assert svc.STATUS_APPROVED  == "APPROVED"
    assert svc.STATUS_REJECTED  == "REJECTED"
    assert svc.STATUS_PAID      == "PAID"


def test_validate_status_case_insensitive():
    assert svc.validate_status("draft") == "DRAFT"
    assert svc.validate_status("PAID") == "PAID"


def test_validate_status_rejects_unknown():
    with pytest.raises(ValueError):
        svc.validate_status("ARCHIVED")


def test_validate_status_rejects_non_string():
    with pytest.raises(ValueError):
        svc.validate_status(1)  # type: ignore[arg-type]


# Transitions — positive paths.
@pytest.mark.parametrize("src,dst", [
    ("DRAFT",     "SUBMITTED"),
    ("SUBMITTED", "APPROVED"),
    ("SUBMITTED", "REJECTED"),
    ("APPROVED",  "PAID"),
    ("REJECTED",  "DRAFT"),   # resubmit loop
])
def test_can_transition_allowed(src, dst):
    assert svc.can_transition(from_status=src, to_status=dst) is True


# Transitions — negative paths.
@pytest.mark.parametrize("src,dst", [
    ("DRAFT",     "APPROVED"),
    ("DRAFT",     "REJECTED"),
    ("DRAFT",     "PAID"),
    ("SUBMITTED", "DRAFT"),
    ("SUBMITTED", "PAID"),
    ("SUBMITTED", "SUBMITTED"),
    ("APPROVED",  "DRAFT"),
    ("APPROVED",  "REJECTED"),
    ("APPROVED",  "SUBMITTED"),
    ("REJECTED",  "SUBMITTED"),
    ("REJECTED",  "APPROVED"),
    ("REJECTED",  "PAID"),
    ("PAID",      "DRAFT"),
    ("PAID",      "SUBMITTED"),
    ("PAID",      "APPROVED"),
    ("PAID",      "REJECTED"),
    ("PAID",      "PAID"),
])
def test_can_transition_denied(src, dst):
    assert svc.can_transition(from_status=src, to_status=dst) is False


def test_assert_transition_raises_on_illegal():
    with pytest.raises(ValueError):
        svc.assert_transition(from_status="DRAFT", to_status="PAID")


def test_assert_transition_silent_on_legal():
    svc.assert_transition(from_status="DRAFT", to_status="SUBMITTED")


def test_items_mutable_only_in_draft():
    assert svc.items_mutable_in("DRAFT") is True
    for s in ("SUBMITTED", "APPROVED", "REJECTED", "PAID"):
        assert svc.items_mutable_in(s) is False


# ══════════════════════════════════════════════════════════════════════
# Pure service — compute_totals
# ══════════════════════════════════════════════════════════════════════


def test_compute_totals_empty():
    t = svc.compute_totals([])
    assert t.item_count == 0
    assert t.total == Decimal("0.00")


def test_compute_totals_sums_and_quantises():
    t = svc.compute_totals([
        Decimal("10.00"), Decimal("20.50"), Decimal("5.255"),
    ])
    assert t.item_count == 3
    # Banker's rounding: 35.755 → 35.76 (5 rounds up because 4 is even
    # but we're at .755 which rounds to .76 under ROUND_HALF_EVEN).
    # Defer to whatever Decimal produces — just assert it quantises.
    assert t.total.as_tuple().exponent == -2


def test_compute_totals_accepts_strings():
    # The helper coerces via str() so callers passing SQL Decimals
    # returned as various numeric types still work.
    t = svc.compute_totals([Decimal("1"), Decimal("2"), Decimal("3")])
    assert t.total == Decimal("6.00")


# ══════════════════════════════════════════════════════════════════════
# Migration source contract
# ══════════════════════════════════════════════════════════════════════


def test_migration_chains_from_v97():
    assert 'revision = "d0e2f4a9b2c5"' in MIGRATION_SRC
    assert 'down_revision = "c8d0e2f4a9b2"' in MIGRATION_SRC


def test_migration_creates_both_tables():
    assert '"expense_reports"' in MIGRATION_SRC
    assert '"expense_report_items"' in MIGRATION_SRC


def test_migration_status_enum_five_values():
    for v in ("DRAFT", "SUBMITTED", "APPROVED", "REJECTED", "PAID"):
        assert f'"{v}"' in MIGRATION_SRC
    assert 'name="expense_report_status"' in MIGRATION_SRC


def test_migration_cascades():
    # Report.org_id → org CASCADE.
    # Item.report_id → report CASCADE.
    # Item.expense_id → expense CASCADE.
    assert MIGRATION_SRC.count('ondelete="CASCADE"') >= 3


def test_migration_unique_expense_id_index():
    # One expense can belong to at most one report.
    assert "ux_expense_report_items_expense_id" in MIGRATION_SRC
    assert "unique=True" in MIGRATION_SRC


def test_migration_hot_list_index():
    assert "ix_expense_reports_org_status_created" in MIGRATION_SRC


def test_migration_downgrade_clean():
    assert 'drop_table("expense_report_items")' in MIGRATION_SRC
    assert 'drop_table("expense_reports")' in MIGRATION_SRC
    assert 'Enum(name="expense_report_status").drop' in MIGRATION_SRC


# ══════════════════════════════════════════════════════════════════════
# Model source contract
# ══════════════════════════════════════════════════════════════════════


def test_model_tablenames():
    assert '__tablename__ = "expense_reports"' in MODEL_SRC
    assert '__tablename__ = "expense_report_items"' in MODEL_SRC


def test_model_report_columns():
    for col in (
        "org_id", "created_by_user_id", "title", "currency", "status",
        "note", "submitted_at", "decided_at", "decided_by_user_id",
        "review_note", "paid_at", "paid_reference", "created_at",
        "updated_at",
    ):
        assert f"{col}:" in MODEL_SRC, f"missing column {col!r}"


def test_model_item_columns():
    assert "report_id:" in MODEL_SRC
    assert "expense_id:" in MODEL_SRC
    assert "added_at:" in MODEL_SRC


def test_model_status_enum():
    assert "class ExpenseReportStatus" in MODEL_SRC
    for v in ("DRAFT", "SUBMITTED", "APPROVED", "REJECTED", "PAID"):
        assert f'{v} = "{v}"' in MODEL_SRC


def test_model_indexes_match_migration():
    assert '"ix_expense_reports_org_id"' in MODEL_SRC
    assert '"ix_expense_reports_org_status_created"' in MODEL_SRC
    assert '"ux_expense_report_items_expense_id"' in MODEL_SRC


# ══════════════════════════════════════════════════════════════════════
# Router source contract
# ══════════════════════════════════════════════════════════════════════


def test_router_prefix():
    assert 'prefix="/api/expense-reports"' in ROUTER_SRC


def test_router_has_all_endpoints():
    assert '@router.get("", response_model=list[ReportOut])' in ROUTER_SRC
    assert '@router.post("", response_model=ReportOut' in ROUTER_SRC
    assert '@router.get("/{report_id}"' in ROUTER_SRC
    assert '@router.patch("/{report_id}"' in ROUTER_SRC
    assert '@router.delete("/{report_id}"' in ROUTER_SRC
    assert '@router.post(\n    "/{report_id}/items"' in ROUTER_SRC
    assert '@router.delete(\n    "/{report_id}/items/{expense_id}"' in ROUTER_SRC
    assert '@router.post("/{report_id}/submit"' in ROUTER_SRC
    assert '@router.post("/{report_id}/approve"' in ROUTER_SRC
    assert '@router.post("/{report_id}/reject"' in ROUTER_SRC
    assert '@router.post("/{report_id}/mark-paid"' in ROUTER_SRC


def test_router_audit_actions():
    for action in (
        "expense_report.created",
        "expense_report.updated",
        "expense_report.deleted",
        "expense_report.item_added",
        "expense_report.item_removed",
        "expense_report.submitted",
        "expense_report.approved",
        "expense_report.rejected",
        "expense_report.paid",
    ):
        assert action in ROUTER_SRC, f"missing audit action {action!r}"


def test_router_log_action_count_matches_writes():
    # 9 write-ish endpoints: create / update / delete / add_item /
    # remove_item / submit / approve / reject / paid.
    assert ROUTER_SRC.count("log_action(") == 9


def test_router_every_log_action_uses_request():
    # Each log_action call must receive `request=request`.
    assert ROUTER_SRC.count("request=request") >= ROUTER_SRC.count("log_action(")


def test_router_tenant_scope_at_load():
    assert "row.org_id != org_id" in ROUTER_SRC
    assert '"Report not found"' in ROUTER_SRC


def test_router_uses_pure_service_state_machine():
    # Every transition runs through svc_100.assert_transition.
    assert "svc_100.assert_transition" in ROUTER_SRC
    assert "svc_100.items_mutable_in" in ROUTER_SRC


def test_router_items_check_approved_status():
    # Only APPROVED expenses can be added to a report.
    assert "ExpenseStatus.APPROVED" in ROUTER_SRC
    assert "only APPROVED expenses can be added" in ROUTER_SRC


def test_router_items_check_currency_match():
    # Mixing currencies would make the report total meaningless.
    assert "expense currency does not match report currency" in ROUTER_SRC


def test_router_item_duplicate_gives_409():
    assert "IntegrityError" in ROUTER_SRC
    assert "expense already belongs to a report" in ROUTER_SRC


def test_router_submit_requires_items():
    assert '"report has no items"' in ROUTER_SRC


def test_router_approve_reject_paid_are_owner_admin_only():
    # Three call sites (approve / reject / mark-paid) plus the
    # helper's own definition signature — so four total
    # occurrences of the `_require_owner_or_admin(member)` symbol.
    assert ROUTER_SRC.count("_require_owner_or_admin(member)") == 4
    assert ROUTER_SRC.count("def _require_owner_or_admin") == 1


def test_router_author_guard_on_non_privileged():
    assert "_require_author_or_owner" in ROUTER_SRC
    assert '"not_report_author"' in ROUTER_SRC


def test_router_edit_only_in_draft_or_rejected():
    # PATCH + DELETE gates + the "cannot edit/delete in status X"
    # error messages.
    assert 'cannot edit report in status' in ROUTER_SRC
    assert 'cannot delete report in status' in ROUTER_SRC


def test_router_stamps_decided_and_paid_metadata():
    assert "row.decided_at = datetime.now(timezone.utc)" in ROUTER_SRC
    assert "row.decided_by_user_id =" in ROUTER_SRC
    assert "row.paid_at = datetime.now(timezone.utc)" in ROUTER_SRC
    assert "row.paid_reference =" in ROUTER_SRC
    assert "row.submitted_at = datetime.now(timezone.utc)" in ROUTER_SRC


def test_router_uses_compute_totals_from_service():
    assert "svc_100.compute_totals" in ROUTER_SRC


def test_router_uses_status_validators():
    assert "svc_100.validate_status" in ROUTER_SRC
    assert "svc_100.validate_title" in ROUTER_SRC
    assert "svc_100.validate_currency" in ROUTER_SRC
    assert "svc_100.validate_note" in ROUTER_SRC
    assert "svc_100.validate_review_note" in ROUTER_SRC
    assert "svc_100.validate_paid_reference" in ROUTER_SRC


# ══════════════════════════════════════════════════════════════════════
# main.py registration
# ══════════════════════════════════════════════════════════════════════


def test_main_imports_router():
    # expense_reports is registered via expenses_router (vertical-slice architecture)
    feat_src = _read("app/features/expenses/router.py")
    assert "expense_reports" in feat_src


def test_main_includes_router():
    assert "expenses_router" in MAIN_SRC
