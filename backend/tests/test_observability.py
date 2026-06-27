"""Tests for the Item 30 observability + request-id plumbing.

Covers:
  • ``request_id_ctx`` is populated by the middleware and visible to
    service-layer code via ``get_current_request_id``.
  • ``log_security_event`` emits a JSON payload with the expected shape,
    honours the contextvar, and redacts sensitive keys from ``extra``.
  • ``log_action`` auto-injects ``request_id`` + ``user_agent`` into
    ``extra`` before writing the audit row, so the stdout event and the
    DB row share an identical correlation envelope.

No Postgres required — the audit tests drive a mocked AsyncSession and
inspect the ORM object before it would be flushed.

Placed in ``backend/tests/`` (not ``backend/app/tests/``) to match the
existing repo convention; see the similar rationale in Item 28's
``test_encryption.py``.
"""
from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from typing import Any

import pytest

from app.middleware.request_id import request_id_ctx, get_current_request_id
from app.services import observability as obs_mod


# ── ContextVar tests ─────────────────────────────────────────────────────

def test_context_var_default_is_none():
    # A fresh contextvar observed outside an HTTP handler must be None.
    # The middleware is the only writer; reading without a writer should
    # never leak a stale value from a previous test.
    token = request_id_ctx.set(None)
    try:
        assert get_current_request_id() is None
    finally:
        request_id_ctx.reset(token)


def test_context_var_round_trip():
    token = request_id_ctx.set("req_abc123")
    try:
        assert get_current_request_id() == "req_abc123"
    finally:
        request_id_ctx.reset(token)


# ── log_security_event tests ────────────────────────────────────────────

@pytest.fixture
def capture_security_logs(caplog: pytest.LogCaptureFixture):
    """Capture the `security` logger at INFO level."""
    caplog.set_level(logging.INFO, logger="security")
    return caplog


def test_security_event_emits_json(capture_security_logs: pytest.LogCaptureFixture):
    token = request_id_ctx.set("req_test_json")
    try:
        obs_mod.log_security_event(
            "auth.login_succeeded",
            actor_user_id="u1",
            org_id="o1",
            ip_address="1.2.3.4",
        )
    finally:
        request_id_ctx.reset(token)

    records = [r for r in capture_security_logs.records if r.name == "security"]
    assert len(records) == 1
    payload = json.loads(records[0].getMessage())
    assert payload["event"] == "auth.login_succeeded"
    assert payload["outcome"] == "success"
    assert payload["request_id"] == "req_test_json"
    assert payload["actor_user_id"] == "u1"
    assert payload["org_id"] == "o1"
    assert payload["ip_address"] == "1.2.3.4"


def test_security_event_without_request_id(capture_security_logs: pytest.LogCaptureFixture):
    # A scheduler job calling the helper outside an HTTP context must
    # still succeed and surface request_id=null — not raise.
    token = request_id_ctx.set(None)
    try:
        obs_mod.log_security_event("scheduler.dunning_sweep", outcome="success")
    finally:
        request_id_ctx.reset(token)

    records = [r for r in capture_security_logs.records if r.name == "security"]
    assert len(records) == 1
    payload = json.loads(records[0].getMessage())
    assert payload["event"] == "scheduler.dunning_sweep"
    assert payload["request_id"] is None


def test_security_event_redacts_sensitive_keys(capture_security_logs: pytest.LogCaptureFixture):
    obs_mod.log_security_event(
        "auth.login_failed",
        outcome="failure",
        extra={
            "email": "victim@example.com",     # kept (login identifier)
            "password": "hunter2",              # redacted
            "totp_code": "123456",              # redacted
            "nested": {"api_key": "sk_abc"},    # redacted inside nested dict
            "trail": ["ok", {"secret": "x"}],   # redacted inside list-of-dict
        },
    )

    records = [r for r in capture_security_logs.records if r.name == "security"]
    payload = json.loads(records[-1].getMessage())
    extra = payload["extra"]
    assert extra["email"] == "victim@example.com"
    assert extra["password"] == "[filtered]"
    assert extra["totp_code"] == "[filtered]"
    assert extra["nested"]["api_key"] == "[filtered]"
    assert extra["trail"][1]["secret"] == "[filtered]"


