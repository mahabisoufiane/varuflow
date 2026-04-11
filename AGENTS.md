# AGENTS.md — Varuflow Developer & AI Agent Guide

> This document is for human developers and AI coding agents working on Varuflow.
> Read CLAUDE.md for the full rule set. This guide covers the _how_ and _why_
> behind the architecture so you can make safe, consistent changes.

---

## Repository Layout

```
varuflow/
├── backend/          FastAPI app (Python 3.11+)
│   ├── app/
│   │   ├── config.py          Pydantic-settings; all env vars live here
│   │   ├── main.py            App factory, CORS, middleware, router mounts
│   │   ├── database.py        Async SQLAlchemy engine + session factory
│   │   ├── middleware/
│   │   │   ├── auth.py        JWT validation (Supabase + local-auth)
│   │   │   ├── plan_check.py  require_plan() dependency
│   │   │   └── rate_limit.py  IP rate limiter (global + per-path)
│   │   ├── models/            SQLAlchemy ORM models (one file per domain)
│   │   ├── routers/           One file per feature domain
│   │   └── schemas/           Pydantic request/response models
│   └── migrations/versions/   Alembic migrations (numbered v1–vN)
├── frontend/         Next.js 16 app (App Router, Turbopack)
│   └── src/
│       ├── app/[locale]/      Locale-aware routes
│       │   ├── (app)/         Authenticated app shell
│       │   ├── (marketing)/   Public marketing pages
│       │   └── auth/          Login, signup, MFA, password reset
│       ├── components/
│       │   ├── app/           App-shell components (AppShell, AiChat, …)
│       │   └── ui/            Generic design-system components
│       └── lib/
│           ├── api-client.ts  Single wrapper for all backend calls
│           └── supabase/      Supabase browser + server clients
└── mobile/           React Native / Expo (enterprise gate)
```

---

## Core Architectural Patterns

### 1. Auth Flow

```
Browser → Supabase Auth → JWT → FastAPI (middleware/auth.py)
                                    ↓
                          get_current_user()   extracts user_id
                                    ↓
                          get_current_member() resolves org_id
                                    ↓
                          Every router filters data by org_id
```

- **Never** query without `where(Model.org_id == org_id)` — multi-tenancy isolation
- **Portal tokens** (`type: "portal"` claim) are rejected by `get_current_user()`
- Dev bypass: `ENV=development` only; `DEBUG=True` has NO effect on auth gates

### 2. Plan Gating

```python
from app.middleware.plan_check import require_plan
from app.models.organization import OrgPlan

# Option A — gate the entire router (all endpoints inherit it)
router = APIRouter(dependencies=[Depends(require_plan(OrgPlan.PRO))])

# Option B — gate a single endpoint
@router.get("/export")
async def export(_plan: None = Depends(require_plan(OrgPlan.PRO)), ...):
```

PRO-gated routers: `ai_engine`, `recurring`, `integrations` (sync + chat)  
PRO-gated endpoints: `analytics /export/pdf`  
FREE endpoints: everything else

### 3. Database Conventions

- All migrations live in `backend/migrations/versions/` named `vN_description.py`
- `down_revision` must point to the previous migration's `revision` ID
- Foreign key columns **must** have a DB-level index (`op.create_index`)
- Use `with_for_update()` when checking counts before inserting (race-condition safe):

```python
org = await db.scalar(
    select(Organization).where(Organization.id == org_id).with_for_update()
)
```

- Models use `OrgPlan.PRO` / `OrgPlan.FREE` enum values — never raw strings `"PRO"` / `"FREE"`

### 4. Error Handling

Every endpoint must follow:

```python
@router.post("/endpoint")
async def my_endpoint(...):
    try:
        # logic
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.error("endpoint_name failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
```

Never let a raw traceback reach the client response.

### 5. Idempotency

Two patterns are used — apply the right one for each case:

| Pattern | Used for | File |
|---------|----------|------|
| DB unique constraint on `event_id` | Stripe webhooks | `billing.py` → `StripeProcessedEvent` |
| Consume-on-use (delete after read) | OAuth CSRF nonces | `integrations.py` → `FortnoxOAuthState` |
| SELECT before INSERT guard | AI send-reminder, draft-PO | `ai_engine.py` |

