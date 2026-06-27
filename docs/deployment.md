# Deployment Guide

Varuflow runs on **Railway** (backend) and **Vercel** (frontend).

---

## Overview

```
git push main
  ├── Railway auto-deploys backend via Dockerfile
  └── Vercel auto-deploys frontend via Next.js build
```

Both platforms watch the `main` branch. There is no manual deploy step in normal workflow.

---

## Backend — Railway

### Service Configuration

| Setting | Value |
|---------|-------|
| Root directory | `backend/` |
| Build | `Dockerfile` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| Port | `8000` |
| Health check | `GET /api/health` |

> **Never use `--reload` in the start command on Railway.** That flag is for local dev only.

### Required Environment Variables

Set all of these in Railway → Variables:

```
# Core
DATABASE_URL=postgresql+asyncpg://...        # Railway Postgres supplies this
ENV=production
DEBUG=false

# Auth
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=<service-role-key>
SUPABASE_JWT_SECRET=<jwt-secret>
AUTH_JWT_SECRET=<64-char-random-hex>         # python -c "import secrets; print(secrets.token_hex(32))"

# Security enforcement (must be true in production)
ENFORCE_JWT_SIGNATURE=true
ENFORCE_SECRET_VALIDATION=true
ALLOW_DEV_BYPASS=false

# CORS
CORS_ORIGINS=https://varuflow.vercel.app     # comma-separated, no spaces

# Portal
PORTAL_JWT_SECRET=<32-char-random>           # python -c "import secrets; print(secrets.token_hex(16))"
PORTAL_BASE_URL=https://varuflow.vercel.app
FRONTEND_URL=https://varuflow.vercel.app

# Email
RESEND_API_KEY=re_...

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRO_PRICE_ID=price_...

# Fortnox
FORTNOX_CLIENT_ID=<id>
FORTNOX_CLIENT_SECRET=<secret>
FORTNOX_ENCRYPTION_KEY=<Fernet-key>          # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FORTNOX_REDIRECT_URI=https://varuflow-production.up.railway.app/api/integrations/fortnox/callback

# Encryption
PII_ENCRYPTION_KEY=<Fernet-key>              # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# AI
OPENAI_API_KEY=sk-...

# Observability
SENTRY_DSN=https://...@sentry.io/...

# Admin
ADMIN_API_KEY=<32-char-random>

# Optional
BOLAGSVERKET_API_URL=
BOLAGSVERKET_API_TOKEN=
BANKID_CLIENT_CERT_PATH=                     # Required for BankID in production
OPEN_EXCHANGE_RATES_API_KEY=
WHATSAPP_API_URL=
WHATSAPP_API_TOKEN=
WHATSAPP_FROM_NUMBER=
SMS_API_URL=
SMS_API_TOKEN=
SMS_FROM_NUMBER=
```

### Startup Validation

On every deploy, `validate_production_config()` runs before requests are served. It will **crash the deployment** if:

- `PORTAL_JWT_SECRET` or `AUTH_JWT_SECRET` are still placeholder values
- `SUPABASE_JWT_SECRET` is empty
- `ENFORCE_JWT_SIGNATURE=true` but `SUPABASE_JWT_SECRET` is empty
- `DEBUG=true`
- `CORS_ORIGINS` contains `*` or is empty
- `PII_ENCRYPTION_KEY` is empty (customer PII would be plaintext)
- Fortnox credentials are set but `FORTNOX_ENCRYPTION_KEY` or `FORTNOX_REDIRECT_URI` are empty

Check Railway deploy logs if the service fails to start.

### Database

Railway provides a managed PostgreSQL instance. The `DATABASE_URL` variable is auto-injected when you add a Postgres service to the Railway project.

Migrations run automatically on startup via the FastAPI lifespan hook. To run manually:

```bash
# Via Railway CLI
railway run alembic upgrade head
```

---

## Frontend — Vercel

### Project Configuration

