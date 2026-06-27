# Architecture

High-level overview of Varuflow's system design, data flow, and infrastructure.

---

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                      Clients                            │
│  Browser (Next.js SSR/CSR)   Mobile (PWA)              │
└──────────────┬──────────────────────────┬───────────────┘
               │ HTTPS                    │ HTTPS
               ▼                          ▼
┌─────────────────────┐      ┌─────────────────────────┐
│   Vercel (CDN/Edge) │      │  Vercel (CDN/Edge)      │
│   Frontend          │      │  B2B Customer Portal    │
│   Next.js 16        │      │  /portal/*              │
│   varuflow.vercel.  │      │  /supplier-portal/*     │
│   app               │      │                         │
└──────────┬──────────┘      └───────────┬─────────────┘
           │ HTTPS REST                  │ HTTPS REST
           ▼                             ▼
┌─────────────────────────────────────────────────────────┐
│               Railway (Backend)                         │
│               FastAPI — Python 3.11                     │
│               uvicorn (production, no --reload)         │
│               varuflow-production.up.railway.app        │
│                                                         │
│  Middleware stack (LIFO — last added = outermost):      │
│  1. Security headers                                    │
│  2. Rate limiting (per-org + per-IP)                    │
│  3. Read-only guard (503 on writes during maintenance)  │
│  4. CORS (must be innermost = first add_middleware call)│
│                                                         │
│  Routers: 86 modules                                    │
│  Models:  73 SQLAlchemy ORM models                      │
│  Services: 99 service modules                           │
└──────────┬──────────────────────┬───────────────────────┘
           │ asyncpg              │ HTTP
           ▼                      ▼
┌────────────────────┐   ┌──────────────────────────────┐
│  PostgreSQL 16     │   │  External Services           │
│  Railway Postgres  │   │  ┌─────────────────────────┐ │
│                    │   │  │ Supabase Auth (GoTrue)  │ │
│  94 migrations     │   │  │ JWT issuance + refresh  │ │
│  Soft deletes on  │   │  └─────────────────────────┘ │
│  core entities     │   │  ┌─────────────────────────┐ │
│                    │   │  │ Stripe                  │ │
│                    │   │  │ SaaS billing            │ │
│                    │   │  │ Invoice payment links   │ │
│                    │   │  └─────────────────────────┘ │
│                    │   │  ┌─────────────────────────┐ │
│                    │   │  │ Resend (email)          │ │
│                    │   │  └─────────────────────────┘ │
│                    │   │  ┌─────────────────────────┐ │
│                    │   │  │ Fortnox (SE accounting) │ │
│                    │   │  └─────────────────────────┘ │
│                    │   │  ┌─────────────────────────┐ │
│                    │   │  │ BankID (SE e-ID)        │ │
│                    │   │  └─────────────────────────┘ │
│                    │   │  ┌─────────────────────────┐ │
│                    │   │  │ Bolagsverket (SE co.)   │ │
│                    │   │  └─────────────────────────┘ │
│                    │   │  ┌─────────────────────────┐ │
│                    │   │  │ OpenAI (GPT-4o chat)    │ │
│                    │   │  └─────────────────────────┘ │
│                    │   │  ┌─────────────────────────┐ │
│                    │   │  │ openexchangerates.org   │ │
│                    │   │  │ (daily FX rates)        │ │
│                    │   │  └─────────────────────────┘ │
└────────────────────┘   └──────────────────────────────┘
```

---

## Multi-Tenancy

Every organization (wholesaler) is isolated by `org_id`. This is enforced at the database query level — not just at the middleware level.

```
Organization (org_id: UUID)
  └── Users (user_id from Supabase Auth)
  └── Customers
  └── Invoices
  └── Products / Inventory
  └── POS Sessions
  └── Analytics data
  └── Fortnox token (encrypted at rest)
```

**Rule:** Every DB query must include `WHERE org_id = :org_id`. The auth middleware extracts `org_id` from the JWT and passes it to every endpoint via the `user` dependency dict. Any endpoint that accidentally omits the filter is a security bug.

---

## Authentication Flow

### Production (Supabase)

```
1. User visits /sv/dashboard
2. proxy.ts (Next.js 16 middleware) calls supabase.auth.getUser()
3. If no session → redirect to /sv/auth/login
4. User logs in via Supabase Auth (email+password or BankID)
5. Supabase issues JWT (signed with SUPABASE_JWT_SECRET)
6. Frontend stores session in cookies (sb-<project-ref>-auth-token via @supabase/ssr)
7. API calls include Authorization: Bearer <JWT>
8. Backend middleware/auth.py validates JWT signature + extracts user_id + org_id
9. org_id is looked up from Organization table (user_id → org_id mapping)
```

### Local Development

```
1. proxy.ts detects no NEXT_PUBLIC_SUPABASE_URL or key → skips auth check
2. Frontend loads without a login wall
3. API calls have no Authorization header
4. Backend: ALLOW_DEV_BYPASS=true + ENV=development → returns DEV_USER_ID / DEV_ORG_ID
5. App is fully usable without Supabase configured
```

---

## Authorization Layers

| Layer | Where | Guards |
|-------|-------|--------|
| Route-level | `proxy.ts` (Next.js) | Unauthenticated users redirected to login |
| JWT validation | `middleware/auth.py` | Signature verification, expiry, claims |
| Org isolation | Every DB query | `WHERE org_id = user["org_id"]` |
| Plan gating | `middleware/plan_check.py` | FREE vs PRO feature access |
| Portal isolation | `middleware/auth.py` | `type: "portal"` JWT claim — portal tokens rejected on internal routes |
| Admin isolation | `X-Admin-Key` header | Admin endpoints require shared secret |

---

## Data Model (Core Entities)

```
Organization
  ├── org_id (UUID, PK)
  ├── name, org_number (Swedish orgnr), vat_number
  ├── base_currency (default: SEK)
  ├── plan (FREE / PRO)
  ├── fortnox_access_token (Fernet encrypted)
  └── ...

User → Supabase Auth (user_id UUID)
  └── Organization membership (user_id + org_id)

Customer
  ├── org_id (FK → Organization)
  ├── email, phone, address (Fernet encrypted — PII_ENCRYPTION_KEY)
  ├── payment_terms_days (default: 30)
  └── deleted_at (soft delete)

Invoice
  ├── org_id, customer_id
  ├── status: DRAFT → SENT → PAID | OVERDUE | CANCELLED
  ├── pdf_path, peppol_xml_path
  └── deleted_at (soft delete)

Product
  ├── org_id
  ├── sku, name, price, stock_quantity
  └── deleted_at (soft delete)
```

---

## Background Jobs (APScheduler)

Registered in `backend/app/services/scheduler.py`:

| Job | Schedule | Description |
|-----|----------|-------------|
| Dunning sweep | Daily 08:00 | Sends reminder emails/SMS at Day +3/+7/+14/+30 past due |
| Recurring invoices | Daily 07:00 | Auto-generates and sends recurring invoice drafts |
| Exchange rate fetch | Daily 06:00 | Pulls FX rates from openexchangerates.org |
| Auto-reorder check | Daily 09:00 | Creates draft POs for products below reorder threshold |
| Nightly summary | Daily 22:00 | Sends digest email to org owners |
| Fortnox token refresh | Every 55 min | Refreshes OAuth tokens before they expire (1hr lifetime) |

---

## Frontend Architecture

```
frontend/src/
├── app/
│   ├── [locale]/              # All locale-prefixed pages (sv/en)
│   │   ├── (app)/             # Authenticated group — requires session
│   │   │   ├── dashboard/
│   │   │   ├── invoices/
│   │   │   ├── customers/
│   │   │   ├── inventory/
│   │   │   ├── analytics/
│   │   │   ├── pos/
│   │   │   ├── recurring/
│   │   │   └── settings/
│   │   ├── (marketing)/       # Public marketing pages
│   │   └── auth/              # Login, signup, password reset
│   ├── portal/                # B2B customer portal (no locale prefix)
│   └── supplier-portal/       # Supplier portal (no locale prefix)
│
├── components/
│   ├── ui/                    # shadcn/ui base components
│   ├── app/                   # App-specific components
│   └── auth/                  # Auth components (BankIDButton, etc.)
│
├── lib/
│   ├── api-client.ts          # Primary API client (all backend calls)
│   ├── api.ts                 # Legacy API helpers
│   ├── portal-client.ts       # Portal-specific API client
│   ├── supabase/
│   │   ├── client.ts          # Lazy singleton browser client
│   │   └── server.ts          # Server-side Supabase client
│   └── utils.ts
│
└── i18n/
    ├── routing.ts             # Defines locales: ["sv", "en"], defaultLocale: "sv"
    ├── request.ts             # Server-side i18n config
    └── navigation.ts          # Type-safe navigation helpers
```

### Key Rules
- All backend calls go through `src/lib/api-client.ts` — never `fetch()` directly
- Never import `@supabase/supabase-js` directly — use `src/lib/supabase/client.ts`
- `reactStrictMode: false` in `next.config.mjs` — prevents GoTrue double-init AbortError
- `npm install --legacy-peer-deps` — ESLint peer dep conflict with Next.js 16

---

## Deployment Architecture

```
git push main
    │
    ├── Vercel (auto-deploy)
    │   ├── Build: npm run build
    │   ├── Edge: proxy.ts (Next.js 16 middleware)
    │   └── CDN: static assets globally distributed
    │
    └── Railway (auto-deploy)
        ├── Build: Docker (backend/Dockerfile)
        ├── Start: uvicorn app.main:app --host 0.0.0.0 --port 8000
        ├── Health: GET /api/health → { status: ok, db: ok }
        └── Startup validation: validate_production_config() — crashes on bad secrets
```

See [docs/deployment.md](deployment.md) for the full deployment guide.
