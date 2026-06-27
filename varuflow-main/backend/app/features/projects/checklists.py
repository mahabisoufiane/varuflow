"""Checklists — templates, template items, runs and run items.

Endpoints
─────────
GET    /api/checklists/templates                        → list templates with item count
POST   /api/checklists/templates                        → create template
GET    /api/checklists/templates/{id}                   → detail with items
PATCH  /api/checklists/templates/{id}                   → update template
DELETE /api/checklists/templates/{id}                   → delete template
POST   /api/checklists/templates/{id}/items             → add item to template
PATCH  /api/checklists/items/{item_id}                  → update item
DELETE /api/checklists/items/{item_id}                  → delete item
POST   /api/checklists/templates/{id}/start             → start a run
GET    /api/checklists/runs                             → list runs for org
GET    /api/checklists/runs/{run_id}                    → run detail with items
POST   /api/checklists/runs/{run_id}/check/{item_id}    → toggle item checked
PATCH  /api/checklists/runs/{run_id}/items/{item_id}    → update run item notes
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from .checklist import (
    ChecklistTemplate,
    ChecklistTemplateItem,
    ChecklistRun,
    ChecklistRunItem,
)
from app.middleware.plan_check import require_module

router = APIRouter(prefix="/api/checklists", tags=["checklists"], dependencies=[Depends(require_module("hr"))])
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _org_id(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


def _user_id(ctx: tuple) -> uuid.UUID:
    user, _ = ctx
    return uuid.UUID(str(user["user_id"]))


def _template_out(tmpl: ChecklistTemplate, item_count: int = 0) -> dict[str, Any]:
    return {
        "id": str(tmpl.id),
        "org_id": str(tmpl.org_id),
        "title": tmpl.title,
        "category": tmpl.category,
        "description": tmpl.description,
        "frequency": tmpl.frequency,
        "created_by": str(tmpl.created_by) if tmpl.created_by else None,
        "item_count": item_count,
        "created_at": tmpl.created_at.isoformat(),
        "updated_at": tmpl.updated_at.isoformat(),
    }


def _item_out(item: ChecklistTemplateItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "template_id": str(item.template_id),
        "title": item.title,
        "description": item.description,
        "sort_order": item.sort_order,
        "created_at": item.created_at.isoformat(),
    }


def _run_item_out(ri: ChecklistRunItem) -> dict[str, Any]:
    return {
        "id": str(ri.id),
        "run_id": str(ri.run_id),
        "template_item_id": str(ri.template_item_id),
        "is_checked": ri.is_checked,
        "checked_by": str(ri.checked_by) if ri.checked_by else None,
        "checked_at": ri.checked_at.isoformat() if ri.checked_at else None,
        "notes": ri.notes,
    }


def _run_out(run: ChecklistRun, items: list[ChecklistRunItem] | None = None) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": str(run.id),
        "template_id": str(run.template_id),
        "org_id": str(run.org_id),
        "started_by": str(run.started_by),
        "status": run.status,
        "started_at": run.started_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }
    if items is not None:
        d["items"] = [_run_item_out(i) for i in items]
    return d


# ── Schemas ────────────────────────────────────────────────────────────────────

class TemplateIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    category: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    frequency: str = Field(default="manual")


class TemplatePatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    category: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    frequency: Optional[str] = None


class TemplateItemIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: Optional[str] = None
    sort_order: int = Field(default=0)


class TemplateItemPatch(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    description: Optional[str] = None
    sort_order: Optional[int] = None


class RunItemNotesPatch(BaseModel):
    notes: Optional[str] = None


# ── Template endpoints ─────────────────────────────────────────────────────────

@router.get("/templates")
async def list_templates(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        tmpls = (await db.execute(
            select(ChecklistTemplate)
            .where(ChecklistTemplate.org_id == org_id)
            .order_by(ChecklistTemplate.created_at)
        )).scalars().all()

        results = []
        for tmpl in tmpls:
            items = (await db.execute(
                select(ChecklistTemplateItem)
                .where(ChecklistTemplateItem.template_id == tmpl.id)
            )).scalars().all()
            results.append(_template_out(tmpl, item_count=len(items)))
        return results
    except Exception as e:
        log.error("list_templates failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/templates", status_code=201)
async def create_template(
    body: TemplateIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        tmpl = ChecklistTemplate(
            org_id=org_id,
            title=body.title,
            category=body.category,
            description=body.description,
            frequency=body.frequency,
            created_by=user_id,
        )
        db.add(tmpl)
        await db.commit()
        await db.refresh(tmpl)
        return _template_out(tmpl, item_count=0)
    except Exception as e:
        log.error("create_template failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/templates/{tmpl_id}")
async def get_template(
    tmpl_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        tmpl = await db.scalar(
            select(ChecklistTemplate).where(
                ChecklistTemplate.id == tmpl_id, ChecklistTemplate.org_id == org_id
            )
        )
        if not tmpl:
            raise HTTPException(status_code=404, detail="Checklist template not found")

        items = (await db.execute(
            select(ChecklistTemplateItem)
            .where(ChecklistTemplateItem.template_id == tmpl_id)
            .order_by(ChecklistTemplateItem.sort_order)
        )).scalars().all()

        d = _template_out(tmpl, item_count=len(items))
        d["items"] = [_item_out(i) for i in items]
        return d
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_template failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/templates/{tmpl_id}")
async def patch_template(
    tmpl_id: uuid.UUID,
    body: TemplatePatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        tmpl = await db.scalar(
            select(ChecklistTemplate).where(
                ChecklistTemplate.id == tmpl_id, ChecklistTemplate.org_id == org_id
            )
        )
        if not tmpl:
            raise HTTPException(status_code=404, detail="Checklist template not found")

        if body.title is not None:
            tmpl.title = body.title
        if body.category is not None:
            tmpl.category = body.category
        if body.description is not None:
            tmpl.description = body.description
        if body.frequency is not None:
            tmpl.frequency = body.frequency

        tmpl.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(tmpl)

        items = (await db.execute(
            select(ChecklistTemplateItem)
            .where(ChecklistTemplateItem.template_id == tmpl_id)
        )).scalars().all()
        return _template_out(tmpl, item_count=len(items))
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_template failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/templates/{tmpl_id}", status_code=204)
async def delete_template(
    tmpl_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        tmpl = await db.scalar(
            select(ChecklistTemplate).where(
                ChecklistTemplate.id == tmpl_id, ChecklistTemplate.org_id == org_id
            )
        )
        if not tmpl:
            raise HTTPException(status_code=404, detail="Checklist template not found")
        await db.delete(tmpl)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_template failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Template item endpoints ────────────────────────────────────────────────────

@router.post("/templates/{tmpl_id}/items", status_code=201)
async def add_template_item(
    tmpl_id: uuid.UUID,
    body: TemplateItemIn,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        tmpl = await db.scalar(
            select(ChecklistTemplate).where(
                ChecklistTemplate.id == tmpl_id, ChecklistTemplate.org_id == org_id
            )
        )
        if not tmpl:
            raise HTTPException(status_code=404, detail="Checklist template not found")

        item = ChecklistTemplateItem(
            template_id=tmpl_id,
            title=body.title,
            description=body.description,
            sort_order=body.sort_order,
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return _item_out(item)
    except HTTPException:
        raise
    except Exception as e:
        log.error("add_template_item failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/items/{item_id}")
async def patch_template_item(
    item_id: uuid.UUID,
    body: TemplateItemPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        item = await db.scalar(
            select(ChecklistTemplateItem).where(ChecklistTemplateItem.id == item_id)
        )
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        # Verify template belongs to org
        tmpl = await db.scalar(
            select(ChecklistTemplate).where(
                ChecklistTemplate.id == item.template_id, ChecklistTemplate.org_id == org_id
            )
        )
        if not tmpl:
            raise HTTPException(status_code=403, detail="Not authorised")

        if body.title is not None:
            item.title = body.title
        if body.description is not None:
            item.description = body.description
        if body.sort_order is not None:
            item.sort_order = body.sort_order

        await db.commit()
        await db.refresh(item)
        return _item_out(item)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_template_item failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/items/{item_id}", status_code=204)
async def delete_template_item(
    item_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    org_id = _org_id(ctx)
    try:
        item = await db.scalar(
            select(ChecklistTemplateItem).where(ChecklistTemplateItem.id == item_id)
        )
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        tmpl = await db.scalar(
            select(ChecklistTemplate).where(
                ChecklistTemplate.id == item.template_id, ChecklistTemplate.org_id == org_id
            )
        )
        if not tmpl:
            raise HTTPException(status_code=403, detail="Not authorised")

        await db.delete(item)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("delete_template_item failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Run endpoints ──────────────────────────────────────────────────────────────

@router.post("/templates/{tmpl_id}/start", status_code=201)
async def start_run(
    tmpl_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        tmpl = await db.scalar(
            select(ChecklistTemplate).where(
                ChecklistTemplate.id == tmpl_id, ChecklistTemplate.org_id == org_id
            )
        )
        if not tmpl:
            raise HTTPException(status_code=404, detail="Checklist template not found")

        template_items = (await db.execute(
            select(ChecklistTemplateItem)
            .where(ChecklistTemplateItem.template_id == tmpl_id)
            .order_by(ChecklistTemplateItem.sort_order)
        )).scalars().all()

        run = ChecklistRun(
            template_id=tmpl_id,
            org_id=org_id,
            started_by=user_id,
            status="in_progress",
        )
        db.add(run)
        await db.flush()

        run_items: list[ChecklistRunItem] = []
        for ti in template_items:
            ri = ChecklistRunItem(
                run_id=run.id,
                template_item_id=ti.id,
                is_checked=False,
            )
            db.add(ri)
            run_items.append(ri)

        await db.commit()
        await db.refresh(run)
        for ri in run_items:
            await db.refresh(ri)

        return _run_out(run, items=run_items)
    except HTTPException:
        raise
    except Exception as e:
        log.error("start_run failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/runs")
async def list_runs(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    org_id = _org_id(ctx)
    try:
        runs = (await db.execute(
            select(ChecklistRun)
            .where(ChecklistRun.org_id == org_id)
            .order_by(ChecklistRun.started_at.desc())
            .limit(50)
        )).scalars().all()
        return [_run_out(r) for r in runs]
    except Exception as e:
        log.error("list_runs failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/runs/{run_id}")
async def get_run(
    run_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        run = await db.scalar(
            select(ChecklistRun).where(
                ChecklistRun.id == run_id, ChecklistRun.org_id == org_id
            )
        )
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        items = (await db.execute(
            select(ChecklistRunItem).where(ChecklistRunItem.run_id == run_id)
        )).scalars().all()

        return _run_out(run, items=items)
    except HTTPException:
        raise
    except Exception as e:
        log.error("get_run failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/runs/{run_id}/check/{item_id}")
async def toggle_run_item(
    run_id: uuid.UUID,
    item_id: uuid.UUID,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    user_id = _user_id(ctx)
    try:
        run = await db.scalar(
            select(ChecklistRun).where(
                ChecklistRun.id == run_id, ChecklistRun.org_id == org_id
            )
        )
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        ri = await db.scalar(
            select(ChecklistRunItem).where(
                ChecklistRunItem.id == item_id, ChecklistRunItem.run_id == run_id
            )
        )
        if not ri:
            raise HTTPException(status_code=404, detail="Run item not found")

        now = datetime.now(timezone.utc)
        if not ri.is_checked:
            ri.is_checked = True
            ri.checked_by = user_id
            ri.checked_at = now
        else:
            ri.is_checked = False
            ri.checked_by = None
            ri.checked_at = None

        await db.flush()

        # Check if all items are now checked → complete the run
        all_items = (await db.execute(
            select(ChecklistRunItem).where(ChecklistRunItem.run_id == run_id)
        )).scalars().all()

        if all(i.is_checked for i in all_items):
            run.status = "completed"
            run.completed_at = now

        await db.commit()
        await db.refresh(ri)
        return _run_item_out(ri)
    except HTTPException:
        raise
    except Exception as e:
        log.error("toggle_run_item failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/runs/{run_id}/items/{item_id}")
async def patch_run_item(
    run_id: uuid.UUID,
    item_id: uuid.UUID,
    body: RunItemNotesPatch,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_id = _org_id(ctx)
    try:
        run = await db.scalar(
            select(ChecklistRun).where(
                ChecklistRun.id == run_id, ChecklistRun.org_id == org_id
            )
        )
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        ri = await db.scalar(
            select(ChecklistRunItem).where(
                ChecklistRunItem.id == item_id, ChecklistRunItem.run_id == run_id
            )
        )
        if not ri:
            raise HTTPException(status_code=404, detail="Run item not found")

        if body.notes is not None:
            ri.notes = body.notes

        await db.commit()
        await db.refresh(ri)
        return _run_item_out(ri)
    except HTTPException:
        raise
    except Exception as e:
        log.error("patch_run_item failed: %s", e, extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
