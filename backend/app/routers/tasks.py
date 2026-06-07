"""Tasks router — assign, track, and manage work items.

GET  /api/work/tasks               — list tasks (filter: status, assignee_id, overdue)
POST /api/work/tasks               — create task
GET  /api/work/tasks/my            — tasks assigned to current user
GET  /api/work/tasks/{id}          — task detail + subtasks + comments
PATCH /api/work/tasks/{id}         — update task (status, priority, due_date, etc.)
DELETE /api/work/tasks/{id}        — delete task
POST /api/work/tasks/{id}/complete — mark done
POST /api/work/tasks/{id}/comments — add comment
GET  /api/work/tasks/metrics       — completion metrics per staff member
"""
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.tasks import Task, TaskComment
from app.middleware.plan_check import require_module

logger = logging.getLogger(__name__)
router = APIRouter(tags=["tasks"], dependencies=[Depends(require_module("hr"))])


# ── Schemas ───────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    assignee_id: str | None = None
    priority: str = "medium"
    due_date: str | None = None
    status: str = "todo"
    parent_task_id: str | None = None
    ref_type: str | None = None
    ref_id: str | None = None
    is_recurring: bool = False
    recurrence_rule: str | None = None


class TaskPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    assignee_id: str | None = None
    priority: str | None = None
    due_date: str | None = None
    status: str | None = None
    ref_type: str | None = None
    ref_id: str | None = None


class CommentCreate(BaseModel):
    body: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _task_dict(t: Task, include_comments: bool = False, include_subtasks: bool = False) -> dict:
    today = date.today()
    is_overdue = bool(t.due_date and t.due_date < today and t.status not in ("done",))
    d: dict = {
        "id": str(t.id),
        "title": t.title,
        "description": t.description,
        "assignee_id": str(t.assignee_id) if t.assignee_id else None,
        "created_by": str(t.created_by) if t.created_by else None,
        "status": t.status,
        "priority": t.priority,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "parent_task_id": str(t.parent_task_id) if t.parent_task_id else None,
        "ref_type": t.ref_type,
        "ref_id": str(t.ref_id) if t.ref_id else None,
        "is_recurring": t.is_recurring,
        "recurrence_rule": t.recurrence_rule,
        "is_overdue": is_overdue,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }
    if include_comments:
        d["comments"] = [{"id": str(c.id), "staff_id": str(c.staff_id) if c.staff_id else None, "body": c.body, "created_at": c.created_at.isoformat()} for c in (t.comments or [])]
    if include_subtasks:
        d["subtasks"] = [_task_dict(s) for s in (t.subtasks or [])]
    return d


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/api/work/tasks/metrics")
async def task_metrics(member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    """Completion metrics per assignee (manager view)."""
    try:
        org_id = member["org_id"]
        rows = (await db.execute(
            select(Task).where(Task.org_id == org_id, Task.parent_task_id.is_(None))
        )).scalars().all()
        counts: dict[str, dict] = {}
        for t in rows:
            aid = str(t.assignee_id) if t.assignee_id else "__unassigned__"
            if aid not in counts:
                counts[aid] = {"total": 0, "done": 0, "overdue": 0, "in_progress": 0}
            counts[aid]["total"] += 1
            if t.status == "done":
                counts[aid]["done"] += 1
            elif t.status == "in_progress":
                counts[aid]["in_progress"] += 1
            if t.due_date and t.due_date < date.today() and t.status != "done":
                counts[aid]["overdue"] += 1
        return [{"assignee_id": k, **v, "completion_rate": round(v["done"] / v["total"] * 100) if v["total"] else 0} for k, v in counts.items()]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"task_metrics failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/work/tasks/my")
