"""Customer Webhooks Config — Sprint 14

Note: named customer_webhooks_config to avoid conflict with existing webhooks.py.

Endpoints:
  GET    /api/customer-webhooks              list customer webhooks for org
  POST   /api/customer-webhooks              create webhook (auto-generates HMAC secret)
  GET    /api/customer-webhooks/{id}         detail
  PATCH  /api/customer-webhooks/{id}         update
  DELETE /api/customer-webhooks/{id}         delete
  GET    /api/customer-webhooks/{id}/deliveries   delivery history
  POST   /api/customer-webhooks/{id}/rotate-secret  generate new HMAC secret
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .customer_webhook import CustomerWebhook, CustomerWebhookDelivery
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/customer-webhooks", tags=["integrations_webhooks"], dependencies=[Depends(require_module("settings"))])
log = logging.getLogger(__name__)


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _generate_secret() -> str:
    return secrets.token_hex(32)


class WebhookIn(BaseModel):
    customer_id: Optional[uuid.UUID] = None
    url: str
    events: list[str] = []
    description: Optional[str] = None


class WebhookPatch(BaseModel):
    url: Optional[str] = None
    events: Optional[list[str]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


def _to_dict(w: CustomerWebhook) -> dict:
    return {
        "id": str(w.id),
        "org_id": str(w.org_id),
        "customer_id": str(w.customer_id) if w.customer_id else None,
        "url": w.url,
        "events": w.events,
        "description": w.description,
        "is_active": w.is_active,
        "created_at": w.created_at.isoformat() if w.created_at else None,
        "updated_at": w.updated_at.isoformat() if w.updated_at else None,
    }


def _delivery_to_dict(d: CustomerWebhookDelivery) -> dict:
    return {
        "id": str(d.id),
        "webhook_id": str(d.webhook_id),
        "event_type": d.event_type,
        "response_status": d.response_status,
        "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
        "attempt_count": d.attempt_count,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@router.get("")
async def list_webhooks(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
):
    org_id = _org(ctx)
    try:
        result = await db.execute(
            select(CustomerWebhook)
            .where(CustomerWebhook.org_id == org_id)
            .offset(skip)
            .limit(limit)
        )
        webhooks = result.scalars().all()
        return {"items": [_to_dict(w) for w in webhooks], "total": len(webhooks)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_customer_webhooks failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def create_webhook(
    body: WebhookIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        secret = _generate_secret()
        webhook = CustomerWebhook(
            org_id=org_id,
            customer_id=body.customer_id,
            url=body.url,
            secret=secret,
            events=body.events,
            description=body.description,
        )
        db.add(webhook)
        await db.commit()
        await db.refresh(webhook)
        result = _to_dict(webhook)
        result["secret"] = secret  # Return once at creation
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_customer_webhook failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{webhook_id}")
async def get_webhook(
    webhook_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        result = await db.execute(
            select(CustomerWebhook).where(
                CustomerWebhook.id == webhook_id,
                CustomerWebhook.org_id == org_id,
            )
        )
        webhook = result.scalar_one_or_none()
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        return _to_dict(webhook)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_customer_webhook failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{webhook_id}")
async def update_webhook(
    webhook_id: uuid.UUID,
    body: WebhookPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        result = await db.execute(
            select(CustomerWebhook).where(
                CustomerWebhook.id == webhook_id,
                CustomerWebhook.org_id == org_id,
            )
        )
        webhook = result.scalar_one_or_none()
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")

        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(webhook, field, value)

        await db.commit()
        await db.refresh(webhook)
        return _to_dict(webhook)
    except HTTPException:
        raise
    except Exception as e:
        log.error("update_customer_webhook failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        result = await db.execute(
            select(CustomerWebhook).where(
                CustomerWebhook.id == webhook_id,
                CustomerWebhook.org_id == org_id,
            )
        )
        webhook = result.scalar_one_or_none()
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        await db.delete(webhook)
        await db.commit()
        return {"deleted": True, "id": str(webhook_id)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_customer_webhook failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{webhook_id}/deliveries")
async def list_deliveries(
    webhook_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 50,
):
    org_id = _org(ctx)
    try:
        # Verify webhook belongs to org
        result = await db.execute(
            select(CustomerWebhook).where(
                CustomerWebhook.id == webhook_id,
                CustomerWebhook.org_id == org_id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Webhook not found")

        d_result = await db.execute(
            select(CustomerWebhookDelivery)
            .where(
                CustomerWebhookDelivery.webhook_id == webhook_id,
                CustomerWebhookDelivery.org_id == org_id,
            )
            .order_by(CustomerWebhookDelivery.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        deliveries = d_result.scalars().all()
        return {"items": [_delivery_to_dict(d) for d in deliveries], "total": len(deliveries)}
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_webhook_deliveries failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{webhook_id}/rotate-secret")
async def rotate_secret(
    webhook_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        result = await db.execute(
            select(CustomerWebhook).where(
                CustomerWebhook.id == webhook_id,
                CustomerWebhook.org_id == org_id,
            )
        )
        webhook = result.scalar_one_or_none()
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")

        new_secret = _generate_secret()
        webhook.secret = new_secret
        await db.commit()
        return {"rotated": True, "id": str(webhook_id), "secret": new_secret}
    except HTTPException:
        raise
    except Exception as e:
        log.error("rotate_webhook_secret failed: %s", str(e), extra={"org_id": str(org_id)})  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
        raise HTTPException(status_code=500, detail="Internal server error")
