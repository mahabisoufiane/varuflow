"""Tests for the inventory audit trail (Item 47).

Pure + source-contract style, matching Items 28-46.

Required test names (spec):

* test_product_movement_history
* test_filter_by_date
* test_filter_by_user
* test_export_csv
* test_unusual_movement_flag
* test_warehouse_filter
* test_audit_trail_shows_reason
* test_org_isolation
* test_plan_gate
* test_linked_to_audit_log
"""
from __future__ import annotations

import csv
import io
import pathlib
from datetime import datetime, timezone

from app.services import inventory_audit_service as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"


def _read(relpath: str) -> str:
    return (_BACKEND_ROOT / relpath).read_text()


ROUTER_SRC = _read("routers/inventory_audit.py")
SERVICE_SRC = _read("services/inventory_audit_service.py")
INVENTORY_SRC = _read("routers/inventory.py")
AUDIT_SVC_SRC = _read("services/audit.py")
MAIN_SRC = _read("main.py")


# ═══════════════════════════════════════════════════════════════════
# 1. test_product_movement_history
# ═══════════════════════════════════════════════════════════════════


def test_product_movement_history():
    # Shortcut endpoint exists with path param and correct response model.
    assert (
        '@router.get("/product/{product_id}", response_model=list[MovementAuditOut])'
        in ROUTER_SRC
    )
    # Shortcut delegates to the shared tenant-scoped query helper.
    assert "async def list_product_audit" in ROUTER_SRC
    assert "_query_movements" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 2. test_filter_by_date
# ═══════════════════════════════════════════════════════════════════


def test_filter_by_date():
    assert "start_date: datetime | None = Query" in ROUTER_SRC
    assert "end_date: datetime | None = Query" in ROUTER_SRC
    assert "StockMovement.created_at >= start_date" in ROUTER_SRC
    assert "StockMovement.created_at <= end_date" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 3. test_filter_by_user
# ═══════════════════════════════════════════════════════════════════


def test_filter_by_user():
    assert "actor_user_id: uuid.UUID | None = Query" in ROUTER_SRC
    # Post-fetch filter against the joined audit-log row.
    assert "if actor_user_id is not None and actor_id != actor_user_id:" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 4. test_export_csv
# ═══════════════════════════════════════════════════════════════════


def test_export_csv():
    # Router wires the CSV endpoint and uses the pure renderer.
    assert '@router.get("/movements.csv")' in ROUTER_SRC
    assert "svc.render_csv" in ROUTER_SRC
    assert 'media_type="text/csv"' in ROUTER_SRC
    assert 'Content-Disposition' in ROUTER_SRC
    assert 'attachment; filename="inventory-audit.csv"' in ROUTER_SRC
    # Export is itself audited.
    assert '"inventory_audit.exported"' in ROUTER_SRC

    # Pure round-trip of the renderer with a representative row.
    row = svc.ExportRow(
        timestamp=datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        type="OUT",
        quantity=7,
        product_sku="SKU-1",
        product_name="Widget",
        warehouse="Main",
        reference="PO-1",
        reason="note",
        actor_user_id="11111111-1111-1111-1111-111111111111",
        ip_address="1.2.3.4",
        unusual=False,
    )
    body = svc.render_csv([row])
    reader = list(csv.reader(io.StringIO(body)))
    assert reader[0] == list(svc.CSV_HEADERS)
    assert reader[1][1] == "OUT"
    assert reader[1][2] == "7"
    assert reader[1][3] == "SKU-1"


# ═══════════════════════════════════════════════════════════════════
# 5. test_unusual_movement_flag
# ═══════════════════════════════════════════════════════════════════


def test_unusual_movement_flag():
    # Large OUT is unusual.
    f1 = svc.classify_movement(movement_type="OUT", quantity=100)
    assert f1.unusual is True
    assert "large_out" in f1.reasons

    # Small OUT is clean.
    f2 = svc.classify_movement(movement_type="OUT", quantity=5)
    assert f2.unusual is False
    assert f2.reasons == ()

    # Any ADJUSTMENT is flagged manually; large ones get double reason.
    f3 = svc.classify_movement(movement_type="ADJUSTMENT", quantity=1)
    assert f3.unusual is True
    assert "manual_adjustment" in f3.reasons

    f4 = svc.classify_movement(movement_type="ADJUSTMENT", quantity=999)
    assert "manual_adjustment" in f4.reasons
    assert "large_adjustment" in f4.reasons

    # IN movements are never flagged.
    f5 = svc.classify_movement(movement_type="IN", quantity=10_000)
    assert f5.unusual is False