---

## Security Checklist (run before every PR)

```bash
# 1. No hardcoded production URL in frontend
grep -r "varuflow-production.up.railway.app" frontend/src
# Expected: 0 results

# 2. No wildcard CORS
grep -r 'allow_origins=\["\*"\]' backend/
# Expected: 0 results

# 3. No secrets in source
grep -rn "sk_live\|sk_test\|whsec_\|re_[a-zA-Z]" backend/app/
# Expected: 0 results

# 4. No OpenAI import in ai_engine.py (GPT-4o only in integrations.py)
grep -n "openai" backend/app/routers/ai_engine.py
# Expected: 0 results

# 5. TypeScript compiles clean
cd frontend && npx tsc --noEmit
```

---

## Adding a New Feature

### Backend — new router

1. Create `backend/app/routers/your_feature.py`
2. Add auth dependency to every endpoint: `ctx: tuple = Depends(get_current_member)`
3. Filter all queries: `.where(Model.org_id == _org_id(ctx))`
4. Add plan gate if PRO-only: `dependencies=[Depends(require_plan(OrgPlan.PRO))]`
5. Mount in `main.py`: `app.include_router(your_router)`
6. Create migration if new tables: `alembic revision --autogenerate -m "v<N>_your_feature"`
7. Add env vars to `backend/.env.example` and `config.py`

### Frontend — new page

1. Create `src/app/[locale]/(app)/your-page/page.tsx`
2. Use `api` from `@/lib/api-client` — never `fetch()` directly
3. Handle 401 by redirecting to `/${locale}/auth/login`
4. Add translations to all 4 locale files: `en.json`, `sv.json`, `no.json`, `da.json`
5. If PRO-only: wrap with `<PlanGate plan="PRO">…</PlanGate>`

---

## Known Gotchas

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| CORS blocks dashboard in prod | CORSMiddleware not first in middleware chain | In `main.py`, CORS must be `add_middleware` call #1 |
| Plan gate never fires | `OrgPlan.PRO` compared as string `"PRO"` (raw string) | Always use `OrgPlan.PRO` enum |
| Stripe webhook processed twice | No idempotency check | Insert `StripeProcessedEvent(event_id=...)` after processing |
| Rate limiter bypassed | `TRUST_PROXY=True` but app exposed directly | Set `TRUST_PROXY=False` when not behind Railway proxy |
| Session modal fires on network blip | `TOKEN_REFRESH_FAILED` treated as `SIGNED_OUT` | `_layout.tsx` explicitly ignores `TOKEN_REFRESH_FAILED` |
| `experimental.turbo` warning in Next.js | Wrong config key | Use `turbopack.resolveAlias`, never `experimental.turbo` |
| Docker module resolution broken | Stale `node_modules` volume | `docker volume rm varuflow_frontend_node_modules` |

---

## Environment Variables Quick Reference

| Variable | Where set | Purpose |
|----------|-----------|---------|
| `DATABASE_URL` | Railway | PostgreSQL connection string |
| `ENV` | Railway | `production` (never `development` on Railway) |
| `CORS_ORIGINS` | Railway | Comma-separated allowed origins |
| `SUPABASE_JWT_SECRET` | Railway | Verifies Supabase-issued JWTs |
| `STRIPE_WEBHOOK_SECRET` | Railway | Verifies Stripe webhook signatures |
| `PORTAL_JWT_SECRET` | Railway | Signs B2B portal tokens |
| `AUTH_JWT_SECRET` | Railway | Signs local-auth access tokens |
| `TRUST_PROXY` | Railway | `True` — Railway injects X-Forwarded-For |
| `NEXT_PUBLIC_API_URL` | Vercel | Points to Railway backend |

Full lists: `backend/.env.example`, `frontend/.env.local.example`

---

## Migration Naming Convention

```
v1  — initial_schema
v2  — <feature>
...
v9  — fortnox_oauth_csrf
v10 — stripe_idempotency
```

`down_revision` in each file must equal the `revision` of the previous file.
Always review the auto-generated diff before applying: `alembic upgrade head`.
