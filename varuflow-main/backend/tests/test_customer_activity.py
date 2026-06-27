"""Item 75 — Customer activity timeline."""
from __future__ import annotations

import pathlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services import customer_activity as svc


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


SERVICE_SRC = _read("app/services/customer_activity.py")
ROUTER_SRC  = _read("app/features/customers/customer_activity.py")
MAIN_SRC    = _read("app/main.py")


# ── helpers ──────────────────────────────────────────────────────────────


_NOW = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)


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
    ("customer_note.created",      "note"),
    ("customer_note.pinned",       "note"),
    ("customer_contact.promoted",  "contact"),
    ("customer_tag.assigned",      "tag"),
    ("customer_statement.viewed",  "statement"),
    ("customer.created",           "customer"),
    ("credit_note.issued",         "credit_note"),
    ("invoice.sent",               "invoice"),
    ("payment.recorded",           "payment"),
    ("random.thing",               "other"),
])
def test_categorize_known_actions(action, cat):
    assert svc.categorize(action) == cat


# ── matches_customer ────────────────────────────────────────────────────


def test_matches_customer_via_target_id():
    r = _row(
        action="customer.updated",
        created_at=_NOW, target_id="cust-1",
    )
    assert svc.matches_customer(r, customer_id="cust-1")
    assert not svc.matches_customer(r, customer_id="cust-2")


def test_matches_customer_via_extra_customer_id():
    r = _row(
        action="customer_note.created",
        created_at=_NOW,
        target_id="note-abc",
        extra={"customer_id": "cust-7", "is_pinned": False},
    )
    assert svc.matches_customer(r, customer_id="cust-7")
    assert not svc.matches_customer(r, customer_id="cust-1")


def test_matches_customer_rejects_unknown_action():
    r = _row(
        action="something.weird",
        created_at=_NOW,
        target_id="cust-1",
    )
    assert not svc.matches_customer(r, customer_id="cust-1")


def test_matches_customer_casts_uuid_in_extra_to_str():
    # The dispatcher sometimes stashes UUID objects (pre-serialize)
    # into ``extra``. ``matches_customer`` must tolerate that.
    r = _row(
        action="invoice.created",
        created_at=_NOW,
        target_id="inv-1",
        extra={"customer_id": uuid.UUID("11111111-1111-1111-1111-111111111111")},
    )
    assert svc.matches_customer(
        r, customer_id="11111111-1111-1111-1111-111111111111",
    )


def test_matches_customer_handles_missing_extra():
    r = _row(
        action="customer_note.created",
        created_at=_NOW, target_id="note-1", extra=None,
    )
    assert not svc.matches_customer(r, customer_id="cust-1")


# ── build_timeline ──────────────────────────────────────────────────────


def test_build_empty_returns_empty():
    t = svc.build_timeline(customer_id="c", rows=[], limit=10, offset=0)
    assert t.total == 0
    assert t.entries == []
    assert t.customer_id == "c"


def test_build_filters_by_customer_id():
    rows = [
        _row(action="customer.updated", created_at=_NOW, target_id="cust-1"),
        _row(action="customer.updated",
             created_at=_NOW - timedelta(minutes=1), target_id="cust-other"),
    ]
    t = svc.build_timeline(customer_id="cust-1", rows=rows)
    assert t.total == 1
    assert t.entries[0].target_id == "cust-1"


def test_build_merges_target_id_and_extra_matches():
    rows = [
        _row(
            action="customer.updated",
            created_at=_NOW - timedelta(minutes=3),
            target_id="cust-1",
        ),
        _row(
            action="customer_note.created",
            created_at=_NOW - timedelta(minutes=2),
            target_id="note-a",
            extra={"customer_id": "cust-1"},
        ),
        _row(
            action="customer_tag.assigned",
            created_at=_NOW - timedelta(minutes=1),
            target_id="cust-1",
        ),
    ]
    t = svc.build_timeline(customer_id="cust-1", rows=rows)
    assert t.total == 3


def test_build_sorts_newest_first():
    rows = [
        _row(action="customer.updated",
             created_at=_NOW - timedelta(minutes=5), target_id="c"),
        _row(action="customer.updated",
             created_at=_NOW - timedelta(minutes=1), target_id="c"),
        _row(action="customer.updated",
             created_at=_NOW - timedelta(minutes=3), target_id="c"),
    ]
    t = svc.build_timeline(customer_id="c", rows=rows)
    ts = [e.created_at for e in t.entries]
    assert ts == sorted(ts, reverse=True)


