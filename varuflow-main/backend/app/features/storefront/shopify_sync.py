"""Shopify + WooCommerce sync

Shopify: Private App API key (X-Shopify-Access-Token header)
WooCommerce: consumer key + secret (HTTP Basic auth)

Endpoints:
  POST /api/integrations/shopify/connect
  DELETE /api/integrations/shopify/disconnect
  GET  /api/integrations/shopify/status
  POST /api/integrations/shopify/sync-orders
  POST /api/integrations/shopify/sync-inventory
  POST /api/integrations/shopify/webhook        (no auth — Shopify HMAC in header)

  POST /api/integrations/woocommerce/connect
  DELETE /api/integrations/woocommerce/disconnect
  GET  /api/integrations/woocommerce/status
  POST /api/integrations/woocommerce/sync-orders
  POST /api/integrations/woocommerce/sync-inventory
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_plan
from app.features.integrations.models import IntegrationConfig
from app.features.invoicing.models import Customer, Invoice, InvoiceLineItem, InvoiceStatus
from app.features.inventory.models import Product, StockLevel
from app.features.auth.organization import OrgPlan

router = APIRouter(tags=["integrations_ecommerce"])
log = logging.getLogger(__name__)

SHOPIFY_API_VERSION = "2024-01"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


async def _get_config(db: AsyncSession, org_id: uuid.UUID, provider: str) -> Optional[IntegrationConfig]:
    row = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.org_id == org_id,
            IntegrationConfig.provider == provider,
        )
    )
    return row.scalar_one_or_none()


async def _upsert_customer(db: AsyncSession, org_id: uuid.UUID, company_name: str) -> Customer:
    """Find or create a customer by company_name (email is encrypted, cannot query by it)."""
    row = await db.execute(
        select(Customer).where(
            Customer.org_id == org_id,
            Customer.company_name == company_name,
        )
    )
    customer = row.scalar_one_or_none()
    if not customer:
        customer = Customer(org_id=org_id, company_name=company_name)
        db.add(customer)
        await db.flush()
    return customer


async def _import_shopify_order(
    db: AsyncSession,
    org_id: uuid.UUID,
    order: dict,
    currency: str,
) -> tuple[bool, str]:
    """Import a single Shopify order as Varuflow Invoice. Returns (imported, invoice_number)."""
    order_number = str(order.get("order_number", order.get("id", "")))
    inv_number = f"SHO-{order_number}"

    existing = await db.execute(
        select(Invoice).where(
            Invoice.org_id == org_id,
            Invoice.invoice_number == inv_number,
        )
    )
    if existing.scalar_one_or_none():
        return False, inv_number

    customer_name = (
        order.get("billing_address", {}).get("company")
        or order.get("customer", {}).get("default_address", {}).get("company")
        or order.get("email", "Shopify Customer")
        or "Shopify Customer"
    )
    customer = await _upsert_customer(db, org_id, customer_name)

    subtotal = Decimal(str(order.get("subtotal_price", "0")))
    total_tax = Decimal(str(order.get("total_tax", "0")))
    total = Decimal(str(order.get("total_price", "0")))

    created_at_str = order.get("created_at", "")
    try:
        issue_date = datetime.fromisoformat(created_at_str.replace("Z", "+00:00")).date()
    except Exception:
        issue_date = datetime.now(timezone.utc).date()

    status_map = {
        "paid": InvoiceStatus.PAID,
        "pending": InvoiceStatus.SENT,
        "refunded": InvoiceStatus.CANCELLED,
        "voided": InvoiceStatus.CANCELLED,
    }
    fin_status = order.get("financial_status", "pending")
    inv_status = status_map.get(fin_status, InvoiceStatus.SENT)

    invoice = Invoice(
        org_id=org_id,
        customer_id=customer.id,
        invoice_number=inv_number,
        status=inv_status,
        issue_date=issue_date,
        currency=currency,
        subtotal=subtotal,
        vat_amount=total_tax,
        total_sek=total,
        notes=f"Imported from Shopify order #{order_number}",
    )
    db.add(invoice)
    await db.flush()

    for line in order.get("line_items", []):
        qty = Decimal(str(line.get("quantity", 1)))
        price = Decimal(str(line.get("price", "0")))
        li = InvoiceLineItem(
            invoice_id=invoice.id,
            description=line.get("title", "Shopify item"),
            quantity=qty,
            unit_price=price,
            tax_rate=Decimal("0"),
            line_total=qty * price,
        )
        db.add(li)

    return True, inv_number


async def _import_woo_order(
    db: AsyncSession,
    org_id: uuid.UUID,
    order: dict,
    currency: str,
) -> tuple[bool, str]:
    """Import a single WooCommerce order as Varuflow Invoice."""
    order_id = str(order.get("id", ""))
    inv_number = f"WOO-{order_id}"

    existing = await db.execute(
        select(Invoice).where(
            Invoice.org_id == org_id,
            Invoice.invoice_number == inv_number,
        )
    )
    if existing.scalar_one_or_none():
        return False, inv_number

    billing = order.get("billing", {})
    company_name = billing.get("company") or f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip() or "WooCommerce Customer"
    customer = await _upsert_customer(db, org_id, company_name)

    subtotal = sum(Decimal(str(li.get("subtotal", "0"))) for li in order.get("line_items", []))
    total_tax = Decimal(str(order.get("total_tax", "0")))
    total = Decimal(str(order.get("total", "0")))

    date_str = order.get("date_created", "")
    try:
        issue_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
    except Exception:
        issue_date = datetime.now(timezone.utc).date()

    status_map = {
        "completed": InvoiceStatus.PAID,
        "processing": InvoiceStatus.SENT,
        "pending": InvoiceStatus.SENT,
        "cancelled": InvoiceStatus.CANCELLED,
        "refunded": InvoiceStatus.CANCELLED,
    }
    inv_status = status_map.get(order.get("status", "pending"), InvoiceStatus.SENT)

    invoice = Invoice(
        org_id=org_id,
        customer_id=customer.id,
        invoice_number=inv_number,
        status=inv_status,
        issue_date=issue_date,
        currency=currency,
        subtotal=subtotal,
        vat_amount=total_tax,
        total_sek=total,
        notes=f"Imported from WooCommerce order #{order_id}",
    )
    db.add(invoice)
    await db.flush()

    for line in order.get("line_items", []):
        qty = Decimal(str(line.get("quantity", 1)))
        price = Decimal(str(line.get("price", "0")))
        li = InvoiceLineItem(
            invoice_id=invoice.id,
            description=line.get("name", "WooCommerce item"),
            quantity=qty,
            unit_price=price,
            tax_rate=Decimal("0"),
            line_total=qty * price,
        )
        db.add(li)

    return True, inv_number


# ── Schemas ───────────────────────────────────────────────────────────────────

class ShopifyConnectIn(BaseModel):
    store_url: str   # e.g. my-store.myshopify.com
    access_token: str
    api_secret: Optional[str] = None  # Shopify API secret key — used to verify webhook HMAC signatures

class WooConnectIn(BaseModel):
    store_url: str   # full URL e.g. https://mystore.com
    consumer_key: str
    consumer_secret: str

class SyncResult(BaseModel):
    imported: int
    skipped: int
    errors: int
    message: str

class StatusOut(BaseModel):
    provider: str
    connected: bool
    store_url: Optional[str]
    is_active: bool
    last_sync_at: Optional[str]
    last_sync_status: Optional[str]
    last_error: Optional[str]


# ── Shopify endpoints ─────────────────────────────────────────────────────────

@router.post("/api/integrations/shopify/connect")
async def shopify_connect(
    body: ShopifyConnectIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org(ctx)
    try:
        # Validate credentials by calling /shop.json
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://{body.store_url}/admin/api/{SHOPIFY_API_VERSION}/shop.json",
                headers={"X-Shopify-Access-Token": body.access_token},
            )
        if resp.status_code == 401:
            raise HTTPException(status_code=422, detail="Invalid Shopify access token")
        if resp.status_code != 200:
            raise HTTPException(status_code=422, detail=f"Shopify credential check failed: {resp.status_code}")

        shopify_config: dict = {"store_url": body.store_url, "access_token": body.access_token}
        if body.api_secret:
            shopify_config["api_secret"] = body.api_secret

        cfg = await _get_config(db, org_id, "shopify")
        if cfg:
            cfg.config = shopify_config
            cfg.is_active = True
        else:
            cfg = IntegrationConfig(
                org_id=org_id,
                provider="shopify",
                config=shopify_config,
            )
            db.add(cfg)
        await db.commit()
        return {"connected": True, "store_url": body.store_url}
    except HTTPException:
        raise
    except Exception as e:
        log.error("shopify_connect failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/integrations/shopify/disconnect")
async def shopify_disconnect(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "shopify")
        if cfg:
            cfg.is_active = False
            cfg.config = {}
            await db.commit()
        return {"disconnected": True}
    except Exception as e:
        log.error("shopify_disconnect failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/integrations/shopify/status", response_model=StatusOut)
async def shopify_status(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "shopify")
        if not cfg:
            return StatusOut(provider="shopify", connected=False, store_url=None, is_active=False,
                             last_sync_at=None, last_sync_status=None, last_error=None)
        return StatusOut(
            provider="shopify",
            connected=cfg.is_active,
            store_url=cfg.config.get("store_url") if cfg.config else None,
            is_active=cfg.is_active,
            last_sync_at=cfg.last_sync_at.isoformat() if cfg.last_sync_at else None,
            last_sync_status=cfg.last_sync_status,
            last_error=cfg.last_error,
        )
    except Exception as e:
        log.error("shopify_status failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/integrations/shopify/sync-orders", response_model=SyncResult)
async def shopify_sync_orders(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "shopify")
        if not cfg or not cfg.is_active:
            raise HTTPException(status_code=422, detail="Shopify not connected")

        store_url = cfg.config.get("store_url")
        access_token = cfg.config.get("access_token")
        imported = skipped = errors = 0

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"https://{store_url}/admin/api/{SHOPIFY_API_VERSION}/orders.json",
                params={"status": "any", "limit": 50},
                headers={"X-Shopify-Access-Token": access_token},
            )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Shopify API error: {resp.status_code}")

        orders = resp.json().get("orders", [])
        currency = resp.json().get("orders", [{}])[0].get("currency", "SEK") if orders else "SEK"

        for order in orders:
            try:
                ok, _ = await _import_shopify_order(db, org_id, order, currency)
                if ok:
                    imported += 1
                else:
                    skipped += 1
            except Exception:
                errors += 1

        cfg.last_sync_at = datetime.now(timezone.utc)
        cfg.last_sync_status = "success" if errors == 0 else "partial"
        await db.commit()

        return SyncResult(imported=imported, skipped=skipped, errors=errors,
                          message=f"Synced {imported} new orders, {skipped} already imported")
    except HTTPException:
        raise
    except Exception as e:
        log.error("shopify_sync_orders failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/integrations/shopify/sync-inventory", response_model=SyncResult)
async def shopify_sync_inventory(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "shopify")
        if not cfg or not cfg.is_active:
            raise HTTPException(status_code=422, detail="Shopify not connected")

        store_url = cfg.config.get("store_url")
        access_token = cfg.config.get("access_token")

        # Get Shopify products to build SKU→inventory_item_id map
        async with httpx.AsyncClient(timeout=30) as client:
            prod_resp = await client.get(
                f"https://{store_url}/admin/api/{SHOPIFY_API_VERSION}/products.json",
                params={"limit": 250},
                headers={"X-Shopify-Access-Token": access_token},
            )
        if prod_resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Shopify API error: {prod_resp.status_code}")

        shopify_products = prod_resp.json().get("products", [])
        sku_map: dict[str, tuple[str, str]] = {}  # sku → (inventory_item_id, location_id)
        location_id = None

        # Get location ID
        async with httpx.AsyncClient(timeout=10) as client:
            loc_resp = await client.get(
                f"https://{store_url}/admin/api/{SHOPIFY_API_VERSION}/locations.json",
                headers={"X-Shopify-Access-Token": access_token},
            )
        if loc_resp.status_code == 200:
            locs = loc_resp.json().get("locations", [])
            if locs:
                location_id = str(locs[0]["id"])

        for prod in shopify_products:
            for variant in prod.get("variants", []):
                sku = variant.get("sku", "")
                if sku:
                    sku_map[sku] = (str(variant.get("inventory_item_id", "")), location_id or "")

        # Get Varuflow products with stock levels
        varuflow_prods = await db.execute(
            select(Product.id, Product.sku, StockLevel.quantity)
            .join(StockLevel, StockLevel.product_id == Product.id, isouter=True)
            .where(Product.org_id == org_id, Product.sku.isnot(None))
        )
        pushed = skipped = errors = 0

        async with httpx.AsyncClient(timeout=30) as client:
            for prod_id, sku, qty in varuflow_prods:
                if not sku or sku not in sku_map:
                    skipped += 1
                    continue
                inv_item_id, loc_id = sku_map[sku]
                if not inv_item_id or not loc_id:
                    skipped += 1
                    continue
                try:
                    r = await client.post(
                        f"https://{store_url}/admin/api/{SHOPIFY_API_VERSION}/inventory_levels/set.json",
                        json={"location_id": int(loc_id), "inventory_item_id": int(inv_item_id), "available": int(qty or 0)},
                        headers={"X-Shopify-Access-Token": access_token, "Content-Type": "application/json"},
                    )
                    if r.status_code == 200:
                        pushed += 1
                    else:
                        errors += 1
                except Exception:
                    errors += 1

        cfg.last_sync_at = datetime.now(timezone.utc)
        cfg.last_sync_status = "success" if errors == 0 else "partial"
        await db.commit()

        return SyncResult(imported=pushed, skipped=skipped, errors=errors,
                          message=f"Pushed {pushed} inventory levels to Shopify")
    except HTTPException:
        raise
    except Exception as e:
        log.error("shopify_sync_inventory failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


def _verify_shopify_hmac(body: bytes, hmac_header: str, secret: str) -> bool:
    """Return True only when the Shopify-supplied HMAC matches the computed digest."""
    if not secret or not hmac_header:
        return False
    digest = base64.b64encode(
        hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    ).decode("utf-8")
    return hmac.compare_digest(digest, hmac_header)


@router.post("/api/integrations/shopify/webhook", status_code=200)
async def shopify_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive Shopify ORDER_CREATED webhook (auth-free — Shopify signs with HMAC-SHA256)."""
    try:
        raw_body = await request.body()

        # Shopify sends X-Shopify-Shop-Domain header to identify which store
        shop_domain = request.headers.get("X-Shopify-Shop-Domain", "")
        hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")

        if not shop_domain:
            return {"received": False}

        # Find org by store_url in IntegrationConfig
        row = await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.provider == "shopify",
                IntegrationConfig.is_active == True,  # noqa: E712
            )
        )
        cfg = None
        for c in row.scalars():
            if c.config and c.config.get("store_url", "") in (shop_domain, shop_domain.replace("https://", "")):
                cfg = c
                break

        if not cfg:
            log.warning("shopify_webhook: no matching org for shop %s", shop_domain)
            return {"received": True}

        # Verify HMAC signature using the stored API secret for this integration.
        # The secret is stored under config["api_secret"] when the app is installed.
        # Reject the request outright if we have a secret and the signature is wrong.
        api_secret = cfg.config.get("api_secret", "") if cfg.config else ""
        if api_secret:
            if not _verify_shopify_hmac(raw_body, hmac_header, api_secret):
                log.warning(
                    "shopify_webhook: HMAC mismatch for shop %s — request rejected",
                    shop_domain,
                )
                return {"received": False}
        else:
            # No secret stored — legacy connection. Log a warning so operators
            # know to re-connect and store the API secret.
            log.warning(
                "shopify_webhook: no api_secret stored for shop %s — skipping HMAC verification. "
                "Reconnect the Shopify integration to enable signature validation.",
                shop_domain,
            )

        import json
        payload = json.loads(raw_body)
        currency = payload.get("currency", "SEK")
        ok, inv_number = await _import_shopify_order(db, cfg.org_id, payload, currency)
        if ok:
            await db.commit()
            log.info("shopify_webhook: imported order %s", inv_number)

        return {"received": True}
    except Exception as e:
        log.error("shopify_webhook failed: %s", str(e))
        return {"received": False}


