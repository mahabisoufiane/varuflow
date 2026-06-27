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
from app.features.auth.organization import OrgPlan, OrgRole, Organization, OrganizationMember
from app.services.plan_limits import (
    ApproachingLimitError,
    LimitExceededError,
    PLAN_MODULES,
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

# Role hierarchy — controls *role-within-module* access. Having a module grants
# the module; the role then decides how much of it you see:
#   MEMBER = regular employee (own data: own leave, own timesheet, clock in/out)
#   ADMIN  = manager / HR admin (team data: roster, approvals, reviews)
#   OWNER  = owner (payroll, salaries, destructive actions)
# A higher rank satisfies any lower requirement.
_ROLE_RANK: dict[OrgRole, int] = {
    OrgRole.MEMBER: 0,
    OrgRole.ADMIN:  1,
    OrgRole.OWNER:  2,
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


def require_role(minimum: OrgRole):
    """Return a FastAPI dependency that enforces a minimum *org role*.

    This is the role-within-module guard. Use it ALONGSIDE ``require_module``:
    the module check decides whether the user can touch the feature at all;
    this check decides whether their role is senior enough for the specific
    action. Example — every HR member can file their own leave, but only a
    manager (ADMIN) can approve someone else's:

        @router.post("/leave")                       # any HR member
        async def request_leave(...): ...

        @router.post("/leave/{id}/approve",          # managers only
            dependencies=[Depends(require_role(OrgRole.ADMIN))])
        async def approve_leave(...): ...

    Raises 403 with a structured payload the frontend can branch on:
        {"code": "INSUFFICIENT_ROLE", "required": "ADMIN", "current": "MEMBER"}
    """
    from app.middleware.auth import get_current_member  # local: avoids circular import

    async def _check(ctx: tuple = Depends(get_current_member)) -> None:
        _user_dict, member = ctx
        if _ROLE_RANK.get(member.role, 0) < _ROLE_RANK.get(minimum, 99):
            log.warning(
                '"event":"role_gate_denied","user_id":"%s","has":"%s","required":"%s"',
                member.user_id, member.role.value, minimum.value,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "INSUFFICIENT_ROLE",
                    "required": minimum.value,
                    "current": member.role.value,
                },
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


def require_module(module_key: str):
    """Return a FastAPI dependency that enforces module-level access.

    Checks two layers:
    1. Plan tier — is this module available on the org's plan?
    2. User assignment — is this user granted access to the module?

    OWNER and ADMIN roles bypass the user assignment check (they have
    access to all modules their plan allows). Only MEMBER-role users
    with ``module_access_mode = 'RESTRICTED'`` are gated.

    Usage:
        @router.get("/sales")
        async def list_sales(
            _: None = Depends(require_module("pos")),
            ...
        ): ...
    """
    from app.middleware.auth import get_current_member
    from app.features.auth.modules import MemberModule
    from app.features.auth.organization import OrgRole

    async def _check(
        ctx: tuple = Depends(get_current_member),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        _user_dict, member = ctx
        org_id = member.org_id
        plan = await _get_org_plan(member.user_id, db)

        plan_key = plan.value if hasattr(plan, "value") else str(plan)
        allowed_modules = PLAN_MODULES.get(plan_key, frozenset())

        if "*" not in allowed_modules and module_key not in allowed_modules:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "MODULE_NOT_IN_PLAN",
                    "module": module_key,
                    "current_plan": plan_key,
                },
            )

        if member.role in (OrgRole.OWNER, OrgRole.ADMIN):
            return

        if getattr(member, "module_access_mode", "ALL") == "ALL":
            return

        has_access = await db.scalar(
            select(MemberModule.id).where(
                MemberModule.member_id == member.id,
                MemberModule.module_key == module_key,
            )
        )
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "MODULE_NOT_ASSIGNED",
                    "module": module_key,
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
