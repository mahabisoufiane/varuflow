# PROD_AUDIT.md — Production Readiness Audit
**Date:** 2026-06-13  
**Auditor:** Claude Code (automated review of source + pip-audit output)  
**Scope:** varuflow-main/ — backend (FastAPI), frontend (Next.js), Dockerfile, CI, dependencies  
**Phase:** 0 — Audit only. No fixes applied.

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 4 |
| HIGH | 9 |
| MEDIUM | 11 |
| LOW | 7 |
| **Total** | **31** |

---

## CRITICAL

### C-1 — Rate limiter is per-process; broken with multiple Railway replicas
**File:** `backend/app/middleware/rate_limit.py` (comment in module docstring)  
**Detail:** The sliding-window counter lives in a `defaultdict` in the Python process. The code itself says *"Works for single-instance deployments; swap the counter for Redis when running multiple replicas."* If Railway auto-scales to 2+ instances, each instance has its own counter — rate limits effectively multiply by the replica count and per-org quotas stop working. An org could brute-force auth or hammer the AI endpoint at `N × limit` RPS.  
**Fix:** Replace the in-memory store with a Redis-backed counter (e.g., `redis-py` with `INCR` + `EXPIRE`). Add `REDIS_URL` to env vars and `MANUAL_CONFIG.md`.

### C-2 — PyJWT algorithm-confusion CVE (PYSEC-2026-179 / GHSA-xgmm-8j9v-c9wx)
**File:** system pip environment; verify in `backend/` Poetry venv  
**Detail:** The pip-audit scan found `pyjwt==2.12.1` with CVE-2026-179: verifiers supporting both asymmetric and HMAC algorithms allow an attacker to use the issuer's public key as the HMAC secret, forging arbitrary tokens. The app uses `python-jose` (not `pyjwt` directly), but `python-jose[cryptography]` may pull in `pyjwt` as a transitive dependency. **Must verify** with `cd backend && poetry run pip show pyjwt`. If present, upgrade to pyjwt>=2.13.0 by upgrading python-jose or pinning pyjwt directly.  
**Fix:** `cd backend && poetry run pip show pyjwt` — if installed, add `pyjwt = ">=2.13.0"` to pyproject.toml and run `poetry lock --no-update && poetry install`.

### C-3 — aiohttp cookie-jar arbitrary code execution (CVE-2026-34993)
**File:** system pip environment; verify in `backend/` Poetry venv  
**Detail:** pip-audit found `aiohttp==3.13.5` with CVE-2026-34993: `CookieJar.load()` with untrusted input may allow arbitrary code execution. aiohttp is a transitive dependency (via openai SDK or httpx). Verify with `poetry run pip show aiohttp`. If `>=3.14.0` is not installed, this is critical.  
**Fix:** Add `aiohttp = ">=3.14.0"` to pyproject.toml dev dependencies (or as an override) and `poetry lock`.

### C-4 — No CI gate for tenant isolation suite
**File:** `.github/workflows/ci.yml`  
**Detail:** The CI pipeline runs `pytest --tb=short -q` which catches all existing tests, but no dedicated tenant-isolation test suite exists yet (`tests/test_tenant_isolation.py` is absent). Without a focused cross-tenant IDOR test suite, a regression in any of the 280 routers could ship silently. This is the highest-risk surface.  
**Fix:** Phase 1 — create `tests/test_tenant_isolation.py` covering every router. Add it as a required CI step before deploy.

---

## HIGH

