"""Item 66 — Customer contracts."""
from __future__ import annotations

import pathlib
from datetime import date
from decimal import Decimal

import pytest

from app.services import customer_contract as svc


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


MIGRATION_SRC = _read("migrations/versions/d5e7f9a1b4c5_v74_customer_contracts.py")
MODEL_SRC = _read("app/models/customer_contract.py")
SERVICE_SRC = _read("app/services/customer_contract.py")
ROUTER_SRC = _read("app/features/projects/contracts.py")
MAIN_SRC = _read("app/main.py")


# ── Pure service: title/body/reason ───────────────────────────────────────


def test_validate_title_trims_and_collapses():
    assert svc.validate_title("  My  Contract ") == "My Contract"
    with pytest.raises(ValueError):
        svc.validate_title("")
    with pytest.raises(ValueError):
        svc.validate_title("x" * (svc.MAX_TITLE_LENGTH + 1))


def test_validate_body_allows_none_and_caps_length():
    assert svc.validate_body(None) is None
    svc.validate_body("x" * svc.MAX_BODY_LENGTH)
    with pytest.raises(ValueError):
        svc.validate_body("x" * (svc.MAX_BODY_LENGTH + 1))


def test_validate_reason_requires_non_empty():
    assert svc.validate_reason("  breach  ") == "breach"
    with pytest.raises(ValueError):
        svc.validate_reason("")
    with pytest.raises(ValueError):
        svc.validate_reason("x" * (svc.MAX_REASON_LENGTH + 1))


# ── Pure service: numeric + currency ──────────────────────────────────────


def test_validate_value_amount_non_negative():
    assert svc.validate_value_amount("100") == Decimal("100")
    with pytest.raises(ValueError):
        svc.validate_value_amount(Decimal("-0.01"))
    with pytest.raises(ValueError):
        svc.validate_value_amount(True)  # type: ignore[arg-type]


def test_validate_value_amount_cap():
    svc.validate_value_amount(svc.MAX_VALUE)
    with pytest.raises(ValueError):
        svc.validate_value_amount(svc.MAX_VALUE + Decimal("1"))


def test_validate_currency_uppercases():
    assert svc.validate_currency("sek") == "SEK"
    for bad in ("SE", "SEKX", "12A", ""):
        with pytest.raises(ValueError):
            svc.validate_currency(bad)


def test_validate_renew_months_bounds_and_none():
    assert svc.validate_renew_months(None) is None
    svc.validate_renew_months(svc.MIN_RENEW_MONTHS)
    svc.validate_renew_months(svc.MAX_RENEW_MONTHS)
    for bad in (0, svc.MAX_RENEW_MONTHS + 1, True, "12"):
        with pytest.raises(ValueError):
            svc.validate_renew_months(bad)  # type: ignore[arg-type]


# ── Pure service: dates ───────────────────────────────────────────────────


def test_validate_dates_accepts_open_ended():
    out = svc.validate_dates(date(2026, 1, 1), None)
    assert out.start == date(2026, 1, 1) and out.end is None


def test_validate_dates_accepts_ordered_pair():
    out = svc.validate_dates(date(2026, 1, 1), date(2026, 12, 31))
    assert out.end == date(2026, 12, 31)


def test_validate_dates_rejects_end_before_start():
    with pytest.raises(ValueError):
        svc.validate_dates(date(2026, 6, 1), date(2026, 5, 31))


# ── Pure service: transitions ─────────────────────────────────────────────


def test_transition_allows_draft_to_active():
    svc.assert_transition("DRAFT", "ACTIVE")


def test_transition_allows_active_to_expired_or_terminated():
    svc.assert_transition("ACTIVE", "EXPIRED")
    svc.assert_transition("ACTIVE", "TERMINATED")


def test_transition_rejects_terminal_states():
    for src in ("EXPIRED", "TERMINATED"):
        for tgt in ("ACTIVE", "DRAFT"):
            with pytest.raises(ValueError):
                svc.assert_transition(src, tgt)


def test_transition_rejects_draft_to_expired_skip():
    with pytest.raises(ValueError):
        svc.assert_transition("DRAFT", "EXPIRED")


