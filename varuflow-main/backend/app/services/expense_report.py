"""Pure helpers for expense reports (Item 100).

State-machine transition table + validators (title, currency, note,
paid_reference). The router layer owns DB access and authorisation.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

MIN_TITLE_LEN:       int = 1
MAX_TITLE_LEN:       int = 200
MAX_NOTE:            int = 2_000
MAX_REVIEW_NOTE:     int = 2_000
MAX_PAID_REFERENCE:  int = 120

# Canonical status vocabulary (string keys — tests don't need the SA
# enum).
STATUS_DRAFT:     str = "DRAFT"
STATUS_SUBMITTED: str = "SUBMITTED"
STATUS_APPROVED:  str = "APPROVED"
STATUS_REJECTED:  str = "REJECTED"
STATUS_PAID:      str = "PAID"

STATUSES: tuple[str, ...] = (
    STATUS_DRAFT, STATUS_SUBMITTED, STATUS_APPROVED,
    STATUS_REJECTED, STATUS_PAID,
)

# Allowed transitions. Any move NOT listed here is a 409 in the
# router. The REJECTED → DRAFT loop lets the submitter fix and
# resubmit a rejected report.
_TRANSITIONS: dict[str, frozenset[str]] = {
    STATUS_DRAFT:     frozenset({STATUS_SUBMITTED}),
    STATUS_SUBMITTED: frozenset({STATUS_APPROVED, STATUS_REJECTED}),
    STATUS_APPROVED:  frozenset({STATUS_PAID}),
    STATUS_REJECTED:  frozenset({STATUS_DRAFT}),
    STATUS_PAID:      frozenset(),  # terminal
}

# Which statuses allow mutating items (add/remove expense)?
_ITEM_MUTATION_OK: frozenset[str] = frozenset({STATUS_DRAFT})


# ── validators ─────────────────────────────────────────────────────────


def validate_title(raw: object) -> str:
    if not isinstance(raw, str):
        raise ValueError("title must be a string")
    s = raw.strip()
    if len(s) < MIN_TITLE_LEN:
        raise ValueError("title is required")
    if len(s) > MAX_TITLE_LEN:
        raise ValueError(f"title exceeds {MAX_TITLE_LEN} characters")
    return s


def validate_currency(raw: object) -> str:
    if not isinstance(raw, str):
        raise ValueError("currency must be a string")
    s = raw.strip().upper()
    if len(s) != 3 or not s.isalpha():
        raise ValueError("currency must be a 3-letter ISO code")
    return s


def _validate_optional_text(
    raw: object | None, *, label: str, limit: int,
) -> str | None:
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


def validate_note(raw: object | None) -> str | None:
    return _validate_optional_text(raw, label="note", limit=MAX_NOTE)


def validate_review_note(raw: object | None) -> str | None:
    return _validate_optional_text(
        raw, label="review_note", limit=MAX_REVIEW_NOTE,
    )


def validate_paid_reference(raw: object | None) -> str | None:
    return _validate_optional_text(
        raw, label="paid_reference", limit=MAX_PAID_REFERENCE,
    )


# ── state machine ──────────────────────────────────────────────────────


def validate_status(raw: object) -> str:
    if not isinstance(raw, str):
        raise ValueError("status must be a string")
    s = raw.strip().upper()
    if s not in STATUSES:
        raise ValueError(f"status must be one of {', '.join(STATUSES)}")
    return s


def can_transition(*, from_status: str, to_status: str) -> bool:
    """True iff ``from → to`` is a legal transition."""
    from_status = validate_status(from_status)
    to_status   = validate_status(to_status)
    return to_status in _TRANSITIONS.get(from_status, frozenset())


def assert_transition(*, from_status: str, to_status: str) -> None:
    """Raise ``ValueError`` for illegal transitions."""
    if not can_transition(from_status=from_status, to_status=to_status):
        raise ValueError(
            f"cannot transition report from {from_status} to {to_status}"
        )


def items_mutable_in(status: str) -> bool:
    """True iff adding/removing items is allowed in ``status``."""
    return validate_status(status) in _ITEM_MUTATION_OK


# ── totals ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ReportTotals:
    item_count: int
    total:      Decimal  # sum of amounts over a single currency


def compute_totals(rows: "list[Decimal]") -> ReportTotals:
    """Sum item amounts. Callers are responsible for slicing by
    currency — we don't try to cross-currency-convert here.
    """
    if not rows:
        return ReportTotals(item_count=0, total=Decimal("0.00"))
    total = Decimal("0")
    for r in rows:
        total += Decimal(str(r))
    return ReportTotals(
        item_count=len(rows),
        total=total.quantize(Decimal("0.01")),
    )
