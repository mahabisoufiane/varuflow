"""Email-campaign router (Item 40, v55).

Endpoints under ``/api/campaigns``:

CRUD:

* ``GET    /``                      — list campaigns.
* ``POST   /``                      — create draft.
* ``GET    /{id}``                  — detail.
* ``PATCH  /{id}``                  — edit draft (forbidden once SENT).
* ``DELETE /{id}``                  — delete draft / scheduled (not SENT).

Operational:

* ``POST   /{id}/preview``          — render the final HTML (returns
  body) or send a test to ``to``.
* ``POST   /{id}/send``             — dispatch now (draft / scheduled).
* ``POST   /{id}/schedule``         — set scheduled_at, flip status.
* ``GET    /{id}/sends``            — per-recipient delivery ledger.
* ``GET    /{id}/stats``            — aggregate counters (open / bounce).

Public (no auth):

* ``GET    /unsubscribe?token=…``   — HMAC-signed opt-out handler.

All mutations call :func:`log_action`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from app.models.campaigns import (
    Campaign,
    CampaignSend,
    CampaignSendStatus,
    CampaignStatus,
)
from app.models.invoicing import Customer
from app.models.organization import Organization
from app.models.segments import Segment
from app.services import campaign_engine as svc
from app.services.audit import log_action

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"], dependencies=[Depends(require_module("crm"))])


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _actor(ctx: tuple) -> uuid.UUID | None:
    user, _ = ctx
    uid = user.get("user_id")
    if isinstance(uid, uuid.UUID):
        return uid
    try:
        return uuid.UUID(str(uid))
    except Exception:
        return None


async def _load(
    db: AsyncSession, *, campaign_id: uuid.UUID, org_id: uuid.UUID,
) -> Campaign:
    c = await db.scalar(
        select(Campaign).where(
            Campaign.id == campaign_id, Campaign.org_id == org_id,
        )
    )
    if c is None:
        raise HTTPException(status_code=404, detail="campaign_not_found")
    return c


async def _org_name(db: AsyncSession, org_id: uuid.UUID) -> str:
    org = await db.get(Organization, org_id)
    return getattr(org, "name", "") if org else ""


def _unsubscribe_base() -> str:
    # Separate helper so tests + the engine can override without
    # monkey-patching settings. The FRONTEND_URL is the public host;
    # the unsubscribe endpoint is co-located on the backend so a
    # frontend redeploy doesn't invalidate live unsubscribe tokens.
    return f"{settings.FRONTEND_URL}/api/campaigns/unsubscribe"


# ═══════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════


class CampaignCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    subject: str = Field(min_length=1, max_length=300)
    body_html: str = Field(min_length=1)
    segment_id: uuid.UUID | None = None


class CampaignUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    subject: str | None = Field(default=None, min_length=1, max_length=300)
    body_html: str | None = None
    segment_id: uuid.UUID | None = None


class CampaignScheduleIn(BaseModel):
    scheduled_at: datetime


class CampaignPreviewIn(BaseModel):
    to: EmailStr | None = None  # when set, deliver a test email


class CampaignOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    subject: str
    body_html: str
    segment_id: uuid.UUID | None
    status: CampaignStatus
    scheduled_at: datetime | None
    sent_at: datetime | None
    recipient_count: int
    created_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SendOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    email: str
    status: CampaignSendStatus
    sent_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PreviewOut(BaseModel):
    body_html: str
    recipient_count: int


class StatsOut(BaseModel):
    total: int
    sent: int
    failed: int
    bounced: int
    opened: int
    open_rate: float
    bounce_rate: float


# ═══════════════════════════════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════════════════════════════


@router.get("", response_model=list[CampaignOut])
async def list_campaigns(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    status_filter: CampaignStatus | None = Query(None, alias="status"),
):
    org_id = _org(ctx)
    stmt = (
        select(Campaign)
        .where(Campaign.org_id == org_id)
        .order_by(Campaign.created_at.desc())
    )
    if status_filter is not None:
        stmt = stmt.where(Campaign.status == status_filter)
    rows = (await db.execute(stmt)).scalars().all()
    return rows


@router.get("/{campaign_id}", response_model=CampaignOut)
async def get_campaign(
    campaign_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    return await _load(db, campaign_id=campaign_id, org_id=_org(ctx))


@router.post("", response_model=CampaignOut, status_code=201)
async def create_campaign(
    body: CampaignCreateIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)

    # Validate the segment belongs to the same org so a forged
    # segment_id can't link a campaign to another tenant's audience.
    if body.segment_id is not None:
        seg = await db.scalar(
            select(Segment).where(
                Segment.id == body.segment_id, Segment.org_id == org_id,
            )
        )
        if seg is None:
            raise HTTPException(status_code=404, detail="segment_not_found")

    c = Campaign(
        id=uuid.uuid4(),
        org_id=org_id,
        name=body.name.strip(),
        subject=body.subject.strip(),
        body_html=body.body_html,
        segment_id=body.segment_id,
        status=CampaignStatus.DRAFT,
        created_by=_actor(ctx),
    )
    db.add(c)
    await db.flush()
    await log_action(
        db,
        action="campaign.created",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="campaign",
        target_id=str(c.id),
        request=request,
        extra={"name": c.name},
    )
    await db.commit()
    return await _load(db, campaign_id=c.id, org_id=org_id)


@router.patch("/{campaign_id}", response_model=CampaignOut)
async def update_campaign(
    campaign_id: uuid.UUID,
    body: CampaignUpdateIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    c = await _load(db, campaign_id=campaign_id, org_id=org_id)
    if c.status == CampaignStatus.SENT:
        raise HTTPException(status_code=409, detail="campaign_already_sent")

    changes: dict[str, Any] = {}
    if body.name is not None and body.name.strip() != c.name:
        c.name = body.name.strip()
        changes["name"] = c.name
    if body.subject is not None:
        c.subject = body.subject.strip()
        changes["subject"] = True
    if body.body_html is not None:
        c.body_html = body.body_html
        changes["body"] = True
    if body.segment_id is not None:
        seg = await db.scalar(
            select(Segment).where(
                Segment.id == body.segment_id, Segment.org_id == org_id,
            )
        )
        if seg is None:
            raise HTTPException(status_code=404, detail="segment_not_found")
        c.segment_id = body.segment_id
        changes["segment_id"] = str(body.segment_id)

    await log_action(
        db,
        action="campaign.updated",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="campaign",
        target_id=str(c.id),
        request=request,
        extra=changes,
    )
    await db.commit()
    return await _load(db, campaign_id=c.id, org_id=org_id)


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    c = await _load(db, campaign_id=campaign_id, org_id=org_id)
    if c.status == CampaignStatus.SENT:
        # A sent campaign is business-record evidence; refuse to
        # delete. Archival happens through GDPR purge elsewhere.
        raise HTTPException(status_code=409, detail="campaign_already_sent")
    await db.delete(c)
    await log_action(
        db,
        action="campaign.deleted",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="campaign",
        target_id=str(campaign_id),
        request=request,
    )
    await db.commit()
    return Response(status_code=204)


# ═══════════════════════════════════════════════════════════════════
# Operational
# ═══════════════════════════════════════════════════════════════════


@router.post("/{campaign_id}/preview", response_model=PreviewOut)
async def preview_campaign(
    campaign_id: uuid.UUID,
    body: CampaignPreviewIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Render the final HTML. If ``body.to`` is provided, also send a
    single test email to that address so the operator can eyeball the
    actual inbox rendering before committing to a broadcast."""
    from app.services.email import send_campaign_email

    org_id = _org(ctx)
    c = await _load(db, campaign_id=campaign_id, org_id=org_id)
    org_name = await _org_name(db, org_id)

    # Preview uses the engine's signed token so the footer URL in the
    # preview looks exactly like the production link. The token is
    # still safe to expose — only flips the sender's own opt-out, and
    # the sender is the one previewing.
    token = svc.sign_unsubscribe_token(
        campaign_id=c.id,
        customer_id=_actor(ctx) or uuid.UUID("00000000-0000-0000-0000-000000000000"),
        secret=settings.AUTH_JWT_SECRET,
    )
    unsubscribe_url = f"{_unsubscribe_base()}?token={token}"
    rendered = svc.inject_gdpr_footer(
        svc.sanitize_body_html(c.body_html or ""),
        unsubscribe_url=unsubscribe_url,
        org_name=org_name,
    )

    recipient_count = 0
    if c.segment_id is not None:
        recipients = await svc.build_recipient_list(
            db, segment_id=c.segment_id, org_id=org_id,
        )
        recipient_count = len(recipients)

    if body.to:
        await send_campaign_email(
            to_email=str(body.to),
            subject=f"[PREVIEW] {c.subject}",
            body_html=rendered,
            org_name=org_name,
        )

    await log_action(
        db,
        action="campaign.previewed",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="campaign",
        target_id=str(c.id),
        request=request,
        extra={"test_send": bool(body.to), "recipient_count": recipient_count},
    )
    await db.commit()
    return PreviewOut(body_html=rendered, recipient_count=recipient_count)


