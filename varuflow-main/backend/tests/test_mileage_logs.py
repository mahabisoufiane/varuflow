"""Item 98 — Mileage logs."""
from __future__ import annotations

import pathlib
from datetime import date
from decimal import Decimal

import pytest

from app.services import mileage as svc


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


SERVICE_SRC   = _read("app/services/mileage.py")
ROUTER_SRC    = _read("app/features/expenses/mileage_logs.py")
MIGRATION_SRC = _read("migrations/versions/b6c8d0e2f4a9_v96_mileage_logs.py")
MODEL_SRC     = _read("app/features/expenses/mileage_log.py")
MAIN_SRC      = _read("app/main.py")


# ══════════════════════════════════════════════════════════════════════
# Pure service — validators
# ══════════════════════════════════════════════════════════════════════


def test_distance_accepts_string_and_quantises():
    assert svc.validate_distance("12.345") == Decimal("12.34")  # banker's
    assert svc.validate_distance("1") == Decimal("1.00")


def test_distance_rejects_below_min():
    with pytest.raises(ValueError):
        svc.validate_distance("0.00")


def test_distance_rejects_over_max():
    with pytest.raises(ValueError):
        svc.validate_distance("100000.01")


def test_distance_rejects_non_numeric():
    with pytest.raises(ValueError):
        svc.validate_distance("not a number")


def test_distance_rejects_bool():
    with pytest.raises(ValueError):
        svc.validate_distance(True)


def test_rate_accepts_four_decimals():
    assert svc.validate_rate("25.0000") == Decimal("25.0000")
    assert svc.validate_rate("2") == Decimal("2.0000")


def test_rate_zero_allowed():
    # Rate 0 is permissible (e.g. company car with zero reimbursement).
    assert svc.validate_rate("0") == Decimal("0.0000")


def test_rate_rejects_negative():
    with pytest.raises(ValueError):
        svc.validate_rate("-0.0001")


def test_rate_rejects_over_max():
    with pytest.raises(ValueError):
        svc.validate_rate("10000")


def test_rate_rejects_non_numeric():
    with pytest.raises(ValueError):
        svc.validate_rate("zilch")


def test_rate_rejects_bool():
    with pytest.raises(ValueError):
        svc.validate_rate(False)


def test_currency_uppercases():
    assert svc.validate_currency("sek") == "SEK"


def test_currency_rejects_non_iso():
    with pytest.raises(ValueError):
        svc.validate_currency("se")
    with pytest.raises(ValueError):
        svc.validate_currency("SE1")
    with pytest.raises(ValueError):
        svc.validate_currency(123)  # type: ignore[arg-type]


def test_trip_date_accepts_date():
    d = date(2026, 4, 24)
    assert svc.validate_trip_date(d) is d


def test_trip_date_rejects_non_date():
    with pytest.raises(ValueError):
        svc.validate_trip_date("2026-04-24")  # type: ignore[arg-type]


def test_origin_destination_purpose_vehicle_none_passes_through():
    assert svc.validate_origin(None) is None
    assert svc.validate_destination(None) is None
    assert svc.validate_purpose(None) is None
    assert svc.validate_vehicle(None) is None


def test_origin_destination_purpose_vehicle_blank_becomes_none():
    assert svc.validate_origin("   ") is None
    assert svc.validate_destination("   ") is None
    assert svc.validate_purpose("   ") is None
    assert svc.validate_vehicle("   ") is None


def test_origin_destination_purpose_vehicle_reject_non_string():
    with pytest.raises(ValueError):
        svc.validate_origin(123)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        svc.validate_destination(123)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        svc.validate_purpose(123)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        svc.validate_vehicle(123)  # type: ignore[arg-type]


def test_origin_rejects_overlong():
    with pytest.raises(ValueError):
        svc.validate_origin("x" * (svc.MAX_TEXT + 1))


def test_destination_rejects_overlong():
    with pytest.raises(ValueError):
        svc.validate_destination("x" * (svc.MAX_TEXT + 1))


def test_purpose_rejects_overlong():
    with pytest.raises(ValueError):
        svc.validate_purpose("x" * (svc.MAX_PURPOSE + 1))


def test_vehicle_rejects_overlong():
    with pytest.raises(ValueError):
        svc.validate_vehicle("x" * (svc.MAX_VEHICLE + 1))


def test_origin_destination_purpose_vehicle_at_max_length():
    assert svc.validate_origin("x" * svc.MAX_TEXT) == "x" * svc.MAX_TEXT
    assert svc.validate_destination("x" * svc.MAX_TEXT) == "x" * svc.MAX_TEXT
    assert svc.validate_purpose("x" * svc.MAX_PURPOSE) == "x" * svc.MAX_PURPOSE
    assert svc.validate_vehicle("x" * svc.MAX_VEHICLE) == "x" * svc.MAX_VEHICLE