# ── WooCommerce endpoints ──────────────────────────────────────────────────────

@router.post("/api/integrations/woocommerce/connect")
async def woo_connect(
    body: WooConnectIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org(ctx)
    try:
        store = body.store_url.rstrip("/")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{store}/wp-json/wc/v3/system_status",
                auth=(body.consumer_key, body.consumer_secret),
            )
        if resp.status_code == 401:
            raise HTTPException(status_code=422, detail="Invalid WooCommerce credentials")
        if resp.status_code not in (200, 404):  # 404 on /system_status is OK (permissions)
            raise HTTPException(status_code=422, detail=f"WooCommerce credential check failed: {resp.status_code}")

        cfg = await _get_config(db, org_id, "woocommerce")
        creds = {"store_url": store, "consumer_key": body.consumer_key, "consumer_secret": body.consumer_secret}
        if cfg:
            cfg.config = creds
            cfg.is_active = True
        else:
            cfg = IntegrationConfig(org_id=org_id, provider="woocommerce", config=creds)
            db.add(cfg)
        await db.commit()
        return {"connected": True, "store_url": store}
    except HTTPException:
        raise
    except Exception as e:
        log.error("woo_connect failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/integrations/woocommerce/disconnect")
async def woo_disconnect(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "woocommerce")
        if cfg:
            cfg.is_active = False
            cfg.config = {}
            await db.commit()
        return {"disconnected": True}
    except Exception as e:
        log.error("woo_disconnect failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/integrations/woocommerce/status", response_model=StatusOut)
