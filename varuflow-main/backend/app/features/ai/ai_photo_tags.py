"""AI photo tags router — Sprint 13.  prefix /api/ai/photo-tags"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.features.ai.ai_photo_tag import AiPhotoTag

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai/photo-tags", tags=["ai-photo-tags"], dependencies=[Depends(require_module("ai"))])


def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Schemas ────────────────────────────────────────────────────────────────────

class AnalyzePhotoIn(BaseModel):
    photo_url: str
    product_id: Optional[uuid.UUID] = None


class AiPhotoTagOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    product_id: Optional[uuid.UUID]
    photo_url: str
    tags: list
    model_used: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=AiPhotoTagOut, status_code=201)
async def analyze_photo(
    body: AnalyzePhotoIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)

        tags: list = []
        model_used = "gpt-4o"

        try:
            import openai
            client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            vision_prompt = (
                "Analyze this product image and return a JSON array of tags. "
                "Each tag must have: category (color/style/material/type), name, confidence (0.0-1.0). "
                "Return only valid JSON array, no markdown."
            )
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": vision_prompt},
                            {"type": "image_url", "image_url": {"url": body.photo_url}},
                        ],
                    }
                ],
                max_tokens=500,
            )
            raw = response.choices[0].message.content.strip()
            try:
                tags = json.loads(raw)
            except json.JSONDecodeError:
                tags = [{"category": "type", "name": "product", "confidence": 0.5}]
        except Exception as ai_err:
            logger.error(
                f"OpenAI vision call failed in analyze_photo: {str(ai_err)}",
                extra={"org_id": str(org_id)},
            )
            tags = [{"category": "type", "name": "product", "confidence": 0.5}]

        record = AiPhotoTag(
            org_id=org_id,
            product_id=body.product_id,
            photo_url=body.photo_url,
            tags=tags,
            model_used=model_used,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"analyze_photo failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=list[AiPhotoTagOut])
async def list_photo_tags(
    product_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        q = select(AiPhotoTag).where(AiPhotoTag.org_id == org_id)
        if product_id:
            q = q.where(AiPhotoTag.product_id == product_id)
        q = q.order_by(AiPhotoTag.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(q)
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_photo_tags failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{tag_id}", status_code=204)
async def delete_photo_tag(
    tag_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(AiPhotoTag, tag_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="AI photo tag not found")
        await db.delete(record)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_photo_tag failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