def test_build_tiebreak_on_id_is_deterministic():
    same = _NOW
    rows = [
        _row(action="customer.updated", id_="aaa",
             created_at=same, target_id="c"),
        _row(action="customer.updated", id_="bbb",
             created_at=same, target_id="c"),
        _row(action="customer.updated", id_="ccc",
             created_at=same, target_id="c"),
    ]
    t1 = svc.build_timeline(customer_id="c", rows=list(rows))
    t2 = svc.build_timeline(customer_id="c", rows=list(reversed(rows)))
    assert [e.id for e in t1.entries] == [e.id for e in t2.entries]
    # Highest id first on a tie (reverse=True over str compare).
    assert t1.entries[0].id == "ccc"


def test_build_paginates():
    rows = [
        _row(action="customer.updated",
             created_at=_NOW - timedelta(minutes=i),
             id_=f"{i:02d}",
             target_id="c")
        for i in range(25)
    ]
    t = svc.build_timeline(customer_id="c", rows=rows, limit=10, offset=0)
    assert t.total == 25
    assert len(t.entries) == 10
    # Next page picks up where the last left off without overlap.
    first_ids = {e.id for e in t.entries}
    t2 = svc.build_timeline(customer_id="c", rows=rows, limit=10, offset=10)
    second_ids = {e.id for e in t2.entries}
    assert first_ids.isdisjoint(second_ids)
    assert len(t2.entries) == 10


def test_build_offset_past_end_returns_empty_entries_but_keeps_total():
    rows = [
        _row(action="customer.updated",
             created_at=_NOW - timedelta(minutes=i),
             target_id="c")
        for i in range(3)
    ]
    t = svc.build_timeline(customer_id="c", rows=rows, limit=10, offset=99)
    assert t.total == 3
    assert t.entries == []


def test_build_entry_carries_category_and_extra():
    rows = [
        _row(
            action="customer_note.pinned",
            created_at=_NOW,
            target_id="note-1",
            extra={"customer_id": "c", "note_id": "note-1"},
        ),
    ]
    t = svc.build_timeline(customer_id="c", rows=rows)
    assert t.entries[0].category == "note"
    assert t.entries[0].extra["note_id"] == "note-1"


def test_build_never_returns_none_extra():
    rows = [
        _row(action="customer.updated", created_at=_NOW,
             target_id="c", extra=None),
    ]
    t = svc.build_timeline(customer_id="c", rows=rows)
    assert t.entries[0].extra == {}


def test_known_actions_covers_all_feature_families():
    known = svc.known_actions()
    for a in (
        "customer.updated",
        "customer_note.created",
        "customer_tag.assigned",
        "customer_contact.promoted",
        "customer_statement.viewed",
        "credit_note.issued",
        "invoice.sent",
        "payment.recorded",
    ):
        assert a in known


# ── Constants sanity ────────────────────────────────────────────────────


def test_constants_are_sane():
    assert svc.DEFAULT_PAGE_LIMIT == 50
    assert svc.MAX_PAGE_LIMIT == 200


# ── Router source contract ──────────────────────────────────────────────


def test_router_prefix_and_endpoint():
    assert 'prefix="/api/customer-activity"' in ROUTER_SRC
    assert '@router.get("/{customer_id}"' in ROUTER_SRC


def test_router_does_not_emit_audit_events():
    # Reading the audit log must not tail itself — otherwise any
    # drive-by timeline view would inflate the log and keep itself
    # from ever draining.
    assert "log_action" not in ROUTER_SRC


def test_router_tenant_scope_on_every_query():
    # Customer-belongs guard + audit_log scope.
    assert "row.org_id != org_id" in ROUTER_SRC
    assert "AuditLogEntry.org_id == member.org_id" in ROUTER_SRC


def test_router_404s_unknown_customer():
    assert '"Customer not found"' in ROUTER_SRC


def test_router_uses_pure_service():
    for name in (
        "svc_75.build_timeline",
        "svc_75.normalize_page",
        "svc_75.known_actions",
        "svc_75.AuditRow",
    ):
        assert name in ROUTER_SRC


def test_router_queries_target_id_and_extra_customer_id():
    # Both the directly-targeted and the extra-referenced rows must
    # be pulled, otherwise the timeline misses half the events.
    assert "AuditLogEntry.target_id == cid_str" in ROUTER_SRC
    assert 'AuditLogEntry.extra["customer_id"].astext == cid_str' in ROUTER_SRC


def test_router_has_bounded_sql_limit():
    # Hard upper bound so the feed never runaway-loads audit history.
    assert "MAX_PAGE_LIMIT * 20" in ROUTER_SRC


def test_router_registered_in_main():

    # Registered via customers_router (vertical-slice architecture).
    # The individual module is wired inside the feature router, not directly in main.py.
    feat_src = _read("app/features/customers/router.py")
    assert "customer_activity" in feat_src
    assert "customers_router" in MAIN_SRC
