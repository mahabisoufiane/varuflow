# Varuflow — Complete Project Documentation

## Quick pitch (30 seconds)

Varuflow is the **all-in-one business platform for Nordic wholesalers**. Replace your spreadsheets, separate invoicing app, and manual stock tracking with one tool that covers inventory, invoicing, POS, analytics, and an AI business advisor — available in Swedish, Norwegian, Danish, and English.

**Live demo:** `demo@varuflow.se` / `Demo1234!` (run `python backend/scripts/seed_demo.py` first)  
**Video script:** [docs/DEMO_VIDEO_SCRIPT.md](docs/DEMO_VIDEO_SCRIPT.md)

| Feature | What it does |
|---------|-------------|
| Inventory | Products, warehouses, stock movements, purchase orders, barcode scanning |
| Invoicing | Create → PDF → email → Stripe pay link → auto-mark PAID |
| POS | Tablet cash register with barcode scanner and receipt printing |
| Customer portal | Magic-link self-service portal — customers view invoices and pay online |
| AI advisor | Rules-based insight cards + GPT-4o chat in Swedish/Norwegian/Danish/English |
| Analytics | 6-month revenue charts, top customers, top products — PDF export |
| Fortnox | One-click sync to Sweden's dominant accounting ERP |
| E-invoicing | Norwegian EHF/Peppol and Swedish/EU standard XML export |
| Multi-entity | Parent org + country branches for groups operating in multiple markets |
| Mobile | Expo React Native app (iOS + Android) |

---

## What Is Varuflow?

Varuflow is a **B2B SaaS platform for Nordic wholesalers**, targeting small-to-medium Swedish, Norwegian, and Danish wholesale businesses. It replaces fragmented tools (spreadsheets, separate invoicing apps, manual stock tracking) with a single integrated system covering inventory, invoicing, analytics, POS, and AI-driven business intelligence.

The target customer is a Nordic wholesale operator who buys goods from suppliers, stores them in warehouses, and sells them to business customers on credit terms (invoices with net-30/60 payment).

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    FRONTEND                         │
│  Next.js 14 App Router · TypeScript · Tailwind CSS  │
│  next-intl (EN/SV/NO/DA) · shadcn/ui · Recharts     │
│  Supabase Auth (client) · PWA (custom SW)           │
└────────────────────┬────────────────────────────────┘
                     │ HTTP (fetch + AbortController)
┌────────────────────▼────────────────────────────────┐
│                    BACKEND                          │
│  FastAPI · Python 3.12 · async SQLAlchemy 2.0       │
│  PostgreSQL (asyncpg) · Alembic migrations          │
│  Supabase Auth JWT validation · python-jose HS256   │
│  Resend (email) · Stripe (payments) · ReportLab PDF │
│  OpenAI GPT-4o (AI chat) · Rules engine (AI cards) │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│               EXTERNAL SERVICES                     │
│  Supabase (auth + DB hosting)                       │
│  Resend (transactional email)                       │
│  Stripe (payment links + webhooks)                  │
│  OpenAI (GPT-4o for AI advisor chat)                │
│  Fortnox (Swedish accounting ERP integration)       │
└─────────────────────────────────────────────────────┘
```

---

## Module-by-Module Breakdown

### 1. Authentication & Multi-tenancy

**How it works:**
- Users sign up / log in via Supabase Auth (email + password or magic link)
- Each user belongs to an **Organisation** — all data is scoped by `org_id`
- The FastAPI middleware validates the Supabase JWT on every request and extracts `org_id` from the user's profile
- After sign-up, users go through an **onboarding flow** that creates their organisation and sets a default locale (sv/no/da/en)
- Team members can be invited; roles are stored in the `OrganisationMember` table

**Key files:**
- `backend/app/middleware/auth.py` — JWT validation, org resolution
- `backend/app/routers/auth.py` — profile creation, org setup
- `frontend/src/app/[locale]/auth/` — login, signup pages
- `frontend/src/app/[locale]/onboarding/` — post-signup org creation

---

### 2. Inventory Management

The inventory system tracks products across multiple warehouses with full movement history.

**Products:**
- Each product has: name, SKU, barcode, purchase price (cost), sell price, category, VAT rate, minimum stock threshold, and supplier
- Products can be searched by name or barcode
- Product detail page shows current stock levels per warehouse and full movement history

**Warehouses:**
- Organisations can have multiple warehouses (e.g. "Main Warehouse Stockholm", "Distribution Oslo")
- Stock levels are tracked per product-per-warehouse combination

**Stock Movements:**
- Every stock change is recorded as a movement with type: `IN` (received), `OUT` (sold/dispatched), or `TRANSFER`
- Movements feed the AI engine's velocity calculations
- The movements list is filterable by type, product, and date

**Purchase Orders:**
- Create POs to suppliers with line items
- PO statuses: DRAFT → SENT → RECEIVED
- Receiving a PO automatically creates `IN` stock movements
- Norwegian EHF XML and Peppol BIS XML export for electronic procurement

**Suppliers:**
- Supplier directory with contact info, payment terms, and lead time
- Linked to products (each product has a primary supplier)

**Key files:**
- `backend/app/models/inventory.py` — Product, Warehouse, StockLevel, StockMovement, Supplier, PurchaseOrder models
- `backend/app/routers/inventory.py` — all CRUD + stock movement endpoints
- `frontend/src/app/[locale]/(app)/inventory/` — all inventory pages

---

### 3. Invoicing

Full invoicing workflow from draft to payment collection.

**Invoice lifecycle:**
```
DRAFT → SENT → PAID
              ↓
           OVERDUE (auto-detected when due_date < today)