async def woo_status(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "woocommerce")
        if not cfg:
            return StatusOut(provider="woocommerce", connected=False, store_url=None, is_active=False,
                             last_sync_at=None, last_sync_status=None, last_error=None)
        return StatusOut(
            provider="woocommerce",
            connected=cfg.is_active,
            store_url=cfg.config.get("store_url") if cfg.config else None,
            is_active=cfg.is_active,
            last_sync_at=cfg.last_sync_at.isoformat() if cfg.last_sync_at else None,
            last_sync_status=cfg.last_sync_status,
            last_error=cfg.last_error,
        )
    except Exception as e:
        log.error("woo_status failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/integrations/woocommerce/sync-orders", response_model=SyncResult)
async def woo_sync_orders(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "woocommerce")
        if not cfg or not cfg.is_active:
            raise HTTPException(status_code=422, detail="WooCommerce not connected")

        store = cfg.config.get("store_url")
        auth = (cfg.config.get("consumer_key"), cfg.config.get("consumer_secret"))
        imported = skipped = errors = 0

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{store}/wp-json/wc/v3/orders",
                params={"per_page": 50, "orderby": "date", "order": "desc"},
                auth=auth,
            )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"WooCommerce API error: {resp.status_code}")

        orders = resp.json()
        currency = orders[0].get("currency", "SEK") if orders else "SEK"

        for order in orders:
            try:
                ok, _ = await _import_woo_order(db, org_id, order, currency)
                if ok:
                    imported += 1
                else:
                    skipped += 1
            except Exception:
                errors += 1

        cfg.last_sync_at = datetime.now(timezone.utc)
        cfg.last_sync_status = "success" if errors == 0 else "partial"
        await db.commit()

        return SyncResult(imported=imported, skipped=skipped, errors=errors,
                          message=f"Synced {imported} new WooCommerce orders")
    except HTTPException:
        raise
    except Exception as e:
        log.error("woo_sync_orders failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/integrations/woocommerce/sync-inventory", response_model=SyncResult)
