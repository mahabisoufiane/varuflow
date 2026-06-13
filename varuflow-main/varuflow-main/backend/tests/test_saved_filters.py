"""Item 61 — Saved filters."""
from __future__ import annotations

import pathlib

import pytest

from app.services import saved_filter as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(p: str) -> str:
    return (_BACKEND_ROOT / p).read_text()


MIGRATION_SRC = _read("migrations/versions/f0b2d4e6a8c1_v70_saved_filters.py")
MODEL_SRC = _read("app/models/saved_filter.py")
SERVICE_SRC = _read("app/services/saved_filter.py")
ROUTER_SRC = _read("app/routers/saved_filters.py")
MAIN_SRC = _read("app/main.py")


# ── Pure service: field regex ─────────────────────────────────────────────


def test_field_accepts_lowercase_snake_with_dot():
    for ok in ("status", "issue_date", "customer.email", "a", "total_ex_vat"):
        svc._validate_field(ok)


def test_field_rejects_bad_shapes():
    for bad in ("", "Status", "1field", "field!", "a" * 65, None, 42):
        with pytest.raises((ValueError, TypeError)):
            svc._validate_field(bad)


# ── Pure service: clause ops ──────────────────────────────────────────────


def test_clause_all_simple_ops_accept_scalar():
    for op in ("eq", "neq", "gt", "gte", "lt", "lte", "contains"):
        svc._validate_clause({"field": "total", "op": op, "value": 10})


def test_clause_rejects_unknown_op():
    with pytest.raises(ValueError):
        svc._validate_clause({"field": "total", "op": "like", "value": 1})


def test_clause_rejects_unknown_keys():
    with pytest.raises(ValueError):
        svc._validate_clause(
            {"field": "x", "op": "eq", "value": 1, "extra": "nope"}
        )


def test_clause_in_requires_non_empty_list():
    svc._validate_clause({"field": "x", "op": "in", "value": ["a", "b"]})
    for bad in ([], "a", {"x": 1}, None):
        with pytest.raises(ValueError):
            svc._validate_clause({"field": "x", "op": "in", "value": bad})


def test_clause_in_enforces_max_list_length():
    svc._validate_clause(
        {"field": "x", "op": "in", "value": ["v"] * svc.MAX_IN_VALUES}
    )
    with pytest.raises(ValueError):
        svc._validate_clause(
            {"field": "x", "op": "in", "value": ["v"] * (svc.MAX_IN_VALUES + 1)}
        )


def test_clause_between_requires_two_element_list():
    svc._validate_clause({"field": "x", "op": "between", "value": [1, 10]})
    for bad in ([1], [1, 2, 3], "1,2", None):
        with pytest.raises(ValueError):
            svc._validate_clause(
                {"field": "x", "op": "between", "value": bad}
            )


def test_clause_value_must_be_scalar_for_simple_ops():
    with pytest.raises(ValueError):
        svc._validate_clause(
            {"field": "x", "op": "eq", "value": {"nested": 1}}
        )
    with pytest.raises(ValueError):
        svc._validate_clause({"field": "x", "op": "eq", "value": [1, 2]})


def test_clause_text_value_length_capped():
    svc._validate_clause(
        {"field": "x", "op": "eq", "value": "a" * svc.MAX_TEXT_VALUE_LENGTH}
    )
    with pytest.raises(ValueError):
        svc._validate_clause(
            {
                "field": "x",
                "op": "eq",
                "value": "a" * (svc.MAX_TEXT_VALUE_LENGTH + 1),
            }
        )


# ── Pure service: definition ──────────────────────────────────────────────


def test_definition_requires_dict_and_rejects_unknown_keys():
    with pytest.raises(ValueError):
        svc.validate_definition("not a dict")
    with pytest.raises(ValueError):
        svc.validate_definition({"clauses": [], "bogus": 1})


def test_definition_normalises_sort_to_empty_list():
    out = svc.validate_definition({"clauses": []})
    assert out == {"clauses": [], "sort": []}


def test_definition_enforces_clause_limit():
    good = {"field": "x", "op": "eq", "value": 1}
    svc.validate_definition({"clauses": [good] * svc.MAX_CLAUSES})
    with pytest.raises(ValueError):
        svc.validate_definition({"clauses": [good] * (svc.MAX_CLAUSES + 1)})