```

**Features:**
- Create invoices with line items (product, quantity, unit price, VAT)
- Auto-calculates subtotal, VAT (25% Swedish standard), and total in SEK
- Invoice number is auto-generated per organisation (INV-0001, INV-0002…)
- PDF generation via ReportLab — downloadable from the invoice detail page
- Email delivery via Resend — sends invoice PDF to customer
- **Stripe payment links** — generate a hosted Stripe Checkout page and attach the link to the invoice; customers can pay by card; webhook marks invoice as PAID on success
- **Norwegian EHF Billing 3.0 XML export** — for Norwegian customers requiring electronic invoicing via Peppol network (scheme 0192, NOK currency)
- **Overdue reminders** — automated email reminders with urgency copy (1st reminder vs 2nd reminder tone), optional Stripe pay-now button embedded

**Payments:**
- Manual payment recording (bank transfer, cash, etc.)
- Stripe webhook auto-recording for card payments
- Payment history per invoice

**Key files:**
- `backend/app/models/invoicing.py` — Invoice, InvoiceLineItem, Payment, Customer models
- `backend/app/routers/invoicing.py` — CRUD, PDF, email, EHF XML, Stripe payment link endpoints
- `backend/app/services/pdf_generator.py` — ReportLab PDF template
- `backend/app/services/email.py` — Resend email functions
- `frontend/src/app/[locale]/(app)/invoices/` — invoice list, detail, new invoice pages

---

### 4. Recurring Invoices

Automate repeat billing for customers on subscription-like contracts.

**How it works:**
- Define a recurring template: customer, line items, frequency (weekly/monthly/quarterly/yearly), start date, optional end date
- The system generates the next invoice automatically based on the schedule
- Templates can be paused or cancelled

**Key files:**
- `backend/app/routers/recurring.py`
- `frontend/src/app/[locale]/(app)/recurring/page.tsx`

---

### 5. Customers (CRM)

Simple B2B customer directory.

- Company name, contact person, email, phone, address, org number
- Customer portal access management (magic link issuance)
- Customer history: all invoices, total invoiced, average payment time
- Customer detail page shows LTV (lifetime value) and invoice history

**Key files:**
- `backend/app/routers/invoicing.py` (customers are part of invoicing domain)
- `frontend/src/app/[locale]/(app)/customers/page.tsx`

---

### 6. B2B Customer Portal

A separate self-service portal for **customers** (buyers) — not internal users.

**How it works:**
1. Internal user sends a magic link to a customer's email via the customer page
2. Customer clicks the link → hits `/portal/auth/verify?token=xxx`
3. Backend validates the one-time token, issues a **portal JWT** (separate from Supabase auth, HS256 signed with `PORTAL_JWT_SECRET`, includes `type: "portal"` claim to prevent reuse as internal token)
4. Customer is redirected to their invoice list at `/portal/invoices`
5. Portal shows only invoices for that specific customer (scoped by `customer_id` + `org_id`)
6. Customers can download PDF invoices and click Stripe "Pay now" buttons

**Dev mode:** When Resend is not configured, the magic link URL is returned in the API response body for testing without email.

**Key files:**
- `backend/app/routers/portal.py` — magic link issue, token verify, portal-scoped invoice endpoints
- `backend/app/models/invoicing.py` — `CustomerPortalToken` model
- `frontend/src/app/portal/` — standalone portal app (separate layout, no AppShell)
- `frontend/src/lib/portal-client.ts` — portal API client using localStorage JWT

---

### 7. Point of Sale (POS / Cash Register)

A simple in-store cash register for walk-in sales.

**How it works:**
- Barcode scanner support (camera or USB HID)
- Add products to cart by scanning or searching
- Apply discounts per line
- Complete sale → auto-creates OUT stock movements and records the transaction
- Receipt printing support
- Session-based: open/close cash register sessions with opening float

**Key files:**
- `backend/app/models/pos.py` — PosSession, PosTransaction models
- `backend/app/routers/pos.py`
- `frontend/src/app/[locale]/(app)/pos/page.tsx`
- `frontend/src/components/app/BarcodeScanner.tsx` — camera-based barcode scanner component

---

### 8. Analytics

Business intelligence dashboard with date-range filtering and PDF export.

**Metrics available:**
- Revenue over time (invoiced vs collected) — area chart by month
- Top 5 customers by revenue — bar chart
- Top 5 products by revenue — horizontal bar chart
- Invoice status breakdown — pie chart (DRAFT / SENT / PAID / OVERDUE counts)
- All charts respect `from_date` / `to_date` query params

**PDF Export:**
- ReportLab generates a multi-page analytics report
- Includes the same metrics as the screen in printable format

**Key files:**
- `backend/app/routers/analytics.py` — overview endpoint + PDF export
- `frontend/src/app/[locale]/(app)/analytics/page.tsx`

---

### 9. AI Intelligence Engine

Two-part AI system: proactive action cards + reactive chat advisor.

#### Part A: AI Action Cards (Rules-based, no LLM cost)

The backend runs 5 analytical modules every time `GET /api/ai/cards` is called. No OpenAI calls — pure SQL + Python logic.

| Module | What it detects | How |
|--------|----------------|-----|
| 1. Stockout Risk | Products running out soon | SUM(OUT movements last 7 days) / 7 = daily velocity → days_until_empty vs lead time (5 days) |
| 2. Margin Leak | Products with low gross margin | (sell_price - purchase_price) / sell_price vs category benchmark; flagged if < 75% of benchmark |
| 3. Dead Stock | Products with no sales movement | No OUT movements in last 30 days |
| 4. (reserved) | — | — |
| 5. Overdue + Churn Risk | Customers who haven't paid or haven't ordered recently | Overdue by age bucket (30/60/90+ days); churn flag if LTV > 5,000 SEK and no invoice in 45 days |

Each card has: `module`, `severity` (HIGH/MEDIUM/LOW), `title`, `body`, `suggested_action`, and an `action_type` (`SEND_REMINDER` or `DRAFT_PO`).

**Actionable buttons on each card:**
- `SEND_REMINDER` → calls `POST /api/ai/actions/send-reminder` → triggers overdue reminder email via Resend
- `DRAFT_PO` → calls `POST /api/ai/actions/draft-po` → auto-creates a Purchase Order for the product's primary supplier

Cards are shown on the dashboard and on the dedicated `/ai` page (with module filter bar, KPI summary row, expandable detail view).

#### Part B: AI Chat Advisor (GPT-4o)

A floating chat panel (bottom-right of every app page) powered by OpenAI GPT-4o.

**System prompt structure:** The advisor follows a DETECT → DIAGNOSE → PRESCRIBE framework across 5 domains:
1. Inventory & Supply Chain
2. Cash Flow & Receivables
3. Pricing & Margin
4. Customer Behaviour & Churn
5. Operational Efficiency

**Guardrails:**
- Only answers questions about the user's wholesale business
- Responds in the same language the user writes in (Swedish, Norwegian, Danish, or English)
- Will not give legal/tax/financial advice
- Chat history is stored in `localStorage` (no server-side history)

**Key files:**
- `backend/app/routers/ai_engine.py` — rules engine, action endpoints
- `backend/app/routers/integrations.py` — `/api/integrations/chat` GPT-4o endpoint
- `frontend/src/components/app/AiActionCards.tsx` — dashboard widget
- `frontend/src/app/[locale]/(app)/ai/page.tsx` — full AI advisor page
- `frontend/src/components/app/AiChat.tsx` — floating chat panel

---

### 10. Internationalisation (i18n)

Full 4-locale support built into the routing layer.

| Locale | Language | Notes |
|--------|----------|-------|
| `en` | English | Default fallback |
| `sv` | Swedish | Primary market, SEK currency |
| `no` | Norwegian Bokmål | NOK currency, EHF invoicing |
| `da` | Danish | DKK currency |

- URL structure: `/en/dashboard`, `/sv/dashboard`, `/no/dashboard`, `/da/dashboard`
- Locale switcher in the sidebar footer (EN / SV / NO / DA buttons)
- Norwegian locale enables EHF XML export button on invoices
- Translation files: `frontend/messages/{en,sv,no,da}.json`

**Key files:**
- `frontend/src/i18n/routing.ts` — locale list and default
- `frontend/src/i18n/request.ts` — server-side locale resolution
- `frontend/src/middleware.ts` — locale prefix middleware (excludes `/portal` paths)

---

### 11. Progressive Web App (PWA)

Varuflow installs as a native-like app on mobile and desktop.

- `public/manifest.json` — app name, icons, `display: standalone`, `start_url: /dashboard`, theme `#1a2332`
- `public/sw.js` — custom service worker (no next-pwa dependency):
  - **Precache** app shell on install
  - **Navigation requests** → network-first (always fresh HTML)
  - **Static assets** → cache-first (fast loads)
  - **API requests** → network-only (never serve stale data)
  - **Push notifications** — service worker listens for push events and shows notifications
