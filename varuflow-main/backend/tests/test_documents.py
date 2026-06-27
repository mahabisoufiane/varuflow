"""Tests for document storage (Item 44, v58).

Pure + contract-style split, same pattern as Items 28-43.

Required test names (spec):

* test_upload_document
* test_categorize_document
* test_expiry_alert
* test_search_by_tag
* test_link_to_supplier
* test_team_share
* test_gdpr_deletion
* test_file_size_limit
* test_org_isolation
* test_audit_log_on_upload_and_delete
"""
from __future__ import annotations

import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from app.services import document_service as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"


def _read(relpath: str) -> str:
    _p = _BACKEND_ROOT / relpath
    if _p.is_file():
        return _p.read_text()
    # Path was split into a feature package (e.g. routers/invoicing/);
    # concatenate its modules so source-string assertions still hold.
    _pkg = _p.with_suffix("")
    if _pkg.is_dir():
        return "".join(_f.read_text() for _f in sorted(_pkg.rglob("*.py")))
    return _p.read_text()


ROUTER_SRC = _read("features/projects/documents.py")
SERVICE_SRC = _read("services/document_service.py")
MODEL_SRC = _read("features/projects/documents_models.py")
MAIN_SRC = _read("main.py")
GDPR_SRC = _read("features/compliance/gdpr.py")
MIGRATION_SRC = (
    _BACKEND_ROOT.parent
    / "migrations"
    / "versions"
    / "e4f6a8b1c3d5_v58_documents.py"
).read_text()


# ═══════════════════════════════════════════════════════════════════
# 1. test_upload_document
# ═══════════════════════════════════════════════════════════════════


def test_upload_document():
    # Router exposes POST /api/documents with a 201 status code.
    assert '@router.post("", response_model=DocumentOut, status_code=201)' in ROUTER_SRC
    assert "async def create_document" in ROUTER_SRC
    # Router validates MIME / size via pydantic field validators.
    assert "svc.validate_mime" in ROUTER_SRC
    assert "svc.validate_size" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 2. test_categorize_document
# ═══════════════════════════════════════════════════════════════════


def test_categorize_document():
    # Allow-list round-trips.
    for cat in svc.ALLOWED_CATEGORIES:
        assert svc.validate_category(cat) == cat
    # Unknown → "other" (not an exception — so legacy rows keep working
    # when a category name is renamed upstream).
    assert svc.validate_category("unknown-thing") == "other"
    assert svc.validate_category(None) == "other"  # type: ignore[arg-type]
    # Stored as String(60) in the model — not a PG ENUM.
    assert "String(60)" in MODEL_SRC
    # Category filter exposed on the list endpoint.
    assert "svc.validate_category(category)" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 3. test_expiry_alert
# ═══════════════════════════════════════════════════════════════════


def test_expiry_alert():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # No expiry → never alerts.
    st = svc.expiry_status(None, now=now)
    assert st.alert is False and st.expired is False and st.days_until is None
    # Within window → alert.
    soon = now + timedelta(days=10)
    st = svc.expiry_status(soon, now=now)
    assert st.alert is True and st.expired is False and st.days_until == 10
    # Already expired.
    st = svc.expiry_status(now - timedelta(days=1), now=now)
    assert st.alert is True and st.expired is True
    # Far out.
    st = svc.expiry_status(now + timedelta(days=365), now=now)
    assert st.alert is False and st.expired is False
    # Naive datetime is normalised to UTC (no TypeError on subtract).
    naive = datetime(2026, 6, 1)
    svc.expiry_status(naive, now=now)
    # Dedicated /expiring endpoint wired.
    assert '@router.get("/expiring")' in ROUTER_SRC
    assert "EXPIRY_ALERT_DAYS" in SERVICE_SRC


# ═══════════════════════════════════════════════════════════════════
# 4. test_search_by_tag
# ═══════════════════════════════════════════════════════════════════


def test_search_by_tag():
    # Pure containment matcher.
    assert svc.matches_tag_query(["legal", "2026"], ["legal"]) is True
    assert svc.matches_tag_query(["legal"], ["legal", "2026"]) is False
    assert svc.matches_tag_query([], ["anything"]) is False
    assert svc.matches_tag_query(["X"], []) is True  # no filter → match
    # Tag normalisation: strip / lowercase / dedupe / cap.
    assert svc.normalise_tags([" Legal ", "legal", "2026"]) == ["legal", "2026"]
    assert len(svc.normalise_tags(["t%d" % i for i in range(50)])) == svc.MAX_TAGS
    # Router accepts tag filter and uses array contains.
    assert "tag: list[str] | None = Query" in ROUTER_SRC
    assert "Document.tags.contains(tags)" in ROUTER_SRC
    # Migration creates a GIN index on tags[] so @> is index-friendly.
    assert "ix_documents_tags_gin" in MIGRATION_SRC
    assert 'postgresql_using="gin"' in MIGRATION_SRC


# ═══════════════════════════════════════════════════════════════════
# 5. test_link_to_supplier
# ═══════════════════════════════════════════════════════════════════


def test_link_to_supplier():
    # Whitelist enforces the polymorphic type at the validator layer.
    assert svc.validate_linked_type("supplier") == "supplier"
    assert svc.validate_linked_type("customer") == "customer"
    assert svc.validate_linked_type("product") == "product"
    assert svc.validate_linked_type(None) is None
    with pytest.raises(svc.DocumentValidationError):
        svc.validate_linked_type("drop_table")
    # Router exposes the linked-entity list endpoint.
    assert '@router.get("/linked/{linked_type}/{linked_id}"' in ROUTER_SRC
    # Model carries the polymorphic columns.
    assert "linked_type" in MODEL_SRC and "linked_id" in MODEL_SRC
    # Migration indexes the polymorphic lookup via partial index.
    assert "ix_documents_linked" in MIGRATION_SRC


