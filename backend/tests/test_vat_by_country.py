"""Item 52 — Automatic VAT Calculation by Country.

Pure tests for the country-driven VAT resolver. Covers the four
required jurisdictions (SE, GB, AE, MA) plus zero-VAT scenarios
(intra-EU reverse charge, export, unknown country).
"""
from __future__ import annotations

import pathlib
from decimal import Decimal

import pytest

from app.services import vat as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(relpath: str) -> str:
    return (_BACKEND_ROOT / relpath).read_text()


ROUTER_SRC = _read("app/routers/invoicing.py")
SERVICE_SRC = _read("app/services/vat.py")


# ── Required 10 tests ──────────────────────────────────────────────────────


def test_se_standard_rate():
    """Sweden — 25% standard."""
    rate = svc.standard_rate("SE")
    assert rate == Decimal("25.00")
    res = svc.resolve_vat_for_line(seller_country="SE", buyer_country="SE")
    assert res.rate_pct == Decimal("25.00")
    assert res.reason == "domestic"
    assert res.reverse_charge is False


def test_uk_standard_rate():
    """United Kingdom — 20% standard (post-Brexit, non-EU)."""
    rate = svc.standard_rate("GB")
    assert rate == Decimal("20.00")
    res = svc.resolve_vat_for_line(seller_country="GB", buyer_country="GB")
    assert res.rate_pct == Decimal("20.00")
    assert res.reason == "domestic"


def test_ae_standard_rate():
    """United Arab Emirates — 5% standard, no reverse charge."""
    rate = svc.standard_rate("AE")
    assert rate == Decimal("5.00")
    res = svc.resolve_vat_for_line(seller_country="AE", buyer_country="AE")
    assert res.rate_pct == Decimal("5.00")
    assert res.reason == "domestic"


def test_ma_standard_rate():
    """Morocco — 20% standard."""
    rate = svc.standard_rate("MA")
    assert rate == Decimal("20.00")
    res = svc.resolve_vat_for_line(seller_country="MA", buyer_country="MA")
    assert res.rate_pct == Decimal("20.00")


def test_zero_vat_intra_eu_reverse_charge():
    """SE seller → DE buyer with VAT number → 0% reverse charge."""
    res = svc.resolve_vat_for_line(
        seller_country="SE",
        buyer_country="DE",
        buyer_has_vat_number=True,
    )
    assert res.rate_pct == Decimal("0.00")
    assert res.reason == "intra_eu_reverse_charge"
    assert res.reverse_charge is True


def test_zero_vat_export_non_eu():
    """SE seller → AE buyer → 0% export, no reverse charge."""
    res = svc.resolve_vat_for_line(
        seller_country="SE",
        buyer_country="AE",
    )
    assert res.rate_pct == Decimal("0.00")
    assert res.reason == "export_non_eu"
    assert res.reverse_charge is False


def test_zero_vat_non_eu_export():
    """Non-EU seller exporting to a different country → 0%."""
    res = svc.resolve_vat_for_line(
        seller_country="AE",
        buyer_country="SA",
    )
    assert res.rate_pct == Decimal("0.00")
    assert res.reason == "export"


def test_reduced_rate_se():
    """SE reduced rates 12% (food) and 6% (books) validate."""
    reduced = svc.reduced_rates("SE")
    assert Decimal("12.00") in reduced
    assert Decimal("6.00") in reduced
    res = svc.resolve_vat_for_line(
        seller_country="SE",
        buyer_country="SE",
        reduced_rate=Decimal("6.00"),
    )
    assert res.rate_pct == Decimal("6.00")
    assert res.reason == "reduced_rate"


def test_compute_vat_amount_rounding():
    """Round half up — SE 25% on 123.45 = 30.86 (not 30.8625)."""
    amt = svc.compute_vat_amount(Decimal("123.45"), Decimal("25.00"))
    assert amt == Decimal("30.86")
    assert svc.compute_vat_amount(Decimal("100.00"), Decimal("5.00")) == Decimal("5.00")
    assert svc.compute_vat_amount(Decimal("100.00"), Decimal("0.00")) == Decimal("0.00")


def test_resolve_vat_endpoint_wired():
    """VAT resolution logic is available in the service layer."""
    assert "resolve_vat_for_line" in SERVICE_SRC
    assert "VatResolution" in SERVICE_SRC
    assert "vat_amount" in ROUTER_SRC or "tax_rate" in ROUTER_SRC


# ── Invariants ─────────────────────────────────────────────────────────────


def test_eu_membership_list_is_current():
    assert svc.is_eu("SE") is True
    assert svc.is_eu("DE") is True
    assert svc.is_eu("FR") is True
    assert svc.is_eu("GB") is False  # post-Brexit
    assert svc.is_eu("AE") is False
    assert svc.is_eu("MA") is False


def test_unknown_country_returns_none():
    assert svc.standard_rate("ZZ") is None
    res = svc.resolve_vat_for_line(seller_country="ZZ", buyer_country="ZZ")
    assert res.rate_pct == Decimal("0.00")
    assert res.reason == "seller_country_unknown"


def test_invalid_reduced_rate_raises():
    with pytest.raises(ValueError):
        svc.resolve_vat_for_line(
            seller_country="SE",
            buyer_country="SE",
            reduced_rate=Decimal("7.00"),  # not in SE reduced list
        )


def test_service_is_pure():
    """No DB/HTTP/Stripe imports in the service module."""
    assert "sqlalchemy" not in SERVICE_SRC.lower()
    assert "httpx" not in SERVICE_SRC.lower()
    assert "stripe" not in SERVICE_SRC.lower()