- `PwaInstallBanner` component — shows install prompt when `beforeinstallprompt` fires
- Settings page has a "Notifications" tab to request push permission

---

### 12. Fortnox Integration

Connects to Fortnox (the dominant Swedish accounting ERP) via OAuth2.

- `GET /api/integrations/fortnox/auth` → redirects to Fortnox OAuth consent
- `GET /api/integrations/fortnox/callback` → exchanges code for access token, stores in org settings
- `GET /api/integrations/fortnox/status` → returns `{ connected: bool }`
- When connected, a green "FX" badge appears in the sidebar
- Invoices can be synced to Fortnox (creates Fortnox invoices from Varuflow invoices)

---

### 13. Billing (Stripe Subscriptions)

Varuflow's own SaaS subscription billing (separate from Stripe payment links used for customer invoices).

- `POST /api/billing/checkout` → creates a Stripe Checkout session for the org's subscription
- `POST /api/billing/webhook` → handles `customer.subscription.updated`, `invoice.paid` etc.
- `GET /api/billing/portal` → Stripe Customer Portal link for self-service plan management
- Plan enforcement gates features (e.g., AI features require Pro plan)

**Key files:**
- `backend/app/routers/billing.py`
- `frontend/src/app/[locale]/(app)/settings/page.tsx` — billing tab

