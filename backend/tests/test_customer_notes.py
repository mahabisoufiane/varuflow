"""Item 71 — Customer notes."""
from __future__ import annotations

import pathlib

import pytest

from app.services import customer_note as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(p: str) -> str:
    return (_BACKEND_ROOT / p).read_text()


MIGRATION_SRC = _read(
    "migrations/versions/b9c1d3e5f7a8_v78_customer_notes.py"
)
MODEL_SRC   = _read("app/models/customer_note.py")
SERVICE_SRC = _read("app/services/customer_note.py")
ROUTER_SRC  = _read("app/routers/customer_notes.py")
MAIN_SRC    = _read("app/main.py")


# ── Pure service — validate_body ──────────────────────────────────────────


def test_validate_body_strips_and_returns():
    assert svc.validate_body("  hello  ") == "hello"


def test_validate_body_preserves_internal_whitespace():
    body = "line one\nline two\n- bullet"
    assert svc.validate_body(body) == body


def test_validate_body_rejects_none():
    with pytest.raises(ValueError):
        svc.validate_body(None)  # type: ignore[arg-type]


def test_validate_body_rejects_non_string():
    with pytest.raises(ValueError):
        svc.validate_body(42)  # type: ignore[arg-type]


def test_validate_body_rejects_empty():
    with pytest.raises(ValueError, match="required"):
        svc.validate_body("")
    with pytest.raises(ValueError, match="required"):
        svc.validate_body("   \n\t ")


def test_validate_body_rejects_overlong():
    with pytest.raises(ValueError, match="too long"):
        svc.validate_body("x" * (svc.MAX_BODY_LENGTH + 1))


def test_validate_body_accepts_at_max_length():
    s = "x" * svc.MAX_BODY_LENGTH
    assert svc.validate_body(s) == s


# ── Pure service — extract_mentions ──────────────────────────────────────


def test_extract_mentions_basic():
    assert svc.extract_mentions("hey @alice check this") == ["alice"]


def test_extract_mentions_multiple_and_dedup():
    body = "@bob pinged @alice and @bob again"
    assert svc.extract_mentions(body) == ["bob", "alice"]


def test_extract_mentions_preserves_order():
    assert svc.extract_mentions("@c @a @b") == ["c", "a", "b"]


def test_extract_mentions_case_insensitive_dedup():
    assert svc.extract_mentions("@Alice @alice @ALICE") == ["alice"]


def test_extract_mentions_ignores_email():
    # An @ following a word character (e.g. `foo@bar.com`) is not a
    # mention — it's an email address.
    assert svc.extract_mentions("email foo@bar.com") == []


def test_extract_mentions_allows_at_start():
    assert svc.extract_mentions("@alice hi") == ["alice"]


def test_extract_mentions_empty_for_none_or_blank():
    assert svc.extract_mentions("") == []
    assert svc.extract_mentions("no mentions here") == []


def test_extract_mentions_handle_max_length():
    # Handles longer than the regex cap are simply truncated by the
    # regex to its allowed prefix — they're still valid tokens.
    long = "a" * 50
    out = svc.extract_mentions(f"hey @{long}")
    assert len(out) == 1
    assert out[0].startswith("a")
    assert len(out[0]) <= 32


# ── Pure service — pin limit ─────────────────────────────────────────────


def test_assert_pin_limit_under_cap_ok():
    svc.assert_pin_limit(current_pinned=0)
    svc.assert_pin_limit(current_pinned=svc.MAX_PINNED_PER_CUSTOMER - 1)


def test_assert_pin_limit_at_cap_rejects():
    with pytest.raises(ValueError, match="pin limit"):
        svc.assert_pin_limit(current_pinned=svc.MAX_PINNED_PER_CUSTOMER)


def test_assert_pin_limit_over_cap_rejects():
    with pytest.raises(ValueError):
        svc.assert_pin_limit(current_pinned=svc.MAX_PINNED_PER_CUSTOMER + 5)


def test_assert_pin_limit_rejects_negative_input():
    with pytest.raises(ValueError):
        svc.assert_pin_limit(current_pinned=-1)


# ── Migration source contract ────────────────────────────────────────────


def test_migration_chain_from_v77():
    assert 'down_revision = "a8b0c2d4e6f9"' in MIGRATION_SRC
    assert 'revision = "b9c1d3e5f7a8"' in MIGRATION_SRC


def test_migration_creates_customer_notes_table():
    assert '"customer_notes"' in MIGRATION_SRC


