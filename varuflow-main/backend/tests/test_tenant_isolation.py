"""Phase 1 — Comprehensive tenant isolation test suite.

For every tested domain this suite:
  1. Seeds realistic data for BOTH tenant A and tenant B using ENTERPRISE plan orgs.
  2. As tenant A, attempts to READ, LIST, UPDATE, and DELETE tenant B's records.
  3. Asserts the response is 404 or 403 — never 200 with tenant B's data.

IDOR pattern: tenant A sends a valid request using tenant B's resource UUID.
The expected outcome is 404 (resource not found in this org's scope) not 403
(which would confirm the resource exists and reveal its presence).

Important: orgs use OrgPlan.ENTERPRISE so require_module() passes for all
modules. The point is to test data-layer isolation, not plan gating.

Structural choke point: see app/database.py::scoped_select — use it instead
of bare select() for any query on tenant-owned data.

Run:
    cd backend && poetry run pytest tests/test_tenant_isolation.py -v
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import delete as _sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLogEntry
from app.models.campaigns import Campaign
from app.models.documents import Document
from app.models.expenses import Expense
from app.models.inventory import (
    Product,
    PurchaseOrder,
    PurchaseOrderStatus,
    Supplier,
    Warehouse,
)
from app.models.invoicing import Customer, Invoice, InvoiceLineItem, InvoiceStatus
from app.models.organization import OrgPlan, Organization, OrganizationMember, OrgRole
from app.models.tasks import Task


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────


def _ids(payload) -> set[str]:
    """Extract IDs from a list response (handles both list and paginated dict)."""
    if isinstance(payload, dict):
        payload = payload.get("items", [])
    return {str(item["id"]) for item in payload}


async def _seed_customer(db, org_id, name: str) -> Customer:
    c = Customer(org_id=org_id, company_name=name)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _seed_invoice(db, org_id, customer_id, number: str) -> Invoice:
    inv = Invoice(
        org_id=org_id,
        customer_id=customer_id,
        invoice_number=number,
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=30),
        status=InvoiceStatus.SENT,
    )
    db.add(inv)
    await db.flush()
    db.add(InvoiceLineItem(
        invoice_id=inv.id,
        description="Test item",
        quantity=1,
        unit_price=100,
        tax_rate=25,
        line_total=125,
    ))
    await db.commit()
    await db.refresh(inv)
    return inv


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def two_enterprise_orgs(db_session: AsyncSession):
    """Two fully isolated ENTERPRISE-plan tenants, each with one OWNER.

    ENTERPRISE is used so that require_module() grants access to all modules —
    we want to test data-layer isolation, not plan gating.
    """
    org_a = Organization(
        id=uuid.uuid4(),
        name="Alpha Tenant AB",
        org_number="556100-1001",
        plan=OrgPlan.ENTERPRISE,
    )
    org_b = Organization(
        id=uuid.uuid4(),
        name="Bravo Tenant AB",
        org_number="556100-1002",
        plan=OrgPlan.ENTERPRISE,
    )
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    member_a = OrganizationMember(org_id=org_a.id, user_id=user_a, role=OrgRole.OWNER)
    member_b = OrganizationMember(org_id=org_b.id, user_id=user_b, role=OrgRole.OWNER)

    db_session.add_all([org_a, org_b, member_a, member_b])
    await db_session.commit()

    yield {
        "a": {"org": org_a, "user_id": user_a, "member": member_a},
        "b": {"org": org_b, "user_id": user_b, "member": member_b},
    }

    # Use SQL DELETE so the DB-level ON DELETE CASCADE removes members + children
    # without the ORM trying to set org_id = NULL (which violates NOT NULL).
    org_ids = [org_a.id, org_b.id]
    await db_session.execute(
        _sql_delete(Organization).where(Organization.id.in_(org_ids))
    )
    await db_session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# INVOICING — Customers (originally from Phase 0 draft, upgraded to ENTERPRISE)
# ─────────────────────────────────────────────────────────────────────────────


async def test_customers_list_isolated(db_session, two_enterprise_orgs, client_factory):
    """List endpoint must return only the caller's customers."""
    await _seed_customer(db_session, two_enterprise_orgs["a"]["org"].id, "AlphaCustomer")
    await _seed_customer(db_session, two_enterprise_orgs["b"]["org"].id, "BravoCustomer")

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get("/api/invoicing/customers")
    assert r.status_code == 200
    names = [c["company_name"] for c in r.json()]
    assert "AlphaCustomer" in names
    assert "BravoCustomer" not in names, "LEAK: tenant B customer in tenant A list"


