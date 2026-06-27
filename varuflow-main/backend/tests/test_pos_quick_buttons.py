"""Item 65 — POS quick-sale buttons."""
from __future__ import annotations

import pathlib
from decimal import Decimal

import pytest

from app.services import pos_quick_button as svc


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


MIGRATION_SRC = _read("migrations/versions/c4d6e8f0a2b3_v73_pos_quick_buttons.py")
MODEL_SRC = _read("app/features/pos/pos_quick_button.py")
SERVICE_SRC = _read("app/services/pos_quick_button.py")
ROUTER_SRC = _read("app/features/pos/pos_quick_buttons.py")
MAIN_SRC = _read("app/main.py")


# ── Pure service: label ───────────────────────────────────────────────────


def test_validate_label_trims_and_collapses_whitespace():
    assert svc.validate_label("  Hot   Coffee ") == "Hot Coffee"


def test_validate_label_rejects_blank():
    for bad in ("", "   "):
        with pytest.raises(ValueError):
            svc.validate_label(bad)


def test_validate_label_caps_length():
    svc.validate_label("x" * svc.MAX_LABEL_LENGTH)
    with pytest.raises(ValueError):
        svc.validate_label("x" * (svc.MAX_LABEL_LENGTH + 1))


def test_validate_label_rejects_non_string():
    with pytest.raises(ValueError):
        svc.validate_label(42)  # type: ignore[arg-type]


# ── Pure service: color ───────────────────────────────────────────────────


def test_validate_color_accepts_hex_and_lowercases():
    assert svc.validate_color("#1E90FF") == "#1e90ff"
    assert svc.validate_color(None) is None
    assert svc.validate_color("") is None


def test_validate_color_rejects_bad_input():
    for bad in ("red", "#abc", "1E90FF", "#GGGGGG", "#12345"):
        with pytest.raises(ValueError):
            svc.validate_color(bad)


# ── Pure service: quantity ────────────────────────────────────────────────


def test_validate_quantity_accepts_string_and_decimal():
    assert svc.validate_quantity("2") == Decimal("2")
    assert svc.validate_quantity(Decimal("1.5")) == Decimal("1.5")


def test_validate_quantity_bounds():
    svc.validate_quantity(svc.MIN_QUANTITY)
    svc.validate_quantity(svc.MAX_QUANTITY)
    for bad in (Decimal("0"), Decimal("-1"), Decimal("10000")):
        with pytest.raises(ValueError):
            svc.validate_quantity(bad)


def test_validate_quantity_rejects_bools_and_junk():
    with pytest.raises(ValueError):
        svc.validate_quantity(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        svc.validate_quantity("not-a-number")


# ── Pure service: reorder ─────────────────────────────────────────────────


def test_reorder_assigns_sequential_positions():
    out = svc.reorder(["a", "b", "c"], ["c", "a", "b"])
    assert out == [("c", 1), ("a", 2), ("b", 3)]


def test_reorder_rejects_length_mismatch():
    with pytest.raises(ValueError):
        svc.reorder(["a", "b"], ["a", "b", "c"])


def test_reorder_rejects_duplicates():
    with pytest.raises(ValueError):
        svc.reorder(["a", "b"], ["a", "a"])


def test_reorder_rejects_unknown_ids():
    with pytest.raises(ValueError):
        svc.reorder(["a", "b"], ["a", "z"])


# ── Pure service: capacity + next_position ────────────────────────────────


def test_next_position_empty_starts_at_one():
    assert svc.next_position([]) == 1


def test_next_position_appends_after_highest():
    assert svc.next_position([1, 3, 2]) == 4


def test_assert_capacity_under_limit_ok():
    svc.assert_capacity(svc.MAX_BUTTONS_PER_ORG - 1)


def test_assert_capacity_at_or_above_limit_rejects():
    with pytest.raises(ValueError):
        svc.assert_capacity(svc.MAX_BUTTONS_PER_ORG)
    with pytest.raises(ValueError):
        svc.assert_capacity(svc.MAX_BUTTONS_PER_ORG + 1)


# ── Migration + model ─────────────────────────────────────────────────────


def test_migration_v73_chains_from_v72():
    assert 'revision = "c4d6e8f0a2b3"' in MIGRATION_SRC
    assert 'down_revision = "b3c5d7e9f1a4"' in MIGRATION_SRC


def test_migration_has_org_position_unique():
    assert "uq_pos_quick_buttons_org_position" in MIGRATION_SRC


def test_model_matches_migration():
    assert "class PosQuickButton(Base)" in MODEL_SRC
    assert "uq_pos_quick_buttons_org_position" in MODEL_SRC
    assert "position" in MODEL_SRC


# ── Router source-contract ────────────────────────────────────────────────


def test_router_registered_on_api_pos_quick_buttons():
    assert 'prefix="/api/pos/quick-buttons"' in ROUTER_SRC
    # pos_quick_buttons is registered via pos_router (vertical-slice architecture)
    feat_src = _read("app/features/pos/router.py")
    assert "pos_quick_buttons" in feat_src
    assert "pos_router" in MAIN_SRC


def test_router_has_five_endpoints():
    for sig in (
        '@router.get("", response_model=list[ButtonOut])',
        '@router.post("", response_model=ButtonOut',
        '@router.patch("/{button_id}"',
        '@router.delete("/{button_id}"',
        '@router.post("/reorder"',
    ):
        assert sig in ROUTER_SRC, f"missing signature: {sig}"


def test_router_scopes_product_to_caller_org():
    assert "Product.org_id == member.org_id" in ROUTER_SRC


def test_router_scopes_button_lookups_to_org():
    assert ROUTER_SRC.count("row.org_id != member.org_id") >= 2


def test_router_reorder_uses_two_phase_update():
    # Negative-stash pattern to dodge (org_id, position) UNIQUE.
    assert "r.position = -(i + 1)" in ROUTER_SRC


def test_router_logs_all_mutations():
    for action in (
        '"pos_quick_button.created"',
        '"pos_quick_button.updated"',
        '"pos_quick_button.deleted"',
        '"pos_quick_button.reordered"',
    ):
        assert action in ROUTER_SRC, f"missing audit action: {action}"
