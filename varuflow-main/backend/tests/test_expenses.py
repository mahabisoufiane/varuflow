"""Tests for expense tracking (Item 43, v57).

Pure + contract-style split (same as Items 28-42).

Required test names (spec):

* test_create_expense
* test_receipt_upload
* test_approval_flow
* test_rejection_flow
* test_export_csv
* test_expense_analytics_by_category
* test_mobile_receipt_capture
* test_staff_sees_own_expenses_only
* test_owner_sees_all_expenses
* test_org_isolation
"""
from __future__ import annotations

import pathlib
import uuid
from decimal import Decimal

import pytest

from app.services import expense_service as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1] / "app"


def _read(relpath: str) -> str:
    return (_BACKEND_ROOT / relpath).read_text()


ROUTER_SRC = _read("routers/expenses.py")
SERVICE_SRC = _read("services/expense_service.py")
MODEL_SRC = _read("models/expenses.py")
ANALYTICS_SRC = _read("routers/analytics.py")
MAIN_SRC = _read("main.py")
MIGRATION_SRC = (
    _BACKEND_ROOT.parent
    / "migrations"
    / "versions"
    / "d3e5f7a9b2c4_v57_expenses.py"
).read_text()


def _row(**kw) -> dict:
    base = {
        "id": uuid.uuid4(),
        "expense_date": "2026-04-01",
        "amount": Decimal("100.00"),
        "currency": "SEK",
        "description": "",
        "status": "DRAFT",
        "receipt_url": None,
        "created_by": uuid.uuid4(),
        "category_id": uuid.uuid4(),
        "category_name": "Travel",
        "category_color": "#2563eb",
        "sie_account": "5810",
    }
    base.update(kw)
    return base


# ═══════════════════════════════════════════════════════════════════
# 1. test_create_expense
# ═══════════════════════════════════════════════════════════════════


def test_create_expense():
    # Router exposes POST /api/expenses that writes an audit row.
    assert '@router.post("", response_model=ExpenseOut, status_code=201)' in ROUTER_SRC
    assert 'action="expense.created"' in ROUTER_SRC

    # Pure amount validator round-trips a positive decimal and
    # rejects zero / negative / garbage.
    assert svc.validate_amount("42.50") == Decimal("42.50")
    assert svc.validate_amount(99) == Decimal("99.00")
    with pytest.raises(ValueError):
        svc.validate_amount(0)
    with pytest.raises(ValueError):
        svc.validate_amount(-1)
    with pytest.raises(ValueError):
        svc.validate_amount("not a number")

    # Currency guard accepts ISO 4217 uppercase triplets only.
    assert svc.validate_currency("SEK") == "SEK"
    assert svc.validate_currency("USD") == "USD"
    with pytest.raises(ValueError):
        svc.validate_currency("sek")
    with pytest.raises(ValueError):
        svc.validate_currency("SE")


# ═══════════════════════════════════════════════════════════════════
# 2. test_receipt_upload
# ═══════════════════════════════════════════════════════════════════


def test_receipt_upload():
    # Allowed MIMEs pass — no raise.
    for mime in svc.ALLOWED_RECEIPT_MIMES:
        svc.validate_receipt(mime, 1024)

    # Unknown MIMEs rejected (XSS guard on SVGs / executables).
    with pytest.raises(svc.ReceiptError):
        svc.validate_receipt("image/svg+xml", 1024)
    with pytest.raises(svc.ReceiptError):
        svc.validate_receipt("application/x-msdownload", 1024)

    # Oversize rejected.
    with pytest.raises(svc.ReceiptError):
        svc.validate_receipt("image/jpeg", svc.MAX_RECEIPT_BYTES + 1)

    # Empty rejected.
    with pytest.raises(svc.ReceiptError):
        svc.validate_receipt("image/jpeg", 0)

    # None metadata is fine — the receipt can be added later.
    svc.validate_receipt(None, None)

    # Router records the final URL + metadata in a dedicated endpoint.
    assert '@router.post("/{expense_id}/receipt"' in ROUTER_SRC
    assert 'action="expense.receipt_attached"' in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 3. test_approval_flow
# ═══════════════════════════════════════════════════════════════════


def test_approval_flow():
    # DRAFT → APPROVED is the standard happy path.
    assert svc.can_transition("DRAFT", "APPROVED") is True
    assert svc.can_transition("DRAFT", "REJECTED") is True
    # Idempotent re-calls allowed.
    assert svc.can_transition("APPROVED", "APPROVED") is True
    # APPROVED is terminal from a state-machine point of view.
    assert svc.can_transition("APPROVED", "DRAFT") is False
    assert svc.can_transition("APPROVED", "REJECTED") is False

    svc.assert_transition("DRAFT", "APPROVED")
    with pytest.raises(svc.ApprovalError):
        svc.assert_transition("APPROVED", "DRAFT")

    # Router approval endpoint requires owner/admin and audits.
    assert '@router.post("/{expense_id}/approve"' in ROUTER_SRC
    assert "_require_owner_or_admin(ctx)" in ROUTER_SRC
    assert 'action="expense.approved"' in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 4. test_rejection_flow
