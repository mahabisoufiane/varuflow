"""Tests for the supplier portal (Item 37, v52).

Pure + contract-style tests — exercise the pure service helpers
directly and use ``inspect.getsource`` to validate router properties
(no PATCH/PUT/DELETE, audit call present, ownership guards) that
cannot be reached from the 3.9 pytest sandbox without a DB.

Path convention: ``backend/tests/`` (not ``backend/app/tests/``) —
same deviation as Items 28–36.
"""
from __future__ import annotations

import inspect
import pathlib
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import supplier_portal_service as svc


# Lazy source readers — the 3.9 sandbox can't import modules that use
# ``str | None`` annotations (organization.py, auth.py, email.py,
# routers/supplier_portal.py). Reading the source text bypasses the
# import chain while still letting the tests lock in invariants.
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


ROUTER_SRC = _read("features/purchases/supplier_portal.py")
EMAIL_SRC = _read("services/email.py")
MODEL_SRC = _read("features/purchases/supplier_portal_models.py")
MIGRATION_SRC = (_BACKEND_ROOT.parent / "migrations" / "versions" /
                 "d0e1f2a3b4c5_v52_supplier_portal.py").read_text()


# ═══════════════════════════════════════════════════════════════════
# Fixtures & helpers
# ═══════════════════════════════════════════════════════════════════


NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)


def _record(
    *,
    supplier_id=None,
    org_id=None,
    raw="sample-raw-token-value",
    created_at=NOW - timedelta(days=1),
    expires_at=NOW + timedelta(days=13),
    last_used_at=None,
    is_revoked=False,
) -> svc.TokenRecord:
    return svc.TokenRecord(
        supplier_id=supplier_id or uuid.uuid4(),
        org_id=org_id or uuid.uuid4(),
        token_hash=svc.hash_token(raw),
        created_at=created_at,
        expires_at=expires_at,
        last_used_at=last_used_at,
        is_revoked=is_revoked,
    )


# ═══════════════════════════════════════════════════════════════════
# 1. test_token_generation
# ═══════════════════════════════════════════════════════════════════


def test_token_generation():
    tokens = {svc.generate_token() for _ in range(50)}
    # All unique (CSPRNG collisions would be astronomical).
    assert len(tokens) == 50
    for tok in tokens:
        # URL-safe base64 of 32 random bytes is ≥ 43 chars.
        assert len(tok) >= 43
        # SHA-256 hash is deterministic + 64 hex chars.
        h = svc.hash_token(tok)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)
        # Hash is deterministic.
        assert h == svc.hash_token(tok)
        # Raw tokens differ → hashes differ.
    hashes = {svc.hash_token(t) for t in tokens}
    assert len(hashes) == 50


def test_hash_token_rejects_empty():
    with pytest.raises(ValueError):
        svc.hash_token("")
    with pytest.raises(ValueError):
        svc.hash_token(None)  # type: ignore[arg-type]


def test_compute_expires_at_is_bounded():
    t0 = NOW
    # Default window.
    exp = svc.compute_expires_at(t0, svc.DEFAULT_EXPIRY_DAYS)
    assert exp == t0 + timedelta(days=svc.DEFAULT_EXPIRY_DAYS)
    # Caller over-ask is clamped.
    assert svc.compute_expires_at(t0, 999) == t0 + timedelta(days=svc.MAX_EXPIRY_DAYS)
    # Zero / negative is clamped up to 1.
    assert svc.compute_expires_at(t0, 0) == t0 + timedelta(days=1)
    assert svc.compute_expires_at(t0, -5) == t0 + timedelta(days=1)


# ═══════════════════════════════════════════════════════════════════
# 2. test_supplier_views_own_pos_only
# ═══════════════════════════════════════════════════════════════════


def test_supplier_views_own_pos_only():
    """``list_supplier_pos`` and ``get_supplier_po`` both filter on
    ``(supplier_id, org_id)`` — confirmed by reading the service
    source. Bypassing these filters would let one supplier read
    another's PO history; the contract test locks the filter in.
    """
    src = inspect.getsource(svc.list_supplier_pos)
    assert "PurchaseOrder.supplier_id == supplier_id" in src
    assert "PurchaseOrder.org_id == org_id" in src
    # Draft POs must not leak to the supplier.
    assert "PurchaseOrderStatus.DRAFT" in src
    assert "!= PurchaseOrderStatus.DRAFT" in src

    src_detail = inspect.getsource(svc.get_supplier_po)
    assert "PurchaseOrder.supplier_id == supplier_id" in src_detail
    assert "PurchaseOrder.org_id == org_id" in src_detail
    assert "!= PurchaseOrderStatus.DRAFT" in src_detail


