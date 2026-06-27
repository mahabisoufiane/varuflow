"""Quote comparison boards — Sprint 10.

Endpoints under ``/api/quote-comparisons``:

    GET    ""       list comparisons (filter by customer_id)
    POST   ""       create comparison
    GET    /{id}    detail with each quote's info joined
    PATCH  /{id}    update quote_ids/notes/title
    DELETE /{id}    delete
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.quote_comparison import QuoteComparison

router = APIRouter(prefix="/api/quote-comparisons", tags=["quote-comparisons"])
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class ComparisonCreate(BaseModel):
    customer_id: uuid.UUID
    title: str
    quote_ids: list[str] = []
    notes: str | None = None


class ComparisonUpdate(BaseModel):
    title: str | None = None
    quote_ids: list[str] | None = None
    notes: str | None = None


class QuoteDetail(BaseModel):
    id: str
    # Populated when quote record is found; None if quote not accessible
    quote_number: str | None = None
    total: float | None = None
    status: str | None = None


class ComparisonOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: uuid.UUID
    title: str
    quote_ids: list[str]
    notes: str | None
    created_at: datetime
    updated_at: datetime
    quotes: list[QuoteDetail] = []


def _to_out(row: QuoteComparison, quotes: list[QuoteDetail] | None = None) -> ComparisonOut:
    return ComparisonOut(
        id=row.id,
        org_id=row.org_id,
        customer_id=row.customer_id,
        title=row.title,
        quote_ids=row.quote_ids or [],
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
        quotes=quotes or [],
    )


async def _load(db: AsyncSession, *, comparison_id: uuid.UUID, org_id: uuid.UUID) -> QuoteComparison:
    row = await db.get(QuoteComparison, comparison_id)
    if row is None or row.org_id != org_id:
        raise HTTPException(status_code=404, detail="Quote comparison not found")
    return row


async def _fetch_quotes(db: AsyncSession, quote_ids: list[str], org_id: uuid.UUID) -> list[QuoteDetail]:
    """Attempt to load quote details from the quotes table; fails gracefully."""
    details: list[QuoteDetail] = []
    try:
        from app.models.quotes import Quote  # type: ignore[import]
        for qid_str in quote_ids:
            try:
                qid = uuid.UUID(qid_str)
            except ValueError:
                details.append(QuoteDetail(id=qid_str))
                continue
            q = await db.get(Quote, qid)
            if q is not None and q.org_id == org_id:
                details.append(QuoteDetail(
                    id=qid_str,
                    quote_number=getattr(q, "quote_number", None),
                    total=float(getattr(q, "total", 0) or 0),
                    status=getattr(q, "status", None),
                ))
            else:
                details.append(QuoteDetail(id=qid_str))
    except Exception:
        details = [QuoteDetail(id=qid_str) for qid_str in quote_ids]
    return details


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ComparisonOut])
async def list_comparisons(
    customer_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        stmt = select(QuoteComparison).where(QuoteComparison.org_id == member.org_id)
        if customer_id is not None:
            stmt = stmt.where(QuoteComparison.customer_id == customer_id)
        stmt = stmt.order_by(QuoteComparison.created_at.desc()).limit(limit).offset(offset)
        rows = (await db.scalars(stmt)).all()
        return [_to_out(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_comparisons failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=ComparisonOut, status_code=201)
async def create_comparison(
    body: ComparisonCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        row = QuoteComparison(
            org_id=member.org_id,
            customer_id=body.customer_id,
            title=body.title,
            quote_ids=body.quote_ids,
            notes=body.notes,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _to_out(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_comparison failed: {str(e)}", extra={"org_id": str(member.org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{comparison_id}", response_model=ComparisonOut)
async def get_comparison(
    comparison_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        row = await _load(db, comparison_id=comparison_id, org_id=member.org_id)
        quotes = await _fetch_quotes(db, row.quote_ids or [], member.org_id)
        return _to_out(row, quotes)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_comparison failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{comparison_id}", response_model=ComparisonOut)
async def update_comparison(
    comparison_id: uuid.UUID,
    body: ComparisonUpdate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        row = await _load(db, comparison_id=comparison_id, org_id=member.org_id)
        for field, val in body.model_dump(exclude_unset=True).items():
            setattr(row, field, val)
        await db.commit()
        await db.refresh(row)
        return _to_out(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_comparison failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{comparison_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comparison(
    comparison_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        _user, member = ctx
        row = await _load(db, comparison_id=comparison_id, org_id=member.org_id)
        await db.delete(row)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_comparison failed: {str(e)}", extra={"org_id": str(ctx[1].org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
