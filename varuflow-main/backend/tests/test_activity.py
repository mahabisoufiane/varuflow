"""Item 62 — Activity feed."""
from __future__ import annotations

import pathlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.services import activity as svc


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


MIGRATION_SRC = _read("migrations/versions/a2b4c6d8e0f2_v71_activity_feed.py")
MODEL_SRC = _read("app/models/activity_event.py")
SERVICE_SRC = _read("app/services/activity.py")
ROUTER_SRC = _read("app/routers/activity.py")
MAIN_SRC = _read("app/main.py")


# ── Pure service: action ──────────────────────────────────────────────────


def test_validate_action_accepts_dotted_snake():
    for ok in (
        "invoice.sent",
        "customer.created",
        "appointment.checked_in",
        "note.added",
        "invoice.payment.received",
    ):
        assert svc.validate_action(ok) == ok


def test_validate_action_rejects_bad_shapes():
    for bad in (
        "",
        "Invoice.Sent",
        "invoice",
        "invoice.",
        ".sent",
        "invoice..sent",
        "invoice-sent",
        "a.b.c.d.e",
        "1invoice.sent",
    ):
        with pytest.raises(ValueError):
            svc.validate_action(bad)


def test_validate_action_rejects_non_string():
    with pytest.raises(ValueError):
        svc.validate_action(None)  # type: ignore[arg-type]


def test_validate_action_length_capped():
    long = "a." + ("b" * svc.MAX_ACTION_LENGTH)
    with pytest.raises(ValueError):
        svc.validate_action(long)


# ── Pure service: entity_type ─────────────────────────────────────────────


def test_validate_entity_type_none_and_empty_are_none():
    assert svc.validate_entity_type(None) is None
    assert svc.validate_entity_type("") is None


def test_validate_entity_type_whitelist():
    for ok in ("product", "customer", "invoice", "appointment", "note"):
        assert svc.validate_entity_type(ok) == ok
    for bad in ("foo", "Invoice", "PRODUCT"):
        with pytest.raises(ValueError):
            svc.validate_entity_type(bad)


# ── Pure service: summary + metadata ──────────────────────────────────────


def test_validate_summary_trims_and_caps():
    assert svc.validate_summary("  hello ") == "hello"
    with pytest.raises(ValueError):
        svc.validate_summary("")
    with pytest.raises(ValueError):
        svc.validate_summary("   ")
    with pytest.raises(ValueError):
        svc.validate_summary("x" * (svc.MAX_SUMMARY_LENGTH + 1))


def test_validate_metadata_default_empty_dict():
    assert svc.validate_metadata(None) == {}
    assert svc.validate_metadata({}) == {}


def test_validate_metadata_allows_scalars_only():
    out = svc.validate_metadata(
        {"n": 1, "f": 1.5, "b": True, "s": "ok", "z": None}
    )
    assert out == {"n": 1, "f": 1.5, "b": True, "s": "ok", "z": None}


def test_validate_metadata_rejects_nested_and_lists():
    with pytest.raises(ValueError):
        svc.validate_metadata({"x": {"nested": 1}})
    with pytest.raises(ValueError):
        svc.validate_metadata({"x": [1, 2]})


def test_validate_metadata_enforces_key_and_value_limits():
    with pytest.raises(ValueError):
        svc.validate_metadata({str(i): i for i in range(svc.MAX_METADATA_KEYS + 1)})
    with pytest.raises(ValueError):
        svc.validate_metadata({"x": "a" * (svc.MAX_METADATA_VALUE_LENGTH + 1)})


def test_validate_metadata_requires_non_empty_string_keys():
    with pytest.raises(ValueError):
        svc.validate_metadata({"": 1})
    with pytest.raises(ValueError):
        svc.validate_metadata({1: "x"})  # type: ignore[dict-item]


def test_validate_metadata_rejects_non_dict():
    with pytest.raises(ValueError):
        svc.validate_metadata("hi")  # type: ignore[arg-type]


# ── Pure service: limit clamping ──────────────────────────────────────────