def test_migration_cascades_on_org_and_customer():
    # Deleting an org or a customer must drop their notes.
    assert 'ForeignKey("organizations.id", ondelete="CASCADE")' in MIGRATION_SRC
    assert 'ForeignKey("customers.id", ondelete="CASCADE")' in MIGRATION_SRC


def test_migration_has_hot_query_composite_index():
    assert "ix_customer_notes_customer_pinned_created" in MIGRATION_SRC
    # Composite index in that exact order.
    assert '["customer_id", "is_pinned", "created_at"]' in MIGRATION_SRC


def test_migration_author_user_id_bare_uuid():
    # Must not carry an FK (auth table lives in Supabase).
    lines = MIGRATION_SRC.splitlines()
    for i, line in enumerate(lines):
        if '"author_user_id"' in line:
            block = "\n".join(lines[i:i + 4])
            assert "ForeignKey" not in block
            return
    raise AssertionError("author_user_id column not found")


# ── Model source contract ────────────────────────────────────────────────


def test_model_declares_all_fields():
    for f in (
        "org_id", "customer_id", "author_user_id", "body",
        "is_pinned", "created_at", "updated_at",
    ):
        assert f in MODEL_SRC


def test_model_is_pinned_defaults_false():
    assert "default=False" in MODEL_SRC


# ── Router source contract ───────────────────────────────────────────────


def test_router_prefix_and_endpoints():
    assert 'prefix="/api/customer-notes"' in ROUTER_SRC
    for path in (
        '@router.get("", ',
        '@router.post(\n    "",',
        '@router.get("/{note_id}"',
        '@router.patch("/{note_id}"',
        '@router.delete("/{note_id}"',
        '@router.post("/{note_id}/pin"',
        '@router.post("/{note_id}/unpin"',
    ):
        assert path in ROUTER_SRC, f"missing: {path!r}"


def test_router_edit_is_author_only():
    assert "only the author may edit this note" in ROUTER_SRC


def test_router_delete_author_or_privileged():
    assert "only the author or OWNER/ADMIN may delete this note" in ROUTER_SRC
    assert "_is_privileged" in ROUTER_SRC
    assert "OrgRole.OWNER" in ROUTER_SRC and "OrgRole.ADMIN" in ROUTER_SRC


def test_router_pin_and_unpin_are_idempotent():
    # Both endpoints early-return the existing row when the bit is
    # already in the desired state, instead of raising 409.
    assert "if row.is_pinned:" in ROUTER_SRC
    assert "if not row.is_pinned:" in ROUTER_SRC


def test_router_enforces_pin_cap():
    assert "assert_pin_limit" in ROUTER_SRC
    assert "_count_pinned" in ROUTER_SRC


def test_router_pin_count_excludes_self():
    # When checking whether this specific note can be pinned, the
    # query must exclude its own id so pinning does not double-count
    # itself.
    assert "exclude_id=row.id" in ROUTER_SRC


def test_router_list_pins_bubble_to_top():
    assert "CustomerNote.is_pinned.desc()" in ROUTER_SRC
    assert "CustomerNote.created_at.desc()" in ROUTER_SRC


def test_router_tenant_scopes_every_query():
    # SQL-level org scope on list and helper count queries.
    assert "CustomerNote.org_id == member.org_id" in ROUTER_SRC
    assert "CustomerNote.org_id == org_id" in ROUTER_SRC
    # Row-level guard inside _load() for by-id fetches.
    assert "row.org_id != org_id" in ROUTER_SRC


def test_router_customer_belongs_check():
    assert "_assert_customer_belongs" in ROUTER_SRC
    assert "Customer.org_id == org_id" in ROUTER_SRC


def test_router_emits_five_audit_actions():
    for action in (
        '"customer_note.created"',
        '"customer_note.updated"',
        '"customer_note.deleted"',
        '"customer_note.pinned"',
        '"customer_note.unpinned"',
    ):
        assert action in ROUTER_SRC, f"missing audit action: {action}"
    # All must use the session-wide request=request kwarg.
    assert ROUTER_SRC.count("request=request") >= 5


def test_router_mentions_logged_on_create_and_update():
    # Both create and update audit entries carry the parsed mentions
    # so the activity feed can emit pings without re-parsing.
    assert ROUTER_SRC.count('"mentions"') >= 2


def test_router_registered_in_main():
    assert "customer_notes.router" in MAIN_SRC
    assert "customer_notes," in MAIN_SRC
