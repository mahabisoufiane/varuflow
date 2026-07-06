"""Quotes router — staff create/manage quotes, send to clients, convert to invoices."""
import logging
import secrets
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.features.invoicing.model_quotes import Quote, QuoteLineItem
from app.features.invoicing.models import Invoice, InvoiceLineItem

logger = logging.getLogger(__name__)
router = APIRouter(tags=["quotes"], dependencies=[Depends(require_module("crm"))])
public_router = APIRouter(tags=["quotes-public"])


class LineItemIn(BaseModel):
    description: str
    quantity: float = 1
    unit_price: float
    # Swedish standard VAT by default; send 12/6/0 explicitly for reduced or
    # zero-rated lines. VAT is computed per line (see create_quote) so quote
    # totals agree with the invoice later generated from the same lines.
    tax_rate: float = 25


class QuoteCreate(BaseModel):
    customer_id: str
    title: str
    quote_number: str | None = None
    cover_text: str | None = None
    scope: str | None = None
    terms: str | None = None
    currency: str = "SEK"
    valid_until: str | None = None
    items: list[LineItemIn] = []


class QuotePatch(BaseModel):
    title: str | None = None
    cover_text: str | None = None
    scope: str | None = None
    terms: str | None = None
    valid_until: str | None = None


@router.get("/api/quotes")
async def list_quotes(
    status: str | None = None,
    customer_id: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(Quote).where(Quote.org_id == org_id)
        if status:
            q = q.where(Quote.status == status)
        if customer_id:
            q = q.where(Quote.customer_id == uuid.UUID(customer_id))
        rows = (await db.execute(q.order_by(Quote.created_at.desc()))).scalars().all()
        return [_quote_summary(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_quotes failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/quotes", status_code=201)
async def create_quote(body: QuoteCreate, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        subtotal = Decimal("0")
        vat = Decimal("0")
        items_data = []
        for i, item in enumerate(body.items):
            lt = Decimal(str(item.quantity)) * Decimal(str(item.unit_price))
            subtotal += lt
            # Per-line VAT — a 12% food line and a 25% goods line must not
            # both be taxed at a blanket 25%; the invoice generated from these
            # same lines computes per-line, and the two documents must agree.
            vat += lt * Decimal(str(item.tax_rate)) / Decimal("100")
            items_data.append((item, lt, i))
        total = subtotal + vat

        quote = Quote(
            org_id=org_id, customer_id=uuid.UUID(body.customer_id),
            quote_number=body.quote_number, title=body.title,
            cover_text=body.cover_text, scope=body.scope, terms=body.terms,
            currency=body.currency, subtotal=subtotal, vat_amount=vat, total=total,
            valid_until=datetime.strptime(body.valid_until, "%Y-%m-%d").date() if body.valid_until else None,
            created_by_staff_id=member.get("staff_id"),
            public_token=secrets.token_hex(32),
        )
        db.add(quote)
        await db.flush()
        for item, lt, i in items_data:
            db.add(QuoteLineItem(
                quote_id=quote.id, description=item.description,
                quantity=Decimal(str(item.quantity)), unit_price=Decimal(str(item.unit_price)),
                tax_rate=Decimal(str(item.tax_rate)), line_total=lt, sort_order=i,
            ))
        await db.commit()
        await db.refresh(quote, ["line_items"])
        return _quote_detail(quote)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_quote failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/quotes/{quote_id}")
async def get_quote(quote_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        quote = (await db.execute(select(Quote).where(Quote.id == uuid.UUID(quote_id), Quote.org_id == org_id))).scalar_one_or_none()
        if not quote:
            raise HTTPException(status_code=404, detail="Not found")
        await db.refresh(quote, ["line_items"])
        return _quote_detail(quote)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_quote failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/quotes/{quote_id}")
async def update_quote(quote_id: str, body: QuotePatch, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        quote = (await db.execute(select(Quote).where(Quote.id == uuid.UUID(quote_id), Quote.org_id == org_id))).scalar_one_or_none()
        if not quote:
            raise HTTPException(status_code=404, detail="Not found")
        if quote.status != "draft":
            raise HTTPException(status_code=409, detail="Can only edit draft quotes")
        if body.title is not None:
            quote.title = body.title
        if body.cover_text is not None:
            quote.cover_text = body.cover_text
        if body.scope is not None:
            quote.scope = body.scope
        if body.terms is not None:
            quote.terms = body.terms
        if body.valid_until is not None:
            quote.valid_until = datetime.strptime(body.valid_until, "%Y-%m-%d").date()
        quote.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_quote failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/quotes/{quote_id}", status_code=204)
async def delete_quote(quote_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        quote = (await db.execute(select(Quote).where(Quote.id == uuid.UUID(quote_id), Quote.org_id == org_id))).scalar_one_or_none()
        if not quote:
            raise HTTPException(status_code=404, detail="Not found")
        if quote.status != "draft":
            raise HTTPException(status_code=409, detail="Can only delete draft quotes")
        await db.delete(quote)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_quote failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/quotes/{quote_id}/send")
async def send_quote(quote_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        quote = (await db.execute(select(Quote).where(Quote.id == uuid.UUID(quote_id), Quote.org_id == org_id))).scalar_one_or_none()
        if not quote:
            raise HTTPException(status_code=404, detail="Not found")
        if quote.status not in ("draft",):
            raise HTTPException(status_code=409, detail="Quote already sent")
        quote.status = "sent"
        quote.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return {"status": "sent"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"send_quote failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/quotes/{quote_id}/revise")
async def revise_quote(quote_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    """Create a new revision by copying the quote."""
    try:
        org_id = member["org_id"]
        original = (await db.execute(select(Quote).where(Quote.id == uuid.UUID(quote_id), Quote.org_id == org_id))).scalar_one_or_none()
        if not original:
            raise HTTPException(status_code=404, detail="Not found")
        await db.refresh(original, ["line_items"])
        new_quote = Quote(
            org_id=org_id, customer_id=original.customer_id,
            quote_number=original.quote_number, revision=original.revision + 1,
            parent_quote_id=original.id, title=original.title,
            cover_text=original.cover_text, scope=original.scope, terms=original.terms,
            currency=original.currency, subtotal=original.subtotal,
            vat_amount=original.vat_amount, total=original.total,
            valid_until=original.valid_until,
            created_by_staff_id=member.get("staff_id"),
            public_token=secrets.token_hex(32),
        )
        db.add(new_quote)
        await db.flush()
        for item in original.line_items:
            db.add(QuoteLineItem(
                quote_id=new_quote.id, description=item.description,
                quantity=item.quantity, unit_price=item.unit_price,
                tax_rate=item.tax_rate, line_total=item.line_total, sort_order=item.sort_order,
            ))
        await db.commit()
        await db.refresh(new_quote, ["line_items"])
        return _quote_detail(new_quote)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"revise_quote failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/quotes/{quote_id}/convert")
async def convert_quote_to_invoice(quote_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    """Convert an accepted quote to a DRAFT invoice."""
    try:
        org_id = member["org_id"]
        quote = (await db.execute(select(Quote).where(Quote.id == uuid.UUID(quote_id), Quote.org_id == org_id))).scalar_one_or_none()
        if not quote:
            raise HTTPException(status_code=404, detail="Not found")
        if quote.status != "accepted":
            raise HTTPException(status_code=409, detail="Only accepted quotes can be converted")
        if quote.invoice_id:
            raise HTTPException(status_code=409, detail="Already converted")
        await db.refresh(quote, ["line_items"])

        invoice = Invoice(
            org_id=org_id, customer_id=quote.customer_id,
            status="DRAFT", subtotal=quote.subtotal,
            vat_amount=quote.vat_amount, total_sek=quote.total,
            currency=quote.currency, notes=f"From quote: {quote.title}",
            quote_id=quote.id,
        )
        db.add(invoice)
        await db.flush()
        for item in quote.line_items:
            db.add(InvoiceLineItem(
                invoice_id=invoice.id, description=item.description,
                quantity=item.quantity, unit_price=item.unit_price,
                tax_rate=item.tax_rate, line_total=item.line_total,
            ))
        quote.status = "invoiced"
        quote.invoice_id = invoice.id
        quote.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return {"invoice_id": str(invoice.id), "status": "invoiced"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"convert_quote_to_invoice failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


def _quote_summary(q: Quote) -> dict:
    return {
        "id": str(q.id), "quote_number": q.quote_number, "revision": q.revision,
        "title": q.title, "status": q.status, "total": float(q.total),
        "currency": q.currency, "customer_id": str(q.customer_id),
        "valid_until": q.valid_until.isoformat() if q.valid_until else None,
        "created_at": q.created_at.isoformat() if q.created_at else None,
        "public_token": q.public_token,
    }


def _quote_detail(q: Quote) -> dict:
    return {
        **_quote_summary(q),
        "cover_text": q.cover_text, "scope": q.scope, "terms": q.terms,
        "subtotal": float(q.subtotal), "vat_amount": float(q.vat_amount),
        "accepted_at": q.accepted_at.isoformat() if q.accepted_at else None,
        "rejected_at": q.rejected_at.isoformat() if q.rejected_at else None,
        "decline_reason": q.decline_reason,
        "acceptance_name": q.acceptance_name,
        "invoice_id": str(q.invoice_id) if q.invoice_id else None,
        "parent_quote_id": str(q.parent_quote_id) if q.parent_quote_id else None,
        "line_items": [{"id": str(i.id), "description": i.description, "quantity": float(i.quantity), "unit_price": float(i.unit_price), "tax_rate": float(i.tax_rate), "line_total": float(i.line_total)} for i in (q.line_items or [])],
    }


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/api/quotes/analytics")
async def get_quote_analytics(member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rows = (await db.execute(
            select(Quote).where(Quote.org_id == org_id)
        )).scalars().all()

        total = len(rows)
        accepted = [r for r in rows if r.status == "accepted"]
        rejected = [r for r in rows if r.status in ("rejected", "declined")]
        acceptance_rate = round(len(accepted) / total * 100, 1) if total else 0

        times_to_accept = []
        for q in accepted:
            if q.accepted_at and q.created_at:
                delta = (q.accepted_at - q.created_at).total_seconds() / 3600
                times_to_accept.append(delta)
        avg_hours_to_accept = round(sum(times_to_accept) / len(times_to_accept), 1) if times_to_accept else None

        won_revenue = float(sum(q.total for q in accepted))
        lost_revenue = float(sum(q.total for q in rejected))

        status_breakdown: dict[str, int] = {}
        for r in rows:
            status_breakdown[r.status] = status_breakdown.get(r.status, 0) + 1

        return {
            "total_quotes": total,
            "acceptance_rate_pct": acceptance_rate,
            "avg_hours_to_accept": avg_hours_to_accept,
            "won_revenue": won_revenue,
            "lost_revenue": lost_revenue,
            "status_breakdown": status_breakdown,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_quote_analytics failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── PDF download ──────────────────────────────────────────────────────────────

@router.get("/api/quotes/{quote_id}/pdf")
async def download_quote_pdf(quote_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        from app.services.pdf_generator import generate_quote_pdf
        org_id = member["org_id"]
        quote = (await db.execute(select(Quote).where(Quote.id == uuid.UUID(quote_id), Quote.org_id == org_id))).scalar_one_or_none()
        if not quote:
            raise HTTPException(status_code=404, detail="Not found")
        await db.refresh(quote, ["line_items"])
        pdf_bytes = generate_quote_pdf(quote)
        filename = f"quote-{quote.quote_number or quote_id[:8]}.pdf"
        return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"download_quote_pdf failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Public (no-auth) endpoints via public_router ──────────────────────────────

class DeclineIn(BaseModel):
    reason: str = ""


@public_router.get("/api/quotes/view/{token}")
async def public_view_quote(token: str, db: AsyncSession = Depends(get_db)):
    """Load quote by public token. Auto-advances status sent → viewed."""
    try:
        quote = (await db.execute(
            select(Quote).where(Quote.public_token == token)
        )).scalar_one_or_none()
        if not quote:
            raise HTTPException(status_code=404, detail="Quote not found")
        await db.refresh(quote, ["line_items"])
        if quote.status == "sent":
            quote.status = "viewed"
            quote.updated_at = datetime.now(timezone.utc)
            await db.commit()
        return _quote_detail(quote)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"public_view_quote failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


class AcceptIn(BaseModel):
    acceptance_name: str = ""


@public_router.post("/api/quotes/view/{token}/accept")
async def public_accept_quote(token: str, body: AcceptIn, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        quote = (await db.execute(
            select(Quote).where(Quote.public_token == token)
        )).scalar_one_or_none()
        if not quote:
            raise HTTPException(status_code=404, detail="Quote not found")
        if quote.status not in ("sent", "viewed"):
            raise HTTPException(status_code=409, detail=f"Quote cannot be accepted in status '{quote.status}'")
        now = datetime.now(timezone.utc)
        quote.status = "accepted"
        quote.accepted_at = now
        quote.updated_at = now
        if body.acceptance_name:
            quote.acceptance_name = body.acceptance_name
        # Capture client IP (respects X-Forwarded-For via proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        quote.acceptance_ip = (forwarded.split(",")[0].strip() if forwarded else None) or (request.client.host if request.client else None)
        await db.commit()
        return {"status": "accepted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"public_accept_quote failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@public_router.post("/api/quotes/view/{token}/decline")
async def public_decline_quote(token: str, body: DeclineIn, db: AsyncSession = Depends(get_db)):
    try:
        quote = (await db.execute(
            select(Quote).where(Quote.public_token == token)
        )).scalar_one_or_none()
        if not quote:
            raise HTTPException(status_code=404, detail="Quote not found")
        if quote.status not in ("sent", "viewed"):
            raise HTTPException(status_code=409, detail=f"Quote cannot be declined in status '{quote.status}'")
        now = datetime.now(timezone.utc)
        quote.status = "rejected"
        quote.rejected_at = now
        quote.decline_reason = body.reason or None
        quote.updated_at = now
        await db.commit()
        return {"status": "rejected"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"public_decline_quote failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
