"""Tests for customer segmentation (Item 39, v54).

Pure + contract-style (same split as Items 28-38). The 3.9 sandbox
can't import `app.models.__init__` or the router module (str | None
annotations in org / auth), so we exercise the pure engine directly
and lock the DB + router invariants via source-text reading.

Required test names (spec):

* test_auto_segment_high_value
* test_auto_segment_at_risk
* test_manual_segment_create
* test_customer_added_to_segment
* test_segment_refresh_job
* test_rule_evaluation
* test_export_segment_csv
* test_segment_count_accuracy
* test_org_isolation
* test_segment_used_in_analytics_filter
"""
from __future__ import annotations

import pathlib
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.services import segmentation_engine as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"


def _read(relpath: str) -> str:
    _p = _BACKEND_ROOT / relpath
    if _p.is_file():
        return _p.read_text()
    # Path was split into a feature package (e.g. routers/invoicing/);
    # concatenate its modules so source-string assertions still hold.
    _pkg = _p.with_suffix("")
    if _pkg.is_dir():
        return "".join(_f.read_text() for _f in sorted(_pkg.rglob("*.py")))
    return _p.read_text()


ROUTER_SRC = _read("features/customers/segments.py")
SERVICE_SRC = _read("services/segmentation_engine.py")
ANALYTICS_SRC = _read("features/analytics/analytics.py")
SCHEDULER_SRC = _read("services/scheduler.py")
MODEL_SRC = _read("features/customers/segments_models.py")
MIGRATION_SRC = (
    _BACKEND_ROOT.parent
    / "migrations"
    / "versions"
    / "f1a2b3c4d5e6_v54_segments.py"
).read_text()


NOW = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def _metrics(
    *,
    ltv=Decimal("0"),
    order_count=0,
    last_days_ago=None,
    first_days_ago=None,
    customer_id=None,
) -> svc.CustomerMetrics:
    return svc.CustomerMetrics(
        customer_id=customer_id or uuid.uuid4(),
        ltv=ltv,
        order_count=order_count,
        last_purchase_at=None if last_days_ago is None else NOW - timedelta(days=last_days_ago),
        first_purchase_at=None if first_days_ago is None else NOW - timedelta(days=first_days_ago),
    )


# ═══════════════════════════════════════════════════════════════════
# 1. test_auto_segment_high_value
# ═══════════════════════════════════════════════════════════════════


def test_auto_segment_high_value():
    rules = {"kind": "AUTO_HIGH_VALUE"}
    # Default threshold is 50_000 SEK LTV.
    assert svc.evaluate_rule(_metrics(ltv=Decimal("50000")), rules, NOW)
    assert svc.evaluate_rule(_metrics(ltv=Decimal("75000")), rules, NOW)
    assert not svc.evaluate_rule(_metrics(ltv=Decimal("49999.99")), rules, NOW)
    # Zero-LTV customer never qualifies.
    assert not svc.evaluate_rule(_metrics(), rules, NOW)

    # Override threshold via rule payload.
    hi = {"kind": "AUTO_HIGH_VALUE", "thresholds": {"high_value_ltv_sek": 200_000}}
    assert not svc.evaluate_rule(_metrics(ltv=Decimal("100000")), hi, NOW)
    assert svc.evaluate_rule(_metrics(ltv=Decimal("200000")), hi, NOW)


# ═══════════════════════════════════════════════════════════════════
# 2. test_auto_segment_at_risk
# ═══════════════════════════════════════════════════════════════════


def test_auto_segment_at_risk():
    rules = {"kind": "AUTO_AT_RISK"}
    # Repeat customer who hasn't purchased in 100 days → at risk
    # (default window 90 ≤ days < 180).
    m = _metrics(order_count=3, last_days_ago=100, first_days_ago=400)
    assert svc.evaluate_rule(m, rules, NOW)

    # Too recent — not at risk.
    m2 = _metrics(order_count=3, last_days_ago=30, first_days_ago=400)
    assert not svc.evaluate_rule(m2, rules, NOW)

    # Lapsed past 180 days — belongs to INACTIVE, NOT at-risk.
    m3 = _metrics(order_count=3, last_days_ago=200, first_days_ago=400)
    assert not svc.evaluate_rule(m3, rules, NOW)
    assert svc.evaluate_rule(m3, {"kind": "AUTO_INACTIVE"}, NOW)

    # Single-order customer never qualifies for AT_RISK.
    m4 = _metrics(order_count=1, last_days_ago=100, first_days_ago=100)
    assert not svc.evaluate_rule(m4, rules, NOW)

    # Zero-purchase customer (no last_purchase_at) never qualifies.
    assert not svc.evaluate_rule(_metrics(), rules, NOW)