# ═══════════════════════════════════════════════════════════════════


def test_rejection_flow():
    # REJECTED rows can be resubmitted as DRAFT — closes the loop so
    # the submitter can fix and retry.
    assert svc.can_transition("REJECTED", "DRAFT") is True
    assert svc.can_transition("REJECTED", "APPROVED") is False
    assert svc.can_transition("REJECTED", "REJECTED") is True

    # Router reject endpoint requires a note (RejectIn.note
    # min_length=1) so a reason is always on record.
    assert "class RejectIn" in ROUTER_SRC
    assert "min_length=1" in ROUTER_SRC
    assert 'action="expense.rejected"' in ROUTER_SRC

    # Resubmit endpoint flips REJECTED back to DRAFT.
    assert '@router.post("/{expense_id}/resubmit"' in ROUTER_SRC
    assert 'action="expense.resubmitted"' in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 5. test_export_csv
# ═══════════════════════════════════════════════════════════════════


def test_export_csv():
    pid = uuid.uuid4()
    rows = [
        _row(id=pid, amount=Decimal("120.00"), description="Flight",
             category_name="Travel", sie_account="5810"),
        _row(amount=Decimal("35.50"), description="Coffee",
             category_name=None, sie_account=None, category_id=None),
    ]
    body = svc.build_expenses_csv(rows)
    import csv, io
    parsed = list(csv.reader(io.StringIO(body)))
    # Header is stable — downstream accounting importers grep these
    # column names.
    assert parsed[0] == [
        "id", "expense_date", "category", "description", "amount",
        "currency", "status", "created_by", "receipt_url", "sie_account",
    ]
    assert len(parsed) == 3  # header + 2 rows
    # Missing category renders as "Uncategorised", never "None".
    assert parsed[2][2] == "Uncategorised"
    # Missing sie_account falls back to 6990.
    assert parsed[2][9] == svc.SIE_FALLBACK_ACCOUNT
    # Amount always two-decimal.
    assert parsed[1][4] == "120.00"

    # Empty export still ships the header so the importer has a schema.
    header_only = svc.build_expenses_csv([])
    assert header_only.strip().startswith("id,expense_date,category")

    # Router export endpoint is owner/admin-only and audits.
    assert '@router.get("/export.csv")' in ROUTER_SRC
    assert 'action="expense.exported"' in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 6. test_expense_analytics_by_category
# ═══════════════════════════════════════════════════════════════════


def test_expense_analytics_by_category():
    travel_id = uuid.uuid4()
    office_id = uuid.uuid4()
    rows = [
        _row(category_id=travel_id, category_name="Travel", amount=Decimal("100")),
        _row(category_id=travel_id, category_name="Travel", amount=Decimal("250")),
        _row(category_id=office_id, category_name="Office", amount=Decimal("75")),
        _row(category_id=None, category_name=None, amount=Decimal("50")),
    ]
    totals = svc.group_by_category(rows)
    by_name = {t.category_name: t for t in totals}
    assert by_name["Travel"].total == Decimal("350")
    assert by_name["Travel"].count == 2
    assert by_name["Office"].total == Decimal("75")
    assert by_name["Uncategorised"].total == Decimal("50")
    # Sorted by total descending.
    assert totals[0].category_name == "Travel"
    # Serialisation is wire-ready.
    d = totals[0].to_dict()
    assert d["total"] == "350.00"
    assert d["count"] == 2

    # Router endpoint wired.
    assert '@router.get("/analytics/by-category"' in ROUTER_SRC
    # Analytics /overview surfaces an ExpenseSummary.
    assert "ExpenseSummary" in ANALYTICS_SRC
    assert "_expense_summary" in ANALYTICS_SRC


# ═══════════════════════════════════════════════════════════════════
# 7. test_mobile_receipt_capture
# ═══════════════════════════════════════════════════════════════════


def test_mobile_receipt_capture():
    # Mobile capture uploads image/jpeg (iPhone/Android default).
    svc.validate_receipt("image/jpeg", 2_500_000)
    svc.validate_receipt("image/heic", 3_000_000)   # iPhone native
    svc.validate_receipt("image/webp", 1_500_000)   # Android Chrome

    # Router comment locks in the capture flow (phone → S3 → attach).
    assert "Mobile receipt capture flow" in ROUTER_SRC
    # Allow-list locks in the mobile MIMEs we support.
    assert "image/jpeg" in SERVICE_SRC
    assert "image/heic" in SERVICE_SRC
    assert "image/webp" in SERVICE_SRC


