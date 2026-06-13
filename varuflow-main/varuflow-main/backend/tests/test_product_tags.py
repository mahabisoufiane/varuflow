"""Item 81 — Product tags."""
from __future__ import annotations

import pathlib

import pytest

from app.services import product_tag as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(p: str) -> str:
    return (_BACKEND_ROOT / p).read_text()


SERVICE_SRC   = _read("app/services/product_tag.py")
ROUTER_SRC    = _read("app/routers/product_tags.py")
MIGRATION_SRC = _read("migrations/versions/c7d9e1f3a5b8_v85_product_tags.py")
MODEL_SRC     = _read("app/models/product_tag.py")
MAIN_SRC      = _read("app/main.py")


# ── Pure service: normalize_name ─────────────────────────────────────────


def test_name_trim_and_collapse_whitespace():
    assert svc.normalize_name("  Seasonal   item ") == "Seasonal item"


def test_name_rejects_non_string():
    for bad in (None, 42, b"seasonal", ["seasonal"]):
        with pytest.raises(ValueError):
            svc.normalize_name(bad)  # type: ignore[arg-type]


def test_name_rejects_empty_and_whitespace_only():
    for bad in ("", "   ", "\t\n "):
        with pytest.raises(ValueError):
            svc.normalize_name(bad)


def test_name_rejects_control_chars():
    with pytest.raises(ValueError):
        svc.normalize_name("seas\x00bad")


def test_name_rejects_over_limit():
    with pytest.raises(ValueError, match="32"):
        svc.normalize_name("x" * 33)


def test_name_accepts_max_length():
    assert svc.normalize_name("x" * 32) == "x" * 32


def test_name_preserves_non_ascii():
    assert svc.normalize_name("Årsvara") == "Årsvara"


# ── Pure service: normalize_color ────────────────────────────────────────


def test_color_accepts_valid_hex_lowercased():
    assert svc.normalize_color("#2D6A4F") == "#2d6a4f"
    assert svc.normalize_color("#abcdef") == "#abcdef"


def test_color_rejects_missing_hash():
    with pytest.raises(ValueError):
        svc.normalize_color("2d6a4f")


def test_color_rejects_short_form():
    with pytest.raises(ValueError):
        svc.normalize_color("#abc")


def test_color_rejects_non_hex_chars():
    with pytest.raises(ValueError):
        svc.normalize_color("#gg2d4f")


def test_color_rejects_non_string():
    for bad in (None, 0xFF0000, [1, 2, 3]):
        with pytest.raises(ValueError):
            svc.normalize_color(bad)  # type: ignore[arg-type]


def test_color_trims_surrounding_whitespace():
    assert svc.normalize_color("  #2d6a4f  ") == "#2d6a4f"


# ── Pure service: keys_equal ─────────────────────────────────────────────


def test_keys_equal_case_insensitive():
    assert svc.keys_equal("Seasonal", "seasonal")
    assert svc.keys_equal("Seasonal item", " seasonal   item ")


def test_keys_equal_different_names_not_equal():
    assert not svc.keys_equal("Seasonal", "Bestseller")


# ── Pure service: assert_under_limit ─────────────────────────────────────


def test_assert_under_limit_under_cap():
    svc.assert_under_limit(current_count=0)
    svc.assert_under_limit(current_count=19)


def test_assert_under_limit_at_cap_raises():
    with pytest.raises(ValueError, match="limit"):
        svc.assert_under_limit(current_count=20)


def test_assert_under_limit_over_cap_raises():
    with pytest.raises(ValueError):
        svc.assert_under_limit(current_count=99)


def test_assert_under_limit_rejects_negative():
    with pytest.raises(ValueError):
        svc.assert_under_limit(current_count=-1)


# ── Constants ────────────────────────────────────────────────────────────


def test_constants_are_sane():
    assert svc.MAX_TAGS_PER_PRODUCT == 20
    assert svc.MAX_NAME_LEN == 32
    assert svc.MIN_NAME_LEN >= 1


# ── Migration contract ──────────────────────────────────────────────────


def test_migration_chains_from_v84():
    assert 'down_revision = "b6c8d0e2f4a7"' in MIGRATION_SRC
    assert 'revision = "c7d9e1f3a5b8"' in MIGRATION_SRC