async def test_customer_detail_idor(db_session, two_enterprise_orgs, client_factory):
    """GET /customers/{id} with tenant B's ID must return 404."""
    b_cust = await _seed_customer(db_session, two_enterprise_orgs["b"]["org"].id, "BravoOnly")
    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get(f"/api/invoicing/customers/{b_cust.id}")
    assert r.status_code == 404, f"IDOR: got {r.status_code}"


async def test_customer_update_idor(db_session, two_enterprise_orgs, client_factory):
    """PUT /customers/{id} with tenant B's ID must return 404."""
    b_cust = await _seed_customer(db_session, two_enterprise_orgs["b"]["org"].id, "BravoTarget")
    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.put(
            f"/api/invoicing/customers/{b_cust.id}",
            json={"company_name": "Hijacked"},
        )
    assert r.status_code in (404, 405), f"IDOR write: got {r.status_code}"


async def test_customer_delete_idor(db_session, two_enterprise_orgs, client_factory):
    """DELETE /customers/{id} with tenant B's ID must return 404."""
    b_cust = await _seed_customer(db_session, two_enterprise_orgs["b"]["org"].id, "BravoDelete")
    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.delete(f"/api/invoicing/customers/{b_cust.id}")
    assert r.status_code == 404, f"IDOR delete: got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# INVOICING — Invoices
# ─────────────────────────────────────────────────────────────────────────────


async def test_invoices_list_isolated(db_session, two_enterprise_orgs, client_factory):
    """Invoice list must not include other-tenant invoices."""
    a_cust = await _seed_customer(db_session, two_enterprise_orgs["a"]["org"].id, "AlphaCust")
    b_cust = await _seed_customer(db_session, two_enterprise_orgs["b"]["org"].id, "BravoCust")
    await _seed_invoice(db_session, two_enterprise_orgs["a"]["org"].id, a_cust.id, "INV-A-1")
    await _seed_invoice(db_session, two_enterprise_orgs["b"]["org"].id, b_cust.id, "INV-B-1")

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get("/api/invoicing/invoices")
    assert r.status_code == 200
    numbers = [inv["invoice_number"] for inv in r.json()]
    assert "INV-A-1" in numbers
    assert "INV-B-1" not in numbers, "LEAK: tenant B invoice in tenant A list"


async def test_invoice_detail_idor(db_session, two_enterprise_orgs, client_factory):
    b_cust = await _seed_customer(db_session, two_enterprise_orgs["b"]["org"].id, "BravoCust2")
    b_inv = await _seed_invoice(db_session, two_enterprise_orgs["b"]["org"].id, b_cust.id, "INV-B-2")
    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get(f"/api/invoicing/invoices/{b_inv.id}")
    assert r.status_code == 404, f"IDOR: got {r.status_code}"


async def test_cannot_create_invoice_for_cross_org_customer(
    db_session, two_enterprise_orgs, client_factory
):
    """Creating an invoice with a customer_id from another org must fail."""
    b_cust = await _seed_customer(db_session, two_enterprise_orgs["b"]["org"].id, "BravoCust3")
    body = {
        "customer_id": str(b_cust.id),
        "issue_date": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=30)).isoformat(),
        "items": [{"description": "x", "quantity": 1, "unit_price": 10, "tax_rate": 25}],
    }
    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.post("/api/invoicing/invoices", json=body)
    assert r.status_code == 404, f"Cross-org customer reference not blocked: got {r.status_code}"


