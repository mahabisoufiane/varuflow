# Audit & Logging Runbook (Item 30)

Varuflow maintains two complementary visibility surfaces for
security-sensitive operations:

1. **`audit_log` table** — durable, append-only, retained seven years
   for bokföringslagen compliance. Query target for forensic
   investigations and legal discovery.
2. **`security` stdout logger** — ephemeral JSON log lines emitted
   through the container's stdout and picked up by the log aggregator
   (Railway/Datadog/Loki/Sentry breadcrumbs). Query target for real-
   time dashboards, alerting, and incident response.

Every `log_action` call writes to both surfaces with an identical
correlation envelope (`request_id`, `user_agent`, `ip_address`,
`actor_user_id`, `org_id`). This is by design — a failed DB flush
still leaves a stdout trail, and a log-aggregator outage still leaves
a queryable DB row.

## Where the plumbing lives

| Component | File |
|-----------|------|
| Request-ID middleware | [backend/app/middleware/request_id.py](../../backend/app/middleware/request_id.py) |
| Audit helper | [backend/app/services/audit.py](../../backend/app/services/audit.py) |
| Observability helper | [backend/app/services/observability.py](../../backend/app/services/observability.py) |
| `audit_log` model | [backend/app/models/audit.py](../../backend/app/models/audit.py) |
| Unit tests | [backend/tests/test_observability.py](../../backend/tests/test_observability.py) |

## Request-ID propagation

The `RequestIdMiddleware` either accepts a client-supplied
`X-Request-ID` header (if it matches `[A-Za-z0-9_-]{8,64}`) or mints a
fresh UUID-v4. That ID is then:

* stored on `request.state.request_id` for route handlers,
* stored in the `request_id_ctx` `ContextVar` so service-layer code
  can retrieve it without threading `Request` through every function,
* tagged on the Sentry scope,
* echoed back on the response as `X-Request-ID`, and
* emitted on the per-request access log line in `main.py`.

Service code reads the correlation ID via:

```python
from app.middleware.request_id import get_current_request_id

rid = get_current_request_id()  # None outside an HTTP context
```

Scheduler jobs, management scripts, and tests that bypass the HTTP
middleware see `None`; the downstream helpers handle that by omitting
the `request_id` field rather than stamping a misleading value.

## Structured security events

```python
from app.services.observability import log_security_event

log_security_event(
    "auth.login_failed",
    outcome="failure",
    ip_address=request.client.host,
    extra={"email": body.email, "reason": "INVALID_CREDENTIALS"},
)
```

Emitted JSON payload (line-wrapped for readability):

```json
{
  "event": "auth.login_failed",
  "outcome": "failure",
  "request_id": "a1b2c3d4e5f6...",
  "ip_address": "203.0.113.5",
  "extra": {"email": "victim@example.com", "reason": "INVALID_CREDENTIALS"}
}
```

### Mandatory fields

* `event` — dotted name, e.g. `auth.login_failed`,
  `billing.plan_upgraded`, `ip_allowlist.entry_added`. Reuse the
  existing `action` strings from `log_action` so dashboards can join
  log lines to `audit_log` rows by this key.
* `outcome` — one of `"success"`, `"failure"`, `"denied"`. Lets the
  dashboard compute per-event failure rates without parsing event
  names.

### Optional fields

* `actor_user_id`, `org_id`, `target_type`, `target_id` — direct
  copies of the equivalent `audit_log` columns.
* `ip_address` — populated via `app.services.audit.get_client_ip` so
  TRUST_PROXY handling stays consistent with rate-limit attribution.
* `extra` — arbitrary caller-supplied context. **Do not** put
  passwords, TOTP codes, tokens, or cookies here; the redactor will
  strip them (see below), but the habit matters.

### Redaction

`log_security_event` runs its `extra` dict through `_redact` before
logging. Keys whose name matches `_REDACTED_KEYS` are replaced with
`[filtered]`; the redactor descends into nested dicts and lists but
caps recursion at depth 6 so a circular reference cannot stall the
event loop.

Sentry breadcrumbs emitted from the same call use the same payload
(minus the `extra` dict, to keep the breadcrumb size bounded).

## Audit-log auto-enrichment

`log_action(request=...)` calls `enrich_extra(extra, request)` before
the DB write. The helper (pure function in `observability.py`) adds
two correlation fields **unless the caller already supplied them**:

* `request_id` — from the `ContextVar`.
* `user_agent` — from `request.headers['User-Agent']`, capped at 512
  chars.

A scheduler job correlating an audit row to an external job id can
pre-populate `extra={"request_id": my_job_id}` and `enrich_extra`
leaves it alone.

## Querying the audit log

```sql
-- Recent mutations by a specific user:
SELECT created_at, action, target_type, target_id, extra
FROM audit_log
WHERE actor_user_id = '...'
ORDER BY created_at DESC
LIMIT 50;

-- All events tied to one request id (useful during incident review —
-- the request_id is in the JSONB ``extra`` column):
SELECT created_at, action, actor_user_id, target_type, ip_address, extra
FROM audit_log
WHERE extra->>'request_id' = '<request-id>'
ORDER BY created_at;

-- Failed logins in the last 10 minutes (outcome lives in the stdout
-- event, not the DB — pair with a log-aggregator query on
-- ``event:"auth.login_failed"`` for a complete picture):
SELECT created_at, ip_address, extra->>'email' AS email
FROM audit_log
WHERE action = 'auth.login_failed'
  AND created_at > now() - interval '10 minutes';
```

## Querying stdout events

Example Datadog/Loki filter:

```text
service:varuflow-api event:"auth.login_failed" outcome:"failure"
```

or to pivot on a single transaction across services:

```text
service:varuflow-api request_id:"a1b2c3d4e5f6..."
```

## Adding a new security event

1. If the event corresponds to a persistent state change (password
   reset, plan upgrade, team role change) **use `log_action`** — the
   audit row is mandatory and the stdout event is emitted as a
   mirror automatically.
2. If the event is diagnostic and not worth seven-year retention
   (login attempts, rate-limit denies, MFA challenges), call
   `log_security_event` directly. No DB row is written.
3. Pick an `event` string that uses dot-separated namespaces:
   `<subsystem>.<verb>` — e.g. `auth.login_succeeded`,
   `ip_allowlist.entry_removed`. Reuse subsystems that already exist
   rather than inventing synonyms (`auth.*`, `billing.*`,
   `ip_allowlist.*`, `team.*`).
4. Set `outcome` accurately so dashboard queries keep working.
5. Never put credentials in `extra`. The redactor will strip them but
   the habit matters.

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Log line has `"request_id": null` | Call happened outside an HTTP request (scheduler, test, script). | Expected; no action. |
| Audit row missing `request_id` in `extra` | Row written before Item 30 shipped. | Accept — the column is a rolling field, not a column. |
| Log aggregator shows only `event` + `outcome` | Route/router doesn't populate the optional fields. | Add them to the `log_security_event(...)` / `log_action(...)` call. |
| Redactor stripped a field I wanted to keep | Key name matched `_REDACTED_KEYS`. | Rename the key (e.g. `email_address` instead of `email` is fine — `email` is explicitly allowed; `password_hint` would be stripped because `password` substring matches via lowercase). |
| `sentry_sdk.add_breadcrumb` failing | Sentry SDK not initialised in this process. | No action — the helper swallows the exception; breadcrumbs are best-effort. |
