"""Outbound webhooks (v30, ENTERPRISE-gated).

Lets a customer register HTTPS endpoints to receive event notifications
(``invoice.created``, ``invoice.paid``, ``stock.low``, ``order.placed``,
``customer.created``). The plaintext signing secret is returned ONCE
when an endpoint is created — the server only stores its SHA-256 hash.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_plan
from app.models.organization import OrgPlan, OrgRole
from app.models.webhook import (
    SUPPORTED_EVENTS,
    WebhookDelivery,
    WebhookEndpoint,
)
from app.services.webhook_dispatcher import generate_secret, hash_secret

router = APIRouter(
    prefix="/api/webhooks",
    tags=["webhooks"],
    dependencies=[Depends(require_plan(OrgPlan.ENTERPRISE))],
)


def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _require_owner_or_admin(ctx: tuple) -> None:
    """Webhooks expose tenant data to a third party; only owners and
    admins can create or remove them."""
    _, member = ctx
    if member.role not in (OrgRole.OWNER, OrgRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can manage webhooks",
        )


class EndpointCreate(BaseModel):
    url: HttpUrl
    events: list[str] = Field(..., min_length=1)


class EndpointOut(BaseModel):
    id: uuid.UUID
    url: str
    events: list[str]
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class EndpointCreated(EndpointOut):
    # Plaintext signing secret. Returned ONCE on creation. Customers
    # must store this server-side; we cannot recover it.
    secret: str
    secret_verification_hint: str = (
        "HMAC-SHA256 the request body with sha256(secret).hexdigest() "
        "as the key, then compare to the X-Varuflow-Signature header."
    )


class DeliveryOut(BaseModel):
    id: uuid.UUID
    endpoint_id: uuid.UUID
    event_type: str
    status_code: int | None
    delivered_at: datetime | None
    next_retry_at: datetime | None
    attempt_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post(
    "/endpoints",
    response_model=EndpointCreated,
    status_code=status.HTTP_201_CREATED,
)
async def register_endpoint(
    body: EndpointCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _require_owner_or_admin(ctx)

    # Reject http:// — replaying a webhook over plaintext leaks the
    # event payload (which contains invoice totals, customer emails,
    # etc.) and would let a network attacker forge events. Stripe and
    # GitHub have the same restriction for the same reason.
    parsed = urlparse(str(body.url))
    if parsed.scheme != "https":
        raise HTTPException(
            status_code=400,
            detail="Webhook URL must use HTTPS.",
        )

    bad = [e for e in body.events if e not in SUPPORTED_EVENTS]
    if bad:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported event(s): {', '.join(sorted(set(bad)))}",
        )

    secret = generate_secret()
    endpoint = WebhookEndpoint(
        org_id=_org_id(ctx),
        url=str(body.url),
        secret_hash=hash_secret(secret),
        events=list(dict.fromkeys(body.events)),  # de-dupe, preserve order
        active=True,
    )
    db.add(endpoint)
    await db.commit()
    await db.refresh(endpoint)

    return EndpointCreated(
        id=endpoint.id,
        url=endpoint.url,
        events=endpoint.events,
        active=endpoint.active,
        created_at=endpoint.created_at,
        secret=secret,
    )


@router.get("/endpoints", response_model=list[EndpointOut])
async def list_endpoints(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(WebhookEndpoint)
        .where(WebhookEndpoint.org_id == _org_id(ctx))
        .order_by(WebhookEndpoint.created_at.desc())
    )).scalars().all()
    return rows


@router.delete(
    "/endpoints/{endpoint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_endpoint(
    endpoint_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    _require_owner_or_admin(ctx)
    ep = await db.scalar(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == endpoint_id,
            WebhookEndpoint.org_id == _org_id(ctx),
        )
    )
    if not ep:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    # Soft-deactivate — keeps the delivery history queryable for audits.
    ep.active = False
    await db.commit()


@router.get("/deliveries", response_model=list[DeliveryOut])
async def list_deliveries(
    endpoint_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(WebhookDelivery)
        .join(WebhookEndpoint, WebhookEndpoint.id == WebhookDelivery.endpoint_id)
        .where(WebhookEndpoint.org_id == _org_id(ctx))
        .order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
    )
    if endpoint_id:
        q = q.where(WebhookDelivery.endpoint_id == endpoint_id)
    return (await db.execute(q)).scalars().all()
