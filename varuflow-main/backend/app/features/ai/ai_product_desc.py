"""AI product description router — Sprint 13.  prefix /api/ai/product-descriptions"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.features.ai.ai_product_description import AiProductDescription

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai/product-descriptions", tags=["ai-product-descriptions"], dependencies=[Depends(require_module("ai"))])


def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Schemas ────────────────────────────────────────────────────────────────────

class GenerateDescriptionIn(BaseModel):
    product_id: Optional[uuid.UUID] = None
    name: str
    category: Optional[str] = None
    features: list[str] = []
    tone: str = "professional"


class AcceptDescriptionIn(BaseModel):
    apply_to_product: bool = False


class AiProductDescriptionOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    product_id: Optional[uuid.UUID]
    generated_text: str
    model_used: str
    accepted: Optional[bool]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=AiProductDescriptionOut, status_code=201)
async def generate_description(
    body: GenerateDescriptionIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)

        features_text = ", ".join(body.features) if body.features else "N/A"
        prompt = (
            f"Write a {body.tone} product description for a wholesale product.\n"
            f"Product name: {body.name}\n"
            f"Category: {body.category or 'General'}\n"
            f"Key features: {features_text}\n"
            "Write a concise, compelling description of 2-3 sentences suitable for a B2B catalog."
        )

        generated_text = f"[AI description for {body.name}]"
        model_used = "gpt-4o"

        try:
            import openai
            client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
            )
            generated_text = response.choices[0].message.content.strip()
        except Exception as ai_err:
            logger.error(
                f"OpenAI call failed in generate_description: {str(ai_err)}",
                extra={"org_id": str(org_id)},
            )
            generated_text = (
                f"A high-quality {body.name} designed for professional wholesale use. "
                "Contact us for bulk pricing and availability."
            )

        record = AiProductDescription(
            org_id=org_id,
            product_id=body.product_id,
            prompt_context={"name": body.name, "category": body.category, "features": body.features, "tone": body.tone},
            generated_text=generated_text,
            model_used=model_used,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"generate_description failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=list[AiProductDescriptionOut])
async def list_descriptions(
    product_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        q = select(AiProductDescription).where(AiProductDescription.org_id == org_id)
        if product_id:
            q = q.where(AiProductDescription.product_id == product_id)
        q = q.order_by(AiProductDescription.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(q)
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_descriptions failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{desc_id}/accept", response_model=AiProductDescriptionOut)
async def accept_description(
    desc_id: uuid.UUID,
    body: AcceptDescriptionIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(AiProductDescription, desc_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="AI product description not found")
        record.accepted = True
        if body.apply_to_product and record.product_id:
            await db.execute(
                text("UPDATE products SET description = :desc WHERE id = :pid AND org_id = :org_id"),
                {"desc": record.generated_text, "pid": str(record.product_id), "org_id": str(org_id)},
            )
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"accept_description failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{desc_id}/reject", response_model=AiProductDescriptionOut)
async def reject_description(
    desc_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(AiProductDescription, desc_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="AI product description not found")
        record.accepted = False
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"reject_description failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
