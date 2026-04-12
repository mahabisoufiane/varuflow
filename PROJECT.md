# Varuflow — Full Project Map
> Every file, its responsibility, and what you can change in it.

---

## DEPLOYMENT

| Target | URL | Trigger |
|--------|-----|---------|
| Frontend | https://varuflow.vercel.app | push to `main` → Vercel auto-deploys |
| Backend | https://varuflow-production.up.railway.app | push to `main` → Railway auto-deploys |
| DB | Supabase PostgreSQL (hosted) | Alembic migrations run on Railway startup |

**Health check:** `GET https://varuflow-production.up.railway.app/api/health`

---

## ENVIRONMENT VARIABLES

### Railway (backend)
| Variable | What it does |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `ENV` | Must be `production` on Railway |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase public anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase admin key (bypasses RLS) |
| `SUPABASE_JWT_SECRET` | ⚠️ Currently bypassed — must match Supabase Dashboard → Settings → API → JWT Secret |
| `RESEND_API_KEY` | Email sending (invoices, reminders, auth emails) |
| `STRIPE_SECRET_KEY` | Stripe API key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signature verification |
| `STRIPE_PRO_PRICE_ID` | Stripe price ID for the PRO plan |
| `OPENAI_API_KEY` | GPT-4o for AI chat only |
| `PORTAL_JWT_SECRET` | Signs B2B customer portal tokens |
| `PORTAL_BASE_URL` | Must be `https://varuflow.vercel.app` |
| `FORTNOX_CLIENT_ID` | Fortnox OAuth app client ID |
| `FORTNOX_CLIENT_SECRET` | Fortnox OAuth app client secret |
| `CORS_ORIGINS` | Must be `https://varuflow.vercel.app` |
| `AUTH_JWT_SECRET` | Signs standalone local-auth access tokens |

### Vercel (frontend)
| Variable | What it does |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | `https://varuflow-production.up.railway.app` |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase public anon key |

---

## BACKEND — backend/app/

### Entry points

#### main.py
- Creates the FastAPI app, registers all middleware and routers
- CORS: CORSMiddleware is the last add_middleware() call → outermost in Starlette LIFO stack → processes requests first
- Security headers: X-Content-Type-Options, X-Frame-Options, Referrer-Policy
- Global exception handler: catches unhandled exceptions, returns JSON 500 with CORS headers
- Alembic: runs `alembic upgrade head` on startup automatically
- Change here: middleware order, startup logic, adding new routers

#### config.py
- All environment variables as a Pydantic Settings class
- validate_production_config() — crashes the process on startup if critical vars are missing
- ⚠️ SUPABASE_JWT_SECRET validation is currently commented out (temporary)
- Change here: add new env vars, adjust production validation rules

#### database.py
- SQLAlchemy async engine + session factory
- pool_size=10, max_overflow=20
- Change here: connection pool tuning

---

### Middleware — middleware/

#### middleware/auth.py
- _decode_token() — decodes Supabase JWTs
- ⚠️ Signature verification is currently BYPASSED (verify_signature: False)
  → To re-enable: set correct SUPABASE_JWT_SECRET in Railway (Supabase Dashboard → Settings → API → JWT Secret)
  → Then uncomment the `if settings.SUPABASE_JWT_SECRET:` block
- get_current_user() — FastAPI dependency, returns {user_id, email} from JWT
- get_current_member() — extends get_current_user, fetches OrganizationMember row from DB
- Portal token guard: rejects tokens with type:"portal" on internal routes
- Change here: JWT algorithm, dev bypass rules, portal token validation

#### middleware/plan_check.py
- require_plan(minimum) — FastAPI dependency that gates routes by org plan
- Plans: FREE < STARTER < PRO < ENTERPRISE
- Used as router-level dependency on: ai_engine, analytics, recurring, integrations
- Change here: plan tier logic, add new plan gates

#### middleware/rate_limit.py
- IP-based rate limiting: 100 req/min per IP
- Applied before CORS so 429 responses still have CORS headers
- Change here: rate limit thresholds, exempted paths

