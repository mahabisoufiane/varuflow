"""AI customer personas router — Sprint 13.  prefix /api/ai/personas"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.ai_customer_persona import AiCustomerPersona

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai/personas", tags=["ai-personas"], dependencies=[Depends(require_module("ai"))])


def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Schemas ────────────────────────────────────────────────────────────────────

class AiPersonaOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: Optional[str]
    behavior_traits: list
    customer_ids: list
    segment_size: int
    last_computed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PatchPersonaIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=list[AiPersonaOut])
async def list_personas(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        q = (
            select(AiCustomerPersona)
            .where(AiCustomerPersona.org_id == org_id)
            .order_by(AiCustomerPersona.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(q)
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_personas failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/compute", response_model=list[AiPersonaOut], status_code=201)
async def compute_personas(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)

        # Gather customer stats: total invoiced, invoice count, last invoice date
        rows = await db.execute(
            text(
                "SELECT c.id, c.company_name, "
                "COALESCE(SUM(i.total_amount), 0) AS total_spend, "
                "COUNT(i.id) AS invoice_count, "
                "MAX(i.created_at) AS last_order "
                "FROM customers c "
                "LEFT JOIN invoices i ON i.customer_id = c.id AND i.deleted_at IS NULL "
                "WHERE c.org_id = :org_id AND c.deleted_at IS NULL "
                "GROUP BY c.id, c.company_name "
                "LIMIT 200"
            ),
            {"org_id": str(org_id)},
        )
        customers = [dict(r._mapping) for r in rows.all()]

        if not customers:
            return []

        summary_lines = [
            f"- {c['company_name']}: spend={c['total_spend']}, orders={c['invoice_count']}, last_order={c['last_order']}"
            for c in customers[:50]
        ]
        summary = "\n".join(summary_lines)

        prompt = (
            f"Here are customer stats for a Nordic B2B wholesaler:\n{summary}\n\n"
            "Cluster these customers into 3-5 distinct personas. For each persona return JSON with: "
            "name (string), description (string), behavior_traits (array of strings). "
            "Return only a valid JSON array of persona objects, no markdown."
        )

        personas_data = [
            {"name": "Regular Buyers", "description": "Consistent ordering pattern.", "behavior_traits": ["frequent orders", "mid-range spend"]},
            {"name": "High-Value Accounts", "description": "High total spend with infrequent large orders.", "behavior_traits": ["high spend", "low frequency"]},
            {"name": "New Customers", "description": "Recently acquired with limited history.", "behavior_traits": ["new account", "small orders"]},
        ]

        try:
            import openai
            client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
            )
            raw = response.choices[0].message.content.strip()
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list) and parsed:
                    personas_data = parsed
            except json.JSONDecodeError:
                pass
        except Exception as ai_err:
            logger.error(
                f"OpenAI call failed in compute_personas: {str(ai_err)}",
                extra={"org_id": str(org_id)},
            )

        now = datetime.now(timezone.utc)
        created_personas = []
        for p in personas_data:
            persona = AiCustomerPersona(
                org_id=org_id,
                name=p.get("name", "Unnamed Persona"),
                description=p.get("description"),
                behavior_traits=p.get("behavior_traits", []),
                customer_ids=[str(c["id"]) for c in customers],
                segment_size=len(customers),
                last_computed_at=now,
            )
            db.add(persona)
            created_personas.append(persona)

        await db.commit()
        for p in created_personas:
            await db.refresh(p)
        return created_personas
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"compute_personas failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{persona_id}", response_model=AiPersonaOut)
async def get_persona(
    persona_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(AiCustomerPersona, persona_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="AI customer persona not found")
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_persona failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{persona_id}", response_model=AiPersonaOut)
async def patch_persona(
    persona_id: uuid.UUID,
    body: PatchPersonaIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(AiCustomerPersona, persona_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="AI customer persona not found")
        if body.name is not None:
            record.name = body.name
        if body.description is not None:
            record.description = body.description
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"patch_persona failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{persona_id}", status_code=204)
async def delete_persona(
    persona_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        record = await db.get(AiCustomerPersona, persona_id)
        if not record or record.org_id != org_id:
            raise HTTPException(status_code=404, detail="AI customer persona not found")
        await db.delete(record)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_persona failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
