
# CLAUDE.md — Varuflow Codebase Reference
# Read this before touching any code. Derived from the actual source.

---

## Architecture

**Varuflow** is a multi-tenant B2B SaaS Business OS for Nordic SMBs.

| Layer | Tech | Host |
|-------|------|------|
| Backend | FastAPI 0.136 · Python 3.11 · SQLAlchemy 2 async · Alembic · APScheduler | Railway |
| Database | PostgreSQL (via asyncpg) · pool_size=10 max_overflow=20 | Railway Postgres |
| Auth | Supabase JWT (HS256) + local-auth fallback (python-jose) | Supabase |
| Frontend | Next.js 16 (App Router + Turbopack) · TypeScript | Vercel |
| Error tracking | Sentry SDK (FastAPI + SQLAlchemy integrations) | sentry.io |
| Rate limiting | slowapi + custom in-memory middleware (single-instance only) | in-process |
| File storage | Supabase Storage via REST | Supabase |
| Payments | Stripe (two integrations: SaaS billing + storefront) | Stripe |
| Email | Resend or SMTP | configured via env |

URLs: API → `https://varuflow-production.up.railway.app` · Web → `https://varuflow.vercel.app`

---

## Repository layout

```
varuflow-main/
├── backend/
│   ├── app/
│   │   ├── config.py          # pydantic-settings; all env vars; startup validation
│   │   ├── database.py        # async engine + session factory + Base
│   │   ├── main.py            # FastAPI app, middleware order, lifespan, router mounts
│   │   ├── middleware/
│   │   │   ├── auth.py        # JWT decode, get_current_user, get_current_member, MemberCtx
│   │   │   ├── plan_check.py  # require_plan / require_module FastAPI deps
│   │   │   ├── rate_limit.py  # in-memory sliding-window limiter + per_org_rate_limit dep
│   │   │   ├── request_id.py  # injects X-Request-ID on every request
│   │   │   └── readonly.py    # READONLY_MODE flag → 503 on writes
│   │   ├── models/            # 160+ SQLAlchemy ORM models, one file per domain
│   │   ├── routers/           # 280 router files; each scopes every query by org_id
│   │   ├── schemas/           # Pydantic v2 in/out schemas
│   │   └── services/          # Domain logic (auth, email, PDF, audit, etc.)
│   ├── migrations/            # 173 Alembic revisions
│   ├── tests/                 # 127 test files · 2747 passing · pytest-asyncio
│   └── pyproject.toml         # Poetry; test runner; Ruff config
├── frontend/src/              # Next.js App Router
│   ├── app/[locale]/          # All locale routes (en/sv/no/da)
│   ├── lib/api-client.ts      # Centralized fetch wrapper — use this for all API calls
│   └── lib/supabase/          # Lazy singleton Supabase client
└── .github/workflows/         # ci.yml (lint→test→build), deploy.yml, security.yml
```

---

## Running the project

```bash
# Backend (requires PostgreSQL)
cd backend
poetry install
alembic upgrade head
poetry run uvicorn app.main:app --reload --port 8000

# Tests (requires docker compose up db)
poetry run pytest --tb=short -q

# Lint
poetry run ruff check app

# Frontend
cd frontend
npm install --legacy-peer-deps   # required — ESLint peer conflict with Next 16
npm run dev                       # Turbopack

# Docker (full stack)
docker compose up
```

---

## Tenant isolation — the most critical invariant

Every query that touches business data MUST filter by `org_id`. Use the `scoped_select` choke point from `app/database.py`:

```python
from app.database import scoped_select

# Correct — always scoped:
ctx: tuple = Depends(get_current_member)
_, member = ctx
org_id = member.org_id          # always from the authenticated JWT, never from request body/path
result = await db.execute(
    scoped_select(Product, org_id).where(Product.id == product_id)
)

# WRONG — do not do this without a comment explaining why:
result = await db.execute(select(Product).where(Product.id == product_id))
```

