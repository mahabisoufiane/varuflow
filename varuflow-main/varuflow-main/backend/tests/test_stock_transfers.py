"""Tests for multi-location stock transfers (Item 38, v53).

Pure + contract-style. The 3.9 sandbox can't import router / model /
email modules (they use ``str | None`` annotations in other modules
on the import chain), so we exercise the pure service directly and
lock router / model / migration invariants via source-text reading.

Required test names (spec):

* ``test_create_transfer``
* ``test_stock_deducted_on_ship``
* ``test_stock_added_on_receipt``
* ``test_partial_receipt``
* ``test_cancel_transfer``
* ``test_transfer_history``
* ``test_org_isolation``
* ``test_transfer_email_notification``
* ``test_batch_transfer_support``
* ``test_audit_log_entries``
"""
from __future__ import annotations

import pathlib
import uuid
from datetime import datetime, timezone

import pytest

from app.services import stock_transfer_service as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"


def _read(relpath: str) -> str:
    return (_BACKEND_ROOT / relpath).read_text()


ROUTER_SRC = _read("routers/stock_transfers.py")
SERVICE_SRC = _read("services/stock_transfer_service.py")
EMAIL_SRC = _read("services/email.py")
MODEL_SRC = _read("models/stock_transfers.py")
MIGRATION_SRC = (
    _BACKEND_ROOT.parent
    / "migrations"
    / "versions"
    / "e1f2a3b4c5d6_v53_stock_transfers.py"
).read_text()


NOW = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _line_view(
    product_id=None,
    *,
    batch_id=None,
    requested=10,
    shipped=0,
    received=0,
) -> svc.LineView:
    return svc.LineView(
        product_id=product_id or _uuid(),
        batch_id=batch_id,
        qty_requested=requested,
        qty_shipped=shipped,
        qty_received=received,
    )


# ═══════════════════════════════════════════════════════════════════
# 1. test_create_transfer  —  draft validation + dedup + status
# ═══════════════════════════════════════════════════════════════════


def test_create_transfer():
    wh_from, wh_to = _uuid(), _uuid()
    p1, p2 = _uuid(), _uuid()
    lines = [
        {"product_id": p1, "qty_requested": 5},
        {"product_id": p2, "qty_requested": 3},
    ]
    drafts = svc.validate_transfer_draft(wh_from, wh_to, lines)
    assert len(drafts) == 2
    assert {d.product_id for d in drafts} == {p1, p2}
    assert all(d.qty_requested > 0 for d in drafts)

    # Same warehouse → 400-equivalent.
    with pytest.raises(ValueError, match="same_warehouse_transfer"):
        svc.validate_transfer_draft(wh_from, wh_from, lines)

    # Empty list.
    with pytest.raises(ValueError, match="no_lines"):
        svc.validate_transfer_draft(wh_from, wh_to, [])

    # Zero qty.
    with pytest.raises(ValueError, match="qty_must_be_positive"):
        svc.validate_transfer_draft(
            wh_from, wh_to,
            [{"product_id": p1, "qty_requested": 0}],
        )

    # Missing product id.
    with pytest.raises(ValueError, match="missing_product_id"):
        svc.validate_transfer_draft(
            wh_from, wh_to, [{"qty_requested": 1}],
        )

    # Bad UUID.
    with pytest.raises(ValueError, match="bad_uuid:product_id"):
        svc.validate_transfer_draft(
            wh_from, wh_to,
            [{"product_id": "not-a-uuid", "qty_requested": 1}],
        )

    # Duplicate (product, batch) rows are merged.
    merged = svc.validate_transfer_draft(
        wh_from, wh_to,
        [
            {"product_id": p1, "qty_requested": 4},
            {"product_id": p1, "qty_requested": 6},
        ],
    )
    assert len(merged) == 1
    assert merged[0].qty_requested == 10

    # Router creates DRAFT, calls validate + logs + commits.
    assert "StockTransferStatus.DRAFT" in ROUTER_SRC
    assert "validate_transfer_draft" in ROUTER_SRC
    assert 'action="stock_transfer.created"' in ROUTER_SRC
    assert "status_code=201" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 2. test_stock_deducted_on_ship
