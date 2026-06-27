"""B2B Customer Portal — magic-link auth and invoice access.

POST /api/portal/auth/magic-link   — request a login link (no auth required)
GET  /api/portal/auth/verify       — exchange token for portal JWT
POST /api/portal/auth/logout       — revoke current portal session
GET  /api/portal/invoices          — list customer's invoices
GET  /api/portal/invoices/{id}     — invoice detail
GET  /api/portal/invoices/{id}/pdf — download PDF
GET  /api/portal/catalogue         — product catalogue + per-customer prices
POST /api/portal/orders            — place a self-service order (Feature 13)
GET  /api/portal/orders            — customer's order history
"""
import hashlib
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.features.customers.customer_price_override import CustomerPriceOverride
from app.features.inventory.models import (
    Product,
    StockLevel,
    StockMovement,
    StockMovementType,
    Warehouse,
)
from app.features.invoicing.models import (
    Customer,
    CustomerPortalToken,
    Invoice,
    InvoiceLineItem,
    InvoiceStatus,
)
from app.features.auth.organization import Organization
from .portal_session import PortalSession
from app.features.invoicing.router import _generate_invoice_pdf, _invoice_number
from app.features.invoicing.schemas import InvoiceOut, InvoiceSummary
from app.services.audit import log_action
from app.services.email import (
    send_internal_order_notification_email,
    send_magic_link_email,
    send_order_confirmation_email,
    send_portal_otp_email,
)

router = APIRouter(prefix="/api/portal", tags=["portal"])

_bearer = HTTPBearer(auto_error=True)

_ALGORITHM = "HS256"
# Magic-link token (used once to exchange for a portal JWT): 15 min
_TOKEN_EXPIRY_MINUTES = 15
# Portal JWT session: 24 h. The portal is a long-lived passwordless session
# for B2B customers — shorter than a week (which invited too-easy token theft
# from shared devices) but long enough to view an invoice + pay later the
# same day. If a customer needs longer access, they request another magic link.
_JWT_EXPIRY_HOURS = 24


