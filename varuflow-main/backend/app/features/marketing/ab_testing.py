"""A/B testing — tests and variants for email campaign optimization.

Endpoints
─────────
GET    /api/ab-testing                          → list tests
POST   /api/ab-testing                          → create test + auto-create A/B variants
GET    /api/ab-testing/{id}                     → detail with variants
PATCH  /api/ab-testing/{id}                     → update metadata
PATCH  /api/ab-testing/{id}/variants/{vid}      → update variant
POST   /api/ab-testing/{id}/start               → start test
POST   /api/ab-testing/{id}/complete            → determine winner, complete test
POST   /api/ab-testing/{id}/record              → record stats update for a variant
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from .ab_test import AbTest, AbTestVariant

router = APIRouter(prefix="/api/ab-testing", tags=["ab-testing"], dependencies=[Depends(require_module("crm"))])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _variant_out(v: AbTestVariant) -> dict[str, Any]:
    return {
        "id": str(v.id),
        "ab_test_id": str(v.ab_test_id),
        "variant": v.variant,
        "subject_line": v.subject_line,
        "body_html": v.body_html,
        "recipient_pct": float(v.recipient_pct),
        "sent_count": v.sent_count,
        "open_count": v.open_count,
        "click_count": v.click_count,
        "conversion_count": v.conversion_count,
        "created_at": v.created_at.isoformat(),
    }


def _test_out(t: AbTest, variants: Optional[list[AbTestVariant]] = None) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": str(t.id),
        "org_id": str(t.org_id),
        "name": t.name,
        "campaign_id": str(t.campaign_id) if t.campaign_id else None,
        "test_metric": t.test_metric,
        "status": t.status,
        "winner_variant": t.winner_variant,
        "auto_promote": t.auto_promote,
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "created_at": t.created_at.isoformat(),
    }
    if variants is not None:
        d["variants"] = [_variant_out(v) for v in variants]
    return d


# ── Schemas ────────────────────────────────────────────────────────────────────

class TestIn(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    campaign_id: Optional[uuid.UUID] = None
    test_metric: str = Field(default="open_rate", max_length=30)
    auto_promote: bool = Field(default=True)


class TestPatch(BaseModel):
    name: Optional[str] = Field(default=None, max_length=300)
    campaign_id: Optional[uuid.UUID] = None
    test_metric: Optional[str] = Field(default=None, max_length=30)
    auto_promote: Optional[bool] = None


class VariantPatch(BaseModel):
    subject_line: Optional[str] = Field(default=None, max_length=300)
    body_html: Optional[str] = None
    recipient_pct: Optional[Decimal] = None


class RecordIn(BaseModel):
    variant: str = Field(max_length=1)
    sent_count: Optional[int] = None
    open_count: Optional[int] = None
    click_count: Optional[int] = None
    conversion_count: Optional[int] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_tests(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        rows = (await db.execute(
            select(AbTest).where(AbTest.org_id == org_id).order_by(AbTest.created_at.desc())
        )).scalars().all()
        return [_test_out(t) for t in rows]
    except Exception as e:
        log.error("list_tests failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_test(
    body: TestIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        test = AbTest(
            org_id=org_id,
            name=body.name,
            campaign_id=body.campaign_id,
            test_metric=body.test_metric,
            auto_promote=body.auto_promote,
        )
        db.add(test)
        await db.flush()

        # Auto-create A and B variants
        for variant_label in ("A", "B"):
            v = AbTestVariant(
                ab_test_id=test.id,
                variant=variant_label,
                recipient_pct=Decimal("50"),
            )
            db.add(v)

        await db.commit()
        await db.refresh(test)

        variants = (await db.execute(
            select(AbTestVariant).where(AbTestVariant.ab_test_id == test.id).order_by(AbTestVariant.variant)
        )).scalars().all()
        return _test_out(test, variants)
    except Exception as e:
        log.error("create_test failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{test_id}")
async def get_test(
    test_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        test = await db.scalar(
            select(AbTest).where(AbTest.id == test_id, AbTest.org_id == org_id)
        )
        if not test:
            raise HTTPException(status_code=404, detail="A/B test not found")

        variants = (await db.execute(
            select(AbTestVariant).where(AbTestVariant.ab_test_id == test_id).order_by(AbTestVariant.variant)
        )).scalars().all()
        return _test_out(test, variants)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_test failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{test_id}")
async def patch_test(
    test_id: uuid.UUID,
    body: TestPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        test = await db.scalar(
            select(AbTest).where(AbTest.id == test_id, AbTest.org_id == org_id)
        )
        if not test:
            raise HTTPException(status_code=404, detail="A/B test not found")

        if body.name is not None:
            test.name = body.name
        if body.campaign_id is not None:
            test.campaign_id = body.campaign_id
        if body.test_metric is not None:
            test.test_metric = body.test_metric
        if body.auto_promote is not None:
            test.auto_promote = body.auto_promote

        await db.commit()
        await db.refresh(test)

        variants = (await db.execute(
            select(AbTestVariant).where(AbTestVariant.ab_test_id == test_id).order_by(AbTestVariant.variant)
        )).scalars().all()
        return _test_out(test, variants)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_test failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{test_id}/variants/{variant_id}")
async def patch_variant(
    test_id: uuid.UUID,
    variant_id: uuid.UUID,
    body: VariantPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        # Verify test belongs to org
        test = await db.scalar(
            select(AbTest).where(AbTest.id == test_id, AbTest.org_id == org_id)
        )
        if not test:
            raise HTTPException(status_code=404, detail="A/B test not found")

        variant = await db.scalar(
            select(AbTestVariant).where(
                AbTestVariant.id == variant_id, AbTestVariant.ab_test_id == test_id
            )
        )
        if not variant:
            raise HTTPException(status_code=404, detail="Variant not found")

        if body.subject_line is not None:
            variant.subject_line = body.subject_line
        if body.body_html is not None:
            variant.body_html = body.body_html
        if body.recipient_pct is not None:
            variant.recipient_pct = body.recipient_pct

        await db.commit()
        await db.refresh(variant)
        return _variant_out(variant)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_variant failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{test_id}/start")
async def start_test(
    test_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        test = await db.scalar(
            select(AbTest).where(AbTest.id == test_id, AbTest.org_id == org_id)
        )
        if not test:
            raise HTTPException(status_code=404, detail="A/B test not found")

        variants = (await db.execute(
            select(AbTestVariant).where(AbTestVariant.ab_test_id == test_id)
        )).scalars().all()
        if len(variants) < 2:
            raise HTTPException(status_code=422, detail="Test must have at least two variants before starting")

        test.status = "running"
        test.started_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(test)
        return _test_out(test, variants)
    except HTTPException:
        raise
    except Exception as e:
        log.error("start_test failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{test_id}/complete")
async def complete_test(
    test_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        test = await db.scalar(
            select(AbTest).where(AbTest.id == test_id, AbTest.org_id == org_id)
        )
        if not test:
            raise HTTPException(status_code=404, detail="A/B test not found")

        variants = (await db.execute(
            select(AbTestVariant).where(AbTestVariant.ab_test_id == test_id)
        )).scalars().all()

        # Determine winner by test_metric
        def _rate(v: AbTestVariant) -> float:
            if test.test_metric == "open_rate":
                return v.open_count / v.sent_count if v.sent_count else 0.0
            elif test.test_metric == "click_rate":
                return v.click_count / v.sent_count if v.sent_count else 0.0
            else:  # conversion_rate
                return v.conversion_count / v.sent_count if v.sent_count else 0.0

        winner_variant = max(variants, key=_rate, default=None) if variants else None
        winner_label = winner_variant.variant if winner_variant else None

        test.winner_variant = winner_label
        test.status = "complete"
        test.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(test)

        result = _test_out(test, variants)
        if test.auto_promote and winner_label:
            result["promote_message"] = f"Variant {winner_label} should be promoted based on {test.test_metric}."
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error("complete_test failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{test_id}/record")
async def record_stats(
    test_id: uuid.UUID,
    body: RecordIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        test = await db.scalar(
            select(AbTest).where(AbTest.id == test_id, AbTest.org_id == org_id)
        )
        if not test:
            raise HTTPException(status_code=404, detail="A/B test not found")

        variant = await db.scalar(
            select(AbTestVariant).where(
                AbTestVariant.ab_test_id == test_id,
                AbTestVariant.variant == body.variant.upper(),
            )
        )
        if not variant:
            raise HTTPException(status_code=404, detail=f"Variant {body.variant} not found")

        if body.sent_count is not None:
            variant.sent_count = body.sent_count
        if body.open_count is not None:
            variant.open_count = body.open_count
        if body.click_count is not None:
            variant.click_count = body.click_count
        if body.conversion_count is not None:
            variant.conversion_count = body.conversion_count

        await db.commit()
        await db.refresh(variant)
        return _variant_out(variant)
    except HTTPException:
        raise
    except Exception as e:
        log.error("record_stats failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
