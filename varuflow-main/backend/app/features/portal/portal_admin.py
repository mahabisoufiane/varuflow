"""Portal Admin router — staff-side management of chat, tickets, reminders, timeline."""
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from .models import (
    PortalChatMessage, OrderTimelineEvent, InvoiceViewEvent,
    PortalTicket, PortalTicketReply, FriendlyReminder,
)

logger = logging.getLogger(__name__)
router = APIRouter(
    tags=["portal-admin"],
    dependencies=[Depends(require_module("invoicing"))],
)


# ── Chat ───────────────────────────────────────────────────────────────────────

@router.get("/api/portal-admin/chat/unread")
async def chat_unread(member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        # Customers with unread messages (sent by customer, read_at is null)
        from sqlalchemy import distinct
        rows = (await db.execute(
            select(
                PortalChatMessage.customer_id,
                func.count(PortalChatMessage.id).label("unread_count"),
                func.max(PortalChatMessage.created_at).label("last_msg"),
            )
            .where(PortalChatMessage.org_id == org_id, PortalChatMessage.sender_type == "customer", PortalChatMessage.read_at == None)
            .group_by(PortalChatMessage.customer_id)
            .order_by(func.max(PortalChatMessage.created_at).desc())
        )).all()
        return [{"customer_id": str(r.customer_id), "unread_count": r.unread_count, "last_message_at": r.last_msg.isoformat() if r.last_msg else None} for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"chat_unread failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/portal-admin/chat/{customer_id}")
async def chat_with_customer(customer_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        cid = uuid.UUID(customer_id)
        rows = (await db.execute(
            select(PortalChatMessage)
            .where(PortalChatMessage.org_id == org_id, PortalChatMessage.customer_id == cid)
            .order_by(PortalChatMessage.created_at.asc())
            .limit(200)
        )).scalars().all()
        # Mark customer messages as read
        for m in rows:
            if m.sender_type == "customer" and m.read_at is None:
                m.read_at = datetime.now(timezone.utc)
        await db.commit()
        return [{"id": str(m.id), "sender_type": m.sender_type, "body": m.body, "created_at": m.created_at.isoformat()} for m in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"chat_with_customer failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


class StaffChatIn(BaseModel):
    body: str


@router.post("/api/portal-admin/chat/{customer_id}", status_code=201)
async def chat_send_as_staff(customer_id: str, body: StaffChatIn, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        msg = PortalChatMessage(
            org_id=org_id, customer_id=uuid.UUID(customer_id),
            sender_type="staff", sender_staff_id=member.get("staff_id"),
            body=body.body,
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return {"id": str(msg.id), "sender_type": "staff", "body": msg.body, "created_at": msg.created_at.isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"chat_send_as_staff failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Tickets ────────────────────────────────────────────────────────────────────

@router.get("/api/portal-admin/tickets")
async def admin_tickets_list(
    status: str | None = None,
    assigned_staff_id: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(PortalTicket).where(PortalTicket.org_id == org_id)
        if status:
            q = q.where(PortalTicket.status == status)
        if assigned_staff_id:
            q = q.where(PortalTicket.assigned_staff_id == uuid.UUID(assigned_staff_id))
        rows = (await db.execute(q.order_by(PortalTicket.created_at.desc()))).scalars().all()
        now = datetime.now(timezone.utc)
        result = []
        for t in rows:
            sla_overdue = bool(
                t.sla_hours and t.status not in ("resolved", "closed") and t.created_at and
                (now - t.created_at).total_seconds() / 3600 > t.sla_hours
            )
            result.append({
                "id": str(t.id),
                "customer_id": str(t.customer_id),
                "subject": t.subject,
                "description": t.description,
                "status": t.status,
                "priority": t.priority,
                "ticket_type": t.ticket_type,
                "sla_hours": t.sla_hours,
                "sla_overdue": sla_overdue,
                "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
                "csat_token": t.csat_token,
                "assigned_staff_id": str(t.assigned_staff_id) if t.assigned_staff_id else None,
                "created_at": t.created_at.isoformat(),
            })
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"admin_tickets_list failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


class TicketPatch(BaseModel):
    status: str | None = None
    priority: str | None = None
    assigned_staff_id: str | None = None


@router.patch("/api/portal-admin/tickets/{ticket_id}")
async def admin_ticket_update(ticket_id: str, body: TicketPatch, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        ticket = (await db.execute(select(PortalTicket).where(PortalTicket.id == uuid.UUID(ticket_id), PortalTicket.org_id == org_id))).scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        if body.status:
            ticket.status = body.status
            if body.status in ("resolved", "closed") and not ticket.resolved_at:
                import secrets as _secrets
                ticket.resolved_at = datetime.now(timezone.utc)
                if not ticket.csat_token:
                    ticket.csat_token = _secrets.token_urlsafe(32)[:64]
        if body.priority:
            ticket.priority = body.priority
        if body.assigned_staff_id:
            ticket.assigned_staff_id = uuid.UUID(body.assigned_staff_id)
        ticket.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return {"id": str(ticket.id), "status": ticket.status, "priority": ticket.priority, "assigned_staff_id": str(ticket.assigned_staff_id) if ticket.assigned_staff_id else None, "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None, "csat_token": ticket.csat_token}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"admin_ticket_update failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


class StaffReplyIn(BaseModel):
    body: str
    is_internal: bool = False


@router.post("/api/portal-admin/tickets/{ticket_id}/reply", status_code=201)
async def admin_ticket_reply(ticket_id: str, body: StaffReplyIn, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        ticket = (await db.execute(select(PortalTicket).where(PortalTicket.id == uuid.UUID(ticket_id), PortalTicket.org_id == org_id))).scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        reply = PortalTicketReply(ticket_id=ticket.id, sender_type="staff", sender_staff_id=member.get("staff_id"), body=body.body, is_internal=body.is_internal)
        db.add(reply)
        await db.commit()
        await db.refresh(reply)
        return {"id": str(reply.id), "sender_type": "staff", "body": reply.body, "is_internal": reply.is_internal, "created_at": reply.created_at.isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"admin_ticket_reply failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Ticket detail ──────────────────────────────────────────────────────────────

@router.get("/api/portal-admin/tickets/{ticket_id}")
async def admin_ticket_detail(ticket_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        ticket = (await db.execute(select(PortalTicket).where(PortalTicket.id == uuid.UUID(ticket_id), PortalTicket.org_id == org_id))).scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        await db.refresh(ticket, ["replies"])
        from datetime import datetime as _dt, timezone as _tz
        now = _dt.now(_tz.utc)
        sla_overdue = False
        if ticket.sla_hours and ticket.status not in ("resolved", "closed") and ticket.created_at:
            sla_overdue = (now - ticket.created_at).total_seconds() / 3600 > ticket.sla_hours
        return {
            "id": str(ticket.id), "customer_id": str(ticket.customer_id),
            "subject": ticket.subject, "description": ticket.description,
            "status": ticket.status, "priority": ticket.priority,
            "ticket_type": ticket.ticket_type, "sla_hours": ticket.sla_hours,
            "sla_overdue": sla_overdue,
            "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
            "csat_token": ticket.csat_token,
            "assigned_staff_id": str(ticket.assigned_staff_id) if ticket.assigned_staff_id else None,
            "created_at": ticket.created_at.isoformat(),
            "replies": [{"id": str(r.id), "sender_type": r.sender_type, "body": r.body, "is_internal": r.is_internal, "created_at": r.created_at.isoformat()} for r in ticket.replies],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"admin_ticket_detail failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Invoice views ──────────────────────────────────────────────────────────────

@router.get("/api/portal-admin/invoice-views/{invoice_id}")
async def admin_invoice_views(invoice_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rows = (await db.execute(
            select(InvoiceViewEvent)
            .where(InvoiceViewEvent.org_id == org_id, InvoiceViewEvent.invoice_id == uuid.UUID(invoice_id))
            .order_by(InvoiceViewEvent.viewed_at.desc())
        )).scalars().all()
        return [{"id": str(v.id), "customer_id": str(v.customer_id), "viewed_at": v.viewed_at.isoformat(), "ip_address": v.ip_address} for v in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"admin_invoice_views failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Friendly reminders ─────────────────────────────────────────────────────────

class ReminderIn(BaseModel):
    invoice_id: str
    customer_id: str
    reminder_type: str = "gentle"
    scheduled_for: str
    email_subject: str
    email_body: str


@router.get("/api/portal-admin/reminders")
async def admin_reminders_list(member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rows = (await db.execute(
            select(FriendlyReminder).where(FriendlyReminder.org_id == org_id).order_by(FriendlyReminder.scheduled_for.desc()).limit(100)
        )).scalars().all()
        return [{"id": str(r.id), "invoice_id": str(r.invoice_id), "customer_id": str(r.customer_id), "reminder_type": r.reminder_type, "scheduled_for": r.scheduled_for.isoformat(), "sent_at": r.sent_at.isoformat() if r.sent_at else None, "email_subject": r.email_subject} for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"admin_reminders_list failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/portal-admin/reminders", status_code=201)
async def admin_reminder_create(body: ReminderIn, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        reminder = FriendlyReminder(
            org_id=org_id, invoice_id=uuid.UUID(body.invoice_id),
            customer_id=uuid.UUID(body.customer_id),
            reminder_type=body.reminder_type,
            scheduled_for=datetime.fromisoformat(body.scheduled_for),
            email_subject=body.email_subject, email_body=body.email_body,
        )
        db.add(reminder)
        await db.commit()
        await db.refresh(reminder)
        return {"id": str(reminder.id), "scheduled_for": reminder.scheduled_for.isoformat(), "reminder_type": reminder.reminder_type}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"admin_reminder_create failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Timeline (staff adds events) ──────────────────────────────────────────────

class TimelineEventIn(BaseModel):
    invoice_id: str | None = None
    event_type: str
    title: str
    description: str | None = None
    occurred_at: str


@router.post("/api/portal-admin/timeline/{customer_id}", status_code=201)
async def admin_timeline_add(customer_id: str, body: TimelineEventIn, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        evt = OrderTimelineEvent(
            org_id=org_id, customer_id=uuid.UUID(customer_id),
            invoice_id=uuid.UUID(body.invoice_id) if body.invoice_id else None,
            event_type=body.event_type, title=body.title,
            description=body.description,
            occurred_at=datetime.fromisoformat(body.occurred_at),
        )
        db.add(evt)
        await db.commit()
        await db.refresh(evt)
        return {"id": str(evt.id), "event_type": evt.event_type, "title": evt.title, "occurred_at": evt.occurred_at.isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"admin_timeline_add failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
