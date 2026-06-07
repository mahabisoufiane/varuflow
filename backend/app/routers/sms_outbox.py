"""SMS / WhatsApp outbox router.

GET  /api/sms-outbox                  — list messages (filter: customer_id, channel, status)
POST /api/sms-outbox                  — queue / log a manual outbound message
GET  /api/sms-outbox/conversation/{number} — two-way thread with a phone number
GET  /api/sms-outbox/opt-outs         — list opt-outs
POST /api/sms-outbox/opt-outs         — add opt-out
DELETE /api/sms-outbox/opt-outs/{id}  — remove opt-out (re-allow)
POST /api/sms-outbox/webhook/twilio   — Twilio status/inbound callback (no auth)
PATCH /api/sms-outbox/{id}/status     — manually update status
"""
import hashlib
import hmac
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.sms_outbox import SmsMessage, SmsOptOut
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sms-outbox", tags=["sms_outbox"], dependencies=[Depends(require_module("crm"))])

TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")


# ── Schemas ───────────────────────────────────────────────────────────────────

class SmsIn(BaseModel):
    to_number: str
    body: str
    channel: str = "sms"          # sms | whatsapp
    customer_id: Optional[str] = None
    from_number: Optional[str] = None
    template_id: Optional[str] = None
    ref_type: Optional[str] = None
    ref_id: Optional[str] = None


class OptOutIn(BaseModel):
    phone_number: str
    channel: str = "sms"


class StatusPatch(BaseModel):
    status: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _msg_out(m: SmsMessage) -> dict:
    return {
        "id": str(m.id),
        "org_id": str(m.org_id),
        "customer_id": str(m.customer_id) if m.customer_id else None,
        "to_number": m.to_number,
        "from_number": m.from_number,
        "body": m.body,
        "channel": m.channel,
        "direction": m.direction,
        "status": m.status,
        "provider_sid": m.provider_sid,
        "delivered_at": m.delivered_at.isoformat() if m.delivered_at else None,
        "read_at": m.read_at.isoformat() if m.read_at else None,
        "cost_credits": float(m.cost_credits) if m.cost_credits is not None else None,
        "template_id": str(m.template_id) if m.template_id else None,
        "ref_type": m.ref_type,
        "ref_id": str(m.ref_id) if m.ref_id else None,
        "sent_at": m.sent_at.isoformat(),
        "created_at": m.created_at.isoformat(),
    }


async def _is_opted_out(db: AsyncSession, org_id, phone: str, channel: str) -> bool:
    r = (await db.execute(
        select(SmsOptOut).where(
            SmsOptOut.org_id == org_id,
            SmsOptOut.phone_number == phone,
            SmsOptOut.channel == channel,
        )
    )).scalar_one_or_none()
    return r is not None


# ── List / send ───────────────────────────────────────────────────────────────