# ═══════════════════════════════════════════════════════════════════
# 3. test_manual_segment_create
# ═══════════════════════════════════════════════════════════════════


def test_manual_segment_create():
    # Router creates MANUAL segments with rules={} and doesn't refresh.
    assert "SegmentCreateIn" in ROUTER_SRC
    assert "type: SegmentType" in ROUTER_SRC
    # Initial compute only runs for AUTO.
    assert "if seg.type == SegmentType.AUTO:" in ROUTER_SRC
    # Audit on create.
    assert 'action="segment.created"' in ROUTER_SRC
    # Name uniqueness enforced (ConflictError on duplicate).
    assert 'detail="segment_name_taken"' in ROUTER_SRC
    # Manual-only guard: add/remove member endpoints reject AUTO.
    assert "cannot_manually_edit_auto_segment" in ROUTER_SRC

    # Model + migration enforce uq_segments_org_name.
    assert 'uq_segments_org_name' in MODEL_SRC
    assert 'uq_segments_org_name' in MIGRATION_SRC

    # SegmentType enum complete.
    assert svc.AutoKind.HIGH_VALUE.value == "AUTO_HIGH_VALUE"
    assert svc.AutoKind.VIP.value == "AUTO_VIP"


# ═══════════════════════════════════════════════════════════════════
# 4. test_customer_added_to_segment
# ═══════════════════════════════════════════════════════════════════


def test_customer_added_to_segment():
    # Router POST /{id}/members audits + enforces MANUAL + idempotency.
    assert 'action="segment.member_added"' in ROUTER_SRC
    assert 'action="segment.member_removed"' in ROUTER_SRC
    # Customer must belong to same org (404 otherwise).
    assert 'detail="customer_not_found"' in ROUTER_SRC
    # Duplicate POST is a no-op (not a 409) — idempotent add.
    assert "if existing is None:" in ROUTER_SRC

    # Delete member increments audit + decrements count.
    assert "seg.customer_count = max(0, (seg.customer_count or 0) - 1)" in ROUTER_SRC

    # DB uniqueness prevents a race inserting twice.
    assert "uq_segment_members_segment_customer" in MIGRATION_SRC


# ═══════════════════════════════════════════════════════════════════
# 5. test_segment_refresh_job
# ═══════════════════════════════════════════════════════════════════


def test_segment_refresh_job():
    # Scheduler wires a segment_refresh job with its own lock.
    assert "_LOCK_SEGMENT_REFRESH" in SCHEDULER_SRC
    assert 'id="segment_refresh"' in SCHEDULER_SRC
    assert "_segment_refresh_sweep" in SCHEDULER_SRC
    # Cron trigger fires nightly (03:30 Stockholm).
    assert (
        'CronTrigger(hour=3, minute=30, timezone="Europe/Stockholm")'
        in SCHEDULER_SRC
    )
    # The sweep delegates to the service's refresh-all helper.
    assert "refresh_all_auto_segments" in SCHEDULER_SRC

    # Service exposes the three recompute helpers.
    assert "async def refresh_segment" in SERVICE_SRC
    assert "async def refresh_all_auto_segments" in SERVICE_SRC
    assert "async def compute_customer_metrics" in SERVICE_SRC

    # Router manual-refresh endpoint also audits.
    assert 'action="segment.refreshed"' in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 6. test_rule_evaluation
# ═══════════════════════════════════════════════════════════════════


