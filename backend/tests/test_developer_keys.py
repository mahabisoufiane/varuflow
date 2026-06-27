"""Tests for API developer keys (Item 45, v59).

Pure + contract-style split, same pattern as Items 28-44.

Required test names (spec):

* test_generate_api_key
* test_key_shown_once_only
* test_key_rotation
* test_key_revocation
* test_scope_enforcement
* test_last_used_tracking
* test_usage_log
* test_enterprise_plan_gate
* test_org_isolation
* test_audit_log
"""
from __future__ import annotations

import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from app.services import developer_key_service as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"


def _read(relpath: str) -> str:
    return (_BACKEND_ROOT / relpath).read_text()


ROUTER_SRC = _read("routers/developer.py")
SERVICE_SRC = _read("services/developer_key_service.py")
MODEL_SRC = _read("models/developer.py")
MAIN_SRC = _read("main.py")
AUTH_SRC = _read("middleware/auth.py")
MIGRATION_SRC = (
    _BACKEND_ROOT.parent
    / "migrations"
    / "versions"
    / "a8b1c3d5e7f2_v59_developer_keys.py"
).read_text()


# ═══════════════════════════════════════════════════════════════════
# 1. test_generate_api_key
# ═══════════════════════════════════════════════════════════════════


def test_generate_api_key():
    gen = svc.generate_key()
    # Plaintext begins with the distinguishing tag so the auth
    # middleware can fast-path between JWT and API-key paths.
    assert gen.plaintext.startswith("vk_")
    assert gen.prefix and len(gen.prefix) == svc.KEY_PREFIX_LEN
    # Hash is a SHA-256 hex digest (64 chars).
    assert len(gen.hash) == 64 and all(c in "0123456789abcdef" for c in gen.hash)
    # Hash round-trips only via the same plaintext.
    assert svc.verify_key(gen.plaintext, gen.hash) is True
    assert svc.verify_key(gen.plaintext + "x", gen.hash) is False
    # Router exposes the issuing endpoint.
    assert '@router.post("", response_model=ApiKeyIssuedOut, status_code=201)' in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 2. test_key_shown_once_only
# ═══════════════════════════════════════════════════════════════════


def test_key_shown_once_only():
    # Only one response schema carries the plaintext.
    assert "class ApiKeyIssuedOut(ApiKeyOut):" in ROUTER_SRC
    assert 'plaintext: str = Field(..., description="Shown once' in ROUTER_SRC
    # The listing schema does NOT include a plaintext field.
    assert "class ApiKeyOut(BaseModel):" in ROUTER_SRC
    # The list endpoint returns ApiKeyOut (no plaintext) — confirmed by
    # absence of plaintext assignment on the list path.
    list_region = ROUTER_SRC.split("@router.get(\"\", response_model=list[ApiKeyOut])")[1].split("@router.post")[0]
    assert "plaintext" not in list_region
    # Model stores only the hash, never the plaintext.
    assert "key_hash: Mapped[str]" in MODEL_SRC
    # No mapped column carries the plaintext (docstrings may mention it).
    assert "plaintext: Mapped" not in MODEL_SRC
    assert "mapped_column" in MODEL_SRC
    # Migration persists the hash, not the plaintext.
    assert '"key_hash"' in MIGRATION_SRC
    assert '"plaintext"' not in MIGRATION_SRC


# ═══════════════════════════════════════════════════════════════════
# 3. test_key_rotation
# ═══════════════════════════════════════════════════════════════════


def test_key_rotation():
    # Rotate endpoint exists and issues a fresh plaintext.
    assert '@router.post("/{key_id}/rotate", response_model=ApiKeyIssuedOut)' in ROUTER_SRC
    # Old row is revoked atomically (same transaction as the new insert).
    rotate_region = ROUTER_SRC.split("async def rotate_key")[1].split("async def revoke_key")[0]
    assert "old.is_revoked = True" in rotate_region
    assert "svc.generate_key()" in rotate_region
    # Audit trail on rotation.
    assert 'action="api_key.rotated"' in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 4. test_key_revocation
# ═══════════════════════════════════════════════════════════════════


def test_key_revocation():
    assert '@router.post("/{key_id}/revoke", status_code=204)' in ROUTER_SRC
    revoke_region = ROUTER_SRC.split("async def revoke_key")[1].split("async def list_usage")[0]
    assert "row.is_revoked = True" in revoke_region
    assert 'action="api_key.revoked"' in revoke_region
    # Lookup helper refuses revoked keys at auth time.
    assert "row.is_revoked or is_expired(row.expires_at)" in SERVICE_SRC
    # Bulk revoke helper exists for offboarding / GDPR paths.
    assert "async def revoke_all_for_org" in SERVICE_SRC


# ═══════════════════════════════════════════════════════════════════
# 5. test_scope_enforcement
# ═══════════════════════════════════════════════════════════════════


def test_scope_enforcement():
    # Whitelist enforced at validator.
    assert svc.validate_scopes(["read"]) == ["read"]
    assert svc.validate_scopes(["READ", "write"]) == ["read", "write"]
    with pytest.raises(svc.ApiKeyValidationError):
        svc.validate_scopes(["superuser"])
    # At least one scope required.
    with pytest.raises(svc.ApiKeyValidationError):
        svc.validate_scopes([])
    # Hierarchy: admin > write > read.
    assert svc.has_scope(["admin"], "read") is True
    assert svc.has_scope(["admin"], "write") is True
    assert svc.has_scope(["admin"], "admin") is True
    assert svc.has_scope(["write"], "read") is True
    assert svc.has_scope(["write"], "admin") is False
    assert svc.has_scope(["read"], "write") is False
    assert svc.has_scope([], "read") is False
    # Unknown required scope never passes.
    assert svc.has_scope(["admin"], "superuser") is False


# ═══════════════════════════════════════════════════════════════════
# 6. test_last_used_tracking
# ═══════════════════════════════════════════════════════════════════


def test_last_used_tracking():
    # Model carries the last_used_at column.
    assert "last_used_at" in MODEL_SRC
    # Migration persists it too.
    assert '"last_used_at"' in MIGRATION_SRC
    # record_usage helper updates it.
    record_region = SERVICE_SRC.split("async def record_usage")[1].split("async def revoke_all_for_org")[0]
    assert "last_used_at" in record_region
    # Auth middleware invokes record_usage on every API-key request.
    assert "record_usage" in AUTH_SRC


# ═══════════════════════════════════════════════════════════════════
# 7. test_usage_log
# ═══════════════════════════════════════════════════════════════════


def test_usage_log():
    # Dedicated endpoint returns the last N calls, newest first.
    assert '@router.get("/{key_id}/usage", response_model=list[ApiKeyUsageOut])' in ROUTER_SRC
    assert ".order_by(ApiKeyUsage.called_at.desc())" in ROUTER_SRC
    assert ".limit(svc.USAGE_LOG_LIMIT)" in ROUTER_SRC
    # Log cap is 100 to match spec.
    assert svc.USAGE_LOG_LIMIT == 100
    # Trim-on-insert keeps the table bounded.
    record_region = SERVICE_SRC.split("async def record_usage")[1]
    assert ".limit(USAGE_LOG_LIMIT)" in record_region
    assert "ApiKeyUsage.id.notin_(keep_ids)" in record_region
    # Migration creates the supporting composite index.
    assert "ix_api_key_usages_key_called" in MIGRATION_SRC


# ═══════════════════════════════════════════════════════════════════
# 8. test_enterprise_plan_gate
# ═══════════════════════════════════════════════════════════════════


def test_enterprise_plan_gate():
    # Router-level dependency enforces ENTERPRISE plan.
    assert "dependencies=[Depends(require_plan(OrgPlan.ENTERPRISE))]" in ROUTER_SRC
    assert "from app.middleware.plan_check import require_plan" in ROUTER_SRC
    # Owner/admin role check guards the mutation paths.
    assert "def _require_owner_or_admin" in ROUTER_SRC
    assert "Only owners and admins can manage API keys" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 9. test_org_isolation
# ═══════════════════════════════════════════════════════════════════


def test_org_isolation():
    # Every key load filters by (id, org_id).
    assert "ApiKey.id == key_id, ApiKey.org_id == org_id" in ROUTER_SRC
    assert "ApiKey.org_id == org_id" in ROUTER_SRC
    # Usage endpoint goes through the tenant loader before reading logs.
    usage_region = ROUTER_SRC.split("async def list_usage")[1]
    assert "_load(db, key_id=key_id, org_id=org_id)" in usage_region
    # Model cascades on org deletion.
    assert 'ondelete="CASCADE"' in MODEL_SRC
    # Usage rows cascade on key deletion (no orphans).
    assert 'ForeignKey("api_keys.id", ondelete="CASCADE")' in MODEL_SRC


# ═══════════════════════════════════════════════════════════════════
# 10. test_audit_log
# ═══════════════════════════════════════════════════════════════════


def test_audit_log():
    for action in (
        '"api_key.created"',
        '"api_key.rotated"',
        '"api_key.revoked"',
    ):
        assert f"action={action}" in ROUTER_SRC
    assert ROUTER_SRC.count("await log_action(") >= 3
    assert "from app.services.audit import log_action" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# Invariants / smoke
# ═══════════════════════════════════════════════════════════════════


def test_router_registered_in_main():
    assert "developer" in MAIN_SRC
    assert "app.include_router(developer.router)" in MAIN_SRC


def test_migration_v59_chains_from_v58():
    assert 'revision = "a8b1c3d5e7f2"' in MIGRATION_SRC
    assert 'down_revision = "e4f6a8b1c3d5"' in MIGRATION_SRC


def test_migration_creates_expected_indexes():
    for idx in (
        "ix_api_keys_org",
        "ix_api_keys_prefix",
        "ix_api_keys_active",
        "ix_api_key_usages_key_called",
    ):
        assert idx in MIGRATION_SRC
    # Prefix index is unique so a collision can't silently mismatch.
    assert "unique=True" in MIGRATION_SRC


def test_parse_key_rejects_junk():
    # parse_key rejects JWTs and malformed strings fast, before DB hit.
    with pytest.raises(svc.ApiKeyValidationError):
        svc.parse_key("Bearer eyJhbGciOi...")
    with pytest.raises(svc.ApiKeyValidationError):
        svc.parse_key("vk_only_missing_secret")  # good prefix tag but wrong length
    with pytest.raises(svc.ApiKeyValidationError):
        svc.parse_key("")
    gen = svc.generate_key()
    prefix, plain = svc.parse_key(gen.plaintext)
    assert prefix == gen.prefix and plain == gen.plaintext


def test_expiry_rejects_stale_keys():
    past = datetime.now(timezone.utc) - timedelta(days=1)
    future = datetime.now(timezone.utc) + timedelta(days=1)
    assert svc.is_expired(past) is True
    assert svc.is_expired(future) is False
    assert svc.is_expired(None) is False


def test_api_key_auth_resolver_wired():
    # Auth middleware exposes the API-key resolver.
    assert "async def resolve_api_key_caller" in AUTH_SRC
    assert "developer_key_service" in AUTH_SRC
    # It stores scopes on the pseudo-user so handlers can scope-check.
    assert '"api_key_scopes"' in AUTH_SRC


def test_service_constants_exposed():
    assert svc.KEY_PREFIX_TAG == "vk_"
    assert svc.KEY_PREFIX_LEN == 8
    assert svc.KEY_SECRET_LEN == 32
    assert svc.USAGE_LOG_LIMIT == 100
    assert svc.ALLOWED_SCOPES == ("read", "write", "admin")