# ══════════════════════════════════════════════════════════════════════
# Pure service — compute_amount
# ══════════════════════════════════════════════════════════════════════


def test_compute_amount_basic():
    d = svc.validate_distance("100")
    r = svc.validate_rate("25")
    assert svc.compute_amount(distance_km=d, rate_per_km=r) == Decimal("2500.00")


def test_compute_amount_quantises_to_cents():
    d = svc.validate_distance("12.34")
    r = svc.validate_rate("0.5555")
    # 12.34 * 0.5555 = 6.85487 → 6.85 (banker's)
    assert svc.compute_amount(distance_km=d, rate_per_km=r) == Decimal("6.85")


def test_compute_amount_zero_rate_is_zero():
    d = svc.validate_distance("999")
    r = svc.validate_rate("0")
    assert svc.compute_amount(distance_km=d, rate_per_km=r) == Decimal("0.00")


def test_compute_amount_rejects_non_decimal():
    with pytest.raises(ValueError):
        svc.compute_amount(distance_km=1.0, rate_per_km=Decimal("1"))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        svc.compute_amount(distance_km=Decimal("1"), rate_per_km="2")  # type: ignore[arg-type]


# ══════════════════════════════════════════════════════════════════════
# Pure service — summarize
# ══════════════════════════════════════════════════════════════════════


def test_summarize_empty():
    s = svc.summarize([])
    assert s.trip_count == 0
    assert s.total_km == Decimal("0.00")
    assert s.total_amount == Decimal("0.00")
    assert s.currency is None


def test_summarize_single_currency():
    s = svc.summarize([
        (Decimal("10"), Decimal("250"), "SEK"),
        (Decimal("5"),  Decimal("125"), "SEK"),
    ])
    assert s.trip_count == 2
    assert s.total_km == Decimal("15.00")
    assert s.total_amount == Decimal("375.00")
    assert s.currency == "SEK"


def test_summarize_mixed_currency_drops_currency():
    s = svc.summarize([
        (Decimal("10"), Decimal("250"), "SEK"),
        (Decimal("5"),  Decimal("100"), "EUR"),
    ])
    assert s.trip_count == 2
    assert s.currency is None  # mixed → caller shows "Mixed"


def test_summarize_quantises_totals():
    s = svc.summarize([
        (Decimal("1.234"), Decimal("3.005"), "SEK"),
        (Decimal("2.345"), Decimal("5.005"), "SEK"),
    ])
    # totals quantised banker's
    assert s.total_km   == Decimal("3.58")
    assert s.total_amount == Decimal("8.01")


# ══════════════════════════════════════════════════════════════════════
# Constants sanity
# ══════════════════════════════════════════════════════════════════════


def test_constants_sane():
    assert svc.MIN_DISTANCE == Decimal("0.01")
    assert svc.MAX_DISTANCE == Decimal("100000.00")
    assert svc.MIN_RATE == Decimal("0")
    assert svc.MAX_RATE == Decimal("9999.9999")
    assert svc.MAX_TEXT == 200
    assert svc.MAX_PURPOSE == 255
    assert svc.MAX_VEHICLE == 40


# ══════════════════════════════════════════════════════════════════════
# Migration source contract
# ══════════════════════════════════════════════════════════════════════


def test_migration_chains_from_v95():
    assert 'revision = "b6c8d0e2f4a9"' in MIGRATION_SRC
    assert 'down_revision = "a4b6c8d0e2f7"' in MIGRATION_SRC


def test_migration_creates_table():
    assert '"mileage_logs"' in MIGRATION_SRC


def test_migration_org_id_cascade():
    assert 'organizations.id"' in MIGRATION_SRC
    assert 'ondelete="CASCADE"' in MIGRATION_SRC


def test_migration_category_set_null():
    assert 'expense_categories.id"' in MIGRATION_SRC
    # SET NULL appears for the FK on category_id and expense_id
    assert MIGRATION_SRC.count('ondelete="SET NULL"') >= 2


def test_migration_expense_id_set_null():
    assert 'expenses.id"' in MIGRATION_SRC


def test_migration_decimal_columns():
    # distance_km is Numeric(10,2), rate_per_km is Numeric(10,4),
    # amount is Numeric(14,2).
    assert "Numeric(10, 2)" in MIGRATION_SRC
    assert "Numeric(10, 4)" in MIGRATION_SRC
    assert "Numeric(14, 2)" in MIGRATION_SRC


def test_migration_indexes():
    assert "ix_mileage_logs_org_id" in MIGRATION_SRC
    assert "ix_mileage_logs_org_trip_date" in MIGRATION_SRC


def test_migration_downgrade_drops_table_and_indexes():
    assert "drop_table(\"mileage_logs\")" in MIGRATION_SRC
    assert "drop_index(\"ix_mileage_logs_org_id\"" in MIGRATION_SRC
    assert "drop_index(\"ix_mileage_logs_org_trip_date\"" in MIGRATION_SRC