---

### Models — models/

Every model change needs a migration:
  cd backend
  alembic revision --autogenerate -m "description"
  alembic upgrade head

#### models/organization.py
- Organization — org table: name, org_number, vat_number, plan, stripe_customer_id, fortnox credentials
- OrganizationMember — links user_id → org_id with role (OWNER/ADMIN/MEMBER)
- OrgPlan enum: FREE, STARTER, PRO, ENTERPRISE
- OrgRole enum: OWNER, ADMIN, MEMBER
- FortnoxOAuthState — CSRF state tokens for Fortnox OAuth flow
- Change here: add org-level fields, change plan tiers

#### models/inventory.py
- Product — SKU, name, category, prices, barcode, is_active
- Supplier — name, contact, lead time
- Warehouse — name, location
- StockLevel — quantity per product per warehouse, min_threshold
- StockMovement — IN/OUT/ADJUSTMENT movements with quantity, reason
- PurchaseOrder — PO to supplier with status (DRAFT/SENT/RECEIVED)
- PurchaseOrderItem — line items on a PO
- Change here: add product fields, new movement types, warehouse logic

#### models/invoicing.py
- Customer — company_name, email, address, payment_terms, is_active
- Invoice — invoice_number, status (DRAFT/SENT/PAID/OVERDUE/CANCELLED), totals in SEK/EUR
- InvoiceLineItem — line items on an invoice
- Payment — payment records linked to invoices
- CustomerPortalToken — short-lived tokens for B2B portal access
- RecurringInvoice — recurring invoice templates with frequency and next_date
- Change here: invoice fields, payment methods, recurring frequency options

#### models/pos.py
- PosSession — cashier session (open/closed) with cash totals
- PosSale — completed sale in a POS session
- PosSaleItem — line items on a POS sale
- Change here: POS-specific fields, refund logic

#### models/auth.py
- AuthUser — standalone local auth (bcrypt password, TOTP, email verification, lockout)
- AuthRefreshToken — hashed refresh tokens (SHA-256) with expiry
- AuthLoginAttempt — audit log of every login attempt
- Change here: password policy, TOTP, session length

#### models/waitlist.py
- WaitlistEntry — email + company for the public waitlist
- Change here: add fields for waitlist segmentation

---

### Routers — routers/

#### routers/auth.py
- POST /api/auth/onboarding — creates org for new Supabase user (idempotent)
- GET  /api/auth/me — returns current user + org info
- Change here: onboarding flow, what gets created on signup