# ═══════════════════════════════════════════════════════════════════
# 8. test_staff_sees_own_expenses_only
# ═══════════════════════════════════════════════════════════════════


def test_staff_sees_own_expenses_only():
    # List endpoint scopes by creator for MEMBER role.
    assert "def _scope_to_member" in ROUTER_SRC
    assert "m.role == OrgRole.MEMBER" in ROUTER_SRC
    assert "Expense.created_by == actor" in ROUTER_SRC
    # Detail + update + delete all guard on created_by for MEMBERs.
    # Count the 404-on-foreign-rows guards — get/patch/delete/resubmit/receipt.
    assert ROUTER_SRC.count("row.created_by != _actor(ctx)") >= 5


# ═══════════════════════════════════════════════════════════════════
# 9. test_owner_sees_all_expenses
# ═══════════════════════════════════════════════════════════════════


def test_owner_sees_all_expenses():
    # Scope helper branches only on MEMBER — owners/admins fall through.
    assert "if m.role == OrgRole.MEMBER:" in ROUTER_SRC
    # Owner/admin-only endpoints are explicitly gated.
    assert ROUTER_SRC.count("_require_owner_or_admin(ctx)") >= 5
    # Approve + reject + export + category CRUD require owner/admin.
    for sym in (
        "def approve_expense",
        "def reject_expense",
        "def export_csv",
        "def create_category",
        "def update_category",
        "def delete_category",
    ):
        assert sym in ROUTER_SRC


# ═══════════════════════════════════════════════════════════════════
# 10. test_org_isolation
# ═══════════════════════════════════════════════════════════════════


def test_org_isolation():
    # Every loader filters by org_id.
    assert "Expense.org_id == org_id" in ROUTER_SRC
    assert "ExpenseCategory.org_id == org_id" in ROUTER_SRC
    # 404 is the cross-tenant response (no leak via 403 vs 404 timing).
    assert 'detail="expense_not_found"' in ROUTER_SRC
    assert 'detail="category_not_found"' in ROUTER_SRC
    # FKs cascade on org deletion so no orphan expenses linger.
    assert 'ondelete="CASCADE"' in MIGRATION_SRC


# ═══════════════════════════════════════════════════════════════════
# Additional invariants
# ═══════════════════════════════════════════════════════════════════


def test_router_registered_in_main():
    assert "expenses," in MAIN_SRC
    assert "expenses.router" in MAIN_SRC


def test_migration_v57_chains_from_v56():
    assert 'down_revision = "c2d4e6f8a1b3"' in MIGRATION_SRC
    assert 'revision = "d3e5f7a9b2c4"' in MIGRATION_SRC


def test_default_categories_seed_covers_swedish_sie_accounts():
    seeds = dict((name, (color, sie, is_default))
                 for name, color, sie, is_default in svc.DEFAULT_CATEGORY_SEEDS)
    # Swedish SMB accounting account ranges.
    assert seeds["Travel"][1] == "5810"
    assert seeds["Office"][1] == "6110"
    assert seeds["Meals"][1] == "5831"
    assert seeds["Software"][1] == "6540"
    # Exactly one seed is the default (matches the partial unique
    # index constraint in v57).
    assert sum(1 for _, _, _, d in svc.DEFAULT_CATEGORY_SEEDS if d) == 1
    assert seeds["Other"][2] is True


def test_approved_row_is_locked_for_edit():
    # PATCH endpoint blocks edits on APPROVED rows. The review /
    # resubmit flow handles corrections — once approved, the row
    # is part of the accounting record.
    assert 'detail="expense_locked"' in ROUTER_SRC


def test_partial_unique_index_for_default_category():
    # At most one default category per org — enforced in SQL.
    assert "ux_expense_categories_one_default" in MIGRATION_SRC
    assert "is_default = true" in MIGRATION_SRC


def test_pending_approval_partial_index_speeds_review_queue():
    # Review queue is served by a partial index so even a tenant
    # with years of history renders the queue in O(pending), not
    # O(all).
    assert "ix_expenses_pending_approval" in MIGRATION_SRC
    assert "status = 'DRAFT'" in MIGRATION_SRC


def test_sie_account_fallback():
    # An expense without a category_sie_account falls back to 6990.
    assert svc.sie_account_for({"sie_account": None}) == "6990"
    assert svc.sie_account_for({"sie_account": ""}) == "6990"
    assert svc.sie_account_for({"sie_account": "5810"}) == "5810"


def test_create_default_categories_is_idempotent():
    # Source-text: the DB helper returns existing rows if any are
    # already present, otherwise it seeds the defaults.
    assert "if existing:" in SERVICE_SRC
    assert "return list(existing)" in SERVICE_SRC
