"""Customer chat threads and messages.

Endpoints
─────────
GET    /api/chat/threads                      → list threads for org
POST   /api/chat/threads                      → create thread
GET    /api/chat/threads/{thread_id}          → detail + last 50 messages
PATCH  /api/chat/threads/{thread_id}          → update status
POST   /api/chat/threads/{thread_id}/messages → send message
PATCH  /api/chat/messages/{msg_id}/read       → mark message read
GET    /api/chat/unread-count                 → sum of unread across open threads
DELETE /api/chat/threads/{thread_id}          → delete thread + messages
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.customer_chat import CustomerChatMessage, CustomerChatThread

router = APIRouter(prefix="/api/chat", tags=["customer-chat"])
log = logging.getLogger(__name__)

_VALID_STATUSES = {"open", "resolved", "closed"}
_VALID_SENDER_TYPES = {"customer", "staff"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return uuid.UUID(str(user["user_id"]))


def _thread_out(thread: CustomerChatThread) -> dict[str, Any]:
    return {
        "id": str(thread.id),
        "org_id": str(thread.org_id),
        "customer_id": str(thread.customer_id) if thread.customer_id else None,
        "subject": thread.subject,
        "status": thread.status,
        "last_message_at": thread.last_message_at.isoformat() if thread.last_message_at else None,
        "unread_staff_count": thread.unread_staff_count,
        "created_at": thread.created_at.isoformat(),
        "updated_at": thread.updated_at.isoformat(),
    }


def _msg_out(msg: CustomerChatMessage) -> dict[str, Any]:
    return {
        "id": str(msg.id),
        "thread_id": str(msg.thread_id),
        "org_id": str(msg.org_id),
        "sender_type": msg.sender_type,
        "sender_id": str(msg.sender_id) if msg.sender_id else None,
        "body": msg.body,
        "attachment_url": msg.attachment_url,
        "attachment_type": msg.attachment_type,
        "read_at": msg.read_at.isoformat() if msg.read_at else None,
        "created_at": msg.created_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class ThreadIn(BaseModel):
    customer_id: Optional[uuid.UUID] = None
    subject: Optional[str] = Field(default=None, max_length=200)


class ThreadPatch(BaseModel):
    status: str


class MessageIn(BaseModel):
    body: str = Field(min_length=1)
    sender_type: str = Field(default="staff")
    attachment_url: Optional[str] = None
    attachment_type: Optional[str] = Field(default=None, max_length=50)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/threads")
async def list_threads(
    status: Optional[str] = Query(default=None),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all threads for the org, sorted by last_message_at desc."""
    org_id = _org_id(ctx)
    try:
        q = select(CustomerChatThread).where(CustomerChatThread.org_id == org_id)
        if status:
            q = q.where(CustomerChatThread.status == status)
        q = q.order_by(CustomerChatThread.last_message_at.desc().nullslast())
        threads = (await db.execute(q)).scalars().all()
        return [_thread_out(t) for t in threads]
    except Exception as e:
        log.error("list_threads failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/threads", status_code=201)
async def create_thread(
    body: ThreadIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        thread = CustomerChatThread(
            org_id=org_id,
            customer_id=body.customer_id,
            subject=body.subject,
        )
        db.add(thread)
        await db.commit()
        await db.refresh(thread)
        return _thread_out(thread)
    except Exception as e:
        log.error("create_thread failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/threads/{thread_id}")
async def get_thread(
    thread_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return thread detail plus last 50 messages sorted by created_at asc."""
    org_id = _org_id(ctx)
    try:
        thread = await db.scalar(
            select(CustomerChatThread).where(
                CustomerChatThread.id == thread_id,
                CustomerChatThread.org_id == org_id,
            )
        )
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        msgs = (await db.execute(
            select(CustomerChatMessage)
            .where(CustomerChatMessage.thread_id == thread_id)
            .order_by(CustomerChatMessage.created_at.asc())
            .limit(50)
        )).scalars().all()

        result = _thread_out(thread)
        result["messages"] = [_msg_out(m) for m in msgs]
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_thread failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/threads/{thread_id}")
async def patch_thread(
    thread_id: uuid.UUID,
    body: ThreadPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        thread = await db.scalar(
            select(CustomerChatThread).where(
                CustomerChatThread.id == thread_id,
                CustomerChatThread.org_id == org_id,
            )
        )
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        if body.status not in _VALID_STATUSES:
            raise HTTPException(
                status_code=422, detail=f"status must be one of {_VALID_STATUSES}"
            )
        thread.status = body.status
        thread.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(thread)
        return _thread_out(thread)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_thread failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/threads/{thread_id}/messages", status_code=201)
async def send_message(
    thread_id: uuid.UUID,
    body: MessageIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        thread = await db.scalar(
            select(CustomerChatThread).where(
                CustomerChatThread.id == thread_id,
                CustomerChatThread.org_id == org_id,
            )
        )
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        if body.sender_type not in _VALID_SENDER_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"sender_type must be one of {_VALID_SENDER_TYPES}",
            )

        msg = CustomerChatMessage(
            thread_id=thread_id,
            org_id=org_id,
            sender_type=body.sender_type,
            sender_id=user_id,
            body=body.body,
            attachment_url=body.attachment_url,
            attachment_type=body.attachment_type,
        )
        db.add(msg)

        now = datetime.now(timezone.utc)
        thread.last_message_at = now
        thread.updated_at = now
        if body.sender_type == "customer":
            thread.unread_staff_count = (thread.unread_staff_count or 0) + 1
        else:
            thread.unread_staff_count = 0

        await db.commit()
        await db.refresh(msg)
        return _msg_out(msg)
    except HTTPException:
        raise
    except Exception as e:
        log.error("send_message failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/messages/{msg_id}/read")
async def mark_message_read(
    msg_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        msg = await db.scalar(
            select(CustomerChatMessage).where(
                CustomerChatMessage.id == msg_id,
                CustomerChatMessage.org_id == org_id,
            )
        )
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")

        msg.read_at = datetime.now(timezone.utc)

        # Reset unread count on the parent thread
        thread = await db.scalar(
            select(CustomerChatThread).where(CustomerChatThread.id == msg.thread_id)
        )
        if thread:
            thread.unread_staff_count = 0
            thread.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(msg)
        return _msg_out(msg)
    except HTTPException:
        raise
    except Exception as e:
        log.error("mark_message_read failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/unread-count")
async def unread_count(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return total unread_staff_count sum across all open threads for the org."""
    org_id = _org_id(ctx)
    try:
        result = await db.scalar(
            select(func.coalesce(func.sum(CustomerChatThread.unread_staff_count), 0)).where(
                CustomerChatThread.org_id == org_id,
                CustomerChatThread.status == "open",
            )
        )
        return {"unread_count": int(result or 0)}
    except Exception as e:
        log.error("unread_count failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/threads/{thread_id}", status_code=204)
async def delete_thread(
    thread_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        thread = await db.scalar(
            select(CustomerChatThread).where(
                CustomerChatThread.id == thread_id,
                CustomerChatThread.org_id == org_id,
            )
        )
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        await db.delete(thread)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_thread failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