| Setting | Value |
|---------|-------|
| Framework | Next.js |
| Root directory | `frontend/` |
| Build command | `npm run build` |
| Output directory | `.next` |
| Install command | `npm install --legacy-peer-deps` |

> `--legacy-peer-deps` is **required** — ESLint has a peer dep conflict with Next.js 16 that blocks plain `npm install`.

### Required Environment Variables

Set in Vercel → Project → Settings → Environment Variables:

```
NEXT_PUBLIC_API_URL=https://varuflow-production.up.railway.app
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>

# Optional
NEXT_PUBLIC_SENTRY_DSN=https://...@sentry.io/...
```

> `NEXT_PUBLIC_` prefix is required for variables to be available in browser code.

### Custom Domain

1. Vercel → Project → Settings → Domains → Add `varuflow.se`
2. Add DNS records as instructed by Vercel
3. Update `CORS_ORIGINS` on Railway to include the new domain:
   ```
   CORS_ORIGINS=https://varuflow.vercel.app,https://varuflow.se
   ```
4. Update `NEXT_PUBLIC_SUPABASE_URL` redirect allowlists in Supabase dashboard

---

## Supabase (Auth)

### Required Configuration in Supabase Dashboard

1. **Site URL:** `https://varuflow.vercel.app`
2. **Redirect URLs (allowlist):**
   - `https://varuflow.vercel.app/**`
   - `https://varuflow.se/**` (if custom domain configured)
3. **Email templates:** Customize confirmation/reset emails with your branding
4. **JWT expiry:** Default 3600 seconds (1 hour) — adjust in Auth → Configuration

### Getting JWT Secret

Supabase Project → Settings → API → JWT Secret  
This value goes into Railway as `SUPABASE_JWT_SECRET`.

---

## Stripe

### Two Separate Webhook Endpoints

Varuflow has two Stripe integrations with separate webhook endpoints:

| Endpoint | Purpose | Event types |
|----------|---------|-------------|
| `POST /api/billing/webhook` | SaaS subscription billing | `customer.subscription.*`, `invoice.payment_*` |
| `POST /api/invoicing/stripe-webhook` | Customer invoice payment links | `checkout.session.completed`, `payment_intent.*` |

Each endpoint needs its own webhook secret (`STRIPE_WEBHOOK_SECRET`). Configure both in the Stripe Dashboard → Webhooks.

### Plan Enforcement

Set `STRIPE_PRO_PRICE_ID` to the Stripe Price ID for the PRO monthly plan. Plan limits are enforced in `backend/app/middleware/plan_check.py`.

---

## CI/CD Checklist (Before Merging to Main)

- [ ] `npx tsc --noEmit` passes (no TypeScript errors)
- [ ] `pytest` passes (no backend test failures)
- [ ] No hardcoded URLs: `grep -r "varuflow-production.up.railway.app" frontend/src` → 0 results
- [ ] No wildcard CORS: `grep -r 'allow_origins=\["\\*"\]' backend/` → 0 results
- [ ] No secrets in code: `grep -rn "sk_live\|sk_test\|whsec_" backend/app/` → 0 results
- [ ] Alembic migration present for any model changes
- [ ] New env vars added to `.env.example`

---

## Rollback

Railway keeps the last 5 deploys. To rollback:

1. Railway → Service → Deployments
2. Find the previous successful deploy
3. Click "Redeploy"

For database rollbacks, see [docs/operations/backup-and-restore.md](operations/backup-and-restore.md).

---

## Maintenance Mode

To put the backend into read-only mode (e.g. during DB restore):

```
# Railway Variables → set:
READONLY_MODE=true

# Redeploy or wait for Railway to pick up the change
```

All non-safe HTTP methods (POST, PUT, PATCH, DELETE) return `503 Service Unavailable`.  
GET requests continue to work normally.

To exit maintenance mode: set `READONLY_MODE=false` and redeploy.
