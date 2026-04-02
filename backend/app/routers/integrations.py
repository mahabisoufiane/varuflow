"""External integrations: Fortnox OAuth2, AI assistant."""
import uuid
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.organization import Organization
from app.models.invoicing import Invoice, InvoiceStatus

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

FORTNOX_AUTH_URL = "https://apps.fortnox.se/oauth-v1/auth"
FORTNOX_TOKEN_URL = "https://apps.fortnox.se/oauth-v1/token"
FORTNOX_API_BASE = "https://api.fortnox.se/3"
FORTNOX_SCOPES = "bookkeeping invoice customer"


def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Status ────────────────────────────────────────────────────────────────────

class FortnoxStatus(BaseModel):
    connected: bool
    token_expiry: Optional[datetime] = None


@router.get("/fortnox/status", response_model=FortnoxStatus)
async def fortnox_status(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, _org_id(ctx))
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return FortnoxStatus(
        connected=bool(org.fortnox_access_token),
        token_expiry=org.fortnox_token_expiry,
    )


# ── Connect (OAuth2 initiation) ────────────────────────────────────────────────

@router.get("/fortnox/connect")
async def fortnox_connect(ctx: tuple = Depends(get_current_member)):
    if not settings.FORTNOX_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Fortnox not configured — add FORTNOX_CLIENT_ID")

    params = {
        "client_id": settings.FORTNOX_CLIENT_ID,
        "redirect_uri": settings.FORTNOX_REDIRECT_URI,
        "scope": FORTNOX_SCOPES,
        "state": str(_org_id(ctx)),
        "access_type": "offline",
        "response_type": "code",
    }
    return RedirectResponse(f"{FORTNOX_AUTH_URL}?{urlencode(params)}")


# ── Callback (OAuth2 token exchange) ──────────────────────────────────────────

@router.get("/fortnox/callback")
async def fortnox_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    if not settings.FORTNOX_CLIENT_ID or not settings.FORTNOX_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Fortnox not configured")

    try:
        org_id = uuid.UUID(state)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid state")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            FORTNOX_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.FORTNOX_REDIRECT_URI,
                "client_id": settings.FORTNOX_CLIENT_ID,
                "client_secret": settings.FORTNOX_CLIENT_SECRET,
            },
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Fortnox token error: {resp.text}")
        data = resp.json()

    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    org.fortnox_access_token = data["access_token"]
    org.fortnox_refresh_token = data.get("refresh_token")
    expires_in = data.get("expires_in", 3600)
    org.fortnox_token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
    await db.commit()

    return RedirectResponse("http://localhost:3000/settings?tab=integrations&connected=1")


# ── Disconnect ────────────────────────────────────────────────────────────────

@router.delete("/fortnox/disconnect")
async def fortnox_disconnect(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, _org_id(ctx))
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    org.fortnox_access_token = None
    org.fortnox_refresh_token = None
    org.fortnox_token_expiry = None
    await db.commit()
    return {"disconnected": True}


# ── Token refresh helper ───────────────────────────────────────────────────────

async def _get_valid_token(org: Organization) -> str:
    if not org.fortnox_access_token:
        raise HTTPException(status_code=400, detail="Fortnox not connected")

    # Refresh if expiring within 5 minutes
    if org.fortnox_token_expiry and org.fortnox_token_expiry < datetime.utcnow() + timedelta(minutes=5):
        if not org.fortnox_refresh_token:
            raise HTTPException(status_code=400, detail="Fortnox token expired — reconnect")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                FORTNOX_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": org.fortnox_refresh_token,
                    "client_id": settings.FORTNOX_CLIENT_ID,
                    "client_secret": settings.FORTNOX_CLIENT_SECRET,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                org.fortnox_access_token = data["access_token"]
                org.fortnox_refresh_token = data.get("refresh_token", org.fortnox_refresh_token)
                org.fortnox_token_expiry = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600))

    return org.fortnox_access_token


def _fortnox_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ── Sync invoices → Fortnox ───────────────────────────────────────────────────

class SyncResult(BaseModel):
    synced: int
    errors: list[str]


@router.post("/fortnox/sync-invoices", response_model=SyncResult)
async def sync_invoices_to_fortnox(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.orm import selectinload
    org_id = _org_id(ctx)
    org = await db.get(Organization, org_id)
    token = await _get_valid_token(org)
    await db.commit()  # save refreshed token

    # Fetch sent/overdue invoices not yet synced
    result = await db.execute(
        select(Invoice)
        .options(selectinload(Invoice.customer), selectinload(Invoice.line_items))
        .where(
            Invoice.org_id == org_id,
            Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.OVERDUE, InvoiceStatus.PAID]),
        )
        .limit(50)
    )
    invoices = result.scalars().all()

    synced = 0
    errors = []

    async with httpx.AsyncClient(timeout=30) as client:
        for inv in invoices:
            try:
                rows = [
                    {
                        "Description": li.description,
                        "DeliveredQuantity": float(li.quantity),
                        "Price": float(li.unit_price),
                        "VAT": int(li.tax_rate),
                    }
                    for li in inv.line_items
                ]
                payload = {
                    "Invoice": {
                        "InvoiceDate": str(inv.issue_date),
                        "DueDate": str(inv.due_date),
                        "CustomerName": inv.customer.company_name,
                        "CustomerNumber": str(inv.customer.id)[:10],
                        "InvoiceRows": rows,
                        "Currency": "SEK",
                        "YourReference": inv.invoice_number,
                    }
                }
                resp = await client.post(
                    f"{FORTNOX_API_BASE}/invoices",
                    json=payload,
                    headers=_fortnox_headers(token),
                )
                if resp.status_code in (200, 201):
                    synced += 1
                else:
                    errors.append(f"{inv.invoice_number}: {resp.status_code} {resp.text[:100]}")
            except Exception as e:
                errors.append(f"{inv.invoice_number}: {str(e)[:100]}")

    return SyncResult(synced=synced, errors=errors)


