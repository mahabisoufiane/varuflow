# Varuflow — Project Reference

> **One file to understand everything.** Stack, structure, env vars, common errors, and dev workflow.

---

## What Is Varuflow

B2B SaaS for Nordic (Swedish / Norwegian / Danish) wholesale businesses.
Replaces spreadsheets and fragmented tools with a single system covering:
inventory · invoicing · recurring billing · POS · analytics · AI advisor · customer portal

**Target user:** A Nordic wholesale operator who buys from suppliers, stores goods in warehouses, and sells to business customers on credit (net-30/60 invoices in SEK/NOK/DKK).

---

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16.2.3 (App Router, Turbopack default) |
| Frontend language | TypeScript |
| Styling | Tailwind CSS + shadcn/ui components |
| i18n | next-intl 3.x — locales: `en`, `sv`, `no`, `da` |
| Auth | Supabase Auth (`@supabase/ssr`) |
| Backend | FastAPI, Python 3.11+, async SQLAlchemy 2.0 |
| Database | PostgreSQL (asyncpg driver) |
| Migrations | Alembic |
| JWT validation | python-jose HS256 (Supabase JWTs) |
| PDF generation | ReportLab |
| Email | Resend |
| Payments | Stripe (customer invoices + SaaS billing) |
| AI chat | OpenAI GPT-4o |
| ERP integration | Fortnox (Swedish accounting, OAuth2) |
| Containerisation | Docker Compose — postgres + backend + frontend |
| Frontend runtime | Node 20 Alpine |

---

## Monorepo Layout