def test_rule_evaluation():
    # Generic all/any predicates.
    rules_all = {
        "all": [
            {"field": "ltv", "op": "gte", "value": 1000},
            {"field": "order_count", "op": "gt", "value": 2},
        ]
    }
    assert svc.evaluate_rule(_metrics(ltv=Decimal("2000"), order_count=3), rules_all, NOW)
    assert not svc.evaluate_rule(_metrics(ltv=Decimal("2000"), order_count=1), rules_all, NOW)
    assert not svc.evaluate_rule(_metrics(ltv=Decimal("500"), order_count=5), rules_all, NOW)

    rules_any = {
        "any": [
            {"field": "ltv", "op": "gte", "value": 100_000},
            {"field": "order_count", "op": "gte", "value": 50},
        ]
    }
    assert svc.evaluate_rule(_metrics(ltv=Decimal("100000")), rules_any, NOW)
    assert svc.evaluate_rule(_metrics(order_count=50), rules_any, NOW)
    assert not svc.evaluate_rule(_metrics(ltv=Decimal("1"), order_count=1), rules_any, NOW)

    # All operators honoured.
    for op, expected in [
        ("eq", True), ("ne", False),
        ("gt", False), ("gte", True),
        ("lt", False), ("lte", True),
    ]:
        assert svc.evaluate_rule(
            _metrics(order_count=5),
            {"all": [{"field": "order_count", "op": op, "value": 5}]},
            NOW,
        ) == expected, f"op={op} failed"

    # Validation rejects malformed rules.
    with pytest.raises(ValueError, match="bad_rule_field"):
        svc.validate_rules({"all": [{"field": "not_a_field", "op": "eq", "value": 1}]})
    with pytest.raises(ValueError, match="bad_rule_op"):
        svc.validate_rules({"all": [{"field": "ltv", "op": "bogus", "value": 1}]})
    with pytest.raises(ValueError, match="rule_missing_key"):
        svc.validate_rules({"all": [{"field": "ltv", "op": "gte"}]})
    with pytest.raises(ValueError, match="unknown_auto_kind"):
        svc.validate_rules({"kind": "AUTO_MADE_UP"})
    with pytest.raises(ValueError, match="rules_not_object"):
        svc.validate_rules([])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="bad_rule_value"):
        svc.validate_rules({"all": [{"field": "ltv", "op": "gte", "value": "xx"}]})

    # Empty object = no match (safe default).
    assert not svc.evaluate_rule(_metrics(ltv=Decimal("10000000")), {}, NOW)


# ═══════════════════════════════════════════════════════════════════
# 7. test_export_segment_csv
# ═══════════════════════════════════════════════════════════════════


def test_export_segment_csv():
    # Header-only for empty.
    empty = svc.build_segment_csv([])
    assert empty.strip() == "customer_id,company_name,email"

    # Proper quoting for names that contain commas / quotes / newlines.
    rows = [
        ("abc", "Acme AB", "ops@acme.se"),
        ("def", 'Söder, "Inc"', ""),
        ("ghi", "Line1\nLine2", "x@y.z"),
    ]
    body = svc.build_segment_csv(rows)
    import csv, io
    parsed = list(csv.reader(io.StringIO(body)))
    assert parsed[0] == ["customer_id", "company_name", "email"]
    assert parsed[1] == ["abc", "Acme AB", "ops@acme.se"]
    assert parsed[2] == ["def", 'Söder, "Inc"', ""]
    assert parsed[3] == ["ghi", "Line1\nLine2", "x@y.z"]

    # Router endpoint streams the same helper + audits + sets filename.
    assert "export_segment_csv" in ROUTER_SRC
    assert "build_segment_csv" in ROUTER_SRC
    assert 'media_type="text/csv; charset=utf-8"' in ROUTER_SRC
    assert "Content-Disposition" in ROUTER_SRC
    assert 'action="segment.exported"' in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 8. test_segment_count_accuracy
# ═══════════════════════════════════════════════════════════════════


def test_segment_count_accuracy():
    # select_members returns only matching customers.
    metrics = [
        _metrics(ltv=Decimal("100000"), customer_id=uuid.uuid4()),
        _metrics(ltv=Decimal("10000"), customer_id=uuid.uuid4()),
        _metrics(ltv=Decimal("75000"), customer_id=uuid.uuid4()),
    ]
    ids = svc.select_members(metrics, {"kind": "AUTO_HIGH_VALUE"}, NOW)
    assert len(ids) == 2  # 100k + 75k — 10k below threshold

    # Deterministic ordering (sorted by id stringification).
    assert ids == sorted(ids, key=str)

    # VIP: either-or semantics — customers who satisfy one branch count once.
    m_big_ltv = _metrics(ltv=Decimal("200000"), order_count=1, customer_id=uuid.uuid4())
    m_many_orders = _metrics(ltv=Decimal("1"), order_count=30, customer_id=uuid.uuid4())
    m_neither = _metrics(ltv=Decimal("1"), order_count=1, customer_id=uuid.uuid4())
    ids = svc.select_members(
        [m_big_ltv, m_many_orders, m_neither], {"kind": "AUTO_VIP"}, NOW,
    )
    assert set(ids) == {m_big_ltv.customer_id, m_many_orders.customer_id}

    # Refresh helper updates customer_count + last_computed_at.
    assert "segment.customer_count = len(member_ids)" in SERVICE_SRC
    assert "segment.last_computed_at = moment" in SERVICE_SRC

    # Router refresh endpoint calls through.
    assert "await svc.refresh_segment(db, seg)" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 9. test_org_isolation
