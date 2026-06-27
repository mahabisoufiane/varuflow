# OPERATIONS.md — Varuflow runbook

Quick reference for on-call and day-to-day operations. For credential
setup see `MANUAL_CONFIG.md`. For known limitations see `KNOWN_LIMITS.md`.

---

## Logs

All logs are structured JSON written to stdout (captured by Railway).

### Reading logs in Railway

1. Open the Railway project → backend service → **Logs** tab.
2. Key fields in every line:

| Field | What it tells you |
|-------|-------------------|
| `request_id` | Trace a single HTTP request end-to-end |
| `org_id` | Which tenant generated this log line |
| `user_id` | Which authenticated user |
| `level` | `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `message` | Human-readable summary |

### Common log patterns

```
# A request came in
{"request_id": "abc", "method": "POST", "path": "/api/invoicing/customers", ...}

# Rate limit hit
{"level": "WARNING", "message": "Rate limit exceeded", "ip": "...", "path": "..."}

# Scheduler job skipped (another replica holds the lock)
{"level": "INFO", "message": "dunning_sweep skipped — another replica holds the lock"}

# A job ran successfully
{"level": "INFO", "message": "Low-stock alert sent to Nordisk Handel AB (3 items)"}

# Sentry error captured
{"level": "ERROR", "sentry_event_id": "...", "message": "..."}
```

---

## Health checks

### Endpoints

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /health` | None | Liveness probe — returns `{"status": "ok"}` or 503 |
| `GET /health/db` | None | Readiness probe — pings PostgreSQL |
| `GET /health/status-history` | **None (intentional — see M-4 note below)** | Public status page data |

**M-4 note:** `/health/status-history` is intentionally public. It powers the
customer-facing status page and contains per-service uptime percentages and
incident counts. It does **not** expose IP addresses, tenant data, or detailed
stack traces. If incident descriptions are ever added that contain internal
detail, gate this endpoint behind `X-Admin-Key`.

### Railway health check

Railway uses `/health` as the liveness probe (configured in `backend/Dockerfile`
`HEALTHCHECK` instruction). A 503 causes Railway to restart the container.

---

## Alerts

Sentry is the primary alerting channel. Configure:
1. **Sentry DSN** → set `SENTRY_DSN` environment variable on Railway.
2. **Alert rules** → in Sentry project settings, create rules for:
   - Any new `ERROR` issue → immediate notification
   - `CRITICAL` level → PagerDuty / Slack webhook

### What each alert means

| Pattern | Likely cause | First action |
|---------|-------------|--------------|
| `"migration failed"` at startup | New column type incompatible with existing data | Roll back deploy, check `alembic upgrade head` output |
| `"Rate limit exceeded"` spike | Bot / scraper / brute-force attempt | Check the `ip` field; block at Railway WAF if persistent |
| `"advisory lock"` spam | Multiple replicas winning the same scheduler job | Check replica count; advisory locks are the intended guard but logs should show only one winner per tick |
| `"Webhook retry sweep processed N"` | Failed webhook deliveries being retried | Check the external endpoint the webhook targets |
| `"Sentry" not receiving events` | `SENTRY_DSN` missing or wrong project | Verify env var on Railway |

---

## Scheduler jobs

Managed by APScheduler with a PostgreSQL job store (Phase 5 / M-6). Job metadata
is persisted in the `apscheduler_jobs` table. On restart, misfired jobs fire
within their `misfire_grace_time`.

### List of jobs

