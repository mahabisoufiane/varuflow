"""Item 70 — Customer credit notes."""
from __future__ import annotations

import pathlib
from decimal import Decimal

import pytest

from app.services import credit_note as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(p: str) -> str:
    return (_BACKEND_ROOT / p).read_text()


MIGRATION_SRC = _read(
    "migrations/versions/a8b0c2d4e6f9_v77_credit_notes.py"
)
MODEL_SRC   = _read("app/models/credit_note.py")
SERVICE_SRC = _read("app/services/credit_note.py")
ROUTER_SRC  = _read("app/routers/credit_notes.py")
MAIN_SRC    = _read("app/main.py")


# ── Pure service — validators ─────────────────────────────────────────────


def test_validate_currency_upper_3_letter():
    assert svc.validate_currency(" sek ") == "SEK"
    assert svc.validate_currency("EUR") == "EUR"


def test_validate_currency_rejects_bad():
    for bad in ("", "SE", "SEKA", "se1"):
        with pytest.raises(ValueError):
            svc.validate_currency(bad)


def test_validate_reason_strips_and_allows_none():
    assert svc.validate_reason(None) is None
    assert svc.validate_reason("   ") is None
    assert svc.validate_reason("  refund  ") == "refund"


def test_validate_reason_rejects_overlong():
    with pytest.raises(ValueError):
        svc.validate_reason("x" * (svc.MAX_REASON_LENGTH + 1))


def test_validate_description_required():
    with pytest.raises(ValueError):
        svc.validate_description("   ")


def test_validate_description_rejects_overlong():
    with pytest.raises(ValueError):
        svc.validate_description("x" * (svc.MAX_DESC_LENGTH + 1))


def test_validate_quantity_positive():
    assert svc.validate_quantity("2.5") == Decimal("2.500")
    with pytest.raises(ValueError):
        svc.validate_quantity(0)
    with pytest.raises(ValueError):
        svc.validate_quantity(-1)


def test_validate_quantity_rejects_bool():
    with pytest.raises(ValueError):
        svc.validate_quantity(True)


def test_validate_unit_price_non_negative():
    assert svc.validate_unit_price("0") == Decimal("0.00")
    assert svc.validate_unit_price("12,50") == Decimal("12.50")
    with pytest.raises(ValueError):
        svc.validate_unit_price(-1)


def test_validate_tax_rate_whitelist():
    for good in ("0", "6", "12", "25"):
        svc.validate_tax_rate(good)
    for bad in ("17", "8", "50"):
        with pytest.raises(ValueError):
            svc.validate_tax_rate(bad)


# ── Pure service — totals ────────────────────────────────────────────────


def test_compute_line_applies_vat_half_up():
    r = svc.compute_line(
        quantity=Decimal("3"),
        unit_price=Decimal("10.00"),
        tax_rate=Decimal("25.00"),
    )
    assert r.line_total == Decimal("30.00")
    assert r.tax_amount == Decimal("7.50")


def test_compute_line_zero_vat():
    r = svc.compute_line(
        quantity=Decimal("2"),
        unit_price=Decimal("100.00"),
        tax_rate=Decimal("0.00"),
    )
    assert r.line_total == Decimal("200.00")
    assert r.tax_amount == Decimal("0.00")


def test_compute_totals_sums_lines():
    totals = svc.compute_totals([
        {"quantity": 2, "unit_price": Decimal("10"),  "tax_rate": Decimal("25")},
        {"quantity": 1, "unit_price": Decimal("100"), "tax_rate": Decimal("12")},
    ])
    assert totals.subtotal  == Decimal("120.00")
    assert totals.tax_total == Decimal("17.00")  # 5.00 + 12.00
    assert totals.total     == Decimal("137.00")


def test_compute_totals_uses_25_default_tax():
    totals = svc.compute_totals([
        {"quantity": 1, "unit_price": Decimal("100")},
    ])
    assert totals.tax_total == Decimal("25.00")


def test_compute_totals_rejects_overflow():
    with pytest.raises(ValueError):
        svc.compute_totals([
            {"quantity": 1, "unit_price": Decimal("1")}
        ] * (svc.MAX_LINES + 1))


# ── Pure service — status machine ────────────────────────────────────────


def test_assert_transition_allowed():
    svc.assert_transition(svc.STATUS_DRAFT,  svc.STATUS_ISSUED)
    svc.assert_transition(svc.STATUS_DRAFT,  svc.STATUS_VOIDED)
    svc.assert_transition(svc.STATUS_ISSUED, svc.STATUS_VOIDED)


def test_assert_transition_rejects_terminal_out():
    with pytest.raises(ValueError):
        svc.assert_transition(svc.STATUS_VOIDED, svc.STATUS_DRAFT)
    with pytest.raises(ValueError):
        svc.assert_transition(svc.STATUS_ISSUED, svc.STATUS_DRAFT)


# ── Pure service — number minting ────────────────────────────────────────


def test_next_number_first_of_year():
    assert svc.next_number(year=2026, existing=set()) == "CN-2026-0001"


def test_next_number_increments_max_of_year():
    used = {"CN-2026-0001", "CN-2026-0003", "CN-2025-0999"}
    assert svc.next_number(year=2026, existing=used) == "CN-2026-0004"


def test_next_number_ignores_other_years_and_garbage():
    used = {"CN-2025-9999", "garbage", "", "CN-2026-0010"}
    assert svc.next_number(year=2026, existing=used) == "CN-2026-0011"