# ═══════════════════════════════════════════════════════════════════


def test_stock_deducted_on_ship():
    # Compute ship qty: default = requested; overrides honoured.
    p1 = _uuid()
    lines = [_line_view(product_id=p1, requested=10)]
    qty = svc.compute_ship_quantities(lines)
    assert qty[p1] == 10

    qty = svc.compute_ship_quantities(lines, overrides={p1: 7})
    assert qty[p1] == 7

    with pytest.raises(ValueError, match="ship_qty_negative"):
        svc.compute_ship_quantities(lines, overrides={p1: -1})

    with pytest.raises(ValueError, match="ship_qty_exceeds_requested"):
        svc.compute_ship_quantities(lines, overrides={p1: 11})

    # Transition check: DRAFT → IN_TRANSIT is legal, IN_TRANSIT → IN_TRANSIT is not.
    svc.assert_can_transition(svc.TransferStatus.DRAFT, svc.TransferStatus.IN_TRANSIT)
    with pytest.raises(ValueError, match="invalid_transition"):
        svc.assert_can_transition(
            svc.TransferStatus.IN_TRANSIT, svc.TransferStatus.IN_TRANSIT,
        )

    # Router writes an OUT movement against the FROM warehouse and
    # decrements stock via adjust_stock_level with a NEGATIVE delta.
    assert "StockMovementType.OUT" in ROUTER_SRC
    assert "delta=-shipped" in ROUTER_SRC
    assert "transfer.from_warehouse_id" in ROUTER_SRC
    assert "StockTransferStatus.IN_TRANSIT" in ROUTER_SRC
    assert "transfer.shipped_at" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 3. test_stock_added_on_receipt
# ═══════════════════════════════════════════════════════════════════


def test_stock_added_on_receipt():
    p1, p2 = _uuid(), _uuid()
    lines = [
        _line_view(product_id=p1, requested=10, shipped=10, received=0),
        _line_view(product_id=p2, requested=5, shipped=5, received=0),
    ]
    deltas = svc.compute_receive_quantities(lines, {p1: 10, p2: 5})
    assert deltas == {p1: 10, p2: 5}

    # Status fully closes.
    hydrated = [
        svc.LineView(p1, None, 10, 10, 10),
        svc.LineView(p2, None, 5, 5, 5),
    ]
    assert svc.status_after_receipt(hydrated) == svc.TransferStatus.RECEIVED

    # Unknown product rejected.
    with pytest.raises(ValueError, match="unknown_line_for_receipt"):
        svc.compute_receive_quantities(lines, {_uuid(): 1})

    # Over-receipt rejected.
    with pytest.raises(ValueError, match="receive_qty_exceeds_shipped"):
        svc.compute_receive_quantities(lines, {p1: 11})

    # Negative delta rejected.
    with pytest.raises(ValueError, match="receive_qty_negative"):
        svc.compute_receive_quantities(lines, {p1: -1})

    # Router uses IN movement against the TO warehouse with POSITIVE delta.
    assert "StockMovementType.IN" in ROUTER_SRC
    assert "delta=+delta" in ROUTER_SRC
    assert "transfer.to_warehouse_id" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 4. test_partial_receipt
# ═══════════════════════════════════════════════════════════════════