`scoped_select(Model, org_id)` is defined in `app/database.py`. It returns a SQLAlchemy `Select` pre-filtered by `org_id`. It is the **mandatory default** for all tenant data queries. Using bare `select()` on a tenant model is a code smell that must be called out in review.

**Never trust a client-supplied org_id.** Always derive it from `get_current_member`.
The `MemberCtx` wrapper in `middleware/auth.py` supports both dict and tuple access for backward compat.

The tenant isolation regression suite is at `tests/test_tenant_isolation.py` and runs in CI.

---

## Critical rules (non-negotiable)

1. **CORS** — `CORSMiddleware` must be the **first** middleware in `main.py`. Never `allow_origins=["*"]`.
2. **JWT** — `ENFORCE_JWT_SIGNATURE=True` in production. Portal tokens (`type: "portal"`) are rejected by internal routes.
3. **Secrets** — all secrets via env vars. `validate_production_config()` runs at startup and refuses to boot on dangerous defaults or missing required vars.
4. **Dev bypass** — requires BOTH `ENV=development` AND `ALLOW_DEV_BYPASS=True`. Railway must always have `ENV=production`.
5. **Rate limiter** — in-memory only; does not share state across Railway replicas. Swap to Redis before horizontal scaling.
6. **AI router** — `ai_engine.py` is rules-based, zero OpenAI calls. GPT-4 only in the dedicated integrations router.
7. **Stripe webhooks** — always verify signature before processing.
8. **Migrations** — `alembic upgrade head` runs in the startup lifespan. Never drop columns without a data backup step.
9. **Uploads** — MIME allowlist + 20 MB limit enforced in `routers/uploads.py`; files land in Supabase Storage (not local disk).
10. **No raw SQL with user input** — always SQLAlchemy ORM or `text()` with bound params.

---

## Required env vars (production)

Validated at startup in `app/config.py → validate_production_config()`. Missing values abort boot.

| Var | Purpose |
|-----|---------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SUPABASE_URL / SERVICE_KEY / JWT_SECRET` | Supabase project |
| `AUTH_JWT_SECRET / PORTAL_JWT_SECRET` | Local + portal JWT signing |
| `PII_ENCRYPTION_KEY` | Fernet key for PII at rest |
| `FORTNOX_ENCRYPTION_KEY` | Fernet key for Fortnox OAuth tokens (if Fortnox enabled) |
| `STRIPE_SECRET_KEY / WEBHOOK_SECRET / PRO_PRICE_ID` | Billing |
| `STRIPE_STOREFRONT_WEBHOOK_SECRET` | Storefront Stripe webhooks |
| `RESEND_API_KEY` | Transactional email |
| `ADMIN_API_KEY` | Admin-only endpoints (X-Admin-Key header) |
| `SENTRY_DSN` | Error tracking (warning only if missing) |
| `CORS_ORIGINS` | Explicit allowlist, no wildcard |

See `backend/.env.example` and `MANUAL_CONFIG.md` for full list and generation instructions.

---

## Definition of production-ready

Varuflow is production-ready when:

- [ ] No CRITICAL or HIGH audit items remain open
- [ ] Tenant isolation test suite is green and runs in CI
- [ ] Every secret is an env var with startup validation enforced
- [ ] Health checks (`/health`, `/health/db`) respond correctly from Railway
- [ ] Sentry DSN is configured and receiving events
- [ ] Structured logs include request_id + org_id + user_id on every line
- [ ] CI blocks merge on: lint failure · test failure · tenant-isolation failure · build failure
- [ ] Backups restore successfully into a scratch database
- [ ] Rate limiter backed by Redis (before multi-replica Railway deployment)
- [ ] A new customer can be onboarded without a developer touching the database

---

## Known limits (document, don't silently work around)

- Rate limiter is in-memory → does not work with >1 Railway replica. Pin replicas to 1 or swap to Redis.
- `bcrypt<4.0.0` pinned to avoid passlib incompatibility — see pyproject.toml comment.
- BankID requires a production relying-party cert from Finansiell ID-Teknik BID AB; defaults to test env.
- No Redis instance configured by default; APScheduler and rate limiter are single-process.
