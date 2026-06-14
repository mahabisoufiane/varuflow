# KNOWN_LIMITS.md — Varuflow Architectural Limits

Known constraints that are **by design** in the current release. Each entry
documents what the limit is, when it becomes a problem, and the upgrade path.

---

## 1. In-memory rate limiter — does not work with multiple Railway replicas

**What:** `app/middleware/rate_limit.py` uses a `defaultdict` in the Python
process to count requests. Each Railway replica has its own counter.

**When it's a problem:** When Railway auto-scales to 2+ replicas, each
instance counts independently. Effective rate limit for one user becomes
`N × configured_limit` (where N = replica count). An org can brute-force
auth or hammer the AI endpoint at N times the allowed rate.

**Current mitigation:** Pin Railway to 1 replica (`replicas = 1` in service
settings). The in-process rate limiter works correctly at single-instance scale.

**Upgrade path (Phase 5 / C-1):** Replace the in-memory counter with a
Redis-backed implementation (`redis-py` `INCR` + `EXPIRE`). Add
`REDIS_URL` to env vars and `MANUAL_CONFIG.md`. Ticket: C-1 in PROD_AUDIT.md.

---

## 2. APScheduler uses in-memory job store — jobs lost on restart

**What:** `app/services/scheduler.py` uses APScheduler's default in-memory
job store. All 33 registered jobs are recurring (recreated at startup from
`create_scheduler()`), so restarts don't lose the schedule itself.

**When it's a problem:** If a one-off deferred job is ever added (e.g.,
"send follow-up in 24 h" triggered by a user action), a Railway deploy or
crash before the fire time silently drops it. No retry, no dead-letter queue.

**Current mitigation:** Only recurring jobs are used. Any deferred work uses
the `IdempotencyKey` table to record intent so a restart + re-run is
idempotent.

**Upgrade path (Phase 5 / M-6):** Configure `SQLAlchemyJobStore` using the
existing `DATABASE_URL` so job state survives restarts. Alternative: migrate
deferred work to Celery + Redis for a proper task queue.

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
