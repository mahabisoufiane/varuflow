"""Source-contract tests for the POS router."""
import inspect

SRC = inspect.getsource(__import__("app.features.pos.pos", fromlist=["_"]))


# ── Auth dependency ──────────────────────────────────────────────────────────

def test_auth_dependency_injected():
    assert "Depends(get_current_member)" in SRC


def test_auth_import():
    assert "from app.middleware.auth import get_current_member" in SRC


# ── Org isolation ────────────────────────────────────────────────────────────

def test_org_id_filtering_on_sessions():
    assert "PosSession.org_id == org_id" in SRC


def test_org_id_filtering_on_sales():
    assert "PosSale.org_id == org_id" in SRC


def test_org_id_filtering_on_product_lookup():
    assert "Product.org_id == org_id" in SRC


# ── Cart / sale item operations ──────────────────────────────────────────────

def test_sale_item_schema_exists():
    assert "class SaleItemIn(BaseModel):" in SRC


def test_sale_item_has_quantity_field():
    assert "quantity: Decimal" in SRC


def test_sale_item_has_product_id():
    assert "product_id: uuid.UUID" in SRC


def test_create_sale_endpoint():
    assert '@router.post("/sales"' in SRC


def test_sale_items_list_in_sale_input():
    assert "items: list[SaleItemIn]" in SRC


# ── Discount / tax application ───────────────────────────────────────────────

def test_tax_rate_on_line_items():
    assert "tax_rate: Decimal" in SRC


def test_vat_calculation():
    assert "line_total * item.tax_rate / 100" in SRC


def test_subtotal_and_vat_aggregation():
    assert "subtotal += line_total" in SRC
    assert "vat_total += vat" in SRC


# ── Payment processing ──────────────────────────────────────────────────────

def test_payment_method_field():
    assert "payment_method: PosPaymentMethod" in SRC


def test_cash_payment_requires_amount_tendered():
    assert "Cash sales require amount_tendered" in SRC


def test_cash_underpayment_rejected():
    assert "Amount tendered" in SRC and "less than total" in SRC


def test_change_due_calculated():
    assert "change_due" in SRC


# ── Receipt generation ───────────────────────────────────────────────────────

def test_receipt_endpoint_exists():
    assert '@router.get("/sales/{sale_id}/receipt")' in SRC


def test_receipt_returns_pdf():
    assert "application/pdf" in SRC


def test_receipt_filename():
    assert "receipt-" in SRC


# ── Z-report ─────────────────────────────────────────────────────────────────

def test_zreport_endpoint_exists():
    assert '@router.get("/sessions/{session_id}/zreport")' in SRC


def test_zreport_requires_closed_session():
    assert "Z-report is only available after the session is closed" in SRC


def test_zreport_payment_method_breakdown():
    assert "Payment methods" in SRC
    assert "by_method" in SRC


# ── Cash reconciliation ─────────────────────────────────────────────────────

def test_net_revenue_excludes_refunds():
    assert "net_revenue = total_revenue - total_refunds" in SRC


def test_refund_count_tracked():
    assert "Refund count" in SRC


def test_session_net_revenue_helper():
    assert "def _session_net_revenue" in SRC


def test_session_close_endpoint():
    assert '@router.patch("/sessions/{session_id}/close"' in SRC


# ── Refund / stock restore ──────────────────────────────────────────────────

def test_refund_endpoint_exists():
    assert '@router.post("/sales/{sale_id}/refund"' in SRC


def test_refund_idempotent_guard():
    assert "Sale already refunded" in SRC


def test_refund_restores_stock():
    assert "StockMovementType.IN" in SRC
    assert "POS refund" in SRC


# ── Audit logging / stock movements ─────────────────────────────────────────

def test_stock_movement_on_sale():
    assert "StockMovementType.OUT" in SRC
    assert '"POS sale"' in SRC


def test_sale_number_generated():
    assert "sale_number" in SRC
    assert "POS-" in SRC


def test_stock_movement_reference_is_sale_number():
    assert "reference=sale_number" in SRC