### H-1 — No HEALTHCHECK instruction in Dockerfile
**File:** `Dockerfile` (line ~24 — CMD line, no HEALTHCHECK before it); `backend/Dockerfile` same  
**Detail:** Both Dockerfiles are missing a `HEALTHCHECK` instruction. Railway and Docker Compose will not know when the container is ready or degraded. A container serving 500s on every request will be kept in the load-balancer rotation.  
**Fix:** Add before `CMD`:  
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```

### H-2 — No graceful SIGTERM shutdown
**File:** `Dockerfile` — `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`  
**Detail:** Uvicorn handles SIGTERM but the FastAPI lifespan context manager in `main.py` should explicitly drain in-flight APScheduler jobs and close the SQLAlchemy engine. Currently the lifespan's `finally` block (if present) must be verified. Railway sends SIGTERM before termination; without draining, background jobs (dunning sweeps, AI tasks) will be killed mid-execution.  
**Fix:** Add `scheduler.shutdown(wait=True)` and `await engine.dispose()` in the lifespan `finally` block; verify this runs on SIGTERM.

### H-3 — PyJWT DoS CVEs (PYSEC-2026-177, PYSEC-2026-178)
**File:** transitive dependency — verify with `poetry run pip show pyjwt`  
**Detail:** Two unauthenticated DoS vectors in pyjwt ≤2.12.1. PYSEC-2026-177: unbounded Base64URL decode on detached JWS. PYSEC-2026-178: JWKS endpoint hit on every unknown `kid` with no rate limiting. Even if the app doesn't use JWKS directly, pyjwt being present in the venv makes it reachable via python-jose.  
**Fix:** Same as C-2 — upgrade pyjwt to ≥2.13.0.

### H-4 — aiohttp cross-origin cookie leak (CVE-2026-47265)
**File:** transitive dependency via openai SDK  
**Detail:** Cookies set via the `cookies` parameter are forwarded after a cross-origin redirect in aiohttp ≤3.13.5. The app uses `httpx` for most external calls, but OpenAI's SDK may use aiohttp internally — any secrets passed via cookies would be leaked to a redirect target.  
**Fix:** Same as C-3 — pin aiohttp to ≥3.14.0.

### H-5 — Background scheduler jobs not audited for tenant isolation
**File:** `backend/app/services/scheduler.py`, `backend/app/routers/scheduler.py`  
**Detail:** APScheduler jobs (dunning sweeps, auto-reorder, AI sequences, cart recovery) run without a per-request auth context. If any job queries data without explicit `org_id` filtering, it could process one tenant's records for all tenants. Not yet reviewed systematically.  
**Fix:** Audit every scheduled function in `services/scheduler.py`. Ensure each query has `.where(Model.org_id == job_org_id)`. Add unit tests that seed two orgs and assert jobs don't bleed across.

### H-6 — No automated database backup script in repo
**File:** (missing — no `scripts/backup.py` or similar)  
**Detail:** No scripted, tested backup procedure exists in the repository. The `PROD_AUDIT.md` prompt identifies this as required: a backup script + documented, tested restore. Railway Postgres offers point-in-time recovery but it's not operator-runnable from the codebase.  
**Fix:** Phase 3 — write `scripts/backup.sh` (pg_dump → compressed → off-site store) and `scripts/restore.sh` with a sandbox-only guard. Document restore procedure in `OPERATIONS.md`.

### H-7 — `paramiko` SHA-1 algorithm allowed (CVE-2026-44405)
**File:** system pip environment; verify in Poetry venv  
**Detail:** pip-audit found `paramiko==4.0.0` allowing SHA-1 in rsakey.py. Paramiko is not in pyproject.toml directly. If it's a transitive dep, it's a HIGH finding; if system-only, it's out of scope. SHA-1 is broken for cryptographic use.  
**Fix:** `poetry run pip show paramiko` — if present, add `paramiko = ">=4.1.0"` (or whatever version patches this) as a dependency override. Track fix version in `KNOWN_LIMITS.md` until upstream releases.

### H-8 — CI deploy workflow is not gated on test pass + security scan
**File:** `.github/workflows/deploy.yml`  
**Detail:** Need to verify `deploy.yml` explicitly requires `ci.yml` to succeed before triggering. If deploy is triggered by push independently of ci.yml, a broken build can reach Railway. Also: no image vulnerability scan (e.g., `trivy` or `grype`) in the build pipeline.  
**Fix:** Add `needs: [backend, frontend]` to the deploy job in `deploy.yml`. Add Trivy scan step after Docker build.

### H-9 — Logging format is pseudo-JSON, not true structured JSON
**File:** `backend/app/main.py` lines ~18–32  
**Detail:** The logging config uses Python `logging.config.dictConfig` with a format string: `'{"time":"%(asctime)s","level":"%(levelname)s",...,"msg":%(message)r}'`. `%(message)r` uses Python `repr()` — log messages containing double quotes, newlines, or unicode will produce invalid JSON, breaking log aggregation tools (Datadog, Loki, CloudWatch Logs Insights).  
**Fix:** Replace the format string with `python-json-logger` (`pythonjsonlogger.jsonlogger.JsonFormatter`) which serializes fields properly. Or use `structlog` (already in system pip env) with a JSON renderer.

---

## MEDIUM

### M-1 — request_id not propagated into all log contexts
**File:** `backend/app/middleware/request_id.py`  
**Detail:** The middleware injects `X-Request-ID` into the response header but `request_id` is not added to Python logger's `extra` dict globally — so log lines from services called deeper in the stack won't carry the ID. Tenant/user correlation works only for lines explicitly logged with `extra={"org_id": ...}`.  
**Fix:** Use a `contextvars.ContextVar` populated by the middleware; add a logging filter that injects `request_id`, `org_id`, and `user_id` into every log record.

### M-2 — Soft delete not universal across all business-critical models
**File:** `backend/app/models/` — spot check needed across 160+ model files  
**Detail:** CLAUDE.md Rule 5 specifies soft delete on Customer, Invoice, Product, Organization. Some models (tasks, stock movements, audit entries) use hard delete. Without systematic soft-delete + retention, accidental deletes are unrecoverable.  
**Fix:** Audit which tables need soft delete. Add `deleted_at: datetime | None` column + Alembic migration for any missing ones. Add a base mixin in `database.py` that exposes `.soft_delete()` and a `is_deleted` filter.

### M-3 — No GDPR data-export endpoint verified
**File:** (expected in routers, unverified)  
**Detail:** Phase 7 requires GDPR Art. 20 portability export. Spot check did not find a `/api/me/export` or `/api/org/export` endpoint.  
**Fix:** Implement `GET /api/me/export` returning a machine-readable (JSON or CSV) dump of all PII for the requesting tenant. Add to Phase 7.

### M-4 — `/health/status-history` is public and unauthenticated
**File:** `backend/app/routers/health.py` — `@router.get("/health/status-history")`  
**Detail:** The status-history endpoint returns per-service uptime buckets and recent incidents with no authentication. While this is intentionally public (status page), it exposes infrastructure topology (which services exist, when they degraded) to unauthenticated callers. Low operational risk but worth documenting.  
**Fix:** Document as intentional in `OPERATIONS.md`. If incident descriptions should be private, gate this endpoint behind X-Admin-Token.

### M-5 — `bcrypt<4.0.0` pin creates version drift
**File:** `backend/pyproject.toml` — `bcrypt = ">=3.2.0,<4.0.0"`  
**Detail:** The pin prevents using bcrypt 4.x due to a passlib self-test failure. This is documented in the comment but passlib is no longer actively maintained. Remaining on bcrypt 3.x means missing security fixes in 4.x.  
**Fix:** Migrate away from passlib to direct bcrypt 4.x usage (`bcrypt.hashpw` / `bcrypt.checkpw`) or switch to `argon2-cffi` for password hashing. Unpin bcrypt after migration.

### M-6 — APScheduler uses in-memory job store
**File:** `backend/app/services/scheduler.py`  
**Detail:** APScheduler defaults to in-memory storage for jobs. On Railway, a restart (e.g., deploy, crash) drops all scheduled one-off jobs. Recurring jobs survive (they're recreated at startup) but deferred one-off jobs (e.g., "send follow-up in 24h") are lost silently.  
**Fix:** Configure APScheduler with a PostgreSQL job store (`SQLAlchemyJobStore` using the existing DB URL) so jobs survive restarts. Or migrate to a proper task queue (Celery + Redis).

### M-7 — No seed/demo script with production guard
**File:** (missing — no `scripts/seed.py`)  
**Detail:** The dev bypass auto-creates a demo org+member in `middleware/auth.py` (good), but there's no explicit seeding script with an `if ENV != "development": sys.exit(1)` guard. Phase 3 requires this.  
**Fix:** Create `scripts/seed_dev.py` with a hard guard: `assert os.getenv("ENV") == "development", "Refusing to seed non-dev environment"`.

### M-8 — Middleware order in `main.py` should be verified after every change
**File:** `backend/app/main.py`  
**Detail:** CORS must be first. The existing CLAUDE.md documents this and says it "broke production once." The middleware registration order is fragile — any developer adding `app.add_middleware(...)` at the top of a block can silently reorder it. No automated test asserts the order.  
**Fix:** Add a test `test_middleware_order.py` that introspects `app.middleware_stack` and asserts `CORSMiddleware` is outermost.

### M-9 — No PII inventory document
**File:** (missing — `DATA_PROCESSING.md` referenced in Phase 7)  
**Detail:** ~160 models, many containing customer PII (email, phone, address, TOTP secrets, financial data). No authoritative inventory maps which columns hold PII, what retention policy applies, or confirms encryption status.  
**Fix:** Phase 7 — generate `DATA_PROCESSING.md` by scanning all models for string columns that look like PII (`email`, `phone`, `address`, `name`, `iban`, etc.) and cross-referencing with `app/services/encryption.py`.

### M-10 — Connection pool shared with scheduler jobs
**File:** `backend/app/database.py`  
**Detail:** APScheduler jobs and HTTP request handlers share the same `async_session` pool (pool_size=10, max_overflow=20). Under load, long-running scheduler jobs can exhaust connections and starve HTTP handlers. No connection timeout is configured on the pool.  
**Fix:** Add `pool_timeout=30` and `connect_args={"command_timeout": 60}` to the engine. Consider a separate pool for the scheduler with lower max_overflow.

### M-11 — Frontend auth guards not systematically verified
**File:** `frontend/src/app/[locale]/` — 369 pages  
**Detail:** With 369 frontend routes, the audit can't verify every page has an auth guard. Missing guards could let an unauthenticated user render a page that silently fails to load data (less severe because the API will 401), but some pages may render cached data or expose layout structure.  
**Fix:** Add a Next.js middleware guard in `middleware.ts` that protects all `/(app)/` routes. Verify the portal and supplier-portal routes use their own separate guards.

---

## LOW

### L-1 — pip 26.1.1 CVE (PYSEC-2026-196)
**File:** system pip, not app dependency  
**Detail:** pip itself has a path traversal bug in entry-point installation. Only affects `pip install`, not runtime. Update system pip but this does not affect the running application.  
**Fix:** `pip install --upgrade pip` in Dockerfile (`RUN pip install --no-cache-dir -r requirements.txt && pip install --upgrade pip`) or pin the builder stage.

### L-2 — Calendly URLs hardcoded in config
**File:** `backend/app/config.py` lines 109–111  
**Detail:** `CALENDLY_DETRACTOR_URL`, `CALENDLY_CSM_URL`, `CALENDLY_FOUNDER_URL` default to `https://calendly.com/varuflow/...`. These are non-sensitive but if Calendly links change, a code deploy is required.  
**Fix:** Already env-var backed (pydantic-settings will read from env). No code change needed — just ensure Railway Variables are set if the defaults need to change.