def test_partial_receipt():
    p1, p2 = _uuid(), _uuid()
    # Shipped 10+5, receive only 7+0 first pass.
    first = [
        svc.LineView(p1, None, 10, 10, 7),
        svc.LineView(p2, None, 5, 5, 0),
    ]
    assert svc.status_after_receipt(first) == svc.TransferStatus.PARTIAL

    # Router must allow PARTIAL → PARTIAL (follow-up receipts) and
    # PARTIAL → RECEIVED (closing receipt).
    svc.assert_can_transition(svc.TransferStatus.PARTIAL, svc.TransferStatus.PARTIAL)
    svc.assert_can_transition(svc.TransferStatus.PARTIAL, svc.TransferStatus.RECEIVED)
    with pytest.raises(ValueError):
        svc.assert_can_transition(
            svc.TransferStatus.PARTIAL, svc.TransferStatus.CANCELLED,
        )

    # Second pass closes it out.
    second_deltas = svc.compute_receive_quantities(first, {p1: 3, p2: 5})
    assert second_deltas == {p1: 3, p2: 5}
    closed = [
        svc.LineView(p1, None, 10, 10, 10),
        svc.LineView(p2, None, 5, 5, 5),
    ]
    assert svc.status_after_receipt(closed) == svc.TransferStatus.RECEIVED
    assert svc.is_terminal(svc.TransferStatus.RECEIVED)
    assert not svc.is_terminal(svc.TransferStatus.PARTIAL)

    # Router receive endpoint computes status via status_after_receipt.
    assert "status_after_receipt" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 5. test_cancel_transfer
# ═══════════════════════════════════════════════════════════════════


def test_cancel_transfer():
    # Only DRAFT → CANCELLED allowed; IN_TRANSIT can't be cancelled.
    svc.assert_can_transition(svc.TransferStatus.DRAFT, svc.TransferStatus.CANCELLED)
    with pytest.raises(ValueError, match="invalid_transition"):
        svc.assert_can_transition(
            svc.TransferStatus.IN_TRANSIT, svc.TransferStatus.CANCELLED,
        )
    with pytest.raises(ValueError, match="invalid_transition"):
        svc.assert_can_transition(
            svc.TransferStatus.RECEIVED, svc.TransferStatus.CANCELLED,
        )
    with pytest.raises(ValueError, match="invalid_transition"):
        svc.assert_can_transition(
            svc.TransferStatus.PARTIAL, svc.TransferStatus.CANCELLED,
        )
    assert svc.is_terminal(svc.TransferStatus.CANCELLED)

    # Router cancel endpoint sets CANCELLED + cancelled_at + logs action.
    assert "StockTransferStatus.CANCELLED" in ROUTER_SRC
    assert "transfer.cancelled_at" in ROUTER_SRC
    assert 'action="stock_transfer.cancelled"' in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 6. test_transfer_history
# ═══════════════════════════════════════════════════════════════════


def test_transfer_history():
    # Summarise builds a history row shape.
    p1, p2 = _uuid(), _uuid()
    wh_from, wh_to = _uuid(), _uuid()
    lines = [
        svc.LineView(p1, None, 10, 10, 10),
        svc.LineView(p2, None, 5, 5, 3),
    ]
    s = svc.summarise(
        _uuid(),
        svc.TransferStatus.PARTIAL,
        wh_from, wh_to, NOW, lines,
    )
    assert s.line_count == 2
    assert s.total_requested == 15
    assert s.total_received == 13
    assert s.from_warehouse_id == wh_from
    assert s.to_warehouse_id == wh_to
    assert s.status == svc.TransferStatus.PARTIAL

    # list_transfers defined with status + warehouse filters.
    assert "async def list_transfers" in SERVICE_SRC
    assert "StockTransfer.from_warehouse_id == warehouse_id" in SERVICE_SRC
    assert "StockTransfer.to_warehouse_id == warehouse_id" in SERVICE_SRC
    assert ".order_by(StockTransfer.created_at.desc())" in SERVICE_SRC

    # Router list endpoint exposes both filters.
    assert 'alias="status"' in ROUTER_SRC
    assert "warehouse_id: uuid.UUID | None = Query(None)" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 7. test_org_isolation
# ═══════════════════════════════════════════════════════════════════


