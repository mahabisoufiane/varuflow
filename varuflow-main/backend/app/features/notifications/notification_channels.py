"""Slack + Teams notification channels

Endpoints:
  GET  /api/integrations/notifications/channels
  POST /api/integrations/notifications/channels
  PATCH /api/integrations/notifications/channels/{id}
  DELETE /api/integrations/notifications/channels/{id}
  POST /api/integrations/notifications/channels/{id}/test

Internal service:
  fire_notification(db, org_id, event_type, payload) — import and call from other routers
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.features.integrations.models import NotificationChannel
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/integrations/notifications", tags=["integrations_notifications"], dependencies=[Depends(require_module("settings"))])
log = logging.getLogger(__name__)

SUPPORTED_EVENTS = [
    "stock.low",
    "invoice.overdue",
    "new_po",
    "payment_received",
    "customer.created",
    "invoice.created",
    "invoice.paid",
]


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChannelIn(BaseModel):
    channel_type: str    # slack | teams
    name: str
    webhook_url: str
    events: list[str]
    is_active: bool = True

class ChannelPatch(BaseModel):
    name: Optional[str] = None
    webhook_url: Optional[str] = None
    events: Optional[list[str]] = None
    is_active: Optional[bool] = None

class ChannelOut(BaseModel):
    id: str
    channel_type: str
    name: str
    webhook_url: str
    events: list[str]
    is_active: bool
    last_sent_at: Optional[str]
    created_at: str

class ChannelsOut(BaseModel):
    channels: list[ChannelOut]


def _out(ch: NotificationChannel) -> ChannelOut:
    return ChannelOut(
        id=str(ch.id),
        channel_type=ch.channel_type,
        name=ch.name,
        webhook_url=ch.webhook_url,
        events=ch.events or [],
        is_active=ch.is_active,
        last_sent_at=ch.last_sent_at.isoformat() if ch.last_sent_at else None,
        created_at=ch.created_at.isoformat(),
    )


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _build_slack_payload(event_type: str, payload: dict[str, Any]) -> dict:
    text = payload.get("message", f"Varuflow event: {event_type}")
    return {
        "text": text,
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f"Varuflow — {event_type.replace('.', ' ').title()}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        ],
    }


def _build_teams_payload(event_type: str, payload: dict[str, Any]) -> dict:
    text = payload.get("message", f"Varuflow event: {event_type}")
    return {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": f"Varuflow — {event_type}",
        "sections": [{"activityTitle": f"**{event_type.replace('.', ' ').title()}**", "text": text}],
    }


# ── Service function (importable) ─────────────────────────────────────────────

async def fire_notification(
    db: AsyncSession,
    org_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Post to all active notification channels subscribed to event_type."""
    try:
        rows = await db.execute(
            select(NotificationChannel).where(
                NotificationChannel.org_id == org_id,
                NotificationChannel.is_active == True,  # noqa: E712
            )
        )
        channels = [ch for ch in rows.scalars() if event_type in (ch.events or [])]
        if not channels:
            return

        async with httpx.AsyncClient(timeout=10) as client:
            for ch in channels:
                try:
                    if ch.channel_type == "slack":
                        body = _build_slack_payload(event_type, payload)
                    else:
                        body = _build_teams_payload(event_type, payload)

                    await client.post(ch.webhook_url, json=body)
                    ch.last_sent_at = datetime.now(timezone.utc)
                except Exception as ex:
                    log.warning("fire_notification channel %s failed: %s", ch.id, str(ex))

        await db.commit()
    except Exception as e:
        log.error("fire_notification failed: %s", str(e), extra={"org_id": str(org_id)})


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/channels", response_model=ChannelsOut)
async def list_channels(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        rows = await db.execute(
            select(NotificationChannel)
            .where(NotificationChannel.org_id == org_id)
            .order_by(NotificationChannel.created_at.desc())
        )
        return ChannelsOut(channels=[_out(ch) for ch in rows.scalars()])
    except Exception as e:
        log.error("list_channels failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/channels", response_model=ChannelOut)
async def create_channel(
    body: ChannelIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        if body.channel_type not in ("slack", "teams"):
            raise HTTPException(status_code=422, detail="channel_type must be 'slack' or 'teams'")
        invalid_events = [e for e in body.events if e not in SUPPORTED_EVENTS]
        if invalid_events:
            raise HTTPException(status_code=422, detail=f"Unknown events: {invalid_events}. Valid: {SUPPORTED_EVENTS}")

        ch = NotificationChannel(
            org_id=org_id,
            channel_type=body.channel_type,
            name=body.name,
            webhook_url=body.webhook_url,
            events=body.events,
            is_active=body.is_active,
        )
        db.add(ch)
        await db.commit()
        await db.refresh(ch)
        return _out(ch)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_channel failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/channels/{channel_id}", response_model=ChannelOut)
async def update_channel(
    channel_id: uuid.UUID,
    body: ChannelPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(NotificationChannel).where(
                NotificationChannel.id == channel_id,
                NotificationChannel.org_id == org_id,
            )
        )
        ch = row.scalar_one_or_none()
        if not ch:
            raise HTTPException(status_code=404, detail="Channel not found")
        if body.name is not None:
            ch.name = body.name
        if body.webhook_url is not None:
            ch.webhook_url = body.webhook_url
        if body.events is not None:
            ch.events = body.events
        if body.is_active is not None:
            ch.is_active = body.is_active
        await db.commit()
        await db.refresh(ch)
        return _out(ch)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_channel failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(NotificationChannel).where(
                NotificationChannel.id == channel_id,
                NotificationChannel.org_id == org_id,
            )
        )
        ch = row.scalar_one_or_none()
        if not ch:
            raise HTTPException(status_code=404, detail="Channel not found")
        await db.delete(ch)
        await db.commit()
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_channel failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/channels/{channel_id}/test")
async def test_channel(
    channel_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        row = await db.execute(
            select(NotificationChannel).where(
                NotificationChannel.id == channel_id,
                NotificationChannel.org_id == org_id,
            )
        )
        ch = row.scalar_one_or_none()
        if not ch:
            raise HTTPException(status_code=404, detail="Channel not found")

        if ch.channel_type == "slack":
            body = {"text": "Test notification from Varuflow — your Slack integration is working!"}
        else:
            body = {
                "@type": "MessageCard",
                "@context": "https://schema.org/extensions",
                "summary": "Varuflow test",
                "text": "Test notification from Varuflow — your Teams integration is working!",
            }

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(ch.webhook_url, json=body)

        if resp.status_code not in (200, 201, 204):
            raise HTTPException(status_code=502, detail=f"Webhook returned {resp.status_code}")

        ch.last_sent_at = datetime.now(timezone.utc)
        await db.commit()
        return {"sent": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error("test_channel failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