def _hash_magic_token(raw: str) -> str:
    """SHA-256 of the raw magic-link token. Only the hash is persisted so a
    DB leak cannot be used to log in as any customer."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ── Schemas ──────────────────────────────────────────────────────────────────

class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkResponse(BaseModel):
    status: str
    # Only populated in dev (Resend not configured)
    dev_magic_url: str | None = None


class VerifyResponse(BaseModel):
    portal_token: str
    customer_name: str
    org_name: str


# ── Portal JWT helpers ────────────────────────────────────────────────────────

async def _issue_portal_jwt(
    db: AsyncSession,
    customer_id: uuid.UUID,
    org_id: uuid.UUID,
) -> str:
    """Mint a portal JWT and register it in ``portal_sessions``.

    The jti (JWT ID) claim is the link between the signed token and the
    session row we persist. On every subsequent request we resolve the
    jti to its row and reject the call if the row is missing, expired,
    or revoked. This makes portal JWTs revocable and blocks replay of
    forged tokens (see ``_decode_portal_jwt`` + ``get_portal_customer``).
    """
    jti = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=_JWT_EXPIRY_HOURS)
    db.add(PortalSession(
        jti=jti,
        customer_id=customer_id,
        org_id=org_id,
        expires_at=exp,
    ))
    await db.commit()
    return jwt.encode(
        {
            "sub": str(customer_id),
            "org_id": str(org_id),
            "type": "portal",
            "jti": jti,
            "exp": exp,
        },
        settings.PORTAL_JWT_SECRET,
        algorithm=_ALGORITHM,
    )


def _decode_portal_jwt(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.PORTAL_JWT_SECRET,
            algorithms=[_ALGORITHM],
            options={"verify_aud": False},
        )
        if payload.get("type") != "portal":
            raise ValueError("Not a portal token")
        return payload
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired portal session")


async def get_portal_customer(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> tuple[uuid.UUID, uuid.UUID]:
    """Dependency: returns (customer_id, org_id) from portal JWT."""
    payload = _decode_portal_jwt(credentials.credentials)

    # Guard the UUID casts. _decode_portal_jwt validates the signature
    # and the `type` claim, but a token with missing or non-UUID sub /
    # org_id would otherwise raise KeyError / ValueError and 500 the
    # request — easily triggered by any self-signed token that happens
    # to share our PORTAL_JWT_SECRET (e.g. a dev token replayed to prod).
    try:
        customer_id = uuid.UUID(str(payload["sub"]))
        org_id = uuid.UUID(str(payload["org_id"]))
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid or expired portal session")

    # Replay prevention: the jti must resolve to a live portal_sessions
    # row. Tokens issued before v21 won't carry a jti — reject those too
    # so a leaked pre-v21 token cannot outlive the rollout.
    jti = payload.get("jti")
    if not jti or not isinstance(jti, str):
        raise HTTPException(status_code=401, detail="Invalid or expired portal session")

    now = datetime.now(timezone.utc)
    session = await db.scalar(
        select(PortalSession).where(PortalSession.jti == jti)
    )
    if (
        session is None
        or session.revoked_at is not None
        or session.expires_at.replace(tzinfo=timezone.utc) < now
        or session.customer_id != customer_id
        or session.org_id != org_id
    ):
        raise HTTPException(status_code=401, detail="Invalid or expired portal session")

    # Touch last_seen_at in a fire-and-forget UPDATE; we don't need it to
    # succeed for the request, so we don't await a commit here — the
    # trailing get_db() dependency will flush when the request ends.
    await db.execute(
        update(PortalSession)
        .where(PortalSession.id == session.id)
        .values(last_seen_at=now)
    )

    customer = await db.get(Customer, customer_id)
    if not customer or not customer.is_active or customer.org_id != org_id:
        raise HTTPException(status_code=401, detail="Customer not found or inactive")

    return customer_id, org_id


# ── Auth endpoints ────────────────────────────────────────────────────────────

@router.post("/auth/magic-link", response_model=MagicLinkResponse)
async def request_magic_link(
    body: MagicLinkRequest,
    db: AsyncSession = Depends(get_db),
):
    """Find customer(s) by email and send a magic login link to each match.

    The same email address can belong to different customers in different
    organisations (a buyer who orders from multiple Nordic wholesalers on
    Varuflow). Every matching customer is entitled to a portal for their
    own org, so we iterate all matches rather than picking one and
    silently sending only one of them. The previous code used
    `scalar_one_or_none()` which RAISED `MultipleResultsFound` (500)
    as soon as two orgs shared a customer email — a trivial way for one
    tenant's customer signup to DoS another tenant's portal login.
    """
    # Customer.email is stored lowercased on every write path (CustomerCreate
    # normalizes via field_validator, Fortnox import calls .lower() too).
    # Pydantic's EmailStr does NOT lowercase, so a portal user typing
    # "Foo@Bar.com" would silently miss the row stored as "foo@bar.com" and
    # never receive their magic link. Normalize before the lookup so case
    # doesn't lock anyone out of their own portal.
    email_norm = body.email.strip().lower()
    # Hard cap: if the same email somehow belongs to hundreds of orgs
    # (bulk-import accident), we don't want a single /auth/magic-link
    # POST to spray hundreds of outbound emails. 10 is far more than
    # any legitimate buyer would use.
    result = await db.execute(
        select(Customer)
        .where(Customer.email == email_norm, Customer.is_active == True)  # noqa: E712
        .limit(10)
    )
    customers = result.scalars().all()

    # Always return OK to avoid email enumeration.
    if not customers:
        return MagicLinkResponse(status="sent")

    dev_urls: list[str] = []
    from app.features.auth.organization import Organization
    for customer in customers:
        # Per-customer throttle: if an unused, non-expired magic-link token
        # was issued in the last 60 seconds, silently skip creating another
        # one. Protects the customer's inbox from an attacker who knows
        # their email and spams the endpoint, and prevents unbounded DB
        # rows.
        recent_cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
        recent = await db.scalar(
            select(CustomerPortalToken.id).where(
                CustomerPortalToken.customer_id == customer.id,
                CustomerPortalToken.used == False,  # noqa: E712
                CustomerPortalToken.created_at >= recent_cutoff,
            ).limit(1)
        )
        if recent:
            continue

        raw_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=_TOKEN_EXPIRY_MINUTES)

        portal_token = CustomerPortalToken(
            customer_id=customer.id,
            org_id=customer.org_id,
            token=_hash_magic_token(raw_token),
            expires_at=expires_at,
        )
        db.add(portal_token)
        await db.commit()

        magic_url = f"{settings.PORTAL_BASE_URL}/portal/auth/verify?token={raw_token}"

        org = await db.get(Organization, customer.org_id)
        org_name = org.name if org else "Varuflow"

        sent = await send_magic_link_email(
            to_email=customer.email,
            customer_name=customer.company_name,
            magic_url=magic_url,
            org_name=org_name,
        )
        if not sent:
            dev_urls.append(magic_url)

    # In dev (Resend not configured), return the first URL directly so
    # devs can test. We only surface the first to avoid leaking multi-
    # org presence when several customers happen to share the email.
    return MagicLinkResponse(
        status="sent",
        dev_magic_url=dev_urls[0] if dev_urls else None,
    )


@router.get("/auth/verify", response_model=VerifyResponse)
async def verify_magic_link(
    token: str = Query(...),
    request: Request = None,  # noqa: B008
    db: AsyncSession = Depends(get_db),
):
    """Exchange a magic-link token for a portal JWT."""
    now = datetime.now(timezone.utc)

    token_hash = _hash_magic_token(token)
    result = await db.execute(
        select(CustomerPortalToken)
        .options(selectinload(CustomerPortalToken.customer))
        .where(CustomerPortalToken.token == token_hash)
        # Lock the token row so two concurrent verifies cannot both observe
        # `used=False` and both issue a portal JWT (TOCTOU race).
        .with_for_update()
    )
    pt = result.scalar_one_or_none()

    # Replay detection: if the token exists but is already used, this is
    # an explicit replay attempt (someone captured the magic URL from an
    # email forward, proxy log, or browser history). Log the audit event
    # before the 400 so incident response can see when + which customer.
    if pt is not None and pt.used:
        try:
            await log_action(
                db,
                action="PORTAL_MAGIC_LINK_REPLAY",
                org_id=pt.org_id,
                actor_user_id=None,
                target_type="customer",
                target_id=str(pt.customer_id),
                request=request,
                extra={"token_id": str(pt.id)},
            )
            await db.commit()
        except Exception:
            await db.rollback()

    if not pt or pt.used or pt.expires_at.replace(tzinfo=timezone.utc) < now:
        raise HTTPException(status_code=400, detail="Invalid or expired link")

    pt.used = True
    await db.commit()

    from app.features.auth.organization import Organization
    org = await db.get(Organization, pt.org_id)
    org_name = org.name if org else "Varuflow"

    portal_jwt = await _issue_portal_jwt(db, pt.customer_id, pt.org_id)
    return VerifyResponse(
        portal_token=portal_jwt,
        customer_name=pt.customer.company_name,
        org_name=org_name,
    )


@router.post("/auth/logout")
async def portal_logout(
    ctx: tuple = Depends(get_portal_customer),
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
):
    """Revoke the current portal session.

    We re-decode the presented token to extract its jti (already
    validated by ``get_portal_customer``) and stamp ``revoked_at`` on
    the matching row. Subsequent requests with the same JWT will fail
    the session lookup and get a 401.
    """
    payload = _decode_portal_jwt(credentials.credentials)
    jti = payload.get("jti")
    if jti:
        await db.execute(
            update(PortalSession)
            .where(PortalSession.jti == jti, PortalSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await db.commit()
    return {"status": "revoked"}


# ── Invoice endpoints ─────────────────────────────────────────────────────────

@router.get("/invoices", response_model=list[InvoiceSummary])
async def list_portal_invoices(
    ctx: tuple = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    customer_id, org_id = ctx
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer))
        .where(Invoice.customer_id == customer_id, Invoice.org_id == org_id)
        .where(Invoice.status != InvoiceStatus.DRAFT)
        .order_by(Invoice.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
async def get_portal_invoice(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(
            Invoice.id == invoice_id,
            Invoice.customer_id == customer_id,
            Invoice.org_id == org_id,
            Invoice.status != InvoiceStatus.DRAFT,
        )
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


@router.get("/invoices/{invoice_id}/pdf")
async def download_portal_invoice_pdf(
    invoice_id: uuid.UUID,
    ctx: tuple = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(
            Invoice.id == invoice_id,
            Invoice.customer_id == customer_id,
            Invoice.org_id == org_id,
            Invoice.status != InvoiceStatus.DRAFT,
        )
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    pdf_bytes = _generate_invoice_pdf(inv)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{inv.invoice_number}.pdf"'},
    )


# ── Self-service catalogue + ordering (Feature 13) ────────────────────────────

class CatalogueItem(BaseModel):
    product_id: str
    name: str
    sku: str
    unit: str
    price: Decimal
    price_is_override: bool
    stock_available: int
    image_url: str | None = None
    description: str | None = None


class CatalogueResponse(BaseModel):
    org_name: str
    ordering_enabled: bool
    items: list[CatalogueItem]


@router.get("/catalogue", response_model=CatalogueResponse)
async def get_portal_catalogue(
    ctx: tuple = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(200, ge=1, le=500),
):
    """Return the product catalogue visible to the calling portal customer.

    Prices:
        * base ``products.sell_price``
        * overridden by ``customer_price_overrides`` when a negotiated
          price exists for this specific customer

    Stock:
        * sum of ``stock_levels.quantity`` across every warehouse in the
          org minus any outstanding RESERVED movements — the same figure
          a second customer trying to order the last unit would see.
    """
    customer_id, org_id = ctx

    customer = await db.get(Customer, customer_id)
    org = await db.get(Organization, org_id)
    org_name = org.name if org else "Varuflow"

    # Price overrides keyed by product_id for O(1) lookup in the loop.
    override_rows = (await db.execute(
        select(CustomerPriceOverride.product_id, CustomerPriceOverride.override_price)
        .where(
            CustomerPriceOverride.org_id == org_id,
            CustomerPriceOverride.customer_id == customer_id,
        )
    )).all()
    overrides: dict[uuid.UUID, Decimal] = {
        r.product_id: Decimal(r.override_price) for r in override_rows
    }

    stock_rows = (await db.execute(
        select(
            StockLevel.product_id,
            func.coalesce(func.sum(StockLevel.quantity), 0).label("qty"),
        )
        .where(StockLevel.org_id == org_id)
        .group_by(StockLevel.product_id)
    )).all()
    stock_by_product: dict[uuid.UUID, int] = {
        r.product_id: int(r.qty or 0) for r in stock_rows
    }

    # Subtract outstanding RESERVED movements. A reservation is a soft
    # decrement: the stock_levels row isn't yet touched (admin still
    # needs to confirm/ship), so we net it out here instead.
    reserved_rows = (await db.execute(
        select(
            StockMovement.product_id,
            func.coalesce(func.sum(StockMovement.quantity), 0).label("qty"),
        )
        .where(
            StockMovement.org_id == org_id,
            StockMovement.type == StockMovementType.RESERVED,
        )
        .group_by(StockMovement.product_id)
    )).all()
    reserved_by_product: dict[uuid.UUID, int] = {
        r.product_id: int(r.qty or 0) for r in reserved_rows
    }

    product_rows = (await db.execute(
        select(Product)
        .where(Product.org_id == org_id, Product.is_active == True)  # noqa: E712
        .order_by(Product.name.asc())
        .limit(limit)
    )).scalars().all()

    items: list[CatalogueItem] = []
    for p in product_rows:
        override = overrides.get(p.id)
        price = override if override is not None else p.sell_price
        on_hand = stock_by_product.get(p.id, 0)
        reserved = reserved_by_product.get(p.id, 0)
        items.append(CatalogueItem(
            product_id=str(p.id),
            name=p.name,
            sku=p.sku,
            unit=p.unit,
            price=Decimal(price).quantize(Decimal("0.01")),
            price_is_override=override is not None,
            stock_available=max(0, on_hand - reserved),
            # Image URLs are not persisted yet; leave None so the frontend
            # can render a placeholder without schema churn.
            image_url=None,
            description=p.description,
        ))

    return CatalogueResponse(
        org_name=org_name,
        ordering_enabled=bool(customer and customer.portal_ordering_enabled),
        items=items,
    )


# ── Orders ────────────────────────────────────────────────────────────────────

class OrderLineIn(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(..., ge=1, le=10_000)


class OrderRequest(BaseModel):
    # Small hard cap so a malformed cart can't OOM us or create a
    # thousand-line DRAFT invoice in one shot.
    lines: list[OrderLineIn] = Field(..., min_length=1, max_length=50)
    notes: str | None = Field(default=None, max_length=500)


class OrderLineOut(BaseModel):
    product_id: str
    description: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class OrderResponse(BaseModel):
    order_number: str         # == invoice_number of the DRAFT invoice
    invoice_id: str
    status: str               # "pending" — see _invoice_status_to_order_status
    total_sek: Decimal
    lines: list[OrderLineOut]


class OrderHistoryItem(BaseModel):
    order_number: str
    invoice_id: str
    status: str
    total_sek: Decimal
    created_at: datetime


def _invoice_status_to_order_status(status: InvoiceStatus) -> str:
    """Translate invoice lifecycle into user-facing order lifecycle.

    DRAFT    → "pending"    (seller still reviewing the portal order)
    SENT     → "confirmed"  (invoice issued, goods typically shipped)
    PAID     → "invoiced"   (fulfilment complete + paid)
    OVERDUE  → "invoiced"   (surface the invoiced step; payment status is
                             visible on the invoice itself)
    """
    if status == InvoiceStatus.DRAFT:
        return "pending"
    if status == InvoiceStatus.SENT:
        return "confirmed"
    return "invoiced"


@router.post("/orders", response_model=OrderResponse, status_code=201)
async def place_portal_order(
    body: OrderRequest,
    request: Request,
    ctx: tuple = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    """Create a DRAFT invoice + RESERVED stock movements for a portal order.

    The DRAFT invoice is the source of truth for the order. The seller
    reviews it, adjusts pricing if needed, then sends it — at which
    point the normal invoice lifecycle takes over. We don't touch
    ``stock_levels.quantity`` here because the admin still needs to
    confirm shipment; instead we write ``RESERVED`` movements so the
    catalogue endpoint shows an accurate "available" figure to the
    next customer.
    """
    customer_id, org_id = ctx

    customer = await db.get(Customer, customer_id)
    if customer is None or not customer.is_active:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not customer.portal_ordering_enabled:
        # Explicit 403 distinct from the 401 the auth layer would return,
        # so the frontend can show a "ordering disabled for your account"
        # message instead of forcing a logout.
        raise HTTPException(
            status_code=403,
            detail="Portal ordering is not enabled for this customer",
        )

    # Load every requested product in one round-trip and reject unknowns.
    product_ids = [ln.product_id for ln in body.lines]
    if len(set(product_ids)) != len(product_ids):
        raise HTTPException(status_code=400, detail="Duplicate product_id in order")

    products = (await db.execute(
        select(Product)
        .where(Product.id.in_(product_ids), Product.org_id == org_id, Product.is_active == True)  # noqa: E712
    )).scalars().all()
    by_id = {p.id: p for p in products}
    if len(by_id) != len(product_ids):
        raise HTTPException(status_code=400, detail="One or more products not found")

    # Price overrides for this customer.
    override_rows = (await db.execute(
        select(CustomerPriceOverride.product_id, CustomerPriceOverride.override_price)
        .where(
            CustomerPriceOverride.org_id == org_id,
            CustomerPriceOverride.customer_id == customer_id,
        )
    )).all()
    overrides = {r.product_id: Decimal(r.override_price) for r in override_rows}

    # Pick one warehouse (deterministically, by name) as the reservation
    # target. Multi-warehouse splitting is an admin-side concern we
    # intentionally defer — warehouse allocation is visible on the DRAFT
    # invoice for the seller to adjust before shipping.
    warehouse = (await db.execute(
        select(Warehouse)
        .where(Warehouse.org_id == org_id, Warehouse.is_active == True)  # noqa: E712
        .order_by(Warehouse.name.asc())
        .limit(1)
    )).scalar_one_or_none()
    if warehouse is None:
        raise HTTPException(
            status_code=409,
            detail="This organisation has no active warehouse configured",
        )

    # Allocate a fresh invoice number: INV-YYYY-NNNN for the org's
    # current year, using the same generator as the main invoicing
    # router so the number space stays coherent.
    year_prefix = f"INV-{datetime.now(timezone.utc).year}-"
    last = await db.scalar(
        select(func.max(Invoice.invoice_number))
        .where(
            Invoice.org_id == org_id,
            Invoice.invoice_number.like(f"{year_prefix}%"),
        )
    )
    next_seq = 1
    if last:
        try:
            next_seq = int(str(last).rsplit("-", 1)[1]) + 1
        except (IndexError, ValueError):
            next_seq = 1
    order_number = _invoice_number(org_id, next_seq)

    # Build line items + running totals.
    today = date.today()
    lines_out: list[OrderLineOut] = []
    subtotal = Decimal("0.00")
    vat_total = Decimal("0.00")

    invoice = Invoice(
        org_id=org_id,
        customer_id=customer_id,
        invoice_number=order_number,
        issue_date=today,
        due_date=today + timedelta(days=customer.payment_terms_days or 30),
        status=InvoiceStatus.DRAFT,
        subtotal=Decimal("0.00"),
        vat_amount=Decimal("0.00"),
        total_sek=Decimal("0.00"),
        notes=body.notes,
    )
    db.add(invoice)
    await db.flush()  # need invoice.id before inserting line items

    for ln in body.lines:
        product = by_id[ln.product_id]
        unit_price = overrides.get(product.id, Decimal(product.sell_price))
        qty = Decimal(ln.quantity)
        line_total = (unit_price * qty).quantize(Decimal("0.01"))
        vat_rate = Decimal(product.tax_rate or Decimal("25.00"))
        line_vat = (line_total * vat_rate / Decimal("100")).quantize(Decimal("0.01"))
        subtotal += line_total
        vat_total += line_vat

        db.add(InvoiceLineItem(
            invoice_id=invoice.id,
            product_id=product.id,
            description=product.name,
            quantity=qty,
            unit_price=unit_price,
            tax_rate=vat_rate,
            line_total=line_total,
        ))
        # RESERVED stock movement — positive quantity means "this many
        # units are earmarked against a draft order". The catalogue
        # endpoint subtracts the sum of RESERVED movements from on-hand
        # stock. Reversing a reservation (e.g. order cancelled) is a
        # matter of inserting an equal-magnitude ADJUSTMENT or deleting
        # the RESERVED row — that flow lives on the admin side.
        db.add(StockMovement(
            org_id=org_id,
            product_id=product.id,
            warehouse_id=warehouse.id,
            type=StockMovementType.RESERVED,
            quantity=ln.quantity,
            reference=order_number,
            note=f"Portal order by {customer.company_name}",
        ))
        lines_out.append(OrderLineOut(
            product_id=str(product.id),
            description=product.name,
            quantity=ln.quantity,
            unit_price=unit_price.quantize(Decimal("0.01")),
            line_total=line_total,
        ))

    total_sek = (subtotal + vat_total).quantize(Decimal("0.01"))
    invoice.subtotal = subtotal.quantize(Decimal("0.01"))
    invoice.vat_amount = vat_total.quantize(Decimal("0.01"))
    invoice.total_sek = total_sek

    await log_action(
        db,
        action="ORDER_PLACED_BY_PORTAL",
        org_id=org_id,
        actor_user_id=None,
        target_type="invoice",
        target_id=str(invoice.id),
        request=request,
        extra={
            "customer_id": str(customer_id),
            "order_number": order_number,
            "total_sek": str(total_sek),
            "line_count": len(body.lines),
        },
    )
    await db.commit()

    # Best-effort email notifications. Failures are logged inside the
    # email helper and must not bubble up — the order has already been
    # committed and the customer should see a success response.
    try:
        org = await db.get(Organization, org_id)
        org_name = org.name if org else "Varuflow"
        email_lines = [
            {
                "description": ln.description,
                "quantity": str(ln.quantity),
                "unit_price": str(ln.unit_price),
                "line_total": str(ln.line_total),
            }
            for ln in lines_out
        ]
        if customer.email:
            await send_order_confirmation_email(
                to_email=customer.email,
                customer_name=customer.company_name,
                order_number=order_number,
                total_sek=str(total_sek),
                lines=email_lines,
                org_name=org_name,
            )
        if org and org.orders_notification_email:
            await send_internal_order_notification_email(
                to_email=org.orders_notification_email,
                org_name=org_name,
                customer_name=customer.company_name,
                order_number=order_number,
                total_sek=str(total_sek),
                lines=email_lines,
            )
        # v25 — push the same signal to any owners/admins who installed
        # the mobile app. Separate from email so either channel can be
        # configured independently; both are best-effort.
        from app.services.push import send_to_org_members
        from app.features.auth.organization import OrgRole
        await send_to_org_members(
            db,
            org_id=org_id,
            event="portal_order",
            title="Ny order",
            body=f"{customer.company_name} lade order {order_number}",
            data={
                "type": "portal_order",
                "order_number": order_number,
                "invoice_id": str(invoice.id),
            },
            roles=[OrgRole.OWNER, OrgRole.ADMIN],
        )
    except Exception:  # noqa: BLE001
        # Never fail the order because the mail host hiccuped.
        pass

    return OrderResponse(
        order_number=order_number,
        invoice_id=str(invoice.id),
        status=_invoice_status_to_order_status(InvoiceStatus.DRAFT),
        total_sek=total_sek,
        lines=lines_out,
    )


@router.get("/orders", response_model=list[OrderHistoryItem])
async def list_portal_orders(
    ctx: tuple = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
):
    """Order history for the logged-in portal customer.

    Orders are just invoices — DRAFT is "pending", SENT is "confirmed",
    PAID/OVERDUE are "invoiced". Surfaced as a leaner shape than the
    full invoice detail so the orders-list page can render quickly.
    """
    customer_id, org_id = ctx
    rows = (await db.execute(
        select(Invoice)
        .where(
            Invoice.customer_id == customer_id,
            Invoice.org_id == org_id,
        )
        .order_by(Invoice.created_at.desc())
        .limit(limit)
    )).scalars().all()

    return [
        OrderHistoryItem(
            order_number=inv.invoice_number,
            invoice_id=str(inv.id),
            status=_invoice_status_to_order_status(inv.status),
            total_sek=Decimal(inv.total_sek).quantize(Decimal("0.01")),
            created_at=inv.created_at,
        )
        for inv in rows
    ]


class ReorderLine(BaseModel):
    product_id: str
    quantity: int


@router.get("/orders/{invoice_id}/lines", response_model=list[ReorderLine])
async def get_order_lines(
    invoice_id: str,
    ctx: tuple = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    """Return the line items of a past order so the customer can reorder.

    Only returns lines for invoices that belong to the logged-in customer.
    """
    customer_id, org_id = ctx
    try:
        inv_uuid = uuid.UUID(invoice_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Order not found")

    invoice = (await db.execute(
        select(Invoice).where(
            Invoice.id == inv_uuid,
            Invoice.customer_id == customer_id,
            Invoice.org_id == org_id,
        )
    )).scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Order not found")

    lines = (await db.execute(
        select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice.id)
    )).scalars().all()

    return [
        ReorderLine(product_id=str(line.product_id), quantity=int(line.quantity))
        for line in lines
        if line.product_id is not None
    ]


# ── OTP second factor (Item 51) ─────────────────────────────────────────────
#
# An alternative login path to magic-link: the customer requests a
# 6-digit code via POST /auth/otp/request, then submits it via
# POST /auth/otp/verify to receive a portal JWT. Codes are:
#
#   * 6 digits, generated via secrets.randbelow
#   * SHA-256 hashed at rest (never the raw code)
#   * valid for 5 minutes
#   * max 5 verify attempts before the code is marked consumed
#   * one live code per customer — re-requesting invalidates the prior
#
# The request endpoint is rate-limited per-email via the 60-sec cooldown
# baked into the pure service; and the verify endpoint logs an audit
# event on every success / replay / exhaustion.

from .portal_otp import PortalOtpToken
from app.services import portal_otp as otp_svc


class OtpRequestBody(BaseModel):
    email: EmailStr


class OtpRequestResponse(BaseModel):
    status: str = "sent"
    dev_code: str | None = None


class OtpVerifyBody(BaseModel):
    email: EmailStr
    code: str


@router.post("/auth/otp/request", response_model=OtpRequestResponse)
async def request_portal_otp(
    body: OtpRequestBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Issue a 6-digit OTP to the customer's email.

    Returns ``status=sent`` regardless of match (email enumeration
    defense). Silently skips when a live code was issued in the last
    60 seconds. In dev (no RESEND_API_KEY) the code is returned in
    the response body for testing.
    """
    email_norm = body.email.strip().lower()
    result = await db.execute(
        select(Customer)
        .where(Customer.email == email_norm, Customer.is_active == True)  # noqa: E712
        .limit(10)
    )
    customers = result.scalars().all()
    if not customers:
        return OtpRequestResponse(status="sent")

    dev_code: str | None = None
    now = datetime.now(timezone.utc)
    from app.features.auth.organization import Organization

    for customer in customers:
        # Cooldown: if a live un-consumed code exists and was created
        # within the cooldown window, skip issuing another.
        recent = await db.scalar(
            select(PortalOtpToken)
            .where(
                PortalOtpToken.customer_id == customer.id,
                PortalOtpToken.consumed == False,  # noqa: E712
            )
            .order_by(PortalOtpToken.created_at.desc())
            .limit(1)
        )
        if recent and not otp_svc.can_resend(
            recent.created_at.replace(tzinfo=timezone.utc), now
        ):
            continue

        # Invalidate any live codes for this customer (one-code-at-a-time).
        await db.execute(
            update(PortalOtpToken)
            .where(
                PortalOtpToken.customer_id == customer.id,
                PortalOtpToken.consumed == False,  # noqa: E712
            )
            .values(consumed=True, used_at=now)
        )

        issued = otp_svc.issue_otp(now)
        db.add(PortalOtpToken(
            customer_id=customer.id,
            org_id=customer.org_id,
            code_hash=issued.code_hash,
            channel="email",
            expires_at=issued.expires_at,
        ))
        await db.commit()

        try:
            await log_action(
                db,
                action="portal_otp.sent",
                org_id=customer.org_id,
                actor_user_id=None,
                target_type="customer",
                target_id=str(customer.id),
                request=request,
                extra={},
            )
            await db.commit()
        except Exception:
            await db.rollback()

        org = await db.get(Organization, customer.org_id)
        org_name = org.name if org else "Varuflow"
        sent = await send_portal_otp_email(
            to_email=email_norm,
            customer_name=customer.company_name,
            code=issued.code,
            expires_in_seconds=otp_svc.OTP_TTL_SECONDS,
            org_name=org_name,
        )
        if not sent and dev_code is None:
            dev_code = issued.code

    return OtpRequestResponse(status="sent", dev_code=dev_code)


