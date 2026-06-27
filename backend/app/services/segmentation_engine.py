"""Customer segmentation engine (Item 39, v54).

Pure + DB-bound split (same pattern as Items 30-38).

Pure layer
----------
* :class:`CustomerMetrics` — per-customer roll-up the rules evaluate
  against. Built once from SQL aggregates, then reused across every
  auto-segment so a refresh sweep of 50 segments is still O(customers)
  not O(customers × segments).
* :data:`BUILTIN_KINDS` — named auto-segment kinds. Each entry is a
  ``RuleSpec`` that maps a single JSON ``{"kind": "AUTO_HIGH_VALUE"}``
  blob to the same field/op/value structure as a custom rule — keeping
  one code path for both built-in and user-authored rules.
* :func:`evaluate_rule` — evaluates a rule payload (``{"all": [...]}``
  / ``{"any": [...]}`` / ``{"kind": "AUTO_*"}``) against a
  ``CustomerMetrics`` instance. Returns ``True`` iff the customer
  belongs in the segment.
* :func:`select_members` — runs ``evaluate_rule`` across a metrics
  list and returns the set of matching customer ids.

DB layer
--------
Lazy-imports the ORM models so the pure tests never need a database
connection. The scheduler + router invoke:

* :func:`compute_customer_metrics` — one-shot per-org roll-up
  (LTV, order count, first/last purchase).
* :func:`refresh_segment` — recomputes an AUTO segment's membership
  via SQL ``DELETE + INSERT``. Returns the new row count.
* :func:`refresh_all_auto_segments` — refresh every AUTO segment
  for an org (used by the router's refresh-all endpoint and by the
  nightly scheduler sweep).

Default thresholds tuned for small Swedish SMBs (< €500k ARR); owners
can override via the rules JSON.
"""
from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable


# ═══════════════════════════════════════════════════════════════════
# Thresholds + metric shape (pure)
# ═══════════════════════════════════════════════════════════════════


# Default thresholds for the named auto-segments. Each threshold is
# overridable via the segment's ``rules["thresholds"]`` dict so an
# owner can say "treat anyone over 200k SEK as high value" without
# writing a custom rule.
DEFAULT_THRESHOLDS: dict[str, Any] = {
    "high_value_ltv_sek": 50_000,
    "vip_ltv_sek": 100_000,
    "vip_order_count": 20,
    "new_days": 30,
    "at_risk_days": 90,
    "inactive_days": 180,
}


@dataclass
class CustomerMetrics:
    """Per-customer roll-up the rule engine evaluates against.

    Built once per refresh sweep from a single ``GROUP BY`` query
    over paid invoices so segment evaluation is O(customers), not
    O(customers × rules).
    """
    customer_id: uuid.UUID
    # Lifetime-value in the org's base currency, snapshot-normalised
    # via the invoice-time exchange rate.
    ltv: Decimal = Decimal("0")
    order_count: int = 0
    first_purchase_at: datetime | None = None
    last_purchase_at: datetime | None = None
    created_at: datetime | None = None

    def days_since_last_purchase(self, now: datetime) -> int | None:
        if self.last_purchase_at is None:
            return None
        return max(0, (now - self.last_purchase_at).days)

    def days_since_first_purchase(self, now: datetime) -> int | None:
        if self.first_purchase_at is None:
            return None
        return max(0, (now - self.first_purchase_at).days)


# ═══════════════════════════════════════════════════════════════════
# Rule evaluation (pure)
# ═══════════════════════════════════════════════════════════════════


class AutoKind(str, enum.Enum):
    """Named auto-segment kinds. Selecting a kind is equivalent to
    filling in a specific rule payload — the engine normalises both
    paths to the same underlying ``compare(field, op, value)`` calls."""
    HIGH_VALUE = "AUTO_HIGH_VALUE"
    AT_RISK = "AUTO_AT_RISK"
    NEW = "AUTO_NEW"
    INACTIVE = "AUTO_INACTIVE"
    VIP = "AUTO_VIP"


_ALLOWED_FIELDS = {
    "ltv",
    "order_count",
    "days_since_last_purchase",
    "days_since_first_purchase",
}

_ALLOWED_OPS = {"eq", "ne", "gt", "gte", "lt", "lte"}