def test_next_number_year_out_of_range():
    with pytest.raises(ValueError):
        svc.next_number(year=1999, existing=set())


def test_next_number_grows_past_9999():
    used = {"CN-2026-9999"}
    assert svc.next_number(year=2026, existing=used) == "CN-2026-10000"


# ── Pure service — invoice allocation cap ────────────────────────────────


def test_assert_fits_invoice_ok():
    svc.assert_fits_invoice(
        credit_total=Decimal("50"),
        invoice_total=Decimal("100"),
        invoice_paid=Decimal("30"),
        invoice_credited=Decimal("20"),
    )


def test_assert_fits_invoice_rejects_overshoot():
    with pytest.raises(ValueError, match="exceeds"):
        svc.assert_fits_invoice(
            credit_total=Decimal("60"),
            invoice_total=Decimal("100"),
            invoice_paid=Decimal("30"),
            invoice_credited=Decimal("20"),
        )


def test_assert_fits_invoice_rejects_non_positive():
    with pytest.raises(ValueError):
        svc.assert_fits_invoice(
            credit_total=Decimal("0"),
            invoice_total=Decimal("100"),
            invoice_paid=Decimal("0"),
            invoice_credited=Decimal("0"),
        )


# ── Migration source contract ────────────────────────────────────────────


def test_migration_chain_to_v76():
    assert 'down_revision = "f7a9b1c3d6e7"' in MIGRATION_SRC
    assert 'revision = "a8b0c2d4e6f9"' in MIGRATION_SRC


def test_migration_creates_both_tables():
    assert '"credit_notes"' in MIGRATION_SRC
    assert '"credit_note_lines"' in MIGRATION_SRC


def test_migration_creates_enum_with_three_states():
    for s in ("DRAFT", "ISSUED", "VOIDED"):
        assert s in MIGRATION_SRC
    assert "credit_note_status" in MIGRATION_SRC


def test_migration_unique_number_per_org():
    assert "uq_credit_notes_org_number" in MIGRATION_SRC


def test_migration_indexes():
    for name in (
        "ix_credit_notes_org_id",
        "ix_credit_notes_customer_id",
        "ix_credit_notes_invoice_id",
        "ix_credit_notes_status",
        "ix_credit_note_lines_credit_note_id",
    ):
        assert name in MIGRATION_SRC


# ── Model source contract ────────────────────────────────────────────────


def test_model_declares_all_status_states():
    for s in ("DRAFT", "ISSUED", "VOIDED"):
        assert f'"{s}"' in MODEL_SRC


def test_model_invoice_id_nullable():
    # Standalone credits (no source invoice) are allowed.
    assert "invoice_id" in MODEL_SRC
    assert "uuid.UUID | None" in MODEL_SRC


# ── Router source contract ───────────────────────────────────────────────


def test_router_prefix_and_endpoints():
    assert 'prefix="/api/credit-notes"' in ROUTER_SRC
    for path in (
        '@router.get("", ',
        '@router.post(\n    "",',
        '@router.get("/{credit_note_id}"',
        '@router.patch("/{credit_note_id}"',
        '@router.delete("/{credit_note_id}"',
        '@router.post("/{credit_note_id}/issue"',
        '@router.post("/{credit_note_id}/void"',
    ):
        assert path in ROUTER_SRC, f"missing: {path!r}"


def test_router_draft_only_mutation_guards():
    # PATCH + DELETE must reject non-DRAFT.
    assert "only DRAFT credit notes may be edited" in ROUTER_SRC
    assert "only DRAFT credit notes may be deleted" in ROUTER_SRC


def test_router_issue_locks_org_row():
    assert "with_for_update" in ROUTER_SRC
    assert "Organization.id == member.org_id" in ROUTER_SRC


def test_router_issue_enforces_invoice_cap():
    assert "assert_fits_invoice" in ROUTER_SRC


def test_router_void_requires_reason():
    assert "void reason is required" in ROUTER_SRC


def test_router_logs_five_audit_actions():
    for action in (
        '"creditnote.created"',
        '"creditnote.updated"',
        '"creditnote.deleted"',
        '"creditnote.issued"',
        '"creditnote.voided"',
    ):
        assert action in ROUTER_SRC, f"missing audit action: {action}"
    # All must use request=request kwarg (session convention).
    assert ROUTER_SRC.count("request=request") >= 5


def test_router_tenant_scopes_every_query():
    # SQL-level tenant filters (list + existing-credit sum).
    assert ROUTER_SRC.count("CreditNote.org_id == member.org_id") >= 2
    # Plus a row-level guard inside _load(): org_id mismatch → 404.
    assert "row.org_id != org_id" in ROUTER_SRC


def test_router_customer_and_invoice_ownership_checks():
    assert "_assert_customer_belongs" in ROUTER_SRC
    assert "_assert_invoice_belongs"  in ROUTER_SRC
    assert "invoice and credit-note customer_id do not match" in ROUTER_SRC


def test_router_issued_credits_only_count_in_cap():
    # Existing credits query must filter to ISSUED to ignore drafts
    # and already-voided credits — otherwise the cap over-counts.
    assert "CreditNote.status == CreditNoteStatus.ISSUED" in ROUTER_SRC


def test_router_registered_in_main():
    assert "credit_notes.router" in MAIN_SRC
    assert "credit_notes," in MAIN_SRC
