"""Item 96 — Expense activity timeline."""
from __future__ import annotations

import pathlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services import expense_activity as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(p: str) -> str:
    _p = _BACKEND_ROOT / p
    if _p.is_file():
        return _p.read_text()
    # Path was split into a feature package (e.g. routers/invoicing/);
    # concatenate its modules so source-string assertions still hold.
    _pkg = _p.with_suffix("")
    if _pkg.is_dir():
        return "".join(_f.read_text() for _f in sorted(_pkg.rglob("*.py")))
    return _p.read_text()


SERVICE_SRC = _read("app/services/expense_activity.py")
ROUTER_SRC  = _read("app/features/expenses/expense_activity.py")
MAIN_SRC    = _read("app/main.py")


_NOW = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)


def _row(
    *,
    action: str,
    created_at: datetime,
    id_: str | None = None,
    target_id: str | None = None,
    extra: dict | None = None,
    target_type: str | None = None,
    actor_user_id: str | None = "user-1",
) -> svc.AuditRow:
    return svc.AuditRow(
        id=id_ or str(uuid.uuid4()),
        action=action,
        actor_user_id=actor_user_id,
        target_type=target_type,
        target_id=target_id,
        extra=extra,
        created_at=created_at,
    )


# ── normalize_page ──────────────────────────────────────────────────────


def test_normalize_page_defaults():
    l, o = svc.normalize_page(limit=None, offset=None)
    assert l == svc.DEFAULT_PAGE_LIMIT
    assert o == 0


def test_normalize_page_respects_limit():
    l, _ = svc.normalize_page(limit=25, offset=0)
    assert l == 25


def test_normalize_page_caps_limit():
    l, _ = svc.normalize_page(limit=10_000, offset=0)
    assert l == svc.MAX_PAGE_LIMIT


def test_normalize_page_rejects_zero_limit():
    with pytest.raises(ValueError):
        svc.normalize_page(limit=0, offset=0)


def test_normalize_page_rejects_negative_offset():
    with pytest.raises(ValueError):
        svc.normalize_page(limit=10, offset=-1)


def test_normalize_page_rejects_non_int():
    with pytest.raises(ValueError):
        svc.normalize_page(limit="ten", offset=0)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        svc.normalize_page(limit=10, offset="zero")  # type: ignore[arg-type]


# ── categorize ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("action, cat", [
    ("expense_note.created",     "note"),
    ("expense_note.pinned",      "note"),
    ("expense_tag.assigned",     "tag"),
    ("expense_tag.unassigned",   "tag"),
    ("expense.created",          "expense"),
    ("expense.approved",         "expense"),
    ("random.thing",             "other"),
])
def test_categorize_known_actions(action, cat):
    assert svc.categorize(action) == cat


# ── matches_expense ─────────────────────────────────────────────────────


def test_matches_expense_via_target_id():
    r = _row(action="expense.updated", created_at=_NOW, target_id="exp-1")
    assert svc.matches_expense(r, expense_id="exp-1")
    assert not svc.matches_expense(r, expense_id="exp-2")


def test_matches_expense_via_extra_expense_id():
    r = _row(
        action="expense_note.created",
        created_at=_NOW,
        target_id="note-abc",
        extra={"expense_id": "exp-7", "pinned": False},
    )
    assert svc.matches_expense(r, expense_id="exp-7")
    assert not svc.matches_expense(r, expense_id="exp-1")


def test_matches_expense_rejects_unknown_action():
    r = _row(action="something.weird", created_at=_NOW, target_id="exp-1")
    assert not svc.matches_expense(r, expense_id="exp-1")


def test_matches_expense_casts_uuid_in_extra_to_str():
    r = _row(
        action="expense_note.pinned",
        created_at=_NOW,
        target_id="note-1",
        extra={"expense_id": uuid.UUID("11111111-1111-1111-1111-111111111111")},
    )
    assert svc.matches_expense(
        r, expense_id="11111111-1111-1111-1111-111111111111",
    )


def test_matches_expense_handles_missing_extra():
    r = _row(
        action="expense_note.created",
        created_at=_NOW, target_id="note-1", extra=None,
    )
    assert not svc.matches_expense(r, expense_id="exp-1")


def test_matches_expense_tag_actions_use_target_id():
    # expense_tag.assigned/unassigned target the expense directly.
    r = _row(
        action="expense_tag.assigned",
        created_at=_NOW, target_id="exp-5",
        extra={"tag_id": "tag-1"},
    )
    assert svc.matches_expense(r, expense_id="exp-5")


# ── build_timeline ──────────────────────────────────────────────────────


def test_build_empty_returns_empty():
    t = svc.build_timeline(expense_id="e", rows=[], limit=10, offset=0)
    assert t.total == 0
    assert t.entries == []
    assert t.expense_id == "e"


def test_build_filters_by_expense_id():
    rows = [
        _row(action="expense.updated", created_at=_NOW, target_id="exp-1"),
        _row(action="expense.updated",
             created_at=_NOW - timedelta(minutes=1), target_id="exp-other"),
    ]
    t = svc.build_timeline(expense_id="exp-1", rows=rows)
    assert t.total == 1
    assert t.entries[0].target_id == "exp-1"


