"""Structured observability helpers (Item 30).

Complements ``app.services.audit`` — while ``audit.log_action`` persists
sensitive events to the ``audit_log`` table for forensics, this module
emits *structured JSON log lines* to the container stdout for real-time
visibility in Railway / Render / Sentry.

Every security-relevant action should produce both:

  • an audit-log row  (durable, queryable, retained 7 years)
  • a security event  (ephemeral, searchable by ops in log aggregator)

``log_action`` now calls ``log_security_event`` automatically so the two
stay in lock-step — no router needs to call both by hand.

Design goals
------------
* **Zero new dependencies.** Uses stdlib ``logging`` + ``json``. The
  existing JSON formatter in main.py serialises ``msg`` as JSON so a
  dict payload arrives on stdout pre-parsed by Datadog / Loki / Sentry.
* **Request-ID correlation.** ``get_current_request_id()`` reads the
  contextvar populated by ``RequestIdMiddleware``. Callers never have
  to thread the ID manually — a service-layer helper called three
  frames deep from a route still emits the right ``request_id``.
* **Non-blocking.** Exceptions inside the helper are swallowed with a
  single error log. A broken log statement must never crash the
  underlying business action.
* **Redaction-safe.** Caller-supplied ``extra`` fields are filtered
  through ``_REDACTED_KEYS`` so a stray ``password`` or
  ``totp_code`` key never lands in log storage. The Sentry scrubber
  is a second line of defence; this is the first.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.middleware.request_id import get_current_request_id

log = logging.getLogger("security")

# Keys whose values are always redacted before leaving the process. The
# list mirrors the Sentry ``_SENSITIVE_KEYS`` set in main.py so an
# operator reviewing either output sees identical redaction behaviour.
_REDACTED_KEYS = frozenset({
    "password", "hashed_password", "token", "access_token", "refresh_token",
    "totp_code", "totp_secret", "api_key", "admin_key", "authorization",
    "cookie", "set-cookie", "stripe-signature", "secret",
})


def _redact(value: Any, _depth: int = 0) -> Any:
    """Redact sensitive keys from a value, descending into dicts and lists.

    Bounded recursion prevents a pathological ``extra`` (e.g. a circular
    reference leaking in via a caller bug) from consuming the event loop.
    """
    if _depth > 6:
        return "[truncated]"
    if isinstance(value, dict):
        return {
            k: ("[filtered]" if k.lower() in _REDACTED_KEYS else _redact(v, _depth + 1))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(v, _depth + 1) for v in value]
    return value


def log_security_event(
    event: str,
    *,
    actor_user_id: str | None = None,
    org_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    ip_address: str | None = None,
    outcome: str = "success",
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit a structured security event to stdout + Sentry breadcrumb.

    Parameters
    ----------
    event
        Dotted name describing the action, e.g. ``"auth.login_failed"``,
        ``"billing.plan_upgraded"``, ``"ip_allowlist.entry_added"``.
        Free-form; existing audit ``action`` strings are reused verbatim
        so dashboards can join log events to audit-log rows by this key.
    outcome
        ``"success"`` (default), ``"failure"``, or ``"denied"``. Lets
        a dashboard compute auth-failure rates without parsing event
        names.
    extra
        Arbitrary caller-supplied context. Filtered through the
        redaction pass before logging. Never put passwords, TOTP codes,
        or tokens here — the redactor will strip them, but the log
        statement also reaches stderr in dev so the habit matters.
    """
    try:
        request_id = get_current_request_id()
        payload: dict[str, Any] = {
            "event": event,
            "outcome": outcome,
            "request_id": request_id,
        }
        if actor_user_id is not None:
            payload["actor_user_id"] = actor_user_id
        if org_id is not None:
            payload["org_id"] = org_id
        if target_type is not None:
            payload["target_type"] = target_type
        if target_id is not None:
            payload["target_id"] = target_id
        if ip_address is not None:
            payload["ip_address"] = ip_address
        if extra:
            payload["extra"] = _redact(extra)

        # Serialise ourselves so the caller gets consistent JSON whatever
        # the root formatter does. The main.py JSON formatter re-quotes
        # ``msg`` as a Python-repr'd string — that still parses cleanly
        # in Datadog/Loki because the outer envelope is its own JSON.
        log.info(json.dumps(payload, default=str, sort_keys=True))

        # Sentry breadcrumb so a subsequent exception shows the full
        # trail of security-relevant decisions. No-ops when Sentry is
        # not configured.
        try:
            import sentry_sdk
            sentry_sdk.add_breadcrumb(
                category="security",
                message=event,
                level="warning" if outcome != "success" else "info",
                data={k: v for k, v in payload.items() if k != "extra"},
            )
        except Exception:
            pass
    except Exception as exc:  # noqa: BLE001 — observability must never crash caller
        # Fall back to a plain log line so the operator at least knows
        # something happened, even if the structured emit failed.
        log.error("log_security_event failed event=%s err=%s", event, exc)


def enrich_extra(
    extra: dict[str, Any] | None,
    request: Any | None,
) -> dict[str, Any]:
    """Return a new dict containing ``extra`` plus correlation fields.

    Pure function (no DB, no network, no ORM imports) so it can be unit-
    tested in isolation. Used by ``audit.log_action`` to inject
    correlation metadata into the audit row's ``extra`` column before
    the DB write.

    Rules:

    * Never mutates ``extra`` in place — caller may keep their reference.
    * ``request_id`` is pulled from the Item 30 ContextVar so service-
      layer calls several frames deep still get correlated.
    * ``request_id`` / ``user_agent`` are only written if the caller
      didn't already supply them (caller wins — a scheduler job
      correlating against an external job id keeps that id).
    * ``user_agent`` is capped at 512 chars so a pathological scanner
      banner doesn't bloat the JSONB column or the log line.
    * ``request`` is typed ``Any`` so callers don't have to import
      ``fastapi.Request`` in modules that never otherwise use FastAPI.
      We only ever read ``request.headers.get(...)`` from it.
    """
    enriched: dict[str, Any] = dict(extra or {})
    rid = get_current_request_id()
    if rid and "request_id" not in enriched:
        enriched["request_id"] = rid
    if request is not None and "user_agent" not in enriched:
        ua = request.headers.get("User-Agent")
        if ua:
            enriched["user_agent"] = ua[:512]
    return enriched