def test_org_isolation():
    # load_transfer / list_transfers / load_warehouses all filter on org_id.
    assert "StockTransfer.org_id == org_id" in SERVICE_SRC
    assert "Warehouse.org_id == org_id" in SERVICE_SRC

    # Router never queries without org_id (both read + write endpoints go
    # through the service helpers, which encode the filter).
    for fn in ("load_transfer", "list_transfers", "load_warehouses"):
        assert fn in ROUTER_SRC, f"{fn} must be called by the router"

    # Migration enforces CASCADE on org deletion so orphan rows can't
    # hang around after a tenant is purged.
    assert 'ForeignKey("organizations.id", ondelete="CASCADE")' in MIGRATION_SRC

    # Ownership guard: 404 / 409 surface cleanly rather than leaking
    # cross-org data through a generic 500.
    assert "transfer_not_found" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 8. test_transfer_email_notification
# ═══════════════════════════════════════════════════════════════════


def test_transfer_email_notification():
    # Both helpers exist in the email module.
    assert "async def send_stock_transfer_request_email" in EMAIL_SRC
    assert "async def send_stock_transfer_received_email" in EMAIL_SRC

    # Both short-circuit when Resend is unconfigured — no raise, return False.
    # Each helper body starts with the standard "if not settings.RESEND_API_KEY: return False".
    req_idx = EMAIL_SRC.index("async def send_stock_transfer_request_email")
    rcv_idx = EMAIL_SRC.index("async def send_stock_transfer_received_email")
    assert "if not settings.RESEND_API_KEY" in EMAIL_SRC[req_idx:req_idx + 1200]
    assert "if not settings.RESEND_API_KEY" in EMAIL_SRC[rcv_idx:rcv_idx + 1200]

    # Router wires in both helpers on the right endpoints.
    assert "send_stock_transfer_request_email" in ROUTER_SRC
    assert "send_stock_transfer_received_email" in ROUTER_SRC
    # Email failure never rolls back the DB (wrapped in try/except).
    assert "transfer_request_email_failed" in ROUTER_SRC
    assert "transfer_received_email_failed" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 9. test_batch_transfer_support
# ═══════════════════════════════════════════════════════════════════


def test_batch_transfer_support():
    # LineDraft + LineView both carry batch_id.
    p1 = _uuid()
    b1 = _uuid()
    drafts = svc.validate_transfer_draft(
        _uuid(), _uuid(),
        [{"product_id": p1, "qty_requested": 4, "batch_id": b1}],
    )
    assert drafts[0].batch_id == b1

    # Dedup key is (product_id, batch_id) — two different batches of
    # the same product stay as two distinct lines.
    b2 = _uuid()
    drafts = svc.validate_transfer_draft(
        _uuid(), _uuid(),
        [
            {"product_id": p1, "qty_requested": 4, "batch_id": b1},
            {"product_id": p1, "qty_requested": 6, "batch_id": b2},
        ],
    )
    assert len(drafts) == 2
    assert {d.batch_id for d in drafts} == {b1, b2}

    # Bad batch UUID rejected at the parse layer.
    with pytest.raises(ValueError, match="bad_uuid:batch_id"):
        svc.validate_transfer_draft(
            _uuid(), _uuid(),
            [{"product_id": p1, "qty_requested": 1, "batch_id": "bad"}],
        )

    # Empty-string batch_id is treated as None (not a parse error) so
    # callers can POST a uniform schema.
    drafts = svc.validate_transfer_draft(
        _uuid(), _uuid(),
        [{"product_id": p1, "qty_requested": 1, "batch_id": ""}],
    )
    assert drafts[0].batch_id is None

    # Model + migration carry batch_id with SET NULL on deletion so a
    # deleted batch doesn't cascade-kill in-flight transfers.
    assert 'ForeignKey("product_batches.id", ondelete="SET NULL")' in MIGRATION_SRC
    assert "batch_id" in MODEL_SRC
    # Router threads batch_id through to the stock movement row.
    assert "batch_id=item.batch_id" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 10. test_audit_log_entries
