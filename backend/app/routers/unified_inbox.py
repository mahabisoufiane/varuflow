"""Unified inbox router (Sprint 12) — prefix /api/inbox."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.unified_message import UnifiedInboxThread, UnifiedMessage
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/inbox", tags=["unified-inbox"], dependencies=[Depends(require_module("crm"))])


# ── Schemas ──────────────────────────────────────────────────────────────────

class ThreadOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    customer_id: Optional[uuid.UUID]
    channel: str
    subject: Optional[str]
    last_message_at: datetime
    is_archived: bool
    is_read: bool
    assigned_to_user_id: Optional[uuid.UUID]
    sentiment: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreateThreadIn(BaseModel):
    customer_id: Optional[uuid.UUID] = None
    channel: str = Field(default="in_app", max_length=20)
    subject: Optional[str] = Field(default=None, max_length=300)


class MessageOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    thread_id: uuid.UUID
    customer_id: Optional[uuid.UUID]
    channel: str
    direction: str
    external_message_id: Optional[str]
    sender_name: Optional[str]
    sender_contact: Optional[str]
    subject: Optional[str]
    body: str
    is_read: bool
    assigned_to_user_id: Optional[uuid.UUID]
    parent_message_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SendMessageIn(BaseModel):
    direction: str = Field(default="inbound", max_length=10)
    body: str
    sender_name: Optional[str] = Field(default=None, max_length=200)
    sender_contact: Optional[str] = Field(default=None, max_length=200)
    subject: Optional[str] = Field(default=None, max_length=300)


class AssignIn(BaseModel):
    user_id: uuid.UUID


class UnreadCountOut(BaseModel):
    total: int
    by_channel: dict[str, int]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/unread-count", response_model=UnreadCountOut)
async def get_unread_count(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        q = (
            select(UnifiedInboxThread.channel, func.count(UnifiedInboxThread.id).label("cnt"))
            .where(
                UnifiedInboxThread.org_id == org_id,
                UnifiedInboxThread.is_read.is_(False),
                UnifiedInboxThread.is_archived.is_(False),
            )
            .group_by(UnifiedInboxThread.channel)
        )
        rows = (await db.execute(q)).all()
        by_channel = {row.channel: row.cnt for row in rows}
        total = sum(by_channel.values())
        return UnreadCountOut(total=total, by_channel=by_channel)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_unread_count failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/threads", response_model=list[ThreadOut])
async def list_threads(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    channel: Optional[str] = Query(default=None),
    is_archived: bool = Query(default=False),
    is_read: Optional[bool] = Query(default=None),
    sentiment: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    try:
        org_id = _org_id(ctx)
        q = select(UnifiedInboxThread).where(
            UnifiedInboxThread.org_id == org_id,
            UnifiedInboxThread.is_archived == is_archived,
        )
        if channel:
            q = q.where(UnifiedInboxThread.channel == channel)
        if is_read is not None:
            q = q.where(UnifiedInboxThread.is_read == is_read)
        if sentiment:
            q = q.where(UnifiedInboxThread.sentiment == sentiment)
        q = q.order_by(UnifiedInboxThread.last_message_at.desc()).limit(limit).offset(offset)
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_threads failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/threads", response_model=ThreadOut, status_code=201)
async def create_thread(
    body: CreateThreadIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        thread = UnifiedInboxThread(
            org_id=org_id,
            customer_id=body.customer_id,
            channel=body.channel,
            subject=body.subject,
        )
        db.add(thread)
        await db.commit()
        await db.refresh(thread)
        return thread
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_thread failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/threads/{thread_id}", response_model=ThreadOut)
async def get_thread(
    thread_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        thread = await db.get(UnifiedInboxThread, thread_id)
        if not thread or thread.org_id != org_id:
            raise HTTPException(status_code=404, detail="Thread not found")
        return thread
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_thread failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/threads/{thread_id}/archive", response_model=ThreadOut)
async def archive_thread(
    thread_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        thread = await db.get(UnifiedInboxThread, thread_id)
        if not thread or thread.org_id != org_id:
            raise HTTPException(status_code=404, detail="Thread not found")
        thread.is_archived = True
        thread.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(thread)
        return thread
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"archive_thread failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/threads/{thread_id}/assign", response_model=ThreadOut)
async def assign_thread(
    thread_id: uuid.UUID,
    body: AssignIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        thread = await db.get(UnifiedInboxThread, thread_id)
        if not thread or thread.org_id != org_id:
            raise HTTPException(status_code=404, detail="Thread not found")
        thread.assigned_to_user_id = body.user_id
        thread.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(thread)
        return thread
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"assign_thread failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/threads/{thread_id}/messages", response_model=list[MessageOut])
async def list_thread_messages(
    thread_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    try:
        org_id = _org_id(ctx)
        thread = await db.get(UnifiedInboxThread, thread_id)
        if not thread or thread.org_id != org_id:
            raise HTTPException(status_code=404, detail="Thread not found")
        q = (
            select(UnifiedMessage)
            .where(UnifiedMessage.thread_id == thread_id, UnifiedMessage.org_id == org_id)
            .order_by(UnifiedMessage.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await db.execute(q)).scalars().all()
        return rows
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_thread_messages failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/threads/{thread_id}/messages", response_model=MessageOut, status_code=201)
async def send_message(
    thread_id: uuid.UUID,
    body: SendMessageIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        thread = await db.get(UnifiedInboxThread, thread_id)
        if not thread or thread.org_id != org_id:
            raise HTTPException(status_code=404, detail="Thread not found")
        msg = UnifiedMessage(
            org_id=org_id,
            thread_id=thread_id,
            channel=thread.channel,
            direction=body.direction,
            body=body.body,
            sender_name=body.sender_name,
            sender_contact=body.sender_contact,
            subject=body.subject,
        )
        db.add(msg)
        thread.last_message_at = datetime.now(timezone.utc)
        thread.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(msg)
        return msg
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"send_message failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/messages/{message_id}/read", response_model=MessageOut)
async def mark_message_read(
    message_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = _org_id(ctx)
        msg = await db.get(UnifiedMessage, message_id)
        if not msg or msg.org_id != org_id:
            raise HTTPException(status_code=404, detail="Message not found")
        msg.is_read = True
        msg.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(msg)
        return msg
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"mark_message_read failed: {e}", extra={"org_id": str(_org_id(ctx))})
        raise HTTPException(status_code=500, detail="Internal server error")