# ═══════════════════════════════════════════════════════════════════
# 6. test_warehouse_filter
# ═══════════════════════════════════════════════════════════════════


def test_warehouse_filter():
    assert (
        '@router.get("/warehouse/{warehouse_id}", response_model=list[MovementAuditOut])'
        in ROUTER_SRC
    )
    assert "warehouse_id: uuid.UUID | None = Query" in ROUTER_SRC
    assert "StockMovement.warehouse_id == warehouse_id" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 7. test_audit_trail_shows_reason
# ═══════════════════════════════════════════════════════════════════


def test_audit_trail_shows_reason():
    # Schema exposes ``reason`` (mapped from the movement's ``note`` column).
    assert "reason: str | None" in ROUTER_SRC
    assert "reason=m.note" in ROUTER_SRC
    # Reason also flows to the CSV export.
    assert "reason" in svc.CSV_HEADERS


# ═══════════════════════════════════════════════════════════════════
# 8. test_org_isolation
# ═══════════════════════════════════════════════════════════════════


def test_org_isolation():
    # Every query pulls org_id from the authenticated member context
    # and filters by it — never trusts a client-supplied value.
    assert "StockMovement.org_id == org_id" in ROUTER_SRC
    assert "def _org(ctx:" in ROUTER_SRC
    assert "org_id = _org(ctx)" in ROUTER_SRC
    # Audit-log join is also tenant-scoped.
    assert "org_id=org_id" in ROUTER_SRC
    assert 'target_type="stock_movement"' in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 9. test_plan_gate
# ═══════════════════════════════════════════════════════════════════


def test_plan_gate():
    # PRO-gated at the router level — every endpoint inherits.
    assert "from app.middleware.plan_check import require_plan" in ROUTER_SRC
    assert "from app.models.organization import OrgPlan" in ROUTER_SRC
    assert "dependencies=[Depends(require_plan(OrgPlan.PRO))]" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 10. test_linked_to_audit_log
# ═══════════════════════════════════════════════════════════════════


def test_linked_to_audit_log():
    # The inventory-audit router reads audit-log rows keyed by
    # target_type="stock_movement" — the linkage is consumed here.
    assert 'target_type="stock_movement"' in ROUTER_SRC

    # services.audit exports the batched lookup helper.
    assert "async def fetch_audit_for_targets" in AUDIT_SVC_SRC

    # Router consumes it.
    assert "from app.services.audit import fetch_audit_for_targets" in ROUTER_SRC
    assert "fetch_audit_for_targets(" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# Invariants
# ═══════════════════════════════════════════════════════════════════


def test_router_registered_in_main():
    assert "inventory_audit" in MAIN_SRC
    assert "app.include_router(inventory_audit.router)" in MAIN_SRC


def test_csv_headers_match_spec():
    assert svc.CSV_HEADERS == (
        "timestamp",
        "type",
        "quantity",
        "product_sku",
        "product_name",
        "warehouse",
        "reference",
        "reason",
        "actor_user_id",
        "ip_address",
        "unusual",
    )


def test_classify_movement_thresholds_pure():
    # Exactly at threshold is NOT flagged — strict > comparison.
    at = svc.classify_movement(
        movement_type="OUT",
        quantity=svc.LARGE_MOVEMENT_THRESHOLD,
    )
    assert at.unusual is False

    # One over the threshold is flagged.
    over = svc.classify_movement(
        movement_type="OUT",
        quantity=svc.LARGE_MOVEMENT_THRESHOLD + 1,
    )
    assert over.unusual is True
    assert "large_out" in over.reasons

    # Lowercase input is normalized.
    lower = svc.classify_movement(movement_type="out", quantity=9999)
    assert "large_out" in lower.reasons


def test_csv_rfc4180_escaping():
    # Product names with commas and quotes must round-trip cleanly.
    row = svc.ExportRow(
        timestamp=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        type="IN",
        quantity=1,
        product_sku="A",
        product_name='Widget, "Deluxe" Edition',
        warehouse="Main",
        reference=None,
        reason=None,
        actor_user_id=None,
        ip_address=None,
        unusual=False,
    )
    body = svc.render_csv([row])
    parsed = list(csv.reader(io.StringIO(body)))
    assert parsed[0] == list(svc.CSV_HEADERS)
    assert parsed[1][4] == 'Widget, "Deluxe" Edition'


def test_export_row_cap_defined():
    # Hard cap protects workers from OOM on noisy orgs.
    assert svc.EXPORT_ROW_CAP >= 1000
    assert isinstance(svc.EXPORT_ROW_CAP, int)
