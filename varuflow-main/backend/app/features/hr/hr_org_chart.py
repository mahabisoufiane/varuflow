"""HR Org chart router: hierarchical tree from reports_to_staff_id."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.middleware.plan_check import require_module, require_role
from app.features.bookings.models import Staff
from .models import EmployeeProfile
from app.features.auth.organization import OrgRole

log = logging.getLogger(__name__)
# Org chart exposes reporting lines / management structure — manager-level.
router = APIRouter(dependencies=[Depends(require_module("hr")), Depends(require_role(OrgRole.ADMIN))])


def _build_tree(nodes: list[dict]) -> list[dict]:
    by_id = {n["id"]: n for n in nodes}
    roots: list[dict] = []
    for n in nodes:
        pid = n.get("reports_to_staff_id")
        if pid and str(pid) in by_id:
            by_id[str(pid)]["children"].append(n)
        else:
            roots.append(n)
    return roots


@router.get("/api/hr/org-chart")
async def org_chart(
    auth=Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    user, member = auth
    org_id = member.org_id
    try:
        staff_rows = (await db.execute(
            select(Staff).where(Staff.org_id == org_id)
        )).scalars().all()

        profile_map: dict[str, EmployeeProfile] = {
            str(p.staff_id): p
            for p in (await db.execute(
                select(EmployeeProfile).where(EmployeeProfile.org_id == org_id)
            )).scalars().all()
        }

        nodes: list[dict] = []
        for s in staff_rows:
            p = profile_map.get(str(s.id))
            nodes.append({
                "id": str(s.id),
                "name": s.name,
                "role": getattr(s, "role", None),
                "job_title": p.job_title if p else None,
                "employment_type": p.employment_type if p else None,
                "reports_to_staff_id": str(p.reports_to_staff_id) if p and p.reports_to_staff_id else None,
                "children": [],
            })

        return _build_tree(nodes)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"org_chart failed: {e}", extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