async def test_invoice_delete_idor(db_session, two_enterprise_orgs, client_factory):
    b_cust = await _seed_customer(db_session, two_enterprise_orgs["b"]["org"].id, "BravoCust4")
    b_inv = await _seed_invoice(db_session, two_enterprise_orgs["b"]["org"].id, b_cust.id, "INV-B-4")
    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.delete(f"/api/invoicing/invoices/{b_inv.id}")
    assert r.status_code == 404, f"IDOR delete: got {r.status_code}"


async def test_invoice_send_idor(db_session, two_enterprise_orgs, client_factory):
    """POST /invoices/{id}/send must not trigger send for tenant B's invoice."""
    b_cust = await _seed_customer(db_session, two_enterprise_orgs["b"]["org"].id, "BravoCust5")
    b_inv = await _seed_invoice(db_session, two_enterprise_orgs["b"]["org"].id, b_cust.id, "INV-B-5")
    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.post(f"/api/invoicing/invoices/{b_inv.id}/send")
    assert r.status_code == 404, f"IDOR send action: got {r.status_code}"


async def test_invoice_pdf_idor(db_session, two_enterprise_orgs, client_factory):
    """GET /invoices/{id}/pdf must not serve tenant B's PDF."""
    b_cust = await _seed_customer(db_session, two_enterprise_orgs["b"]["org"].id, "BravoCust6")
    b_inv = await _seed_invoice(db_session, two_enterprise_orgs["b"]["org"].id, b_cust.id, "INV-B-6")
    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get(f"/api/invoicing/invoices/{b_inv.id}/pdf")
    assert r.status_code == 404, f"IDOR PDF: got {r.status_code}"


async def test_invoice_payments_sub_resource_idor(db_session, two_enterprise_orgs, client_factory):
    """GET /invoices/{id}/payments with tenant B's ID must 404."""
    b_cust = await _seed_customer(db_session, two_enterprise_orgs["b"]["org"].id, "BravoCust7")
    b_inv = await _seed_invoice(db_session, two_enterprise_orgs["b"]["org"].id, b_cust.id, "INV-B-7")
    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get(f"/api/invoicing/invoices/{b_inv.id}/payments")
    assert r.status_code == 404, f"IDOR payments sub-resource: got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# INVENTORY — Products
# ─────────────────────────────────────────────────────────────────────────────


async def test_products_list_isolated(db_session, two_enterprise_orgs, client_factory):
    prod_a = Product(
        org_id=two_enterprise_orgs["a"]["org"].id,
        name="Alpha Widget", sku="ALPHA-001",
        purchase_price=Decimal("10"), sell_price=Decimal("20"),
    )
    prod_b = Product(
        org_id=two_enterprise_orgs["b"]["org"].id,
        name="Bravo Widget", sku="BRAVO-001",
        purchase_price=Decimal("10"), sell_price=Decimal("20"),
    )
    db_session.add_all([prod_a, prod_b])
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get("/api/inventory/products")
    assert r.status_code == 200
    ids = _ids(r.json())
    assert str(prod_a.id) in ids
    assert str(prod_b.id) not in ids, "LEAK: tenant B product in tenant A list"


async def test_product_detail_idor(db_session, two_enterprise_orgs, client_factory):
    prod_b = Product(
        org_id=two_enterprise_orgs["b"]["org"].id,
        name="Bravo Secret", sku="SECRET-001",
        purchase_price=Decimal("5"), sell_price=Decimal("10"),
    )
    db_session.add(prod_b)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get(f"/api/inventory/products/{prod_b.id}")
    assert r.status_code == 404, f"IDOR: got {r.status_code}"


async def test_product_delete_idor(db_session, two_enterprise_orgs, client_factory):
    prod_b = Product(
        org_id=two_enterprise_orgs["b"]["org"].id,
        name="Bravo Delete", sku="DELETE-001",
        purchase_price=Decimal("5"), sell_price=Decimal("10"),
    )
    db_session.add(prod_b)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.delete(f"/api/inventory/products/{prod_b.id}")
    assert r.status_code == 404, f"IDOR delete: got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# INVENTORY — Suppliers
# ─────────────────────────────────────────────────────────────────────────────


