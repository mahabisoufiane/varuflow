"""Pure helpers for product variants (Item 53).

Kept side-effect-free so tests can exercise pricing and stock logic
without a database.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable


@dataclass(frozen=True)
class VariantPricing:
    sell_price: Decimal
    purchase_price: Decimal


def effective_prices(
    *,
    parent_sell_price: Decimal,
    parent_purchase_price: Decimal,
    variant_sell_override: Decimal | None,
    variant_purchase_override: Decimal | None,
) -> VariantPricing:
    """Variant price = override if set, else inherited from parent.

    Both overrides are independent — a variant can override only the
    sell price without touching the purchase price.
    """
    return VariantPricing(
        sell_price=(
            variant_sell_override
            if variant_sell_override is not None
            else parent_sell_price
        ),
        purchase_price=(
            variant_purchase_override
            if variant_purchase_override is not None
            else parent_purchase_price
        ),
    )


def normalise_attributes(raw: dict[str, Any] | None) -> dict[str, str]:
    """Coerce attribute values to strings and drop empty keys/values.

    ``{"size": "M", "color": " Blue "}`` → ``{"size": "M", "color": "Blue"}``.
    Keys and values are trimmed and values stringified; empty strings are
    dropped. Keeps the JSONB payload small and comparable.
    """
    if not raw:
        return {}
    out: dict[str, str] = {}
    for key, value in raw.items():
        if key is None:
            continue
        k = str(key).strip()
        if not k:
            continue
        if value is None:
            continue
        v = str(value).strip()
        if not v:
            continue
        out[k] = v
    return out


def attributes_match(a: dict[str, str], b: dict[str, str]) -> bool:
    """Equality of two normalised attribute maps (case-sensitive values)."""
    return normalise_attributes(a) == normalise_attributes(b)


def find_variant_by_attributes(
    variants: Iterable[dict[str, Any]],
    target_attrs: dict[str, Any],
) -> dict[str, Any] | None:
    """Return the first variant whose attributes match ``target_attrs``.

    ``variants`` is expected to be a sequence of dict-like rows with an
    ``attributes`` key. Returns ``None`` if no match.
    """
    target = normalise_attributes(target_attrs)
    for v in variants:
        if attributes_match(v.get("attributes") or {}, target):
            return v
    return None


def total_stock(levels: Iterable[dict[str, Any]]) -> int:
    """Sum ``quantity`` across a sequence of stock level rows."""
    return sum(int(r.get("quantity") or 0) for r in levels)


def has_sufficient_stock(
    levels: Iterable[dict[str, Any]],
    required: int,
) -> bool:
    if required <= 0:
        return True
    return total_stock(levels) >= required
