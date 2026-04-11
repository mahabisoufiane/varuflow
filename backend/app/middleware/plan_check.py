# File: backend/app/middleware/plan_check.py
# Purpose: FastAPI dependency that enforces plan-level access on premium endpoints
# Used by: Any router endpoint that requires PRO or higher plan

import logging
import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.organization import OrgPlan, Organization, OrganizationMember

log = logging.getLogger(__name__)

# Plan hierarchy — index position determines relative rank
_PLAN_RANK: dict[OrgPlan, int] = {
    OrgPlan.FREE: 0,
    OrgPlan.PRO:  1,
}


async def _get_org_plan(user_id: uuid.UUID, db: AsyncSession) -> OrgPlan:
    """Look up the organisation plan for a user via their OrganizationMember row."""
    row = await db.execute(
        select(Organization.plan)
        .join(OrganizationMember, OrganizationMember.org_id == Organization.id)
        .where(OrganizationMember.user_id == user_id)
        .limit(1)
    )
    plan = row.scalar_one_or_none()
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found. Complete onboarding first.",
        )
    return plan


def require_plan(minimum: OrgPlan):
    """Return a FastAPI dependency that enforces a minimum plan level.

    Usage:
        @router.get("/advanced")
        async def advanced(
            _: None = Depends(require_plan(OrgPlan.PRO)),
            user: dict = Depends(get_current_user),
        ): ...
    """
    async def _check(
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        plan = await _get_org_plan(current_user["user_id"], db)
        if _PLAN_RANK.get(plan, 0) < _PLAN_RANK.get(minimum, 999):
            log.warning(
                '"event":"plan_gate_denied","user_id":"%s","has":"%s","required":"%s"',
                current_user["user_id"], plan.value, minimum.value,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires {minimum.value} plan or above.",
            )

    return _check
