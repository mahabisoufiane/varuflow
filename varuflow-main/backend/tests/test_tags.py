"""Item 60 — Tag manager."""
from __future__ import annotations

import pathlib

import pytest

from app.services import tag as svc


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


MIGRATION_SRC = _read("migrations/versions/e9a1c3d5f7b0_v69_tags.py")
MODEL_SRC = _read("app/features/customers/tag.py")
SERVICE_SRC = _read("app/services/tag.py")
ROUTER_SRC = _read("app/features/customers/tags.py")
MAIN_SRC = _read("app/main.py")


# ── Pure service ──────────────────────────────────────────────────────────


def test_slugify_basic_cases():
    assert svc.slugify("Summer Sale") == "summer-sale"
    assert svc.slugify("  VIP!! ") == "vip"
    assert svc.slugify("Gold  tier") == "gold-tier"
    assert svc.slugify("Café 2026") == "caf-2026"


def test_slugify_rejects_blank_and_non_alphanum():
    for bad in ("", "   ", "!!!", "---"):
        with pytest.raises(ValueError):
            svc.slugify(bad)


def test_slugify_truncates_to_max_slug_length():
    long = "x" * (svc.MAX_SLUG_LENGTH + 10)
    out = svc.slugify(long)
    assert len(out) <= svc.MAX_SLUG_LENGTH


def test_normalise_name_collapses_whitespace():
    assert svc.normalise_name("  foo   bar ") == "foo bar"
    assert svc.normalise_name(None) == ""


def test_validate_name_length():
    svc.validate_name("x")  # min
    svc.validate_name("x" * svc.MAX_NAME_LENGTH)
    with pytest.raises(ValueError):
        svc.validate_name("")
    with pytest.raises(ValueError):
        svc.validate_name("x" * (svc.MAX_NAME_LENGTH + 1))


def test_validate_color_hex_only():
    assert svc.validate_color("#1E90FF") == "#1e90ff"
    assert svc.validate_color(None) is None
    assert svc.validate_color("") is None
    for bad in ("red", "#abc", "1e90ff", "#GGGGGG"):
        with pytest.raises(ValueError):
            svc.validate_color(bad)


def test_validate_entity_type():
    for ok in ("product", "customer", "invoice"):
        svc.validate_entity_type(ok)
    for bad in ("staff", "order", ""):
        with pytest.raises(ValueError):
            svc.validate_entity_type(bad)


def test_dedupe_tag_ids_preserves_order():
    assert svc.dedupe_tag_ids([1, 2, 1, 3, 2]) == [1, 2, 3]
    assert svc.dedupe_tag_ids([]) == []


# ── Migration + model ─────────────────────────────────────────────────────


def test_migration_v69_chains_from_v68():
    assert 'revision = "e9a1c3d5f7b0"' in MIGRATION_SRC
    assert 'down_revision = "d8f0b2c4e6a9"' in MIGRATION_SRC
    assert "uq_tags_org_slug" in MIGRATION_SRC
    assert "uq_tag_assignments_tag_entity" in MIGRATION_SRC


def test_model_has_tag_and_assignment():
    assert "class Tag(Base)" in MODEL_SRC
    assert "class TagAssignment(Base)" in MODEL_SRC
    assert "uq_tags_org_slug" in MODEL_SRC
    assert "uq_tag_assignments_tag_entity" in MODEL_SRC


# ── Router source-contract ────────────────────────────────────────────────


def test_router_registered_on_api_tags():

    # Registered via customers_router (vertical-slice architecture).
    # The individual module is wired inside the feature router, not directly in main.py.
    feat_src = _read("app/features/customers/router.py")
    assert "tags" in feat_src
    assert "customers_router" in MAIN_SRC

    # Registered via customers_router (vertical-slice architecture).
    # The individual module is wired inside the feature router, not directly in main.py.
    feat_src = _read("app/features/customers/router.py")
    assert "tags" in feat_src
    assert "customers_router" in MAIN_SRC


def test_router_has_six_endpoints():
    for sig in (
        '@router.post("", response_model=TagOut',
        '@router.get("", response_model=list[TagOut])',
        '@router.delete("/{tag_id}"',
        '@router.post(\n    "/assign"',
        '@router.post("/unassign"',
        '@router.get("/for"',
    ):
        assert sig in ROUTER_SRC, f"missing signature: {sig}"


def test_router_tenant_scopes_every_path():
    # Tag ownership check on create / delete / assign / unassign.
    assert ROUTER_SRC.count("tag.org_id != member.org_id") >= 2
    assert "row.org_id != member.org_id" in ROUTER_SRC
    # Shared helper pins the entity row to the caller's org.
    assert "_assert_entity_belongs" in ROUTER_SRC
    assert "row.org_id != org_id" in ROUTER_SRC


def test_router_logs_all_mutations():
    for action in (
        '"tag.created"',
        '"tag.deleted"',
        '"tag.assigned"',
        '"tag.unassigned"',
    ):
        assert action in ROUTER_SRC, f"missing audit action: {action}"


def test_router_assign_is_idempotent():
    # If the (tag_id, entity_type, entity_id) row already exists,
    # return it instead of raising 409.
    assert "if existing is not None:\n        return existing" in ROUTER_SRC


def test_router_unassign_is_idempotent():
    # Missing row is the success case, not a 404.
    assert "Idempotent unassign" in ROUTER_SRC


def test_router_rejects_duplicate_slug_on_create():
    assert '"slug already exists"' in ROUTER_SRC