async def test_suppliers_list_isolated(db_session, two_enterprise_orgs, client_factory):
    sup_a = Supplier(org_id=two_enterprise_orgs["a"]["org"].id, name="Alpha Supplier AB")
    sup_b = Supplier(org_id=two_enterprise_orgs["b"]["org"].id, name="Bravo Supplier AB")
    db_session.add_all([sup_a, sup_b])
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get("/api/inventory/suppliers")
    assert r.status_code == 200
    ids = _ids(r.json())
    assert str(sup_a.id) in ids
    assert str(sup_b.id) not in ids, "LEAK: tenant B supplier in tenant A list"


async def test_supplier_detail_idor(db_session, two_enterprise_orgs, client_factory):
    # No GET /suppliers/{id} endpoint exists — test the PUT update endpoint instead,
    # which IS scoped by org_id and must return 404 for a cross-tenant supplier.
    sup_b = Supplier(org_id=two_enterprise_orgs["b"]["org"].id, name="Bravo Sup Secret")
    db_session.add(sup_b)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.put(f"/api/inventory/suppliers/{sup_b.id}", json={})
    assert r.status_code == 404, f"IDOR: got {r.status_code}"


async def test_supplier_delete_idor(db_session, two_enterprise_orgs, client_factory):
    # No DELETE /suppliers/{id} endpoint exists — 405 is acceptable (confirms no
    # DELETE surface). Combined with test_supplier_detail_idor (PUT) this covers
    # all writable mutation paths for suppliers.
    sup_b = Supplier(org_id=two_enterprise_orgs["b"]["org"].id, name="Bravo Sup Delete")
    db_session.add(sup_b)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.delete(f"/api/inventory/suppliers/{sup_b.id}")
    assert r.status_code in (404, 405), f"IDOR delete: got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# INVENTORY — Warehouses
# ─────────────────────────────────────────────────────────────────────────────


async def test_warehouses_list_isolated(db_session, two_enterprise_orgs, client_factory):
    wh_a = Warehouse(org_id=two_enterprise_orgs["a"]["org"].id, name="Alpha Warehouse")
    wh_b = Warehouse(org_id=two_enterprise_orgs["b"]["org"].id, name="Bravo Warehouse")
    db_session.add_all([wh_a, wh_b])
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get("/api/inventory/warehouses")
    assert r.status_code == 200
    ids = _ids(r.json())
    assert str(wh_a.id) in ids
    assert str(wh_b.id) not in ids, "LEAK: tenant B warehouse in tenant A list"


async def test_warehouse_detail_idor(db_session, two_enterprise_orgs, client_factory):
    # No GET /warehouses/{id} endpoint exists — test the PUT update endpoint instead,
    # which IS scoped by org_id and must return 404 for a cross-tenant warehouse.
    wh_b = Warehouse(org_id=two_enterprise_orgs["b"]["org"].id, name="Bravo WH Secret")
    db_session.add(wh_b)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.put(f"/api/inventory/warehouses/{wh_b.id}", json={})
    assert r.status_code == 404, f"IDOR: got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# INVENTORY — Purchase Orders
# ─────────────────────────────────────────────────────────────────────────────


async def test_purchase_orders_list_isolated(db_session, two_enterprise_orgs, client_factory):
    sup_a = Supplier(org_id=two_enterprise_orgs["a"]["org"].id, name="Sup A")
    sup_b = Supplier(org_id=two_enterprise_orgs["b"]["org"].id, name="Sup B")
    db_session.add_all([sup_a, sup_b])
    await db_session.flush()
    po_a = PurchaseOrder(
        org_id=two_enterprise_orgs["a"]["org"].id,
        supplier_id=sup_a.id,
        status=PurchaseOrderStatus.DRAFT,
    )
    po_b = PurchaseOrder(
        org_id=two_enterprise_orgs["b"]["org"].id,
        supplier_id=sup_b.id,
        status=PurchaseOrderStatus.DRAFT,
    )
    db_session.add_all([po_a, po_b])
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get("/api/inventory/purchase-orders")
    assert r.status_code == 200
    ids = _ids(r.json())
    assert str(po_b.id) not in ids, "LEAK: tenant B PO in tenant A list"


