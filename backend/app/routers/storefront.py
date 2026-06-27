"""Public storefront router — no auth required.

Endpoints live at /api/shop/... and are safe to call from the browser
without a Supabase session token. Org isolation is enforced via the
storefront slug → org_id mapping; all queries are scoped to that org.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.ecommerce import CartSession, OnlineOrder, OnlineOrderItem, Storefront
from app.models.inventory import Product

log = logging.getLogger(__name__)

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_storefront(slug: str, db: AsyncSession) -> Storefront:
    sf = (
        await db.execute(select(Storefront).where(Storefront.slug == slug))
    ).scalar_one_or_none()
    if not sf or not sf.is_active:
        raise HTTPException(status_code=404, detail="Storefront not found")
    return sf


async def _get_cart(token: str, storefront_id: uuid.UUID, db: AsyncSession) -> CartSession:
    try:
        token_uuid = uuid.UUID(token)
    except ValueError:
        raise HTTPException(status_code=404, detail="Cart not found")
    cart = (
        await db.execute(
            select(CartSession).where(
                CartSession.guest_token == token_uuid,
                CartSession.storefront_id == storefront_id,
                CartSession.recovered_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    return cart


def _order_number() -> str:
    now = datetime.now(timezone.utc)
    suffix = str(uuid.uuid4().int)[:4]
    return f"ORD-{now:%Y%m%d}-{suffix}"


def _item_subtotal(items: list[dict[str, Any]]) -> tuple[Decimal, Decimal]:
    """Return (subtotal_ex_vat, vat_amount)."""
    subtotal = Decimal("0")
    vat = Decimal("0")
    for it in items:
        price = Decimal(str(it["unit_price"]))
        qty = int(it["qty"])
        rate = Decimal(str(it.get("tax_rate", "0.25")))
        line = price * qty
        subtotal += line
        vat += line * rate
    return subtotal, vat


# ── Storefront info ───────────────────────────────────────────────────────────


@router.get("/api/shop/{slug}")
async def get_storefront(slug: str, db: AsyncSession = Depends(get_db)):
    try:
        sf = await _get_storefront(slug, db)
        return {
            "id": str(sf.id),
            "slug": sf.slug,
            "name": sf.name,
            "tagline": sf.tagline,
            "logo_url": sf.logo_url,
            "primary_color": sf.primary_color,
            "currency": sf.currency,
            "payment_methods": sf.payment_methods.split(","),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_storefront failed slug=%s: %s", slug, e)
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Product catalog ───────────────────────────────────────────────────────────


@router.get("/api/shop/{slug}/products")
async def list_products(
    slug: str,
    page: int = 1,
    per_page: int = 24,
    db: AsyncSession = Depends(get_db),
):
    try:
        sf = await _get_storefront(slug, db)
        offset = (page - 1) * per_page
        rows = (
            await db.execute(
                select(Product)
                .where(
                    Product.org_id == sf.org_id,
                    Product.is_active == True,  # noqa: E712
                )
                .offset(offset)
                .limit(per_page)
            )
        ).scalars().all()
        return {
            "items": [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "sku": p.sku,
                    "price": str(p.selling_price) if p.selling_price else None,
                    "image_url": getattr(p, "image_url", None),
                    "slug": getattr(p, "slug", None),
                }
                for p in rows
            ],
            "page": page,
            "per_page": per_page,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_products failed slug=%s: %s", slug, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/shop/{slug}/products/{pid}")
async def get_product(slug: str, pid: uuid.UUID, db: AsyncSession = Depends(get_db)):
    try:
        sf = await _get_storefront(slug, db)
        product = await db.get(Product, pid)
        if not product or product.org_id != sf.org_id or not product.is_active:
            raise HTTPException(status_code=404, detail="Product not found")
        return {
            "id": str(product.id),
            "name": product.name,
            "sku": product.sku,
            "description": getattr(product, "description", None),
            "price": str(product.selling_price) if product.selling_price else None,
            "tax_rate": str(product.tax_rate) if hasattr(product, "tax_rate") and product.tax_rate is not None else "0.25",
            "image_url": getattr(product, "image_url", None),
            "slug": getattr(product, "slug", None),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_product failed pid=%s: %s", pid, e)
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Cart ──────────────────────────────────────────────────────────────────────


@router.post("/api/shop/{slug}/cart", status_code=201)
async def create_cart(slug: str, db: AsyncSession = Depends(get_db)):
    try:
        sf = await _get_storefront(slug, db)
        cart = CartSession(
            org_id=sf.org_id,
            storefront_id=sf.id,
            items=[],
        )
        db.add(cart)
        await db.commit()
        await db.refresh(cart)
        return {"guest_token": str(cart.guest_token), "cart_id": str(cart.id)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_cart failed slug=%s: %s", slug, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/shop/{slug}/cart/{token}")
async def get_cart(slug: str, token: str, db: AsyncSession = Depends(get_db)):
    try:
        sf = await _get_storefront(slug, db)
        cart = await _get_cart(token, sf.id, db)
        return {
            "cart_id": str(cart.id),
            "guest_token": str(cart.guest_token),
            "items": cart.items,
            "customer_email": cart.customer_email,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_cart failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


class AddItemBody(BaseModel):
    product_id: uuid.UUID
    qty: int = 1


@router.post("/api/shop/{slug}/cart/{token}/items", status_code=201)
async def add_item(
    slug: str,
    token: str,
    body: AddItemBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        sf = await _get_storefront(slug, db)
        cart = await _get_cart(token, sf.id, db)

        product = await db.get(Product, body.product_id)
        if not product or product.org_id != sf.org_id or not product.is_active:
            raise HTTPException(status_code=404, detail="Product not found")

        price = product.selling_price or Decimal("0")
        tax_rate = getattr(product, "tax_rate", Decimal("0.25")) or Decimal("0.25")

        items: list[dict] = list(cart.items)
        # Merge with existing line for same product
        for it in items:
            if it.get("product_id") == str(body.product_id):
                it["qty"] = int(it["qty"]) + body.qty
                break
        else:
            items.append({
                "product_id": str(body.product_id),
                "description": product.name,
                "qty": body.qty,
                "unit_price": str(price),
                "tax_rate": str(tax_rate),
            })

        cart.items = items
        cart.last_activity_at = datetime.now(timezone.utc)
        await db.commit()
        return {"items": cart.items}
    except HTTPException:
        raise
    except Exception as e:
        log.error("add_item failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


class UpdateItemBody(BaseModel):
    qty: int


@router.put("/api/shop/{slug}/cart/{token}/items/{product_id}")
async def update_item(
    slug: str,
    token: str,
    product_id: uuid.UUID,
    body: UpdateItemBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        sf = await _get_storefront(slug, db)
        cart = await _get_cart(token, sf.id, db)

        pid_str = str(product_id)
        items: list[dict] = [it for it in cart.items if it.get("product_id") != pid_str]
        if body.qty > 0:
            existing = next((it for it in cart.items if it.get("product_id") == pid_str), None)
            if existing:
                existing["qty"] = body.qty
                items = [it if it.get("product_id") != pid_str else existing for it in cart.items]

        cart.items = items
        cart.last_activity_at = datetime.now(timezone.utc)
        await db.commit()
        return {"items": cart.items}
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_item failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/shop/{slug}/cart/{token}/items/{product_id}", status_code=204)
async def remove_item(
    slug: str,
    token: str,
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    try:
        sf = await _get_storefront(slug, db)
        cart = await _get_cart(token, sf.id, db)
        pid_str = str(product_id)
        cart.items = [it for it in cart.items if it.get("product_id") != pid_str]
        cart.last_activity_at = datetime.now(timezone.utc)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("remove_item failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Checkout ──────────────────────────────────────────────────────────────────


class CheckoutBody(BaseModel):
    customer_name: str
    customer_email: EmailStr
    shipping_address: dict[str, str]


@router.post("/api/shop/{slug}/cart/{token}/checkout")
async def checkout(
    slug: str,
    token: str,
    body: CheckoutBody,
    db: AsyncSession = Depends(get_db),
):
    try:
        sf = await _get_storefront(slug, db)
        cart = await _get_cart(token, sf.id, db)

        if not cart.items:
            raise HTTPException(status_code=400, detail="Cart is empty")

        cart.customer_email = body.customer_email
        cart.checkout_started_at = datetime.now(timezone.utc)
        cart.last_activity_at = datetime.now(timezone.utc)
        await db.commit()

        if not settings.STRIPE_SECRET_KEY:
            raise HTTPException(status_code=503, detail="Stripe not configured")

        stripe.api_key = settings.STRIPE_SECRET_KEY

        line_items = []
        for it in cart.items:
            price_cents = int(Decimal(str(it["unit_price"])) * 100)
            line_items.append({
                "price_data": {
                    "currency": sf.currency.lower(),
                    "unit_amount": price_cents,
                    "product_data": {"name": it["description"]},
                },
                "quantity": int(it["qty"]),
            })

        payment_method_types = [m.strip() for m in sf.payment_methods.split(",") if m.strip()]

        session = stripe.checkout.Session.create(
            mode="payment",
            currency=sf.currency.lower(),
            payment_method_types=payment_method_types,
            line_items=line_items,
            customer_email=body.customer_email,
            metadata={
                "cart_token": token,
                "org_id": str(sf.org_id),
                "storefront_id": str(sf.id),
                "customer_name": body.customer_name,
                "shipping_address": str(body.shipping_address),
                "slug": slug,
            },
            success_url=f"{settings.FRONTEND_URL}/shop/{slug}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/shop/{slug}/cart",
        )

        return {"checkout_url": session.url}
    except HTTPException:
        raise
    except stripe.StripeError as e:
        log.error("Stripe checkout error slug=%s: %s", slug, e)
        raise HTTPException(status_code=502, detail="Payment provider error")
    except Exception as e:
        log.error("checkout failed slug=%s: %s", slug, e)
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Stripe webhook ────────────────────────────────────────────────────────────


@router.post("/api/shop/webhooks/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not settings.STRIPE_STOREFRONT_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_STOREFRONT_WEBHOOK_SECRET
        )
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] != "checkout.session.completed":
        return {"received": True}

    session_data = event["data"]["object"]
    meta = session_data.get("metadata", {})
    cart_token_str = meta.get("cart_token")
    org_id_str = meta.get("org_id")
    storefront_id_str = meta.get("storefront_id")
    customer_name = meta.get("customer_name", "")
    slug = meta.get("slug", "")

    if not cart_token_str or not org_id_str or not storefront_id_str:
        log.warning("stripe_webhook: missing metadata in session %s", session_data.get("id"))
        return {"received": True}

    # Idempotency check
    stripe_session_id = session_data.get("id", "")
    existing = (
        await db.execute(
            select(OnlineOrder).where(
                OnlineOrder.stripe_checkout_session_id == stripe_session_id
            )
        )
    ).scalar_one_or_none()
    if existing:
        return {"received": True}

    try:
        cart_token_uuid = uuid.UUID(cart_token_str)
        cart = (
            await db.execute(
                select(CartSession).where(CartSession.guest_token == cart_token_uuid)
            )
        ).scalar_one_or_none()

        if not cart:
            log.warning("stripe_webhook: cart not found token=%s", cart_token_str)
            return {"received": True}

        # Build shipping address from metadata string (best-effort)
        shipping_address: dict = {}
        try:
            import ast
            shipping_address = ast.literal_eval(meta.get("shipping_address", "{}"))
        except Exception:
            pass

        subtotal, vat_amount = _item_subtotal(cart.items)
        total = subtotal + vat_amount

        order = OnlineOrder(
            org_id=uuid.UUID(org_id_str),
            storefront_id=uuid.UUID(storefront_id_str),
            order_number=_order_number(),
            status="CONFIRMED",
            customer_email=session_data.get("customer_email") or cart.customer_email or "",
            customer_name=customer_name,
            shipping_address=shipping_address,
            subtotal=subtotal,
            vat_amount=vat_amount,
            total=total,
            stripe_checkout_session_id=stripe_session_id,
            stripe_payment_intent_id=session_data.get("payment_intent"),
            payment_method=session_data.get("payment_method_types", ["card"])[0],
            confirmed_at=datetime.now(timezone.utc),
        )
        db.add(order)
        await db.flush()

        for it in cart.items:
            db.add(OnlineOrderItem(
                order_id=order.id,
                product_id=uuid.UUID(it["product_id"]) if it.get("product_id") else None,
                description=it["description"],
                quantity=int(it["qty"]),
                unit_price=Decimal(str(it["unit_price"])),
                tax_rate=Decimal(str(it.get("tax_rate", "0.25"))),
                line_total=Decimal(str(it["unit_price"])) * int(it["qty"]),
            ))

        cart.recovered_at = datetime.now(timezone.utc)

        await db.commit()

        # Send confirmation email
        try:
            from app.services.email import send_order_confirmation_storefront
            sf = await db.get(Storefront, order.storefront_id)
            shop_url = f"{settings.FRONTEND_URL}/shop/{slug}"
            await send_order_confirmation_storefront(
                to_email=order.customer_email,
                customer_name=order.customer_name,
                order_number=order.order_number,
                items=cart.items,
                total=str(total),
                currency=sf.currency if sf else "SEK",
                shop_name=sf.name if sf else "Shop",
                shop_url=shop_url,
            )
        except Exception:
            log.exception("order_confirmation email failed for order %s", order.id)

    except Exception:
        log.exception("stripe_webhook processing failed session=%s", stripe_session_id)

    return {"received": True}
