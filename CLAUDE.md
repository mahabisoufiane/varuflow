# CLAUDE.md — Varuflow Project Rules
# ⚠️ READ THIS ENTIRE FILE BEFORE TOUCHING ANY CODE.
# These rules are NON-NEGOTIABLE. Verify every item before and after every change.

---

## What Is This Project

Varuflow is a B2B SaaS for Nordic wholesalers (Sweden/Norway/Denmark).
Stack: Next.js 16 (App Router, Turbopack) + FastAPI (Python 3.11+) + PostgreSQL + Supabase Auth.
Frontend on Vercel → https://varuflow.vercel.app
Backend on Railway → https://varuflow-production.up.railway.app
Monorepo: /frontend (Next.js) + /backend (FastAPI)

---

## 🔴 RULE 1 — CORS (Most Critical — Already Broke Production Once)

CORS is the #1 production killer for this project. Verify on EVERY backend change.

File to check: `backend/app/main.py`

Required configuration (must match exactly):
```python
from fastapi.middleware.cors import CORSMiddleware
import os

origins = os.getenv("CORS_ORIGINS", "https://varuflow.vercel.app").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    max_age=3600,
)
```

Rules:
- CORSMiddleware MUST be the FIRST middleware registered — before auth, before logging, before anything
- NEVER use allow_origins=["*"] — this is forbidden in production
- CORS_ORIGINS env var must be set on Railway: https://varuflow.vercel.app
- After any main.py change, grep for middleware order and confirm CORS is first

Checklist:
- [ ] CORSMiddleware present in main.py
- [ ] CORSMiddleware is first (line order before all other add_middleware calls)
- [ ] allow_origins reads from CORS_ORIGINS env var
- [ ] OPTIONS is in allow_methods
- [ ] CORS_ORIGINS is in backend/.env.example

---

## 🔴 RULE 2 — AUTHENTICATION & AUTHORIZATION

Every route in every router MUST be protected. No exceptions without explicit documentation.

Backend auth file: `backend/app/middleware/auth.py`