# ═══════════════════════════════════════════════════════════════════
# 3. test_po_confirmation_by_supplier
# ═══════════════════════════════════════════════════════════════════


def test_po_confirmation_by_supplier():
    sid = uuid.uuid4()
    # Happy path — supplier matches, PO not yet confirmed.
    svc.can_confirm_po(
        po_supplier_id=sid,
        requesting_supplier_id=sid,
        confirmed_at=None,
    )


def test_confirm_po_rejects_cross_supplier():
    a, b = uuid.uuid4(), uuid.uuid4()
    with pytest.raises(ValueError) as exc:
        svc.can_confirm_po(
            po_supplier_id=a,
            requesting_supplier_id=b,
            confirmed_at=None,
        )
    assert "po_not_owned_by_supplier" in str(exc.value)


def test_confirm_po_idempotent_once_confirmed():
    sid = uuid.uuid4()
    with pytest.raises(ValueError) as exc:
        svc.can_confirm_po(
            po_supplier_id=sid,
            requesting_supplier_id=sid,
            confirmed_at=NOW,
        )
    assert "po_already_confirmed" in str(exc.value)


def test_confirm_po_uses_conditional_update():
    # The DB-level guard is the ``confirmed_at.is_(None)`` filter in
    # the UPDATE — without it two concurrent confirms could both
    # succeed (replay window). Pin the source so this can't regress.
    src = inspect.getsource(svc.confirm_po)
    assert "confirmed_at.is_(None)" in src
    assert "PurchaseOrder.confirmed_at.is_(None)" in src
    # Only confirms non-draft POs.
    assert "PurchaseOrderStatus.DRAFT" in src


# ═══════════════════════════════════════════════════════════════════
# 4. test_expired_token_rejected
# ═══════════════════════════════════════════════════════════════════


def test_expired_token_rejected():
    raw = "test-token-value"
    rec = _record(
        raw=raw,
        created_at=NOW - timedelta(days=30),
        expires_at=NOW - timedelta(seconds=1),
    )
    with pytest.raises(ValueError) as exc:
        svc.validate_token_record(rec, raw_token=raw, now=NOW)
    assert "token_expired" in str(exc.value)

    # Boundary — expires_at exactly at ``now`` is treated as expired.
    rec2 = _record(raw=raw, expires_at=NOW)
    with pytest.raises(ValueError):
        svc.validate_token_record(rec2, raw_token=raw, now=NOW)


def test_unexpired_token_accepted():
    raw = "fresh-token-abc"
    rec = _record(raw=raw)
    # Should not raise.
    svc.validate_token_record(rec, raw_token=raw, now=NOW)


# ═══════════════════════════════════════════════════════════════════
# 5. test_revoked_token_rejected
# ═══════════════════════════════════════════════════════════════════


def test_revoked_token_rejected():
    raw = "revokable"
    rec = _record(raw=raw, is_revoked=True)
    with pytest.raises(ValueError) as exc:
        svc.validate_token_record(rec, raw_token=raw, now=NOW)
    assert "token_revoked" in str(exc.value)


def test_is_token_live_helper():
    raw = "live"
    assert svc.is_token_live(_record(raw=raw), NOW) is True
    assert svc.is_token_live(_record(raw=raw, is_revoked=True), NOW) is False
    assert svc.is_token_live(
        _record(raw=raw, expires_at=NOW - timedelta(seconds=1)), NOW
    ) is False


# ═══════════════════════════════════════════════════════════════════
# 6. test_replay_attack_rejected
# ═══════════════════════════════════════════════════════════════════


def test_replay_attack_rejected():
    """A stale / wrong raw token must never validate against a stored
    hash. This is the "replay attack" vector: attacker captures an
    old URL, server must reject when comparing to the rotated hash.
    """
    genuine = "genuine-raw-token"
    rec = _record(raw=genuine)
    # Totally different token with matching structure.
    with pytest.raises(ValueError) as exc:
        svc.validate_token_record(rec, raw_token="stolen-attempt", now=NOW)
    assert "token_hash_mismatch" in str(exc.value)
    # Even a one-byte tweak fails.
    with pytest.raises(ValueError) as exc2:
        svc.validate_token_record(rec, raw_token=genuine + "x", now=NOW)
    assert "token_hash_mismatch" in str(exc2.value)
    # Empty raw token: hash_token raises first.
    with pytest.raises(ValueError):
        svc.validate_token_record(rec, raw_token="", now=NOW)


def test_hash_is_one_way_proxy():
    # The service never exposes the raw token back to the DB layer;
    # only the hash is stored. Confirm by reading the service source.
    src = inspect.getsource(svc.issue_token)
    assert "hash_token" in src
    # No place in the service stores the raw token on the row.
    assert "token_hash=token_hash" in src
    # `raw` is only returned to the caller — never assigned onto
    # the ORM instance.
    assert "token=raw" not in src