# ═══════════════════════════════════════════════════════════════════


def test_org_isolation():
    # Router always filters by org_id before touching a segment.
    assert ROUTER_SRC.count("Segment.org_id == org_id") >= 1
    assert "_load_segment" in ROUTER_SRC
    # Segment id alone never returns a row — the helper raises 404 when
    # the (id, org) tuple misses.
    assert 'detail="segment_not_found"' in ROUTER_SRC

    # Service helpers also join on org_id for the analytics-filter path.
    assert "Segment.org_id == org_id" in SERVICE_SRC
    assert "async def list_segment_customer_ids" in SERVICE_SRC

    # Migration enforces CASCADE on org deletion so orphan segments
    # can't linger after a tenant purge.
    assert 'ForeignKey("organizations.id", ondelete="CASCADE")' in MIGRATION_SRC
    # CASCADE on customer deletion so a deleted customer drops out of
    # every segment automatically.
    assert 'ForeignKey("customers.id", ondelete="CASCADE")' in MIGRATION_SRC


# ═══════════════════════════════════════════════════════════════════
# 10. test_segment_used_in_analytics_filter
# ═══════════════════════════════════════════════════════════════════


def test_segment_used_in_analytics_filter():
    # /api/analytics/overview accepts an optional ?segment_id=.
    assert "segment_id: uuid.UUID | None = Query" in ANALYTICS_SRC
    # Overview resolves it via the service helper (enforces org scope).
    assert "list_segment_customer_ids" in ANALYTICS_SRC
    # Aggregates narrow on customer_id IN the segment list.
    assert "Invoice.customer_id.in_(segment_customer_ids)" in ANALYTICS_SRC
    # Empty segment short-circuits with an impossible id (doesn't break the planner).
    assert "00000000-0000-0000-0000-000000000000" in ANALYTICS_SRC


# ═══════════════════════════════════════════════════════════════════
# Additional invariants
# ═══════════════════════════════════════════════════════════════════


def test_migration_v54_shape():
    assert 'revision = "f1a2b3c4d5e6"' in MIGRATION_SRC
    assert 'down_revision = "e1f2a3b4c5d6"' in MIGRATION_SRC
    assert 'op.create_table(\n        "segments"' in MIGRATION_SRC
    assert 'op.create_table(\n        "segment_members"' in MIGRATION_SRC
    assert 'SEGMENT_TYPE_ENUM_NAME = "segment_type"' in MIGRATION_SRC
    # Indexes land.
    assert "ix_segments_org_type" in MIGRATION_SRC
    assert "ix_segment_members_segment" in MIGRATION_SRC
    assert "ix_segment_members_customer" in MIGRATION_SRC
    # Enum dropped explicitly on downgrade.
    assert 'sa.Enum(name=SEGMENT_TYPE_ENUM_NAME).drop' in MIGRATION_SRC


def test_auto_kind_definitions():
    for kind in svc.AutoKind:
        # Every AutoKind expands to a well-formed generic rule.
        expanded = svc._expand_auto_kind(kind.value, {})
        svc.validate_rules(expanded)

    # All 5 kinds from the spec are present.
    names = {k.value for k in svc.AutoKind}
    assert names == {
        "AUTO_HIGH_VALUE", "AUTO_AT_RISK",
        "AUTO_NEW", "AUTO_INACTIVE", "AUTO_VIP",
    }


def test_auto_segment_new_and_inactive():
    # NEW: has purchased at least once within the last 30 days.
    rules = {"kind": "AUTO_NEW"}
    assert svc.evaluate_rule(_metrics(order_count=1, first_days_ago=5), rules, NOW)
    assert not svc.evaluate_rule(_metrics(order_count=1, first_days_ago=90), rules, NOW)
    assert not svc.evaluate_rule(_metrics(), rules, NOW)

    # INACTIVE: last purchase ≥ 180 days ago.
    inactive = {"kind": "AUTO_INACTIVE"}
    assert svc.evaluate_rule(
        _metrics(order_count=3, last_days_ago=200), inactive, NOW,
    )
    assert not svc.evaluate_rule(
        _metrics(order_count=3, last_days_ago=30), inactive, NOW,
    )


def test_days_since_helpers_return_nonneg():
    m = _metrics(last_days_ago=10)
    assert m.days_since_last_purchase(NOW) == 10
    # "now" before last_purchase_at (clock skew) clamps to 0 rather
    # than surfacing a negative age.
    past = NOW - timedelta(days=30)
    assert m.days_since_last_purchase(past) == 0