# ══════════════════════════════════════════════════════════════════════
# Model source contract
# ══════════════════════════════════════════════════════════════════════


def test_model_tablename():
    assert '__tablename__ = "mileage_logs"' in MODEL_SRC


def test_model_has_required_columns():
    for col in (
        "trip_date", "distance_km", "rate_per_km", "amount", "currency",
        "category_id", "origin", "destination", "purpose", "vehicle",
        "expense_id", "converted_at",
    ):
        assert f"{col}:" in MODEL_SRC, f"missing column {col!r}"


def test_model_indexes_match_migration():
    assert '"ix_mileage_logs_org_id"' in MODEL_SRC
    assert '"ix_mileage_logs_org_trip_date"' in MODEL_SRC


# ══════════════════════════════════════════════════════════════════════
# Router source contract
# ══════════════════════════════════════════════════════════════════════


def test_router_prefix():
    assert 'prefix="/api/mileage-logs"' in ROUTER_SRC


def test_router_has_all_endpoints():
    # 7 endpoints
    assert '@router.get("", response_model=list[LogOut])' in ROUTER_SRC
    assert '@router.get("/summary"' in ROUTER_SRC
    assert '@router.post("", response_model=LogOut' in ROUTER_SRC
    assert '@router.get("/{log_id}"' in ROUTER_SRC
    assert '@router.patch("/{log_id}"' in ROUTER_SRC
    assert '@router.delete("/{log_id}"' in ROUTER_SRC
    assert '@router.post("/{log_id}/convert"' in ROUTER_SRC


def test_router_audit_actions():
    # 4 audit actions: created / updated / deleted / converted.
    for action in (
        "mileage_log.created",
        "mileage_log.updated",
        "mileage_log.deleted",
        "mileage_log.converted",
    ):
        assert action in ROUTER_SRC, f"missing audit action {action!r}"


def test_router_log_action_uses_request():
    # Every log_action invocation must be passed `request=request`.
    log_action_count = ROUTER_SRC.count("log_action(")
    request_kw_count = ROUTER_SRC.count("request=request")
    assert log_action_count == 4
    assert request_kw_count >= log_action_count


def test_router_tenant_scope_at_load():
    assert "row.org_id != org_id" in ROUTER_SRC
    assert '"Mileage log not found"' in ROUTER_SRC


def test_router_category_belongs_check():
    assert "_assert_category_belongs" in ROUTER_SRC
    assert '"Category not found"' in ROUTER_SRC


def test_router_uses_pure_service():
    # Wired through svc_98.* helpers.
    for fn in (
        "svc_98.validate_distance",
        "svc_98.validate_rate",
        "svc_98.validate_currency",
        "svc_98.validate_trip_date",
        "svc_98.validate_origin",
        "svc_98.validate_destination",
        "svc_98.validate_purpose",
        "svc_98.validate_vehicle",
        "svc_98.compute_amount",
        "svc_98.summarize",
    ):
        assert fn in ROUTER_SRC, f"missing service call {fn!r}"


def test_router_convert_creates_draft_expense():
    # Conversion mints an Expense in DRAFT status.
    assert "ExpenseStatus.DRAFT" in ROUTER_SRC


def test_router_convert_links_back():
    assert "row.expense_id = expense.id" in ROUTER_SRC
    assert "row.converted_at = datetime.now(timezone.utc)" in ROUTER_SRC


def test_router_convert_idempotent_check():
    # Refuses double-conversion with 409.
    assert '"log already converted"' in ROUTER_SRC


def test_router_update_blocked_after_conversion():
    assert '"log has been converted' in ROUTER_SRC


def test_router_summary_validates_date_range():
    assert '"to_date must be >= from_date"' in ROUTER_SRC


def test_router_list_supports_only_unconverted_filter():
    assert "only_unconverted" in ROUTER_SRC
    assert "MileageLog.expense_id.is_(None)" in ROUTER_SRC


def test_router_recomputes_amount_on_distance_or_rate_change():
    # The denormalised amount must be recomputed when either input
    # changes.
    assert '"distance_km" in changed or "rate_per_km" in changed' in ROUTER_SRC


def test_router_no_log_action_on_reads():
    # log_action must NEVER be called from the GET endpoints.
    # Heuristic: there's exactly one log_action per write endpoint
    # (4 total) and we already counted 4.
    assert ROUTER_SRC.count("log_action(") == 4


# ══════════════════════════════════════════════════════════════════════
# main.py registration
# ══════════════════════════════════════════════════════════════════════


def test_main_imports_router():
    # mileage_logs is registered via expenses_router (vertical-slice architecture)
    feat_src = _read("app/features/expenses/router.py")
    assert "mileage_logs" in feat_src


def test_main_includes_router():
    assert "expenses_router" in MAIN_SRC