# ═══════════════════════════════════════════════════════════════════
# 7. test_org_isolation
# ═══════════════════════════════════════════════════════════════════


def test_org_isolation():
    """Every DB wrapper filters on ``org_id`` — verified via source
    inspection (same style as §65's generator check). A cross-org
    supplier can't resolve a PO or a token from another tenant.
    """
    for fn in (
        svc.list_supplier_pos,
        svc.get_supplier_po,
        svc.confirm_po,
        svc.revoke_token,
        svc.find_active_tokens,
    ):
        assert "org_id" in inspect.getsource(fn), f"{fn.__name__} lacks org_id filter"


def test_token_record_carries_org_scope():
    # TokenRecord must expose org_id so the router can enforce
    # cross-org isolation by comparing to the member's org_id.
    rec = _record()
    assert isinstance(rec.org_id, uuid.UUID)
    assert isinstance(rec.supplier_id, uuid.UUID)


# ═══════════════════════════════════════════════════════════════════
# 8. test_send_portal_link_email
# ═══════════════════════════════════════════════════════════════════


def test_send_portal_link_email():
    """The email helper is declared in services/email.py with the right
    signature. Reading the source text avoids importing the module
    (which uses 3.10+ annotations that the 3.9 sandbox can't eval).
    """
    assert "async def send_supplier_portal_email(" in EMAIL_SRC
    # Required template args appear in the function signature.
    sig_start = EMAIL_SRC.index("async def send_supplier_portal_email(")
    sig_end = EMAIL_SRC.index(")", sig_start)
    sig = EMAIL_SRC[sig_start:sig_end]
    for arg in ("to_email", "supplier_name", "magic_url", "org_name", "expires_in_days"):
        assert arg in sig, f"missing arg: {arg}"
    # Dev short-circuit when Resend isn't configured.
    assert "if not settings.RESEND_API_KEY:" in EMAIL_SRC
    assert "return False" in EMAIL_SRC


def test_magic_url_is_wellformed():
    url = svc.build_magic_url("https://app.example.com", "tok-123")
    assert url == "https://app.example.com/supplier-portal/verify?token=tok-123"
    # Trailing slash on base is stripped.
    assert svc.build_magic_url("https://app.example.com/", "tok") == (
        "https://app.example.com/supplier-portal/verify?token=tok"
    )


# ═══════════════════════════════════════════════════════════════════
# 9. test_no_edit_access
# ═══════════════════════════════════════════════════════════════════


def test_no_edit_access():
    """The supplier-facing half of the router exposes only GETs plus
    the single sanctioned ``POST .../confirm`` mutation. No PATCH /
    PUT / DELETE is allowed — read-only + confirm is the whole API
    surface for portal users.
    """
    # Explicitly not present.
    assert "@router.patch" not in ROUTER_SRC
    assert "@router.put" not in ROUTER_SRC
    assert "@router.delete" not in ROUTER_SRC
    # Every ``@router.post`` handler must use either the supplier
    # portal dep (single confirm endpoint) or the admin dep (token
    # issue / revoke) — no unauthenticated mutation.
    # ``split`` yields ``n+1`` chunks for ``n`` occurrences; drop the
    # leading (pre-first-split) chunk which is the module docstring +
    # imports.
    post_blocks = ROUTER_SRC.split("@router.post(")[1:]
    # 3 POSTs: token issue (admin), token revoke (admin), confirm (supplier).
    assert len(post_blocks) == 3
    for block in post_blocks:
        assert (
            "Depends(get_portal_supplier)" in block
            or "Depends(get_current_member)" in block
        )


def test_portal_only_confirm_can_mutate_po():
    # There is exactly ONE supplier-facing mutation in the service layer.
    mutation_fns = [
        name for name in dir(svc)
        if name.startswith("confirm_")
    ]
    assert mutation_fns == ["confirm_po"]


def test_no_price_or_product_mutation_symbol():
    # Nothing in the service layer modifies product or price rows.
    src = inspect.getsource(svc)
    for forbidden in (
        "Product.sell_price",
        "PurchaseOrderItem.unit_price",
        "Product.purchase_price",
    ):
        # These appear nowhere (read-only view path).
        assert forbidden not in src


# ═══════════════════════════════════════════════════════════════════
# 10. test_audit_log_on_po_confirmation
# ═══════════════════════════════════════════════════════════════════


