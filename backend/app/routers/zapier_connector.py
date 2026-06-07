"""Zapier / Make.com connector — Sprint 14 (zapier_hooks table)

Separate from the existing zapier_connect.py (REST-hook subscribe/actions).
This router manages the new zapier_hooks and zapier_event_logs tables.

Endpoints:
  GET    /api/zapier/hooks              list hooks for org
  POST   /api/zapier/hooks              create hook
  DELETE /api/zapier/hooks/{id}         remove hook
  GET    /api/zapier/event-logs         list event logs
  POST   /api/zapier/test-fire          fire a test event to a hook
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.zapier import ZapierHook, ZapierEventLog
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/zapier", tags=["integrations_zapier"], dependencies=[Depends(require_module("settings"))])
log = logging.getLogger(__name__)

VALID_HOOK_TYPES = {"zapier", "make", "generic"}


def _org_user(ctx: tuple) -> tuple[uuid.UUID, uuid.UUID]:
    _, member = ctx
    return member.org_id, member.user_id


class HookIn(BaseModel):
    subscribe_url: str
    event_type: str
    hook_type: str = "zapier"


class TestFireIn(BaseModel):
    hook_id: uuid.UUID
    event_type: str
    payload: Optional[dict] = None


def _hook_to_dict(h: ZapierHook) -> dict:
    return {
        "id": str(h.id),
        "org_id": str(h.org_id),
        "user_id": str(h.user_id),
        "subscribe_url": h.subscribe_url,
        "event_type": h.event_type,
        "hook_type": h.hook_type,
        "is_active": h.is_active,
        "created_at": h.created_at.isoformat() if h.created_at else None,
    }


def _log_to_dict(e: ZapierEventLog) -> dict:
    return {
        "id": str(e.id),
        "org_id": str(e.org_id),
        "hook_id": str(e.hook_id) if e.hook_id else None,
        "event_type": e.event_type,
        "status": e.status,
        "attempt_count": e.attempt_count,
        "response_status": e.response_status,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


@router.get("/hooks")
async def list_hooks(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
):
    org_id, _ = _org_user(ctx)
    try:
        result = await db.execute(
            select(ZapierHook)
            .where(ZapierHook.org_id == org_id)
            .offset(skip)
            .limit(limit)
        )
        hooks = result.scalars().all()
        return {"items": [_hook_to_dict(h) for h in hooks], "total": len(hooks)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_zapier_hooks failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/hooks", status_code=201)
async def create_hook(
    body: HookIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id, user_id = _org_user(ctx)
    try:
        if body.hook_type not in VALID_HOOK_TYPES:
            raise HTTPException(status_code=422, detail=f"hook_type must be one of {VALID_HOOK_TYPES}")

        hook = ZapierHook(
            org_id=org_id,
            user_id=user_id,
            subscribe_url=body.subscribe_url,
            event_type=body.event_type,
            hook_type=body.hook_type,
        )
        db.add(hook)
        await db.commit()
        await db.refresh(hook)
        return _hook_to_dict(hook)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_zapier_hook failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/hooks/{hook_id}")
async def delete_hook(
    hook_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id, _ = _org_user(ctx)
    try:
        result = await db.execute(
            select(ZapierHook).where(
                ZapierHook.id == hook_id,
                ZapierHook.org_id == org_id,
            )
        )
        hook = result.scalar_one_or_none()
        if not hook:
            raise HTTPException(status_code=404, detail="Hook not found")
        await db.delete(hook)
        await db.commit()
        return {"deleted": True, "id": str(hook_id)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_zapier_hook failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/event-logs")
async def list_event_logs(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
):
    org_id, _ = _org_user(ctx)
    try:
        stmt = select(ZapierEventLog).where(ZapierEventLog.org_id == org_id)
        if status:
            stmt = stmt.where(ZapierEventLog.status == status)
        if event_type:
            stmt = stmt.where(ZapierEventLog.event_type == event_type)
        stmt = stmt.offset(skip).limit(limit)
        result = await db.execute(stmt)
        logs = result.scalars().all()
        return {"items": [_log_to_dict(e) for e in logs], "total": len(logs)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_zapier_event_logs failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/test-fire")
async def test_fire(
    body: TestFireIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id, _ = _org_user(ctx)
    try:
        result = await db.execute(
            select(ZapierHook).where(
                ZapierHook.id == body.hook_id,
                ZapierHook.org_id == org_id,
            )
        )
        hook = result.scalar_one_or_none()
        if not hook:
            raise HTTPException(status_code=404, detail="Hook not found")

        event_log = ZapierEventLog(
            org_id=org_id,
            hook_id=hook.id,
            event_type=body.event_type,
            payload=body.payload or {"test": True, "event_type": body.event_type},
            status="pending",
            attempt_count=0,
        )
        db.add(event_log)
        await db.commit()
        await db.refresh(event_log)
        return {
            "test_fired": True,
            "hook_id": str(hook.id),
            "subscribe_url": hook.subscribe_url,
            "event_log_id": str(event_log.id),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("zapier_test_fire failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
