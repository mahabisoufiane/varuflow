"""Source-contract tests for team / HR endpoints.

Validates structural invariants of the team and payroll routers using
``inspect.getsource`` and file reads — no DB or async runtime required.

Covers:
  - Team member CRUD endpoints exist
  - Role management (OWNER, ADMIN, MEMBER)
  - Org isolation (queries filter by org_id)
  - Auth dependency on every endpoint
  - Invite flow with plan limits
  - Remove member safeguards
  - Audit logging via log_action
  - Payroll router auth & org isolation
"""
from __future__ import annotations

import inspect
import pathlib

import pytest

_BACKEND = pathlib.Path(__file__).resolve().parents[1] / "app"


def _read(relpath: str) -> str:
    return (_BACKEND / relpath).read_text()


TEAM_SRC = _read("routers/team.py")
PAYROLL_SRC = _read("routers/payroll.py")


# ═══════════════════════════════════════════════════════════════════
# 1. Team CRUD endpoints exist
# ═══════════════════════════════════════════════════════════════════


def test_list_members_endpoint_exists():
    """GET /api/team must be defined."""
    assert "@router.get(" in TEAM_SRC
    assert "async def list_members" in TEAM_SRC


def test_invite_endpoint_exists():
    """POST /api/team/invite must be defined."""
    assert '"/invite"' in TEAM_SRC or "'/invite'" in TEAM_SRC
    assert "async def invite_member" in TEAM_SRC


def test_update_role_endpoint_exists():
    """PATCH /api/team/{member_id}/role must be defined."""
    assert "/{member_id}/role" in TEAM_SRC
    assert "async def update_role" in TEAM_SRC


def test_remove_member_endpoint_exists():
    """DELETE /api/team/{member_id} must be defined."""
    assert '@router.delete("/{member_id}"' in TEAM_SRC
    assert "async def remove_member" in TEAM_SRC


# ═══════════════════════════════════════════════════════════════════
# 2. Role management — OWNER / ADMIN / MEMBER
# ═══════════════════════════════════════════════════════════════════


def test_three_roles_referenced():
    """Router must reference all three OrgRole values."""
    assert "OrgRole.OWNER" in TEAM_SRC
    assert "OrgRole.ADMIN" in TEAM_SRC
    assert "OrgRole.MEMBER" in TEAM_SRC


def test_owner_required_for_role_change():
    """update_role must call _require_owner (not _require_owner_or_admin)."""
    # Extract the update_role function body
    idx = TEAM_SRC.index("async def update_role")
    body = TEAM_SRC[idx:idx + 600]
    assert "_require_owner(caller)" in body


def test_admin_cannot_invite_owner():
    """Privilege-escalation guard: non-owners cannot invite OrgRole.OWNER."""
    assert "body.role == OrgRole.OWNER" in TEAM_SRC
    assert "Only an existing owner can invite another owner" in TEAM_SRC


# ═══════════════════════════════════════════════════════════════════
# 3. Org isolation
# ═══════════════════════════════════════════════════════════════════


def test_list_members_filters_by_org_id():
    """list_members query must filter by org_id."""
    idx = TEAM_SRC.index("async def list_members")
    body = TEAM_SRC[idx:idx + 500]
    assert "OrganizationMember.org_id == member.org_id" in body


def test_update_role_filters_by_org_id():
    """update_role must scope target lookup to caller's org."""
    idx = TEAM_SRC.index("async def update_role")
    body = TEAM_SRC[idx:idx + 800]
    assert "OrganizationMember.org_id == caller.org_id" in body


def test_remove_member_filters_by_org_id():
    """remove_member must scope target lookup to caller's org."""
    idx = TEAM_SRC.index("async def remove_member")
    body = TEAM_SRC[idx:idx + 800]
    assert "OrganizationMember.org_id == caller.org_id" in body


# ═══════════════════════════════════════════════════════════════════
# 4. Auth dependency on every endpoint
# ═══════════════════════════════════════════════════════════════════


def test_all_endpoints_have_auth_dependency():
    """Every endpoint must depend on get_current_member or require_mfa_if_enforced."""
    assert "get_current_member" in TEAM_SRC or "require_mfa_if_enforced" in TEAM_SRC
    # list_members uses get_current_member
    assert "Depends(get_current_member)" in TEAM_SRC
    # invite, update_role, remove use require_mfa_if_enforced
    assert TEAM_SRC.count("Depends(require_mfa_if_enforced)") >= 3


# ═══════════════════════════════════════════════════════════════════
# 5. Invite flow
# ═══════════════════════════════════════════════════════════════════


def test_invite_enforces_plan_limits():
    """Invite must check plan member limits before inserting."""
    assert "check_limit" in TEAM_SRC
    assert "PLAN_LIMIT_EXCEEDED" in TEAM_SRC


def test_invite_uses_select_for_update():
    """Race-condition safety: invite must lock the org row."""
    idx = TEAM_SRC.index("async def invite_member")
    body = TEAM_SRC[idx:idx + 2500]
    assert "with_for_update()" in body


# ═══════════════════════════════════════════════════════════════════
# 6. Remove member safeguards
# ═══════════════════════════════════════════════════════════════════


def test_cannot_remove_self():
    """remove_member must prevent self-removal."""
    idx = TEAM_SRC.index("async def remove_member")
    body = TEAM_SRC[idx:idx + 1800]
    assert "Cannot remove yourself" in body


def test_cannot_remove_last_owner():
    """remove_member must prevent removing the last owner."""
    idx = TEAM_SRC.index("async def remove_member")
    body = TEAM_SRC[idx:idx + 2500]
    assert "Cannot remove the last owner" in body


# ═══════════════════════════════════════════════════════════════════
# 7. Audit logging
# ═══════════════════════════════════════════════════════════════════


def test_invite_logs_audit_action():
    """Invite must call log_action with team.member_invited."""
    assert '"team.member_invited"' in TEAM_SRC or "'team.member_invited'" in TEAM_SRC


def test_role_change_logs_audit_action():
    """Role change must call log_action with team.role_changed."""
    assert '"team.role_changed"' in TEAM_SRC or "'team.role_changed'" in TEAM_SRC


def test_remove_logs_audit_action():
    """Remove must call log_action with team.member_removed."""
    assert '"team.member_removed"' in TEAM_SRC or "'team.member_removed'" in TEAM_SRC


# ═══════════════════════════════════════════════════════════════════
# 8. Payroll router — auth & org isolation
# ═══════════════════════════════════════════════════════════════════


def test_payroll_endpoints_have_auth():
    """Every payroll endpoint must use get_current_member."""
    assert PAYROLL_SRC.count("Depends(get_current_member)") >= 6


def test_payroll_filters_by_org_id():
    """Payroll queries must filter by org_id."""
    assert "PayrollRun.org_id == org_id" in PAYROLL_SRC
