"""Global Smart Search — Item 55.

One endpoint that searches across the tenant's four most-navigated
entity tables and returns a ranked, grouped result set. The heavy
lifting — normalisation, scoring, ranking, grouping — is in
:mod:`app.services.search` so the logic is testable without a DB.

Endpoint
--------
``GET /api/search?q=...&limit=...&types=...``

* ``q`` — free-text query. Min 2, max 100 chars after normalisation.
* ``limit`` — per-entity cap, clamped to ``MAX_PER_ENTITY``.
* ``types`` — optional comma-separated subset of
  ``customer,invoice,product,staff``. Defaults to all four.

Always tenant-scoped to ``member.org_id``. Read-only, so no
``log_action`` call — audit is reserved for mutations per repo rules.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.auth import AuthUser
from app.models.inventory import Product
from app.models.invoicing import Customer, Invoice
from app.models.organization import OrganizationMember
from app.models.search_history import SearchHistory
from app.services import search as svc
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/search", tags=["search"], dependencies=[Depends(require_module("settings"))])

log = logging.getLogger(__name__)

_ALLOWED_TYPES = frozenset(svc.ENTITY_PRIORITY)


class SearchHitOut(BaseModel):
    entity_type: str
    entity_id:   str
    title:       str
    subtitle:    str | None = None
    score:       int


class SearchResponse(BaseModel):
    query:   str
    total:   int
    results: dict[str, list[SearchHitOut]]


def _parse_types(raw: str | None) -> frozenset[str]:
    if not raw:
        return _ALLOWED_TYPES
    parts = {p.strip().lower() for p in raw.split(",") if p.strip()}
    bad = parts - _ALLOWED_TYPES
    if bad:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown entity type(s): {sorted(bad)}",
        )
    return frozenset(parts or _ALLOWED_TYPES)


@router.get("", response_model=SearchResponse)
async def global_search(
    ctx: tuple = Depends(get_current_member),
    db:  AsyncSession = Depends(get_db),
    q:      str = Query(..., min_length=1, max_length=120),
    limit:  int = Query(default=svc.MAX_PER_ENTITY, ge=1, le=svc.MAX_PER_ENTITY),
    types:  str | None = Query(default=None, max_length=64),
) -> SearchResponse:
    _, member = ctx
    org_id = member.org_id

    normalised = svc.normalise_query(q)
    if not normalised:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Query must be at least {svc.MIN_QUERY_LENGTH} characters",
        )

    wanted = _parse_types(types)
    like = f"%{svc.escape_like(normalised)}%"
    # SQL param cap — pull twice the per-entity limit, then rank client-side
    # so we don't miss an exact match buried in a large substring set.
    pull = limit * 2

    hits: list[svc.SearchHit] = []

    try:
        if "customer" in wanted:
            stmt = (
                select(Customer)
                .where(
                    Customer.org_id == org_id,
                    or_(
                        Customer.company_name.ilike(like, escape="\\"),
                        Customer.org_number.ilike(like, escape="\\"),
                        Customer.vat_number.ilike(like, escape="\\"),
                    ),
                )
                .limit(pull)
            )
            for row in (await db.scalars(stmt)).all():
                score = svc.best_score(
                    normalised,
                    (row.company_name, row.org_number, row.vat_number),
                )
                if score > svc.SCORE_NONE:
                    hits.append(svc.SearchHit(
                        entity_type="customer",
                        entity_id=str(row.id),
                        title=row.company_name,
                        subtitle=row.org_number or row.vat_number,
                        score=score,
                    ))

        if "invoice" in wanted:
            stmt = (
                select(Invoice)
                .where(
                    Invoice.org_id == org_id,
                    Invoice.invoice_number.ilike(like, escape="\\"),
                )
                .limit(pull)
            )
            for row in (await db.scalars(stmt)).all():
                score = svc.score_field(normalised, row.invoice_number)
                if score > svc.SCORE_NONE:
                    hits.append(svc.SearchHit(
                        entity_type="invoice",
                        entity_id=str(row.id),
                        title=row.invoice_number,
                        subtitle=row.status.value if row.status else None,
                        score=score,
                    ))

        if "product" in wanted:
            stmt = (
                select(Product)
                .where(
                    Product.org_id == org_id,
                    or_(
                        Product.name.ilike(like, escape="\\"),
                        Product.sku.ilike(like, escape="\\"),
                        Product.barcode.ilike(like, escape="\\"),
                        Product.category.ilike(like, escape="\\"),
                    ),
                )
                .limit(pull)
            )
            for row in (await db.scalars(stmt)).all():
                score = svc.best_score(
                    normalised,
                    (row.name, row.sku, row.barcode, row.category),
                )
                if score > svc.SCORE_NONE:
                    hits.append(svc.SearchHit(
                        entity_type="product",
                        entity_id=str(row.id),
                        title=row.name,
                        subtitle=row.sku,
                        score=score,
                    ))

        if "staff" in wanted:
            stmt = (
                select(OrganizationMember, AuthUser)
                .join(AuthUser, AuthUser.id == OrganizationMember.user_id)
                .where(
                    OrganizationMember.org_id == org_id,
                    AuthUser.email.ilike(like, escape="\\"),
                )
                .limit(pull)
            )
            for member_row, user_row in (await db.execute(stmt)).all():
                score = svc.score_field(normalised, user_row.email)
                if score > svc.SCORE_NONE:
                    hits.append(svc.SearchHit(
                        entity_type="staff",
                        entity_id=str(member_row.id),
                        title=user_row.email,
                        subtitle=member_row.role.value if member_row.role else None,
                        score=score,
                    ))

    except HTTPException:
        raise
    except Exception as e:
        log.error("global_search failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")

    ranked = svc.rank_hits(hits)
    grouped = svc.group_by_entity(ranked)

    # Apply per-entity cap after ranking so the highest-scored rows win.
    trimmed: dict[str, list[SearchHitOut]] = {}
    total = 0
    for name in svc.ENTITY_PRIORITY:
        rows = grouped.get(name, [])[:limit]
        total += len(rows)
        trimmed[name] = [
            SearchHitOut(
                entity_type=h.entity_type,
                entity_id=h.entity_id,
                title=h.title,
                subtitle=h.subtitle,
                score=h.score,
            )
            for h in rows
        ]

    return SearchResponse(query=normalised, total=total, results=trimmed)


# ── Search History (Sprint 14) ────────────────────────────────────────────────

class SearchHistoryIn(BaseModel):
    query: str
    result_type: Optional[str] = None
    result_id: Optional[uuid.UUID] = None
    result_label: Optional[str] = None


@router.post("/history", status_code=201)
async def log_search_selection(
    body: SearchHistoryIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Log a search selection to search_history."""
    _, member = ctx
    org_id = member.org_id
    user_id = member.user_id
    try:
        entry = SearchHistory(
            org_id=org_id,
            user_id=user_id,
            query=body.query[:200],
            result_type=body.result_type,
            result_id=body.result_id,
            result_label=body.result_label,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return {
            "id": str(entry.id),
            "query": entry.query,
            "result_type": entry.result_type,
            "result_id": str(entry.result_id) if entry.result_id else None,
            "result_label": entry.result_label,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("log_search_selection failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/history")
async def get_search_history(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return the last 20 search selections for the current user."""
    _, member = ctx
    org_id = member.org_id
    user_id = member.user_id
    try:
        result = await db.execute(
            select(SearchHistory)
            .where(
                SearchHistory.org_id == org_id,
                SearchHistory.user_id == user_id,
            )
            .order_by(SearchHistory.created_at.desc())
            .limit(20)
        )
        entries = result.scalars().all()
        return {
            "items": [
                {
                    "id": str(e.id),
                    "query": e.query,
                    "result_type": e.result_type,
                    "result_id": str(e.result_id) if e.result_id else None,
                    "result_label": e.result_label,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in entries
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_search_history failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/history")
async def clear_search_history(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Clear search history for the current user."""
    _, member = ctx
    org_id = member.org_id
    user_id = member.user_id
    try:
        await db.execute(
            delete(SearchHistory).where(
                SearchHistory.org_id == org_id,
                SearchHistory.user_id == user_id,
            )
        )
        await db.commit()
        return {"cleared": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error("clear_search_history failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
