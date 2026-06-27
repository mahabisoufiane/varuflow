"""Employee Onboarding Checklist router.

Each new hire gets their own copy of checklist items, optionally pre-populated
from a company template. The manager ticks off items as the employee works
through their first days/weeks.

Endpoints:
  GET  /api/hr/onboarding/template          — company default template items
  POST /api/hr/onboarding/template          — add a template item
  DELETE /api/hr/onboarding/template/{id}   — remove template item
  GET  /api/hr/onboarding/{staff_id}        — employee's tasks (created from template + custom)
  POST /api/hr/onboarding/{staff_id}/from-template — bulk-create tasks from current template
  POST /api/hr/onboarding/{staff_id}        — add a single custom task
  PATCH /api/hr/onboarding/{staff_id}/{task_id}     — update task (is_done, title, etc.)
  DELETE /api/hr/onboarding/{staff_id}/{task_id}    — remove task
  GET  /api/hr/onboarding/summary           — completion pct per staff member (manager view)
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module
from .hr_onboarding_training import EmployeeOnboardingTask

logger = logging.getLogger(__name__)
router = APIRouter(tags=["hr-onboarding"], dependencies=[Depends(require_module("hr"))])

_CATEGORIES = {"it_setup", "access", "hr_admin", "equipment", "intro", "compliance", "general"}

# Built-in company template that is used when no custom template exists
_BUILT_IN_TEMPLATE = [
    {"title": "Workstation / laptop set up",            "category": "it_setup",    "due_days_after_start": 1},
    {"title": "System accounts created (email, apps)",  "category": "access",      "due_days_after_start": 1},
    {"title": "Physical office/keys access arranged",   "category": "equipment",   "due_days_after_start": 1},
    {"title": "Contract signed and filed in HR",        "category": "hr_admin",    "due_days_after_start": 3},
    {"title": "Payroll set up — bank details collected","category": "hr_admin",    "due_days_after_start": 3},
    {"title": "Welcome meeting with line manager",      "category": "intro",       "due_days_after_start": 1},
    {"title": "Team introduction / meet the colleagues","category": "intro",       "due_days_after_start": 2},
    {"title": "Company handbook acknowledged",          "category": "compliance",  "due_days_after_start": 5},
    {"title": "GDPR / data handling briefing",          "category": "compliance",  "due_days_after_start": 5},
    {"title": "Health & safety induction",              "category": "compliance",  "due_days_after_start": 7},
    {"title": "30-day check-in scheduled with manager", "category": "intro",       "due_days_after_start": 30},
    {"title": "Benefits and pension enrolment",         "category": "hr_admin",    "due_days_after_start": 14},
]


class TaskCreate(BaseModel):
    title: str
    category: str = "general"
    description: str | None = None
    due_days_after_start: int | None = None
    sort_order: int = 0

class TaskUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    description: str | None = None
    is_done: bool | None = None
    due_days_after_start: int | None = None
    sort_order: int | None = None


# ── Template (org-level default list) ────────────────────────────────────────

@router.get("/api/hr/onboarding/template")
async def get_template(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Return org's custom template, or the built-in template if none configured."""
    try:
        org_id = member["org_id"]
        # Org-level template tasks have staff_id = org_id (sentinel value)
        rows = (await db.execute(
            select(EmployeeOnboardingTask).where(
                EmployeeOnboardingTask.org_id == org_id,
                EmployeeOnboardingTask.staff_id == org_id,  # sentinel: template rows use org_id as staff_id
            ).order_by(EmployeeOnboardingTask.sort_order, EmployeeOnboardingTask.created_at)
        )).scalars().all()

        if rows:
            return [_task_dict(t) for t in rows]
        # Fall back to built-in template
        return [{"id": None, "title": t["title"], "category": t["category"],
                  "due_days_after_start": t["due_days_after_start"], "is_template": True}
                for t in _BUILT_IN_TEMPLATE]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_template failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/onboarding/template", status_code=201)
