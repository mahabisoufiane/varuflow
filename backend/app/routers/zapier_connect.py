"""Zapier + Make.com connector

Uses the REST Hooks pattern: Zapier/Make registers a target URL for a trigger event,
and Varuflow fires webhooks using the existing WebhookEndpoint delivery infrastructure.

Action endpoints let Zapier/Make perform operations in Varuflow.

Endpoints:
  GET  /api/integrations/zapier/triggers
  GET  /api/integrations/zapier/actions
  POST /api/integrations/zapier/subscribe
  DELETE /api/integrations/zapier/unsubscribe/{endpoint_id}
  POST /api/integrations/zapier/actions/create-invoice
  POST /api/integrations/zapier/actions/create-customer
  POST /api/integrations/zapier/actions/update-stock
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.invoicing import Customer, Invoice, InvoiceStatus
from app.models.inventory import Product, StockLevel, StockMovement, StockMovementType as MovementType
from app.models.webhook import WebhookEndpoint
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/integrations/zapier", tags=["integrations_automation"], dependencies=[Depends(require_module("settings"))])
log = logging.getLogger(__name__)

TRIGGER_CATALOG = [
    {
        "event_type": "invoice.created",
        "label": "New Invoice Created",
        "description": "Fires when a new invoice is created in Varuflow",
        "sample": {"id": "abc123", "invoice_number": "INV-001", "total": "1200.00", "status": "draft"},
    },
    {
        "event_type": "invoice.paid",
        "label": "Invoice Paid",
        "description": "Fires when an invoice is marked as paid",
        "sample": {"id": "abc123", "invoice_number": "INV-001", "total": "1200.00", "status": "paid"},
    },
    {
        "event_type": "stock.low",
        "label": "Low Stock Alert",
        "description": "Fires when a product stock level falls below its reorder point",
        "sample": {"product_id": "def456", "product_name": "Widget A", "quantity": 3, "reorder_point": 10},
    },
    {
        "event_type": "order.placed",
        "label": "Purchase Order Placed",
        "description": "Fires when a purchase order is created",
        "sample": {"po_id": "po789", "supplier": "Acme Corp", "total": "5400.00"},
    },
    {
        "event_type": "customer.created",
        "label": "New Customer",
        "description": "Fires when a new customer is added",
        "sample": {"id": "cus111", "company_name": "Nordico AB"},
    },
]

ACTION_CATALOG = [
    {
        "action": "create-invoice",
        "label": "Create Draft Invoice",
        "description": "Creates a new draft invoice in Varuflow",
        "input_fields": [
            {"key": "customer_name", "label": "Customer Name", "type": "string", "required": True},
            {"key": "amount", "label": "Amount (SEK)", "type": "number", "required": True},
            {"key": "description", "label": "Line Item Description", "type": "string", "required": False},
        ],
    },
    {
        "action": "create-customer",
        "label": "Create Customer",
        "description": "Creates a new customer in Varuflow",
        "input_fields": [
            {"key": "company_name", "label": "Company Name", "type": "string", "required": True},
        ],
    },
    {
        "action": "update-stock",
        "label": "Update Stock Level",
        "description": "Creates an ADJUSTMENT stock movement for a product (identified by SKU)",
        "input_fields": [
            {"key": "sku", "label": "Product SKU", "type": "string", "required": True},
            {"key": "quantity_delta", "label": "Quantity Change (+/-)", "type": "number", "required": True},
            {"key": "notes", "label": "Notes", "type": "string", "required": False},
        ],
    },
]


# ── Schemas ───────────────────────────────────────────────────────────────────

class SubscribeIn(BaseModel):
    target_url: str
    event_type: str

class SubscribeOut(BaseModel):
    id: str
    event_type: str
    target_url: str

class CreateInvoiceIn(BaseModel):
    customer_name: str
    amount: Decimal
    description: Optional[str] = "Zapier invoice item"

class CreateCustomerIn(BaseModel):
    company_name: str

class UpdateStockIn(BaseModel):
    sku: str
    quantity_delta: int
    notes: Optional[str] = "Zapier stock adjustment"


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Catalog endpoints ─────────────────────────────────────────────────────────

@router.get("/triggers")
async def list_triggers(ctx: tuple = Depends(get_current_member)):
    return {"triggers": TRIGGER_CATALOG}


@router.get("/actions")
async def list_actions(ctx: tuple = Depends(get_current_member)):
    return {"actions": ACTION_CATALOG}


# ── REST Hook subscribe/unsubscribe ───────────────────────────────────────────

@router.post("/subscribe", response_model=SubscribeOut)
async def subscribe(
    body: SubscribeIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        valid_events = {t["event_type"] for t in TRIGGER_CATALOG}
        if body.event_type not in valid_events:
            raise HTTPException(status_code=422, detail=f"Unknown event_type. Valid: {list(valid_events)}")

        endpoint = WebhookEndpoint(
            org_id=org_id,
            target_url=body.target_url,
            events=[body.event_type],
            is_active=True,
            description=f"Zapier/Make subscription: {body.event_type}",
        )
        db.add(endpoint)
        await db.commit()
        await db.refresh(endpoint)

        return SubscribeOut(id=str(endpoint.id), event_type=body.event_type, target_url=body.target_url)
    except HTTPException:
        raise
    except Exception as e:
        log.error("zapier_subscribe failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/unsubscribe/{endpoint_id}")
async def unsubscribe(
    endpoint_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(WebhookEndpoint).where(
                WebhookEndpoint.id == endpoint_id,
                WebhookEndpoint.org_id == org_id,
            )
        )
        endpoint = row.scalar_one_or_none()
        if not endpoint:
            raise HTTPException(status_code=404, detail="Webhook endpoint not found")
        await db.delete(endpoint)
        await db.commit()
        return {"unsubscribed": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error("zapier_unsubscribe failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Action endpoints ──────────────────────────────────────────────────────────

@router.post("/actions/create-invoice")
async def action_create_invoice(
    body: CreateInvoiceIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create a draft invoice via Zapier/Make action."""
    org_id = _org(ctx)
    try:
        # Find or create customer
        cust_row = await db.execute(
            select(Customer).where(
                Customer.org_id == org_id,
                Customer.company_name == body.customer_name,
                Customer.deleted_at.is_(None),
            )
        )
        customer = cust_row.scalar_one_or_none()
        if not customer:
            customer = Customer(org_id=org_id, company_name=body.customer_name)
            db.add(customer)
            await db.flush()

        now = datetime.now(timezone.utc)
        inv_num = f"ZAP-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        invoice = Invoice(
            org_id=org_id,
            customer_id=customer.id,
            invoice_number=inv_num,
            status=InvoiceStatus.DRAFT,
            issue_date=now.date(),
            currency="SEK",
            subtotal=body.amount,
            vat_amount=Decimal("0"),
            total_sek=body.amount,
            notes=f"Created via Zapier. Item: {body.description}",
        )
        db.add(invoice)
        await db.commit()
        await db.refresh(invoice)

        return {
            "id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
            "status": invoice.status.value,
            "total": str(invoice.total_sek),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("zapier_create_invoice failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/actions/create-customer")
async def action_create_customer(
    body: CreateCustomerIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create a customer via Zapier/Make action. Idempotent — returns existing if name matches."""
    org_id = _org(ctx)
    try:
        existing = await db.execute(
            select(Customer).where(
                Customer.org_id == org_id,
                Customer.company_name == body.company_name,
                Customer.deleted_at.is_(None),
            )
        )
        customer = existing.scalar_one_or_none()
        created = False
        if not customer:
            customer = Customer(org_id=org_id, company_name=body.company_name)
            db.add(customer)
            await db.commit()
            await db.refresh(customer)
            created = True

        return {
            "id": str(customer.id),
            "company_name": customer.company_name,
            "created": created,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("zapier_create_customer failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/actions/update-stock")
async def action_update_stock(
    body: UpdateStockIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create an ADJUSTMENT stock movement via Zapier/Make action."""
    org_id = _org(ctx)
    try:
        if body.quantity_delta == 0:
            raise HTTPException(status_code=422, detail="quantity_delta cannot be 0")

        prod_row = await db.execute(
            select(Product).where(
                Product.org_id == org_id,
                Product.sku == body.sku,
            )
        )
        product = prod_row.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product with SKU '{body.sku}' not found")

        # Fetch current stock level
        sl_row = await db.execute(
            select(StockLevel).where(StockLevel.product_id == product.id)
        )
        stock_level = sl_row.scalar_one_or_none()

        movement = StockMovement(
            org_id=org_id,
            product_id=product.id,
            movement_type=MovementType.ADJUSTMENT,
            quantity=abs(body.quantity_delta),
            direction="in" if body.quantity_delta > 0 else "out",
            notes=body.notes or "Zapier stock adjustment",
        )
        db.add(movement)

        if stock_level:
            stock_level.quantity = max(0, int(stock_level.quantity or 0) + body.quantity_delta)
        else:
            stock_level = StockLevel(
                product_id=product.id,
                quantity=max(0, body.quantity_delta),
            )
            db.add(stock_level)

        await db.commit()
        await db.refresh(stock_level)

        return {
            "product_id": str(product.id),
            "sku": body.sku,
            "quantity_delta": body.quantity_delta,
            "new_quantity": int(stock_level.quantity),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("zapier_update_stock failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
