"""Internal admin endpoints — protected by X-Admin-Key header.

These endpoints work in ALL environments (not just dev) so operators can
manage production orgs without direct DB access. The X-Admin-Key check uses
constant-time comparison to prevent timing attacks.

Rule 2 exception: no per-org JWT required — these are operator actions on
org data. The admin key is the only auth mechanism for this router.
"""
import logging
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.organization import OrgPlan, Organization
from app.services.audit import log_action

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def _require_admin(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
):
    """Constant-time comparison against ADMIN_API_KEY."""
    current = getattr(settings, "ADMIN_API_KEY", "") or ""
    if not current:
        raise HTTPException(status_code=503, detail="Admin API not configured")
    if not x_admin_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin key")
    if not secrets.compare_digest(x_admin_key, current):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin key")


class SetPlanBody(BaseModel):
    org_id: str
    plan: str  # "FREE" | "PRO" | "ENTERPRISE"


@router.post("/set-plan", dependencies=[Depends(_require_admin)])
async def set_org_plan(body: SetPlanBody, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        target_plan = OrgPlan(body.plan.upper())
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown plan: {body.plan}. Valid values: FREE, PRO, ENTERPRISE",
        )

    result = await db.execute(select(Organization).where(Organization.id == body.org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    previous_plan = org.plan.value
    org.plan = target_plan
    await db.commit()

    try:
        await log_action(
            db,
            action="ADMIN_SET_PLAN",
            org_id=str(org.id),
            actor_user_id=None,
            target_type="organization",
            target_id=str(org.id),
            request=request,
            extra={"previous_plan": previous_plan, "new_plan": target_plan.value},
        )
        await db.commit()
    except Exception as e:
        log.error("admin_set_plan_audit_failed err=%s", e)
        await db.rollback()

    return {
        "ok": True,
        "org_id": str(org.id),
        "org_name": org.name,
        "previous_plan": previous_plan,
        "plan": target_plan.value,
    }


@router.get("/orgs", dependencies=[Depends(_require_admin)])
async def list_orgs(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all orgs — useful for finding org_id after a user signs up."""
    limit = max(1, min(limit, 200))
    result = await db.execute(
        select(Organization)
        .order_by(Organization.id)
        .limit(limit)
        .offset(offset)
    )
    orgs = result.scalars().all()
    return {
        "count": len(orgs),
        "items": [
            {"id": str(o.id), "name": o.name, "plan": o.plan.value}
            for o in orgs
        ],
    }
