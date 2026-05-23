"""Pure helpers for mileage logs (Item 98).

Validators + ``compute_amount`` (distance_km × rate_per_km, quantised
to two decimals using banker's rounding — the Decimal default and
the right financial choice).

No DB access; the router layer handles persistence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

MIN_DISTANCE: Decimal = Decimal("0.01")
MAX_DISTANCE: Decimal = Decimal("100000.00")  # one trip cap — sanity guard
MIN_RATE:     Decimal = Decimal("0")
MAX_RATE:     Decimal = Decimal("9999.9999")
MAX_TEXT:     int = 200
MAX_PURPOSE:  int = 255
MAX_VEHICLE:  int = 40

# Reuse the expense convention: dual-quantise rates to 4dp and
# amounts to 2dp.
_RATE_Q   = Decimal("0.0001")
_AMOUNT_Q = Decimal("0.01")


def _to_decimal(raw: object, *, label: str) -> Decimal:
    if isinstance(raw, bool):
        raise ValueError(f"{label} must be numeric")
    try:
        return Decimal(str(raw))
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"{label} must be numeric") from e


def validate_distance(raw: object) -> Decimal:
    v = _to_decimal(raw, label="distance_km")
    if v < MIN_DISTANCE:
        raise ValueError(f"distance_km must be >= {MIN_DISTANCE}")
    if v > MAX_DISTANCE:
        raise ValueError(f"distance_km must be <= {MAX_DISTANCE}")
    return v.quantize(_AMOUNT_Q)


def validate_rate(raw: object) -> Decimal:
    v = _to_decimal(raw, label="rate_per_km")
    if v < MIN_RATE:
        raise ValueError(f"rate_per_km must be >= {MIN_RATE}")
    if v > MAX_RATE:
        raise ValueError(f"rate_per_km must be <= {MAX_RATE}")
    return v.quantize(_RATE_Q)


def validate_currency(raw: object) -> str:
    if not isinstance(raw, str):
        raise ValueError("currency must be a string")
    s = raw.strip().upper()
    if len(s) != 3 or not s.isalpha():
        raise ValueError("currency must be a 3-letter ISO code")
    return s


def validate_trip_date(raw: object) -> date:
    if not isinstance(raw, date):
        raise ValueError("trip_date must be a date")
    return raw


def _validate_optional_text(raw: object | None, *, label: str, limit: int) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError(f"{label} must be a string or None")
    s = raw.strip()
    if not s:
        return None
    if len(s) > limit:
        raise ValueError(f"{label} exceeds {limit} characters")
    return s


def validate_origin(raw: object | None) -> str | None:
    return _validate_optional_text(raw, label="origin", limit=MAX_TEXT)


def validate_destination(raw: object | None) -> str | None:
    return _validate_optional_text(raw, label="destination", limit=MAX_TEXT)


def validate_purpose(raw: object | None) -> str | None:
    return _validate_optional_text(raw, label="purpose", limit=MAX_PURPOSE)


def validate_vehicle(raw: object | None) -> str | None:
    return _validate_optional_text(raw, label="vehicle", limit=MAX_VEHICLE)


def compute_amount(*, distance_km: Decimal, rate_per_km: Decimal) -> Decimal:
    """Return ``distance × rate`` quantised to two decimals.

    Both inputs must already be quantised by the validators. Banker's
    rounding (the Decimal default) — same convention as the rest of
    the expense surface (Item 97).
    """
    if not isinstance(distance_km, Decimal) or not isinstance(rate_per_km, Decimal):
        raise ValueError("compute_amount requires Decimal inputs")
    return (distance_km * rate_per_km).quantize(_AMOUNT_Q)


@dataclass(frozen=True)
class MileageSummary:
    """Aggregate over a date range — UI-friendly preview."""
    trip_count:    int
    total_km:      Decimal
    total_amount:  Decimal
    currency:      str | None  # None when the range mixes currencies


def summarize(rows: "list[tuple[Decimal, Decimal, str]]") -> MileageSummary:
    """Aggregate ``(distance_km, amount, currency)`` triples.

    The ``currency`` is propagated only when every row shares it;
    otherwise we report ``None`` so the caller can show a "mixed"
    indicator instead of a misleading total.
    """
    if not rows:
        return MileageSummary(
            trip_count=0,
            total_km=Decimal("0.00"),
            total_amount=Decimal("0.00"),
            currency=None,
        )
    total_km = Decimal("0")
    total_amount = Decimal("0")
    currencies: set[str] = set()
    for dist, amt, cur in rows:
        total_km += Decimal(str(dist))
        total_amount += Decimal(str(amt))
        currencies.add(cur)
    return MileageSummary(
        trip_count=len(rows),
        total_km=total_km.quantize(_AMOUNT_Q),
        total_amount=total_amount.quantize(_AMOUNT_Q),
        currency=next(iter(currencies)) if len(currencies) == 1 else None,
    )
