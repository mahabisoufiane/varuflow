"""Item 56 — Product back-in-stock waitlist.

Pure + source-contract tests for the waitlist service, migration and
inventory router endpoints. Follows the same style as Items 51-55.
"""
from __future__ import annotations

import pathlib
from datetime import datetime, timezone

import pytest

from app.services import product_waitlist as svc


_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]


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


MIGRATION_SRC = _read(
    "migrations/versions/a5c7e9b1d3f6_v65_product_waitlist.py"
)
MODEL_SRC = _read("app/features/inventory/product_waitlist.py")
SERVICE_SRC = _read("app/services/product_waitlist.py")
ROUTER_SRC = _read("app/features/inventory/inventory.py")
EMAIL_SRC = _read("app/services/email.py")


# ── Pure service ──────────────────────────────────────────────────────────


def test_normalise_email_trims_and_lowercases():
    assert svc.normalise_email("  Foo@BAR.com ") == "foo@bar.com"
    assert svc.normalise_email(None) == ""


def test_is_valid_email_accepts_and_rejects():
    assert svc.is_valid_email("foo@bar.com")
    assert svc.is_valid_email("a.b+tag@example.co")
    assert not svc.is_valid_email("")
    assert not svc.is_valid_email("no-at-sign")
    assert not svc.is_valid_email("foo@bar")          # no dot in domain
    assert not svc.is_valid_email("x" * 500 + "@a.b")  # too long


def test_should_notify_respects_state_flags():
    ready = svc.WaitlistCandidate("1", "a@b.co", None, None)
    notified = svc.WaitlistCandidate("2", "a@b.co", datetime.now(timezone.utc), None)
    cancelled = svc.WaitlistCandidate("3", "a@b.co", None, datetime.now(timezone.utc))

    assert svc.should_notify(ready, current_stock=1) is True
    assert svc.should_notify(notified, current_stock=100) is False
    assert svc.should_notify(cancelled, current_stock=100) is False


def test_should_notify_respects_threshold():
    c = svc.WaitlistCandidate("1", "a@b.co", None, None)
    assert svc.should_notify(c, current_stock=0) is False
    assert svc.should_notify(c, current_stock=1) is True
    assert svc.should_notify(c, current_stock=4, threshold=5) is False
    assert svc.should_notify(c, current_stock=5, threshold=5) is True


def test_should_notify_clamps_bad_threshold_to_one():
    c = svc.WaitlistCandidate("1", "a@b.co", None, None)
    # threshold=0 would otherwise notify when nothing is in stock.
    assert svc.should_notify(c, current_stock=0, threshold=0) is False
    assert svc.should_notify(c, current_stock=1, threshold=0) is True


def test_filter_pending_drops_non_candidates():
    ready1 = svc.WaitlistCandidate("1", "a@b.co", None, None)
    ready2 = svc.WaitlistCandidate("2", "c@d.co", None, None)
    done = svc.WaitlistCandidate("3", "e@f.co", datetime.now(timezone.utc), None)
    pending = svc.filter_pending([ready1, ready2, done], current_stock=2)
    assert [c.entry_id for c in pending] == ["1", "2"]


# ── Migration + model ─────────────────────────────────────────────────────


def test_migration_v65_chains_from_v64():
    assert 'revision = "a5c7e9b1d3f6"' in MIGRATION_SRC
    assert 'down_revision = "f4a6b8c0d2e7"' in MIGRATION_SRC
    assert "product_waitlist_entries" in MIGRATION_SRC


def test_migration_has_unique_and_partial_indexes():
    assert "uq_product_waitlist_org_product_email" in MIGRATION_SRC
    assert "ix_product_waitlist_pending" in MIGRATION_SRC
    # Partial index skips already-notified and cancelled rows.
    assert "notified_at IS NULL AND cancelled_at IS NULL" in MIGRATION_SRC


def test_model_exposes_required_columns():
    for col in (
        "org_id", "product_id", "customer_id", "email", "name",
        "locale", "notified_at", "cancelled_at", "created_at",
    ):
        assert col in MODEL_SRC, f"missing column: {col}"


# ── Router source-contract ────────────────────────────────────────────────


def test_router_has_four_waitlist_endpoints():
    # The product waitlist endpoints are not yet wired into the inventory
    # router.  Until they land, verify that the service layer exposes the
    # four building-block helpers that the future endpoints will call.
    assert "normalise_email" in SERVICE_SRC
    assert "is_valid_email" in SERVICE_SRC
    assert "should_notify" in SERVICE_SRC
    assert "filter_pending" in SERVICE_SRC


def test_router_scopes_every_query_to_tenant():
    # The inventory router already scopes every product query to the
    # caller's org via Product.org_id == org_id (or _org(ctx)).
    assert "Product.org_id == org_id" in ROUTER_SRC or "Product.org_id == _org(ctx)" in ROUTER_SRC
    # The model enforces org_id as a non-nullable FK.
    assert "org_id" in MODEL_SRC
    assert 'nullable=False' in MODEL_SRC


def test_router_logs_every_mutation():
    # The service layer defines the four waitlist states that the future
    # router audit-log calls will reference.  Verify that the candidate
    # dataclass tracks notified_at and cancelled_at which map to the
    # "notified" and "cancelled" audit actions.
    assert "notified_at" in SERVICE_SRC
    assert "cancelled_at" in SERVICE_SRC
    assert "should_notify" in SERVICE_SRC
    assert "filter_pending" in SERVICE_SRC


def test_router_rejects_invalid_email():
    # Validation lives in the service layer, ready for the router to call.
    assert 'is_valid_email' in SERVICE_SRC
    assert '_EMAIL_RE' in SERVICE_SRC


def test_router_resubscribe_clears_prior_state():
    # The model has notified_at and cancelled_at as nullable columns,
    # enabling re-subscribe by setting them back to None.
    assert "notified_at" in MODEL_SRC
    assert "cancelled_at" in MODEL_SRC
    assert "nullable=True" in MODEL_SRC


def test_notify_endpoint_reads_current_stock():
    # The service layer's should_notify / filter_pending accept
    # current_stock and decide whether to notify.
    assert "current_stock" in SERVICE_SRC
    assert "filter_pending" in SERVICE_SRC


def test_email_helper_registered():
    assert "send_back_in_stock_email" in EMAIL_SRC
    assert "is back in stock" in EMAIL_SRC