---

### 14. Settings

Organisation-wide configuration page with 5 tabs:

| Tab | What you can do |
|-----|----------------|
| **General** | Org name, address, org number, default currency, VAT number |
| **Team** | Invite members by email, manage roles, remove members |
| **Integrations** | Connect Fortnox, configure OpenAI key, configure Resend key |
| **Billing** | View current plan, upgrade/downgrade, manage payment method |
| **Notifications** | Enable/disable push notifications (requests browser permission) |

---

## Data Model Summary

```
Organisation
  ├── OrganisationMember (users)
  ├── Customer
  │   ├── Invoice
  │   │   ├── InvoiceLineItem
  │   │   ├── Payment
  │   │   └── CustomerPortalToken
  │   └── RecurringInvoice
  ├── Supplier
  │   └── Product
  │       ├── StockLevel (per warehouse)
  │       ├── StockMovement
  │       └── PurchaseOrderItem
  ├── Warehouse
  ├── PurchaseOrder
  │   └── PurchaseOrderItem
  └── PosSession
      └── PosTransaction
```

---

## API Structure

All internal API routes are prefixed and auth-gated:

| Prefix | Router | Purpose |
|--------|--------|---------|
| `/api/auth` | auth.py | Profile, org creation |
| `/api/inventory` | inventory.py | Products, warehouses, stock, movements, POs, suppliers |
| `/api/invoicing` | invoicing.py | Invoices, customers, payments, PDF, EHF, Stripe links |
| `/api/recurring` | recurring.py | Recurring invoice templates |
| `/api/pos` | pos.py | Cash register sessions and transactions |
| `/api/analytics` | analytics.py | Overview metrics, PDF export |
| `/api/ai` | ai_engine.py | Action cards, send-reminder, draft-PO actions |
| `/api/integrations` | integrations.py | AI chat, Fortnox OAuth, OpenAI key config |
| `/api/billing` | billing.py | Stripe subscription management |
| `/api/team` | team.py | Team member management |
| `/api/portal` | portal.py | B2B customer portal (separate auth) |