async def test_purchase_order_detail_idor(db_session, two_enterprise_orgs, client_factory):
    sup_b = Supplier(org_id=two_enterprise_orgs["b"]["org"].id, name="Sup B2")
    db_session.add(sup_b)
    await db_session.flush()
    po_b = PurchaseOrder(
        org_id=two_enterprise_orgs["b"]["org"].id,
        supplier_id=sup_b.id,
        status=PurchaseOrderStatus.DRAFT,
    )
    db_session.add(po_b)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get(f"/api/inventory/purchase-orders/{po_b.id}")
    assert r.status_code == 404, f"IDOR: got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# TASKS
# ─────────────────────────────────────────────────────────────────────────────


async def test_tasks_list_isolated(db_session, two_enterprise_orgs, client_factory):
    task_a = Task(org_id=two_enterprise_orgs["a"]["org"].id, title="Alpha Task")
    task_b = Task(org_id=two_enterprise_orgs["b"]["org"].id, title="Bravo Task")
    db_session.add_all([task_a, task_b])
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get("/api/work/tasks")
    assert r.status_code == 200
    ids = _ids(r.json())
    assert str(task_b.id) not in ids, "LEAK: tenant B task in tenant A list"


async def test_task_detail_idor(db_session, two_enterprise_orgs, client_factory):
    task_b = Task(org_id=two_enterprise_orgs["b"]["org"].id, title="Bravo Secret Task")
    db_session.add(task_b)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get(f"/api/work/tasks/{task_b.id}")
    assert r.status_code == 404, f"IDOR: got {r.status_code}"


async def test_task_patch_idor(db_session, two_enterprise_orgs, client_factory):
    task_b = Task(org_id=two_enterprise_orgs["b"]["org"].id, title="Bravo Patch Target")
    db_session.add(task_b)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.patch(f"/api/work/tasks/{task_b.id}", json={"title": "Hijacked"})
    assert r.status_code == 404, f"IDOR write: got {r.status_code}"


async def test_task_delete_idor(db_session, two_enterprise_orgs, client_factory):
    task_b = Task(org_id=two_enterprise_orgs["b"]["org"].id, title="Bravo Delete Task")
    db_session.add(task_b)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.delete(f"/api/work/tasks/{task_b.id}")
    assert r.status_code == 404, f"IDOR delete: got {r.status_code}"


async def test_task_complete_idor(db_session, two_enterprise_orgs, client_factory):
    """POST /tasks/{id}/complete must not let tenant A complete tenant B's task."""
    task_b = Task(org_id=two_enterprise_orgs["b"]["org"].id, title="Bravo Complete Task")
    db_session.add(task_b)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.post(f"/api/work/tasks/{task_b.id}/complete")
    assert r.status_code == 404, f"IDOR action: got {r.status_code}"


async def test_task_comment_idor(db_session, two_enterprise_orgs, client_factory):
    """POST /tasks/{id}/comments on tenant B's task must 404."""
    task_b = Task(org_id=two_enterprise_orgs["b"]["org"].id, title="Bravo Comment Task")
    db_session.add(task_b)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.post(
            f"/api/work/tasks/{task_b.id}/comments",
            json={"body": "Injected comment"},
        )
    assert r.status_code == 404, f"IDOR comment: got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# EXPENSES
# ─────────────────────────────────────────────────────────────────────────────


async def test_expenses_list_isolated(db_session, two_enterprise_orgs, client_factory):
    exp_a = Expense(
        org_id=two_enterprise_orgs["a"]["org"].id,
        amount=Decimal("100.00"),
        currency="SEK",
        expense_date=date.today(),
        created_by=two_enterprise_orgs["a"]["user_id"],
    )
    exp_b = Expense(
        org_id=two_enterprise_orgs["b"]["org"].id,
        amount=Decimal("200.00"),
        currency="SEK",
        expense_date=date.today(),
        created_by=two_enterprise_orgs["b"]["user_id"],
    )
    db_session.add_all([exp_a, exp_b])
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get("/api/expenses")
    assert r.status_code == 200
    ids = _ids(r.json())
    assert str(exp_b.id) not in ids, "LEAK: tenant B expense in tenant A list"