def test_audit_log_on_po_confirmation():
    # Action string is locked in so downstream SIEM queries don't
    # silently fall off if someone renames the event.
    assert 'action="supplier_portal.po_confirmed"' in ROUTER_SRC
    assert 'target_type="purchase_order"' in ROUTER_SRC
    assert "target_id=str(po_id)" in ROUTER_SRC
    # supplier_id + token_id end up in ``extra`` for incident response.
    assert '"supplier_id": str(supplier_id)' in ROUTER_SRC
    assert '"token_id": str(token_id)' in ROUTER_SRC


def test_audit_log_on_token_issue_and_revoke():
    assert 'action="supplier_portal.token_issued"' in ROUTER_SRC
    assert 'action="supplier_portal.token_revoked"' in ROUTER_SRC
    # Both mutations target the token row for traceability.
    assert ROUTER_SRC.count('target_type="supplier_portal_token"') >= 2


# ═══════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════


def test_mask_raw_token():
    raw = svc.generate_token()
    masked = svc.mask_raw_token(raw)
    assert masked.endswith("…")
    assert len(masked) == 7  # 6 chars + ellipsis
    assert masked.startswith(raw[:6])
    # Empty input handled.
    assert svc.mask_raw_token("") == ""


def test_clamp_expiry_days():
    assert svc.clamp_expiry_days(None) == svc.DEFAULT_EXPIRY_DAYS
    assert svc.clamp_expiry_days(0) == 1
    assert svc.clamp_expiry_days(-10) == 1
    assert svc.clamp_expiry_days(svc.MAX_EXPIRY_DAYS + 1) == svc.MAX_EXPIRY_DAYS
    assert svc.clamp_expiry_days(7) == 7


def test_naive_datetime_handled():
    # Legacy DB rows with naive datetimes get assumed-UTC.
    raw = "naive-token"
    naive_exp = (NOW + timedelta(days=5)).replace(tzinfo=None)
    rec = svc.TokenRecord(
        supplier_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        token_hash=svc.hash_token(raw),
        created_at=NOW.replace(tzinfo=None),
        expires_at=naive_exp,
        last_used_at=None,
        is_revoked=False,
    )
    svc.validate_token_record(rec, raw_token=raw, now=NOW)


def test_validate_token_hash_mismatch_precedence():
    # A revoked, expired token with a WRONG raw still reports the
    # hash mismatch first — auditors don't need to know it was also
    # revoked, and it stops a tester from distinguishing the guards
    # via timing.
    rec = _record(raw="correct", is_revoked=True, expires_at=NOW - timedelta(days=1))
    with pytest.raises(ValueError) as exc:
        svc.validate_token_record(rec, raw_token="wrong", now=NOW)
    assert "token_hash_mismatch" in str(exc.value)


def test_issue_token_flow_with_mocked_db():
    """Exercise the DB-bound ``issue_token`` against a mock session to
    prove (a) the hash matches the returned raw, (b) ``db.add`` + flush
    are called, (c) the row carries the org + supplier IDs.

    Uses ``asyncio.run`` rather than pytest-asyncio so the test runs
    under the ``--noconftest`` sandbox without extra plugins. The
    service model class is lazy-imported inside ``issue_token`` so
    the 3.9 import chain doesn't trip the ``str | None`` annotations
    in ``app.models`` — we stub it instead.
    """
    import asyncio

    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    sid, oid = uuid.uuid4(), uuid.uuid4()

    # Stub the lazy SupplierPortalToken import so we don't have to
    # load app.models at test time. ``issue_token`` imports it via
    # ``from app.features.purchases.supplier_portal_models import SupplierPortalToken``;
    # we inject a fake module into sys.modules.
    import sys
    import types as _types

    class _FakeRow:
        def __init__(self, *, supplier_id, org_id, token_hash, expires_at):
            self.supplier_id = supplier_id
            self.org_id = org_id
            self.token_hash = token_hash
            self.expires_at = expires_at

    fake_mod = _types.ModuleType("app.models.supplier_portal")
    fake_mod.SupplierPortalToken = _FakeRow
    # Also ensure ``app.models`` package stub exists so attribute
    # lookups on the parent don't trigger its real __init__.py.
    if "app.models" not in sys.modules:
        sys.modules["app.models"] = _types.ModuleType("app.models")
    sys.modules["app.models.supplier_portal"] = fake_mod

    raw, row = asyncio.run(
        svc.issue_token(
            mock_db, supplier_id=sid, org_id=oid, expires_in_days=30,
        )
    )
    assert svc.hash_token(raw) == row.token_hash
    assert row.supplier_id == sid
    assert row.org_id == oid
    assert mock_db.add.called
    assert mock_db.flush.await_count == 1


def test_expires_at_exactly_days_later():
    # Spot-check the timedelta math matches expectations to the second.
    t0 = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert svc.compute_expires_at(t0, 14) == datetime(
        2026, 5, 15, 0, 0, 0, tzinfo=timezone.utc,
    )