@router.get("")
async def list_messages(
    customer_id: str | None = None,
    channel: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(SmsMessage).where(SmsMessage.org_id == org_id)
        if customer_id:
            q = q.where(SmsMessage.customer_id == uuid.UUID(customer_id))
        if channel:
            q = q.where(SmsMessage.channel == channel)
        if status:
            q = q.where(SmsMessage.status == status)
        q = q.order_by(SmsMessage.created_at.desc()).limit(limit).offset(offset)
        rows = (await db.execute(q)).scalars().all()
        return [_msg_out(m) for m in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_messages failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", status_code=201)
async def queue_message(
    body: SmsIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        if await _is_opted_out(db, org_id, body.to_number, body.channel):
            raise HTTPException(status_code=422, detail="Recipient has opted out")
        m = SmsMessage(
            org_id=org_id,
            to_number=body.to_number,
            body=body.body,
            channel=body.channel,
            direction="out",
            status="queued",
            customer_id=uuid.UUID(body.customer_id) if body.customer_id else None,
            from_number=body.from_number,
            template_id=uuid.UUID(body.template_id) if body.template_id else None,
            ref_type=body.ref_type,
            ref_id=uuid.UUID(body.ref_id) if body.ref_id else None,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)
        return _msg_out(m)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("queue_message failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/conversation/{number}")
async def get_conversation(
    number: str,
    channel: str = "sms",
    limit: int = 50,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return all messages (in + out) with a specific phone number."""
    try:
        org_id = member["org_id"]
        q = (
            select(SmsMessage)
            .where(
                SmsMessage.org_id == org_id,
                SmsMessage.channel == channel,
                or_(SmsMessage.to_number == number, SmsMessage.from_number == number),
            )
            .order_by(SmsMessage.created_at.asc())
            .limit(limit)
        )
        rows = (await db.execute(q)).scalars().all()
        return [_msg_out(m) for m in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_conversation failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{msg_id}/status")
async def update_status(
    msg_id: str,
    body: StatusPatch,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        VALID_STATUSES = {"queued", "sent", "delivered", "failed", "undelivered", "read"}
        if body.status not in VALID_STATUSES:
            raise HTTPException(status_code=422, detail=f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}")
        m = (await db.execute(
            select(SmsMessage).where(SmsMessage.id == uuid.UUID(msg_id), SmsMessage.org_id == org_id)
        )).scalar_one_or_none()
        if not m:
            raise HTTPException(status_code=404, detail="Message not found")
        m.status = body.status
        if body.status == "delivered" and not m.delivered_at:
            m.delivered_at = datetime.now(timezone.utc)
        await db.commit()
        return _msg_out(m)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_status failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Opt-outs ──────────────────────────────────────────────────────────────────

@router.get("/opt-outs")
async def list_opt_outs(
    channel: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(SmsOptOut).where(SmsOptOut.org_id == org_id)
        if channel:
            q = q.where(SmsOptOut.channel == channel)
        q = q.order_by(SmsOptOut.opted_out_at.desc())
        rows = (await db.execute(q)).scalars().all()
        return [
            {
                "id": str(r.id),
                "phone_number": r.phone_number,
                "channel": r.channel,
                "opted_out_at": r.opted_out_at.isoformat(),
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_opt_outs failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/opt-outs", status_code=201)
async def add_opt_out(
    body: OptOutIn,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        existing = (await db.execute(
            select(SmsOptOut).where(
                SmsOptOut.org_id == org_id,
                SmsOptOut.phone_number == body.phone_number,
                SmsOptOut.channel == body.channel,
            )
        )).scalar_one_or_none()
        if existing:
            return {"id": str(existing.id), "phone_number": existing.phone_number, "channel": existing.channel, "opted_out_at": existing.opted_out_at.isoformat()}
        r = SmsOptOut(org_id=org_id, phone_number=body.phone_number, channel=body.channel)
        db.add(r)
        await db.commit()
        await db.refresh(r)
        return {"id": str(r.id), "phone_number": r.phone_number, "channel": r.channel, "opted_out_at": r.opted_out_at.isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("add_opt_out failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/opt-outs/{opt_id}", status_code=204)
async def remove_opt_out(
    opt_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        r = (await db.execute(
            select(SmsOptOut).where(SmsOptOut.id == uuid.UUID(opt_id), SmsOptOut.org_id == org_id)
        )).scalar_one_or_none()
        if not r:
            raise HTTPException(status_code=404, detail="Opt-out not found")
        await db.delete(r)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("remove_opt_out failed: %s", e, extra={"org_id": str(member.get("org_id", ""))})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Twilio webhook (no auth — validated by signature) ─────────────────────────

@router.post("/webhook/twilio")
async def twilio_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handles:
    - Status callbacks (MessageStatus: sent/delivered/failed/undelivered)
    - Inbound SMS/WhatsApp (From, Body, To)
    Twilio signature validation is performed when TWILIO_AUTH_TOKEN is set.
    """
    try:
        body_bytes = await request.body()
        form = await request.form()
        data = dict(form)

        # Validate Twilio signature when auth token is configured
        if TWILIO_AUTH_TOKEN:
            sig = request.headers.get("X-Twilio-Signature", "")
            url = str(request.url)
            # Build the validation string: URL + sorted form params
            params_str = "".join(f"{k}{v}" for k, v in sorted(data.items()))
            expected = hmac.new(
                TWILIO_AUTH_TOKEN.encode(),
                (url + params_str).encode(),
                hashlib.sha1,
            ).digest()
            import base64
            expected_b64 = base64.b64encode(expected).decode()
            if not hmac.compare_digest(sig, expected_b64):
                logger.warning("Twilio webhook signature mismatch")
                raise HTTPException(status_code=403, detail="Invalid Twilio signature")

        message_sid = data.get("MessageSid") or data.get("SmsSid")
        message_status = data.get("MessageStatus")
        from_number = data.get("From")
        to_number = data.get("To")
        body_text = data.get("Body", "")

        # Status update for outbound message
        if message_sid and message_status:
            m = (await db.execute(
                select(SmsMessage).where(SmsMessage.provider_sid == message_sid)
            )).scalar_one_or_none()
            if m:
                m.status = message_status
                if message_status == "delivered" and not m.delivered_at:
                    m.delivered_at = datetime.now(timezone.utc)
                await db.commit()

        # Inbound message
        elif from_number and to_number and body_text:
            inbound = SmsMessage(
                # org_id cannot be resolved without mapping from_number to org;
                # a real implementation would look up by to_number → org.
                # For now, store with a placeholder lookup — implement org resolution later.
                org_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
                to_number=to_number,
                from_number=from_number,
                body=body_text,
                channel="whatsapp" if "whatsapp" in (from_number or "").lower() else "sms",
                direction="in",
                status="read",
                provider_sid=message_sid,
            )
            db.add(inbound)
            await db.commit()

        # Return empty TwiML response
        from fastapi.responses import Response
        return Response(content="<?xml version='1.0'?><Response/>", media_type="application/xml")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("twilio_webhook failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