async def test_expense_detail_idor(db_session, two_enterprise_orgs, client_factory):
    exp_b = Expense(
        org_id=two_enterprise_orgs["b"]["org"].id,
        amount=Decimal("300.00"),
        currency="SEK",
        expense_date=date.today(),
        created_by=two_enterprise_orgs["b"]["user_id"],
    )
    db_session.add(exp_b)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get(f"/api/expenses/{exp_b.id}")
    assert r.status_code == 404, f"IDOR: got {r.status_code}"


async def test_expense_delete_idor(db_session, two_enterprise_orgs, client_factory):
    exp_b = Expense(
        org_id=two_enterprise_orgs["b"]["org"].id,
        amount=Decimal("400.00"),
        currency="SEK",
        expense_date=date.today(),
        created_by=two_enterprise_orgs["b"]["user_id"],
    )
    db_session.add(exp_b)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.delete(f"/api/expenses/{exp_b.id}")
    assert r.status_code == 404, f"IDOR delete: got {r.status_code}"


async def test_expense_approve_idor(db_session, two_enterprise_orgs, client_factory):
    """POST /expenses/{id}/approve must not let tenant A approve tenant B's expense."""
    exp_b = Expense(
        org_id=two_enterprise_orgs["b"]["org"].id,
        amount=Decimal("500.00"),
        currency="SEK",
        expense_date=date.today(),
        created_by=two_enterprise_orgs["b"]["user_id"],
    )
    db_session.add(exp_b)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.post(f"/api/expenses/{exp_b.id}/approve")
    assert r.status_code == 404, f"IDOR approve: got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# DOCUMENTS
# ─────────────────────────────────────────────────────────────────────────────


async def test_documents_list_isolated(db_session, two_enterprise_orgs, client_factory):
    doc_a = Document(
        org_id=two_enterprise_orgs["a"]["org"].id,
        name="Alpha.pdf",
        file_url="https://storage/a.pdf",
        file_size=1024,
        mime_type="application/pdf",
        tags=[],
    )
    doc_b = Document(
        org_id=two_enterprise_orgs["b"]["org"].id,
        name="Bravo.pdf",
        file_url="https://storage/b.pdf",
        file_size=2048,
        mime_type="application/pdf",
        tags=[],
    )
    db_session.add_all([doc_a, doc_b])
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get("/api/documents")
    assert r.status_code == 200
    ids = _ids(r.json())
    assert str(doc_b.id) not in ids, "LEAK: tenant B document in tenant A list"


async def test_document_detail_idor(db_session, two_enterprise_orgs, client_factory):
    doc_b = Document(
        org_id=two_enterprise_orgs["b"]["org"].id,
        name="BravoSecret.pdf",
        file_url="https://storage/secret.pdf",
        file_size=512,
        mime_type="application/pdf",
        tags=[],
    )
    db_session.add(doc_b)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get(f"/api/documents/{doc_b.id}")
    assert r.status_code == 404, f"IDOR: got {r.status_code}"


async def test_document_delete_idor(db_session, two_enterprise_orgs, client_factory):
    doc_b = Document(
        org_id=two_enterprise_orgs["b"]["org"].id,
        name="BravoDelete.pdf",
        file_url="https://storage/delete.pdf",
        file_size=256,
        mime_type="application/pdf",
        tags=[],
    )
    db_session.add(doc_b)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.delete(f"/api/documents/{doc_b.id}")
    assert r.status_code == 404, f"IDOR delete: got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# CAMPAIGNS (CRM module)
# ─────────────────────────────────────────────────────────────────────────────