```
varuflow/
├── frontend/                   ← Next.js app
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx              ← Root layout (no locale)
│   │   │   ├── not-found.tsx
│   │   │   ├── globals.css
│   │   │   ├── [locale]/
│   │   │   │   ├── layout.tsx          ← Locale layout: next-intl provider + SW script
│   │   │   │   ├── (marketing)/        ← Public landing page
│   │   │   │   │   ├── layout.tsx
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── auth/
│   │   │   │   │   ├── login/page.tsx
│   │   │   │   │   ├── signup/page.tsx
│   │   │   │   │   └── callback/route.ts   ← OAuth code exchange
│   │   │   │   ├── onboarding/page.tsx     ← Post-signup org creation
│   │   │   │   └── (app)/              ← Protected app shell (auth-gated)
│   │   │   │       ├── layout.tsx          ← Auth guard + AppShell wrapper
│   │   │   │       ├── dashboard/page.tsx
│   │   │   │       ├── analytics/page.tsx
│   │   │   │       ├── ai/page.tsx
│   │   │   │       ├── inventory/
│   │   │   │       │   ├── page.tsx        ← Inventory overview
│   │   │   │       │   ├── products/
│   │   │   │       │   │   ├── page.tsx
│   │   │   │       │   │   ├── new/page.tsx
│   │   │   │       │   │   └── [id]/page.tsx
│   │   │   │       │   ├── purchase-orders/
│   │   │   │       │   │   ├── page.tsx
│   │   │   │       │   │   └── new/page.tsx
│   │   │   │       │   ├── movements/page.tsx
│   │   │   │       │   ├── suppliers/page.tsx
│   │   │   │       │   └── warehouses/page.tsx
│   │   │   │       ├── invoices/
│   │   │   │       │   ├── page.tsx
│   │   │   │       │   ├── new/page.tsx
│   │   │   │       │   └── [id]/page.tsx
│   │   │   │       ├── recurring/page.tsx
│   │   │   │       ├── pos/page.tsx
│   │   │   │       ├── customers/page.tsx
│   │   │   │       └── settings/page.tsx
│   │   │   └── portal/                 ← B2B customer portal (no AppShell)
│   │   │       ├── layout.tsx
│   │   │       ├── page.tsx
│   │   │       ├── login/page.tsx
│   │   │       ├── auth/verify/page.tsx
│   │   │       └── invoices/
│   │   │           ├── page.tsx
│   │   │           └── [id]/page.tsx
│   │   ├── components/
│   │   │   ├── app/
│   │   │   │   ├── AppShell.tsx        ← Sidebar, nav, locale switcher, user footer
│   │   │   │   ├── AiChat.tsx          ← Floating GPT-4o chat panel
│   │   │   │   ├── AiActionCards.tsx   ← Dashboard AI cards widget
│   │   │   │   ├── CommandPalette.tsx  ← ⌘K search palette
│   │   │   │   ├── BarcodeScanner.tsx  ← Camera barcode scanner (POS)
│   │   │   │   └── PwaInstallBanner.tsx
│   │   │   └── ui/                     ← shadcn/ui components
│   │   │       ├── button.tsx
│   │   │       ├── badge.tsx
│   │   │       ├── dialog.tsx
│   │   │       ├── label.tsx
│   │   │       ├── select.tsx
│   │   │       ├── sonner.tsx
│   │   │       ├── table.tsx
│   │   │       └── textarea.tsx
│   │   ├── i18n/
│   │   │   ├── routing.ts              ← defineRouting: locales + defaultLocale
│   │   │   ├── request.ts              ← getRequestConfig: loads messages/{locale}.json
│   │   │   └── navigation.ts           ← re-exports Link/useRouter/usePathname with locale
│   │   ├── lib/
│   │   │   ├── api-client.ts           ← Authenticated fetch wrapper for FastAPI
│   │   │   ├── api.ts                  ← (legacy stub, unused)
│   │   │   ├── portal-client.ts        ← Portal API client (localStorage JWT)
│   │   │   ├── utils.ts                ← cn() helper
│   │   │   └── supabase/
│   │   │       ├── client.ts           ← Browser Supabase singleton + isSupabaseConfigured
│   │   │       └── server.ts           ← Server-side createClient() for RSC / Route Handlers
│   │   └── middleware.ts               ← next-intl routing + Supabase session refresh
│   ├── messages/
│   │   ├── en.json
│   │   ├── sv.json
│   │   ├── no.json
│   │   └── da.json
│   ├── public/
│   │   ├── manifest.json               ← PWA manifest
│   │   └── sw.js                       ← Service worker (cache strategy)
│   ├── Dockerfile                      ← node:20-alpine, npm install --legacy-peer-deps
│   ├── next.config.mjs                 ← Turbopack alias, removes experimental.turbo
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── .env.local                      ← Local dev secrets (git-ignored)
│
├── backend/
│   └── app/
│       ├── main.py                     ← FastAPI app, CORS, router mounts
│       ├── config.py                   ← Settings via pydantic-settings (.env)
│       ├── database.py                 ← Async SQLAlchemy engine + get_db()
│       ├── middleware/
│       │   └── auth.py                 ← JWT validation, dev-user bypass (ENV=development)
│       ├── models/
│       │   ├── organization.py         ← Organization, OrganizationMember, OrgRole
│       │   ├── inventory.py            ← Product, Warehouse, StockLevel, StockMovement,
│       │   │                              Supplier, PurchaseOrder, PurchaseOrderItem
│       │   ├── invoicing.py            ← Invoice, InvoiceLineItem, Payment, Customer,
│       │   │                              RecurringInvoice, CustomerPortalToken
│       │   ├── pos.py                  ← PosSession, PosTransaction
│       │   └── waitlist.py             ← WaitlistEntry (marketing)
│       ├── routers/
│       │   ├── auth.py                 ← /api/auth — profile, onboarding
│       │   ├── inventory.py            ← /api/inventory — products, warehouses, stock
│       │   ├── invoicing.py            ← /api/invoicing — invoices, customers, PDF, EHF
│       │   ├── recurring.py            ← /api/recurring — recurring invoice templates
│       │   ├── pos.py                  ← /api/pos — cash register sessions
│       │   ├── analytics.py            ← /api/analytics — overview + PDF export
│       │   ├── ai_engine.py            ← /api/ai — rules-based action cards + actions
│       │   ├── integrations.py         ← /api/integrations — GPT-4o chat, Fortnox OAuth
│       │   ├── billing.py              ← /api/billing — Stripe subscriptions
│       │   ├── portal.py               ← /api/portal — B2B customer portal auth + invoices
│       │   ├── team.py                 ← /api/team — member invite + management
│       │   ├── health.py               ← /api/health
│       │   └── waitlist.py             ← /api/waitlist
│       ├── schemas/
│       │   ├── inventory.py
│       │   └── invoicing.py
│       └── services/
│           ├── email.py                ← Resend transactional email
│           └── pdf_generator.py        ← ReportLab PDF templates
│
├── docker-compose.yml
├── .gitignore
├── VARUFLOW.md                         ← High-level product documentation
└── PROJECT.md                          ← This file — dev reference
```

