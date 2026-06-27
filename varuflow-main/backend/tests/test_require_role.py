"""Role-within-module guard — require_role() dependency.

Verifies the central role gate that decides how much of a module a member sees:
  MEMBER < ADMIN < OWNER

These tests exercise the dependency directly (no DB) by invoking the inner
check with a fake member context, so they run even without PostgreSQL.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.middleware.plan_check import _ROLE_RANK, require_role
from app.features.auth.organization import OrgRole


def _ctx(role: OrgRole) -> tuple:
    """Build a minimal (user_dict, member) context for the dependency."""
    member = SimpleNamespace(role=role, user_id=uuid.uuid4())
    return ({"user_id": member.user_id, "email": "x@y.z"}, member)


def _inner(dep):
    """Extract the inner async _check from the dependency closure."""
    return dep


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "minimum,role,allowed",
    [
        # MEMBER-level endpoint — everyone passes
        (OrgRole.MEMBER, OrgRole.MEMBER, True),
        (OrgRole.MEMBER, OrgRole.ADMIN, True),
        (OrgRole.MEMBER, OrgRole.OWNER, True),
        # ADMIN-level endpoint — members blocked, admins+owners pass
        (OrgRole.ADMIN, OrgRole.MEMBER, False),
        (OrgRole.ADMIN, OrgRole.ADMIN, True),
        (OrgRole.ADMIN, OrgRole.OWNER, True),
        # OWNER-level endpoint — only owner passes
        (OrgRole.OWNER, OrgRole.MEMBER, False),
        (OrgRole.OWNER, OrgRole.ADMIN, False),
        (OrgRole.OWNER, OrgRole.OWNER, True),
    ],
)
async def test_require_role_matrix(minimum, role, allowed):
    # FastAPI dependencies are factories; the returned object is the inner
    # coroutine function. Build it, then call with our fake ctx.
    dep = require_role(minimum)
    # The dependency is a closure `_check(ctx=Depends(...))`; call it directly
    # passing ctx positionally.
    if allowed:
        result = await dep(_ctx(role))
        assert result is None
    else:
        with pytest.raises(HTTPException) as exc:
            await dep(_ctx(role))
        assert exc.value.status_code == 403
        assert exc.value.detail["code"] == "INSUFFICIENT_ROLE"
        assert exc.value.detail["required"] == minimum.value
        assert exc.value.detail["current"] == role.value


def test_role_rank_ordering():
    """MEMBER < ADMIN < OWNER must hold for the gate to make sense."""
    assert _ROLE_RANK[OrgRole.MEMBER] < _ROLE_RANK[OrgRole.ADMIN]
    assert _ROLE_RANK[OrgRole.ADMIN] < _ROLE_RANK[OrgRole.OWNER]
