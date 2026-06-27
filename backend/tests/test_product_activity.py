"""Item 82 — Product activity timeline."""
from __future__ import annotations

import pathlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services import product_activity as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(p: str) -> str:
    return (_BACKEND_ROOT / p).read_text()


SERVICE_SRC = _read("app/services/product_activity.py")
ROUTER_SRC  = _read("app/routers/product_activity.py")
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
    ("product_note.created",         "note"),
    ("product_note.pinned",          "note"),
    ("product_tag.assigned",         "tag"),
    ("product_batch.created",        "batch"),
    ("stock_movement.recorded",      "stock"),
    ("purchase_order_item.received", "purchase_order"),
    ("pos_sale_item.sold",           "pos"),
    ("invoice_line.invoiced",        "invoice"),
    ("product.created",              "product"),
    ("random.thing",                 "other"),
])
def test_categorize_known_actions(action, cat):
    assert svc.categorize(action) == cat


# ── matches_product ─────────────────────────────────────────────────────


def test_matches_product_via_target_id():
    r = _row(
        action="product.updated",
        created_at=_NOW, target_id="prod-1",
    )
    assert svc.matches_product(r, product_id="prod-1")
    assert not svc.matches_product(r, product_id="prod-2")


def test_matches_product_via_extra_product_id():
    r = _row(
        action="product_note.created",
        created_at=_NOW,
        target_id="note-abc",
        extra={"product_id": "prod-7", "is_pinned": False},
    )
    assert svc.matches_product(r, product_id="prod-7")
    assert not svc.matches_product(r, product_id="prod-1")


def test_matches_product_rejects_unknown_action():
    r = _row(
        action="something.weird",
        created_at=_NOW,
        target_id="prod-1",
    )
    assert not svc.matches_product(r, product_id="prod-1")


def test_matches_product_casts_uuid_in_extra_to_str():
    r = _row(
        action="stock_movement.recorded",
        created_at=_NOW,
        target_id="mv-1",
        extra={"product_id": uuid.UUID("11111111-1111-1111-1111-111111111111")},
    )
    assert svc.matches_product(
        r, product_id="11111111-1111-1111-1111-111111111111",
    )


def test_matches_product_handles_missing_extra():
    r = _row(
        action="product_note.created",
        created_at=_NOW, target_id="note-1", extra=None,
    )
    assert not svc.matches_product(r, product_id="prod-1")


# ── build_timeline ──────────────────────────────────────────────────────


def test_build_empty_returns_empty():
    t = svc.build_timeline(product_id="p", rows=[], limit=10, offset=0)
    assert t.total == 0
    assert t.entries == []
    assert t.product_id == "p"


def test_build_filters_by_product_id():
    rows = [
        _row(action="product.updated", created_at=_NOW, target_id="prod-1"),
        _row(action="product.updated",
             created_at=_NOW - timedelta(minutes=1), target_id="prod-other"),
    ]
    t = svc.build_timeline(product_id="prod-1", rows=rows)
    assert t.total == 1
    assert t.entries[0].target_id == "prod-1"


def test_build_merges_target_id_and_extra_matches():
    rows = [
        _row(
            action="product.updated",
            created_at=_NOW - timedelta(minutes=3),
            target_id="prod-1",
        ),
        _row(
            action="product_note.created",
            created_at=_NOW - timedelta(minutes=2),
            target_id="note-a",
            extra={"product_id": "prod-1"},
        ),
        _row(
            action="product_tag.assigned",
            created_at=_NOW - timedelta(minutes=1),
            target_id="prod-1",
        ),
    ]
    t = svc.build_timeline(product_id="prod-1", rows=rows)
    assert t.total == 3


def test_build_sorts_newest_first():
    rows = [
        _row(action="product.updated",
             created_at=_NOW - timedelta(minutes=5), target_id="p"),
        _row(action="product.updated",
             created_at=_NOW - timedelta(minutes=1), target_id="p"),
        _row(action="product.updated",
             created_at=_NOW - timedelta(minutes=3), target_id="p"),
    ]
    t = svc.build_timeline(product_id="p", rows=rows)
    ts = [e.created_at for e in t.entries]
    assert ts == sorted(ts, reverse=True)


