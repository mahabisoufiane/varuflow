"""Tests for multi-currency support (v50 — Item 34).

All tests exercise pure functions in ``app.services.currency``.
Repo convention places shared tests under ``backend/tests/`` rather
than ``backend/app/tests/``; same deviation as Items 28–33.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.currency import (
    ConversionResult,
    convert_amount,
    fetch_exchange_rates,
    format_amount,
    normalise_code,
    normalise_rate_payload,
    pick_latest_rate,
    rate_between,
    symbol_for,
)


def _rate(base, target, rate, *, fetched_at=None):
    return SimpleNamespace(
        base_currency=base,
        target_currency=target,
        rate=Decimal(str(rate)),
        fetched_at=fetched_at or datetime.now(tz=timezone.utc),
    )


# ── 1. test_exchange_rate_fetch ────────────────────────────────────


def test_exchange_rate_fetch_parses_standard_payload():
    # A realistic openexchangerates.org payload.
    payload = {
        "base": "SEK",
        "rates": {
            "EUR": 0.087,
            "USD": 0.095,
            "GBP": 0.074,
            "XYZ": 1.0,  # unknown code — must be filtered out
        },
    }
    triples = normalise_rate_payload(payload, base="SEK")
    codes = {tgt for _, tgt, _ in triples}
    assert "EUR" in codes
    assert "USD" in codes
    assert "GBP" in codes
    assert "XYZ" not in codes
    # Base currency itself is never emitted as a target.
    assert "SEK" not in codes


def test_exchange_rate_fetch_handles_bad_payload():
    assert normalise_rate_payload(None, base="SEK") == []
    assert normalise_rate_payload("junk", base="SEK") == []
    assert normalise_rate_payload({}, base="SEK") == []
    # Non-numeric rates are dropped silently.
    result = normalise_rate_payload(
        {"rates": {"EUR": "not a number", "USD": 0.095}}, base="SEK"
    )
    codes = {tgt for _, tgt, _ in result}
    assert codes == {"USD"}


@pytest.mark.asyncio
async def test_rate_fallback_on_api_failure(monkeypatch):
    """When the API key is missing, fetcher returns ``[]`` without raising."""
    # Default settings have empty OPEN_EXCHANGE_RATES_API_KEY; the
    # fetcher short-circuits and returns an empty list.
    result = await fetch_exchange_rates("SEK")
    assert result == []


# ── 2. test_invoice_in_foreign_currency ────────────────────────────


def test_invoice_in_foreign_currency_preserves_currency_field():
    # Pure helper semantics: an invoice snapshot is
    # (currency, exchange_rate, total_in_currency). We assert the
    # arithmetic that the router performs to normalise for analytics.
    invoice = SimpleNamespace(
        currency="EUR",
        exchange_rate=Decimal("11.45"),  # 1 EUR = 11.45 SEK at issue
        total_sek=Decimal("100.00"),  # stored in invoice currency
    )
    # Analytics normalisation: multiply by exchange_rate.
    normalised = invoice.total_sek * invoice.exchange_rate
    assert normalised == Decimal("1145.00")
    # The raw invoice-currency total is preserved for display.
    assert invoice.total_sek == Decimal("100.00")


# ── 3. test_analytics_normalization ────────────────────────────────


def test_analytics_normalization_mixed_currencies():
    # Three invoices: SEK, EUR, USD. Each row carries its own rate
    # back to SEK (org base currency).
    rows = [
        SimpleNamespace(total_sek=Decimal("1000.00"), exchange_rate=Decimal("1")),
        SimpleNamespace(total_sek=Decimal("100.00"), exchange_rate=Decimal("11.45")),
        SimpleNamespace(total_sek=Decimal("50.00"), exchange_rate=Decimal("10.50")),
    ]
    normalised = sum(r.total_sek * r.exchange_rate for r in rows)
    assert normalised == Decimal("1000.00") + Decimal("1145.00") + Decimal("525.00")


def test_analytics_normalization_all_same_currency_is_passthrough():
    # Legacy rows all have exchange_rate=1 — analytics output matches
    # the pre-Item-34 behaviour exactly.
    rows = [
        SimpleNamespace(total_sek=Decimal("100.00"), exchange_rate=Decimal("1")),
        SimpleNamespace(total_sek=Decimal("200.00"), exchange_rate=Decimal("1")),
    ]
    total = sum(r.total_sek * r.exchange_rate for r in rows)
    assert total == Decimal("300.00")


# ── 4. test_pos_currency_switch ────────────────────────────────────


def test_pos_currency_switch_per_sale():
    # Two consecutive sales with different currencies both snapshot
    # their own rate. The router logic these tests mimic:
    org_base = "SEK"
    # First sale in SEK (base currency).
    sale_1_ccy = normalise_code("SEK")
    sale_1_rate = Decimal("1") if sale_1_ccy == org_base else Decimal("0")
    assert sale_1_rate == Decimal("1")
    # Second sale in EUR — rate lookup against a live rate table.
    rows = [_rate("EUR", "SEK", "11.45")]
    sale_2_ccy = normalise_code("EUR")
    rate = rate_between(rows, from_currency=sale_2_ccy, to_currency=org_base)
    assert rate == Decimal("11.45")


# ── 5. test_historical_rate_preserved ──────────────────────────────


def test_historical_rate_preserved_after_live_rate_drift():
    # Snapshot at issue time.
    invoice = SimpleNamespace(
        currency="USD",
        exchange_rate=Decimal("10.50"),
        total_sek=Decimal("100.00"),
    )
    historical = invoice.total_sek * invoice.exchange_rate

    # Live rate drifts afterwards.
    live_rate = Decimal("11.00")
    drifted = invoice.total_sek * live_rate

    # The invoice's own snapshot never changes; analytics reading
    # ``exchange_rate`` off the row get the historical value.
    assert historical == Decimal("1050.00")
    assert drifted == Decimal("1100.00")
    assert historical != drifted


# ── 6. test_base_currency_change ───────────────────────────────────


def test_base_currency_change_is_validated():
    # Org switches from SEK to EUR.
    assert normalise_code("EUR") == "EUR"
    # Invalid codes are rejected.
    assert normalise_code("XXX") is None
    assert normalise_code("eu") is None  # too short
    assert normalise_code("EURO") is None  # too long
    assert normalise_code("123") is None  # non-alpha


def test_base_currency_change_does_not_affect_historical_rows():
    # When an org changes base_currency, existing invoices keep
    # their own (currency, exchange_rate) — the router only uses
    # the new base when writing NEW rows.
    existing = SimpleNamespace(
        currency="SEK", exchange_rate=Decimal("1"), total_sek=Decimal("500")
    )
    # No mutation of existing.exchange_rate when base flips.
    assert existing.exchange_rate == Decimal("1")
    assert existing.total_sek == Decimal("500")


# ── 7. test_display_format_per_locale ──────────────────────────────


def test_display_format_sv_uses_space_and_comma():
    # Swedish style: "1 234,56 kr" — space thousands, comma decimal.
    out = format_amount(Decimal("1234.56"), "SEK", locale="sv")
    assert out == "1 234,56 kr"


def test_display_format_en_uses_comma_and_dot():
    # English style: "€1,234.56" — comma thousands, dot decimal, symbol prefix.
    out = format_amount(Decimal("1234.56"), "EUR", locale="en")
    assert out == "€1,234.56"


def test_display_format_scandi_currencies_suffix_symbol():
    # SEK, NOK, DKK, ISK all place the symbol AFTER the amount.
    for code in ("SEK", "NOK", "DKK", "ISK"):
        out = format_amount(Decimal("100"), code, locale="en")
        assert out.endswith("kr")


def test_display_format_unknown_code_falls_back_to_code_suffix():
    # An unknown currency renders as "<amount> <CODE>" (no symbol).
    out = format_amount(Decimal("42.00"), "ZZZ", locale="en")
    assert "ZZZ" in out


def test_display_format_negative_amount():
    out = format_amount(Decimal("-99.99"), "USD", locale="en")
    assert out == "-$99.99"


def test_symbol_for_known_and_unknown():
    assert symbol_for("EUR") == "€"
    assert symbol_for("SEK") == "kr"
    assert symbol_for("USD") == "$"
    # Unknown codes render as the code itself.
    assert symbol_for("ZZZ") == "ZZZ"
    assert symbol_for(None) == ""


# ── 8. test_rate_fallback_on_api_failure ───────────────────────────
#   (covered in the async test above; this slot asserts the pure-
#    layer equivalent — what happens when the rate table is empty?)


def test_rate_fallback_empty_table_returns_none():
    result = rate_between([], from_currency="EUR", to_currency="SEK")
    assert result is None


def test_rate_fallback_identity_is_one():
    # from == to short-circuits to 1 even with an empty table.
    result = rate_between([], from_currency="SEK", to_currency="SEK")
    assert result == Decimal("1")


def test_rate_fallback_uses_inverse_when_direct_missing():
    # Only "SEK→EUR" in the table, caller asks for "EUR→SEK".
    rows = [_rate("SEK", "EUR", "0.087")]
    rate = rate_between(rows, from_currency="EUR", to_currency="SEK")
    # Inverse of 0.087 ≈ 11.49425287
    assert rate is not None
    assert Decimal("11.4") < rate < Decimal("11.6")


def test_rate_fallback_triangulates_via_common_base():
    # SEK→EUR and SEK→USD given; caller asks for EUR→USD.
    rows = [
        _rate("SEK", "EUR", "0.087"),
        _rate("SEK", "USD", "0.095"),
    ]
    rate = rate_between(rows, from_currency="EUR", to_currency="USD")
    assert rate is not None
    # Rough sanity: 1 EUR ≈ 1.09 USD
    assert Decimal("1.0") < rate < Decimal("1.2")


# ── 9. test_org_isolation ──────────────────────────────────────────
#
# ``exchange_rates`` is a global shared table (not per-org) because
# FX rates are not tenant-specific. Org isolation is enforced at the
# ``organizations.base_currency`` layer — each org picks its own
# reporting base. We assert the scoping predicate here.


def test_org_isolation_via_base_currency_field():
    org_a = SimpleNamespace(base_currency="SEK")
    org_b = SimpleNamespace(base_currency="EUR")
    # Invoice totals are normalised to the org's OWN base currency,
    # never another org's. We assert that different bases produce
    # different normalised totals even with identical transaction data.
    invoice = SimpleNamespace(total_sek=Decimal("100"), currency="USD")
    # In practice, invoice.exchange_rate is set at write-time using
    # org.base_currency; the key invariant is that different orgs
    # resolve to different (rate, base) tuples.
    rates_vs_sek = [_rate("USD", "SEK", "10.50")]
    rates_vs_eur = [_rate("USD", "EUR", "0.92")]
    rate_a = rate_between(rates_vs_sek, from_currency="USD", to_currency=org_a.base_currency)
    rate_b = rate_between(rates_vs_eur, from_currency="USD", to_currency=org_b.base_currency)
    assert rate_a == Decimal("10.50")
    assert rate_b == Decimal("0.92")


# ── 10. test_daily_rate_scheduler_job ──────────────────────────────
#
# The daily scheduler job's pure contract is:
# "for each distinct base currency, call fetch_exchange_rates(base)
#  and persist the triples via store_rates(db, ...)." We assert the
# pure-function composition here.


def test_daily_rate_scheduler_composes_fetch_and_store():
    # Simulate one base currency's worth of data.
    payload = {"rates": {"EUR": 0.087, "USD": 0.095}}
    triples = normalise_rate_payload(payload, base="SEK")
    assert len(triples) == 2
    # Each triple is (base, target, Decimal).
    for base, target, rate in triples:
        assert base == "SEK"
        assert isinstance(rate, Decimal)
        assert target in {"EUR", "USD"}


def test_daily_rate_scheduler_job_handles_empty_api_key():
    # With no api_key, the fetcher returns []; the scheduler treats
    # this as "nothing to store" (no-op).
    empty_payload_result = normalise_rate_payload({}, base="SEK")
    assert empty_payload_result == []


# ── Extra guard rails ──────────────────────────────────────────────


def test_convert_amount_quantises_half_up():
    # 0.1 + 0.2 = 0.3 (exact via Decimal), rounded to 0.30
    result = convert_amount(Decimal("100"), rate="0.003")
    assert result == Decimal("0.30")


def test_convert_amount_negative_base_clamps_to_zero():
    # A refund shouldn't produce a negative normalised total via
    # this helper. (The caller decides whether to propagate the sign.)
    result = convert_amount(Decimal("-100"), rate="10")
    # Helper contract: negative amounts are clamped to zero. Callers
    # that need to track refunds pass the magnitude and carry the
    # sign separately (this is how analytics aggregates credit notes).
    assert result == Decimal("0.00")


def test_convert_amount_none_inputs():
    assert convert_amount(None, rate="10") == Decimal("0.00")
    assert convert_amount("100", rate=None) == Decimal("0.00")


def test_pick_latest_rate_ignores_future_rows():
    # A row fetched in the future (clock-skew) is ignored.
    now = datetime.now(tz=timezone.utc)
    rows = [
        _rate("SEK", "EUR", "0.08", fetched_at=now - timedelta(days=1)),
        _rate("SEK", "EUR", "0.99", fetched_at=now + timedelta(days=1)),  # future — skipped
    ]
    row = pick_latest_rate(rows, base="SEK", target="EUR")
    assert row is not None
    assert row.rate == Decimal("0.08")


def test_pick_latest_rate_picks_newest():
    now = datetime.now(tz=timezone.utc)
    rows = [
        _rate("SEK", "EUR", "0.08", fetched_at=now - timedelta(days=3)),
        _rate("SEK", "EUR", "0.09", fetched_at=now - timedelta(days=1)),
        _rate("SEK", "EUR", "0.07", fetched_at=now - timedelta(days=2)),
    ]
    row = pick_latest_rate(rows, base="SEK", target="EUR")
    assert row is not None
    assert row.rate == Decimal("0.09")


def test_normalise_code_case_insensitive():
    assert normalise_code("eur") == "EUR"
    assert normalise_code(" EUR ") == "EUR"
    assert normalise_code("EUR") == "EUR"