---

## Frontend App Structure

```
src/app/
├── [locale]/
│   ├── (marketing)/          ← Public landing page
│   ├── auth/                 ← Login, signup, OAuth callback
│   ├── onboarding/           ← Post-signup org setup
│   └── (app)/                ← Protected app (requires auth)
│       ├── layout.tsx        ← Auth guard + AppShell wrapper
│       ├── dashboard/        ← KPIs, receivables, low stock, AI cards
│       ├── analytics/        ← Charts, date filter, PDF export
│       ├── ai/               ← AI advisor full page
│       ├── inventory/        ← Products, warehouses, movements, POs, suppliers
│       ├── invoices/         ← Invoice list, detail, new invoice
│       ├── recurring/        ← Recurring invoice templates
│       ├── pos/              ← Cash register
│       ├── customers/        ← Customer directory
│       └── settings/         ← Org settings, team, billing, integrations
└── portal/                   ← B2B customer portal (separate layout, no AppShell)
    ├── login/
    ├── auth/verify/
    └── invoices/

src/components/app/
├── AppShell.tsx              ← Sidebar nav, locale switcher, user footer
├── AiChat.tsx                ← Floating GPT-4o chat panel
├── AiActionCards.tsx         ← Dashboard AI cards widget
├── CommandPalette.tsx        ← ⌘K search palette
├── BarcodeScanner.tsx        ← Camera barcode scanner for POS
└── PwaInstallBanner.tsx      ← PWA install prompt banner
```

---

## How to Run

### Backend
```bash
cd backend
cp .env.example .env          # fill in DATABASE_URL, SUPABASE_*, RESEND_API_KEY, etc.
pip install -r requirements.txt
alembic upgrade head           # run all migrations
uvicorn app.main:app --reload  # starts on http://localhost:8000
```

### Frontend
```bash
cd frontend
cp .env.local.example .env.local   # fill in NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_API_URL
npm install
npm run dev                         # starts on http://localhost:3000
```

### Required Environment Variables

**Backend (`.env`):**
```
DATABASE_URL=postgresql+asyncpg://...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
RESEND_API_KEY=re_...
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...
OPENAI_API_KEY=sk-...
PORTAL_JWT_SECRET=<random 32+ char string>
PORTAL_BASE_URL=http://localhost:3000
FORTNOX_CLIENT_ID=...
FORTNOX_CLIENT_SECRET=...
```

**Frontend (`.env.local`):**
```
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Current Development Status

The project is a **Phase 1 MVP** with all core modules implemented:

- [x] Auth, multi-tenancy, onboarding
- [x] Inventory (products, warehouses, movements, POs, suppliers)
- [x] Invoicing (CRUD, PDF, email, Stripe, EHF/Peppol XML)
- [x] Recurring invoices
- [x] Customer CRM
- [x] B2B customer portal (magic link auth)
- [x] Point of Sale / cash register
- [x] Analytics with PDF export
- [x] AI action cards (rules-based, 5 modules)
- [x] AI chat advisor (GPT-4o)
- [x] i18n: EN / SV / NO / DA
- [x] PWA (installable, offline shell, push notifications)
- [x] Fortnox integration
- [x] Stripe subscription billing
- [ ] Production deployment (Docker + standalone Next.js build configured)