#### routers/local_auth.py
- Standalone auth system independent of Supabase
- POST /api/local-auth/register — create account
- POST /api/local-auth/login — returns access + refresh tokens
- POST /api/local-auth/refresh — exchange refresh token
- POST /api/local-auth/logout — revoke refresh token
- POST /api/local-auth/totp/* — TOTP enable/disable/verify
- POST /api/local-auth/password-reset/* — request and confirm reset
- Change here: password policy, TOTP config, token expiry

#### routers/inventory.py
- GET/POST   /api/inventory/products — list/create products
- GET/PUT/DELETE /api/inventory/products/{id} — read/update/delete
- GET/POST   /api/inventory/stock — stock levels (?low_stock_only=true)
- POST       /api/inventory/stock/adjust — manual stock adjustment
- GET/POST   /api/inventory/movements — movement log
- GET/POST   /api/inventory/suppliers — suppliers CRUD
- GET/POST   /api/inventory/warehouses — warehouses CRUD
- GET/POST   /api/inventory/purchase-orders — PO CRUD
- POST       /api/inventory/purchase-orders/{id}/receive — mark received, auto-adjusts stock
- Change here: inventory business rules, reorder logic, import/export

#### routers/invoicing.py
- GET/POST   /api/invoicing/customers — customers CRUD
- GET/POST   /api/invoicing/invoices — invoices CRUD
- GET        /api/invoicing/invoices/{id} — single invoice
- POST       /api/invoicing/invoices/{id}/send — send by email (Resend)
- POST       /api/invoicing/invoices/{id}/payment-link — Stripe payment link
- GET        /api/invoicing/invoices/{id}/pdf — generate PDF
- POST       /api/invoicing/payments — record a payment
- Change here: invoice numbering, PDF layout, payment logic, email templates

#### routers/recurring.py
- GET/POST /api/recurring — recurring invoice templates CRUD
- POST     /api/recurring/{id}/pause|resume — pause/resume series
- Scheduler runs daily and generates invoices from active templates
- Change here: recurrence frequency options, generation logic

#### routers/billing.py
- POST /api/billing/checkout — creates Stripe Checkout session → returns URL
- POST /api/billing/portal — creates Stripe Customer Portal session
- POST /api/billing/webhook — Stripe webhook (signature verified, idempotent)
  checkout.session.completed → upgrades org to PRO
  customer.subscription.deleted → downgrades org to FREE
  invoice.payment_failed → grace period (no immediate downgrade)
- Change here: plan tiers, Stripe price IDs, grace period logic

#### routers/analytics.py
- GET /api/analytics/overview — revenue, invoice counts, top customers (PRO+)
- GET /api/analytics/inventory — stock value, turnover metrics (PRO+)
- GET /api/analytics/customers — customer RFM analysis (PRO+)
- Change here: new KPIs, date range filters, export formats

#### routers/ai_engine.py
- GET  /api/ai/cards — generates action cards from live DB data (NO OpenAI)
  Module 1: Inventory (stockout risk, dead stock, reorder alerts)
  Module 2: Margin optimizer (products below benchmark gross margin)
  Module 5: Customer intelligence (overdue invoices, churn signals)
- POST /api/ai/actions/send-reminder — sends payment reminder (idempotent)
- POST /api/ai/actions/mark-seen — marks card as seen
- ⚠️ NO OpenAI imports allowed here — GPT-4o is only in integrations.py
- Change here: add card types, adjust thresholds, new action types

#### routers/integrations.py
- GET  /api/integrations/config — which integrations are enabled
- GET/POST /api/integrations/fortnox/* — Fortnox OAuth (connect, callback, status, disconnect, sync)
- POST /api/integrations/chat — GPT-4o AI chat (ONLY place OpenAI is called)
- Change here: new integrations, Fortnox sync logic, chat system prompt

#### routers/portal.py
- POST /api/portal/auth/send-link — sends magic link to B2B customer
- POST /api/portal/auth/verify — verifies magic link, returns portal JWT
- GET  /api/portal/invoices — customer's own invoices (portal JWT required)
- GET  /api/portal/invoices/{id} — single invoice in portal
- POST /api/portal/invoices/{id}/pay — Stripe payment from portal
- Portal JWTs use PORTAL_JWT_SECRET and have type:"portal" claim — rejected by internal routes
- Change here: portal branding, what customers can see, payment flow

#### routers/pos.py
- GET/POST /api/pos/sessions — POS session management
- POST     /api/pos/sessions/{id}/close — close session, reconcile cash
- POST     /api/pos/sales — record a sale
- GET      /api/pos/products — product list optimised for POS (barcode search)
- Change here: receipt format, barcode scanning, cash reconciliation

#### routers/team.py
- GET    /api/team/members — list org members
- POST   /api/team/invite — invite by email
- PATCH  /api/team/members/{id} — change role
- DELETE /api/team/members/{id} — remove member
- Change here: invitation email, role permissions

#### routers/health.py
- GET /api/health — returns {status, database, version} — no auth required
- Change here: add more dependency checks

#### routers/waitlist.py
- POST /api/waitlist — public, no auth, saves email to waitlist
- Change here: waitlist confirmation email, CRM webhook

---

### Services — services/

#### services/email.py
- Sends emails via Resend API
- Used by: invoicing (send invoice), ai_engine (payment reminders), team (invitations)
- Change here: email templates, from address

#### services/auth_email.py
- Email templates for local-auth flow (verification, password reset)
- Change here: email copy, expiry times

#### services/auth_service.py
- Business logic for local-auth: create user, authenticate, refresh tokens, TOTP, password reset
- Change here: password strength rules, token expiry, TOTP window

#### services/pdf_generator.py
- Generates invoice PDFs using WeasyPrint
- Change here: PDF layout, logo, fonts, page size

#### services/scheduler.py
- APScheduler jobs running inside Railway:
  Daily:  generate recurring invoices from active templates
  Daily:  mark overdue invoices (SENT → OVERDUE if past due date)
  Weekly: clean up expired portal tokens
- Change here: schedule frequency, add new scheduled jobs

---

### Migrations — migrations/versions/

| File | What it creates |
|------|----------------|
| 957ae9166078_initial_schema.py | All core tables: orgs, members, products, stock, invoices, customers, payments, portal tokens, recurring, POS, waitlist |
| a1b2c3d4e5f6_v7_product_reorder_level.py | reorder_level column on products |
| b2c4d8f1a3e5_v3_pos_barcode.py | barcode column on products, POS tables |
| c3d5e9f2b4a6_v5_fortnox_openai.py | Fortnox credential columns on organizations |
| d4e6f0a3c5b7_v5_stripe_payment_links.py | stripe_payment_link_* columns on invoices |
| e5f7a1b4c6d8_v5_portal_tokens.py | customer_portal_tokens table |
| f6a8b2c4d1e3_v6_pos_refund.py | refunded flag on POS sales |
| b3c5e9f1a2d4_v8_local_auth_tables.py | auth_users, auth_refresh_tokens, auth_login_attempts |
| a9b1c3d5e7f2_v9_fortnox_oauth_csrf.py | fortnox_oauth_states CSRF table |
| b4d6f0a2c8e1_v10_stripe_idempotency.py | stripe_processed_events idempotency table |

---

## FRONTEND — frontend/src/

### Auth pages — app/[locale]/auth/

| File | Route | Responsibility |
|------|-------|---------------|
| auth/signup/page.tsx | /auth/signup?plan=starter|professional | Email/password signup + OAuth. Passes plan through email confirmation URL |
| auth/login/page.tsx | /auth/login | Email/password login + OAuth |
| auth/forgot-password/page.tsx | /auth/forgot-password | Sends Supabase password-reset email |
| auth/reset-password/page.tsx | /auth/reset-password | Handles reset link, sets new password |
| auth/callback/route.ts | /auth/callback | Supabase OAuth callback — exchanges code, redirects to ?next= param |
| onboarding/page.tsx | /onboarding?plan=... | 3-step org setup. If plan param set → calls POST /api/billing/checkout on finish |

### App pages — app/[locale]/(app)/

| File | Route | Responsibility |
|------|-------|---------------|
| (app)/layout.tsx | — | Server-side auth guard: no session → redirect to login |
| (app)/dashboard/page.tsx | /dashboard | KPI summary, low stock alerts, recent movements, overdue invoices |
| (app)/inventory/page.tsx | /inventory | Stock level overview with low-stock filter |
| (app)/inventory/products/page.tsx | /inventory/products | Product list |
| (app)/inventory/products/new/page.tsx | /inventory/products/new | Create product |
| (app)/inventory/products/[id]/page.tsx | /inventory/products/:id | Edit product |
| (app)/inventory/movements/page.tsx | /inventory/movements | Stock movement log |
| (app)/inventory/suppliers/page.tsx | /inventory/suppliers | Supplier list |
| (app)/inventory/warehouses/page.tsx | /inventory/warehouses | Warehouse management |
| (app)/inventory/purchase-orders/page.tsx | /inventory/purchase-orders | PO list |
| (app)/inventory/purchase-orders/new/page.tsx | /inventory/purchase-orders/new | Create PO |
| (app)/invoices/page.tsx | /invoices | Invoice list with status filter |
| (app)/invoices/new/page.tsx | /invoices/new | Create invoice with line items |
| (app)/invoices/[id]/page.tsx | /invoices/:id | Invoice detail, send, PDF, payment link |
| (app)/customers/page.tsx | /customers | Customer list |
| (app)/customers/new/page.tsx | /customers/new | Create customer |
| (app)/recurring/page.tsx | /recurring | Recurring invoice templates |
| (app)/pos/page.tsx | /pos | Point-of-sale terminal with barcode scanning |
| (app)/analytics/page.tsx | /analytics | Revenue charts, top customers, inventory metrics (PRO+) |
| (app)/ai/page.tsx | /ai | AI action cards dashboard (PRO+) |
| (app)/settings/page.tsx | /settings | Profile, billing, team, Fortnox integration |

### Marketing pages — app/[locale]/(marketing)/

| File | Route | Responsibility |
|------|-------|---------------|
| (marketing)/page.tsx | / | Landing page |
| (marketing)/HeaderNav.tsx | — | Top nav bar with auth-aware CTA |
| pricing/page.tsx | /pricing | Pricing plans. Start trial → signup with plan. Enterprise → contact modal |

### Portal pages — app/portal/ (no locale prefix)

| File | Route | Responsibility |
|------|-------|---------------|
| portal/login/page.tsx | /portal/login | Enter email to receive magic link |
| portal/auth/verify/page.tsx | /portal/auth/verify | Verify magic link, set portal session |
| portal/page.tsx | /portal | Portal home |
| portal/invoices/page.tsx | /portal/invoices | Customer's invoice list |
| portal/invoices/[id]/page.tsx | /portal/invoices/:id | Invoice detail with Stripe pay button |
| portal/layout.tsx | — | Portal layout, excluded from locale middleware |

### Components — components/

| File | Responsibility |
|------|---------------|
| components/app/AppShell.tsx | Sidebar nav, top bar, theme, user menu. Wraps all (app) pages |
| components/app/AiActionCards.tsx | Fetches GET /api/ai/cards and renders card grid |
| components/app/AiChat.tsx | GPT-4o chat widget, history in localStorage. Calls POST /api/integrations/chat |
| components/app/PlanGate.tsx | Wraps UI that requires a specific plan. Shows upgrade prompt |
| components/app/CommandPalette.tsx | Cmd+K search palette |
| components/app/SessionTimeoutModal.tsx | Shows modal after 15 min idle |
| components/app/BarcodeScanner.tsx | Camera barcode scanner (ZXing) for POS and inventory |
| components/app/PwaInstallBanner.tsx | Add to home screen banner |
| components/ui/ | Design system: button, input, dialog, badge, table, select, skeleton, sonner, ThemeToggle |

### Libraries — lib/

| File | Responsibility |
|------|---------------|
| lib/api-client.ts | ALL backend calls go through here. Auto-attaches Bearer token. On 401 → refresh once → sign out. api.get/post/put/patch/delete/upload |
| lib/supabase/client.ts | Browser Supabase client. isSupabaseConfigured guard. signInWithGoogle/Microsoft |
| lib/supabase/server.ts | Server-side Supabase client for Server Components |
| lib/plan.ts | PLAN_PRICES (SEK/EUR, monthly/yearly). Plan type |
| lib/portal-client.ts | HTTP client for portal routes (attaches portal JWT, not Supabase token) |
| lib/api.ts | Legacy fetch wrapper — prefer api-client.ts for all new code |
| lib/utils.ts | cn() Tailwind class merge utility |

### i18n

| File | Responsibility |
|------|---------------|
| i18n/routing.ts | Supported locales: en, sv, no, da. Default: sv |
| i18n/request.ts | Loads message JSON per request locale |
| i18n/navigation.ts | Locale-aware Link, useRouter, usePathname |
| messages/en.json | English translations — every new string must be added here AND sv/no/da |
| messages/sv.json | Swedish translations |
| messages/no.json | Norwegian translations |
| messages/da.json | Danish translations |

### Config files

| File | Responsibility |
|------|---------------|
| frontend/next.config.mjs | Turbopack, next-intl plugin, reactStrictMode:false |
| frontend/tsconfig.json | exclude:["frontend"] blocks ghost directory |
| frontend/tailwind.config.ts | Tailwind theme with Varuflow CSS variables |

---

## MOBILE — mobile/

### Screens — app/

| File | Route | Responsibility |
|------|-------|---------------|
| app/_layout.tsx | Root | Primary auth gate: onAuthStateChange, checks enterprise plan |
| app/(app)/_layout.tsx | — | Secondary auth gate: hard session + plan check, blocks deep-link bypass |
| app/(app)/dashboard.tsx | / | KPI cards, low-stock alerts, recent activity |
| app/(app)/inventory.tsx | /inventory | Stock list with search |
| app/(app)/analytics.tsx | /analytics | Revenue and inventory charts |
| app/(app)/settings.tsx | /settings | Profile, plan display, sign out |
| app/(auth)/login.tsx | /login | Email/password login |
| app/(auth)/signup.tsx | /signup | Email/password registration |
| app/(auth)/forgot-password.tsx | /forgot-password | Password reset email |

### Libraries — lib/

| File | Responsibility |
|------|---------------|
| lib/supabase.ts | Supabase client (AsyncStorage). UserProfile interface. getProfile, getUserPlan |
| lib/api-client.ts | Authenticated HTTP client. Auto-refreshes token within 60s of expiry |
| lib/use-api-call.ts | Hook around apiClient. On 401 → refresh → sign out if still failing |
| lib/notifications.ts | Expo push notification registration |
| lib/platform.ts | Platform detection utilities |

### Components — components/

| File | Responsibility |
|------|---------------|
| components/app/EnterpriseGate.tsx | Shown when plan < enterprise |
| components/app/LowStockAlert.tsx | Low-stock alert banner |
| components/app/StockCard.tsx | Stock item card |
| components/ui/Button.tsx | Button with LinearGradient |
| components/ui/Card.tsx | Glass-effect card |
| components/ui/Input.tsx | Styled text input |
| components/ui/ThemeToggle.tsx | Dark/light toggle |

### Config

| File | Responsibility |
|------|---------------|
| mobile/app.json | Expo config: bundle ID, version, typedRoutes:true |
| mobile/tsconfig.json | ignoreDeprecations:"5.0", path alias @/* |
| mobile/.expo/types/router.d.ts | Typed route manifest — update manually when adding screens |
| mobile/tailwind.config.js | NativeWind config |

---

## KNOWN TEMPORARY BYPASSES — fix before public launch

| Where | What | How to fix |
|-------|------|-----------|
| backend/app/middleware/auth.py | JWT signature verification disabled | Set SUPABASE_JWT_SECRET in Railway from Supabase Dashboard → Settings → API → JWT Secret. Then uncomment the `if settings.SUPABASE_JWT_SECRET:` block |
| backend/app/config.py | SUPABASE_JWT_SECRET, PORTAL_JWT_SECRET, AUTH_JWT_SECRET production checks disabled | Set real secret values in Railway Variables, then uncomment all 3 validation blocks |
| mobile/app/_layout.tsx | TOKEN_REFRESH_FAILED handler commented out | Uncomment once needed |

---

## RULES QUICK REFERENCE

| Rule | What never to do |
|------|-----------------|
| CORS | Never allow_origins=["*"]. CORS must be outermost middleware |
| Auth | Every endpoint needs auth dependency. Every DB query filters by org_id |
| Errors | Every endpoint needs try/except. No stack traces to client. Always JSON |
| Env vars | Never hardcode URLs/secrets. Add to .env.example + Railway + Vercel |
| Database | Every model change needs a migration. Soft deletes. Paginate lists |
| Frontend | All calls via lib/api-client.ts. 401 → redirect to login |
| Supabase | Always check isSupabaseConfigured() before calling auth methods |
| Next.js | npm install --legacy-peer-deps. Portal paths excluded from locale middleware |
| Stripe | Always verify webhook signature |
| AI | No OpenAI in ai_engine.py. GPT-4o only in integrations.py |