@router.post("/{campaign_id}/send", response_model=CampaignOut)
async def send_campaign_now(
    campaign_id: uuid.UUID,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    c = await _load(db, campaign_id=campaign_id, org_id=org_id)
    if c.status == CampaignStatus.SENT:
        raise HTTPException(status_code=409, detail="campaign_already_sent")
    if c.segment_id is None:
        raise HTTPException(status_code=400, detail="campaign_no_segment")

    org_name = await _org_name(db, org_id)
    count = await svc.send_campaign(
        db,
        campaign=c,
        org_name=org_name,
        base_unsubscribe_url=_unsubscribe_base(),
        secret=settings.AUTH_JWT_SECRET,
    )

    await log_action(
        db,
        action="campaign.sent",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="campaign",
        target_id=str(c.id),
        request=request,
        extra={"recipient_count": count},
    )
    await db.commit()
    return await _load(db, campaign_id=c.id, org_id=org_id)


@router.post("/{campaign_id}/schedule", response_model=CampaignOut)
async def schedule_campaign(
    campaign_id: uuid.UUID,
    body: CampaignScheduleIn,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    c = await _load(db, campaign_id=campaign_id, org_id=org_id)
    if c.status == CampaignStatus.SENT:
        raise HTTPException(status_code=409, detail="campaign_already_sent")
    if c.segment_id is None:
        raise HTTPException(status_code=400, detail="campaign_no_segment")

    scheduled_at = body.scheduled_at
    if scheduled_at.tzinfo is None:
        # Be lenient: the UI posts an ISO datetime; naive timestamps
        # are interpreted as UTC so the scheduler's UTC comparison
        # fires at the expected wall-clock moment.
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)

    # Reject "schedule in the past" outright — an accidental timezone
    # swap must not trigger an instantaneous send without a second
    # click on the explicit /send endpoint.
    if scheduled_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="scheduled_at_in_past")

    c.scheduled_at = scheduled_at
    c.status = CampaignStatus.SCHEDULED

    await log_action(
        db,
        action="campaign.scheduled",
        org_id=org_id,
        actor_user_id=_actor(ctx),
        target_type="campaign",
        target_id=str(c.id),
        request=request,
        extra={"scheduled_at": scheduled_at.isoformat()},
    )
    await db.commit()
    return await _load(db, campaign_id=c.id, org_id=org_id)