---

## Environment Variables

### Frontend — `frontend/.env.local` (git-ignored)

```env
# Backend FastAPI
NEXT_PUBLIC_API_URL=http://localhost:8000

# Supabase Auth
# Get from: supabase.com/dashboard → project → Settings → API
# "Project URL"  →  NEXT_PUBLIC_SUPABASE_URL
# "anon/public"  →  NEXT_PUBLIC_SUPABASE_ANON_KEY
#   (newer dashboards call it "publishable key" — use NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY)
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
# OR if your dashboard shows a publishable key:
# NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY=sb_publishable_...
```

**Note:** Both `NEXT_PUBLIC_SUPABASE_ANON_KEY` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY` are supported.
Leave both empty to run in **dev-bypass mode** (no Supabase needed; backend uses a hardcoded dev user).

### Backend — `backend/.env`

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/varuflow
ENV=development
DEBUG=true

SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_JWT_SECRET=your-jwt-secret

RESEND_API_KEY=re_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
OPENAI_API_KEY=sk-...
PORTAL_JWT_SECRET=<random 32+ chars>
PORTAL_BASE_URL=http://localhost:3000
FORTNOX_CLIENT_ID=...
FORTNOX_CLIENT_SECRET=...
```

---

## Docker Compose Services

| Service | Image | Port | Notes |
|---------|-------|------|-------|
| `postgres` | postgres:16-alpine | 5432 | Data in `pgdata/` volume |
| `backend` | built from `./backend` | 8000 | FastAPI + uvicorn |
| `frontend` | built from `./frontend` | 3000 | Next.js dev server (Turbopack) |

```bash
# Start everything
docker compose up -d

# Rebuild frontend image from scratch (after package.json changes)
docker compose build --no-cache frontend && docker compose up -d frontend

# Restart frontend only (hot-reload picks up code changes automatically)
docker compose restart frontend

# Wipe stale build cache (fixes weird module-not-found errors)
docker compose down
docker volume rm varuflow_frontend_next
docker compose up -d

# Backend logs
docker logs varuflow-backend-1 -f

# Frontend logs
docker logs varuflow-frontend-1 -f
```

---

## URL Map

| URL | What it is |
|-----|-----------|
| `http://localhost:3000/` | Redirects to `/sv/` (default locale) |
| `http://localhost:3000/sv/auth/login` | Login page |
| `http://localhost:3000/sv/auth/signup` | Sign-up page |
| `http://localhost:3000/sv/onboarding` | Post-signup org setup |
| `http://localhost:3000/sv/dashboard` | Main dashboard (auth required) |
| `http://localhost:3000/sv/analytics` | Analytics charts + PDF export |
| `http://localhost:3000/sv/ai` | AI advisor page |
| `http://localhost:3000/sv/inventory` | Inventory overview |
| `http://localhost:3000/sv/invoices` | Invoice list |
| `http://localhost:3000/sv/customers` | Customer directory |
| `http://localhost:3000/sv/settings` | Org settings |
| `http://localhost:3000/sv/pos` | Cash register |
| `http://localhost:3000/portal/invoices` | B2B customer portal |
| `http://localhost:8000/docs` | FastAPI Swagger UI |
| `http://localhost:8000/api/health` | Backend health check |

Replace `/sv/` with `/en/`, `/no/`, or `/da/` to switch locale.

---

## Auth Flow

### Internal users (staff)
1. Sign up at `/auth/signup` → Supabase sends confirmation email
2. Confirm email → redirected to `/auth/callback?next=/onboarding`
3. Onboarding creates the `Organization` + `OrganizationMember` rows via `POST /api/auth/onboarding`
4. All subsequent API calls attach `Authorization: Bearer <supabase_jwt>`
5. Backend `auth.py` middleware validates the JWT and extracts `user_id` + `org_id`

