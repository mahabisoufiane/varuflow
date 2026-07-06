"""Write-route smoke test — the top ~20 money-path mutations as one flow.

Companion to test_route_smoke.py (which only proves the GET surface). Same
bug class, higher stakes: these are the endpoints that create invoices, take
payments and move stock. Each step runs with an ENTERPRISE owner, feeds its
response into later steps, and must return 2xx — a 4xx here means the API
contract the frontend relies on is broken (we control every payload), and a
5xx is a defect outright.

Steps marked optional=True are tolerated as 4xx-but-not-5xx (business-rule
gates that may legitimately reject in a bare org), so the flow keeps going.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest_asyncio

from app.main import app  # noqa: F401 — ensures all routers are mounted
from app.features.auth.organization import (
    Organization,
    OrganizationMember,
    OrgPlan,
    OrgRole,
)


@pytest_asyncio.fixture
async def mutation_org(db_session):
    org = Organization(
        id=uuid.uuid4(),
        name="Mutation Smoke AB",
        org_number="556000-5555",
        plan=OrgPlan.ENTERPRISE,
    )
    member = OrganizationMember(org_id=org.id, user_id=uuid.uuid4(), role=OrgRole.OWNER)
    db_session.add_all([org, member])
    await db_session.commit()
    yield member
    # purchase_order_items.product_id has no ON DELETE action (pre-existing
    # schema gap): the org-delete cascade can reach `products` before the PO
    # items that reference them. Clear the item rows first.
    from sqlalchemy import text as _text
    await db_session.execute(_text(
        "DELETE FROM purchase_order_items WHERE purchase_order_id IN "
        "(SELECT id FROM purchase_orders WHERE org_id = :oid)"
    ), {"oid": str(org.id)})
    await db_session.delete(member)
    await db_session.delete(org)
    await db_session.commit()


async def test_money_path_mutations(mutation_org, client_factory):
    today = date.today().isoformat()
    due = (date.today() + timedelta(days=30)).isoformat()
    ids: dict[str, str] = {}
    failures: list[str] = []

    # (name, method, path, payload, capture_key, optional)
    def steps():
        return [
            ("create customer", "POST", "/api/invoicing/customers",
             {"company_name": "Smoke Kund AB", "email": "kund@smoke.se",
              "org_number": "556000-1111", "payment_terms_days": 30}, "customer", False),
            ("update customer", "PUT", f"/api/invoicing/customers/{ids.get('customer')}",
             {"company_name": "Smoke Kund AB", "email": "ny@smoke.se",
              "payment_terms_days": 20}, None, False),
            ("create supplier", "POST", "/api/inventory/suppliers",
             {"name": "Smoke Leverantör AB", "country": "Sweden"}, "supplier", False),
            ("create warehouse", "POST", "/api/inventory/warehouses",
             {"name": "Smoke Lager", "location": "Stockholm"}, "warehouse", False),
            ("create product", "POST", "/api/inventory/products",
             {"name": "Smoke Kaffe", "sku": f"SMK-{uuid.uuid4().hex[:6]}", "unit": "st",
              "purchase_price": "10.00", "sell_price": "25.00", "tax_rate": "12"},
             "product", False),
            ("update product", "PUT", f"/api/inventory/products/{ids.get('product')}",
             {"sell_price": "29.00"}, None, False),
            ("stock movement IN", "POST", "/api/inventory/movements",
             {"product_id": ids.get("product"), "warehouse_id": ids.get("warehouse"),
              "type": "IN", "quantity": 100, "note": "smoke"}, None, False),
            ("create quote", "POST", "/api/quotes",
             {"customer_id": ids.get("customer"), "title": "Smoke offert",
              "items": [{"description": "Kaffe", "quantity": 10,
                         "unit_price": 25.0, "tax_rate": 12}]}, "quote", False),
            ("send quote", "POST", f"/api/quotes/{ids.get('quote')}/send", {}, None, False),
            ("create invoice", "POST", "/api/invoicing/invoices",
             {"customer_id": ids.get("customer"), "issue_date": today, "due_date": due,
              "items": [{"product_id": ids.get("product"), "description": "Kaffe",
                         "quantity": 10, "unit_price": 25.0, "tax_rate": 12}]},
             "invoice", False),
            ("invoice → SENT", "PATCH",
             f"/api/invoicing/invoices/{ids.get('invoice')}/status",
             {"status": "SENT"}, None, False),
            ("record payment", "POST",
             f"/api/invoicing/invoices/{ids.get('invoice')}/payments",
             {"amount": 100.0, "payment_date": today, "method": "BANK_TRANSFER"},
             None, False),
            ("invoice → PAID", "PATCH",
             f"/api/invoicing/invoices/{ids.get('invoice')}/status",
             {"status": "PAID"}, None, False),
            ("create purchase order", "POST", "/api/inventory/purchase-orders",
             {"supplier_id": ids.get("supplier"),
              "items": [{"product_id": ids.get("product"), "quantity": 50,
                         "unit_price": "10.00"}]}, "po", False),
            ("PO → SENT", "PATCH",
             f"/api/inventory/purchase-orders/{ids.get('po')}/status",
             {"status": "SENT"}, None, False),
            ("PO → RECEIVED", "PATCH",
             f"/api/inventory/purchase-orders/{ids.get('po')}/status",
             {"status": "RECEIVED"}, None, False),
            ("create purchase request", "POST", "/api/purchase-requests",
             {"title": "Smoke inköp", "estimated_total": 500, "currency": "SEK",
              "urgency": "normal",
              "items": [{"description": "Grejer", "quantity": 1, "unit_price": 500}]},
             "preq", False),
            ("approve purchase request", "POST",
             f"/api/purchase-requests/{ids.get('preq')}/approve",
             {"note": "ok"}, None, False),
            ("create purchase request w/ supplier", "POST", "/api/purchase-requests",
             {"title": "Smoke inköp 2", "estimated_total": 250, "currency": "SEK",
              "urgency": "normal", "supplier_id": ids.get("supplier"),
              "items": [{"description": "Mer kaffe", "quantity": 10, "unit_price": 25,
                         "product_id": ids.get("product")}]},
             "preq2", False),
            ("approve → auto-PO", "POST",
             f"/api/purchase-requests/{ids.get('preq2')}/approve",
             {"note": "ok"}, None, False),
            ("convert quote → invoice", "POST",
             f"/api/quotes/{ids.get('quote')}/convert", {}, None, True),
            ("create credit note", "POST", "/api/credit-notes",
             {"invoice_id": ids.get("invoice"), "reason": "smoke",
              "lines": [{"description": "Kaffe", "quantity": 1, "unit_price": 25.0}]},
             None, True),
            ("mark overdue sweep", "POST", "/api/recurring/mark-overdue", {}, None, False),
        ]

    async with client_factory(mutation_org) as client:
        # Re-evaluate steps() each iteration so path/payload f-strings pick up
        # the ids captured by earlier steps (a single upfront call would bake
        # in None for every dependent step).
        for i in range(len(steps())):
            name, method, path, payload, capture, optional = steps()[i]
            resp = await client.request(method, path, json=payload)
            ok = 200 <= resp.status_code < 300
            if ok and capture:
                try:
                    ids[capture] = resp.json()["id"]
                except Exception:
                    failures.append(f"{name}: 2xx but no id in body")
            if not ok:
                tolerated = optional and resp.status_code < 500
                if not tolerated:
                    failures.append(
                        f"{name}: {method} {path} -> {resp.status_code} {resp.text[:160]}"
                    )

    assert not failures, "money-path mutations failed:\n  " + "\n  ".join(failures)