def test_transition_rejects_unknown_status():
    with pytest.raises(ValueError):
        svc.assert_transition("FOO", "ACTIVE")
    with pytest.raises(ValueError):
        svc.assert_transition("DRAFT", "FOO")


# ── Pure service: expiry + renewal ────────────────────────────────────────


def test_is_expired_is_none_for_open_ended():
    assert svc.is_expired(None, date(2030, 1, 1)) is False


def test_is_expired_end_today_is_not_yet_expired():
    assert svc.is_expired(date(2026, 4, 24), date(2026, 4, 24)) is False


def test_is_expired_yesterday_is_expired():
    assert svc.is_expired(date(2026, 4, 23), date(2026, 4, 24)) is True


def test_next_renewal_end_adds_months():
    assert svc.next_renewal_end(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert svc.next_renewal_end(date(2026, 1, 15), 12) == date(2027, 1, 15)


def test_next_renewal_end_handles_leap_year():
    assert svc.next_renewal_end(date(2027, 1, 29), 1) == date(2027, 2, 28)
    assert svc.next_renewal_end(date(2023, 1, 31), 13) == date(2024, 2, 29)


def test_select_renewals_filters_active_with_auto_renew():
    today = date(2026, 4, 24)
    contracts = [
        ("a", "ACTIVE", date(2026, 4, 24), 12),   # expires today
        ("b", "ACTIVE", date(2026, 4, 25), 12),   # future
        ("c", "ACTIVE", date(2026, 4, 20), None),  # no auto_renew
        ("d", "ACTIVE", None, 12),                 # open-ended
        ("e", "DRAFT",  date(2026, 4, 1), 12),    # wrong status
    ]
    assert svc.select_renewals(contracts, today) == ["a"]


# ── Migration + model ─────────────────────────────────────────────────────


def test_migration_v74_chains_from_v73():
    assert 'revision = "d5e7f9a1b4c5"' in MIGRATION_SRC
    assert 'down_revision = "c4d6e8f0a2b3"' in MIGRATION_SRC


def test_migration_has_end_date_index():
    assert "ix_customer_contracts_end_date" in MIGRATION_SRC


def test_model_matches_migration_status_values():
    for v in ("DRAFT", "ACTIVE", "EXPIRED", "TERMINATED"):
        assert f'{v} = "{v}"' in MODEL_SRC


# ── Router source-contract ────────────────────────────────────────────────


def test_router_registered_on_api_contracts():
    assert 'prefix="/api/contracts"' in ROUTER_SRC
    # contracts is registered via projects_router (vertical-slice architecture)
    feat_src = _read("app/features/projects/router.py")
    assert "contracts" in feat_src
    assert "projects_router" in MAIN_SRC


def test_router_has_eight_endpoints():
    for sig in (
        '@router.get("", response_model=list[ContractOut])',
        '@router.post("", response_model=ContractOut',
        '@router.get("/{contract_id}"',
        '@router.patch("/{contract_id}"',
        '@router.delete("/{contract_id}"',
        '@router.post("/{contract_id}/activate"',
        '@router.post("/{contract_id}/terminate"',
        '@router.post("/{contract_id}/renew"',
    ):
        assert sig in ROUTER_SRC, f"missing signature: {sig}"


def test_router_scopes_customer_to_caller_org():
    assert "Customer.org_id == member.org_id" in ROUTER_SRC


def test_router_refuses_edits_to_finalised_contracts():
    assert "cannot edit finalised contract" in ROUTER_SRC


def test_router_delete_only_allowed_for_drafts():
    assert "can only delete DRAFT contracts" in ROUTER_SRC


def test_router_renew_requires_active_and_configured():
    assert "can only renew ACTIVE contracts" in ROUTER_SRC
    assert "no end_date or auto_renew_months" in ROUTER_SRC


def test_router_logs_every_mutation():
    for action in (
        '"contract.created"',
        '"contract.updated"',
        '"contract.deleted"',
        '"contract.activated"',
        '"contract.terminated"',
        '"contract.renewed"',
    ):
        assert action in ROUTER_SRC, f"missing audit action: {action}"