def test_build_tiebreak_on_id_is_deterministic():
    same = _NOW
    rows = [
        _row(action="product.updated", id_="aaa",
             created_at=same, target_id="p"),
        _row(action="product.updated", id_="bbb",
             created_at=same, target_id="p"),
        _row(action="product.updated", id_="ccc",
             created_at=same, target_id="p"),
    ]
    t1 = svc.build_timeline(product_id="p", rows=list(rows))
    t2 = svc.build_timeline(product_id="p", rows=list(reversed(rows)))
    assert [e.id for e in t1.entries] == [e.id for e in t2.entries]
    assert t1.entries[0].id == "ccc"


def test_build_paginates():
    rows = [
        _row(action="product.updated",
             created_at=_NOW - timedelta(minutes=i),
             id_=f"{i:02d}",
             target_id="p")
        for i in range(25)
    ]
    t = svc.build_timeline(product_id="p", rows=rows, limit=10, offset=0)
    assert t.total == 25
    assert len(t.entries) == 10
    first_ids = {e.id for e in t.entries}
    t2 = svc.build_timeline(product_id="p", rows=rows, limit=10, offset=10)
    second_ids = {e.id for e in t2.entries}
    assert first_ids.isdisjoint(second_ids)
    assert len(t2.entries) == 10


def test_build_offset_past_end_returns_empty_entries_but_keeps_total():
    rows = [
        _row(action="product.updated",
             created_at=_NOW - timedelta(minutes=i),
             target_id="p")
        for i in range(3)
    ]
    t = svc.build_timeline(product_id="p", rows=rows, limit=10, offset=99)
    assert t.total == 3
    assert t.entries == []


def test_build_entry_carries_category_and_extra():
    rows = [
        _row(
            action="product_note.pinned",
            created_at=_NOW,
            target_id="note-1",
            extra={"product_id": "p", "note_id": "note-1"},
        ),
    ]
    t = svc.build_timeline(product_id="p", rows=rows)
    assert t.entries[0].category == "note"
    assert t.entries[0].extra["note_id"] == "note-1"


def test_build_never_returns_none_extra():
    rows = [
        _row(action="product.updated", created_at=_NOW,
             target_id="p", extra=None),
    ]
    t = svc.build_timeline(product_id="p", rows=rows)
    assert t.entries[0].extra == {}


def test_known_actions_covers_all_feature_families():
    known = svc.known_actions()
    for a in (
        "product.updated",
        "product_note.created",
        "product_tag.assigned",
        "product_batch.created",
        "stock_movement.recorded",
        "pos_sale_item.sold",
        "invoice_line.invoiced",
    ):
        assert a in known


# ── Constants sanity ────────────────────────────────────────────────────


def test_constants_are_sane():
    assert svc.DEFAULT_PAGE_LIMIT == 50
    assert svc.MAX_PAGE_LIMIT == 200


# ── Router source contract ──────────────────────────────────────────────


def test_router_prefix_and_endpoint():
    assert 'prefix="/api/product-activity"' in ROUTER_SRC
    assert '@router.get("/{product_id}"' in ROUTER_SRC


def test_router_does_not_emit_audit_events():
    # Reading the audit log must not tail itself.
    assert "log_action" not in ROUTER_SRC


def test_router_tenant_scope_on_every_query():
    assert "row.org_id != org_id" in ROUTER_SRC
    assert "AuditLogEntry.org_id == member.org_id" in ROUTER_SRC


def test_router_404s_unknown_product():
    assert '"Product not found"' in ROUTER_SRC


def test_router_uses_pure_service():
    for name in (
        "svc_82.build_timeline",
        "svc_82.normalize_page",
        "svc_82.known_actions",
        "svc_82.AuditRow",
    ):
        assert name in ROUTER_SRC


def test_router_queries_target_id_and_extra_product_id():
    # Both the directly-targeted and the extra-referenced rows must
    # be pulled, otherwise the timeline misses half the events.
    assert "AuditLogEntry.target_id == pid_str" in ROUTER_SRC
    assert 'AuditLogEntry.extra["product_id"].astext == pid_str' in ROUTER_SRC


def test_router_has_bounded_sql_limit():
    assert "MAX_PAGE_LIMIT * 20" in ROUTER_SRC


def test_router_imports_product_from_inventory():
    assert "from app.models.inventory import Product" in ROUTER_SRC


def test_router_registered_in_main():
    assert "product_activity.router" in MAIN_SRC
    assert "product_activity," in MAIN_SRC