# ═══════════════════════════════════════════════════════════════════


def test_audit_log_entries():
    # All four mutation actions call log_action with the expected action strings.
    for action in (
        "stock_transfer.created",
        "stock_transfer.shipped",
        "stock_transfer.received",
        "stock_transfer.cancelled",
    ):
        assert f'action="{action}"' in ROUTER_SRC, f"missing audit: {action}"

    # log_action import + invocation count matches the four mutations.
    assert "from app.services.audit import log_action" in ROUTER_SRC
    assert ROUTER_SRC.count("await log_action(") == 4

    # Each mutation endpoint (create/ship/receive/cancel) has a log_action
    # call — grep by decorator.
    mutation_decorators = [
        '@router.post("", response_model=TransferOut, status_code=201)',
        '@router.post("/{transfer_id}/ship"',
        '@router.post("/{transfer_id}/receive"',
        '@router.post("/{transfer_id}/cancel"',
    ]
    for dec in mutation_decorators:
        assert dec in ROUTER_SRC, f"missing endpoint: {dec}"


# ═══════════════════════════════════════════════════════════════════
# Additional invariant checks
# ═══════════════════════════════════════════════════════════════════


def test_migration_v53_shape():
    # v53 is the correct slot (v45 was taken by ip_allowlist).
    assert 'revision = "e1f2a3b4c5d6"' in MIGRATION_SRC
    assert 'down_revision = "d0e1f2a3b4c5"' in MIGRATION_SRC
    # Both tables + the enum land in one upgrade.
    assert 'op.create_table(\n        "stock_transfers"' in MIGRATION_SRC
    assert 'op.create_table(\n        "stock_transfer_items"' in MIGRATION_SRC
    assert 'STATUS_ENUM_NAME = "stock_transfer_status"' in MIGRATION_SRC
    # Distinct-warehouses CHECK.
    assert "from_warehouse_id <> to_warehouse_id" in MIGRATION_SRC
    # Quantity invariants (5 checks).
    for ck in (
        "qty_requested > 0",
        "qty_shipped >= 0",
        "qty_received >= 0",
        "qty_shipped <= qty_requested",
        "qty_received <= qty_shipped",
    ):
        assert ck in MIGRATION_SRC, f"missing check: {ck}"
    # 5 indexes for query perf.
    assert "ix_stock_transfers_org_status" in MIGRATION_SRC
    assert "ix_stock_transfers_from_wh" in MIGRATION_SRC
    assert "ix_stock_transfers_to_wh" in MIGRATION_SRC
    assert "ix_stock_transfer_items_transfer" in MIGRATION_SRC
    assert "ix_stock_transfer_items_product" in MIGRATION_SRC
    # Downgrade drops the enum too.
    assert 'sa.Enum(name=STATUS_ENUM_NAME).drop' in MIGRATION_SRC


def test_state_machine_complete():
    # DRAFT can only go to IN_TRANSIT or CANCELLED.
    from_draft = {
        t for t in svc.TransferStatus
        if t is not svc.TransferStatus.DRAFT
        and t in svc._ALLOWED[svc.TransferStatus.DRAFT]
    }
    assert from_draft == {svc.TransferStatus.IN_TRANSIT, svc.TransferStatus.CANCELLED}

    # Terminal states have no outgoing edges.
    assert svc._ALLOWED[svc.TransferStatus.RECEIVED] == set()
    assert svc._ALLOWED[svc.TransferStatus.CANCELLED] == set()

    # IN_TRANSIT can advance to PARTIAL or RECEIVED only (no cancel).
    assert svc._ALLOWED[svc.TransferStatus.IN_TRANSIT] == {
        svc.TransferStatus.PARTIAL, svc.TransferStatus.RECEIVED,
    }


def test_now_utc_is_aware():
    t = svc.now_utc()
    assert t.tzinfo is not None
    assert t.utcoffset() == (datetime.now(timezone.utc) - datetime.now(timezone.utc)).__class__(0)