### L-3 — Health endpoint leaks ENV name
**File:** `backend/app/routers/health.py` — `"env": settings.ENV`  
**Detail:** `/health` returns `"env": "production"` (or "development") to any unauthenticated caller. This leaks environment info useful to attackers. Minor issue — the response is intentional for ops tooling.  
**Fix:** Remove `env` from the unauthenticated response; move to the `deep` (admin-gated) block.

### L-4 — `RATE_LIMIT_DISABLED` flag could be accidentally enabled in production
**File:** `backend/app/config.py` — `RATE_LIMIT_DISABLED: bool = False`  
**Detail:** If `RATE_LIMIT_DISABLED=true` is set on Railway (e.g., accidentally left over from a debugging session), all rate limits silently no-op. The startup log emits a warning but does not abort.  
**Fix:** Add `RATE_LIMIT_DISABLED=True` to `validate_production_config()` as a hard failure (not just a warning).

### L-5 — No `KNOWN_LIMITS.md` file yet
**File:** (missing)  
**Detail:** Several constraints (in-memory rate limiter, single-replica APScheduler, BankID test env, bcrypt<4.0.0 pin) are known architectural limits that are currently only documented in comments and CLAUDE.md.  
**Fix:** Create `KNOWN_LIMITS.md` before Phase 6 and list each limit with: what it is, what the trigger for upgrading it is, and what the upgrade path looks like.