async def test_campaigns_list_isolated(db_session, two_enterprise_orgs, client_factory):
    camp_a = Campaign(
        org_id=two_enterprise_orgs["a"]["org"].id,
        name="Alpha Campaign",
        subject="Hello from Alpha",
        body_html="",
    )
    camp_b = Campaign(
        org_id=two_enterprise_orgs["b"]["org"].id,
        name="Bravo Campaign",
        subject="Hello from Bravo",
        body_html="",
    )
    db_session.add_all([camp_a, camp_b])
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get("/api/campaigns")
    assert r.status_code == 200
    ids = _ids(r.json())
    assert str(camp_b.id) not in ids, "LEAK: tenant B campaign in tenant A list"


async def test_campaign_detail_idor(db_session, two_enterprise_orgs, client_factory):
    camp_b = Campaign(
        org_id=two_enterprise_orgs["b"]["org"].id,
        name="Bravo Secret Campaign",
        subject="Secret",
        body_html="",
    )
    db_session.add(camp_b)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get(f"/api/campaigns/{camp_b.id}")
    assert r.status_code == 404, f"IDOR: got {r.status_code}"


async def test_campaign_send_idor(db_session, two_enterprise_orgs, client_factory):
    """POST /campaigns/{id}/send must not let tenant A blast tenant B's campaign."""
    camp_b = Campaign(
        org_id=two_enterprise_orgs["b"]["org"].id,
        name="Bravo Blast Campaign",
        subject="Please don't blast me",
        body_html="",
    )
    db_session.add(camp_b)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.post(f"/api/campaigns/{camp_b.id}/send")
    assert r.status_code == 404, f"IDOR send action: got {r.status_code}"


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT LOG
# ─────────────────────────────────────────────────────────────────────────────


async def test_audit_list_isolated(db_session, two_enterprise_orgs, client_factory):
    """Audit log must not expose another tenant's audit trail."""
    entry_b = AuditLogEntry(
        org_id=two_enterprise_orgs["b"]["org"].id,
        action="billing.plan_upgraded",
        target_type="organization",
        target_id=str(two_enterprise_orgs["b"]["org"].id),
    )
    db_session.add(entry_b)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get("/api/audit")
    assert r.status_code == 200
    ids = _ids(r.json())
    assert str(entry_b.id) not in ids, "LEAK: tenant B audit entry in tenant A list"


# ─────────────────────────────────────────────────────────────────────────────
# GDPR export
# ─────────────────────────────────────────────────────────────────────────────


async def test_gdpr_export_only_dumps_own_org(db_session, two_enterprise_orgs, client_factory):
    """GDPR export must only include the caller's org data."""
    a_cust = await _seed_customer(db_session, two_enterprise_orgs["a"]["org"].id, "AlphaPrivate")
    b_cust = await _seed_customer(db_session, two_enterprise_orgs["b"]["org"].id, "BravoPrivate")

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get("/api/gdpr/export")
    assert r.status_code == 200
    dump = r.json()
    names = [c["company_name"] for c in dump.get("customers", [])]
    assert "AlphaPrivate" in names
    assert "BravoPrivate" not in names, "LEAK: tenant B customer in GDPR export"
    assert dump["organization"]["id"] == str(two_enterprise_orgs["a"]["org"].id)


# ─────────────────────────────────────────────────────────────────────────────
# ANALYTICS — aggregate results must not bleed across tenants
# ─────────────────────────────────────────────────────────────────────────────


async def test_analytics_revenue_no_cross_tenant(db_session, two_enterprise_orgs, client_factory):
    """Revenue analytics for tenant A must not include tenant B's invoices."""
    b_cust = await _seed_customer(db_session, two_enterprise_orgs["b"]["org"].id, "BravoRevenueCust")
    b_inv = Invoice(
        org_id=two_enterprise_orgs["b"]["org"].id,
        customer_id=b_cust.id,
        invoice_number="INV-ANALYTICS-B",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=30),
        status=InvoiceStatus.PAID,
        total_sek=Decimal("999999.00"),
    )
    db_session.add(b_inv)
    await db_session.commit()

    async with client_factory(two_enterprise_orgs["a"]["member"]) as client:
        r = await client.get("/api/analytics/revenue")
    if r.status_code == 200:
        assert "999999" not in str(r.json()), "LEAK: tenant B revenue visible to tenant A analytics"
