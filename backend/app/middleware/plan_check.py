# File: backend/app/middleware/plan_check.py
# Purpose: FastAPI dependency that enforces plan-level access on premium endpoints
# Used by: Any router endpoint that requires PRO or higher plan

import logging
import uuid
from collections.abc import Callable, Awaitable
from typing import Any

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.organization import OrgPlan, Organization, OrganizationMember
from app.services.plan_limits import (
    ApproachingLimitError,
    LimitExceededError,
    check_limit,
    is_feature_unlocked,
)

log = logging.getLogger(__name__)

# Plan hierarchy — index position determines relative rank
_PLAN_RANK: dict[OrgPlan, int] = {
    OrgPlan.FREE: 0,
    OrgPlan.PRO:  1,
    OrgPlan.ENTERPRISE: 2,
}


async def _get_org_plan(user_id: uuid.UUID, db: AsyncSession) -> OrgPlan:
    """Look up the organisation plan for a user via their OrganizationMember row.

    When a user belongs to multiple orgs (e.g. invited to a partner's org
    alongside their own), this function MUST resolve to the same org that
    `get_current_member` resolves to — otherwise `require_plan` would gate
    on Org A's plan while the request body operates on Org B's data,
    letting a user on a FREE org access PRO features by virtue of having a
    PRO membership in a different org. Matches the deterministic ordering
    used in middleware/auth.py: earliest-joined membership wins.
    """
    row = await db.execute(
        select(Organization.plan)
        .join(OrganizationMember, OrganizationMember.org_id == Organization.id)
        .where(OrganizationMember.user_id == user_id)
        .order_by(OrganizationMember.created_at.asc(), OrganizationMember.id.asc())
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


def require_feature(feature_name: str):
    """Return a FastAPI dependency that blocks the endpoint when *feature_name*
    is not available on the caller's current plan.

    Raises HTTP 403 with a structured payload:
        {
            "code": "FEATURE_NOT_AVAILABLE",
            "feature": "<feature_name>",
            "current_plan": "<plan>",
            "suggested_upgrade_url": "<url>"
        }

    Usage:
        @router.post("/webhooks")
        async def create_webhook(
            _: None = Depends(require_feature("api_webhooks")),
            ...
        ): ...
    """
    from app.config import settings  # local import avoids circular load

    async def _check(
        current_user: dict = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        plan = await _get_org_plan(current_user["user_id"], db)
        if not is_feature_unlocked(plan, feature_name):
            log.warning(
                '"event":"feature_gate_denied","user_id":"%s","plan":"%s","feature":"%s"',
                current_user["user_id"], plan.value, feature_name,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FEATURE_NOT_AVAILABLE",
                    "feature": feature_name,
                    "current_plan": plan.value,
                    "suggested_upgrade_url": f"{settings.FRONTEND_URL}/en/settings/billing",
                },
            )

    return _check


def check_resource_limit(resource: str, count_fn: Callable[..., Awaitable[int]]):
    """Return a FastAPI dependency that enforces a resource cap.

    *count_fn* must be an async callable that accepts ``(org_id, db)`` and
    returns the current integer usage count.  It is called inside the
    dependency so it shares the same DB session as the outer request.

    At ≥ 80 % usage the dependency still passes but logs a warning.
    At 100 % it raises HTTP 403:
        {
            "code": "PLAN_LIMIT_EXCEEDED",
            "resource": "<resource>",
            "current_plan": "<plan>",
            "limit": <int>,
            "current": <int>,
            "suggested_upgrade_url": "<url>"
        }

    Usage:
        async def _count_products(org_id, db):
            result = await db.execute(
                select(func.count()).where(Product.org_id == org_id)
            )
            return result.scalar_one()

        @router.post("/products")
        async def create_product(
            _: None = Depends(check_resource_limit(RESOURCE_PRODUCTS, _count_products)),
            ...
        ): ...
    """
    from app.config import settings  # local import avoids circular load
    from app.middleware.auth import get_current_member  # get (member, org_id)

    async def _check(
        ctx: tuple = Depends(get_current_member),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        _user_dict, member = ctx
        org_id = member.org_id
        plan = await _get_org_plan(member.user_id, db)

        current = await count_fn(org_id, db)

        try:
            check_limit(plan, resource, current)
        except LimitExceededError as exc:
            log.warning(
                '"event":"resource_limit_exceeded","org_id":"%s","plan":"%s","resource":"%s","current":%d,"limit":%d',
                org_id, plan.value, resource, exc.current, exc.limit,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PLAN_LIMIT_EXCEEDED",
                    "resource": resource,
                    "current_plan": plan.value,
                    "limit": exc.limit,
                    "current": exc.current,
                    "suggested_upgrade_url": f"{settings.FRONTEND_URL}/en/settings/billing",
                },
            )
        except ApproachingLimitError as exc:
            log.warning(
                '"event":"resource_limit_approaching","org_id":"%s","plan":"%s","resource":"%s","pct":"%.0f%%"',
                org_id, plan.value, resource, exc.percentage * 100,
            )
            # Warn but do NOT block — request proceeds normally.

    return _check