def _coerce_number(value: Any) -> Decimal:
    """Parse a rule's comparison literal into :class:`Decimal`.

    Rejects non-numeric inputs up-front so a malformed rule returns a
    400 at creation time rather than silently excluding every customer
    from the segment.
    """
    try:
        return Decimal(str(value))
    except Exception as exc:  # noqa: BLE001 — surface as caller-visible ValueError
        raise ValueError(f"bad_rule_value:{value!r}") from exc


def _field_value(metrics: CustomerMetrics, field_name: str, now: datetime) -> Decimal | None:
    if field_name == "ltv":
        return Decimal(metrics.ltv)
    if field_name == "order_count":
        return Decimal(metrics.order_count)
    if field_name == "days_since_last_purchase":
        d = metrics.days_since_last_purchase(now)
        return None if d is None else Decimal(d)
    if field_name == "days_since_first_purchase":
        d = metrics.days_since_first_purchase(now)
        return None if d is None else Decimal(d)
    raise ValueError(f"bad_rule_field:{field_name}")


def _compare(actual: Decimal | None, op: str, expected: Decimal) -> bool:
    """Apply a comparison, treating ``None`` as "never satisfies" so a
    customer with no purchases can never match a ``days_since_*`` rule
    (they haven't *done* anything — they're not "at risk", they're
    brand new with zero orders)."""
    if actual is None:
        return False
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "gt":
        return actual > expected
    if op == "gte":
        return actual >= expected
    if op == "lt":
        return actual < expected
    if op == "lte":
        return actual <= expected
    raise ValueError(f"bad_rule_op:{op}")


def _validate_predicate(pred: dict[str, Any]) -> None:
    for key in ("field", "op", "value"):
        if key not in pred:
            raise ValueError(f"rule_missing_key:{key}")
    if pred["field"] not in _ALLOWED_FIELDS:
        raise ValueError(f"bad_rule_field:{pred['field']}")
    if pred["op"] not in _ALLOWED_OPS:
        raise ValueError(f"bad_rule_op:{pred['op']}")
    _coerce_number(pred["value"])


def _expand_auto_kind(
    kind: str, thresholds: dict[str, Any],
) -> dict[str, Any]:
    """Translate ``{"kind": "AUTO_*"}`` into the generic
    ``{"all": [{"field": ..., "op": ..., "value": ...}]}`` shape."""
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    if kind == AutoKind.HIGH_VALUE.value:
        return {"all": [
            {"field": "ltv", "op": "gte", "value": t["high_value_ltv_sek"]},
        ]}
    if kind == AutoKind.AT_RISK.value:
        # A customer counts as at-risk only if they HAVE purchased at
        # least twice before (i.e. they were a repeat customer) AND
        # their last purchase was between at_risk_days and inactive_days
        # ago. Customers who have been dark longer than inactive_days
        # belong to INACTIVE, not AT_RISK, so the two segments do not
        # overlap for the typical threshold pair 90/180.
        return {"all": [
            {"field": "order_count", "op": "gte", "value": 2},
            {"field": "days_since_last_purchase", "op": "gte", "value": t["at_risk_days"]},
            {"field": "days_since_last_purchase", "op": "lt", "value": t["inactive_days"]},
        ]}
    if kind == AutoKind.NEW.value:
        return {"all": [
            {"field": "order_count", "op": "gte", "value": 1},
            {"field": "days_since_first_purchase", "op": "lte", "value": t["new_days"]},
        ]}
    if kind == AutoKind.INACTIVE.value:
        return {"all": [
            {"field": "days_since_last_purchase", "op": "gte", "value": t["inactive_days"]},
        ]}
    if kind == AutoKind.VIP.value:
        # VIP = either very-high LTV OR very-many orders. Either
        # alone qualifies (e.g. a wholesale account that places ~5
        # huge orders a year qualifies on LTV; a subscription
        # customer that pays small amounts monthly qualifies on
        # order count).
        return {"any": [
            {"field": "ltv", "op": "gte", "value": t["vip_ltv_sek"]},
            {"field": "order_count", "op": "gte", "value": t["vip_order_count"]},
        ]}
    raise ValueError(f"unknown_auto_kind:{kind}")