| Job ID | Trigger | What it does |
|--------|---------|-------------|
| `fortnox_sync` | Every 15 min | Refreshes Fortnox tokens |
| `low_stock_check` | Daily 08:00 | Emails orgs with products below reorder level |
| `weekly_digest` | Mon 08:00 | Sends weekly business summary |
| `token_cleanup` | Daily 03:00 | Deletes expired auth/portal tokens |
| `bokforing_reminder` | Jan 15 08:00 | Yearly bokföring nudge |
| `dunning_sweep` | Daily 09:00 | Emails overdue invoice customers |
| `push_stockout` | Daily 07:55 | Push alert for imminent stockouts |
| `push_overdue` | Daily 08:10 | Push alert for D+1 overdue invoices |
| `onboarding_reminder` | Daily 09:30 | One-shot reminder to new orgs |
| `webhook_retry` | Every 5 min | Retries failed webhook deliveries |
| `health_probe` | Every 5 min | Writes uptime row to `health_checks` |
| `stock_count_stuck` | Hourly | Resets stuck stock counts to DRAFT |
| `auto_reorder_check` | Daily 06:00 | Triggers auto-reorder for eligible orgs |
| `recurring_autosend` | Daily 07:00 | Generates and sends recurring invoices |
| `nightly_summary_sweep` | Every 15 min | Per-org nightly summary emails |
| `booking_reminders` | Every 5 min | Dispatches appointment reminders |
| `commission_monthly` | 1st of month 02:00 | Creates monthly commission runs |
| `giftcard_expiry` | Daily 09:00 | Expires stale gift cards + notifies customers |
| `exchange_rates` | Daily 06:00 | Fetches latest fiat exchange rates |
| `loyalty_expiry` | Daily 03:00 | Expires stale loyalty points |
| `segment_refresh` | Daily 03:30 | Refreshes AUTO customer segments |
| `campaign_dispatch` | Every 5 min | Fires scheduled campaigns |
| `review_request_sweep` | Daily 04:00 | Creates review requests for completed bookings |
| `subscription_pause_sweep` | Daily 10:00 | Auto-resumes and reminds paused orgs |
| `abandoned_cart_sweep` | Every 15 min | Sends abandoned cart recovery emails |
| `email_sequence_drip_sweep` | Hourly | Sends drip sequence steps |
| `quote_expiry_sweep` | Daily 02:00 | Expires sent/viewed quotes past valid_until |
| `trial_sweep` | Daily 02:00 | Reminds and downgrades expired trial orgs |
| `partner_commissions_sweep` | 1st of month 03:30 | Decrements partner referral months |
| `health_score_sweep` | Mon 04:00 | Calculates org health scores |
| `nps_reminder_sweep` | Daily 10:07 | Follow-up to unanswered NPS surveys |
| `trial_onboarding_sweep` | Hourly | Sends trial onboarding email sequences |

Multi-replica safety: each job acquires a PostgreSQL advisory lock before
running. Only the replica that wins `pg_try_advisory_lock()` executes; others
skip. See `backend/app/services/scheduler.py` for lock IDs.

---

## Redis (rate limiter)

When `REDIS_URL` is set, the rate limiter uses Redis for shared sliding-window
counters. Check Redis health:

```bash
redis-cli -u $REDIS_URL ping  # should return PONG
redis-cli -u $REDIS_URL info memory  # check used_memory
```

Keys are named `rl:<namespace>:<ip>` with TTL equal to the window duration.
If Redis is unreachable, the rate limiter automatically falls back to the
in-memory counter (safe for single-replica deployments).

---

## Database

### Migrations

Migrations run automatically at startup (`alembic upgrade head` in the
`lifespan` context in `app/main.py`). If a migration fails, the app starts
anyway but logs `"Alembic migration failed — continuing startup anyway."`.

To run manually:
```bash
cd backend
poetry run alembic upgrade head      # apply pending migrations
poetry run alembic current           # show current revision
poetry run alembic history --verbose # list all revisions
```

### Backups

The backup script is at `scripts/backup_db.sh`. Run via cron or Railway
scheduled service. Backs up to the path in `BACKUP_DIR` env var.

### Connection pool

- `pool_size=10`, `max_overflow=20`, `pool_timeout=30s`
- Per-statement timeout: `command_timeout=60s`
- Pool recycle: every 30 min (`pool_recycle=1800`)

If you see `TimeoutError: QueuePool limit of size 10 overflow 20 reached`,
increase `pool_size` or investigate long-running queries with:
```sql
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY duration DESC;
```

---

## Deployments

### Normal deploy

1. Push to `main` → CI runs (lint → test → build → tenant isolation).
2. CI passes → deploy workflow triggers automatically (see `.github/workflows/deploy.yml`).
3. Railway zero-downtime deploy: new container starts, migrations run, old container stops.

### Rollback

```bash
# Roll back to previous Railway deploy
railway rollback  # in Railway CLI

# Or: find the previous deployment in Railway dashboard → Deployments → Redeploy
```

### Maintenance mode (read-only)

Flip `READONLY_MODE=true` in Railway Variables to put the app in read-only mode.
All write endpoints return 503 with `{"code": "READONLY_MODE"}`. Safe methods
(GET, HEAD, OPTIONS) and Stripe webhooks continue to work.

Turn off by setting `READONLY_MODE=false`.

---

## Docker image pinning (L-6)

The backend `Dockerfile` uses `python:3.11-slim` (mutable tag). Dependabot is
configured to open weekly PRs when the tag's underlying image changes. To pin
to a digest for fully reproducible builds:

```bash
# Get the current digest
docker pull python:3.11-slim
docker inspect python:3.11-slim | jq -r '.[0].RepoDigests[0]'
# → python:3.11-slim@sha256:<64-char-hex>

# Then replace in Dockerfile:
FROM python:3.11-slim@sha256:<64-char-hex> AS builder
FROM python:3.11-slim@sha256:<64-char-hex>
```

Update the digest monthly alongside Dependabot's suggestions.