def test_build_merges_target_id_and_extra_matches():
    rows = [
        _row(action="expense.updated",
             created_at=_NOW - timedelta(minutes=3), target_id="exp-1"),
        _row(
            action="expense_note.created",
            created_at=_NOW - timedelta(minutes=2),
            target_id="note-a",
            extra={"expense_id": "exp-1"},
        ),
        _row(action="expense_tag.assigned",
             created_at=_NOW - timedelta(minutes=1), target_id="exp-1"),
    ]
    t = svc.build_timeline(expense_id="exp-1", rows=rows)
    assert t.total == 3


def test_build_sorts_newest_first():
    rows = [
        _row(action="expense.updated",
             created_at=_NOW - timedelta(minutes=5), target_id="e"),
        _row(action="expense.updated",
             created_at=_NOW - timedelta(minutes=1), target_id="e"),
        _row(action="expense.updated",
             created_at=_NOW - timedelta(minutes=3), target_id="e"),
    ]
    t = svc.build_timeline(expense_id="e", rows=rows)
    ts = [e.created_at for e in t.entries]
    assert ts == sorted(ts, reverse=True)


def test_build_tiebreak_on_id_is_deterministic():
    same = _NOW
    rows = [
        _row(action="expense.updated", id_="aaa",
             created_at=same, target_id="e"),
        _row(action="expense.updated", id_="bbb",
             created_at=same, target_id="e"),
        _row(action="expense.updated", id_="ccc",
             created_at=same, target_id="e"),
    ]
    t1 = svc.build_timeline(expense_id="e", rows=list(rows))
    t2 = svc.build_timeline(expense_id="e", rows=list(reversed(rows)))
    assert [e.id for e in t1.entries] == [e.id for e in t2.entries]
    assert t1.entries[0].id == "ccc"


def test_build_paginates():
    rows = [
        _row(action="expense.updated",
             created_at=_NOW - timedelta(minutes=i),
             id_=f"{i:02d}",
             target_id="e")
        for i in range(25)
    ]
    t = svc.build_timeline(expense_id="e", rows=rows, limit=10, offset=0)
    assert t.total == 25
    assert len(t.entries) == 10
    first_ids = {e.id for e in t.entries}
    t2 = svc.build_timeline(expense_id="e", rows=rows, limit=10, offset=10)
    second_ids = {e.id for e in t2.entries}
    assert first_ids.isdisjoint(second_ids)
    assert len(t2.entries) == 10


def test_build_offset_past_end_returns_empty_entries_but_keeps_total():
    rows = [
        _row(action="expense.updated",
             created_at=_NOW - timedelta(minutes=i),
             target_id="e")
        for i in range(3)
    ]
    t = svc.build_timeline(expense_id="e", rows=rows, limit=10, offset=99)
    assert t.total == 3
    assert t.entries == []


def test_build_entry_carries_category_and_extra():
    rows = [
        _row(
            action="expense_note.pinned",
            created_at=_NOW,
            target_id="note-1",
            extra={"expense_id": "e", "note_id": "note-1"},
        ),
    ]
    t = svc.build_timeline(expense_id="e", rows=rows)
    assert t.entries[0].category == "note"
    assert t.entries[0].extra["note_id"] == "note-1"


def test_build_never_returns_none_extra():
    rows = [
        _row(action="expense.updated", created_at=_NOW,
             target_id="e", extra=None),
    ]
    t = svc.build_timeline(expense_id="e", rows=rows)
    assert t.entries[0].extra == {}


def test_known_actions_covers_all_feature_families():
    known = svc.known_actions()
    for a in (
        "expense.updated",
        "expense.approved",
        "expense_note.created",
        "expense_tag.assigned",
        "expense_tag.unassigned",
    ):
        assert a in known


# ── Constants sanity ────────────────────────────────────────────────────


def test_constants_are_sane():
    assert svc.DEFAULT_PAGE_LIMIT == 50
    assert svc.MAX_PAGE_LIMIT == 200


# ── Router source contract ──────────────────────────────────────────────


def test_router_prefix_and_endpoint():
    assert 'prefix="/api/expense-activity"' in ROUTER_SRC
    assert '@router.get("/{expense_id}"' in ROUTER_SRC


def test_router_does_not_emit_audit_events():
    # Reading the audit log must not tail itself.
    assert "log_action" not in ROUTER_SRC


def test_router_tenant_scope_on_every_query():
    assert "row.org_id != org_id" in ROUTER_SRC
    assert "AuditLogEntry.org_id == member.org_id" in ROUTER_SRC


def test_router_404s_unknown_expense():
    assert '"Expense not found"' in ROUTER_SRC


def test_router_uses_pure_service():
    for name in (
        "svc_96.build_timeline",
        "svc_96.normalize_page",
        "svc_96.known_actions",
        "svc_96.AuditRow",
    ):
        assert name in ROUTER_SRC


def test_router_queries_target_id_and_extra_expense_id():
    assert "AuditLogEntry.target_id == eid_str" in ROUTER_SRC
    assert 'AuditLogEntry.extra["expense_id"].astext == eid_str' in ROUTER_SRC


def test_router_has_bounded_sql_limit():
    assert "MAX_PAGE_LIMIT * 20" in ROUTER_SRC


def test_router_imports_expense_from_expenses_module():
    assert "from app.features.expenses.models import Expense" in ROUTER_SRC


def test_router_registered_in_main():

    # Registered via expenses_router (vertical-slice architecture).
    # The individual module is wired inside the feature router, not directly in main.py.
    feat_src = _read("app/features/expenses/router.py")
    assert "expense_activity" in feat_src
    assert "expenses_router" in MAIN_SRC