@router.post("/auth/otp/verify", response_model=VerifyResponse)
async def verify_portal_otp(
    body: OtpVerifyBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Verify OTP code and issue a portal JWT."""
    email_norm = body.email.strip().lower()
    code = (body.code or "").strip()
    if not code.isdigit() or len(code) != otp_svc.OTP_DIGITS:
        raise HTTPException(status_code=400, detail="Invalid code")

    now = datetime.now(timezone.utc)

    # Look up all customers with this email, then find the most recent
    # live token for any of them. Same multi-org handling as magic-link.
    result = await db.execute(
        select(Customer)
        .where(Customer.email == email_norm, Customer.is_active == True)  # noqa: E712
        .limit(10)
    )
    customers = {c.id: c for c in result.scalars().all()}
    if not customers:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    token_row = await db.scalar(
        select(PortalOtpToken)
        .where(
            PortalOtpToken.customer_id.in_(list(customers.keys())),
            PortalOtpToken.consumed == False,  # noqa: E712
        )
        .order_by(PortalOtpToken.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if token_row is None:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    customer = customers.get(token_row.customer_id)
    if customer is None:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    if otp_svc.is_expired(
        token_row.expires_at.replace(tzinfo=timezone.utc), now
    ):
        token_row.consumed = True
        token_row.used_at = now
        await db.commit()
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    if otp_svc.attempts_exhausted(token_row.attempts):
        token_row.consumed = True
        token_row.used_at = now
        await db.commit()
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    if not otp_svc.verify_code(code, token_row.code_hash):
        token_row.attempts += 1
        await db.commit()
        try:
            await log_action(
                db,
                action="portal_otp.failed",
                org_id=token_row.org_id,
                actor_user_id=None,
                target_type="customer",
                target_id=str(customer.id),
                request=request,
                extra={"attempts": token_row.attempts},
            )
            await db.commit()
        except Exception:
            await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    # Success — consume the token (replay protection) then mint JWT.
    token_row.consumed = True
    token_row.used_at = now
    await db.commit()

    try:
        await log_action(
            db,
            action="portal_otp.verified",
            org_id=token_row.org_id,
            actor_user_id=None,
            target_type="customer",
            target_id=str(customer.id),
            request=request,
            extra={},
        )
        await db.commit()
    except Exception:
        await db.rollback()

    from app.features.auth.organization import Organization
    org = await db.get(Organization, customer.org_id)
    org_name = org.name if org else "Varuflow"
    portal_jwt = await _issue_portal_jwt(db, customer.id, customer.org_id)
    return VerifyResponse(
        portal_token=portal_jwt,
        customer_name=customer.company_name,
        org_name=org_name,
    )


# ── Portal Communication endpoints ────────────────────────────────────────────
from .models import (
    PortalChatMessage, OrderTimelineEvent, InvoiceViewEvent,
    PortalTicket, PortalTicketReply,
)


# Chat
@router.get("/chat")
async def portal_chat_list(
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    rows = (await db.execute(
        select(PortalChatMessage)
        .where(PortalChatMessage.org_id == org_id, PortalChatMessage.customer_id == customer_id)
        .order_by(PortalChatMessage.created_at.asc())
        .limit(200)
    )).scalars().all()
    return [{"id": str(m.id), "sender_type": m.sender_type, "body": m.body, "read_at": m.read_at.isoformat() if m.read_at else None, "created_at": m.created_at.isoformat()} for m in rows]


class ChatMessageIn(BaseModel):
    body: str


@router.post("/chat", status_code=201)
async def portal_chat_send(
    body: ChatMessageIn,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    msg = PortalChatMessage(org_id=org_id, customer_id=customer_id, sender_type="customer", body=body.body)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return {"id": str(msg.id), "sender_type": "customer", "body": msg.body, "created_at": msg.created_at.isoformat()}


# Timeline
@router.get("/timeline")
async def portal_timeline(
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    rows = (await db.execute(
        select(OrderTimelineEvent)
        .where(OrderTimelineEvent.org_id == org_id, OrderTimelineEvent.customer_id == customer_id)
        .order_by(OrderTimelineEvent.occurred_at.desc())
        .limit(100)
    )).scalars().all()
    return [{"id": str(e.id), "event_type": e.event_type, "title": e.title, "description": e.description, "occurred_at": e.occurred_at.isoformat(), "invoice_id": str(e.invoice_id) if e.invoice_id else None} for e in rows]


@router.get("/timeline/{invoice_id}")
async def portal_timeline_for_invoice(
    invoice_id: str,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    rows = (await db.execute(
        select(OrderTimelineEvent)
        .where(OrderTimelineEvent.org_id == org_id, OrderTimelineEvent.customer_id == customer_id, OrderTimelineEvent.invoice_id == uuid.UUID(invoice_id))
        .order_by(OrderTimelineEvent.occurred_at.asc())
    )).scalars().all()
    return [{"id": str(e.id), "event_type": e.event_type, "title": e.title, "description": e.description, "occurred_at": e.occurred_at.isoformat()} for e in rows]


# Invoice viewed
@router.post("/invoices/{invoice_id}/viewed", status_code=201)
async def portal_invoice_viewed(
    invoice_id: str,
    request: Request,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    evt = InvoiceViewEvent(
        org_id=org_id, invoice_id=uuid.UUID(invoice_id), customer_id=customer_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", "")[:500],
    )
    db.add(evt)
    await db.commit()
    return {"ok": True}


# Tickets
@router.get("/tickets")
async def portal_tickets_list(
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    rows = (await db.execute(
        select(PortalTicket)
        .where(PortalTicket.org_id == org_id, PortalTicket.customer_id == customer_id)
        .order_by(PortalTicket.created_at.desc())
    )).scalars().all()
    return [{"id": str(t.id), "subject": t.subject, "status": t.status, "priority": t.priority, "created_at": t.created_at.isoformat()} for t in rows]


class TicketIn(BaseModel):
    subject: str
    description: str | None = None


@router.post("/tickets", status_code=201)
async def portal_ticket_create(
    body: TicketIn,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    ticket = PortalTicket(org_id=org_id, customer_id=customer_id, subject=body.subject, description=body.description)
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return {"id": str(ticket.id), "subject": ticket.subject, "status": ticket.status, "created_at": ticket.created_at.isoformat()}


@router.get("/tickets/{ticket_id}")
async def portal_ticket_detail(
    ticket_id: str,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    ticket = (await db.execute(
        select(PortalTicket).where(PortalTicket.id == uuid.UUID(ticket_id), PortalTicket.org_id == org_id, PortalTicket.customer_id == customer_id)
    )).scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    await db.refresh(ticket, ["replies"])
    replies = [{"id": str(r.id), "sender_type": r.sender_type, "body": r.body, "created_at": r.created_at.isoformat()} for r in (ticket.replies or [])]
    return {"id": str(ticket.id), "subject": ticket.subject, "description": ticket.description, "status": ticket.status, "priority": ticket.priority, "created_at": ticket.created_at.isoformat(), "replies": replies}


class ReplyIn(BaseModel):
    body: str


@router.post("/tickets/{ticket_id}/reply", status_code=201)
async def portal_ticket_reply(
    ticket_id: str,
    body: ReplyIn,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    ticket = (await db.execute(
        select(PortalTicket).where(PortalTicket.id == uuid.UUID(ticket_id), PortalTicket.org_id == org_id, PortalTicket.customer_id == customer_id)
    )).scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    reply = PortalTicketReply(ticket_id=ticket.id, sender_type="customer", body=body.body)
    db.add(reply)
    await db.commit()
    await db.refresh(reply)
    return {"id": str(reply.id), "sender_type": "customer", "body": reply.body, "created_at": reply.created_at.isoformat()}


# ── Self-Service: Profile ──────────────────────────────────────────────────────
from app.features.invoicing.models import Customer, Invoice, Payment


@router.get("/profile")
async def portal_profile(
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    c = await db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {
        "id": str(c.id), "company_name": c.company_name,
        "email": c.email, "phone": c.phone, "address": c.address,
        "org_number": c.org_number, "vat_number": c.vat_number,
    }


class ProfilePatch(BaseModel):
    email: str | None = None
    phone: str | None = None
    address: str | None = None


@router.patch("/profile")
async def portal_update_profile(
    body: ProfilePatch,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    c = await db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    if body.email is not None:
        c.email = body.email
    if body.phone is not None:
        c.phone = body.phone
    if body.address is not None:
        c.address = body.address
    await db.commit()
    return {"ok": True}


# ── Self-Service: Statements ───────────────────────────────────────────────────

@router.get("/statements")
async def portal_statements(
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    invoices = (await db.execute(
        select(Invoice)
        .where(Invoice.org_id == org_id, Invoice.customer_id == customer_id, Invoice.status != "DRAFT")
        .order_by(Invoice.issue_date.desc())
        .limit(200)
    )).scalars().all()
    return [{
        "id": str(inv.id), "type": "invoice", "invoice_number": inv.invoice_number,
        "date": inv.issue_date.isoformat() if inv.issue_date else None,
        "amount": float(inv.total_sek) if inv.total_sek else 0,
        "status": inv.status, "currency": inv.currency or "SEK",
    } for inv in invoices]


# ── Self-Service: Loyalty ──────────────────────────────────────────────────────
from app.features.loyalty.models import LoyaltyAccount, LoyaltyTransaction


@router.get("/loyalty")
async def portal_loyalty(
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    account = (await db.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.org_id == org_id, LoyaltyAccount.customer_id == customer_id)
    )).scalar_one_or_none()
    if not account:
        return {"points_balance": 0, "tier": "bronze", "transactions": []}
    txns = (await db.execute(
        select(LoyaltyTransaction).where(LoyaltyTransaction.account_id == account.id).order_by(LoyaltyTransaction.created_at.desc()).limit(50)
    )).scalars().all()
    return {
        "points_balance": account.points_balance,
        "lifetime_points": account.lifetime_points,
        "tier": account.tier,
        "transactions": [{"id": str(t.id), "points": t.points, "type": t.type, "reason": t.reason, "created_at": t.created_at.isoformat()} for t in txns],
    }


class RedeemIn(BaseModel):
    points: int


@router.post("/loyalty/redeem")
async def portal_loyalty_redeem(
    body: RedeemIn,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    account = (await db.execute(
        select(LoyaltyAccount).where(LoyaltyAccount.org_id == org_id, LoyaltyAccount.customer_id == customer_id)
    )).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="No loyalty account")
    if account.points_balance < body.points:
        raise HTTPException(status_code=422, detail="Insufficient points")
    account.points_balance -= body.points
    txn = LoyaltyTransaction(account_id=account.id, points=-body.points, type="redeem", reason="Portal redemption")
    db.add(txn)
    await db.commit()
    return {"points_balance": account.points_balance}


# ── Self-Service: Bookings ─────────────────────────────────────────────────────
from app.features.bookings.models import Service, Appointment


@router.get("/services")
async def portal_services(
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    rows = (await db.execute(select(Service).where(Service.org_id == org_id, Service.is_active == True))).scalars().all()
    return [{"id": str(s.id), "name": s.name, "duration_minutes": s.duration_minutes, "price": float(s.price) if s.price else None} for s in rows]


class BookingIn(BaseModel):
    service_id: str
    start_time: str
    notes: str | None = None


@router.post("/bookings", status_code=201)
async def portal_create_booking(
    body: BookingIn,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    appt = Appointment(
        org_id=org_id, customer_id=customer_id,
        service_id=uuid.UUID(body.service_id),
        start_time=datetime.fromisoformat(body.start_time),
        status="booked", booking_channel="web",
        notes=body.notes,
    )
    db.add(appt)
    await db.commit()
    await db.refresh(appt)
    return {"id": str(appt.id), "status": "booked", "start_time": appt.start_time.isoformat()}


@router.get("/bookings")
async def portal_list_bookings(
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    rows = (await db.execute(
        select(Appointment).where(Appointment.org_id == org_id, Appointment.customer_id == customer_id)
        .order_by(Appointment.start_time.desc()).limit(50)
    )).scalars().all()
    return [{"id": str(a.id), "service_id": str(a.service_id) if a.service_id else None, "start_time": a.start_time.isoformat() if a.start_time else None, "status": a.status} for a in rows]


# ── Self-Service: Quotes ───────────────────────────────────────────────────────
from app.features.invoicing.model_quotes import Quote, QuoteLineItem


@router.get("/quotes")
async def portal_quotes_list(
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    rows = (await db.execute(
        select(Quote).where(Quote.org_id == org_id, Quote.customer_id == customer_id, Quote.status != "draft")
        .order_by(Quote.created_at.desc())
    )).scalars().all()
    return [{"id": str(q.id), "title": q.title, "quote_number": q.quote_number, "revision": q.revision, "status": q.status, "total": float(q.total), "currency": q.currency, "valid_until": q.valid_until.isoformat() if q.valid_until else None, "created_at": q.created_at.isoformat()} for q in rows]


@router.get("/quotes/{quote_id}")
async def portal_quote_detail(
    quote_id: str,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    quote = (await db.execute(
        select(Quote).where(Quote.id == uuid.UUID(quote_id), Quote.org_id == org_id, Quote.customer_id == customer_id)
    )).scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    await db.refresh(quote, ["line_items"])
    return {
        "id": str(quote.id), "title": quote.title, "quote_number": quote.quote_number,
        "revision": quote.revision, "status": quote.status,
        "cover_text": quote.cover_text, "scope": quote.scope, "terms": quote.terms,
        "subtotal": float(quote.subtotal), "vat_amount": float(quote.vat_amount), "total": float(quote.total),
        "currency": quote.currency, "valid_until": quote.valid_until.isoformat() if quote.valid_until else None,
        "line_items": [{"description": i.description, "quantity": float(i.quantity), "unit_price": float(i.unit_price), "tax_rate": float(i.tax_rate), "line_total": float(i.line_total)} for i in (quote.line_items or [])],
    }


@router.post("/quotes/{quote_id}/accept")
async def portal_quote_accept(
    quote_id: str,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    quote = (await db.execute(
        select(Quote).where(Quote.id == uuid.UUID(quote_id), Quote.org_id == org_id, Quote.customer_id == customer_id)
    )).scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if quote.status != "sent":
        raise HTTPException(status_code=409, detail="Quote cannot be accepted in current state")
    quote.status = "accepted"
    quote.accepted_at = datetime.now(timezone.utc)
    quote.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "accepted"}


@router.post("/quotes/{quote_id}/reject")
async def portal_quote_reject(
    quote_id: str,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    quote = (await db.execute(
        select(Quote).where(Quote.id == uuid.UUID(quote_id), Quote.org_id == org_id, Quote.customer_id == customer_id)
    )).scalar_one_or_none()
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    if quote.status != "sent":
        raise HTTPException(status_code=409, detail="Quote cannot be rejected in current state")
    quote.status = "rejected"
    quote.rejected_at = datetime.now(timezone.utc)
    quote.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "rejected"}


# ── Payment options (portal-facing) ──────────────────────────────────────────
from app.features.storefront.payment_options_models import (
    DepositRequest,
    EarlyPaymentDiscount,
    NdaAgreement,
    PaymentPlan,
    PaymentPlanInstalment,
    PortalTermsAcceptance,
)
from decimal import Decimal as _Decimal
import hashlib as _hashlib
import ipaddress as _ipaddress


class _TermsAcceptIn(BaseModel):
    terms_version: str


class _NdaSignIn(BaseModel):
    signer_name: str
    signer_email: str


class _InstalmentPlanIn(BaseModel):
    invoice_id: str
    num_instalments: int
    instalment_amounts: list[float]
    instalment_due_dates: list[str]


@router.get("/payments/{invoice_id}")
async def portal_payment_options(
    invoice_id: str,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    """Return payment options available for this invoice: plans, early discount."""
    try:
        customer_id, org_id = ctx
        inv = (await db.execute(
            select(Invoice).where(
                Invoice.id == uuid.UUID(invoice_id),
                Invoice.org_id == org_id,
                Invoice.customer_id == customer_id,
            )
        )).scalar_one_or_none()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")

        plans = (await db.execute(
            select(PaymentPlan)
            .where(PaymentPlan.invoice_id == inv.id, PaymentPlan.org_id == org_id)
        )).scalars().all()

        discount = (await db.execute(
            select(EarlyPaymentDiscount)
            .where(
                EarlyPaymentDiscount.invoice_id == inv.id,
                EarlyPaymentDiscount.org_id == org_id,
            )
            .order_by(EarlyPaymentDiscount.created_at.desc())
        )).scalar_one_or_none()

        return {
            "invoice_id": str(inv.id),
            "invoice_total": float(inv.total_sek),
            "currency": inv.currency,
            "available_payment_methods": inv.available_payment_methods,
            "payment_plans": [
                {
                    "id": str(p.id),
                    "num_instalments": p.num_instalments,
                    "status": p.status,
                    "total_amount": float(p.total_amount),
                }
                for p in plans
            ],
            "early_discount": {
                "id": str(discount.id),
                "discount_pct": float(discount.discount_pct),
                "days_threshold": discount.days_threshold,
                "discounted_total": float(discount.discounted_total),
                "accepted_at": discount.accepted_at.isoformat() if discount.accepted_at else None,
            } if discount else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error("portal_payment_options failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/payments/{invoice_id}/accept-discount")
async def portal_accept_discount(
    invoice_id: str,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    """Customer accepts the early payment discount for an invoice."""
    try:
        customer_id, org_id = ctx
        inv = await db.scalar(
            select(Invoice).where(
                Invoice.id == uuid.UUID(invoice_id),
                Invoice.org_id == org_id,
                Invoice.customer_id == customer_id,
            )
        )
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        discount = await db.scalar(
            select(EarlyPaymentDiscount).where(
                EarlyPaymentDiscount.invoice_id == inv.id,
                EarlyPaymentDiscount.org_id == org_id,
                EarlyPaymentDiscount.accepted_at.is_(None),
            )
        )
        if not discount:
            raise HTTPException(status_code=404, detail="No pending discount found")
        discount.accepted_at = datetime.now(timezone.utc)
        await db.commit()
        return {"accepted": True, "discounted_total": float(discount.discounted_total)}
    except HTTPException:
        raise
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error("portal_accept_discount failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/payments/{invoice_id}/select-plan")
async def portal_select_plan(
    invoice_id: str,
    body: _InstalmentPlanIn,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    """Customer self-creates a payment instalment plan for an invoice."""
    try:
        customer_id, org_id = ctx
        inv = await db.scalar(
            select(Invoice).where(
                Invoice.id == uuid.UUID(invoice_id),
                Invoice.org_id == org_id,
                Invoice.customer_id == customer_id,
            )
        )
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if len(body.instalment_amounts) != body.num_instalments or len(body.instalment_due_dates) != body.num_instalments:
            raise HTTPException(status_code=422, detail="Amounts and due dates must match num_instalments")
        plan = PaymentPlan(
            org_id=org_id,
            invoice_id=inv.id,
            customer_id=customer_id,
            total_amount=inv.total_sek,
            currency=inv.currency,
            num_instalments=body.num_instalments,
        )
        db.add(plan)
        await db.flush()
        from datetime import date as _date
        for i, (amt, due) in enumerate(zip(body.instalment_amounts, body.instalment_due_dates), start=1):
            db.add(PaymentPlanInstalment(
                plan_id=plan.id,
                instalment_number=i,
                amount=_Decimal(str(amt)),
                due_date=_date.fromisoformat(due),
            ))
        await db.commit()
        return {"plan_id": str(plan.id)}
    except HTTPException:
        raise
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error("portal_select_plan failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/deposits")
async def portal_list_deposits(
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    """List deposit requests for this customer."""
    try:
        customer_id, org_id = ctx
        rows = (await db.execute(
            select(DepositRequest).where(
                DepositRequest.customer_id == customer_id,
                DepositRequest.org_id == org_id,
            ).order_by(DepositRequest.created_at.desc())
        )).scalars().all()
        return [
            {
                "id": str(r.id),
                "amount": float(r.amount),
                "currency": r.currency,
                "status": r.status,
                "paid_at": r.paid_at.isoformat() if r.paid_at else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error("portal_list_deposits failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/terms")
async def portal_accept_terms(
    body: _TermsAcceptIn,
    request: Request,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    """Record customer acceptance of portal terms (gate on first login)."""
    try:
        customer_id, org_id = ctx
        ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else None)
        if ip:
            ip = ip.split(",")[0].strip()[:45]
        acceptance = PortalTermsAcceptance(
            org_id=org_id,
            customer_id=customer_id,
            terms_version=body.terms_version,
            ip_address=ip,
        )
        db.add(acceptance)
        await db.commit()
        return {"accepted": True}
    except HTTPException:
        raise
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error("portal_accept_terms failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/terms/latest")
async def portal_terms_status(
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    """Return the latest terms acceptance for this customer (to check gate)."""
    try:
        customer_id, org_id = ctx
        row = await db.scalar(
            select(PortalTermsAcceptance).where(
                PortalTermsAcceptance.customer_id == customer_id,
                PortalTermsAcceptance.org_id == org_id,
            ).order_by(PortalTermsAcceptance.accepted_at.desc())
        )
        if not row:
            return {"accepted": False}
        return {"accepted": True, "terms_version": row.terms_version, "accepted_at": row.accepted_at.isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error("portal_terms_status failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/contracts/{nda_id}")
async def portal_get_nda(
    nda_id: str,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    try:
        customer_id, org_id = ctx
        nda = await db.scalar(
            select(NdaAgreement).where(
                NdaAgreement.id == uuid.UUID(nda_id),
                NdaAgreement.org_id == org_id,
                NdaAgreement.customer_id == customer_id,
            )
        )
        if not nda:
            raise HTTPException(status_code=404, detail="Contract not found")
        return {
            "id": str(nda.id),
            "title": nda.title,
            "body": nda.body,
            "status": nda.status,
            "signed_at": nda.signed_at.isoformat() if nda.signed_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error("portal_get_nda failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/contracts/{nda_id}/sign")
async def portal_sign_nda(
    nda_id: str,
    body: _NdaSignIn,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    try:
        customer_id, org_id = ctx
        nda = await db.scalar(
            select(NdaAgreement).where(
                NdaAgreement.id == uuid.UUID(nda_id),
                NdaAgreement.org_id == org_id,
                NdaAgreement.customer_id == customer_id,
            )
        )
        if not nda:
            raise HTTPException(status_code=404, detail="Contract not found")
        if nda.status == "signed":
            raise HTTPException(status_code=409, detail="Already signed")
        sig_input = f"{nda_id}:{body.signer_name}:{body.signer_email}:{nda.body}"
        nda.signature_hash = _hashlib.sha256(sig_input.encode()).hexdigest()
        nda.signer_name = body.signer_name
        nda.signer_email = body.signer_email
        nda.status = "signed"
        nda.signed_at = datetime.now(timezone.utc)
        await db.commit()
        return {"signed": True, "signed_at": nda.signed_at.isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error("portal_sign_nda failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/contracts")
async def portal_list_ndas(
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    try:
        customer_id, org_id = ctx
        rows = (await db.execute(
            select(NdaAgreement).where(
                NdaAgreement.customer_id == customer_id,
                NdaAgreement.org_id == org_id,
            ).order_by(NdaAgreement.created_at.desc())
        )).scalars().all()
        return [
            {
                "id": str(r.id),
                "title": r.title,
                "status": r.status,
                "signed_at": r.signed_at.isoformat() if r.signed_at else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error("portal_list_ndas failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


# ── After-sales (portal-facing) ───────────────────────────────────────────────
from app.features.bookings.model_after_sales import (
    ReturnRequest as _ReturnRequest,
    WarrantyRecord as _WarrantyRecord,
    UpsellSuggestion as _UpsellSuggestion,
)
from decimal import Decimal as _DecAS


class _ReturnIn(BaseModel):
    invoice_id: str | None = None
    product_id: str | None = None
    quantity: float | None = None
    reason: str = "other"
    description: str | None = None
    photo_url: str | None = None


@router.get("/returns")
async def portal_list_returns(
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    try:
        customer_id, org_id = ctx
        rows = (await db.execute(
            select(_ReturnRequest).where(
                _ReturnRequest.customer_id == customer_id,
                _ReturnRequest.org_id == org_id,
            ).order_by(_ReturnRequest.created_at.desc())
        )).scalars().all()
        return [
            {
                "id": str(r.id),
                "invoice_id": str(r.invoice_id) if r.invoice_id else None,
                "product_id": str(r.product_id) if r.product_id else None,
                "quantity": float(r.quantity) if r.quantity else None,
                "reason": r.reason,
                "description": r.description,
                "status": r.status,
                "resolution_notes": r.resolution_notes,
                "refund_amount": float(r.refund_amount) if r.refund_amount else None,
                "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error("portal_list_returns failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/returns", status_code=201)
async def portal_submit_return(
    body: _ReturnIn,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    try:
        customer_id, org_id = ctx
        rr = _ReturnRequest(
            org_id=org_id,
            customer_id=customer_id,
            invoice_id=uuid.UUID(body.invoice_id) if body.invoice_id else None,
            product_id=uuid.UUID(body.product_id) if body.product_id else None,
            quantity=_DecAS(str(body.quantity)) if body.quantity else None,
            reason=body.reason,
            description=body.description,
            photo_url=body.photo_url,
        )
        db.add(rr)
        await db.commit()
        return {"id": str(rr.id)}
    except HTTPException:
        raise
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error("portal_submit_return failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/warranties")
async def portal_list_warranties(
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    try:
        customer_id, org_id = ctx
        rows = (await db.execute(
            select(_WarrantyRecord).where(
                _WarrantyRecord.customer_id == customer_id,
                _WarrantyRecord.org_id == org_id,
            ).order_by(_WarrantyRecord.expires_at.asc())
        )).scalars().all()
        return [
            {
                "id": str(w.id),
                "product_name_snapshot": w.product_name_snapshot,
                "serial_number": w.serial_number,
                "warranty_months": w.warranty_months,
                "starts_at": str(w.starts_at),
                "expires_at": str(w.expires_at),
                "status": w.status,
            }
            for w in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error("portal_list_warranties failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/suggestions")
async def portal_list_suggestions(
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    """Active upsell/cross-sell suggestions for this customer."""
    try:
        customer_id, org_id = ctx
        rows = (await db.execute(
            select(_UpsellSuggestion).where(
                _UpsellSuggestion.customer_id == customer_id,
                _UpsellSuggestion.org_id == org_id,
                _UpsellSuggestion.dismissed_at.is_(None),
            ).order_by(_UpsellSuggestion.created_at.desc())
        )).scalars().all()
        return [
            {
                "id": str(s.id),
                "trigger_type": s.trigger_type,
                "product_ids": s.product_ids,
                "message": s.message,
                "shown_at": s.shown_at.isoformat() if s.shown_at else None,
            }
            for s in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error("portal_list_suggestions failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/suggestions/{suggestion_id}/click")
async def portal_click_suggestion(
    suggestion_id: str,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    try:
        customer_id, org_id = ctx
        s = await db.scalar(
            select(_UpsellSuggestion).where(
                _UpsellSuggestion.id == uuid.UUID(suggestion_id),
                _UpsellSuggestion.customer_id == customer_id,
                _UpsellSuggestion.org_id == org_id,
            )
        )
        if not s:
            raise HTTPException(status_code=404, detail="Suggestion not found")
        if not s.clicked_at:
            s.clicked_at = datetime.now(timezone.utc)
            await db.commit()
        return {"clicked": True}
    except HTTPException:
        raise
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error("portal_click_suggestion failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/suggestions/{suggestion_id}/dismiss")
async def portal_dismiss_suggestion(
    suggestion_id: str,
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    try:
        customer_id, org_id = ctx
        s = await db.scalar(
            select(_UpsellSuggestion).where(
                _UpsellSuggestion.id == uuid.UUID(suggestion_id),
                _UpsellSuggestion.customer_id == customer_id,
                _UpsellSuggestion.org_id == org_id,
            )
        )
        if not s:
            raise HTTPException(status_code=404, detail="Suggestion not found")
        s.dismissed_at = datetime.now(timezone.utc)
        await db.commit()
        return {"dismissed": True}
    except HTTPException:
        raise
    except Exception as e:
        import logging as _log
        _log.getLogger(__name__).error("portal_dismiss_suggestion failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Deposits ───────────────────────────────────────────────────────────────────

@router.get("/deposits")
async def portal_deposits(
    ctx: tuple[uuid.UUID, uuid.UUID] = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    """Return all deposit and final invoices for the portal customer."""
    customer_id, org_id = ctx
    rows = (await db.execute(
        select(Invoice)
        .where(
            Invoice.customer_id == customer_id,
            Invoice.org_id == org_id,
            Invoice.invoice_type.in_(["deposit", "final"]),
            Invoice.status != InvoiceStatus.DRAFT,
        )
        .order_by(Invoice.created_at.desc())
    )).scalars().all()
    return [
        {
            "id": str(r.id),
            "invoice_number": r.invoice_number,
            "invoice_type": r.invoice_type,
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "issue_date": str(r.issue_date),
            "due_date": str(r.due_date),
            "total_sek": str(r.total_sek),
            "deposit_amount": str(r.deposit_amount) if r.deposit_amount else None,
            "parent_invoice_id": str(r.parent_invoice_id) if r.parent_invoice_id else None,
        }
        for r in rows
    ]


# ── Invoice ZIP download ───────────────────────────────────────────────────────

@router.get("/invoices-zip")
async def download_invoices_zip(
    portal=Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    """ZIP archive containing PDFs for all customer invoices."""
    import io
    import zipfile
    from fastapi.responses import StreamingResponse as SR

    customer_id, org_id = portal
    invoices = (await db.execute(
        select(Invoice).where(
            Invoice.customer_id == customer_id,
            Invoice.org_id == org_id,
            Invoice.status != InvoiceStatus.DRAFT,
        ).order_by(Invoice.issue_date.desc())
    )).scalars().all()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for inv in invoices:
            try:
                pdf_bytes = _generate_invoice_pdf(inv)
                fname = f"{inv.invoice_number or str(inv.id)}.pdf"
                zf.writestr(fname, pdf_bytes)
            except Exception:
                pass  # skip single invoice failures
    buf.seek(0)
    return SR(
        iter([buf.read()]),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="invoices.zip"'},
    )


# ── Credit notes ──────────────────────────────────────────────────────────────

@router.get("/credit-notes")
async def portal_credit_notes(
    portal=Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    """List all issued credit notes for this customer."""
    from sqlalchemy import and_
    from app.features.invoicing.credit_note import CreditNote, CreditNoteStatus

    customer_id, org_id = portal
    rows = (await db.execute(
        select(CreditNote).where(
            and_(
                CreditNote.customer_id == customer_id,
                CreditNote.org_id == org_id,
                CreditNote.status == CreditNoteStatus.ISSUED,
            )
        ).order_by(CreditNote.created_at.desc())
    )).scalars().all()
    return [
        {
            "id": str(r.id),
            "number": r.number,
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "total": str(r.total) if hasattr(r, "total") else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


# ── Statement PDF ─────────────────────────────────────────────────────────────

@router.get("/statements-pdf")
async def portal_statements_pdf(
    portal=Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    """HTML print view of the customer's account statement (browser prints to PDF)."""
    from fastapi.responses import HTMLResponse
    from sqlalchemy import and_

    customer_id, org_id = portal

    customer = (await db.execute(
        select(Customer).where(Customer.id == customer_id, Customer.org_id == org_id)
    )).scalar_one_or_none()

    invoices = (await db.execute(
        select(Invoice).where(
            and_(
                Invoice.customer_id == customer_id,
                Invoice.org_id == org_id,
                Invoice.status != InvoiceStatus.DRAFT,
            )
        ).order_by(Invoice.issue_date)
    )).scalars().all()

    rows_html = ""
    balance = Decimal("0")
    for inv in invoices:
        total = Decimal(str(inv.total_sek))
        balance += total
        status = inv.status.value if hasattr(inv.status, "value") else str(inv.status)
        rows_html += f"""<tr>
          <td>{inv.issue_date}</td>
          <td>{inv.invoice_number or '—'}</td>
          <td style="color:#4338ca">{status}</td>
          <td style="text-align:right">{inv.total_sek}</td>
          <td style="text-align:right">{balance}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Account Statement</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; color: #222; }}
    h1 {{ font-size: 20px; border-bottom: 2px solid #6366f1; padding-bottom: 6px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 16px; }}
    th {{ background: #f3f4f6; text-align: left; padding: 6px 10px; border: 1px solid #e5e7eb; }}
    td {{ padding: 6px 10px; border: 1px solid #e5e7eb; }}
    .balance {{ font-weight: bold; font-size: 15px; margin-top: 12px; text-align: right; }}
    @media print {{ body {{ margin: 20px; }} }}
  </style>
</head>
<body>
  <h1>Account Statement</h1>
  <p><strong>{customer.company_name if customer else 'Customer'}</strong></p>
  <p>Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}</p>
  <table>
    <thead>
      <tr><th>Date</th><th>Reference</th><th>Status</th><th style="text-align:right">Amount</th><th style="text-align:right">Running Balance</th></tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
  <div class="balance">Outstanding Balance: {balance}</div>
  <script>window.print();</script>
</body>
</html>"""
    return HTMLResponse(content=html)


# ── Notification preferences ──────────────────────────────────────────────────

@router.get("/notification-preferences")
async def get_notification_preferences(
    portal=Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    """Get or create customer notification preferences."""
    from sqlalchemy import and_
    from .portal_notification_prefs import PortalNotificationPreference

    customer_id, org_id = portal
    prefs = (await db.execute(
        select(PortalNotificationPreference).where(
            PortalNotificationPreference.customer_id == customer_id
        )
    )).scalar_one_or_none()

    if not prefs:
        # Return defaults without persisting — created on first PATCH
        return {
            "invoice_created": True, "payment_received": True,
            "quote_sent": True, "appointment_reminder": True, "marketing": False,
        }
    return {c.name: getattr(prefs, c.name) for c in prefs.__table__.columns
            if c.name not in ("id", "org_id", "customer_id")}


class NotifPrefsUpdate(BaseModel):
    invoice_created: bool | None = None
    payment_received: bool | None = None
    quote_sent: bool | None = None
    appointment_reminder: bool | None = None
    marketing: bool | None = None


@router.patch("/notification-preferences")
async def update_notification_preferences(
    body: NotifPrefsUpdate,
    portal=Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import and_
    from .portal_notification_prefs import PortalNotificationPreference

    customer_id, org_id = portal
    prefs = (await db.execute(
        select(PortalNotificationPreference).where(
            PortalNotificationPreference.customer_id == customer_id
        )
    )).scalar_one_or_none()

    if not prefs:
        prefs = PortalNotificationPreference(
            id=uuid.uuid4(), org_id=org_id, customer_id=customer_id
        )
        db.add(prefs)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(prefs, field, value)
    prefs.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(prefs)
    return {c.name: getattr(prefs, c.name) for c in prefs.__table__.columns
            if c.name not in ("id", "org_id", "customer_id")}


# ── Appointment cancel / reschedule ───────────────────────────────────────────

@router.post("/bookings/{appointment_id}/cancel")
async def cancel_appointment(
    appointment_id: uuid.UUID,
    portal=Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    """Customer cancels their own appointment."""
    from sqlalchemy import and_
    from app.features.bookings.models import Appointment

    customer_id, org_id = portal
    appt = (await db.execute(
        select(Appointment).where(
            and_(
                Appointment.id == appointment_id,
                Appointment.customer_id == customer_id,
                Appointment.org_id == org_id,
            )
        )
    )).scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt.status in ("cancelled", "completed", "no_show"):
        raise HTTPException(status_code=409, detail=f"Cannot cancel a {appt.status} appointment")

    appt.status = "cancelled"
    await db.commit()
    await db.refresh(appt)
    return {"id": str(appt.id), "status": appt.status}


class RescheduleBody(BaseModel):
    new_start_time: datetime


@router.patch("/bookings/{appointment_id}/reschedule")
async def reschedule_appointment(
    appointment_id: uuid.UUID,
    body: RescheduleBody,
    portal=Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    """Customer reschedules their appointment to a new start time."""
    from sqlalchemy import and_
    from app.features.bookings.models import Appointment

    customer_id, org_id = portal
    appt = (await db.execute(
        select(Appointment).where(
            and_(
                Appointment.id == appointment_id,
                Appointment.customer_id == customer_id,
                Appointment.org_id == org_id,
            )
        )
    )).scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt.status in ("cancelled", "completed", "no_show"):
        raise HTTPException(status_code=409, detail=f"Cannot reschedule a {appt.status} appointment")
    if body.new_start_time <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="New time must be in the future")

    # Preserve the original duration
    if appt.end_time and appt.start_time:
        duration = appt.end_time - appt.start_time
        appt.end_time = body.new_start_time + duration
    appt.start_time = body.new_start_time
    appt.status = "booked"
    await db.commit()
    await db.refresh(appt)
    return {
        "id": str(appt.id),
        "start_time": appt.start_time.isoformat(),
        "end_time": appt.end_time.isoformat() if appt.end_time else None,
        "status": appt.status,
    }
