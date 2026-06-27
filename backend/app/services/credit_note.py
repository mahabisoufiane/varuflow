"""Pure helpers for customer credit notes (Item 70).

Responsibilities kept in this module:

* Per-line and per-document total computation — identical VAT
  handling to ``invoicing`` (tax is applied on line_total, HALF_UP
  to 2 decimals).
* Currency / reason / quantity / price / tax_rate validation.
* Status-machine guard (``DRAFT → ISSUED → VOIDED``) via
  :func:`assert_transition`.
* Per-org sequential number minting (``CN-YYYY-NNNN``) given the
  set of numbers already used for that ``(org, year)`` pair.
* Allocation cap against a source invoice — a credit note whose
  ``total`` exceeds the invoice's outstanding balance is rejected.

Nothing in here touches the DB. The router is the only layer that
loads rows and commits transactions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# String-based status constants — decoupled from the ORM model so
# this module is safely importable without loading SQLAlchemy (tests
# exercise the service without a DB).
STATUS_DRAFT  = "DRAFT"
STATUS_ISSUED = "ISSUED"
STATUS_VOIDED = "VOIDED"
ALLOWED_STATUSES: frozenset[str] = frozenset({
    STATUS_DRAFT, STATUS_ISSUED, STATUS_VOIDED,
})

_Q2 = Decimal("0.01")

MAX_REASON_LENGTH:  int = 500
MAX_DESC_LENGTH:    int = 500
MAX_QUANTITY:       Decimal = Decimal("1000000")
MAX_UNIT_PRICE:     Decimal = Decimal("10000000")
MAX_LINES:          int = 200

ALLOWED_TAX_RATES: frozenset[Decimal] = frozenset({
    Decimal("0.00"),
    Decimal("6.00"),
    Decimal("12.00"),
    Decimal("25.00"),
})

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_NUMBER_RE   = re.compile(r"^CN-(\d{4})-(\d{4,})$")


@dataclass(frozen=True)
class LineTotals:
    line_total: Decimal   # quantity * unit_price  (HALF_UP to cents)
    tax_amount: Decimal   # line_total * tax_rate/100


@dataclass(frozen=True)
class DocumentTotals:
    subtotal:  Decimal
    tax_total: Decimal
    total:     Decimal


# ── Status machine ────────────────────────────────────────────────────────

_ALLOWED: dict[str, frozenset[str]] = {
    STATUS_DRAFT:  frozenset({STATUS_ISSUED, STATUS_VOIDED}),
    STATUS_ISSUED: frozenset({STATUS_VOIDED}),
    STATUS_VOIDED: frozenset(),
}


def _as_status(s) -> str:
    if hasattr(s, "value"):
        s = s.value
    s = str(s)
    if s not in ALLOWED_STATUSES:
        raise ValueError(f"unknown credit-note status: {s}")
    return s


def assert_transition(src, dst) -> None:
    s = _as_status(src)
    d = _as_status(dst)
    if d not in _ALLOWED[s]:
        raise ValueError(
            f"Invalid credit-note status transition {s} → {d}"
        )


# ── Validators ────────────────────────────────────────────────────────────


def validate_currency(code: str) -> str:
    c = (code or "").strip().upper()
    if not _CURRENCY_RE.match(c):
        raise ValueError("currency must be a 3-letter ISO code")
    return c


def validate_reason(r: str | None) -> str | None:
    if r is None:
        return None
    v = r.strip()
    if not v:
        return None
    if len(v) > MAX_REASON_LENGTH:
        raise ValueError(f"reason too long ({MAX_REASON_LENGTH} chars max)")
    return v


def _coerce_decimal(v, *, field: str) -> Decimal:
    if isinstance(v, bool):
        raise ValueError(f"{field} must be numeric, not bool")
    if isinstance(v, Decimal):
        return v
    if isinstance(v, (int, float)):
        return Decimal(str(v))
    if isinstance(v, str):
        try:
            return Decimal(v.strip().replace(",", ".") or "0")
        except InvalidOperation as exc:
            raise ValueError(f"{field} is not a valid decimal") from exc
    raise ValueError(f"{field} must be numeric")


def validate_quantity(q) -> Decimal:
    d = _coerce_decimal(q, field="quantity")
    if d <= 0:
        raise ValueError("quantity must be > 0")
    if d > MAX_QUANTITY:
        raise ValueError(f"quantity exceeds {MAX_QUANTITY}")
    return d.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def validate_unit_price(p) -> Decimal:
    d = _coerce_decimal(p, field="unit_price")
    if d < 0:
        raise ValueError("unit_price must be ≥ 0")
    if d > MAX_UNIT_PRICE:
        raise ValueError(f"unit_price exceeds {MAX_UNIT_PRICE}")
    return d.quantize(_Q2, rounding=ROUND_HALF_UP)


def validate_tax_rate(r) -> Decimal:
    d = _coerce_decimal(r, field="tax_rate").quantize(_Q2)
    if d not in ALLOWED_TAX_RATES:
        raise ValueError(
            "tax_rate must be one of "
            + ", ".join(str(x) for x in sorted(ALLOWED_TAX_RATES))
        )
    return d


def validate_description(d: str) -> str:
    v = (d or "").strip()
    if not v:
        raise ValueError("description is required")
    if len(v) > MAX_DESC_LENGTH:
        raise ValueError(f"description too long ({MAX_DESC_LENGTH} max)")
    return v


def validate_issue_date(d: date) -> date:
    if not isinstance(d, date):
        raise ValueError("issue_date must be a date")
    return d


# ── Totals ────────────────────────────────────────────────────────────────


def compute_line(
    *, quantity: Decimal, unit_price: Decimal, tax_rate: Decimal,
) -> LineTotals:
    q  = _coerce_decimal(quantity,   field="quantity")
    up = _coerce_decimal(unit_price, field="unit_price")
    tr = _coerce_decimal(tax_rate,   field="tax_rate")
    gross = (q * up).quantize(_Q2, rounding=ROUND_HALF_UP)
    tax   = (gross * tr / Decimal("100")).quantize(
        _Q2, rounding=ROUND_HALF_UP,
    )
    return LineTotals(line_total=gross, tax_amount=tax)


def compute_totals(lines: list[dict]) -> DocumentTotals:
    if len(lines) > MAX_LINES:
        raise ValueError(f"too many lines ({MAX_LINES} max)")
    subtotal = Decimal("0.00")
    tax_total = Decimal("0.00")
    for ln in lines:
        part = compute_line(
            quantity=ln["quantity"],
            unit_price=ln["unit_price"],
            tax_rate=ln.get("tax_rate", Decimal("25.00")),
        )
        subtotal += part.line_total
        tax_total += part.tax_amount
    return DocumentTotals(
        subtotal=subtotal.quantize(_Q2),
        tax_total=tax_total.quantize(_Q2),
        total=(subtotal + tax_total).quantize(_Q2),
    )


# ── Number minting ────────────────────────────────────────────────────────


def next_number(*, year: int, existing: set[str]) -> str:
    """Allocate the next ``CN-YYYY-NNNN`` number for this year.

    ``existing`` is the set of credit-note numbers already minted for
    the *same* tenant — the caller queries it with an SQL
    ``SELECT number FROM credit_notes WHERE org_id=:org`` and passes
    the result. Min width 4 digits but grows naturally past 9999.
    """
    if not (2000 <= year <= 3000):
        raise ValueError("year out of range")
    max_seen = 0
    prefix = f"CN-{year:04d}-"
    for n in existing:
        if not n:
            continue
        m = _NUMBER_RE.match(n)
        if not m:
            continue
        if int(m.group(1)) != year:
            continue
        seq = int(m.group(2))
        if seq > max_seen:
            max_seen = seq
    seq = max_seen + 1
    return f"{prefix}{seq:04d}"


# ── Allocation cap ────────────────────────────────────────────────────────


def assert_fits_invoice(
    *,
    credit_total:         Decimal,
    invoice_total:        Decimal,
    invoice_paid:         Decimal,
    invoice_credited:     Decimal,
) -> None:
    """Reject a credit that would push credits + payments past the total.

    Called only when the credit note has a source invoice. Standalone
    credits (``invoice_id is None``) are uncapped by design.
    """
    credit_total      = _coerce_decimal(credit_total,      field="credit_total")
    invoice_total     = _coerce_decimal(invoice_total,     field="invoice_total")
    invoice_paid      = _coerce_decimal(invoice_paid,      field="invoice_paid")
    invoice_credited  = _coerce_decimal(invoice_credited,  field="invoice_credited")
    if credit_total <= 0:
        raise ValueError("credit note total must be > 0 to issue")
    remaining = invoice_total - invoice_paid - invoice_credited
    if credit_total > remaining:
        raise ValueError(
            f"credit note exceeds invoice remaining balance "
            f"({credit_total} > {remaining})"
        )