def test_clamp_limit_defaults_and_caps():
    assert svc.clamp_limit(None) == svc.DEFAULT_LIMIT
    assert svc.clamp_limit(5) == 5
    assert svc.clamp_limit(svc.MAX_LIMIT + 100) == svc.MAX_LIMIT


def test_clamp_limit_rejects_bad_input():
    with pytest.raises(ValueError):
        svc.clamp_limit(0)
    with pytest.raises(ValueError):
        svc.clamp_limit(-1)
    with pytest.raises(ValueError):
        svc.clamp_limit("not-a-number")


# ── Pure service: cursor encode/decode ────────────────────────────────────


def test_cursor_round_trip():
    t = datetime(2026, 4, 1, 12, 30, 45, tzinfo=timezone.utc)
    eid = uuid.uuid4()
    c = svc.encode_cursor(t, eid)
    t2, eid2 = svc.decode_cursor(c)
    assert t2 == t
    assert eid2 == eid


def test_cursor_normalises_naive_datetime_to_utc():
    t = datetime(2026, 4, 1, 12, 30, 45)
    eid = uuid.uuid4()
    c = svc.encode_cursor(t, eid)
    t2, _ = svc.decode_cursor(c)
    assert t2.tzinfo is not None


def test_cursor_decode_rejects_junk():
    for bad in ("", "not-base64!!!", "YWJj", "Zm9v"):
        with pytest.raises(ValueError):
            svc.decode_cursor(bad)


def test_cursor_decode_rejects_missing_fields():
    import base64, json
    raw = json.dumps({"t": "2026-04-01T12:00:00+00:00"}).encode()
    c = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    with pytest.raises(ValueError):
        svc.decode_cursor(c)


# ── Migration + model ─────────────────────────────────────────────────────


def test_migration_v71_chains_from_v70():
    assert 'revision = "a2b4c6d8e0f2"' in MIGRATION_SRC
    assert 'down_revision = "f0b2d4e6a8c1"' in MIGRATION_SRC


def test_migration_creates_expected_indexes():
    assert "ix_activity_org_created" in MIGRATION_SRC
    assert "ix_activity_entity" in MIGRATION_SRC
    assert "ix_activity_actor" in MIGRATION_SRC


def test_model_matches_migration():
    assert "class ActivityEvent(Base)" in MODEL_SRC
    assert '__tablename__ = "activity_events"' in MODEL_SRC
    assert "action" in MODEL_SRC
    assert "metadata_" in MODEL_SRC  # attribute-level, column is "metadata"


# ── Router source-contract ────────────────────────────────────────────────


def test_router_registered_on_api_activity():
    assert 'prefix="/api/activity"' in ROUTER_SRC
    # activity is registered via analytics_router (vertical-slice architecture)
    feat_src = _read("app/features/analytics/router.py")
    assert "activity" in feat_src
    assert "analytics_router" in MAIN_SRC


def test_router_has_three_endpoints():
    for sig in (
        '@router.get("", response_model=FeedPage)',
        '@router.get("/{entity_type}/{entity_id}"',
        '@router.post("/note"',
    ):
        assert sig in ROUTER_SRC, f"missing signature: {sig}"


def test_router_tenant_scopes_queries():
    assert "ActivityEvent.org_id == org_id" in ROUTER_SRC


def test_router_escapes_like_wildcards_in_prefix():
    # The "like" prefix filter must not let users inject `%` or `_`.
    assert 'replace("%", "\\\\%")' in ROUTER_SRC
    assert 'replace("_", "\\\\_")' in ROUTER_SRC


def test_router_orders_newest_first_with_keyset():
    assert "created_at.desc()" in ROUTER_SRC
    assert "ActivityEvent.id.desc()" in ROUTER_SRC


def test_router_fetches_limit_plus_one_for_next_cursor():
    assert "limit + 1" in ROUTER_SRC
    assert "next_cursor" in ROUTER_SRC


def test_router_note_logs_audit_action():
    assert '"activity.note_added"' in ROUTER_SRC
    assert 'action="note.added"' in ROUTER_SRC