### Dev bypass (no Supabase)
- Leave `NEXT_PUBLIC_SUPABASE_URL` empty in `.env.local`
- Backend `ENV=development` → requests without a token get the hardcoded dev user (`DEV_USER_ID = 00000000-0000-0000-0000-000000000001`)
- First request to a protected route auto-creates `Varuflow Demo AB` org

### B2B customer portal
1. Staff sends magic link: `POST /api/portal/magic-link`
2. Customer clicks link → `GET /portal/auth/verify?token=xxx`
3. Backend validates one-time token, issues a portal JWT (separate secret, `type: "portal"` claim)
4. Portal JWT stored in `localStorage`, attached to all `/api/portal/*` calls

---

## i18n

- Locale in URL prefix: `/sv/`, `/no/`, `/da/` (English is the default and has no prefix)
- Translation files: `frontend/messages/{en,sv,no,da}.json`
- `next-intl` auto-detects locale from URL via `middleware.ts`
- Components use `useTranslations('namespace')` hook
- Server components use `getTranslations('namespace')`
- Locale switcher in sidebar footer (EN / SV / NO / DA buttons)

---

## Common Errors & Fixes

### `supabase.auth.signInWithPassword is not a function`
The Supabase client is returning a stub/null instead of a real client.
**Fix:** Ensure `NEXT_PUBLIC_SUPABASE_URL` and at least one key env var is set in `.env.local`, then `docker compose restart frontend`.

### `@supabase/ssr: Your project's URL and API key are required`
`NEXT_PUBLIC_SUPABASE_ANON_KEY` is empty. Newer Supabase dashboards use `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY` instead.
**Fix:** Set either `NEXT_PUBLIC_SUPABASE_ANON_KEY` or `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY` in `.env.local`. Both are supported.

### `Module not found: Can't resolve 'react-is'`
Stale Docker volume doesn't have `react-is` installed.
**Fix:** `docker volume rm varuflow_frontend_node_modules && docker compose up -d frontend`

### `experimental.turbo` config warning
next-intl plugin injects the old key. Already handled in `next.config.mjs` by deleting it after `withNextIntl()`.

### `localhost:9999/auth/v1/token ERR_CONNECTION_REFUSED`
`NEXT_PUBLIC_SUPABASE_URL` is pointing to a local Supabase instance that isn't running.
**Fix:** Either start Supabase locally (`supabase start`) or set it to the hosted URL.

### API calls go to `localhost:8001` instead of `8000`
Stale env var in `docker-compose.yml` or `.env.local`.
**Fix:** Ensure `NEXT_PUBLIC_API_URL=http://localhost:8000` everywhere.

### `docker compose restart` doesn't apply env var changes
`restart` reuses the existing container. Use `docker compose up -d --force-recreate frontend` instead.

---

## Backend Dev Commands

```bash
cd backend

# Install dependencies
pip install -r requirements.txt
# or with poetry:
poetry install

# Run migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Create a new migration
alembic revision --autogenerate -m "description"
```

---

## Frontend Dev Commands

```bash
cd frontend

# Install dependencies
npm install --legacy-peer-deps

# Start dev server (Turbopack)
npm run dev        # → http://localhost:3000

# Type check
npx tsc --noEmit

# Build for production
npm run build
```

---

## Key Architectural Decisions

| Decision | Reason |
|----------|--------|
| Dev-user bypass in backend | Work on any feature without a live Supabase project |
| `isSupabaseConfigured` guard | Prevents GoTrue lock/AbortError spam in dev |
| Lazy Supabase singleton (Proxy) | Avoids "URL required" crash at module load time in SSR |
| `reactStrictMode: false` | Prevents GoTrue double-init AbortError in dev |
| `npm install --legacy-peer-deps` | ESLint peer dep conflict with Next 16 |
| Turbopack default (`next dev`) | Faster HMR; fixes webpack-mode `OuterLayoutRouter` race condition |
| `turbopack.resolveAlias` in config | next-intl plugin injects `experimental.turbo` (old key) — post-process removes it |
| Portal JWT separate from Supabase | Customers must never be able to reuse a portal token as an internal session |