def validate_rules(rules: dict[str, Any]) -> dict[str, Any]:
    """Raise ``ValueError`` on a malformed payload.

    Accepted shapes:

    * ``{"kind": "AUTO_*", "thresholds": {...}}`` — named auto kind.
    * ``{"all": [predicate, ...]}`` — every predicate must match.
    * ``{"any": [predicate, ...]}`` — at least one predicate matches.
    * ``{}`` — matches no-one (typical for a fresh MANUAL segment).

    Returns the input unchanged on success so a caller can chain the
    call: ``segment.rules = validate_rules(body.rules)``.
    """
    if not isinstance(rules, dict):
        raise ValueError("rules_not_object")
    if "kind" in rules:
        _expand_auto_kind(str(rules["kind"]), rules.get("thresholds") or {})
        return rules
    for group in ("all", "any"):
        if group in rules:
            preds = rules[group]
            if not isinstance(preds, list):
                raise ValueError(f"rules_{group}_not_list")
            for p in preds:
                if not isinstance(p, dict):
                    raise ValueError(f"rules_{group}_predicate_not_object")
                _validate_predicate(p)
    return rules


def evaluate_rule(
    metrics: CustomerMetrics,
    rules: dict[str, Any],
    now: datetime,
) -> bool:
    """Return True if ``metrics`` satisfies ``rules`` at ``now``."""
    # Empty object / None = never match (safe default for a new MANUAL).
    if not rules:
        return False
    if "kind" in rules:
        expanded = _expand_auto_kind(
            str(rules["kind"]), rules.get("thresholds") or {},
        )
        return evaluate_rule(metrics, expanded, now)

    if "all" in rules:
        preds = rules["all"]
        return all(_eval_pred(metrics, p, now) for p in preds)
    if "any" in rules:
        preds = rules["any"]
        return any(_eval_pred(metrics, p, now) for p in preds)
    # No recognised key — treat as "never match" rather than crashing.
    return False


def _eval_pred(
    metrics: CustomerMetrics, pred: dict[str, Any], now: datetime,
) -> bool:
    actual = _field_value(metrics, str(pred["field"]), now)
    expected = _coerce_number(pred["value"])
    return _compare(actual, str(pred["op"]), expected)


def select_members(
    metrics_list: Iterable[CustomerMetrics],
    rules: dict[str, Any],
    now: datetime,
) -> list[uuid.UUID]:
    """Return the sorted list of customer ids that satisfy ``rules``."""
    validate_rules(rules)
    matches = [
        m.customer_id for m in metrics_list
        if evaluate_rule(m, rules, now)
    ]
    # Stable sort so the membership row insertion order is deterministic
    # and the CSV export rows don't bounce between refreshes.
    matches.sort(key=str)
    return matches


# ═══════════════════════════════════════════════════════════════════
# CSV export (pure)
# ═══════════════════════════════════════════════════════════════════


def build_segment_csv(rows: Iterable[tuple[str, str, str]]) -> str:
    """Render rows of ``(customer_id, company_name, email)`` as CSV.

    Uses stdlib ``csv`` to get quoting right — a company name
    containing a comma, newline, or embedded double-quote would break
    a hand-rolled format. Header is always written even for empty
    segments so the downloader can read the schema without a
    membership peek.
    """
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["customer_id", "company_name", "email"])
    for row in rows:
        writer.writerow(list(row))
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════
# DB-bound wrappers (lazy-import models)
# ═══════════════════════════════════════════════════════════════════


