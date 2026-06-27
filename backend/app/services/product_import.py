"""Pure helpers for bulk product import (Item 69).

Parses CSV uploads into validated product rows. Produces a summary
with per-row errors so operators can fix the spreadsheet and retry.

CSV schema
----------
Required columns: ``sku``, ``name``, ``purchase_price``, ``sell_price``.
Optional columns: ``category``, ``unit``, ``tax_rate``, ``barcode``,
``description``, ``reorder_level``.

Rules:
* SKU must be unique within the file.
* ``tax_rate`` must be in {6, 12, 25} — Swedish VAT values.
* Prices must be non-negative Decimal (supports `,` decimal separator).
* ``reorder_level`` defaults to 0; must be non-negative integer.
* Unknown columns are ignored (operators often paste from Excel
  exports with extra metadata columns).
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable

REQUIRED_COLUMNS: frozenset[str] = frozenset({
    "sku", "name", "purchase_price", "sell_price",
})
OPTIONAL_COLUMNS: frozenset[str] = frozenset({
    "category", "unit", "tax_rate", "barcode", "description",
    "reorder_level",
})
KNOWN_COLUMNS: frozenset[str] = REQUIRED_COLUMNS | OPTIONAL_COLUMNS

ALLOWED_TAX_RATES: frozenset[Decimal] = frozenset({
    Decimal("6.00"), Decimal("12.00"), Decimal("25.00"),
})

MAX_ROWS: int = 10_000
MAX_SKU_LENGTH: int = 100
MAX_NAME_LENGTH: int = 255
MAX_CATEGORY_LENGTH: int = 100
MAX_UNIT_LENGTH: int = 50
MAX_BARCODE_LENGTH: int = 50
MAX_PRICE: Decimal = Decimal("10000000")
MAX_REORDER_LEVEL: int = 1_000_000

_Q2 = Decimal("0.01")


@dataclass(frozen=True)
class ProductRow:
    sku:            str
    name:           str
    purchase_price: Decimal
    sell_price:     Decimal
    category:       str | None
    unit:           str
    tax_rate:       Decimal
    barcode:        str | None
    description:    str | None
    reorder_level:  int


@dataclass(frozen=True)
class RowError:
    line:    int  # 1-indexed source row (excluding header)
    field:   str | None
    message: str


@dataclass(frozen=True)
class ImportResult:
    rows:   list[ProductRow]
    errors: list[RowError]


def _clean(v: str | None) -> str:
    return (v or "").strip()


def _parse_decimal(raw: str, *, field: str) -> Decimal:
    s = _clean(raw).replace(" ", "").replace(",", ".")
    if not s:
        raise ValueError(f"{field} is required")
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise ValueError(f"{field} must be a number")
    return d


def _parse_int(raw: str, *, field: str) -> int:
    s = _clean(raw)
    if not s:
        raise ValueError(f"{field} is required")
    try:
        n = int(s)
    except ValueError:
        raise ValueError(f"{field} must be an integer")
    return n


def _require_non_negative(d: Decimal, *, field: str) -> Decimal:
    if d < 0:
        raise ValueError(f"{field} must be non-negative")
    if d > MAX_PRICE:
        raise ValueError(f"{field} exceeds {MAX_PRICE}")
    return d.quantize(_Q2)


def _validate_tax_rate(raw: str) -> Decimal:
    d = _parse_decimal(raw, field="tax_rate")
    d = d.quantize(_Q2)
    if d not in ALLOWED_TAX_RATES:
        raise ValueError(
            f"tax_rate must be one of {sorted(float(r) for r in ALLOWED_TAX_RATES)}"
        )
    return d


def _validate_reorder(raw: str) -> int:
    s = _clean(raw)
    if s == "":
        return 0
    n = _parse_int(raw, field="reorder_level")
    if n < 0:
        raise ValueError("reorder_level must be non-negative")
    if n > MAX_REORDER_LEVEL:
        raise ValueError(f"reorder_level exceeds {MAX_REORDER_LEVEL}")
    return n


def validate_row(record: dict, *, line: int) -> ProductRow:
    """Validate a single CSV row dict. Raises :class:`ValueError`."""
    sku = _clean(record.get("sku"))
    if not sku:
        raise ValueError("sku is required")
    if len(sku) > MAX_SKU_LENGTH:
        raise ValueError(f"sku too long ({MAX_SKU_LENGTH} chars max)")

    name = " ".join(_clean(record.get("name")).split())
    if not name:
        raise ValueError("name is required")
    if len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"name too long ({MAX_NAME_LENGTH} chars max)")

    pp = _require_non_negative(
        _parse_decimal(record.get("purchase_price", ""), field="purchase_price"),
        field="purchase_price",
    )
    sp = _require_non_negative(
        _parse_decimal(record.get("sell_price", ""), field="sell_price"),
        field="sell_price",
    )

    category_raw = _clean(record.get("category"))
    category = category_raw or None
    if category and len(category) > MAX_CATEGORY_LENGTH:
        raise ValueError(f"category too long ({MAX_CATEGORY_LENGTH} max)")

    unit = _clean(record.get("unit")) or "st"
    if len(unit) > MAX_UNIT_LENGTH:
        raise ValueError(f"unit too long ({MAX_UNIT_LENGTH} max)")

    tax_raw = _clean(record.get("tax_rate"))
    tax_rate = _validate_tax_rate(tax_raw) if tax_raw else Decimal("25.00")

    barcode_raw = _clean(record.get("barcode"))
    barcode = barcode_raw or None
    if barcode and len(barcode) > MAX_BARCODE_LENGTH:
        raise ValueError(f"barcode too long ({MAX_BARCODE_LENGTH} max)")

    description_raw = _clean(record.get("description"))
    description = description_raw or None

    reorder_level = _validate_reorder(record.get("reorder_level", ""))

    return ProductRow(
        sku=sku,
        name=name,
        purchase_price=pp,
        sell_price=sp,
        category=category,
        unit=unit,
        tax_rate=tax_rate,
        barcode=barcode,
        description=description,
        reorder_level=reorder_level,
    )


def parse_csv(text: str) -> ImportResult:
    """Parse an entire CSV document, returning good rows + errors."""
    if not isinstance(text, str):
        raise ValueError("csv text must be a string")

    buf = io.StringIO(text)
    reader = csv.DictReader(buf)

    if reader.fieldnames is None:
        return ImportResult(rows=[], errors=[RowError(0, None, "empty file")])

    # Normalise header names.
    header = [h.strip().lower() for h in reader.fieldnames]
    missing = REQUIRED_COLUMNS - set(header)
    if missing:
        return ImportResult(
            rows=[],
            errors=[
                RowError(
                    0, None,
                    f"missing required columns: {sorted(missing)}",
                )
            ],
        )

    rows: list[ProductRow] = []
    errors: list[RowError] = []
    seen_skus: set[str] = set()
    seen_barcodes: set[str] = set()

    for idx, raw in enumerate(reader, start=1):
        if idx > MAX_ROWS:
            errors.append(RowError(idx, None, f"file exceeds {MAX_ROWS} rows"))
            break
        record = {
            h: (raw.get(orig) or "")
            for h, orig in zip(header, reader.fieldnames)
        }
        try:
            row = validate_row(record, line=idx)
        except ValueError as e:
            errors.append(RowError(idx, None, str(e)))
            continue

        if row.sku in seen_skus:
            errors.append(
                RowError(idx, "sku", f"duplicate sku in file: {row.sku}")
            )
            continue
        if row.barcode is not None and row.barcode in seen_barcodes:
            errors.append(
                RowError(
                    idx, "barcode",
                    f"duplicate barcode in file: {row.barcode}",
                )
            )
            continue
        seen_skus.add(row.sku)
        if row.barcode is not None:
            seen_barcodes.add(row.barcode)
        rows.append(row)

    return ImportResult(rows=rows, errors=errors)


def classify_against_existing(
    rows: Iterable[ProductRow],
    *,
    existing_skus: set[str],
) -> tuple[list[ProductRow], list[ProductRow]]:
    """Split parsed rows into (to_insert, to_update)."""
    inserts: list[ProductRow] = []
    updates: list[ProductRow] = []
    for r in rows:
        if r.sku in existing_skus:
            updates.append(r)
        else:
            inserts.append(r)
    return inserts, updates
