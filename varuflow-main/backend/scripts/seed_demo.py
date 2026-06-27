#!/usr/bin/env python3
"""Comprehensive demo data seeder for Varuflow.

Creates a fully-populated demo organisation ("Nilsson & Söner Grossist AB")
with 6 months of realistic transaction history: products, warehouses, stock
movements, customers, suppliers, invoices, POS sessions, and purchase orders.

The resulting dataset makes every screen in the app look live:
 - Dashboard: growing revenue chart, AI insight cards, overdue alerts
 - Inventory: products with varied stock levels, some below minimum
 - Invoices: mix of PAID / SENT / OVERDUE / DRAFT across 6 months
 - Analytics: month-over-month growth visible in charts
 - POS: recent cash-register transactions

Usage (from backend/):
    python scripts/seed_demo.py

Creates a Supabase user  demo@varuflow.se  (password: Demo1234!)
and the matching organisation in the app database.

Environment (.env):
    DATABASE_URL
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from random import Random

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# ── Config ─────────────────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

DEMO_EMAIL    = "demo@varuflow.se"
DEMO_PASSWORD = "Demo1234!"
DEMO_ORG_NAME = "Nilsson & Söner Grossist AB"
DEMO_ORG_NO   = "556601-4422"
DEMO_VAT      = "SE556601442201"
DEMO_ADDRESS  = "Industrivägen 12, 171 48 Stockholm"

rng = Random(42)  # deterministic so the same data generates each run

# ── Product catalogue ──────────────────────────────────────────────────────────

PRODUCTS = [
    # Office Furniture
    {"name": "Skrivbord Ek 140×70 cm",          "sku": "FURN-DESK-140",  "category": "Kontorsmöbler", "sell": 4990,  "cost": 2100, "tax": 25, "unit": "st",   "min_stock": 5,  "stock": 23},
    {"name": "Kontorsstol Ergonomisk Plus",       "sku": "FURN-CHAIR-E",   "category": "Kontorsmöbler", "sell": 3290,  "cost": 1450, "tax": 25, "unit": "st",   "min_stock": 5,  "stock": 11},
    {"name": "Hyllsystem Basic 5-plan",           "sku": "FURN-SHELF-5",   "category": "Kontorsmöbler", "sell": 1890,  "cost":  850, "tax": 25, "unit": "st",   "min_stock": 3,  "stock":  3},  # low stock
    {"name": "Konferensbord Oval 8 pers",         "sku": "FURN-CONF-8",    "category": "Kontorsmöbler", "sell": 8990,  "cost": 3900, "tax": 25, "unit": "st",   "min_stock": 2,  "stock":  4},
    {"name": "Arkivskåp Stål 4 lådor",            "sku": "FURN-CAB-4D",    "category": "Kontorsmöbler", "sell": 2490,  "cost": 1100, "tax": 25, "unit": "st",   "min_stock": 3,  "stock":  8},
    {"name": "Skärmvägg Tyg 180×100 cm",          "sku": "FURN-SCRN-180",  "category": "Kontorsmöbler", "sell": 1490,  "cost":  650, "tax": 25, "unit": "st",   "min_stock": 4,  "stock":  2},  # low stock
    {"name": "Whiteboard 120×90 Magnetisk",       "sku": "FURN-WB-120",    "category": "Kontorsmöbler", "sell":  890,  "cost":  380, "tax": 25, "unit": "st",   "min_stock": 5,  "stock": 17},
    # IT & Electronics
    {"name": "Skärm 27\" 4K IPS",                 "sku": "IT-MON-27K",     "category": "IT & Elektronik","sell": 4290,  "cost": 2100, "tax": 25, "unit": "st",   "min_stock": 5,  "stock": 19},
    {"name": "USB-C Dockningstation 12-port",     "sku": "IT-DOCK-12P",    "category": "IT & Elektronik","sell": 1990,  "cost":  890, "tax": 25, "unit": "st",   "min_stock": 8,  "stock": 34},
    {"name": "Tangentbord Trådlöst SE",           "sku": "IT-KB-WLSE",     "category": "IT & Elektronik","sell":  849,  "cost":  350, "tax": 25, "unit": "st",   "min_stock": 10, "stock": 47},
    {"name": "Mus Ergonomisk Trådlös",            "sku": "IT-MOUSE-WL",    "category": "IT & Elektronik","sell":  549,  "cost":  220, "tax": 25, "unit": "st",   "min_stock": 10, "stock": 52},
    {"name": "Laptop-ställ Aluminium",            "sku": "IT-LSTND-AL",    "category": "IT & Elektronik","sell":  649,  "cost":  250, "tax": 25, "unit": "st",   "min_stock": 8,  "stock": 28},
    {"name": "Webbkamera 4K 60fps",               "sku": "IT-CAM-4K60",    "category": "IT & Elektronik","sell": 1290,  "cost":  560, "tax": 25, "unit": "st",   "min_stock": 5,  "stock":  4},  # low stock
    {"name": "Headset USB-C Noise Cancelling",    "sku": "IT-HS-USNC",     "category": "IT & Elektronik","sell": 1490,  "cost":  640, "tax": 25, "unit": "st",   "min_stock": 5,  "stock": 13},
    {"name": "Kabelkanal Skrivbord 2m",           "sku": "IT-CABLE-2M",    "category": "IT & Elektronik","sell":  299,  "cost":  115, "tax": 25, "unit": "st",   "min_stock": 15, "stock": 61},
    # Office Supplies
    {"name": "A4-papper 80g 500 ark (fp)",        "sku": "SUP-PAPER-A4",   "category": "Kontorsförbrukn","sell":   89,  "cost":   32, "tax": 25, "unit": "fp",   "min_stock": 50, "stock": 210},
    {"name": "Anteckningsbok A5 Hardcover",       "sku": "SUP-NB-A5H",     "category": "Kontorsförbrukn","sell":  149,  "cost":   55, "tax":  6, "unit": "st",   "min_stock": 20, "stock": 88},
    {"name": "Pennor Kulspets Blå (10-pack)",     "sku": "SUP-PEN-B10",    "category": "Kontorsförbrukn","sell":   89,  "cost":   30, "tax":  6, "unit": "förp", "min_stock": 30, "stock": 124},
    {"name": "Pärm A4 50mm Svart",                "sku": "SUP-BINDER-50B", "category": "Kontorsförbrukn","sell":   79,  "cost":   28, "tax": 25, "unit": "st",   "min_stock": 30, "stock": 190},
    {"name": "Etiketter A4 65/ark (pack 25 ark)", "sku": "SUP-LABEL-65",   "category": "Kontorsförbrukn","sell":  149,  "cost":   55, "tax": 25, "unit": "förp", "min_stock": 15, "stock": 73},
    {"name": "Märkpennor Permanent 10-pack",      "sku": "SUP-MARK-10",    "category": "Kontorsförbrukn","sell":  129,  "cost":   48, "tax":  6, "unit": "förp", "min_stock": 20, "stock": 56},
    # Cleaning & Facility
    {"name": "Handdesinfektion 1L (fp 6 st)",     "sku": "FAC-HAND-1L6",   "category": "Facility",      "sell":  390,  "cost":  160, "tax": 25, "unit": "fp",   "min_stock": 20, "stock": 45},
    {"name": "Allrengöring Koncentrat 5L",        "sku": "FAC-CLEAN-5L",   "category": "Facility",      "sell":  249,  "cost":   98, "tax": 25, "unit": "kan",  "min_stock": 10, "stock": 22},
    {"name": "Pappershanddukar Z-fold (250 st)",  "sku": "FAC-TOWEL-250",  "category": "Facility",      "sell":  189,  "cost":   72, "tax": 25, "unit": "fp",   "min_stock": 30, "stock": 112},
    {"name": "Sopkorg Stål 25L",                  "sku": "FAC-BIN-25L",    "category": "Facility",      "sell":  349,  "cost":  145, "tax": 25, "unit": "st",   "min_stock": 5,  "stock": 16},
]

# ── Customers ──────────────────────────────────────────────────────────────────

CUSTOMERS = [
    {"company_name": "Bergström & Partners AB",     "email": "order@bergstrom.se",          "org_number": "556123-4567", "contact": "Anna Bergström",    "phone": "08-123 45 67", "payment_days": 30},
    {"company_name": "Nordic Retail Group AB",      "email": "inkop@nordicretail.se",        "org_number": "559001-2345", "contact": "Johan Lindqvist",   "phone": "031-234 56 78", "payment_days": 30},
    {"company_name": "Göteborgs Handelsskola AB",   "email": "ekonomi@handelsskolan.se",     "org_number": "556789-0123", "contact": "Maria Hansson",     "phone": "031-345 67 89", "payment_days": 45},
    {"company_name": "Svensson & Söner Advokat KB", "email": "faktura@svenssonadv.se",       "org_number": "916401-1234", "contact": "Erik Svensson",     "phone": "08-456 78 90", "payment_days": 30},
    {"company_name": "Pettersson IT AB",            "email": "order@petterssonit.se",        "org_number": "556456-7890", "contact": "Lisa Pettersson",   "phone": "040-123 45 67", "payment_days": 30},
    {"company_name": "Malmö Fastigheter AB",        "email": "drift@malmofastigheter.se",    "org_number": "556321-9876", "contact": "Mikael Ström",      "phone": "040-567 89 01", "payment_days": 45},
    {"company_name": "Uppsala Läkarmottagning AB",  "email": "admin@uppsalaklinik.se",       "org_number": "556654-3210", "contact": "Dr. Sara Nilsson",  "phone": "018-234 56 78", "payment_days": 30},
    {"company_name": "Karlsson Media & Tryck AB",   "email": "inkop@karlssonmedia.se",       "org_number": "556789-1234", "contact": "Peter Karlsson",    "phone": "08-678 90 12", "payment_days": 30},
    {"company_name": "Norrköpings Kommun",          "email": "upphandling@norrkoping.se",    "org_number": "212000-0159", "contact": "Ingrid Johansson",  "phone": "011-123 45 67", "payment_days": 60},
    {"company_name": "Helsingborg Fastighets AB",   "email": "service@hbgfastighet.se",     "org_number": "556901-2345", "contact": "Thomas Persson",    "phone": "042-345 67 89", "payment_days": 30},
]

# ── Suppliers ──────────────────────────────────────────────────────────────────

SUPPLIERS = [
    {"name": "Kinnarps Import AB",       "email": "order@kinnarps-import.se",  "phone": "036-123 45 67", "lead_days": 7},
    {"name": "Nordic Tech Supply AB",    "email": "supply@nordictech.se",      "phone": "08-456 78 90",  "lead_days": 5},
    {"name": "Kontorsförbrukning AB",    "email": "order@kontofsforbrukn.se",  "phone": "031-234 56 78", "lead_days": 3},
    {"name": "Facility Partners Nordic", "email": "sales@facilitypartners.se", "phone": "040-345 67 89", "lead_days": 4},
]

# ── Invoice scenarios (6 months) ───────────────────────────────────────────────
# Generated dynamically in the script — see _build_invoices()

TODAY = date.today()

def _months_ago(n: int) -> date:
    d = TODAY.replace(day=1)
    for _ in range(n):
        if d.month == 1:
            d = d.replace(year=d.year - 1, month=12)
        else:
            d = d.replace(month=d.month - 1)
    return d

def _rand_day_in_month(base: date) -> date:
    import calendar
    _, last = calendar.monthrange(base.year, base.month)
    day = rng.randint(1, last)
    return base.replace(day=day)

# ── Main seeder ────────────────────────────────────────────────────────────────

async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    # 1. Create Supabase user
    user_id = await _create_supabase_user()

    async with async_session() as db:
        # 2. Create org + member
        org_id = await _create_org(db, user_id)

        # 3. Warehouse
        wh_id = await _create_warehouse(db, org_id)

        # 4. Suppliers
        supplier_ids = await _create_suppliers(db, org_id)

        # 5. Products + stock
        product_ids = await _create_products(db, org_id, wh_id, supplier_ids)

        # 6. Customers
        customer_ids = await _create_customers(db, org_id)

        # 7. Invoices (6 months)
        await _create_invoices(db, org_id, customer_ids, product_ids)

        # 8. Stock movements (simulate sell-through)
        await _create_stock_movements(db, org_id, wh_id, product_ids)

        # 9. POS sessions
        await _create_pos_sessions(db, org_id, product_ids)

        # 10. Purchase orders
        await _create_purchase_orders(db, org_id, supplier_ids, product_ids)

        await db.commit()

    await engine.dispose()
    print()
    print("=" * 56)
    print("  Demo organisation created successfully!")
    print("=" * 56)
    print(f"  Email    : {DEMO_EMAIL}")
    print(f"  Password : {DEMO_PASSWORD}")
    print(f"  Org      : {DEMO_ORG_NAME}")
    print()
    print("  Seeded:")
    print(f"    {len(PRODUCTS)} products across 4 categories")
    print(f"    {len(CUSTOMERS)} customers")
    print(f"    {len(SUPPLIERS)} suppliers")
    print(f"    ~60 invoices over 6 months")
    print(f"    stock movements for the last 3 months")
    print(f"    2 POS sessions with walk-in sales")
    print(f"    3 purchase orders (1 DRAFT, 1 SENT, 1 RECEIVED)")
    print("=" * 56)


async def _create_supabase_user() -> uuid.UUID:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        fake_id = uuid.uuid4()
        print(f"[WARN] Supabase credentials not set — using fake user_id {fake_id}")
        return fake_id

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers={"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"},
            json={
                "email": DEMO_EMAIL,
                "password": DEMO_PASSWORD,
                "email_confirm": True,
                "user_metadata": {"full_name": "Demo Admin"},
            },
            timeout=30,
        )
    if r.status_code == 422:
        # User already exists — fetch it
        async with httpx.AsyncClient() as client:
            r2 = await client.get(
                f"{SUPABASE_URL}/auth/v1/admin/users",
                headers={"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"},
                params={"email": DEMO_EMAIL},
                timeout=30,
            )
        data = r2.json()
        users = data.get("users", [])
        if users:
            uid = uuid.UUID(users[0]["id"])
            print(f"[INFO] Supabase user already exists: {uid}")
            return uid
    if r.status_code not in (200, 201):
        print(f"[WARN] Supabase user creation returned {r.status_code}: {r.text[:200]}")
        return uuid.uuid4()

    uid = uuid.UUID(r.json()["id"])
    print(f"[OK] Supabase user created: {uid}")
    return uid


async def _create_org(db: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    from app.features.auth.organization import Organization, OrganizationMember, OrgPlan, OrgRole

    org_id = uuid.uuid4()
    org = Organization(
        id=org_id,
        name=DEMO_ORG_NAME,
        org_number=DEMO_ORG_NO,
        vat_number=DEMO_VAT,
        address=DEMO_ADDRESS,
        plan=OrgPlan.PRO,
        base_currency="SEK",
        fiscal_year_start=1,
        onboarding_wizard_completed=True,
        country_code="SE",
    )
    db.add(org)
    await db.flush()

    member = OrganizationMember(
        org_id=org_id,
        user_id=user_id,
        role=OrgRole.OWNER,
    )
    db.add(member)
    await db.flush()
    print(f"[OK] Organisation: {DEMO_ORG_NAME} ({org_id})")
    return org_id


async def _create_warehouse(db: AsyncSession, org_id: uuid.UUID) -> uuid.UUID:
    from app.features.inventory.models import Warehouse

    wh = Warehouse(
        org_id=org_id,
        name="Lager Stockholm",
        address="Industrivägen 12, 171 48 Stockholm",
    )
    db.add(wh)
    await db.flush()
    print(f"[OK] Warehouse: {wh.name}")
    return wh.id


async def _create_suppliers(db: AsyncSession, org_id: uuid.UUID) -> list[uuid.UUID]:
    from app.features.inventory.models import Supplier

    ids = []
    for s in SUPPLIERS:
        sup = Supplier(
            org_id=org_id,
            name=s["name"],
            email=s["email"],
            phone=s.get("phone"),
        )
        db.add(sup)
        ids.append(sup.id)
    await db.flush()
    print(f"[OK] {len(SUPPLIERS)} suppliers")
    return ids


async def _create_products(
    db: AsyncSession,
    org_id: uuid.UUID,
    wh_id: uuid.UUID,
    supplier_ids: list[uuid.UUID],
) -> list[uuid.UUID]:
    from app.features.inventory.models import Product, StockLevel, StockMovement

    sup_map = {
        "Kontorsmöbler":    supplier_ids[0],
        "IT & Elektronik":  supplier_ids[1],
        "Kontorsförbrukn":  supplier_ids[2],
        "Facility":         supplier_ids[3],
    }

    ids = []
    for p in PRODUCTS:
        prod = Product(
            org_id=org_id,
            name=p["name"],
            sku=p["sku"],
            category=p["category"],
            sell_price=Decimal(str(p["sell"])),
            purchase_price=Decimal(str(p["cost"])),
            tax_rate=Decimal(str(p["tax"])),
            unit=p["unit"],
            min_stock_threshold=p["min_stock"],
            supplier_id=sup_map.get(p["category"]),
        )
        db.add(prod)
        ids.append(prod.id)
    await db.flush()

    # Stock levels + initial IN movements
    for i, p in enumerate(PRODUCTS):
        sl = StockLevel(
            org_id=org_id,
            product_id=ids[i],
            warehouse_id=wh_id,
            quantity=Decimal(str(p["stock"])),
        )
        db.add(sl)

        mv = StockMovement(
            org_id=org_id,
            product_id=ids[i],
            warehouse_id=wh_id,
            movement_type="IN",
            quantity=Decimal(str(p["stock"])),
            reference=f"Opening stock — {TODAY - timedelta(days=180)}",
            created_at=datetime.combine(TODAY - timedelta(days=180), datetime.min.time()).replace(tzinfo=timezone.utc),
        )
        db.add(mv)

    await db.flush()
    print(f"[OK] {len(PRODUCTS)} products with stock levels")
    return ids


async def _create_customers(db: AsyncSession, org_id: uuid.UUID) -> list[uuid.UUID]:
    from app.features.invoicing.models import Customer

    ids = []
    for c in CUSTOMERS:
        cust = Customer(
            org_id=org_id,
            company_name=c["company_name"],
            email=c["email"],
            org_number=c["org_number"],
            contact_person=c.get("contact"),
            phone=c.get("phone"),
            payment_terms=c.get("payment_days", 30),
        )
        db.add(cust)
        ids.append(cust.id)
    await db.flush()
    print(f"[OK] {len(CUSTOMERS)} customers")
    return ids


async def _create_invoices(
    db: AsyncSession,
    org_id: uuid.UUID,
    customer_ids: list[uuid.UUID],
    product_ids: list[uuid.UUID],
) -> None:
    from app.features.invoicing.models import Invoice, InvoiceLineItem, InvoiceStatus, Payment

    # ── 6 months of invoice history ──────────────────────────────────────────
    # Month -5: 7 invoices,  avg ~18 000 SEK  → total ~126 000 SEK
    # Month -4: 9 invoices,  avg ~19 000 SEK  → total ~171 000 SEK
    # Month -3: 11 invoices, avg ~20 500 SEK  → total ~226 000 SEK
    # Month -2: 13 invoices, avg ~21 000 SEK  → total ~273 000 SEK
    # Month -1: 12 invoices, avg ~23 000 SEK  → total ~276 000 SEK
    # Month  0: 8 invoices so far, mix of SENT/DRAFT

    scenarios = []

    # Helper: pick products for a realistic invoice (2–4 line items)
    def _pick_lines(n: int = None) -> list[dict]:
        n = n or rng.randint(2, 4)
        idxs = rng.sample(range(len(PRODUCTS)), k=min(n, len(PRODUCTS)))
        lines = []
        for idx in idxs:
            p = PRODUCTS[idx]
            qty = rng.randint(1, 10)
            lines.append({"product_idx": idx, "qty": qty})
        return lines

    inv_counter = 1

    for month_offset, count, target_status_mix in [
        (5, 7,  {"PAID": 1.0}),                              # 5 months ago — all paid
        (4, 9,  {"PAID": 1.0}),                              # 4 months ago — all paid
        (3, 11, {"PAID": 0.9, "OVERDUE": 0.1}),              # 3 months ago — mostly paid
        (2, 13, {"PAID": 0.85, "OVERDUE": 0.15}),            # 2 months ago — some overdue
        (1, 12, {"PAID": 0.6, "SENT": 0.25, "OVERDUE": 0.15}),  # last month — mix
        (0, 8,  {"SENT": 0.5, "DRAFT": 0.25, "PAID": 0.25}),    # this month — in-flight
    ]:
        base_month = _months_ago(month_offset)
        for _ in range(count):
            issue = _rand_day_in_month(base_month)
            # pick status
            r_val = rng.random()
            cum = 0.0
            status_str = "PAID"
            for s, prob in target_status_mix.items():
                cum += prob
                if r_val <= cum:
                    status_str = s
                    break

            # Don't let future dates become PAID/OVERDUE
            if issue > TODAY:
                status_str = "DRAFT"

            status = InvoiceStatus[status_str]
            payment_terms = CUSTOMERS[rng.randint(0, len(CUSTOMERS) - 1)]["payment_days"]
            due = issue + timedelta(days=payment_terms)
            if status == InvoiceStatus.OVERDUE and due > TODAY:
                due = TODAY - timedelta(days=rng.randint(5, 25))

            cust_id = customer_ids[rng.randint(0, len(customer_ids) - 1)]
            lines = _pick_lines()

            subtotal = Decimal("0")
            vat_total = Decimal("0")
            for line in lines:
                p = PRODUCTS[line["product_idx"]]
                line_ex = Decimal(str(p["sell"])) * line["qty"]
                line_vat = line_ex * Decimal(str(p["tax"])) / 100
                subtotal  += line_ex
                vat_total += line_vat

            total = subtotal + vat_total

            inv_num = f"INV-{inv_counter:04d}"
            inv_counter += 1

            inv = Invoice(
                org_id=org_id,
                customer_id=cust_id,
                invoice_number=inv_num,
                issue_date=issue,
                due_date=due,
                status=status,
                currency="SEK",
                subtotal=subtotal,
                vat_amount=vat_total,
                total_sek=total,
            )
            db.add(inv)
            await db.flush()

            for line in lines:
                p = PRODUCTS[line["product_idx"]]
                line_ex  = Decimal(str(p["sell"])) * line["qty"]
                line_vat = line_ex * Decimal(str(p["tax"])) / 100
                li = InvoiceLineItem(
                    invoice_id=inv.id,
                    description=p["name"],
                    quantity=Decimal(str(line["qty"])),
                    unit_price=Decimal(str(p["sell"])),
                    tax_rate=Decimal(str(p["tax"])),
                    line_total=line_ex + line_vat,
                )
                db.add(li)

            # Add payment for PAID invoices
            if status == InvoiceStatus.PAID:
                paid_date = issue + timedelta(days=rng.randint(5, payment_terms))
                pmt = Payment(
                    org_id=org_id,
                    invoice_id=inv.id,
                    amount=total,
                    payment_date=paid_date,
                    payment_method="bank_transfer",
                    note="Inbetalning banköverföring",
                )
                db.add(pmt)

            scenarios.append(inv_num)

    await db.flush()
    print(f"[OK] {len(scenarios)} invoices generated (6-month history)")


async def _create_stock_movements(
    db: AsyncSession,
    org_id: uuid.UUID,
    wh_id: uuid.UUID,
    product_ids: list[uuid.UUID],
) -> None:
    """Simulate 3 months of realistic OUT movements (sales sell-through)."""
    from app.features.inventory.models import StockMovement

    count = 0
    for days_ago in range(90, 0, -1):
        mv_date = datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time()).replace(tzinfo=timezone.utc)
        # 1–3 product moves per day
        n_moves = rng.randint(1, 3)
        for _ in range(n_moves):
            idx = rng.randint(0, len(product_ids) - 1)
            qty = Decimal(str(rng.randint(1, 5)))
            mv = StockMovement(
                org_id=org_id,
                product_id=product_ids[idx],
                warehouse_id=wh_id,
                movement_type="OUT",
                quantity=qty,
                reference=f"Försäljning {(TODAY - timedelta(days=days_ago)).isoformat()}",
                created_at=mv_date,
            )
            db.add(mv)
            count += 1

    await db.flush()
    print(f"[OK] {count} stock OUT movements (90 days)")


async def _create_pos_sessions(
    db: AsyncSession,
    org_id: uuid.UUID,
    product_ids: list[uuid.UUID],
) -> None:
    """Create 2 POS sessions with walk-in transactions."""
    try:
        from app.features.pos.models import PosSession, PosTransaction
    except ImportError:
        print("[SKIP] POS models not available — skipping POS sessions")
        return

    for session_offset in [7, 1]:
        session_date = TODAY - timedelta(days=session_offset)
        session = PosSession(
            org_id=org_id,
            opened_at=datetime.combine(session_date, datetime.min.time()).replace(tzinfo=timezone.utc, hour=8),
            closed_at=datetime.combine(session_date, datetime.min.time()).replace(tzinfo=timezone.utc, hour=17),
            opening_float=Decimal("2000"),
            closing_float=Decimal(str(2000 + rng.randint(3000, 8000))),
            status="closed",
        )
        db.add(session)
        await db.flush()

        for tx_n in range(rng.randint(8, 14)):
            idx = rng.randint(0, len(product_ids) - 1)
            p = PRODUCTS[idx]
            qty = Decimal(str(rng.randint(1, 3)))
            unit = Decimal(str(p["sell"]))
            total = unit * qty
            tx = PosTransaction(
                org_id=org_id,
                session_id=session.id,
                product_id=product_ids[idx],
                quantity=qty,
                unit_price=unit,
                total_amount=total,
                payment_method=rng.choice(["cash", "card", "swish"]),
                created_at=(
                    datetime.combine(session_date, datetime.min.time())
                    .replace(tzinfo=timezone.utc, hour=rng.randint(9, 16))
                ),
            )
            db.add(tx)

    await db.flush()
    print("[OK] 2 POS sessions with walk-in transactions")


async def _create_purchase_orders(
    db: AsyncSession,
    org_id: uuid.UUID,
    supplier_ids: list[uuid.UUID],
    product_ids: list[uuid.UUID],
) -> None:
    """Create 3 purchase orders: 1 DRAFT, 1 SENT, 1 RECEIVED."""
    try:
        from app.features.inventory.models import PurchaseOrder, PurchaseOrderItem
    except ImportError:
        print("[SKIP] PO models not available — skipping purchase orders")
        return

    po_specs = [
        {"status": "DRAFT",    "days_ago": 2,  "sup_idx": 0, "prod_idxs": [0, 1, 2]},
        {"status": "SENT",     "days_ago": 10, "sup_idx": 1, "prod_idxs": [7, 8, 9]},
        {"status": "RECEIVED", "days_ago": 20, "sup_idx": 2, "prod_idxs": [15, 16, 17]},
    ]

    for i, spec in enumerate(po_specs):
        po = PurchaseOrder(
            org_id=org_id,
            supplier_id=supplier_ids[spec["sup_idx"]],
            po_number=f"PO-{i+1:04d}",
            status=spec["status"],
            order_date=TODAY - timedelta(days=spec["days_ago"]),
            expected_delivery=TODAY + timedelta(days=max(0, 7 - spec["days_ago"])),
        )
        db.add(po)
        await db.flush()

        for pidx in spec["prod_idxs"]:
            p = PRODUCTS[pidx]
            qty = Decimal(str(rng.randint(10, 30)))
            line = PurchaseOrderItem(
                po_id=po.id,
                product_id=product_ids[pidx],
                quantity=qty,
                unit_price=Decimal(str(p["cost"])),
                line_total=qty * Decimal(str(p["cost"])),
            )
            db.add(line)

    await db.flush()
    print("[OK] 3 purchase orders (DRAFT / SENT / RECEIVED)")


if __name__ == "__main__":
    asyncio.run(main())