Rules:
- Every router endpoint must have the auth dependency injected
- Dev bypass (ENV=development) is ONLY for local dev — never deploy with ENV=development to Railway
- Every data query MUST filter by org_id — users must never see another org's data
- Portal routes (/api/portal/*) use a SEPARATE JWT with `type: "portal"` claim
- Portal tokens must NEVER be accepted by internal routes
- Check: does `auth.py` validate the `type` claim to block portal tokens on internal routes?

Auth dependency pattern (use in every router):
```python
async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    # validates Supabase JWT, extracts user_id + org_id
    # raises 401 if invalid
```

Checklist:
- [ ] Every new endpoint has auth dependency
- [ ] Every DB query filters by org_id
- [ ] No endpoint returns data from a different org
- [ ] Portal JWT validated separately with PORTAL_JWT_SECRET
- [ ] ENV=development is NOT set on Railway variables

---

## 🔴 RULE 3 — ERROR HANDLING

Every API endpoint must handle errors. No naked exceptions allowed.

Required pattern for every endpoint:
```python
@router.get("/endpoint")
async def my_endpoint(...):
    try:
        # logic here
        return result
    except HTTPException:
        raise  # re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"endpoint_name failed: {str(e)}", extra={"org_id": org_id})
        raise HTTPException(status_code=500, detail="Internal server error")
```

HTTP status codes — use these exactly:
- 401 → unauthenticated (no/invalid token)
- 403 → unauthorized (authenticated but not allowed)
- 404 → resource not found
- 422 → validation error (Pydantic handles automatically)
- 500 → unexpected server error

Error response format — always JSON:
```json
{ "detail": "Human readable message", "code": "OPTIONAL_ERROR_CODE" }
```

Rules:
- NEVER let a stack trace reach the client response
- NEVER return HTML for an error from the FastAPI backend
- Background tasks (if added) must have retry with exponential backoff
- Log every error with: timestamp, org_id, user_id, endpoint, error message

Checklist:
- [ ] Every new endpoint has try/except
- [ ] All errors return JSON
- [ ] No stack traces in API responses
- [ ] Errors are logged with structured fields

---

## 🔴 RULE 4 — ENVIRONMENT VARIABLES

Rules:
- NEVER hardcode any URL, secret, key, or credential in any .py or .ts/.tsx file
- NEVER commit .env or .env.local (both are in .gitignore — verify)
- Every new env variable must be added to BOTH:
  1. `backend/.env.example` (with placeholder value, no real value)
  2. `frontend/.env.local.example` (same rule)
  3. Railway Variables dashboard (backend vars)
  4. Vercel Environment Variables dashboard (frontend vars)

Required backend env vars (all must exist in Railway):
DATABASE_URL
ENV=production
SUPABASE_URL
SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_JWT_SECRET
RESEND_API_KEY
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
OPENAI_API_KEY
PORTAL_JWT_SECRET
PORTAL_BASE_URL=https://varuflow.vercel.app
FORTNOX_CLIENT_ID
FORTNOX_CLIENT_SECRET
CORS_ORIGINS=https://varuflow.vercel.app

text

Required frontend env vars (all must exist in Vercel):
NEXT_PUBLIC_API_URL=https://varuflow-production.up.railway.app
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY

text

Checklist:
- [ ] No hardcoded URLs in any file
- [ ] grep -r "localhost:8000" frontend/src → must return 0 results in prod code
- [ ] grep -r "sk_live\|sk_test\|whsec_\|re_" backend/app → must return 0 results
- [ ] .env and .env.local are in .gitignore

---

## 🟠 RULE 5 — DATABASE

File: `backend/app/models/` and `backend/app/database.py`

Rules:
- Every model change requires an Alembic migration: `alembic revision --autogenerate -m "description"`
- Every migration must be tested with `alembic upgrade head` before pushing
- Foreign key columns must have DB-level indexes
- NEVER write raw SQL with user input — always use SQLAlchemy ORM or parameterized queries
- Soft deletes on: Customer, Invoice, Product, Organization (add `deleted_at` column, never hard delete)
- All list endpoints must have pagination (LIMIT + OFFSET) — NEVER return unlimited rows
- Connection pool must be configured in `database.py` (pool_size=10, max_overflow=20)

Migration command:
```bash
cd backend && alembic revision --autogenerate -m "your description"
# Review the generated file before applying
alembic upgrade head
```

Checklist:
- [ ] New model fields have migrations
- [ ] New FK columns have indexes
- [ ] No SELECT * without LIMIT on user-facing endpoints
- [ ] No raw SQL with f-strings or % formatting

---

## 🟠 RULE 6 — FRONTEND API CALLS

File: `frontend/src/lib/api-client.ts` — ALL backend calls must go through this client.

Rules:
- NEVER hardcode `https://varuflow-production.up.railway.app` in any component
- Always use `process.env.NEXT_PUBLIC_API_URL` via the api-client
- Every fetch call must have try/catch with user-facing error display (toast or error state)
- Every fetch call must handle: network error, 401 (redirect to login), 403, 404, 500
- On 401 response → clear auth state and redirect to `/[locale]/auth/login`

Required pattern for every data-fetching component:
```typescript
try {
  const data = await apiClient.get('/api/endpoint')
  setData(data)
} catch (error) {
  if (error.status === 401) {
    router.push(`/${locale}/auth/login`)
  } else {
    toast.error('Something went wrong. Please try again.')
  }
}
```

Checklist:
- [ ] grep -r "varuflow-production.up.railway.app" frontend/src → must return 0 results
- [ ] Every new page component has error handling on data fetch
- [ ] 401 responses redirect to login
- [ ] No console.log with token, password, or user PII

---

## 🟠 RULE 7 — SUPABASE AUTH (Known Problem Area)

Known errors and their fixes (DO NOT reintroduce these):

| Error | Cause | Fix |
|-------|-------|-----|
| `supabase.auth.signInWithPassword is not a function` | Supabase client is null/stub | Check isSupabaseConfigured() guard before calling any auth method |
| `@supabase/ssr: URL and API key required` | Missing env var | Check NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in Vercel |
| `localhost:9999/auth/v1/token ERR_CONNECTION_REFUSED` | Wrong SUPABASE_URL pointing to local | Set correct hosted Supabase URL in Vercel env vars |

Rules:
- Always check `isSupabaseConfigured()` before calling Supabase client methods
- Use the lazy singleton (Proxy pattern already in `frontend/src/lib/supabase/client.ts`) — do not create new instances
- `reactStrictMode: false` must stay in next.config.mjs (prevents GoTrue double-init AbortError)
- NEVER import from `@supabase/supabase-js` directly in app code — always use `src/lib/supabase/client.ts`

---

## 🟠 RULE 8 — NEXT.JS / VERCEL SPECIFIC

File: `frontend/next.config.mjs`

Rules:
- Turbopack must stay as default (`next dev` without `--webpack`)
- `turbopack.resolveAlias` must be used (not `experimental.turbo`) — already handled in config, do not regress this
- `npm install --legacy-peer-deps` must be used — ESLint peer dep conflict with Next 16 exists
- Portal routes (`/portal/*`) must be excluded from next-intl locale middleware — already in `middleware.ts`, verify after any middleware changes
- Every new locale route must be added to `frontend/messages/en.json`, `sv.json`, `no.json`, `da.json`

Known Docker issue:
- If `Module not found: Can't resolve 'react-is'` → run `docker volume rm varuflow_frontend_node_modules`
- `docker compose restart` does NOT apply env var changes — always use `docker compose up -d --force-recreate`

Checklist:
- [ ] New pages have translations in all 4 locale files (en, sv, no, da)
- [ ] Portal paths are excluded from locale middleware
- [ ] next.config.mjs does not use experimental.turbo key
- [ ] `customers/new` and all `[id]` routes exist as proper page.tsx files (the 404 on /en/customers/new is a missing page bug)

---

## 🟠 RULE 9 — STRIPE (Two Separate Stripe Integrations)

Varuflow has TWO Stripe integrations — do not confuse them:

1. **Customer invoice payments** (`/api/invoicing/` → creates payment links for wholesale customers)
2. **Varuflow SaaS billing** (`/api/billing/` → Stripe subscriptions for Varuflow's own plans)

Rules for both:
- Webhook endpoint must verify Stripe signature BEFORE processing any event:
```python
stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
```
- NEVER process a webhook without signature verification
- Failed subscription payment → implement grace period (do not cut off access immediately)
- Plan limits must be enforced at API level in the router — not just hidden in the frontend
- STRIPE_WEBHOOK_SECRET must be the correct secret for each webhook endpoint (Railway env)

Checklist:
- [ ] Both webhook endpoints verify Stripe signature
- [ ] Plan limits checked in backend routers, not just UI
- [ ] Webhook returns 200 quickly (offload processing to background if needed)

---

## 🟠 RULE 10 — AI ENGINE

File: `backend/app/routers/ai_engine.py`

Rules:
- AI action cards (`GET /api/ai/cards`) are rules-based — NO OpenAI calls here, pure SQL + Python
- GPT-4o chat is ONLY in `integrations.py` → `/api/integrations/chat`
- OpenAI calls must have try/except — if OpenAI is down, return a graceful fallback message (do not 500)
- Chat history stays in localStorage — never store user chat messages in the DB
- AI actions (send-reminder, draft-PO) must be idempotent — calling twice must not send 2 emails or create 2 POs

Checklist:
- [ ] ai_engine.py has zero OpenAI imports
- [ ] GPT-4o call has try/except with fallback response
- [ ] send-reminder action is idempotent
- [ ] draft-PO action is idempotent

---

## 🟡 RULE 11 — SECURITY HEADERS & PRODUCTION CONFIG

File: `backend/app/main.py`

Required security headers on every response:
```python
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

# Add after CORS middleware:
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response
```

Production config rules:
- `DEBUG=false` and `ENV=production` on Railway — verify in Railway Variables
- Uvicorn must NOT use `--reload` on Railway start command
- `PORTAL_BASE_URL` must be `https://varuflow.vercel.app` on Railway (not localhost)

---

## 🟡 RULE 12 — HEALTH CHECK

File: `backend/app/routers/health.py`

The health endpoint must verify ALL dependencies:
```python
@router.get("/api/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "db": db_status,
        "version": "1.0.0"
    }
```

Checklist:
- [ ] /api/health returns JSON with db status
- [ ] Uptime monitor configured (UptimeRobot or BetterUptime pointing to /api/health)

---

## ⚙️ SELF-VERIFICATION — RUN AFTER EVERY CHANGE

Before marking any task done, run these grep checks:

```bash
# 1. No hardcoded production URLs in frontend
grep -r "varuflow-production.up.railway.app" frontend/src
# Expected: 0 results

# 2. No wildcard CORS
grep -r 'allow_origins=\["\\*"\]' backend/
# Expected: 0 results

# 3. No secrets in code
grep -rn "sk_live\|sk_test\|whsec_\|re_[a-zA-Z]" backend/app/
# Expected: 0 results

# 4. No debug mode in backend
grep -rn 'DEBUG=True\|debug=True' backend/app/
# Expected: 0 results

# 5. No localhost hardcoded in frontend components
grep -rn "localhost:8000\|localhost:3000" frontend/src/
# Expected: 0 results (only env var references allowed)

# 6. No TODOs left in changed files
grep -rn "TODO\|FIXME\|HACK\|XXX" backend/app/ frontend/src/
# Review and resolve before pushing
```

---

## 🚨 ABSOLUTE RULES — NEVER BREAK THESE

1. NEVER use `allow_origins=["*"]` in production
2. NEVER commit `.env` or `.env.local`
3. NEVER deploy with `ENV=development` on Railway
4. NEVER leave an endpoint without auth dependency (document exceptions with a comment explaining why)
5. NEVER drop a DB column in a migration without a data backup step first
6. NEVER call OpenAI in `ai_engine.py` — GPT-4o only in `integrations.py`
7. NEVER accept a portal JWT on an internal route
8. NEVER push code with a Python import error or TypeScript type error (`npx tsc --noEmit` must pass)
9. NEVER hardcode `PORTAL_BASE_URL` as localhost in any deployed environment
10. NEVER send a Stripe webhook response without signature verification

---

## 📋 MODULE → FILE QUICK REFERENCE

| Module | Backend file | Frontend path |
|--------|-------------|---------------|
| Auth | `routers/auth.py`, `middleware/auth.py` | `[locale]/auth/`, `[locale]/onboarding/` |
| Inventory | `routers/inventory.py`, `models/inventory.py` | `[locale]/(app)/inventory/` |
| Invoicing | `routers/invoicing.py`, `models/invoicing.py` | `[locale]/(app)/invoices/` |
| Customers | `routers/invoicing.py` (customers section) | `[locale]/(app)/customers/` |
| Recurring | `routers/recurring.py` | `[locale]/(app)/recurring/` |
| POS | `routers/pos.py`, `models/pos.py` | `[locale]/(app)/pos/` |
| Analytics | `routers/analytics.py` | `[locale]/(app)/analytics/` |
| AI Engine | `routers/ai_engine.py` | `components/app/AiActionCards.tsx`, `[locale]/(app)/ai/` |
| AI Chat | `routers/integrations.py` | `components/app/AiChat.tsx` |
| Portal | `routers/portal.py`, `models/invoicing.py` (CustomerPortalToken) | `portal/` |
| Billing | `routers/billing.py` | `[locale]/(app)/settings/` |
| Fortnox | `routers/integrations.py` | `[locale]/(app)/settings/` |
| Team | `routers/team.py` | `[locale]/(app)/settings/` |
| Health | `routers/health.py` | — |

---

## 🐛 KNOWN BUGS TO NOT REINTRODUCE

| Bug | File | Fix applied |
|-----|------|-------------|
| CORS blocks all dashboard API calls | `main.py` | CORSMiddleware with explicit origins |
| 404 on `/en/customers/new` | `frontend/src/app/[locale]/(app)/customers/new/page.tsx` | Page file must exist |
| `experimental.turbo` config warning | `next.config.mjs` | Delete key after withNextIntl() |
| GoTrue double-init AbortError | `next.config.mjs` | `reactStrictMode: false` |
| Stale Docker volume breaks module resolution | docker-compose.yml | `docker volume rm varuflow_frontend_node_modules` |
| Portal token reused as internal token | `middleware/auth.py` | Validate `type: "portal"` claim and reject |

---

## START OF SESSION CHECKLIST

Every time you open this project, confirm:
- [ ] `ENV=production` is set on Railway (not development)
- [ ] `CORS_ORIGINS=https://varuflow.vercel.app` is set on Railway
- [ ] `NEXT_PUBLIC_API_URL=https://varuflow-production.up.railway.app` is set on Vercel
- [ ] `/api/health` returns `{ status: ok, db: ok }` from Railway
- [ ] No open TODO/FIXME in files you are about to edit