# Backup & Disaster Recovery Runbook

> Owner: infra@varuflow.se — update this page whenever the backup strategy
> changes. Last reviewed: 2026-04-21.

Varuflow's source of truth is the Railway-managed PostgreSQL instance.
Everything else (Supabase Auth, Stripe, Fortnox) is a secondary store we
can reconnect to as long as the Postgres data is intact.

---

## 1. What is backed up

| Store | Owner | Backup method | Retention |
|-------|-------|---------------|-----------|
| Railway Postgres | Railway | Automatic daily snapshots + 7-day PITR | 7 days |
| Repository | GitHub | `origin/main` + tagged releases | indefinite |
| Supabase Auth users | Supabase | Daily snapshot (Supabase → Backups) | 7 days |
| Stripe data | Stripe | Stripe retains; replayable via webhook re-ingest | indefinite |

**Not backed up** (transient / reconstructable):
- Redis cache (none today — in-memory rate limiter only)
- APScheduler in-memory job state (rebuilt at boot)
- `localStorage` on client devices (chat history, UI prefs)

---

## 2. Daily verification (automated)

A scheduled CI job (`.github/workflows/backup-check.yml` — TODO) pings
`/api/health` every 15 minutes. On failure it alerts `infra@varuflow.se`.
Backups themselves are verified by Railway's snapshot UI; once a month an
on-call engineer performs the restore drill below.

---

## 3. Restore drill (monthly)

Goal: prove we can restore from yesterday's snapshot within 30 minutes.

1. **Create a staging Postgres** in the Railway project.
2. **Restore snapshot** — pick yesterday's snapshot from Railway's Backups
   tab → "Restore to new service". Name it `postgres-drill-YYYYMMDD`.
3. **Get its connection string** from the new service's Variables tab.
4. **Spin up a disposable backend**: `railway run --service backend -- \
   DATABASE_URL=<drill-url> alembic current` — confirms schema version.
5. **Sanity-query**:
   ```bash
   psql <drill-url> -c "SELECT COUNT(*) FROM organizations"
   psql <drill-url> -c "SELECT id, invoice_number, total_sek \
                        FROM invoices ORDER BY created_at DESC LIMIT 5"
   ```
6. **Delete** the drill Postgres service when done.
7. Record the outcome (duration, any issues) in
   `docs/operations/drill-log.md`.

---

## 4. Real incident — full restore procedure

**Declare the incident** in #incidents with severity tag. Acknowledge the
affected users via status page if the outage is > 10 minutes.

### Step-by-step

1. **Freeze writes** — pause Railway deploys and set
   `BACKEND_READONLY=true` (TODO) so the API returns 503 on mutating
   verbs. This prevents split-brain between old and restored data.
2. **Pick the target snapshot** — the latest snapshot before the incident
   started. Railway's Backups tab lists timestamps in UTC.
3. **Restore to a new service** — click "Restore to new service". DO NOT
   restore in-place; we want the old service kept for forensics.
4. **Verify schema** — `alembic current` on the restored DB should match
   the current code's head revision. If behind, run `alembic upgrade head`
   inside a temporary backend container against the restored URL.
5. **Point the backend at the restored DB** — update `DATABASE_URL` in the
   backend's Railway Variables; redeploy.
6. **Smoke test**:
   ```bash
   curl https://varuflow-production.up.railway.app/api/health
   # expect: {"status":"ok","database":"ok",...}
   ```
   Plus a login + list-invoices flow in the UI.
7. **Unfreeze writes**, announce resolution, take the old DB offline after
   24 hours of stable operation.

---

## 5. Partial restore (single-org recovery)

If a single customer reports data loss (e.g. accidental GDPR deletion, bug
wiped their customer list), we restore only that org's rows instead of
rolling back the whole database.

1. Restore the nearest snapshot to a drill Postgres as above.
2. Identify `org_id` from the user's email / signed support ticket.
3. Run the export script (TODO: `scripts/export_org.py`) against the drill
   DB to produce a JSON dump matching the `/api/gdpr/export` schema.
4. Use the import script (TODO: `scripts/import_org.py`) to merge those
   rows back into production with `ON CONFLICT DO NOTHING` semantics.
5. Email the customer a summary of what was restored.

---

## 6. Checklist additions for infrastructure changes

Whenever someone changes the backup story, update all of:
- [ ] This runbook.
- [ ] [SECURITY.md](../SECURITY.md) accepted-risk table.
- [ ] `.github/workflows/backup-check.yml` cron if the verification
      cadence changes.
- [ ] Railway project → Backups → retention policy.

## 7. Bokföringslagen retention

Accounting records (invoices, line items, payments, POS sales) MUST be
retained for **7 years** under Swedish bokföringslagen 7 kap. 2 §. The
backup retention window above (7 days) is for disaster recovery — it is
**not** sufficient for statutory retention. Long-term retention is
enforced by the database row lifecycle itself:

- Invoices are never hard-deleted in production code.
- GDPR `/api/gdpr/organization` performs logical anonymisation and leaves
  rows addressable. See [backend/app/routers/gdpr.py](../backend/app/routers/gdpr.py).

If a schema migration ever drops a column used by an accounting record,
that migration **must** include a data-preservation step (copy to a
`*_archive` table) before the drop.