@router.get("/{campaign_id}/sends", response_model=list[SendOut])
async def list_sends(
    campaign_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    await _load(db, campaign_id=campaign_id, org_id=org_id)
    rows = (
        await db.execute(
            select(CampaignSend)
            .where(CampaignSend.campaign_id == campaign_id)
            .order_by(CampaignSend.sent_at.asc())
        )
    ).scalars().all()
    return rows


@router.get("/{campaign_id}/stats", response_model=StatsOut)
async def campaign_stats(
    campaign_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    await _load(db, campaign_id=campaign_id, org_id=org_id)
    rows = (
        await db.execute(
            select(CampaignSend.status).where(
                CampaignSend.campaign_id == campaign_id,
            )
        )
    ).scalars().all()
    stats = svc.compute_stats(
        # Enum → str: the model stores an enum but the pure helper
        # accepts plain strings so it has no ORM dependency.
        r.value if hasattr(r, "value") else str(r) for r in rows
    )
    return StatsOut(**stats.to_dict())


# ═══════════════════════════════════════════════════════════════════
# Inline block editor (Item 63)
# ═══════════════════════════════════════════════════════════════════

from app.services import email_blocks as _blk_63  # noqa: E402


class _BlockRenderRequest(BaseModel):
    blocks: list[dict]


class _BlockRenderResponse(BaseModel):
    html: str
    text: str
    blocks: list[dict]


class _CampaignBlocksPatch(BaseModel):
    blocks:  list[dict]
    subject: str | None = None


@router.post("/render-blocks", response_model=_BlockRenderResponse)
async def render_campaign_blocks(
    body: _BlockRenderRequest,
    _ctx: tuple = Depends(get_current_member),
):
    """Stateless preview: validate + render the block document.

    Used by the editor to show the live preview pane. No campaign row
    is touched, so no audit log entry is produced.
    """
    try:
        normalised = _blk_63.validate_blocks(body.blocks)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _BlockRenderResponse(
        html=_blk_63.render_html(normalised),
        text=_blk_63.render_text(normalised),
        blocks=normalised,
    )


@router.patch("/{campaign_id}/blocks", response_model=CampaignOut)
async def set_campaign_blocks(
    campaign_id: uuid.UUID,
    body: _CampaignBlocksPatch,
    request: Request,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Attach a block document to a draft/scheduled campaign.

    Rendering runs server-side so the stored ``body_html`` is always
    the trusted, escaped output of ``render_html`` — clients cannot
    slip raw HTML through this endpoint.
    """
    campaign = await _load(db, campaign_id=campaign_id, org_id=_org(ctx))
    if campaign.status == CampaignStatus.SENT:
        raise HTTPException(status_code=409, detail="cannot edit SENT campaign")

    try:
        normalised = _blk_63.validate_blocks(body.blocks)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    campaign.blocks = normalised
    campaign.body_html = _blk_63.render_html(normalised)
    if body.subject is not None:
        s = body.subject.strip()
        if not s:
            raise HTTPException(status_code=400, detail="subject is required")
        if len(s) > 300:
            raise HTTPException(status_code=400, detail="subject too long")
        campaign.subject = s

    await log_action(
        db,
        action="campaign.blocks_updated",
        org_id=_org(ctx),
        actor_user_id=_actor(ctx),
        target_type="campaign",
        target_id=str(campaign.id),
        ip_address=request.client.host if request.client else None,
        extra={"block_count": len(normalised)},
    )
    await db.commit()
    await db.refresh(campaign)
    return campaign


# ═══════════════════════════════════════════════════════════════════
# Public unsubscribe
# ═══════════════════════════════════════════════════════════════════


@router.get("/unsubscribe")
async def unsubscribe(
    request: Request,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Public, unauthenticated endpoint that flips a customer's
    ``email_opted_out`` flag. The token is a HMAC-signed
    ``{campaign}.{customer}`` pair — a forged or tampered token is
    indistinguishable from noise and rejected with 400."""
    parsed = svc.verify_unsubscribe_token(
        token, secret=settings.AUTH_JWT_SECRET,
    )
    if parsed is None:
        raise HTTPException(status_code=400, detail="invalid_token")
    campaign_id, customer_id = parsed

    # Load the campaign to know which org to attribute the audit to.
    # A campaign deleted between send and click still lets the user
    # opt out — the customer_id is signed, so we trust it even when
    # the campaign row no longer exists.
    campaign = await db.get(Campaign, campaign_id)
    org_id = campaign.org_id if campaign else None

    changed = await svc.mark_unsubscribed(db, customer_id=customer_id)
    if changed:
        await log_action(
            db,
            action="campaign.unsubscribed",
            org_id=org_id,
            actor_user_id=None,
            target_type="customer",
            target_id=str(customer_id),
            request=request,
            extra={"campaign_id": str(campaign_id)},
        )
    await db.commit()

    # Simple HTML confirmation — the unsubscribe click comes from an
    # email client so an HTML response is friendlier than JSON. Keep
    # the body trivial so no assets need to load.
    html_body = (
        "<html><body style='font-family:sans-serif;max-width:480px;"
        "margin:40px auto;text-align:center'>"
        "<h2 style='color:#1a2332'>You have been unsubscribed</h2>"
        "<p style='color:#555'>You will no longer receive marketing "
        "emails from this sender. Transactional messages (invoices, "
        "order receipts) continue as normal.</p></body></html>"
    )
    return Response(content=html_body, media_type="text/html; charset=utf-8")