async def my_tasks(member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    """Tasks assigned to the current staff member, sorted by due date."""
    try:
        org_id = member["org_id"]
        staff_id = member.get("staff_id")
        if not staff_id:
            return []
        q = select(Task).where(
            and_(Task.org_id == org_id, Task.assignee_id == uuid.UUID(str(staff_id)), Task.status != "done")
        ).order_by(Task.due_date.asc().nullslast(), Task.priority.desc())
        rows = (await db.execute(q)).scalars().all()
        return [_task_dict(t) for t in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"my_tasks failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/work/tasks")
async def list_tasks(
    status: str | None = None,
    assignee_id: str | None = None,
    overdue: bool = False,
    standalone_only: bool = False,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        q = select(Task).where(Task.org_id == org_id, Task.parent_task_id.is_(None))
        if status:
            q = q.where(Task.status == status)
        if assignee_id:
            q = q.where(Task.assignee_id == uuid.UUID(assignee_id))
        if overdue:
            q = q.where(Task.due_date < date.today(), Task.status != "done")
        rows = (await db.execute(q.order_by(Task.due_date.asc().nullslast(), Task.created_at.desc()))).scalars().all()
        return [_task_dict(t) for t in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"list_tasks failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/work/tasks", status_code=201)
async def create_task(body: TaskCreate, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        t = Task(
            org_id=org_id,
            title=body.title,
            description=body.description,
            assignee_id=uuid.UUID(body.assignee_id) if body.assignee_id else None,
            created_by=member.get("staff_id"),
            priority=body.priority,
            status=body.status,
            due_date=date.fromisoformat(body.due_date) if body.due_date else None,
            parent_task_id=uuid.UUID(body.parent_task_id) if body.parent_task_id else None,
            ref_type=body.ref_type,
            ref_id=uuid.UUID(body.ref_id) if body.ref_id else None,
            is_recurring=body.is_recurring,
            recurrence_rule=body.recurrence_rule,
        )
        db.add(t)
        await db.commit()
        return _task_dict(t)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_task failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/work/tasks/{task_id}")
async def get_task(task_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        t = (await db.execute(select(Task).where(Task.id == uuid.UUID(task_id), Task.org_id == org_id))).scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=404, detail="Not found")
        await db.refresh(t, ["comments", "subtasks"])
        return _task_dict(t, include_comments=True, include_subtasks=True)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_task failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/work/tasks/{task_id}")
async def update_task(task_id: str, body: TaskPatch, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        t = (await db.execute(select(Task).where(Task.id == uuid.UUID(task_id), Task.org_id == org_id))).scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=404, detail="Not found")
        now = datetime.now(timezone.utc)
        for field, val in body.model_dump(exclude_unset=True).items():
            if field == "due_date":
                setattr(t, field, date.fromisoformat(val) if val else None)
            elif field in ("assignee_id", "ref_id"):
                setattr(t, field, uuid.UUID(val) if val else None)
            else:
                setattr(t, field, val)
        if body.status == "done" and not t.completed_at:
            t.completed_at = now
        elif body.status and body.status != "done":
            t.completed_at = None
        t.updated_at = now
        await db.commit()
        return _task_dict(t)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_task failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/work/tasks/{task_id}", status_code=204)
async def delete_task(task_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        t = (await db.execute(select(Task).where(Task.id == uuid.UUID(task_id), Task.org_id == org_id))).scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=404, detail="Not found")
        await db.delete(t)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_task failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/work/tasks/{task_id}/complete")
async def complete_task(task_id: str, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        t = (await db.execute(select(Task).where(Task.id == uuid.UUID(task_id), Task.org_id == org_id))).scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=404, detail="Not found")
        t.status = "done"
        t.completed_at = datetime.now(timezone.utc)
        t.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return _task_dict(t)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"complete_task failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/work/tasks/{task_id}/comments", status_code=201)
async def add_comment(task_id: str, body: CommentCreate, member=Depends(get_current_member), db: AsyncSession = Depends(get_db)):
    try:
        org_id = member["org_id"]
        t = (await db.execute(select(Task).where(Task.id == uuid.UUID(task_id), Task.org_id == org_id))).scalar_one_or_none()
        if not t:
            raise HTTPException(status_code=404, detail="Not found")
        c = TaskComment(task_id=t.id, staff_id=member.get("staff_id"), body=body.body)
        db.add(c)
        await db.commit()
        await db.refresh(c)
        return {"id": str(c.id), "staff_id": str(c.staff_id) if c.staff_id else None, "body": c.body, "created_at": c.created_at.isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"add_comment failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
