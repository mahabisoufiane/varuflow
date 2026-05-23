"""Work Management router — tasks, announcements, meeting notes, work orders, tickets."""
import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.work_management import WmTask, WmAnnouncement, MeetingNote, OpsWorkOrder, Ticket

logger = logging.getLogger(__name__)
router = APIRouter(tags=["work-management"])

# ─── Tasks ───────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    assignee_id: str | None = None
    project_id: str | None = None
    status: str = "todo"
    priority: str = "medium"
    due_date: date | None = None

class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    assignee_id: str | None = None
    project_id: str | None = None
    status: str | None = None
    priority: str | None = None
    due_date: date | None = None


@router.get("/api/work/tasks")
async def list_tasks(
    assignee_id: str | None = None,
    project_id: str | None = None,
    status: str | None = None,
    standalone_only: bool = False,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(WmTask).where(WmTask.org_id == org_id)
        if assignee_id:
            q = q.where(WmTask.assignee_id == assignee_id)
        if project_id:
            q = q.where(WmTask.project_id == project_id)
        if status:
            q = q.where(WmTask.status == status)
        if standalone_only:
            q = q.where(WmTask.project_id.is_(None))
        rows = (await db.execute(q.order_by(WmTask.created_at.desc()))).scalars().all()
        return [_task_dict(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_tasks failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/work/tasks", status_code=201)
async def create_task(body: TaskCreate, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rec = WmTask(org_id=org_id, title=body.title, description=body.description,
                   assignee_id=body.assignee_id, project_id=body.project_id,
                   status=body.status, priority=body.priority, due_date=body.due_date)
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
        return _task_dict(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_task failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/work/tasks/{task_id}")
async def update_task(task_id: str, body: TaskUpdate, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rec = (await db.execute(select(WmTask).where(WmTask.id == task_id, WmTask.org_id == org_id))).scalar_one_or_none()
        if not rec:
            raise HTTPException(status_code=404, detail="Task not found")
        data = body.model_dump(exclude_none=True)
        for k, v in data.items():
            setattr(rec, k, v)
        if data.get("status") == "done" and not rec.completed_at:
            rec.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(rec)
        return _task_dict(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_task failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/work/tasks/{task_id}", status_code=204)
async def delete_task(task_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rec = (await db.execute(select(WmTask).where(WmTask.id == task_id, WmTask.org_id == org_id))).scalar_one_or_none()
        if not rec:
            raise HTTPException(status_code=404, detail="Task not found")
        await db.delete(rec)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_task failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


def _task_dict(r: WmTask) -> dict:
    return {
        "id": str(r.id), "org_id": str(r.org_id),
        "project_id": str(r.project_id) if r.project_id else None,
        "title": r.title, "description": r.description,
        "assignee_id": str(r.assignee_id) if r.assignee_id else None,
        "status": r.status, "priority": r.priority,
        "due_date": r.due_date.isoformat() if r.due_date else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ─── Announcements ──────────────────────────────────────────────────────────

class AnnouncementCreate(BaseModel):
    title: str | None = None
    body: str
    pinned: bool = False

class AnnouncementUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    pinned: bool | None = None


@router.get("/api/work/announcements")
async def list_announcements(member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rows = (await db.execute(
            select(WmAnnouncement).where(WmAnnouncement.org_id == org_id)
            .order_by(WmAnnouncement.pinned.desc(), WmAnnouncement.created_at.desc())
        )).scalars().all()
        return [_ann_dict(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_announcements failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/work/announcements", status_code=201)
async def create_announcement(body: AnnouncementCreate, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rec = WmAnnouncement(org_id=org_id, author_id=member.get("staff_id"), title=body.title, body=body.body, pinned=body.pinned)
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
        return _ann_dict(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_announcement failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/work/announcements/{ann_id}")
async def update_announcement(ann_id: str, body: AnnouncementUpdate, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rec = (await db.execute(select(WmAnnouncement).where(WmAnnouncement.id == ann_id, WmAnnouncement.org_id == org_id))).scalar_one_or_none()
        if not rec:
            raise HTTPException(status_code=404, detail="Announcement not found")
        data = body.model_dump(exclude_none=True)
        for k, v in data.items():
            setattr(rec, k, v)
        await db.commit()
        await db.refresh(rec)
        return _ann_dict(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_announcement failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/work/announcements/{ann_id}", status_code=204)
async def delete_announcement(ann_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rec = (await db.execute(select(WmAnnouncement).where(WmAnnouncement.id == ann_id, WmAnnouncement.org_id == org_id))).scalar_one_or_none()
        if not rec:
            raise HTTPException(status_code=404, detail="Announcement not found")
        await db.delete(rec)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_announcement failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


def _ann_dict(r: WmAnnouncement) -> dict:
    return {
        "id": str(r.id), "author_id": str(r.author_id) if r.author_id else None,
        "title": r.title, "body": r.body, "pinned": r.pinned,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ─── Meeting Notes ───────────────────────────────────────────────────────────

class MeetingNoteCreate(BaseModel):
    title: str | None = None
    content: str | None = None
    customer_id: str | None = None
    deal_id: str | None = None
    meeting_date: datetime
    attendees: list = []
    action_items: list = []

class MeetingNoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    customer_id: str | None = None
    deal_id: str | None = None
    meeting_date: datetime | None = None
    attendees: list | None = None
    action_items: list | None = None


@router.get("/api/work/meeting-notes")
async def list_meeting_notes(
    customer_id: str | None = None,
    deal_id: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(MeetingNote).where(MeetingNote.org_id == org_id)
        if customer_id:
            q = q.where(MeetingNote.customer_id == customer_id)
        if deal_id:
            q = q.where(MeetingNote.deal_id == deal_id)
        rows = (await db.execute(q.order_by(MeetingNote.meeting_date.desc()))).scalars().all()
        return [_mn_dict(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_meeting_notes failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/work/meeting-notes", status_code=201)
async def create_meeting_note(body: MeetingNoteCreate, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rec = MeetingNote(
            org_id=org_id, author_id=member.get("staff_id"),
            title=body.title, content=body.content,
            customer_id=body.customer_id, deal_id=body.deal_id,
            meeting_date=body.meeting_date, attendees=body.attendees,
            action_items=body.action_items,
        )
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
        return _mn_dict(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_meeting_note failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/work/meeting-notes/{note_id}")
async def update_meeting_note(note_id: str, body: MeetingNoteUpdate, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rec = (await db.execute(select(MeetingNote).where(MeetingNote.id == note_id, MeetingNote.org_id == org_id))).scalar_one_or_none()
        if not rec:
            raise HTTPException(status_code=404, detail="Meeting note not found")
        data = body.model_dump(exclude_none=True)
        for k, v in data.items():
            setattr(rec, k, v)
        await db.commit()
        await db.refresh(rec)
        return _mn_dict(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_meeting_note failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/work/meeting-notes/{note_id}", status_code=204)
async def delete_meeting_note(note_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rec = (await db.execute(select(MeetingNote).where(MeetingNote.id == note_id, MeetingNote.org_id == org_id))).scalar_one_or_none()
        if not rec:
            raise HTTPException(status_code=404, detail="Meeting note not found")
        await db.delete(rec)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_meeting_note failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


def _mn_dict(r: MeetingNote) -> dict:
    return {
        "id": str(r.id), "customer_id": str(r.customer_id) if r.customer_id else None,
        "deal_id": str(r.deal_id) if r.deal_id else None,
        "author_id": str(r.author_id) if r.author_id else None,
        "title": r.title, "content": r.content,
        "meeting_date": r.meeting_date.isoformat() if r.meeting_date else None,
        "attendees": r.attendees or [], "action_items": r.action_items or [],
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ─── Work Orders ─────────────────────────────────────────────────────────────

_WO_STATUSES = {"open", "in_progress", "completed", "cancelled"}

class WorkOrderCreate(BaseModel):
    title: str
    description: str | None = None
    customer_id: str | None = None
    assigned_staff_id: str | None = None
    priority: str = "medium"
    status: str = "open"
    scheduled_date: datetime | None = None
    location: str | None = None
    parts_used: list = []

class WorkOrderUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    customer_id: str | None = None
    assigned_staff_id: str | None = None
    priority: str | None = None
    status: str | None = None
    scheduled_date: datetime | None = None
    location: str | None = None
    parts_used: list | None = None


@router.get("/api/work/work-orders")
async def list_work_orders(
    status: str | None = None,
    assigned_staff_id: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(OpsWorkOrder).where(OpsWorkOrder.org_id == org_id)
        if status:
            q = q.where(OpsWorkOrder.status == status)
        if assigned_staff_id:
            q = q.where(OpsWorkOrder.assigned_staff_id == assigned_staff_id)
        rows = (await db.execute(q.order_by(OpsWorkOrder.created_at.desc()))).scalars().all()
        return [_wo_dict(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_work_orders failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/work/work-orders", status_code=201)
async def create_work_order(body: WorkOrderCreate, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rec = OpsWorkOrder(
            org_id=org_id, title=body.title, description=body.description,
            customer_id=body.customer_id, assigned_staff_id=body.assigned_staff_id,
            priority=body.priority, status=body.status,
            scheduled_date=body.scheduled_date, location=body.location,
            parts_used=body.parts_used,
        )
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
        return _wo_dict(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_work_order failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/work/work-orders/{wo_id}")
async def update_work_order(wo_id: str, body: WorkOrderUpdate, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rec = (await db.execute(select(OpsWorkOrder).where(OpsWorkOrder.id == wo_id, OpsWorkOrder.org_id == org_id))).scalar_one_or_none()
        if not rec:
            raise HTTPException(status_code=404, detail="Work order not found")
        data = body.model_dump(exclude_none=True)
        if "status" in data and data["status"] not in _WO_STATUSES:
            raise HTTPException(status_code=422, detail=f"status must be one of {_WO_STATUSES}")
        for k, v in data.items():
            setattr(rec, k, v)
        if data.get("status") == "completed" and not rec.completed_at:
            rec.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(rec)
        return _wo_dict(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_work_order failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/work/work-orders/{wo_id}", status_code=204)
async def delete_work_order(wo_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rec = (await db.execute(select(OpsWorkOrder).where(OpsWorkOrder.id == wo_id, OpsWorkOrder.org_id == org_id))).scalar_one_or_none()
        if not rec:
            raise HTTPException(status_code=404, detail="Work order not found")
        await db.delete(rec)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_work_order failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


def _wo_dict(r: OpsWorkOrder) -> dict:
    return {
        "id": str(r.id), "customer_id": str(r.customer_id) if r.customer_id else None,
        "assigned_staff_id": str(r.assigned_staff_id) if r.assigned_staff_id else None,
        "title": r.title, "description": r.description,
        "priority": r.priority, "status": r.status,
        "scheduled_date": r.scheduled_date.isoformat() if r.scheduled_date else None,
        "location": r.location, "parts_used": r.parts_used or [],
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ─── Tickets ─────────────────────────────────────────────────────────────────

_TICKET_STATUSES = {"open", "in_progress", "waiting", "resolved", "closed"}

class TicketCreate(BaseModel):
    title: str
    description: str | None = None
    customer_id: str | None = None
    assigned_staff_id: str | None = None
    category: str | None = None
    priority: str = "medium"
    status: str = "open"
    due_date: date | None = None

class TicketUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    customer_id: str | None = None
    assigned_staff_id: str | None = None
    category: str | None = None
    priority: str | None = None
    status: str | None = None
    due_date: date | None = None
    resolution_notes: str | None = None


@router.get("/api/work/tickets")
async def list_tickets(
    status: str | None = None,
    priority: str | None = None,
    assigned_staff_id: str | None = None,
    category: str | None = None,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(Ticket).where(Ticket.org_id == org_id)
        if status:
            q = q.where(Ticket.status == status)
        if priority:
            q = q.where(Ticket.priority == priority)
        if assigned_staff_id:
            q = q.where(Ticket.assigned_staff_id == assigned_staff_id)
        if category:
            q = q.where(Ticket.category == category)
        rows = (await db.execute(q.order_by(Ticket.created_at.desc()))).scalars().all()
        return [_ticket_dict(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_tickets failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/work/tickets", status_code=201)
async def create_ticket(body: TicketCreate, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rec = Ticket(
            org_id=org_id, title=body.title, description=body.description,
            customer_id=body.customer_id, assigned_staff_id=body.assigned_staff_id,
            category=body.category, priority=body.priority, status=body.status,
            due_date=body.due_date,
        )
        db.add(rec)
        await db.commit()
        await db.refresh(rec)
        return _ticket_dict(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_ticket failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/work/tickets/{ticket_id}")
async def update_ticket(ticket_id: str, body: TicketUpdate, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rec = (await db.execute(select(Ticket).where(Ticket.id == ticket_id, Ticket.org_id == org_id))).scalar_one_or_none()
        if not rec:
            raise HTTPException(status_code=404, detail="Ticket not found")
        data = body.model_dump(exclude_none=True)
        if "status" in data and data["status"] not in _TICKET_STATUSES:
            raise HTTPException(status_code=422, detail=f"status must be one of {_TICKET_STATUSES}")
        for k, v in data.items():
            setattr(rec, k, v)
        await db.commit()
        await db.refresh(rec)
        return _ticket_dict(rec)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_ticket failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/work/tickets/{ticket_id}", status_code=204)
async def delete_ticket(ticket_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        rec = (await db.execute(select(Ticket).where(Ticket.id == ticket_id, Ticket.org_id == org_id))).scalar_one_or_none()
        if not rec:
            raise HTTPException(status_code=404, detail="Ticket not found")
        await db.delete(rec)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_ticket failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


def _ticket_dict(r: Ticket) -> dict:
    return {
        "id": str(r.id), "customer_id": str(r.customer_id) if r.customer_id else None,
        "assigned_staff_id": str(r.assigned_staff_id) if r.assigned_staff_id else None,
        "title": r.title, "description": r.description,
        "category": r.category, "priority": r.priority, "status": r.status,
        "due_date": r.due_date.isoformat() if r.due_date else None,
        "resolution_notes": r.resolution_notes,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
