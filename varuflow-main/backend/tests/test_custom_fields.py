"""Item 59 — Custom fields for products, customers, invoices.

Pure + source-contract tests. Follows Items 51-58 style.
"""
from __future__ import annotations

import pathlib
from decimal import Decimal

import pytest

from app.services import custom_field as svc


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


MIGRATION_SRC = _read(
    "migrations/versions/d8f0b2c4e6a9_v68_custom_fields.py"
)
MODEL_SRC = _read("app/features/customers/custom_field.py")
SERVICE_SRC = _read("app/services/custom_field.py")
ROUTER_SRC = _read("app/features/customers/custom_fields.py")
MAIN_SRC = _read("app/main.py")


def _d(**k):
    base = dict(
        entity_type="product",
        name="color",
        label="Color",
        field_type="text",
        is_required=False,
        options=None,
    )
    base.update(k)
    return svc.DefinitionInput(**base)


# ── Definition validation ────────────────────────────────────────────────


def test_validate_definition_happy_path():
    svc.validate_definition(_d())
    svc.validate_definition(
        _d(field_type="select", options=["red", "blue"])
    )


def test_validate_definition_rejects_bad_entity_type():
    with pytest.raises(ValueError):
        svc.validate_definition(_d(entity_type="staff"))


def test_validate_definition_rejects_bad_field_type():
    with pytest.raises(ValueError):
        svc.validate_definition(_d(field_type="json"))


def test_validate_definition_enforces_name_shape():
    for bad in ("", "1abc", "BAD", "with space", "a", "x" * 65):
        with pytest.raises(ValueError):
            svc.validate_definition(_d(name=bad))


def test_validate_definition_rejects_bad_label():
    with pytest.raises(ValueError):
        svc.validate_definition(_d(label=""))
    with pytest.raises(ValueError):
        svc.validate_definition(_d(label="x" * (svc.MAX_LABEL_LENGTH + 1)))


def test_validate_definition_select_requires_options():
    with pytest.raises(ValueError):
        svc.validate_definition(_d(field_type="select", options=None))
    with pytest.raises(ValueError):
        svc.validate_definition(_d(field_type="select", options=[]))
    with pytest.raises(ValueError):
        svc.validate_definition(
            _d(field_type="select", options=["a", "a"])
        )


def test_validate_definition_rejects_options_on_non_select():
    with pytest.raises(ValueError):
        svc.validate_definition(_d(field_type="text", options=["red"]))


# ── Value coercion ────────────────────────────────────────────────────────


def test_coerce_value_text_roundtrip():
    assert svc.coerce_value("text", "  hello ") == "hello"
    assert svc.coerce_value("text", "") is None
    with pytest.raises(ValueError):
        svc.coerce_value("text", "x" * (svc.MAX_TEXT_VALUE_LENGTH + 1))


def test_coerce_value_number_accepts_int_float_decimal():
    assert svc.coerce_value("number", 42) == "42"
    assert svc.coerce_value("number", "3.14") == "3.14"
    assert svc.coerce_value("number", Decimal("100.00")) == "100"  # normalised
    with pytest.raises(ValueError):
        svc.coerce_value("number", "abc")
    with pytest.raises(ValueError):
        svc.coerce_value("number", "NaN")
    with pytest.raises(ValueError):
        svc.coerce_value("number", "Infinity")


def test_coerce_value_boolean_variants():
    for t in (True, "true", "YES", "1"):
        assert svc.coerce_value("boolean", t) == "true"
    for f in (False, "false", "no", "0"):
        assert svc.coerce_value("boolean", f) == "false"
    with pytest.raises(ValueError):
        svc.coerce_value("boolean", "maybe")


def test_coerce_value_date_iso_only():
    assert svc.coerce_value("date", "2026-05-01") == "2026-05-01"
    for bad in ("2026/05/01", "01-05-2026", "2026-13-01"):
        with pytest.raises(ValueError):
            svc.coerce_value("date", bad)


