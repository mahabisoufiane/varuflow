"""Live chat router (Sprint 11) — prefix /api/live-chat."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.features.notifications.model_live_chat import LiveChatMessage, LiveChatSession
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/live-chat", tags=["live-chat"], dependencies=[Depends(require_module("crm"))])


# ── Schemas ───────────────────────────────────────────────────────────────────

class LiveChatSessionOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    visitor_id: uuid.UUID
    visitor_name: Optional[str]
    visitor_email: Optional[str]
    assigned_staff_user_id: Optional[uuid.UUID]
    status: str
    page_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LiveChatMessageOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    sender_type: str
    sender_name: Optional[str]
    body: str
    created_at: datetime

    class Config:
        from_attributes = True


class StartSessionIn(BaseModel):
    visitor_name: Optional[str] = Field(default=None, max_length=100)
    visitor_email: Optional[str] = Field(default=None, max_length=200)
    page_url: Optional[str] = Field(default=None, max_length=500)


class SendMessageIn(BaseModel):
    sender_type: str = Field(..., max_length=10)
    sender_name: Optional[str] = Field(default=None, max_length=100)
    body: str


class AssignIn(BaseModel):
    staff_user_id: uuid.UUID


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/sessions", response_model=list[LiveChatSessionOut])
async def list_sessions(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = Query(default=None),
    assigned_to_me: bool = Query(default=False),
):
    try:
        org_id = _org_id(ctx)
        user, _ = ctx
        q = select(LiveChatSession).where(LiveChatSession.org_id == org_id)
        if status:
            q = q.where(LiveChatSession.status == status)
        if assigned_to_me:
            q = q.where(LiveChatSession.assigned_staff_user_id == uuid.UUID(user["user_id"]))
        q = q.order_by(LiveChatSession.updated_at.desc())
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_sessions failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sessions", response_model=LiveChatSessionOut, status_code=201)
async def start_session(
    body: StartSessionIn,
    org_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """PUBLIC — no auth required. Visitor starts a chat session."""
    try:
        session = LiveChatSession(
            org_id=org_id,
            visitor_id=uuid.uuid4(),
            visitor_name=body.visitor_name,
            visitor_email=body.visitor_email,
            page_url=body.page_url,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"start_session failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/sessions/{session_id}/messages", response_model=list[LiveChatMessageOut])
async def get_messages(
    session_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        session = await db.get(LiveChatSession, session_id)
        if not session or session.org_id != org_id:
            raise HTTPException(status_code=404, detail="Session not found")
        rows = (
            await db.execute(
                select(LiveChatMessage)
                .where(LiveChatMessage.session_id == session_id)
                .order_by(LiveChatMessage.created_at.asc())
            )
        ).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_messages failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sessions/{session_id}/messages", response_model=LiveChatMessageOut, status_code=201)
async def send_message(
    session_id: uuid.UUID,
    body: SendMessageIn,
    db: AsyncSession = Depends(get_db),
):
    """PUBLIC — no auth required for visitors. If sender_type is 'staff', returns 403."""
    try:
        if body.sender_type == "staff":
            raise HTTPException(status_code=403, detail="Staff must use the authenticated endpoint")
        session = await db.get(LiveChatSession, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        msg = LiveChatMessage(
            session_id=session_id,
            sender_type=body.sender_type,
            sender_name=body.sender_name,
            body=body.body,
        )
        db.add(msg)
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(msg)
        return msg
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"send_message failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sessions/{session_id}/assign", response_model=LiveChatSessionOut)
async def assign_session(
    session_id: uuid.UUID,
    body: AssignIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        session = await db.get(LiveChatSession, session_id)
        if not session or session.org_id != org_id:
            raise HTTPException(status_code=404, detail="Session not found")
        session.assigned_staff_user_id = body.staff_user_id
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(session)
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"assign_session failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sessions/{session_id}/resolve", response_model=LiveChatSessionOut)
async def resolve_session(
    session_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        session = await db.get(LiveChatSession, session_id)
        if not session or session.org_id != org_id:
            raise HTTPException(status_code=404, detail="Session not found")
        session.status = "resolved"
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(session)
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"resolve_session failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sessions/{session_id}/abandon", response_model=LiveChatSessionOut)
async def abandon_session(
    session_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        session = await db.get(LiveChatSession, session_id)
        if not session or session.org_id != org_id:
            raise HTTPException(status_code=404, detail="Session not found")
        session.status = "abandoned"
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(session)
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"abandon_session failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
