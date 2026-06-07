"""AI pricing router — Sprint 13.  prefix /api/ai/pricing"""
from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.ai_price_suggestion import AiPriceSuggestion

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai/pricing", tags=["ai-pricing"], dependencies=[Depends(require_module("ai"))])


def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Schemas ────────────────────────────────────────────────────────────────────

class SuggestPriceIn(BaseModel):
    product_id: Optional[uuid.UUID] = None
    product_name: str
    category: Optional[str] = None
    cost_price: Optional[Decimal] = None
    target_margin_pct: Optional[Decimal] = None
    current_price: Optional[Decimal] = None


class AcceptPriceIn(BaseModel):
    accepted_price: Optional[Decimal] = None
    apply_to_product: bool = False


class AiPriceSuggestionOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    product_id: Optional[uuid.UUID]
    cost_price: Optional[Decimal]
    target_margin_pct: Optional[Decimal]
    current_price: Optional[Decimal]
    suggested_price: Decimal
    reasoning: Optional[str]
    model_used: str
    accepted: Optional[bool]
    accepted_price: Optional[Decimal]
    created_at: datetime

    class Config:
        from_attributes = True


def _extract_price(text: str) -> Optional[Decimal]:
    """Extract first decimal number from AI response text."""
    match = re.search(r"\b(\d+(?:[.,]\d+)?)\b", text)
    if match:
        try:
            return Decimal(match.group(1).replace(",", "."))
        except Exception:
            return None
    return None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/suggest", response_model=AiPriceSuggestionOut, status_code=201)
async def suggest_price(
    body: SuggestPriceIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)

        context_lines = [f"Product: {body.product_name}"]
        if body.category:
            context_lines.append(f"Category: {body.category}")
        if body.cost_price is not None:
            context_lines.append(f"Cost price: {body.cost_price} SEK")
        if body.target_margin_pct is not None:
            context_lines.append(f"Target margin: {body.target_margin_pct}%")
        if body.current_price is not None:
            context_lines.append(f"Current price: {body.current_price} SEK")

        prompt = (
            "\n".join(context_lines) + "\n\n"
            "Based on the above, suggest an optimal retail price in SEK for a Nordic B2B wholesale context. "
            "Reply with: suggested price (number only first), then a short reasoning."
        )

        # Fallback: margin-based calculation
        fallback_price = Decimal("0.00")
        if body.cost_price and body.target_margin_pct:
            margin = body.target_margin_pct / Decimal("100")
            if margin < Decimal("1"):
                fallback_price = body.cost_price / (Decimal("1") - margin)
        elif body.cost_price:
            fallback_price = body.cost_price * Decimal("1.30")
        elif body.current_price:
            fallback_price = body.current_price

        suggested_price = fallback_price
        reasoning = "Calculated using cost-plus margin methodology."
        model_used = "gpt-4o"

        try:
            import openai
            client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
            )
            content = response.choices[0].message.content.strip()
            extracted = _extract_price(content)
            if extracted and extracted > Decimal("0"):
                suggested_price = extracted
            reasoning = content
        except Exception as ai_err:
            logger.error(
                f"OpenAI call failed in suggest_price: {str(ai_err)}",
                extra={"org_id": str(org_id)},
            )

        record = AiPriceSuggestion(
            org_id=org_id,
            product_id=body.product_id,
            cost_price=body.cost_price,
            target_margin_pct=body.target_margin_pct,
            current_price=body.current_price,
            suggested_price=suggested_price,
            reasoning=reasoning,
            model_used=model_used,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"suggest_price failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=list[AiPriceSuggestionOut])
async def list_price_suggestions(
    product_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        q = select(AiPriceSuggestion).where(AiPriceSuggestion.org_id == org_id)
        if product_id:
            q = q.where(AiPriceSuggestion.product_id == product_id)
        q = q.order_by(AiPriceSuggestion.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(q)
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_price_suggestions failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{suggestion_id}/accept", response_model=AiPriceSuggestionOut)
async def accept_price_suggestion(
    suggestion_id: uuid.UUID,
    body: AcceptPriceIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(AiPriceSuggestion, suggestion_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="AI price suggestion not found")
        record.accepted = True
        if body.accepted_price is not None:
            record.accepted_price = body.accepted_price
        else:
            record.accepted_price = record.suggested_price
        if body.apply_to_product and record.product_id:
            await db.execute(
                text("UPDATE products SET price = :price WHERE id = :pid AND org_id = :org_id"),
                {"price": float(record.accepted_price), "pid": str(record.product_id), "org_id": str(org_id)},
            )
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"accept_price_suggestion failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{suggestion_id}/reject", response_model=AiPriceSuggestionOut)
async def reject_price_suggestion(
    suggestion_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(AiPriceSuggestion, suggestion_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="AI price suggestion not found")
        record.accepted = False
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"reject_price_suggestion failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
