"""B2B Customer Portal — magic-link auth and invoice access.

POST /api/portal/auth/magic-link   — request a login link (no auth required)
GET  /api/portal/auth/verify       — exchange token for portal JWT
GET  /api/portal/invoices          — list customer's invoices
GET  /api/portal/invoices/{id}     — invoice detail
GET  /api/portal/invoices/{id}/pdf — download PDF
"""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models.invoicing import (
    Customer,
    CustomerPortalToken,
    Invoice,
    InvoiceStatus,
)
from app.routers.invoicing import _generate_invoice_pdf
from app.schemas.invoicing import InvoiceOut, InvoiceSummary
from app.services.email import send_magic_link_email

router = APIRouter(prefix="/api/portal", tags=["portal"])

_bearer = HTTPBearer(auto_error=True)

_ALGORITHM = "HS256"
_TOKEN_EXPIRY_MINUTES = 15
_JWT_EXPIRY_HOURS = 24 * 7  # 7-day portal session


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

def _issue_portal_jwt(customer_id: uuid.UUID, org_id: uuid.UUID) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=_JWT_EXPIRY_HOURS)
    return jwt.encode(
        {"sub": str(customer_id), "org_id": str(org_id), "type": "portal", "exp": exp},
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
    customer_id = uuid.UUID(payload["sub"])
    org_id = uuid.UUID(payload["org_id"])

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
    """Find customer by email and send a magic login link."""
    result = await db.execute(
        select(Customer)
        .where(Customer.email == body.email, Customer.is_active == True)  # noqa: E712
    )
    customer = result.scalar_one_or_none()

    # Always return OK to avoid email enumeration
    if not customer:
        return MagicLinkResponse(status="sent")

    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=_TOKEN_EXPIRY_MINUTES)

    portal_token = CustomerPortalToken(
        customer_id=customer.id,
        org_id=customer.org_id,
        token=raw_token,
        expires_at=expires_at,
    )
    db.add(portal_token)
    await db.commit()

    magic_url = f"{settings.PORTAL_BASE_URL}/portal/auth/verify?token={raw_token}"

    # Fetch org name for the email
    from app.models.organization import Organization
    org = await db.get(Organization, customer.org_id)
    org_name = org.name if org else "Varuflow"

    sent = await send_magic_link_email(
        to_email=customer.email,
        customer_name=customer.company_name,
        magic_url=magic_url,
        org_name=org_name,
    )

    # In dev (Resend not configured), return the URL directly so devs can test
    return MagicLinkResponse(
        status="sent",
        dev_magic_url=magic_url if not sent else None,
    )


@router.get("/auth/verify", response_model=VerifyResponse)
async def verify_magic_link(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Exchange a magic-link token for a portal JWT."""
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(CustomerPortalToken)
        .options(selectinload(CustomerPortalToken.customer))
        .where(CustomerPortalToken.token == token)
    )
    pt = result.scalar_one_or_none()

    if not pt or pt.used or pt.expires_at.replace(tzinfo=timezone.utc) < now:
        raise HTTPException(status_code=400, detail="Invalid or expired link")

    pt.used = True
    await db.commit()

    from app.models.organization import Organization
    org = await db.get(Organization, pt.org_id)
    org_name = org.name if org else "Varuflow"

    portal_jwt = _issue_portal_jwt(pt.customer_id, pt.org_id)
    return VerifyResponse(
        portal_token=portal_jwt,
        customer_name=pt.customer.company_name,
        org_name=org_name,
    )


# ── Invoice endpoints ─────────────────────────────────────────────────────────

@router.get("/invoices", response_model=list[InvoiceSummary])
async def list_portal_invoices(
    ctx: tuple = Depends(get_portal_customer),
    db: AsyncSession = Depends(get_db),
):
    customer_id, org_id = ctx
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer))
        .where(Invoice.customer_id == customer_id, Invoice.org_id == org_id)
        .where(Invoice.status != InvoiceStatus.DRAFT)
        .order_by(Invoice.created_at.desc())
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