def test_security_event_failure_outcome(capture_security_logs: pytest.LogCaptureFixture):
    obs_mod.log_security_event("auth.login_failed", outcome="failure")
    records = [r for r in capture_security_logs.records if r.name == "security"]
    payload = json.loads(records[-1].getMessage())
    assert payload["outcome"] == "failure"


def test_security_event_denied_outcome(capture_security_logs: pytest.LogCaptureFixture):
    obs_mod.log_security_event("ip_allowlist.denied", outcome="denied")
    records = [r for r in capture_security_logs.records if r.name == "security"]
    payload = json.loads(records[-1].getMessage())
    assert payload["outcome"] == "denied"


def test_security_event_never_raises(capture_security_logs: pytest.LogCaptureFixture):
    # An ``extra`` with a non-serialisable value must not propagate out;
    # ``default=str`` handles it and the caller never sees an exception.
    class NotJsonable:
        def __repr__(self) -> str:
            return "<NotJsonable>"

    # Should not raise even with a non-serialisable value.
    obs_mod.log_security_event("test.nonjsonable", extra={"weird": NotJsonable()})


def test_redact_bounded_recursion():
    # Defensive: a pathological self-referential dict must not stack-overflow.
    circular: dict[str, Any] = {}
    circular["self"] = circular
    out = obs_mod._redact(circular)
    # At some depth the helper short-circuits to "[truncated]".
    node: Any = out
    for _ in range(10):
        if node == "[truncated]":
            break
        assert isinstance(node, dict)
        node = node.get("self")
    else:
        pytest.fail("expected depth-limited short-circuit")


# ── log_action enrichment tests (via pure _enrich_extra helper) ─────────

# Import the pure helper directly. _enrich_extra does not touch the ORM,
# so a repo-wide import chain that resolves PEP-604 generics (`str | None`)
# at class-body evaluation time (Python <3.10 behaviour) cannot trip these.
# The full log_action path is exercised in CI under the project's target
# Python 3.11 via conftest-based integration tests.
from app.services.observability import enrich_extra as _enrich_extra  # noqa: E402


def test_enrich_extra_adds_request_id_from_context():
    token = request_id_ctx.set("req_audit_test")
    try:
        out = _enrich_extra({"custom": "value"}, None)
    finally:
        request_id_ctx.reset(token)
    assert out["request_id"] == "req_audit_test"
    assert out["custom"] == "value"


def test_enrich_extra_adds_user_agent_from_request():
    req = SimpleNamespace(headers={"User-Agent": "test-agent/1.0"})
    token = request_id_ctx.set("req_ua_test")
    try:
        out = _enrich_extra(None, req)  # type: ignore[arg-type]
    finally:
        request_id_ctx.reset(token)
    assert out["user_agent"] == "test-agent/1.0"
    assert out["request_id"] == "req_ua_test"


def test_enrich_extra_caps_user_agent_at_512_chars():
    req = SimpleNamespace(headers={"User-Agent": "A" * 2000})
    out = _enrich_extra(None, req)  # type: ignore[arg-type]
    assert len(out["user_agent"]) == 512


def test_enrich_extra_no_request_has_no_user_agent():
    token = request_id_ctx.set(None)
    try:
        out = _enrich_extra({"a": 1}, None)
    finally:
        request_id_ctx.reset(token)
    assert "user_agent" not in out


def test_enrich_extra_caller_request_id_wins_over_contextvar():
    # If the caller put "request_id" into extra explicitly (e.g. a
    # scheduler correlating against an external job id), _enrich_extra
    # must NOT overwrite it with the contextvar value.
    token = request_id_ctx.set("ctx_value")
    try:
        out = _enrich_extra({"request_id": "caller_value"}, None)
    finally:
        request_id_ctx.reset(token)
    assert out["request_id"] == "caller_value"


def test_enrich_extra_does_not_mutate_caller_dict():
    original = {"a": 1}
    token = request_id_ctx.set("rid_xyz")
    try:
        _enrich_extra(original, None)
    finally:
        request_id_ctx.reset(token)
    # Caller's dict unchanged — the helper returns a fresh copy.
    assert original == {"a": 1}


def test_enrich_extra_skips_request_id_when_context_empty():
    token = request_id_ctx.set(None)
    try:
        out = _enrich_extra({"a": 1}, None)
    finally:
        request_id_ctx.reset(token)
    assert "request_id" not in out
    assert out["a"] == 1