# ═══════════════════════════════════════════════════════════════════
# 6. test_team_share
# ═══════════════════════════════════════════════════════════════════


def test_team_share():
    # is_shared bool on the row defaults to True.
    assert "is_shared" in MODEL_SRC
    assert 'is_shared: bool = True' in ROUTER_SRC or "is_shared=True" in ROUTER_SRC
    # Visibility rule: private docs gated behind uploader or owner/admin.
    assert "def _can_view" in ROUTER_SRC
    assert "OrgRole.OWNER" in ROUTER_SRC and "OrgRole.ADMIN" in ROUTER_SRC
    assert "row.uploaded_by == _actor(ctx)" in ROUTER_SRC
    # MEMBER list query filters to shared+own.
    assert "Document.is_shared == True" in ROUTER_SRC
    assert "Document.uploaded_by == actor" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 7. test_gdpr_deletion
# ═══════════════════════════════════════════════════════════════════


def test_gdpr_deletion():
    # Service exposes a dedicated purge helper returning the row count.
    assert "async def gdpr_purge_documents" in SERVICE_SRC
    # True hard delete — not masked / anonymised (documents carry no
    # BFL retention obligation, unlike invoices).
    assert "delete(Document).where(Document.org_id == org_id)" in SERVICE_SRC
    # GDPR erasure flow calls the purge and reports the count.
    assert "gdpr_purge_documents" in GDPR_SRC
    assert '"documents_purged"' in GDPR_SRC


# ═══════════════════════════════════════════════════════════════════
# 8. test_file_size_limit
# ═══════════════════════════════════════════════════════════════════


def test_file_size_limit():
    assert svc.MAX_FILE_BYTES == 25 * 1024 * 1024
    # Empty / negative rejected.
    with pytest.raises(svc.DocumentValidationError):
        svc.validate_size(0)
    with pytest.raises(svc.DocumentValidationError):
        svc.validate_size(-1)
    # Over-the-limit rejected.
    with pytest.raises(svc.DocumentValidationError):
        svc.validate_size(svc.MAX_FILE_BYTES + 1)
    # At-the-limit accepted.
    assert svc.validate_size(svc.MAX_FILE_BYTES) == svc.MAX_FILE_BYTES
    # MIME allow-list rejects SVGs and executables (same XSS stance
    # as the Item 43 receipt uploader).
    with pytest.raises(svc.DocumentValidationError):
        svc.validate_mime("image/svg+xml")
    with pytest.raises(svc.DocumentValidationError):
        svc.validate_mime("application/x-msdownload")
    assert svc.validate_mime("application/pdf") == "application/pdf"


# ═══════════════════════════════════════════════════════════════════
# 9. test_org_isolation
# ═══════════════════════════════════════════════════════════════════


def test_org_isolation():
    # Every list query is filtered by org_id — no bare Document selects.
    for needle in (
        "Document.org_id == org_id",
        "await _load(db, doc_id=doc_id, org_id=org_id)",
    ):
        assert needle in ROUTER_SRC, f"router missing org scoping: {needle}"
    # Loader itself enforces the composite (id, org_id) predicate.
    assert "Document.id == doc_id, Document.org_id == org_id" in ROUTER_SRC
    # Model uses ondelete=CASCADE so the org cascade cleans up
    # if the GDPR path is ever bypassed.
    assert 'ondelete="CASCADE"' in MODEL_SRC


# ═══════════════════════════════════════════════════════════════════
# 10. test_audit_log_on_upload_and_delete
# ═══════════════════════════════════════════════════════════════════


def test_audit_log_on_upload_and_delete():
    for action in (
        '"document.uploaded"',
        '"document.updated"',
        '"document.deleted"',
    ):
        assert f"action={action}" in ROUTER_SRC, f"missing audit action {action}"
    # Each mutation calls log_action with the target id.
    assert ROUTER_SRC.count("await log_action(") >= 3
    assert "from app.services.audit import log_action" in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# Invariants / smoke
# ═══════════════════════════════════════════════════════════════════


def test_router_registered_in_main():

    # Registered via projects_router (vertical-slice architecture).
    # The individual module is wired inside the feature router, not directly in main.py.
    feat_src = _read("features/projects/router.py")
    assert "documents" in feat_src
    assert "projects_router" in MAIN_SRC


def test_migration_v58_chains_from_v57():
    assert 'revision = "e4f6a8b1c3d5"' in MIGRATION_SRC
    assert 'down_revision = "d3e5f7a9b2c4"' in MIGRATION_SRC


def test_migration_creates_expected_indexes():
    for idx in (
        "ix_documents_org",
        "ix_documents_org_category",
        "ix_documents_expires",
        "ix_documents_tags_gin",
        "ix_documents_linked",
    ):
        assert idx in MIGRATION_SRC


def test_service_constants_exposed():
    assert svc.MAX_TAGS == 20
    assert svc.EXPIRY_ALERT_DAYS == 30
    assert "contract" in svc.ALLOWED_CATEGORIES
    assert "application/pdf" in svc.ALLOWED_MIME_TYPES
    assert "supplier" in svc.ALLOWED_LINKED_TYPES