async def compute_customer_metrics(
    db, *, org_id: uuid.UUID,
) -> list[CustomerMetrics]:
    """One-shot per-org roll-up over PAID invoices.

    DRAFT invoices never count because they may be cancelled; SENT
    invoices may still go unpaid. Using PAID only keeps LTV honest —
    a customer that placed a large order but never paid shouldn't
    promote into HIGH_VALUE.
    """
    from sqlalchemy import func, select

    from app.models.invoicing import Customer, Invoice, InvoiceStatus

    # Pull every customer (so customers that have never purchased still
    # appear with zero metrics — the INACTIVE rule doesn't match them
    # because ``days_since_last_purchase`` is None for a no-purchase
    # customer, which ``_compare`` treats as "never satisfies").
    customers = (
        await db.execute(
            select(Customer.id, Customer.created_at).where(
                Customer.org_id == org_id,
            )
        )
    ).all()

    # Aggregate over paid invoices. Normalise via exchange_rate so a
    # mixed-currency org rolls up into its base currency.
    agg = (
        await db.execute(
            select(
                Invoice.customer_id,
                func.sum(Invoice.total_sek * Invoice.exchange_rate).label("ltv"),
                func.count(Invoice.id).label("order_count"),
                func.min(Invoice.created_at).label("first_purchase_at"),
                func.max(Invoice.created_at).label("last_purchase_at"),
            )
            .where(
                Invoice.org_id == org_id,
                Invoice.status == InvoiceStatus.PAID,
            )
            .group_by(Invoice.customer_id)
        )
    ).all()
    by_customer = {
        row.customer_id: row for row in agg
    }

    out: list[CustomerMetrics] = []
    for row in customers:
        metric_row = by_customer.get(row.id)
        if metric_row is None:
            out.append(
                CustomerMetrics(
                    customer_id=row.id,
                    created_at=row.created_at,
                )
            )
        else:
            out.append(
                CustomerMetrics(
                    customer_id=row.id,
                    ltv=Decimal(str(metric_row.ltv or 0)),
                    order_count=int(metric_row.order_count or 0),
                    first_purchase_at=metric_row.first_purchase_at,
                    last_purchase_at=metric_row.last_purchase_at,
                    created_at=row.created_at,
                )
            )
    return out


async def refresh_segment(
    db,
    segment,  # app.models.segments.Segment
    *,
    metrics: list[CustomerMetrics] | None = None,
    now: datetime | None = None,
) -> int:
    """Recompute an AUTO segment's membership and return the new count.

    MANUAL segments are a no-op (membership is operator-driven); the
    call is still safe so the scheduler can be oblivious to segment
    type.

    When ``metrics`` is passed in, the caller has already rolled them
    up for this org and we skip the aggregation query — used by the
    "refresh all" path so one query powers N segments.
    """
    from sqlalchemy import delete, select

    from app.models.segments import Segment, SegmentMember, SegmentType

    if segment.type != SegmentType.AUTO:
        return int(segment.customer_count or 0)

    if metrics is None:
        metrics = await compute_customer_metrics(db, org_id=segment.org_id)
    moment = now or now_utc()

    member_ids = select_members(metrics, segment.rules or {}, moment)

    # Atomic replace: clear previous membership first, then re-insert.
    # The UniqueConstraint(segment_id, customer_id) protects against a
    # duplicate row surviving a half-applied refresh, but we never
    # leave the segment empty mid-sweep — the delete + bulk-insert run
    # in a single transaction committed by the caller.
    await db.execute(
        delete(SegmentMember).where(SegmentMember.segment_id == segment.id)
    )
    for cid in member_ids:
        db.add(SegmentMember(segment_id=segment.id, customer_id=cid))

    segment.customer_count = len(member_ids)
    segment.last_computed_at = moment
    await db.flush()
    return len(member_ids)


async def refresh_all_auto_segments(
    db, *, org_id: uuid.UUID,
) -> int:
    """Refresh every AUTO segment for an org. Returns total-rows-recomputed."""
    from sqlalchemy import select

    from app.models.segments import Segment, SegmentType

    segments = (
        await db.execute(
            select(Segment).where(
                Segment.org_id == org_id,
                Segment.type == SegmentType.AUTO,
            )
        )
    ).scalars().all()

    if not segments:
        return 0

    metrics = await compute_customer_metrics(db, org_id=org_id)
    now = now_utc()
    total = 0
    for seg in segments:
        total += await refresh_segment(db, seg, metrics=metrics, now=now)
    return total


async def list_segment_customer_ids(
    db, *, segment_id: uuid.UUID, org_id: uuid.UUID,
) -> list[uuid.UUID]:
    """Return customer ids in a segment, guarded by org ownership."""
    from sqlalchemy import select

    from app.models.segments import Segment, SegmentMember

    rows = await db.execute(
        select(SegmentMember.customer_id)
        .join(Segment, Segment.id == SegmentMember.segment_id)
        .where(
            Segment.org_id == org_id,
            SegmentMember.segment_id == segment_id,
        )
    )
    return [r[0] for r in rows.all()]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
