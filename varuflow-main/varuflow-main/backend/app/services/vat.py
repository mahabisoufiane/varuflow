"""Automatic VAT calculation by country (Item 52).

Pure helpers that read the per-country JSON configs already shipped
under ``config/countries/`` and return the correct VAT rate and
classification for an invoice line.

Key scenarios:

* Domestic sale — use the country's standard rate.
* Intra-EU B2B with valid VAT number — zero-rated with
  ``reverse_charge`` marker (buyer self-accounts).
* Export outside the EU — zero-rated, no reverse charge.
* Reduced-rate goods — caller picks the index; we only validate.

Everything here is side-effect-free and depends only on the country
index loader in :mod:`app.services.country`.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from app.services.country import get_country_config

# ISO-3166 alpha-2 codes inside the EU VAT area. Maintained here so a
# new country JSON alone doesn't accidentally flip the reverse-charge
# behaviour — updates to the EU list are a conscious change.
EU_VAT_MEMBER_STATES: frozenset[str] = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE",
})

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class VatResolution:
    """Result of :func:`resolve_vat_for_line`.

    ``rate_pct`` is a Decimal so it plugs straight into the existing
    ``InvoiceLineItem.tax_rate`` column (Numeric(5, 2)).
    ``reason`` is a short machine code — handy for audit log extras and
    for the frontend to pick the right translation.
    """
    rate_pct: Decimal
    reason: str
    reverse_charge: bool = False


def _q(value: float | Decimal | int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def is_eu(country_code: str) -> bool:
    return country_code.upper() in EU_VAT_MEMBER_STATES


def standard_rate(country_code: str) -> Decimal | None:
    """Return the standard VAT rate for ``country_code`` or None if unknown."""
    cfg = get_country_config(country_code)
    if not cfg:
        return None
    vat = cfg.get("vat") or {}
    rate = vat.get("standard_rate_pct")
    if rate is None:
        return None
    return _q(rate)


def reduced_rates(country_code: str) -> list[Decimal]:
    cfg = get_country_config(country_code)
    if not cfg:
        return []
    vat = cfg.get("vat") or {}
    rates = vat.get("reduced_rates_pct") or []
    return [_q(r) for r in rates]


def valid_reduced_rate(country_code: str, rate_pct: Decimal) -> bool:
    target = _q(rate_pct)
    return target in reduced_rates(country_code) or target == ZERO


def resolve_vat_for_line(
    *,
    seller_country: str,
    buyer_country: str | None,
    buyer_has_vat_number: bool = False,
    reduced_rate: Decimal | None = None,
) -> VatResolution:
    """Classify a line's VAT using seller + buyer context.

    Rules in order:

    1. Missing buyer country → assume domestic (seller country).
    2. Reduced rate override — must be in the seller's reduced list.
    3. Seller EU + buyer EU + different country + buyer VAT registered
       → zero-rated reverse charge (Article 138).
    4. Buyer outside seller's VAT jurisdiction (non-EU for an EU seller,
       different country for a non-EU seller) → zero-rated export.
    5. Default → seller country's standard rate.
    """
    seller = seller_country.upper()
    buyer = (buyer_country or seller).upper()

    if reduced_rate is not None:
        if not valid_reduced_rate(seller, reduced_rate):
            raise ValueError(
                f"Reduced rate {reduced_rate} is not valid for {seller}"
            )
        return VatResolution(
            rate_pct=_q(reduced_rate),
            reason="reduced_rate",
        )

    seller_rate = standard_rate(seller)
    if seller_rate is None:
        # Unknown country → fall back to a safe zero with a reason so
        # the caller knows to surface it in the UI.
        return VatResolution(
            rate_pct=ZERO,
            reason="seller_country_unknown",
        )

    if buyer == seller:
        return VatResolution(rate_pct=seller_rate, reason="domestic")

    if is_eu(seller) and is_eu(buyer) and buyer_has_vat_number:
        return VatResolution(
            rate_pct=ZERO,
            reason="intra_eu_reverse_charge",
            reverse_charge=True,
        )

    if is_eu(seller) and not is_eu(buyer):
        return VatResolution(rate_pct=ZERO, reason="export_non_eu")

    if not is_eu(seller) and buyer != seller:
        return VatResolution(rate_pct=ZERO, reason="export")

    # EU seller, EU buyer, no VAT number → treat as B2C domestic-rule
    # distance sale; apply seller's standard rate by default. Proper OSS
    # handling is out of scope for this item.
    return VatResolution(rate_pct=seller_rate, reason="eu_b2c_default")


def compute_vat_amount(line_subtotal: Decimal, rate_pct: Decimal) -> Decimal:
    """Round-half-up VAT on ``line_subtotal`` at ``rate_pct`` (percent)."""
    subtotal = _q(line_subtotal)
    rate = _q(rate_pct)
    raw = (subtotal * rate) / Decimal("100")
    return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