def test_coerce_value_select_whitelists_options():
    assert svc.coerce_value("select", "red", options=["red", "blue"]) == "red"
    with pytest.raises(ValueError):
        svc.coerce_value("select", "green", options=["red", "blue"])
    with pytest.raises(ValueError):
        svc.coerce_value("select", "red", options=[])


def test_coerce_value_required_rejects_empty():
    with pytest.raises(ValueError):
        svc.coerce_value("text", None, required=True)
    with pytest.raises(ValueError):
        svc.coerce_value("text", "", required=True)


def test_coerce_value_unknown_type():
    with pytest.raises(ValueError):
        svc.coerce_value("json", "{}")


# ── Cast on read ─────────────────────────────────────────────────────────


def test_cast_for_read_roundtrip():
    assert svc.cast_for_read("number", "42") == 42
    assert svc.cast_for_read("number", "3.14") == 3.14
    assert svc.cast_for_read("boolean", "true") is True
    assert svc.cast_for_read("boolean", "false") is False
    assert svc.cast_for_read("text", "abc") == "abc"
    assert svc.cast_for_read("date", "2026-05-01") == "2026-05-01"
    assert svc.cast_for_read("select", "red") == "red"
    assert svc.cast_for_read("number", None) is None


# ── Migration + model ─────────────────────────────────────────────────────


def test_migration_v68_chains_from_v67():
    assert 'revision = "d8f0b2c4e6a9"' in MIGRATION_SRC
    assert 'down_revision = "c7e9a1b3d5f8"' in MIGRATION_SRC
    assert "custom_field_definitions" in MIGRATION_SRC
    assert "custom_field_values" in MIGRATION_SRC
    assert "uq_custom_fields_org_entity_name" in MIGRATION_SRC
    assert "uq_custom_field_values_definition_entity" in MIGRATION_SRC


def test_model_has_both_tables():
    assert "class CustomFieldDefinition" in MODEL_SRC
    assert "class CustomFieldValue" in MODEL_SRC


# ── Router source-contract ────────────────────────────────────────────────


def test_router_registered_on_api():
    assert 'prefix="/api/custom-fields"' in ROUTER_SRC
    # custom_fields is registered via customers_router (vertical-slice architecture)
    feat_src = _read("app/features/customers/router.py")
    assert "custom_fields" in feat_src
    assert "customers_router" in MAIN_SRC


def test_router_has_five_endpoints():
    for signature in (
        '@router.post(\n    "/definitions"',
        '@router.get("/definitions"',
        '@router.delete(\n    "/definitions/{definition_id}"',
        '@router.put("/values"',
        '@router.get("/values"',
    ):
        assert signature in ROUTER_SRC, f"missing: {signature}"


def test_router_tenant_scopes_and_cross_entity_guards():
    # Every definition access compares org_id.
    assert "row.org_id != member.org_id" in ROUTER_SRC
    assert "definition.org_id != member.org_id" in ROUTER_SRC
    # The entity-row guard is shared via _assert_entity_belongs.
    assert "_assert_entity_belongs" in ROUTER_SRC
    # That helper must pin the entity to the caller's org.
    assert "row.org_id != org_id" in ROUTER_SRC


def test_router_value_put_requires_matching_entity_type():
    assert "entity_type does not match definition" in ROUTER_SRC


def test_router_logs_all_mutations():
    for action in (
        '"custom_field.definition_created"',
        '"custom_field.definition_deleted"',
        '"custom_field.value_upserted"',
    ):
        assert action in ROUTER_SRC, f"missing audit action: {action}"


def test_router_returns_typed_cast_in_value_out():
    # Response must include both raw and cast — raw preserves the
    # canonical stored string for diffs, cast is what the UI renders.
    assert "cast=svc.cast_for_read" in ROUTER_SRC
    assert "raw=" in ROUTER_SRC