async def woo_sync_inventory(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    _plan=Depends(require_plan(OrgPlan.PRO)),
):
    org_id = _org(ctx)
    try:
        cfg = await _get_config(db, org_id, "woocommerce")
        if not cfg or not cfg.is_active:
            raise HTTPException(status_code=422, detail="WooCommerce not connected")

        store = cfg.config.get("store_url")
        auth = (cfg.config.get("consumer_key"), cfg.config.get("consumer_secret"))

        # Get WooCommerce products
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{store}/wp-json/wc/v3/products",
                params={"per_page": 100, "type": "simple"},
                auth=auth,
            )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"WooCommerce API error: {resp.status_code}")

        woo_products = {p.get("sku", ""): p["id"] for p in resp.json() if p.get("sku")}

        varuflow_prods = await db.execute(
            select(Product.id, Product.sku, StockLevel.quantity)
            .join(StockLevel, StockLevel.product_id == Product.id, isouter=True)
            .where(Product.org_id == org_id, Product.sku.isnot(None))
        )
        pushed = skipped = errors = 0

        async with httpx.AsyncClient(timeout=30) as client:
            for _, sku, qty in varuflow_prods:
                if not sku or sku not in woo_products:
                    skipped += 1
                    continue
                woo_id = woo_products[sku]
                try:
                    r = await client.put(
                        f"{store}/wp-json/wc/v3/products/{woo_id}",
                        json={"stock_quantity": int(qty or 0), "manage_stock": True},
                        auth=auth,
                    )
                    if r.status_code == 200:
                        pushed += 1
                    else:
                        errors += 1
                except Exception:
                    errors += 1

        cfg.last_sync_at = datetime.now(timezone.utc)
        cfg.last_sync_status = "success" if errors == 0 else "partial"
        await db.commit()

        return SyncResult(imported=pushed, skipped=skipped, errors=errors,
                          message=f"Pushed {pushed} stock levels to WooCommerce")
    except HTTPException:
        raise
    except Exception as e:
        log.error("woo_sync_inventory failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