### L-6 — Docker image does not pin base Python version digest
**File:** `Dockerfile` — `FROM python:3.11-slim`  
**Detail:** `python:3.11-slim` is a mutable tag. A Dependabot update or `docker pull` can silently pull a different image. Deterministic builds should pin to a digest.  
**Fix:** Pin to `FROM python:3.11-slim@sha256:<digest>`. Update monthly via Dependabot Docker image scanning (already configured via `.github/dependabot.yml`).

### L-7 — No `OPERATIONS.md` runbook
**File:** (missing)  
**Detail:** Phase 4 requires a minimal runbook: how to read logs, what alerts mean, what each health check measures. Nothing exists yet.  
**Fix:** Phase 4 — create `OPERATIONS.md` after observability is hardened.

---

## Positive findings (already done well)

- `validate_production_config()` — hard startup failure on dangerous defaults or missing secrets. Well designed.
- `MemberCtx` — backward-compatible auth context wrapper avoids accidental org_id bypass.
- CORS allowlist from env; wildcard explicitly forbidden; CORS is first middleware.
- Portal JWT type claim (`type: "portal"`) is rejected on internal routes.
- `ALLOW_DEV_BYPASS` requires BOTH `ENV=development` AND the flag — double guard against prod bypass.
- Admin endpoints use `hmac.compare_digest` — constant-time comparison, no timing attack.
- `pool_pre_ping=True` + `pool_recycle=1800` on the engine — handles Railway's dropped connections.
- Stripe webhook signature verification present on both webhook endpoints.
- File uploads: MIME allowlist + 20 MB cap + Supabase Storage (not local disk) — correct approach.
- Sentry SDK initialized with FastAPI + SQLAlchemy integrations before routes mount.
- 173 Alembic migrations, autogenerated, covering 160+ models.
- CI pipeline: lint → migrations → tests → frontend build on every PR to main.
- `python-jose>=3.4.0` already pins the patched version for CVE-2024-33663/33664.

---

## Next step: Phase 1 — Tenant isolation

Start with `tests/test_tenant_isolation.py` covering all 280 routers. Do not fix anything until the full suite is written and run.
