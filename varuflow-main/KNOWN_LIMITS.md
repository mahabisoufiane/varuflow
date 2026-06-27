# KNOWN_LIMITS.md — Varuflow Architectural Limits

Known constraints that are **by design** in the current release. Each entry
documents what the limit is, when it becomes a problem, and the upgrade path.

---

## 1. ~~In-memory rate limiter — does not work with multiple Railway replicas~~ ✅ RESOLVED (Phase 5 / C-1)

Redis sliding-window counter is now the default when `REDIS_URL` is set.
Falls back to in-memory for single-replica and local-dev environments.
Set `REDIS_URL` on Railway (add a Redis plugin) to enable multi-replica mode.
See `MANUAL_CONFIG.md` for setup instructions.

---

## 2. ~~APScheduler uses in-memory job store — jobs lost on restart~~ ✅ RESOLVED (Phase 5 / M-6)

`SQLAlchemyJobStore` (psycopg2) is now the default job store when `DATABASE_URL`
is set. Job metadata (next-run time, misfire state) is persisted in the
`apscheduler_jobs` table. Misfired jobs fire within their `misfire_grace_time`
window on the next restart. Falls back to in-memory for local dev / CI.

---

## 3. BankID integration uses the test environment by default

**What:** `settings.BANKID_API_URL` defaults to
`https://appapi2.test.bankid.com/rp/v6.0`. Real Swedish e-identification
requires a production Relying Party certificate issued by Finansiell
ID-Teknik BID AB.

**When it's a problem:** Any customer attempting to authenticate via BankID
in a production deploy will hit the test environment, which accepts only
BankID test identities (not real personal identity numbers).

**Current mitigation:** BankID auth returns 503 when `BANKID_CLIENT_CERT_PATH`
is empty, so the failure is explicit rather than silently accepting test BankIDs.

**Upgrade path:** Register as a Relying Party at
`https://www.bankid.com/en/utvecklare`. Supply `BANKID_API_URL`,
`BANKID_CLIENT_CERT_PATH`, and optionally `BANKID_CA_CERT_PATH` in Railway
Variables. See `backend/app/config.py` comments for the full runbook.

---

## 4. ~~`bcrypt < 4.0.0` pin~~ ✅ RESOLVED (Phase 4 / M-5)

Passlib removed; codebase now uses direct `bcrypt 4.x` API (`bcrypt.hashpw` /
`bcrypt.checkpw` / `bcrypt.gensalt`). Constraint updated to `bcrypt = ">=4.0.0"`.
Existing `$2b$12$...` hashes are fully compatible with bcrypt 4.x.

---

## 5. Postgres advisory locks are single-database — no cross-shard coordination

**What:** APScheduler job deduplication uses `pg_try_advisory_lock(lock_id)`.
This guarantees only one Railway replica runs each job per tick *within a single
Postgres instance*.

**When it's a problem:** If the architecture ever splits to multiple Postgres
primaries (sharding, multi-region), advisory locks would not coordinate across
databases.

**Current mitigation:** Single Postgres instance on Railway. Not a practical
concern at current scale.

**Upgrade path:** If sharding is ever required, move scheduler coordination to
a dedicated lock service (Redis `SET NX EX`, ZooKeeper, etc.).

---

*Last updated: 2026-06-14 (Phase 4 — Data Integrity)*
