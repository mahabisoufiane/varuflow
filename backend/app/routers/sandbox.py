"""Sandbox / Demo Mode.

A "sandbox" is the same user's organisation with is_sandbox=True.
It is pre-populated with realistic demo data so owners can explore
features without risking production data.

Endpoints
─────────
GET  /api/sandbox/status      → is current org a sandbox? + demo stats
POST /api/sandbox/create      → create a sandbox org and populate it
POST /api/sandbox/reset       → wipe all transactional data + re-seed
DELETE /api/sandbox           → permanently delete sandbox org
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.invoicing import (
    Customer,
    Invoice,
    InvoiceLineItem,
    InvoiceStatus,
)
from app.models.inventory import Product, Supplier
from app.models.organization import Organization, OrganizationMember, OrgPlan, OrgRole

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return uuid.UUID(str(user.id))


async def _get_org(db: AsyncSession, org_id: uuid.UUID) -> Organization:
    org = await db.scalar(select(Organization).where(Organization.id == org_id))
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    return org


# ── Demo data catalogue ────────────────────────────────────────────────────────

_DEMO_PRODUCTS = [
    {"name": "Nordic Oak Desk", "sku": "DEMO-DESK-001", "sell_price": 4990, "purchase_price": 2200, "tax_rate": 25, "unit": "st"},
    {"name": "Ergonomic Chair Pro", "sku": "DEMO-CHAIR-001", "sell_price": 3290, "purchase_price": 1500, "tax_rate": 25, "unit": "st"},
    {"name": "LED Monitor 27\"", "sku": "DEMO-MON-001", "sell_price": 2890, "purchase_price": 1400, "tax_rate": 25, "unit": "st"},
    {"name": "USB-C Hub 7-Port", "sku": "DEMO-HUB-001", "sell_price": 649, "purchase_price": 250, "tax_rate": 25, "unit": "st"},
    {"name": "Wireless Keyboard SE", "sku": "DEMO-KB-001", "sell_price": 999, "purchase_price": 400, "tax_rate": 25, "unit": "st"},
    {"name": "Notebook A4 Hardcover", "sku": "DEMO-NB-001", "sell_price": 149, "purchase_price": 50, "tax_rate": 6, "unit": "st"},
    {"name": "Ballpoint Pen (10-pack)", "sku": "DEMO-PEN-001", "sell_price": 89, "purchase_price": 30, "tax_rate": 6, "unit": "förp"},
    {"name": "Courier Box 30×30×30", "sku": "DEMO-BOX-001", "sell_price": 25, "purchase_price": 8, "tax_rate": 25, "unit": "st"},
]

_DEMO_CUSTOMERS = [
    {"company_name": "Bergström & Partners AB", "email": "order@bergstrom.se", "org_number": "556123-4567"},
    {"company_name": "Nilsson Trading Nordic", "email": "inköp@nilssonnordic.se", "org_number": "559001-2345"},
    {"company_name": "Lindqvist Bygg AB", "email": "faktura@lindqvistbygg.se", "org_number": "556789-0123"},
    {"company_name": "Svensson Konsult HB", "email": "info@svenssonkonsult.se", "org_number": "916401-1234"},
    {"company_name": "Pettersson Logistik", "email": "order@petterssonlogistik.se", "org_number": "556456-7890"},
]

_DEMO_SUPPLIERS = [
    {"name": "Kontorsgrossisten AB", "email": "order@kontorsgrossisten.se"},
    {"name": "Nordic Supply Co.", "email": "supply@nordicsupply.se"},
]


async def _seed_demo_data(db: AsyncSession, org_id: uuid.UUID) -> None:
    """Insert demo products, customers, suppliers, and invoices."""
    today = date.today()

    # Products
    prod_objs = []
    for p in _DEMO_PRODUCTS:
        prod = Product(
            org_id=org_id,
            name=p["name"],
            sku=p["sku"],
            sell_price=Decimal(str(p["sell_price"])),
            purchase_price=Decimal(str(p["purchase_price"])),
            tax_rate=Decimal(str(p["tax_rate"])),
            unit=p["unit"],
        )
        db.add(prod)
        prod_objs.append(prod)

    # Suppliers
    for s in _DEMO_SUPPLIERS:
        sup = Supplier(org_id=org_id, name=s["name"], email=s["email"])
        db.add(sup)

    # Customers
    cust_objs = []
    for c in _DEMO_CUSTOMERS:
        cust = Customer(
            org_id=org_id,
            company_name=c["company_name"],
            email=c["email"],
            org_number=c["org_number"],
        )
        db.add(cust)
        cust_objs.append(cust)

    await db.flush()  # get IDs

    # Demo invoices — 5 across different statuses
    demo_invoices = [
        {"customer_idx": 0, "offset_days": -30, "status": InvoiceStatus.PAID,    "number": "INV-DEMO-001"},
        {"customer_idx": 1, "offset_days": -20, "status": InvoiceStatus.SENT,    "number": "INV-DEMO-002"},
        {"customer_idx": 2, "offset_days": -10, "status": InvoiceStatus.OVERDUE, "number": "INV-DEMO-003"},
        {"customer_idx": 3, "offset_days": -5,  "status": InvoiceStatus.DRAFT,   "number": "INV-DEMO-004"},
        {"customer_idx": 4, "offset_days":  0,  "status": InvoiceStatus.DRAFT,   "number": "INV-DEMO-005"},
    ]
    for inv_spec in demo_invoices:
        issue = today + timedelta(days=inv_spec["offset_days"])
        due = issue + timedelta(days=30)
        cust = cust_objs[inv_spec["customer_idx"]]
        inv = Invoice(
            org_id=org_id,
            customer_id=cust.id,
            invoice_number=inv_spec["number"],
            issue_date=issue,
            due_date=due,
            status=inv_spec["status"],
            currency="SEK",
        )
        db.add(inv)
        await db.flush()

        # 2 line items per invoice
        for prod in prod_objs[:2]:
            qty = Decimal("2")
            total_ex = prod.sell_price * qty
            vat = total_ex * prod.tax_rate / Decimal("100")
            li = InvoiceLineItem(
                invoice_id=inv.id,
                description=prod.name,
                quantity=qty,
                unit_price=prod.sell_price,
                tax_rate=prod.tax_rate,
                line_total=total_ex + vat,
            )
            db.add(li)

        # Update invoice totals
        subtotal = prod_objs[0].sell_price * 2 + prod_objs[1].sell_price * 2
        vat_total = (prod_objs[0].sell_price * 2 * prod_objs[0].tax_rate / 100 +
                     prod_objs[1].sell_price * 2 * prod_objs[1].tax_rate / 100)
        inv.subtotal = subtotal
        inv.vat_amount = vat_total
        inv.total_sek = subtotal + vat_total

    await db.flush()


async def _wipe_transactional_data(db: AsyncSession, org_id: uuid.UUID) -> None:
    """Delete all transactional data for an org (products, customers, invoices)."""
    from app.models.invoicing import InvoiceLineItem, Invoice, Customer
    from app.models.inventory import Product, Supplier

    # Order matters for FK constraints
    await db.execute(delete(InvoiceLineItem).where(InvoiceLineItem.invoice_id.in_(
        select(Invoice.id).where(Invoice.org_id == org_id)
    )))
    await db.execute(delete(Invoice).where(Invoice.org_id == org_id))
    await db.execute(delete(Customer).where(Customer.org_id == org_id))
    await db.execute(delete(Product).where(Product.org_id == org_id))
    await db.execute(delete(Supplier).where(Supplier.org_id == org_id))
    await db.flush()


# ── Schemas ────────────────────────────────────────────────────────────────────

class SandboxStatus(BaseModel):
    is_sandbox: bool
    sandbox_org_id: str | None    # null if none exists
    production_org_id: str
    demo_stats: dict[str, Any] | None


class SandboxOut(BaseModel):
    sandbox_org_id: str
    message: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status", response_model=SandboxStatus)
async def sandbox_status(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org_id(ctx)
    try:
        org = await _get_org(db, org_id)
        user_id = _user_id(ctx)

        # Find sandbox sibling: an org owned by same user with is_sandbox=True
        sandbox_member = await db.scalar(
            select(OrganizationMember)
            .join(Organization, Organization.id == OrganizationMember.org_id)
            .where(
                OrganizationMember.user_id == user_id,
                Organization.is_sandbox == True,  # noqa: E712
                Organization.id != org_id,
            )
        )

        demo_stats = None
        if sandbox_member:
            sb_org_id = sandbox_member.org_id
            from sqlalchemy import func
            prod_count = (await db.scalar(
                select(func.count(Product.id)).where(Product.org_id == sb_org_id)
            )) or 0
            cust_count = (await db.scalar(
                select(func.count(Customer.id)).where(Customer.org_id == sb_org_id)
            )) or 0
            inv_count = (await db.scalar(
                select(func.count(Invoice.id)).where(Invoice.org_id == sb_org_id)
            )) or 0
            demo_stats = {"products": prod_count, "customers": cust_count, "invoices": inv_count}

        return SandboxStatus(
            is_sandbox=org.is_sandbox,
            sandbox_org_id=str(sandbox_member.org_id) if sandbox_member else None,
            production_org_id=str(org_id),
            demo_stats=demo_stats,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("sandbox_status failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/create", response_model=SandboxOut)
async def create_sandbox(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Create a pre-populated sandbox org for the current user."""
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        # Check not already a sandbox
        prod_org = await _get_org(db, org_id)
        if prod_org.is_sandbox:
            raise HTTPException(status_code=409, detail="You are already inside a sandbox org — switch to production first")

        # Check sandbox doesn't exist yet
        existing = await db.scalar(
            select(OrganizationMember)
            .join(Organization, Organization.id == OrganizationMember.org_id)
            .where(
                OrganizationMember.user_id == user_id,
                Organization.is_sandbox == True,  # noqa: E712
            )
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Sandbox already exists — use POST /api/sandbox/reset to re-seed it",
            )

        # Create sandbox org
        sb_org = Organization(
            name=f"{prod_org.name} [DEMO]",
            base_currency=prod_org.base_currency,
            fiscal_year_start=prod_org.fiscal_year_start,
            is_sandbox=True,
            plan=OrgPlan.PRO,   # demo gets full features
        )
        db.add(sb_org)
        await db.flush()

        # Add current user as owner
        member = OrganizationMember(
            org_id=sb_org.id,
            user_id=user_id,
            role=OrgRole.OWNER,
        )
        db.add(member)
        await db.flush()

        # Seed demo data
        await _seed_demo_data(db, sb_org.id)
        await db.commit()

        return SandboxOut(
            sandbox_org_id=str(sb_org.id),
            message="Sandbox created with demo data. Switch to it from the org selector.",
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_sandbox failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/reset", response_model=SandboxOut)
async def reset_sandbox(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Wipe all transactional data in the sandbox and re-seed with fresh demo data."""
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        # Find sandbox sibling
        sb_member = await db.scalar(
            select(OrganizationMember)
            .join(Organization, Organization.id == OrganizationMember.org_id)
            .where(
                OrganizationMember.user_id == user_id,
                Organization.is_sandbox == True,  # noqa: E712
            )
        )
        if not sb_member:
            raise HTTPException(
                status_code=404,
                detail="No sandbox found — use POST /api/sandbox/create first",
            )

        sb_org_id = sb_member.org_id
        await _wipe_transactional_data(db, sb_org_id)
        await _seed_demo_data(db, sb_org_id)
        await db.commit()

        return SandboxOut(
            sandbox_org_id=str(sb_org_id),
            message="Sandbox reset with fresh demo data.",
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error("reset_sandbox failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("")
async def delete_sandbox(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete the sandbox org and all its data."""
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        sb_member = await db.scalar(
            select(OrganizationMember)
            .join(Organization, Organization.id == OrganizationMember.org_id)
            .where(
                OrganizationMember.user_id == user_id,
                Organization.is_sandbox == True,  # noqa: E712
                Organization.id != org_id,
            )
        )
        if not sb_member:
            raise HTTPException(status_code=404, detail="No sandbox org found")

        sb_org = await db.scalar(
            select(Organization).where(Organization.id == sb_member.org_id)
        )
        if sb_org:
            await db.delete(sb_org)
            await db.commit()
        return {"deleted": True, "sandbox_org_id": str(sb_member.org_id)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_sandbox failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