# ── Sync customers ← Fortnox ──────────────────────────────────────────────────

@router.post("/fortnox/sync-customers", response_model=SyncResult)
async def sync_customers_from_fortnox(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    from app.models.invoicing import Customer

    org_id = _org_id(ctx)
    org = await db.get(Organization, org_id)
    token = await _get_valid_token(org)
    await db.commit()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FORTNOX_API_BASE}/customers",
            headers=_fortnox_headers(token),
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Fortnox error: {resp.text[:200]}")
        customers_data = resp.json().get("Customers", [])

    synced = 0
    errors = []

    for fc in customers_data:
        try:
            company_name = fc.get("Name", "").strip()
            if not company_name:
                continue

            existing = await db.scalar(
                select(Customer).where(
                    Customer.org_id == org_id,
                    Customer.company_name == company_name,
                )
            )
            if existing:
                continue

            customer = Customer(
                org_id=org_id,
                company_name=company_name,
                org_number=fc.get("OrganisationNumber") or None,
                email=fc.get("Email") or None,
                phone=fc.get("Phone1") or None,
                address=(fc.get("Address1") or "") + (" " + fc.get("Address2", "") if fc.get("Address2") else ""),
            )
            db.add(customer)
            synced += 1
        except Exception as e:
            errors.append(f"{fc.get('Name', '?')}: {str(e)[:80]}")

    await db.commit()
    return SyncResult(synced=synced, errors=errors)


# ── AI Assistant ──────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@router.post("/ai/chat", response_model=ChatResponse)
async def ai_chat(
    body: ChatMessage,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="AI not configured — add OPENAI_API_KEY")

    from sqlalchemy import func
    from app.models.inventory import Product, StockLevel
    from app.models.invoicing import Invoice, InvoiceStatus, Customer

    org_id = _org_id(ctx)

    # Build context
    low_stock = await db.execute(
        select(Product.name, StockLevel.quantity, StockLevel.min_threshold)
        .join(StockLevel, StockLevel.product_id == Product.id)
        .where(Product.org_id == org_id, StockLevel.quantity <= StockLevel.min_threshold)
        .limit(10)
    )
    low_stock_rows = low_stock.all()

    overdue = await db.execute(
        select(Invoice.invoice_number, Invoice.total_sek, Invoice.due_date)
        .where(Invoice.org_id == org_id, Invoice.status == InvoiceStatus.OVERDUE)
        .limit(10)
    )
    overdue_rows = overdue.all()

    revenue_result = await db.scalar(
        select(func.coalesce(func.sum(Invoice.total_sek), 0))
        .where(Invoice.org_id == org_id, Invoice.status == InvoiceStatus.PAID)
    )

    context = f"""You are the AI intelligence layer of Varuflow — a B2B SaaS platform for Nordic wholesale businesses.
You are a proactive, context-aware business co-pilot specializing in inventory, invoicing, and cash flow.

LIVE BUSINESS DATA:
- Total paid revenue (all time): {float(revenue_result or 0):,.0f} SEK
- Low stock alerts ({len(low_stock_rows)}): {', '.join(f"{r.name} ({r.quantity} units, min {r.min_threshold})" for r in low_stock_rows) or 'none'}
- Overdue invoices ({len(overdue_rows)}): {', '.join(f"{r.invoice_number} ({float(r.total_sek):,.0f} SEK, due {r.due_date})" for r in overdue_rows) or 'none'}

YOUR CAPABILITIES:
1. INVENTORY INTELLIGENCE — stockout risk, dead stock, purchase order drafts, demand forecasting
2. MARGIN OPTIMIZER — gross margin analysis, price suggestions, bundle opportunities
3. WORKFLOW AUTOMATION — detect anomalies, classify problems, prescribe ranked actions
4. CUSTOMER INTELLIGENCE — RFM segmentation, late payer alerts, churn detection, win-back campaigns

OUTPUT FORMAT for recommendations:
Always structure your response as: [DIAGNOSIS] → [INSIGHT] → [ACTION] → [IMPACT]
Example: "STOCK_RISK detected for Kaffe Mellanrost → 4 units left, 3/day velocity, 5-day lead time → Draft PO for 45 units → Prevents ~4,500 SEK stockout loss"

GUARDRAILS:
- Never suggest price changes >15% without noting human approval required
- Add ⚠️ LOW CONFIDENCE if data is insufficient
- Always cite the actual data above when making recommendations
- Respond in the same language as the user (Swedish or English or Norwegian or Danish)"""

    try:
        import openai
        client_ai = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        resp = await client_ai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": context},
                {"role": "user", "content": body.message},
            ],
            max_tokens=500,
            temperature=0.4,
        )
        reply = resp.choices[0].message.content or "No response"
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI error: {str(e)[:200]}")

    return ChatResponse(reply=reply)