def test_migration_creates_both_tables():
    assert '"product_tags"' in MIGRATION_SRC
    assert '"product_tag_assignments"' in MIGRATION_SRC


def test_migration_case_insensitive_unique_index():
    # Must use a functional expression on lower(name) so "Seasonal"
    # and "seasonal" collide at the database level.
    assert "ux_product_tags_org_name_lower" in MIGRATION_SRC
    assert "lower(name)" in MIGRATION_SRC
    assert "unique=True" in MIGRATION_SRC


def test_migration_cascades_on_org_and_product():
    # Each FK to organizations / products / tags should cascade so
    # deleting a parent row cleans up every dependent assignment.
    assert MIGRATION_SRC.count('ondelete="CASCADE"') >= 3


def test_migration_assignment_has_composite_pk():
    assert "PrimaryKeyConstraint" in MIGRATION_SRC
    assert '"product_id"' in MIGRATION_SRC
    assert '"tag_id"' in MIGRATION_SRC


# ── Model contract ──────────────────────────────────────────────────────


def test_model_tablenames():
    assert '__tablename__ = "product_tags"' in MODEL_SRC
    assert '__tablename__ = "product_tag_assignments"' in MODEL_SRC


def test_model_has_required_columns():
    for col in ("org_id", "name", "color", "created_by_user_id",
                "updated_at", "created_at"):
        assert col in MODEL_SRC


def test_assignment_model_has_assigned_by():
    assert "assigned_by_user_id" in MODEL_SRC
    assert "assigned_at" in MODEL_SRC


# ── Router contract ─────────────────────────────────────────────────────


def test_router_prefix():
    assert 'prefix="/api/product-tags"' in ROUTER_SRC


def test_router_has_all_endpoints():
    # 5 on the tag itself + 3 on the relationship + 1 for product→tags.
    assert '@router.get("", response_model=' in ROUTER_SRC
    assert '@router.post("",' in ROUTER_SRC
    assert '@router.get("/{tag_id}"' in ROUTER_SRC
    assert '@router.patch("/{tag_id}"' in ROUTER_SRC
    assert '@router.delete("/{tag_id}"' in ROUTER_SRC
    assert '@router.get("/{tag_id}/products"' in ROUTER_SRC
    assert '@router.post("/assignments"' in ROUTER_SRC
    assert '@router.delete("/assignments"' in ROUTER_SRC
    assert '@router.get("/products/{product_id}"' in ROUTER_SRC


def test_router_uses_pure_service():
    assert "svc_81.normalize_name" in ROUTER_SRC
    assert "svc_81.normalize_color" in ROUTER_SRC
    assert "svc_81.assert_under_limit" in ROUTER_SRC


def test_router_tenant_scope_on_every_load():
    # _load_tag and _load_product both compare .org_id → org_id
    assert "row.org_id != org_id" in ROUTER_SRC
    # The list and the count queries filter on the scoped org too.
    assert "ProductTag.org_id == member.org_id" in ROUTER_SRC
    assert "Product.org_id == member.org_id" in ROUTER_SRC


def test_router_emits_five_audit_actions():
    for action in (
        "product_tag.created",
        "product_tag.updated",
        "product_tag.deleted",
        "product_tag.assigned",
        "product_tag.unassigned",
    ):
        assert f'"{action}"' in ROUTER_SRC
    # Every single audit emission carries request=request.
    assert ROUTER_SRC.count("request=request") >= 5


def test_router_assignment_is_idempotent():
    # Pre-existing assignment short-circuits — the assign endpoint
    # must not raise on a second call with the same (product, tag).
    assert '"already_assigned"' in ROUTER_SRC


def test_router_returns_409_on_duplicate_name():
    assert "status_code=409" in ROUTER_SRC
    assert "already in use" in ROUTER_SRC


def test_router_404s_on_cross_tenant():
    assert '"Tag not found"' in ROUTER_SRC
    assert '"Product not found"' in ROUTER_SRC


def test_router_imports_product_from_inventory():
    assert "from app.models.inventory import Product" in ROUTER_SRC


def test_router_registered_in_main():
    assert "product_tags.router" in MAIN_SRC
    assert "product_tags," in MAIN_SRC
