"""Dev-only tooling endpoints — only active when ENV=development.

All handlers start with an immediate 404 guard so this router can be
registered unconditionally while remaining completely inert in production.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.organization import OrgPlan, Organization

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dev", tags=["dev-tools"])

_VALID_PLANS = {p.value for p in OrgPlan}


def _require_dev() -> None:
    if settings.ENV != "development":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


class SetPlanRequest(BaseModel):
    plan: str  # FREE | PRO | ENTERPRISE


@router.post("/set-plan")
async def set_plan(
    body: SetPlanRequest,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """Instantly upgrade or downgrade the dev org's plan.

    Only reachable when ENV=development — returns 404 in production.
    """
    _require_dev()

    plan_upper = body.plan.upper()
    if plan_upper not in _VALID_PLANS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid plan '{body.plan}'. Choose from: {sorted(_VALID_PLANS)}",
        )

    _, member = ctx
    org = await db.get(Organization, member.org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Org not found")

    org.plan = OrgPlan(plan_upper)
    await db.commit()
    logger.info("[dev] org %s plan set to %s", org.id, plan_upper)
    return {"ok": True, "org_id": str(org.id), "plan": plan_upper}