def test_sort_accepts_asc_desc_only():
    svc._validate_sort([{"field": "a", "dir": "asc"}])
    svc._validate_sort([{"field": "a", "dir": "desc"}])
    with pytest.raises(ValueError):
        svc._validate_sort([{"field": "a", "dir": "sideways"}])


def test_sort_enforces_column_limit_and_shape():
    svc._validate_sort(
        [{"field": f"a{i}", "dir": "asc"} for i in range(svc.MAX_SORT_COLUMNS)]
    )
    with pytest.raises(ValueError):
        svc._validate_sort(
            [
                {"field": f"a{i}", "dir": "asc"}
                for i in range(svc.MAX_SORT_COLUMNS + 1)
            ]
        )
    with pytest.raises(ValueError):
        svc._validate_sort([{"field": "a", "dir": "asc", "nulls": "last"}])


# ── Pure service: name + entity_type + can_edit ───────────────────────────


def test_validate_name_trims_and_collapses_whitespace():
    assert svc.validate_name("  My   Filter  ") == "My Filter"
    with pytest.raises(ValueError):
        svc.validate_name("")
    with pytest.raises(ValueError):
        svc.validate_name("   ")
    with pytest.raises(ValueError):
        svc.validate_name("x" * (svc.MAX_NAME_LENGTH + 1))


def test_validate_entity_type():
    for ok in ("product", "customer", "invoice", "appointment"):
        svc.validate_entity_type(ok)
    for bad in ("staff", "", "order"):
        with pytest.raises(ValueError):
            svc.validate_entity_type(bad)


def test_can_edit_rules():
    me = "00000000-0000-0000-0000-00000000aaaa"
    other = "00000000-0000-0000-0000-00000000bbbb"
    # Owner of the row
    assert svc.can_edit(me, me, requester_is_owner=False) is True
    # Org OWNER can always edit
    assert svc.can_edit(other, me, requester_is_owner=True) is True
    # Neither owner of row nor OWNER: denied
    assert svc.can_edit(other, me, requester_is_owner=False) is False


# ── Migration + model ─────────────────────────────────────────────────────


def test_migration_v70_chains_from_v69():
    assert 'revision = "f0b2d4e6a8c1"' in MIGRATION_SRC
    assert 'down_revision = "e9a1c3d5f7b0"' in MIGRATION_SRC


def test_migration_has_unique_and_shared_index():
    assert "uq_saved_filters_owner_entity_name" in MIGRATION_SRC
    assert "is_shared" in MIGRATION_SRC


def test_model_matches_migration():
    assert "class SavedFilter(Base)" in MODEL_SRC
    assert "uq_saved_filters_owner_entity_name" in MODEL_SRC
    assert "definition" in MODEL_SRC
    assert "is_shared" in MODEL_SRC


# ── Router source-contract ────────────────────────────────────────────────


def test_router_registered_on_api_saved_filters():
    assert 'prefix="/api/saved-filters"' in ROUTER_SRC
    assert "app.include_router(saved_filters.router)" in MAIN_SRC


def test_router_has_four_endpoints():
    for sig in (
        '@router.post("", response_model=FilterOut',
        '@router.get("", response_model=list[FilterOut])',
        '@router.patch("/{filter_id}"',
        '@router.delete("/{filter_id}"',
    ):
        assert sig in ROUTER_SRC, f"missing signature: {sig}"


def test_router_tenant_scopes_every_path():
    # Every read/mutation path filters by the caller's org.
    assert ROUTER_SRC.count("row.org_id != member.org_id") >= 2
    assert "SavedFilter.org_id == member.org_id" in ROUTER_SRC


def test_router_list_includes_shared_rows_via_or():
    assert "SavedFilter.is_shared.is_(True)" in ROUTER_SRC
    assert "or_(" in ROUTER_SRC


def test_router_enforces_can_edit_on_patch_and_delete():
    assert ROUTER_SRC.count("svc.can_edit(") == 2
    assert '"Not allowed"' in ROUTER_SRC
    assert "status_code=403" in ROUTER_SRC


def test_router_rejects_duplicate_name_with_409():
    assert "status_code=409" in ROUTER_SRC
    assert '"name already exists"' in ROUTER_SRC


def test_router_logs_all_mutations():
    for action in (
        '"saved_filter.created"',
        '"saved_filter.updated"',
        '"saved_filter.deleted"',
    ):
        assert action in ROUTER_SRC, f"missing audit action: {action}"