async def add_template_item(
    body: TaskCreate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Add an item to the org's custom template (uses org_id as staff_id sentinel)."""
    try:
        org_id = member["org_id"]
        task = EmployeeOnboardingTask(
            org_id=org_id,
            staff_id=org_id,  # sentinel
            title=body.title,
            category=body.category if body.category in _CATEGORIES else "general",
            description=body.description,
            due_days_after_start=body.due_days_after_start,
            sort_order=body.sort_order,
            is_from_template=True,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return _task_dict(task)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"add_template_item failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/hr/onboarding/template/{task_id}", status_code=204)
async def delete_template_item(
    task_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        task = (await db.execute(
            select(EmployeeOnboardingTask).where(
                EmployeeOnboardingTask.id == task_id,
                EmployeeOnboardingTask.org_id == org_id,
                EmployeeOnboardingTask.staff_id == org_id,
            )
        )).scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Template item not found")
        await db.delete(task)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_template_item failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Per-employee tasks ────────────────────────────────────────────────────────

@router.get("/api/hr/onboarding/summary")
async def onboarding_summary(
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Completion percentage per staff member — manager dashboard view."""
    try:
        org_id = member["org_id"]
        result = await db.execute(text("""
            SELECT
                t.staff_id,
                s.name AS staff_name,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE t.is_done) AS done
            FROM employee_onboarding_tasks t
            JOIN staff s ON s.id = t.staff_id
            WHERE t.org_id = :org_id
              AND t.staff_id != :org_id
            GROUP BY t.staff_id, s.name
            ORDER BY s.name
        """), {"org_id": org_id})
        return [
            {
                "staff_id": str(r.staff_id), "staff_name": r.staff_name,
                "total": r.total, "done": r.done,
                "completion_pct": round(r.done / r.total * 100, 1) if r.total > 0 else 0,
            }
            for r in result.fetchall()
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"onboarding_summary failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/hr/onboarding/{staff_id}")
async def get_employee_tasks(
    staff_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        rows = (await db.execute(
            select(EmployeeOnboardingTask).where(
                EmployeeOnboardingTask.org_id == org_id,
                EmployeeOnboardingTask.staff_id == staff_id,
            ).order_by(EmployeeOnboardingTask.sort_order, EmployeeOnboardingTask.created_at)
        )).scalars().all()
        return [_task_dict(t) for t in rows]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_employee_tasks failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/onboarding/{staff_id}/from-template", status_code=201)
async def create_from_template(
    staff_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Bulk-create all template tasks for a new hire. Idempotent — skips duplicates."""
    try:
        org_id = member["org_id"]
        # Load template
        template_rows = (await db.execute(
            select(EmployeeOnboardingTask).where(
                EmployeeOnboardingTask.org_id == org_id,
                EmployeeOnboardingTask.staff_id == org_id,
            )
        )).scalars().all()
        template = [{"title": t.title, "category": t.category,
                      "due_days_after_start": t.due_days_after_start, "sort_order": t.sort_order}
                     for t in template_rows] or _BUILT_IN_TEMPLATE

        # Get existing task titles to avoid duplicates
        existing = (await db.execute(
            select(EmployeeOnboardingTask.title).where(
                EmployeeOnboardingTask.org_id == org_id,
                EmployeeOnboardingTask.staff_id == staff_id,
            )
        )).scalars().all()
        existing_titles = {t.lower() for t in existing}

        created = []
        for i, item in enumerate(template):
            if item["title"].lower() in existing_titles:
                continue
            task = EmployeeOnboardingTask(
                org_id=org_id, staff_id=uuid.UUID(staff_id),
                title=item["title"], category=item.get("category", "general"),
                due_days_after_start=item.get("due_days_after_start"),
                sort_order=item.get("sort_order", i),
                is_from_template=True,
            )
            db.add(task)
            created.append(task)
        await db.commit()
        return {"created": len(created), "skipped": len(template) - len(created)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_from_template failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/hr/onboarding/{staff_id}", status_code=201)
async def add_task(
    staff_id: str,
    body: TaskCreate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        task = EmployeeOnboardingTask(
            org_id=org_id, staff_id=uuid.UUID(staff_id),
            title=body.title,
            category=body.category if body.category in _CATEGORIES else "general",
            description=body.description,
            due_days_after_start=body.due_days_after_start,
            sort_order=body.sort_order,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return _task_dict(task)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"add_task failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/api/hr/onboarding/{staff_id}/{task_id}")
async def update_task(
    staff_id: str,
    task_id: str,
    body: TaskUpdate,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        task = (await db.execute(
            select(EmployeeOnboardingTask).where(
                EmployeeOnboardingTask.id == task_id,
                EmployeeOnboardingTask.org_id == org_id,
                EmployeeOnboardingTask.staff_id == staff_id,
            )
        )).scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        data = body.model_dump(exclude_none=True)
        for field, val in data.items():
            setattr(task, field, val)

        # Record when/who completed it
        if data.get("is_done") is True and not task.done_at:
            task.done_at = datetime.now(timezone.utc)
            task.done_by = member.get("user_id")
        elif data.get("is_done") is False:
            task.done_at = None
            task.done_by = None

        await db.commit()
        await db.refresh(task)
        return _task_dict(task)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_task failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/api/hr/onboarding/{staff_id}/{task_id}", status_code=204)
async def delete_task(
    staff_id: str,
    task_id: str,
    member=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    try:
        org_id = member["org_id"]
        task = (await db.execute(
            select(EmployeeOnboardingTask).where(
                EmployeeOnboardingTask.id == task_id,
                EmployeeOnboardingTask.org_id == org_id,
                EmployeeOnboardingTask.staff_id == staff_id,
            )
        )).scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await db.delete(task)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_task failed: {e}", extra={"org_id": member.get("org_id")})
        raise HTTPException(status_code=500, detail="Internal server error")


def _task_dict(t: EmployeeOnboardingTask) -> dict:
    return {
        "id": str(t.id), "staff_id": str(t.staff_id),
        "title": t.title, "category": t.category,
        "description": t.description, "is_done": t.is_done,
        "done_at": t.done_at.isoformat() if t.done_at else None,
        "due_days_after_start": t.due_days_after_start,
        "is_from_template": t.is_from_template, "sort_order": t.sort_order,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }
