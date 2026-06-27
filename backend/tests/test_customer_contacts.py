"""Item 74 — Customer contacts."""
from __future__ import annotations

import pathlib

import pytest

from app.services import customer_contact as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(p: str) -> str:
    return (_BACKEND_ROOT / p).read_text()


SERVICE_SRC   = _read("app/services/customer_contact.py")
ROUTER_SRC    = _read("app/routers/customer_contacts.py")
MIGRATION_SRC = _read("migrations/versions/d2e4f6a8b0c3_v80_customer_contacts.py")
MODEL_SRC     = _read("app/models/customer_contact.py")
MAIN_SRC      = _read("app/main.py")


# ── Pure service: names ──────────────────────────────────────────────────


def test_name_trim_and_collapse():
    assert svc.normalize_name("  Anna  Lind  ") == "Anna Lind"


def test_name_preserves_non_ascii():
    assert svc.normalize_name("Östen Ström") == "Östen Ström"


def test_name_rejects_non_string():
    for bad in (None, 42, b"x", []):
        with pytest.raises(ValueError):
            svc.normalize_name(bad)  # type: ignore[arg-type]


def test_name_rejects_empty():
    with pytest.raises(ValueError):
        svc.normalize_name("   ")


def test_name_rejects_control_chars():
    with pytest.raises(ValueError):
        svc.normalize_name("Ann\x00a")


def test_name_rejects_over_limit():
    with pytest.raises(ValueError, match="128"):
        svc.normalize_name("x" * 129)


# ── Pure service: role ──────────────────────────────────────────────────


def test_role_returns_none_for_none():
    assert svc.normalize_role(None) is None


def test_role_returns_none_for_blank_string():
    assert svc.normalize_role("   ") is None


def test_role_trims_and_keeps_value():
    assert svc.normalize_role("  CFO  ") == "CFO"


def test_role_rejects_over_limit():
    with pytest.raises(ValueError, match="64"):
        svc.normalize_role("x" * 65)


def test_role_rejects_non_string():
    with pytest.raises(ValueError):
        svc.normalize_role(42)  # type: ignore[arg-type]


# ── Pure service: email ─────────────────────────────────────────────────


def test_email_lowercases_and_trims():
    assert svc.normalize_email("  Anna@Example.COM ") == "anna@example.com"


def test_email_returns_none_for_none_or_blank():
    assert svc.normalize_email(None) is None
    assert svc.normalize_email("") is None
    assert svc.normalize_email("   ") is None


def test_email_rejects_missing_at():
    with pytest.raises(ValueError):
        svc.normalize_email("not-an-email")


def test_email_rejects_missing_dot_in_domain():
    with pytest.raises(ValueError):
        svc.normalize_email("x@y")


def test_email_rejects_whitespace_inside():
    with pytest.raises(ValueError):
        svc.normalize_email("a b@example.com")


def test_email_rejects_over_limit():
    with pytest.raises(ValueError):
        svc.normalize_email("a" * 250 + "@x.com")


# ── Pure service: phone ─────────────────────────────────────────────────


def test_phone_accepts_e164_like():
    assert svc.normalize_phone("+46 70 123 45 67") == "+46 70 123 45 67"


def test_phone_accepts_parens_and_dashes():
    assert svc.normalize_phone("(070) 123-4567") == "(070) 123-4567"


def test_phone_returns_none_for_blank():
    assert svc.normalize_phone(None) is None
    assert svc.normalize_phone("   ") is None


def test_phone_rejects_letters():
    with pytest.raises(ValueError):
        svc.normalize_phone("call-me")


def test_phone_rejects_too_short():
    with pytest.raises(ValueError):
        svc.normalize_phone("12")


# ── Pure service: channel + limit ───────────────────────────────────────


def test_assert_has_channel_requires_one():
    svc.assert_has_channel(email="a@b.com", phone=None)
    svc.assert_has_channel(email=None, phone="+46701234567")
    svc.assert_has_channel(email="a@b.com", phone="+46701234567")


def test_assert_has_channel_rejects_all_empty():
    with pytest.raises(ValueError, match="at least one"):
        svc.assert_has_channel(email=None, phone=None)


def test_assert_under_limit_under_cap():
    svc.assert_under_limit(current_count=0)
    svc.assert_under_limit(current_count=49)


def test_assert_under_limit_at_cap_raises():
    with pytest.raises(ValueError, match="limit"):
        svc.assert_under_limit(current_count=50)


def test_assert_under_limit_rejects_negative():
    with pytest.raises(ValueError):
        svc.assert_under_limit(current_count=-1)


def test_constants_are_sane():
    assert svc.MAX_CONTACTS_PER_CUSTOMER == 50
    assert svc.MAX_EMAIL_LEN == 254
    assert svc.MAX_NAME_LEN == 128


# ── Migration contract ──────────────────────────────────────────────────


def test_migration_chains_from_v79():
    assert 'down_revision = "c1d3e5f7a9b2"' in MIGRATION_SRC
    assert 'revision = "d2e4f6a8b0c3"' in MIGRATION_SRC


def test_migration_creates_table():
    assert '"customer_contacts"' in MIGRATION_SRC
    for col in (
        '"name"', '"role"', '"email"', '"phone"',
        '"is_primary"', '"receives_dunning"',
        '"customer_id"', '"org_id"',
    ):
        assert col in MIGRATION_SRC


def test_migration_partial_unique_primary_index():
    # A customer can have at most one primary contact; multiple
    # non-primary rows are OK, so the uniqueness is partial.
    assert "ux_customer_contacts_one_primary_per_customer" in MIGRATION_SRC
    assert "is_primary = true" in MIGRATION_SRC
    assert "unique=True" in MIGRATION_SRC


def test_migration_cascades_on_org_and_customer():
    assert MIGRATION_SRC.count('ondelete="CASCADE"') >= 2


# ── Model contract ──────────────────────────────────────────────────────


def test_model_uses_encrypted_string_for_pii():
    # email + phone are PII — same treatment as customers.email / phone.
    assert "from app.services.encryption import EncryptedString" in MODEL_SRC
    assert "EncryptedString(512)" in MODEL_SRC  # email
    assert "EncryptedString(256)" in MODEL_SRC  # phone


def test_model_tablename_and_columns():
    assert '__tablename__ = "customer_contacts"' in MODEL_SRC
    for col in (
        "is_primary", "receives_dunning", "role", "customer_id",
        "org_id", "updated_at",
    ):
        assert col in MODEL_SRC


# ── Router contract ────────────────────────────────────────────────────


def test_router_prefix():
    assert 'prefix="/api/customer-contacts"' in ROUTER_SRC


def test_router_has_all_endpoints():
    assert '@router.get("", response_model=' in ROUTER_SRC
    assert '@router.post(' in ROUTER_SRC
    assert '@router.get("/{contact_id}"' in ROUTER_SRC
    assert '@router.patch("/{contact_id}"' in ROUTER_SRC
    assert '@router.delete("/{contact_id}"' in ROUTER_SRC
    assert '@router.post("/{contact_id}/primary"' in ROUTER_SRC


def test_router_uses_pure_service():
    for fn in (
        "normalize_name", "normalize_role",
        "normalize_email", "normalize_phone",
        "assert_has_channel", "assert_under_limit",
    ):
        assert f"svc_74.{fn}" in ROUTER_SRC


def test_router_tenant_scope_at_row_and_query_level():
    assert "row.org_id != org_id" in ROUTER_SRC
    assert "CustomerContact.org_id == member.org_id" in ROUTER_SRC


def test_router_emits_four_audit_actions():
    for action in (
        "customer_contact.created",
        "customer_contact.updated",
        "customer_contact.deleted",
        "customer_contact.promoted",
    ):
        assert f'"{action}"' in ROUTER_SRC
    # Plus the already-primary "no_op" audit + the main one = at least 5 call sites.
    assert ROUTER_SRC.count("request=request") >= 5


def test_router_demotes_existing_primary_before_create():
    # _demote_other_primaries must be invoked both on create-as-primary
    # and on the /primary endpoint — otherwise the partial unique index
    # will 500 the second primary.
    assert ROUTER_SRC.count("_demote_other_primaries(") >= 2


def test_router_404s_on_cross_tenant():
    assert '"Contact not found"' in ROUTER_SRC
    assert '"Customer not found"' in ROUTER_SRC


def test_router_handles_primary_conflict_409():
    # The INSERT path protects itself via IntegrityError so a race
    # between "create primary" and another create never 500s.
    assert "IntegrityError" in ROUTER_SRC
    assert "409" in ROUTER_SRC


def test_router_invariant_channel_on_update():
    # After patch, row must still have email or phone — the
    # assert_has_channel call must live in update_contact.
    assert "svc_74.assert_has_channel(email=row.email" in ROUTER_SRC


def test_router_registered_in_main():
    assert "customer_contacts.router" in MAIN_SRC
    assert "customer_contacts," in MAIN_SRC
