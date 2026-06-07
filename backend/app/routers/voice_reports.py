"""Voice reports router — Sprint 13.  prefix /api/voice
Rule-based NLQ only — NO OpenAI calls in this router.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.voice_report_query import VoiceReportQuery
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice-reports"], dependencies=[Depends(require_module("analytics"))])


def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.user_id


# ── Intent parser (rule-based) ─────────────────────────────────────────────────

def _parse_intent(transcript: str) -> dict:
    t = transcript.lower()

    # Determine metric
    if "revenue" in t or "sales" in t or "omsättning" in t:
        metric = "revenue"
    elif "refund" in t or "credit" in t or "återbetalning" in t:
        metric = "refunds"
    elif "customer" in t or "kund" in t:
        metric = "customers"
    elif "invoice" in t or "faktura" in t:
        metric = "invoices"
    else:
        metric = "revenue"

    # Determine period
    if "today" in t or "idag" in t:
        period = "today"
    elif "this week" in t or "denna vecka" in t or "den här veckan" in t:
        period = "this_week"
    elif "last month" in t or "förra månaden" in t:
        period = "last_month"
    elif "this year" in t or "i år" in t or "detta år" in t:
        period = "this_year"
    else:
        period = "this_month"

    return {"metric": metric, "period": period}


def _period_bounds(period: str) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "today":
        return today_start, now
    if period == "this_week":
        week_start = today_start - timedelta(days=now.weekday())
        return week_start, now
    if period == "last_month":
        month_start = today_start.replace(day=1)
        last_month_end = month_start
        last_month_start = (month_start - timedelta(days=1)).replace(day=1)
        return last_month_start, last_month_end
    if period == "this_year":
        year_start = today_start.replace(month=1, day=1)
        return year_start, now
    # default: this_month
    month_start = today_start.replace(day=1)
    return month_start, now


async def _execute_query(
    db: AsyncSession, org_id: uuid.UUID, intent: dict
) -> tuple[str, Any]:
    metric = intent["metric"]
    period = intent["period"]
    start, end = _period_bounds(period)
    params = {"org_id": str(org_id), "start": start, "end": end}

    period_label = period.replace("_", " ")

    if metric == "revenue":
        row = await db.execute(
            text(
                "SELECT COALESCE(SUM(total_amount), 0) FROM invoices "
                "WHERE org_id = :org_id AND status = 'paid' "
                "AND updated_at >= :start AND updated_at < :end AND deleted_at IS NULL"
            ),
            params,
        )
        val = float(row.scalar() or 0)
        return f"Revenue {period_label}: {val:.2f} SEK", {"value": val, "unit": "SEK"}

    if metric == "invoices":
        row = await db.execute(
            text(
                "SELECT COUNT(*) FROM invoices "
                "WHERE org_id = :org_id "
                "AND created_at >= :start AND created_at < :end AND deleted_at IS NULL"
            ),
            params,
        )
        val = int(row.scalar() or 0)
        return f"Invoices {period_label}: {val}", {"value": val, "unit": "invoices"}

    if metric == "customers":
        row = await db.execute(
            text(
                "SELECT COUNT(DISTINCT customer_id) FROM invoices "
                "WHERE org_id = :org_id "
                "AND created_at >= :start AND created_at < :end AND deleted_at IS NULL"
            ),
            params,
        )
        val = int(row.scalar() or 0)
        return f"Unique customers {period_label}: {val}", {"value": val, "unit": "customers"}

    if metric == "refunds":
        row = await db.execute(
            text(
                "SELECT COALESCE(SUM(total_amount), 0) FROM invoices "
                "WHERE org_id = :org_id AND status = 'credit_note' "
                "AND created_at >= :start AND created_at < :end AND deleted_at IS NULL"
            ),
            params,
        )
        val = float(row.scalar() or 0)
        return f"Refunds {period_label}: {val:.2f} SEK", {"value": val, "unit": "SEK"}

    return "Query not recognised", {}


# ── Schemas ────────────────────────────────────────────────────────────────────

class VoiceQueryIn(BaseModel):
    transcript: str


class VoiceQueryOut(BaseModel):
    id: uuid.UUID
    result_text: str
    result_data: Optional[dict]
    parsed_intent: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/query", response_model=VoiceQueryOut, status_code=201)
async def voice_query(
    body: VoiceQueryIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        user_id = _user_id(ctx)
        intent = _parse_intent(body.transcript)
        result_text, result_data = await _execute_query(db, org_id, intent)

        record = VoiceReportQuery(
            org_id=org_id,
            user_id=user_id,
            transcript=body.transcript,
            parsed_intent=intent,
            result_text=result_text,
            result_data=result_data,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"voice_query failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/history", response_model=list[VoiceQueryOut])
async def voice_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        q = (
            select(VoiceReportQuery)
            .where(VoiceReportQuery.org_id == org_id)
            .order_by(VoiceReportQuery.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(q)
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"voice_history failed: {str(e)}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
