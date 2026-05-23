"""Pure helpers for bulk-discounting invoice lines (Item 64).

Two discount modes:

* ``percent`` — reduces each selected line's unit price by a
  percentage (0 < p <= 100).
* ``amount`` — subtracts a fixed currency amount from each selected
  line's unit price (per unit, not per line).

Both modes floor the resulting unit price at zero — we never let a
line go negative. Tax is recomputed against the discounted subtotal.

All arithmetic is done in :class:`decimal.Decimal` to preserve cent
precision. Two-decimal rounding uses ``ROUND_HALF_UP``.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

ALLOWED_KINDS: frozenset[str] = frozenset({"percent", "amount"})

MIN_PERCENT: Decimal = Decimal("0.01")
MAX_PERCENT: Decimal = Decimal("100")
MIN_AMOUNT:  Decimal = Decimal("0.01")
MAX_AMOUNT:  Decimal = Decimal("1000000")

_ZERO = Decimal("0")
_Q2 = Decimal("0.01")


@dataclass(frozen=True)
class LineIn:
    id:          str
    quantity:    Decimal
    unit_price:  Decimal
    tax_rate:    Decimal


@dataclass(frozen=True)
class LineOut:
    id:         str
    unit_price: Decimal
    line_total: Decimal
    changed:    bool


@dataclass(frozen=True)
class Totals:
    subtotal:   Decimal
    vat_amount: Decimal
    total:      Decimal


def _q(v: Decimal) -> Decimal:
    return v.quantize(_Q2, rounding=ROUND_HALF_UP)


def validate_kind(kind: str) -> str:
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"kind must be one of {sorted(ALLOWED_KINDS)}")
    return kind


def validate_value(kind: str, value: Decimal) -> Decimal:
    if not isinstance(value, Decimal):
        try:
            value = Decimal(str(value))
        except Exception:
            raise ValueError("value must be a number")
    if kind == "percent":
        if value < MIN_PERCENT or value > MAX_PERCENT:
            raise ValueError(
                f"percent must be between {MIN_PERCENT} and {MAX_PERCENT}"
            )
    else:  # amount
        if value < MIN_AMOUNT or value > MAX_AMOUNT:
            raise ValueError(
                f"amount must be between {MIN_AMOUNT} and {MAX_AMOUNT}"
            )
    return value


def apply_discount_to_line(
    line: LineIn, *, kind: str, value: Decimal
) -> LineOut:
    """Return a new LineOut reflecting the discount."""
    if kind == "percent":
        factor = (Decimal("100") - value) / Decimal("100")
        new_unit = line.unit_price * factor
    else:  # amount — per-unit subtraction
        new_unit = line.unit_price - value
    if new_unit < _ZERO:
        new_unit = _ZERO
    new_unit = _q(new_unit)
    new_total = _q(new_unit * line.quantity)
    return LineOut(
        id=line.id,
        unit_price=new_unit,
        line_total=new_total,
        changed=new_unit != _q(line.unit_price),
    )


def apply_bulk_discount(
    lines: Iterable[LineIn],
    *,
    kind: str,
    value: Decimal,
    selected_ids: set[str] | None = None,
) -> list[LineOut]:
    """Apply the discount to the selected lines.

    When ``selected_ids`` is ``None`` every line is touched; otherwise
    only lines whose id is in the set are modified. Non-selected
    lines are returned unchanged (``changed=False``).
    """
    validate_kind(kind)
    validate_value(kind, value)
    lines = list(lines)
    if not lines:
        raise ValueError("no lines to discount")
    if selected_ids is not None and not selected_ids:
        raise ValueError("selected_ids cannot be empty")

    out: list[LineOut] = []
    touched = 0
    for ln in lines:
        if selected_ids is not None and ln.id not in selected_ids:
            out.append(
                LineOut(
                    id=ln.id,
                    unit_price=_q(ln.unit_price),
                    line_total=_q(ln.unit_price * ln.quantity),
                    changed=False,
                )
            )
            continue
        out.append(apply_discount_to_line(ln, kind=kind, value=value))
        touched += 1

    if selected_ids is not None and touched != len(selected_ids):
        # Caller asked for specific lines but some didn't exist on the
        # invoice. Signal the miss so the router can 404.
        raise ValueError("one or more selected_ids not on invoice")
    return out


def compute_totals(
    lines_in: Iterable[LineIn], lines_out: Iterable[LineOut]
) -> Totals:
    """Recompute subtotal/VAT/total from the new unit prices.

    ``lines_in`` supplies the tax_rate per line (tax_rate is never
    touched by the bulk discount); ``lines_out`` supplies the new
    line totals. We iterate in lockstep so the caller doesn't have
    to rebuild a dict.
    """
    subtotal = _ZERO
    vat = _ZERO
    for lin, lout in zip(lines_in, lines_out):
        if lin.id != lout.id:
            raise ValueError("lines_in / lines_out must align by id")
        subtotal += lout.line_total
        vat += lout.line_total * (lin.tax_rate / Decimal("100"))
    subtotal = _q(subtotal)
    vat = _q(vat)
    return Totals(subtotal=subtotal, vat_amount=vat, total=_q(subtotal + vat))
