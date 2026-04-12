# Learning Varuflow — How to Build, Understand, and Extend This SaaS

This is your personal learning curriculum for the Varuflow codebase.
Every module explains: **what it is**, **why it exists**, **which files to read**, and **how to practice**.
Read it module by module, in order. You built this app — this guide will help you understand *why* every decision was made.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│  USERS                                                       │
│  Browser (Next.js)   Mobile (Expo/React Native)   Portal    │
└───────────────┬──────────────────────────────────────────────┘
                │ HTTPS / REST JSON
┌───────────────▼──────────────────────────────────────────────┐
│  BACKEND  (FastAPI on Railway)                               │
│  15 routers → ~80 endpoints                                  │
│  Middleware: Rate Limit → CORS → Security Headers → Logging  │
│  Auth: Supabase JWT validation (+ local auth system)         │
│  Plan Gates: FREE < PRO                                      │
└───────────────┬──────────────────────────────────────────────┘
                │ Async SQLAlchemy (asyncpg)
┌───────────────▼──────────────────────────────────────────────┐
│  DATABASE  (PostgreSQL 16 on Supabase)                       │
│  27 tables across 7 model files                              │
│  Alembic migrations run automatically on every deploy        │
└──────────────────────────────────────────────────────────────┘

EXTERNAL SERVICES
├─ Supabase Auth  → user login, JWT tokens
├─ Stripe         → payment links + SaaS subscription billing
├─ Resend         → transactional email (invoices, reminders)
├─ OpenAI         → GPT-4o chat (ONLY in integrations.py)
├─ Fortnox        → Swedish accounting ERP sync (OAuth2)
└─ Sentry         → error tracking in production
```

**Deployment:**
- Frontend → Vercel (auto-deploy on `git push main`)
- Backend → Railway (auto-deploy on `git push main`)
- Mobile → Expo EAS (manual build + submit to stores)

---

## MODULE 1: Development Environment

### What this is
How to run Varuflow on your own machine so you can make changes and test them before pushing to production.

### Why it exists
You should never develop directly on Railway/Vercel. Every change must be tested locally first.

### Files to read
- `docker-compose.yml` — spins up local PostgreSQL
- `backend/.env.example` — all backend env vars with placeholder values
- `frontend/.env.local.example` — all frontend env vars

### How to run everything locally

**1. Database (PostgreSQL)**
```bash
docker-compose up -d   # starts PostgreSQL on localhost:5432
```

**2. Backend (FastAPI)**
```bash
cd backend
poetry install         # install all Python dependencies
cp .env.example .env   # copy example, fill in real values
# Set ENV=development in .env — this enables the dev bypass
poetry run uvicorn app.main:app --reload --port 8000
```
The backend starts at `http://localhost:8000`.
Visit `http://localhost:8000/docs` to see every API endpoint in an interactive UI.

**3. Frontend (Next.js)**
```bash
cd frontend
npm install --legacy-peer-deps   # must use this flag — ESLint peer dep conflict
cp .env.local.example .env.local  # set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                       # starts on http://localhost:3000
```
Uses Turbopack (fast dev server) — do NOT pass `--webpack`.

**4. Mobile (Expo)**
```bash
cd mobile
npm install --legacy-peer-deps
npx expo start
# Scan QR code with Expo Go app on your phone
```

### What `ENV=development` does
When `ENV=development` is set in `backend/.env`, the backend:
1. Skips JWT signature verification — you don't need a real Supabase token
2. Creates a fake dev user (`00000000-0000-0000-0000-000000000001`) and org automatically on first request
3. Auto-creates the org in the database on first request
4. Allows requests with NO token at all (returns dev user)

This is controlled entirely by `backend/app/middleware/auth.py` and `backend/app/config.py`.

**⚠️ NEVER set `ENV=development` on Railway. It opens auth bypass to everyone.**

### Practice
1. Start all three services locally
2. Visit `http://localhost:3000/en/dashboard` — it should load without logging in (dev bypass)
3. Visit `http://localhost:8000/docs` — find the `GET /api/health` endpoint and try it
4. Stop docker-compose, then try to load the dashboard again — observe the 500 error (database is down)

---

## MODULE 2: Database and Models

### What this is
PostgreSQL is the database. SQLAlchemy is the ORM (Object-Relational Mapper) — it lets you write Python classes instead of raw SQL. Alembic manages database schema changes (migrations).

### Why it exists
Every piece of Varuflow data — products, invoices, customers, organizations — is stored in PostgreSQL tables. The models are the source of truth for the schema.

### Files to read
- `backend/app/database.py` — database connection setup
- `backend/app/models/organization.py` — Organization, OrganizationMember
- `backend/app/models/inventory.py` — Product, StockLevel, Warehouse, Supplier, PurchaseOrder
- `backend/app/models/invoicing.py` — Customer, Invoice, InvoiceLineItem, Payment, RecurringInvoice, CustomerPortalToken
- `backend/app/models/pos.py` — PosSession, PosSale, PosSaleItem
- `backend/app/models/auth.py` — AuthUser, AuthRefreshToken, AuthLoginAttempt (local auth)
- `backend/app/models/waitlist.py` — Waitlist
- `backend/alembic/` — migration history

### How the database connection works

`database.py` sets up one async connection pool shared by all requests:

```python
# backend/app/database.py

engine = create_async_engine(
    DATABASE_URL,           # from config.py / Railway env var
    pool_size=10,           # 10 persistent connections
    max_overflow=20,        # up to 20 extra connections at peak
    pool_pre_ping=True,     # auto-reconnect if a connection drops
    pool_recycle=1800,      # recycle connections every 30 min
)

async def get_db():
    async with async_session() as session:
        yield session       # inject session into each request
```

Every route gets its own session (injected via `Depends(get_db)`), which auto-commits or auto-rolls back.

### How SQLAlchemy models work

A model is a Python class that maps to a database table. Example from `models/inventory.py`:

```python
class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    sell_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reorder_level: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
```

Key concepts:
- `Mapped[type]` — tells Python (and your IDE) what type the column is
- `mapped_column(...)` — defines the actual database column
- `ForeignKey("organizations.id")` — link to another table
- `index=True` — creates a database index (makes queries on this column fast)
- `default=uuid.uuid4` — Python-side default (called when you create a new row)

### Multi-tenant scoping — the most important rule

Every table has `org_id`. Every query MUST filter by `org_id`. This prevents one organization from ever seeing another organization's data.

```python
# CORRECT — filters by org_id
result = await db.execute(
    select(Invoice).where(Invoice.org_id == org_id)
)

# WRONG — returns ALL invoices from all organizations
result = await db.execute(select(Invoice))
```

`org_id` is always extracted from the authenticated user's JWT via `get_current_member()`.

### Relationships

Use `relationship()` to link models together:

```python
class Invoice(Base):
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"))
    customer: Mapped["Customer"] = relationship(back_populates="invoices")
    line_items: Mapped[list["InvoiceLineItem"]] = relationship(back_populates="invoice")
```

To load related data in a query, use `selectinload`:
```python
result = await db.execute(
    select(Invoice)
    .options(selectinload(Invoice.line_items))
    .where(Invoice.id == invoice_id)
)
```

### Alembic migrations

Every time you change a model (add a field, rename a column, add a table), you must create a migration. Migrations run automatically on every Railway deploy (`main.py` lifespan calls `alembic upgrade head`).

**Create a migration:**
```bash
cd backend
alembic revision --autogenerate -m "add notes field to products"
# Review the generated file in alembic/versions/
alembic upgrade head    # apply it to your local database
```

**Roll back a migration:**
```bash
alembic downgrade -1    # undo the most recent migration
```

**⚠️ Always review auto-generated migrations before applying.** Alembic sometimes misses things (like index creation on foreign keys) or generates wrong SQL.

### Database schema at a glance

```
organizations ──< organization_members
     │
     ├──< products ──< stock_levels
     │        └──< stock_movements
     │
     ├──< warehouses ──< stock_levels
     │                └──< stock_movements
     │
     ├──< suppliers ──< purchase_orders ──< purchase_order_items
     │
     ├──< customers ──< invoices ──< invoice_line_items
     │         │            └──< payments
     │         ├──< customer_portal_tokens
     │         └──< recurring_invoices
     │
     └──< pos_sessions ──< pos_sales ──< pos_sale_items
```

### Practice
1. Open `backend/app/models/inventory.py` and read the full `Product` model
2. Add a field `weight_kg: Mapped[float | None] = mapped_column(Numeric(8, 3), nullable=True)` to `Product`
3. Run `alembic revision --autogenerate -m "add weight_kg to products"`
4. Open the generated file and verify the SQL is correct
5. Run `alembic upgrade head` and check the column was added

---

## MODULE 3: FastAPI Backend

### What this is
FastAPI is the Python framework that handles all API requests. It routes HTTP requests to the right Python function, validates input, and returns JSON responses.

### Why it exists
The frontend and mobile apps need a backend to store and retrieve data, run business logic, and connect to third-party services (Stripe, Resend, etc.).

### Files to read
- `backend/app/main.py` — app setup, middleware, router registration
- `backend/app/routers/` — 15 router files, one per module
- `backend/app/schemas/` — Pydantic input/output models
- `backend/app/middleware/` — auth, rate limit, plan check

### Project structure

```
backend/app/
├── main.py              ← Entry point. Registers middleware + routers
├── config.py            ← All env vars (Settings class)
├── database.py          ← SQLAlchemy async engine + get_db dependency
├── models/              ← SQLAlchemy ORM models (database tables)
├── routers/             ← API route handlers (one file per module)
├── schemas/             ← Pydantic request/response schemas
├── middleware/          ← auth.py, rate_limit.py, plan_check.py
└── services/            ← email.py, pdf_generator.py, scheduler.py
```

### How a router works

A router groups related endpoints. Example from `billing.py`:

```python
from fastapi import APIRouter, Depends
from app.middleware.auth import get_current_member

router = APIRouter(prefix="/api/billing", tags=["billing"])

@router.post("/checkout")
async def create_checkout_session(
    ctx: tuple = Depends(get_current_member),   # auth required
    db: AsyncSession = Depends(get_db),          # database session injected
):
    _, member = ctx           # member.org_id is the current user's org
    # ... business logic
    return {"url": stripe_url}
```

The router is registered in `main.py`:
```python
app.include_router(billing.router)
```

### Dependency injection

FastAPI's `Depends()` system injects values into route functions:

| Dependency | What it provides |
|---|---|
| `Depends(get_db)` | Async database session (auto-committed/rolled back) |
| `Depends(get_current_user)` | `{user_id: UUID, email: str}` from JWT |
| `Depends(get_current_member)` | `(user_dict, OrganizationMember)` tuple — use this in most routes |
| `Depends(require_plan(OrgPlan.PRO))` | Raises 403 if org plan is below PRO |

```python
# Most route functions start like this:
async def my_endpoint(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    current_user, member = ctx
    org_id = member.org_id    # ALWAYS use this to scope queries
```

### Pydantic schemas

Pydantic validates request/response data automatically. Define input and output schemas in `schemas/`:

```python
# Input schema (what the client sends)
class ProductCreate(BaseModel):
    name: str
    sku: str
    sell_price: Decimal
    tax_rate: Decimal = Decimal("25.00")   # default value

# Output schema (what we return — hides internal fields)
class ProductOut(BaseModel):
    id: uuid.UUID
    name: str
    sku: str
    sell_price: Decimal
    model_config = ConfigDict(from_attributes=True)  # allows ORM objects
```

FastAPI automatically returns 422 if input validation fails. You never write input validation code manually.

### Error handling pattern

Every endpoint must follow this pattern (from `CLAUDE.md`):

```python
@router.post("/products")
async def create_product(
    body: ProductCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        product = Product(org_id=org_id, **body.model_dump())
        db.add(product)
        await db.commit()
        await db.refresh(product)
        return ProductOut.model_validate(product)
    except HTTPException:
        raise                           # re-raise 4xx errors as-is
    except Exception as e:
        log.error("create_product failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
```

**Rules:**
- NEVER let a Python exception reach the client as a stack trace
- ALWAYS re-raise `HTTPException` (those are intentional 4xx responses)
- Log every 500 with `org_id` and `user_id` so Railway logs are searchable

### Middleware stack and why order matters

`main.py` registers middleware in this order:

```python
app.add_middleware(SlowAPIMiddleware)     # 1. Rate limiter
app.add_middleware(RateLimitMiddleware)  # 2. Custom rate limit
app.add_middleware(CORSMiddleware)       # 3. CORS headers
# then @app.middleware("http") decorators:
#   _add_security_headers               # 4. X-Frame-Options etc
#   _log_requests                       # 5. Request logging
```

**Important:** Starlette (the server under FastAPI) processes middleware in **LIFO order** (Last In, First Out). The last `add_middleware()` call is the **outermost** layer. This means:

```
Request comes in:
→ CORSMiddleware (outermost — reads CORS headers first)
  → RateLimitMiddleware
    → SlowAPIMiddleware
      → Security headers
        → Logging
          → Your route function
```

CORS must be outermost so ALL responses (including 429 rate limit and 500 errors) have the `Access-Control-Allow-Origin` header. Without it, browsers will block the response.

### CORS — why it's the #1 production killer

CORS (Cross-Origin Resource Sharing) is a browser security mechanism. When your frontend at `https://varuflow.vercel.app` calls your backend at `https://varuflow-production.up.railway.app`, the browser first sends a preflight `OPTIONS` request to ask "are cross-origin requests allowed?"

If the backend doesn't respond correctly, **ALL API calls fail in the browser** (but still work in Postman/curl, which is confusing).

The fix is already in `main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),  # reads from env var
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],  # OPTIONS is critical
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)
```

**⚠️ Never use `allow_origins=["*"]` in production** — it allows any website to call your API.

### Every router walkthrough

| Router file | Prefix | What it does |
|---|---|---|
| `health.py` | `/api/health` | Returns `{status: ok, db: ok}`. No auth. Used by uptime monitors. |
| `waitlist.py` | `/api/waitlist` | Saves email to waitlist. No auth (public). |
| `auth.py` | `/api/auth` | Supabase user onboarding (creates org on first login), `/me` |
| `local_auth.py` | `/api/local-auth` | Standalone email/password auth system (separate from Supabase) |
| `inventory.py` | `/api/inventory` | Products, warehouses, stock levels, movements, suppliers, purchase orders |
| `invoicing.py` | `/api/invoicing` | Customers, invoices, line items, payments, PDF export, Stripe payment links |
| `recurring.py` | `/api/recurring` | Recurring invoice templates, pause/resume |
| `billing.py` | `/api/billing` | Stripe checkout (SaaS subscription), customer portal, webhook |
| `analytics.py` | `/api/analytics` | Revenue charts, inventory metrics, customer RFM (PRO only) |
| `ai_engine.py` | `/api/ai` | Rules-based action cards — NO OpenAI. Pure SQL + Python logic. |
| `integrations.py` | `/api/integrations` | Fortnox OAuth2 sync + GPT-4o chat (ONLY place OpenAI is called) |
| `portal.py` | `/api/portal` | B2B customer portal: magic link auth, customer invoice view, Stripe pay |
| `pos.py` | `/api/pos` | Point-of-sale sessions, sales, barcode product lookup |
| `team.py` | `/api/team` | Invite team members, change roles, remove members |

### Rate limiting

`middleware/rate_limit.py` limits each IP to 200 requests/minute. On Railway, client IPs come from the `X-Forwarded-For` header (set by Railway's load balancer). `TRUST_PROXY=True` in config tells the rate limiter to trust that header.

Without `TRUST_PROXY=True`, all requests would appear to come from Railway's internal IP, and the rate limiter would block the entire app after 200 requests.

### Practice
1. Read `backend/app/routers/health.py` — it's the simplest router (15 lines)
2. Read `backend/app/routers/inventory.py` — the `list_products` function. Count how many times `org_id` is used to filter queries.
3. Add a new endpoint `GET /api/inventory/products/count` that returns `{"count": 42}` (the number of products for the current org)
4. Test it at `http://localhost:8000/docs`

---

## MODULE 4: Authentication

### What this is
Authentication is how the app knows who is making each request. There are three separate auth systems in Varuflow.

### Why it exists
Without auth, anyone could access anyone else's invoices and data. Auth ensures every request is tied to a specific user and organization.

### Files to read
- `backend/app/middleware/auth.py` — JWT validation, `get_current_user`, `get_current_member`
- `backend/app/models/auth.py` — Local auth database models
- `backend/app/routers/local_auth.py` — Local auth endpoints
- `backend/app/routers/auth.py` — Supabase onboarding endpoint
- `frontend/src/lib/supabase/client.ts` — Browser Supabase client
- `frontend/src/lib/api-client.ts` — Auto Bearer token attachment
- `mobile/app/_layout.tsx` — Root auth guard
- `mobile/app/(app)/_layout.tsx` — App-section auth guard

### System 1: Supabase Auth (primary)

This is how most users log in.

**Flow:**
```
1. User fills email + password on /auth/signup
2. Frontend calls: supabase.auth.signUp({ email, password })
3. Supabase sends confirmation email
4. User clicks link → browser navigates to /en/auth/callback?code=...
5. Callback page calls: supabase.auth.exchangeCodeForSession(code)
6. Supabase returns: { access_token, refresh_token, user }
7. Tokens stored in localStorage by Supabase client
8. Frontend calls POST /api/auth/onboarding to create org in database
9. User redirected to dashboard
```

**Every subsequent request:**
```
1. api-client.ts reads token: supabase.auth.getSession()
2. If token expires within 60 seconds → auto-refresh
3. Attaches: Authorization: Bearer <JWT>
4. Backend auth.py calls jwt.decode() to extract user_id and email
5. Backend calls get_current_member() to find the OrganizationMember row
6. Route function receives (user, member) and can read member.org_id
```

### What is a JWT?

A JWT (JSON Web Token) looks like this:
```
eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyLXV1aWQiLCJlbWFpbCI6InVzZXJAZXhhbXBsZS5jb20iLCJleHAiOjE3MDAwMDAwMDB9.signature
```

It has three parts separated by dots:
1. **Header** — algorithm (`HS256`)
2. **Payload** — data (`sub` = user ID, `email`, `exp` = expiry timestamp)
3. **Signature** — HMAC hash of header+payload using the secret key

The backend verifies the signature using `SUPABASE_JWT_SECRET`. If anyone tampers with the payload, the signature check fails and the request is rejected.

**⚠️ Currently, signature verification is disabled in `auth.py` because `SUPABASE_JWT_SECRET` on Railway doesn't match the actual Supabase secret. This must be fixed before launch:**

```python
# backend/app/middleware/auth.py (currently bypassed)

# TODO: Uncomment this block and set SUPABASE_JWT_SECRET correctly in Railway:
# if settings.SUPABASE_JWT_SECRET:
#     return jwt.decode(
#         token,
#         settings.SUPABASE_JWT_SECRET,
#         algorithms=["HS256"],
#         options={"verify_aud": False},
#     )
# if settings.ENV != "development":
#     raise JWTError("SUPABASE_JWT_SECRET not configured")

# Remove this line when the block above is uncommented:
return jwt.decode(token, "", algorithms=["HS256"], options={"verify_signature": False})
```

### System 2: Portal Auth (B2B customer access)

Wholesale customers (e.g. a retailer who buys from you) get access to a customer portal to view and pay their own invoices. They do NOT have Supabase accounts — they use magic links.

**Flow:**
```
1. Seller clicks "Send portal link" for customer
2. Backend: POST /api/portal/auth/send-link
   → Creates CustomerPortalToken (one-time, 15-min expiry)
   → Sends magic link email: /portal/auth/verify?token=...
3. Customer clicks link
4. Backend: POST /api/portal/auth/verify
   → Validates token (not used, not expired)
   → Marks token as used (prevents replay)
   → Returns portal JWT with payload: {sub: customer_id, org_id, type: "portal"}
5. Frontend stores portal_token
6. GET /api/portal/invoices attaches portal_token as Bearer
7. Backend accepts portal token on portal routes only
```

**Why portal tokens can't access internal routes:**
```python
# backend/app/middleware/auth.py
if payload.get("type") == "portal":
    raise HTTPException(
        status_code=401,
        detail="Portal tokens cannot be used on internal routes",
    )
```

### System 3: Local Auth (standalone email/password)

A fully custom auth system that doesn't depend on Supabase. Uses bcrypt password hashing, JWT access tokens (15-min), and rotating refresh tokens (7-day).

**Key features:**
- `AuthRefreshToken` table stores SHA-256 hash of the token (never the raw token)
- After 5 failed logins → account locked for 15 minutes
- TOTP/MFA supported via pyotp (Google Authenticator compatible)
- Every login attempt logged in `auth_login_attempts` (audit trail)

**Refresh token rotation:**
```
1. POST /api/local-auth/login → returns {access_token (15min), refresh_token (7d)}
2. When access_token expires → POST /api/local-auth/refresh with refresh_token
3. Server issues new access_token AND new refresh_token
4. Old refresh_token is revoked in database
5. If refresh_token is stolen and used twice → second use fails (token revoked)
```

### Mobile auth guard pattern

The mobile app has TWO auth guards, not one. This prevents deep-link bypass attacks:

**Guard 1** (`app/_layout.tsx`): Listens to Supabase auth state changes. If session disappears → redirect to login.

**Guard 2** (`app/(app)/_layout.tsx`): Runs on EVERY entry to the app section. Checks session + plan tier:
```typescript
useEffect(() => {
  async function guard() {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) { router.replace("/(auth)/login"); return; }
    const plan = await getUserPlan(session.user.id);
    if (plan !== "enterprise") { router.replace("/(auth)/login"); return; }
    setChecked(true);
  }
  guard();
}, []);
```

Why two guards? Guard 1 only fires when auth state *changes*. If someone deep-links directly to a protected screen (e.g. via a push notification), Guard 1 might not fire because there's no state change event. Guard 2 always fires.

### Practice
1. Open `http://localhost:8000/docs` and call `POST /api/local-auth/signup` with a test email/password
2. Then call `POST /api/local-auth/login` and copy the `access_token`
3. Call `GET /api/local-auth/me` — paste the token in the Authorize button at the top
4. Try calling `GET /api/local-auth/me` without a token — observe the 401 response
5. Try calling `POST /api/local-auth/login` with a wrong password 5 times — observe the lockout

---

## MODULE 5: Next.js Frontend

### What this is
The web app that users interact with. Built with Next.js 16 App Router, TypeScript, Tailwind CSS, and shadcn/ui components.

### Why it exists
The frontend is what users actually see and click. It fetches data from the backend API and renders it.

### Files to read
- `frontend/src/lib/api-client.ts` — all API calls go here
- `frontend/src/lib/supabase/client.ts` — Supabase browser client
- `frontend/src/i18n/request.ts` — locale detection
- `frontend/messages/{en,sv,no,da}.json` — UI text translations
- `frontend/next.config.mjs` — Next.js configuration
- `frontend/src/app/[locale]/` — all pages

### App Router file structure

```
frontend/src/app/
├── [locale]/                  ← captures /en, /sv, /no, /da
│   ├── layout.tsx             ← root layout (font, theme, toaster)
│   ├── (marketing)/           ← public pages (no auth needed)
│   │   ├── page.tsx           ← landing page (/)
│   │   └── pricing/           ← pricing page
│   ├── auth/                  ← auth pages
│   │   ├── signup/            ← sign up + plan selection
│   │   ├── login/             ← log in
│   │   ├── callback/          ← OAuth exchange
│   │   ├── forgot-password/   ← reset email
│   │   └── reset-password/    ← set new password
│   ├── onboarding/            ← 3-step org setup (runs after signup)
│   └── (app)/                 ← protected pages (need auth)
│       ├── layout.tsx         ← app shell (sidebar, header)
│       ├── dashboard/
│       ├── inventory/
│       │   ├── products/
│       │   │   ├── new/
│       │   │   └── [id]/
│       │   ├── movements/
│       │   ├── suppliers/
│       │   ├── warehouses/
│       │   └── purchase-orders/
│       ├── invoices/
│       │   ├── new/
│       │   └── [id]/
│       ├── customers/
│       │   └── new/
│       ├── recurring/
│       ├── pos/
│       ├── analytics/         ← PRO only
│       ├── ai/                ← PRO only
│       └── settings/
└── portal/                    ← B2B customer portal (no locale)
    ├── page.tsx
    ├── login/
    ├── auth/verify/
    └── invoices/
        └── [id]/
```

### How api-client.ts works

Every single API call in the entire frontend goes through `src/lib/api-client.ts`. Never use raw `fetch()`. This is the most important file to understand.

```typescript
// Example usage in any page:
import { api } from "@/lib/api-client";

// GET
const products = await api.get<Product[]>("/api/inventory/products");

// POST
const invoice = await api.post<Invoice>("/api/invoicing/invoices", {
  customer_id: "...",
  line_items: [...]
});

// DELETE
await api.delete(`/api/inventory/products/${id}`);

// File upload
const result = await api.upload<ImportResult>("/api/inventory/import", file);
```

**What api-client.ts does automatically:**
1. Reads the Supabase JWT from localStorage
2. If token expires within 60 seconds → refreshes it first
3. Adds `Authorization: Bearer <token>` to every request
4. If backend returns 401 → tries to refresh token once, retries request
5. If refresh fails → calls `supabase.auth.signOut()` (redirects to login)
6. If backend returns 500 → shows a sonner toast notification
7. Converts all error messages to human-readable English

### How next-intl works

Every page is under `/[locale]/`. The locale is extracted from the URL and used to load the correct translation file.

Add a new translation:
1. Add the key to `frontend/messages/en.json`
2. Add the same key to `sv.json`, `no.json`, `da.json`
3. In your component: `const t = useTranslations("yourNamespace")` then `t("yourKey")`

**Portal routes are excluded from locale** — `/portal/...` does not have a locale prefix. This is configured in `frontend/src/middleware.ts`.

### Supabase client pattern

```typescript
// frontend/src/lib/supabase/client.ts
export const isSupabaseConfigured = Boolean(SUPABASE_URL) && Boolean(SUPABASE_ANON_KEY);

export function createClient() {
  if (!isSupabaseConfigured) {
    // Returns a stub so the app doesn't crash when env vars are missing
    return createBrowserClient("https://placeholder.supabase.co", "placeholder-key");
  }
  return createBrowserClient(SUPABASE_URL, SUPABASE_ANON_KEY);
}
```

**Always check `isSupabaseConfigured` before calling auth methods:**
```typescript
if (!isSupabaseConfigured) {
  // show a message, don't call supabase.auth.signIn
  return;
}
const supabase = createClient();
await supabase.auth.signInWithPassword({ email, password });
```

### Component library

Varuflow uses shadcn/ui — pre-built React components built on top of Radix UI (accessible primitives) styled with Tailwind CSS.

Components live in `frontend/src/components/ui/`. You don't write raw HTML buttons, inputs, dialogs — you use these.

Key components used everywhere:
- `Button` — all clickable buttons
- `Input`, `Label` — form inputs
- `Select` — dropdowns
- `Dialog` — modal dialogs
- `toast` from `sonner` — notification toasts

### Practice
1. Open `frontend/src/app/[locale]/(app)/dashboard/page.tsx` and read how it fetches data
2. Add a new `GET /api/inventory/products/count` endpoint to the backend (from Module 3)
3. Add the count as a KPI card to the dashboard page
4. Add the "Total Products" text to all 4 translation files (en, sv, no, da)

---

## MODULE 6: Mobile App (Expo)

### What this is
A React Native app built with Expo, using file-based routing (Expo Router), styled with NativeWind (Tailwind for React Native).

### Why it exists
Enterprise customers need a mobile app for warehouse workers to check inventory, scan barcodes, and view analytics on the go.

### Files to read
- `mobile/app/_layout.tsx` — root layout, auth listener
- `mobile/app/(app)/_layout.tsx` — protected app section layout
- `mobile/app/(auth)/login.tsx` — login screen
- `mobile/lib/supabase.ts` — Supabase client setup for React Native
- `mobile/lib/api-client.ts` — mobile API client

### Expo Router structure

Works like Next.js App Router but for React Native:
```
mobile/app/
├── _layout.tsx          ← root — auth guard, navigation container
├── (auth)/              ← public screens (no auth needed)
│   ├── login.tsx
│   ├── signup.tsx
│   └── forgot-password.tsx
└── (app)/               ← protected screens (enterprise only)
    ├── _layout.tsx      ← second auth guard
    ├── dashboard.tsx
    ├── inventory.tsx
    ├── analytics.tsx
    └── settings.tsx
```

Parenthesized folders `(auth)` and `(app)` are **route groups** — they don't appear in the URL, they just organize layout boundaries.

### Supabase in React Native

The mobile app uses `expo-secure-store` instead of localStorage to store tokens securely:

```typescript
// mobile/lib/supabase.ts
import * as SecureStore from "expo-secure-store";
import AsyncStorage from "@react-native-async-storage/async-storage";

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    storage: AsyncStorage,          // token storage
    autoRefreshToken: true,         // auto-refresh before expiry
    persistSession: true,           // keep session across app restarts
    detectSessionInUrl: false,      // not applicable in native
  },
});
```

### NativeWind (Tailwind for React Native)

Use Tailwind classes in React Native components:

```tsx
// Web (React)
<div className="flex flex-col p-4 bg-blue-500">

// React Native (NativeWind)
<View className="flex flex-col p-4 bg-blue-500">
```

Not all Tailwind utilities work in React Native — stick to: layout (flex, p, m, w, h), colors (bg-, text-), typography (text-sm, font-bold).

### Enterprise plan gate

The mobile app is only available to Enterprise plan users. This is enforced in `app/(app)/_layout.tsx`:

```typescript
const plan = await getUserPlan(session.user.id);
if (plan !== "enterprise") {
  router.replace("/(auth)/login");  // redirect out
}
```

`getUserPlan()` calls `GET /api/auth/me` to check the org's plan.

### Building for production

```bash
# Install EAS CLI
npm install -g eas-cli

# Build for iOS + Android
eas build --profile production --platform all

# Submit to App Store + Google Play
eas submit --platform all
```

EAS build profiles are in `mobile/eas.json` (preview, production, huawei).

### Practice
1. Run `npx expo start` in the `mobile/` directory
2. Open the Expo Go app on your phone and scan the QR code
3. Try the login screen with real credentials
4. Read `mobile/app/(app)/dashboard.tsx` and find the API call

---

## MODULE 7: Integrations

### What this is
External services that Varuflow connects to. Each integration has its own setup, authentication, and error handling.

---

### Stripe (Two separate integrations)

**⚠️ Varuflow has two completely separate Stripe integrations:**

1. **SaaS billing** (`/api/billing/`) — users pay for the Varuflow PRO plan
2. **Invoice payments** (`/api/invoicing/...payment-link`) — your customers pay their invoices via Stripe

Do not confuse these.

#### SaaS billing flow

```
1. User completes onboarding with plan=professional
2. Frontend calls: POST /api/billing/checkout
3. Backend creates Stripe Checkout session
4. Returns {url: "https://checkout.stripe.com/..."}
5. Frontend redirects: window.location.href = url
6. User pays on Stripe's hosted page
7. Stripe calls your webhook: POST /api/billing/webhook
8. Backend receives checkout.session.completed event
9. Upgrades org.plan = "PRO" in database
```

#### Webhook signature verification (critical)

Every webhook event MUST be verified before processing:

```python
stripe.Webhook.construct_event(
    payload=body,
    sig_header=request.headers.get("stripe-signature"),
    secret=settings.STRIPE_WEBHOOK_SECRET,
)
```

If verification fails → return 400, don't process the event. This prevents attackers from faking webhook events to upgrade their own account for free.

#### Webhook idempotency

Stripe can send the same event multiple times (if your server returns a 5xx). The `StripeProcessedEvent` table prevents processing the same event twice:

```python
try:
    db.add(StripeProcessedEvent(event_id=event.id))
    await db.commit()
except IntegrityError:
    # Already processed this event — return 200 immediately
    return {"status": "ok"}
# Now process the event...
```

---

### Supabase

Supabase hosts both the authentication system (GoTrue) and the PostgreSQL database.

**Key environment variables:**
```
SUPABASE_URL          → https://<project>.supabase.co
SUPABASE_SERVICE_KEY  → service role key (full DB access — never expose to frontend)
SUPABASE_ANON_KEY     → anon key (limited access — safe for frontend)
SUPABASE_JWT_SECRET   → JWT secret from Supabase Dashboard → Settings → API
```

**⚠️ The `SUPABASE_JWT_SECRET` must exactly match what Supabase uses to sign tokens.** Find it at: Supabase Dashboard → Your Project → Settings → API → JWT Settings → JWT Secret.

---

### Resend (Email)

Resend is used for all transactional emails: invoice sending, payment reminders, team invitations, auth verification.

**Setup:**
1. Create account at resend.com
2. Get API key
3. Set `RESEND_API_KEY` in Railway
4. Add your sending domain in Resend dashboard

**How emails are sent** (from `backend/app/services/email.py`):
```python
import httpx

async def send_email(to: str, subject: str, html: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={"from": settings.SMTP_FROM, "to": to, "subject": subject, "html": html},
        )
```

---

### Fortnox (Swedish ERP)

Fortnox is the most common accounting software for Swedish businesses. The integration lets Varuflow sync invoices and customers to Fortnox automatically.

**OAuth2 flow:**
```
1. User clicks "Connect Fortnox" in settings
2. Backend generates CSRF nonce, stores in fortnox_oauth_states table
3. Redirects to: https://apps.fortnox.se/oauth-v1/auth?client_id=...&state=<nonce>
4. User approves access in Fortnox
5. Fortnox redirects to: /api/integrations/fortnox/callback?code=...&state=<nonce>
6. Backend:
   a. Verifies state nonce (CSRF protection)
   b. Exchanges code for access_token + refresh_token
   c. Stores tokens in Organization row
7. APScheduler job runs daily to refresh tokens before expiry
```

**Why the CSRF nonce matters:** Without it, an attacker could craft a link that connects your Fortnox account to their Varuflow account. The state nonce ensures only you can complete the OAuth flow you initiated.

---

### OpenAI

GPT-4o is used for the AI chat feature. This is the **only place** OpenAI is called in the entire codebase.

**File:** `backend/app/routers/integrations.py` → `POST /api/integrations/chat`

**⚠️ NEVER add OpenAI imports to `ai_engine.py`** — those action cards are rules-based SQL, not AI.

**Always wrap OpenAI calls in try/except:**
```python
try:
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
    )
    return {"reply": response.choices[0].message.content}
except Exception as e:
    log.error("OpenAI call failed: %s", str(e))
    return {"reply": "I'm having trouble right now. Please try again in a moment."}
```

---

## MODULE 8: Deployment

### What this is
How the app gets from your laptop to production.

### Files to read
- `backend/Dockerfile` — Python container for Railway
- `frontend/next.config.mjs` — Vercel build config
- `mobile/eas.json` — Expo EAS build profiles
- `backend/.env.example` — all required backend env vars
- `frontend/.env.local.example` — all required frontend env vars

---

### Railway (Backend)

Railway deploys the backend automatically when you push to `main`.

**How it works:**
1. You push to `main` — Railway detects the change
2. Railway builds the Docker image (`backend/Dockerfile`)
3. Container starts → `uvicorn app.main:app --host 0.0.0.0 --port 8000`
4. On startup, `lifespan()` in `main.py` runs:
   - `validate_production_config()` — crashes if dangerous defaults are present
   - `alembic upgrade head` — applies any pending database migrations
   - `scheduler.start()` — starts background jobs
5. Health check: Railway pings `/api/health` to confirm the app is up

**Setting environment variables on Railway:**
1. Go to railway.app → your project → your service → Variables
2. Add each variable from `.env.example`
3. Click Deploy to apply

**Required Railway variables:**
```
ENV=production
DATABASE_URL=postgresql://...
SUPABASE_URL=https://...
SUPABASE_SERVICE_KEY=...
SUPABASE_JWT_SECRET=...
RESEND_API_KEY=...
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...
STRIPE_PRO_PRICE_ID=...
OPENAI_API_KEY=...
PORTAL_JWT_SECRET=<64-char random hex>
AUTH_JWT_SECRET=<64-char random hex>
PORTAL_BASE_URL=https://varuflow.vercel.app
FORTNOX_CLIENT_ID=...
FORTNOX_CLIENT_SECRET=...
CORS_ORIGINS=https://varuflow.vercel.app
TRUST_PROXY=True
```

---

### Vercel (Frontend)

Vercel deploys the frontend automatically when you push to `main`.

**Build command (in Vercel project settings):**
```bash
npm install --legacy-peer-deps && next build
```
The `--legacy-peer-deps` flag is required due to an ESLint peer dependency conflict with Next.js 16.

**Required Vercel variables:**
```
NEXT_PUBLIC_API_URL=https://varuflow-production.up.railway.app
NEXT_PUBLIC_SUPABASE_URL=https://...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

**Important config in `next.config.mjs`:**
```javascript
reactStrictMode: false   // Must stay false — prevents GoTrue double-init AbortError
```

---

### Expo / EAS (Mobile)

```bash
# Install once
npm install -g eas-cli
eas login

# Build (uploads to Expo cloud builder — takes ~20 minutes)
eas build --profile production --platform all

# Submit to app stores
eas submit --platform all
```

Build profiles are in `mobile/eas.json`:
- `preview` — internal testing (APK/IPA, not store-reviewed)
- `production` — store-ready build
- `huawei` — Android build for Huawei AppGallery

---

## MODULE 9: Security Checklist

### What this is
A prioritized list of security items to address before Varuflow goes public with paying users.

### ⚠️ 3 bypasses currently disabled — fix before public launch

**Fix 1: JWT signature verification** (`backend/app/middleware/auth.py`)

Currently, any JWT is accepted without verifying the signature. This means anyone can forge a token and access any account.

How to fix:
1. Go to Supabase Dashboard → Your Project → Settings → API → JWT Settings
2. Copy the JWT Secret
3. Set it as `SUPABASE_JWT_SECRET` in Railway Variables
4. In `auth.py`, uncomment the verification block and remove the bypass:
```python
# Uncomment this:
if settings.SUPABASE_JWT_SECRET:
    return jwt.decode(
        token,
        settings.SUPABASE_JWT_SECRET,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )
if settings.ENV != "development":
    raise JWTError("SUPABASE_JWT_SECRET not configured")

# Remove this:
# return jwt.decode(token, "", algorithms=["HS256"], options={"verify_signature": False})
```

**Fix 2: PORTAL_JWT_SECRET validation** (`backend/app/config.py`)

Currently, the app starts even if `PORTAL_JWT_SECRET` is the default placeholder. Fix:
1. Generate a real secret: `python -c "import secrets; print(secrets.token_hex(32))"`
2. Set it as `PORTAL_JWT_SECRET` in Railway
3. In `config.py`, uncomment:
```python
if settings.PORTAL_JWT_SECRET in _DANGEROUS_SECRETS:
    errors.append("PORTAL_JWT_SECRET is still the default placeholder...")
```

**Fix 3: AUTH_JWT_SECRET validation** (same file)

Same process as Fix 2 for `AUTH_JWT_SECRET`.

---

### Security rules checklist

**CORS:**
- [ ] `allow_origins` reads from `CORS_ORIGINS` env var (never `["*"]`)
- [ ] `CORS_ORIGINS=https://varuflow.vercel.app` on Railway (no trailing slash)
- [ ] `OPTIONS` in `allow_methods`

**Auth:**
- [ ] JWT signature verification enabled (Fix 1 above)
- [ ] `ENV=production` on Railway (dev bypass closed)
- [ ] Portal tokens rejected on internal routes (`type == "portal"` check in `auth.py`)

**Stripe:**
- [ ] Webhook signature verified before processing
- [ ] Idempotency table (`stripe_processed_events`) prevents duplicate processing
- [ ] `STRIPE_WEBHOOK_SECRET` set on Railway

**SQL injection:**
- [ ] All DB queries use SQLAlchemy ORM or parameterized queries
- [ ] No f-strings in SQL queries (e.g. `text(f"WHERE name = {name}")` is dangerous)

**Secrets:**
- [ ] No hardcoded secrets in any `.py` or `.ts` file
- [ ] `.env` and `.env.local` are in `.gitignore`
- [ ] Check: `grep -rn "sk_live\|sk_test\|whsec_" backend/app/`

**Production config:**
- [ ] `DEBUG=False` on Railway
- [ ] Uvicorn not running with `--reload` on Railway

---

## MODULE 10: Adding New Features

### How to add anything — the full recipe

Every new feature follows the same pattern. Here's the complete recipe.

---

### Step 1: Add a new database model

```python
# backend/app/models/yourmodule.py
from app.database import Base

class YourModel(Base):
    __tablename__ = "your_models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

Create the migration:
```bash
cd backend
alembic revision --autogenerate -m "add your_models table"
# Review the generated file in alembic/versions/
alembic upgrade head
```

---

### Step 2: Add a Pydantic schema

```python
# backend/app/schemas/yourmodule.py
from pydantic import BaseModel, ConfigDict

class YourModelCreate(BaseModel):
    name: str

class YourModelOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

---

### Step 3: Add a router

```python
# backend/app/routers/yourmodule.py
import logging, uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_member
from app.models.yourmodule import YourModel
from app.schemas.yourmodule import YourModelCreate, YourModelOut

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/yourmodule", tags=["yourmodule"])


def _org(ctx: tuple) -> uuid.UUID:
    _, member = ctx
    return member.org_id


@router.get("", response_model=list[YourModelOut])
async def list_items(
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        result = await db.execute(
            select(YourModel).where(YourModel.org_id == org_id)
        )
        return [YourModelOut.model_validate(r) for r in result.scalars().all()]
    except HTTPException:
        raise
    except Exception as e:
        log.error("list_items failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=YourModelOut, status_code=201)
async def create_item(
    body: YourModelCreate,
    ctx: tuple = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    org_id = _org(ctx)
    try:
        item = YourModel(org_id=org_id, **body.model_dump())
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return YourModelOut.model_validate(item)
    except HTTPException:
        raise
    except Exception as e:
        log.error("create_item failed: %s", str(e), extra={"org_id": str(org_id)})
        raise HTTPException(status_code=500, detail="Internal server error")
```

Register in `main.py`:
```python
from app.routers import yourmodule
app.include_router(yourmodule.router)
```

---

### Step 4: Add a frontend page

```typescript
// frontend/src/app/[locale]/(app)/yourmodule/page.tsx
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";
import { useTranslations } from "next-intl";
import { toast } from "sonner";

interface YourItem { id: string; name: string; }

export default function YourModulePage() {
  const t = useTranslations("yourmodule");
  const [items, setItems] = useState<YourItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<YourItem[]>("/api/yourmodule")
      .then(setItems)
      .catch(() => toast.error("Failed to load items"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      <h1>{t("title")}</h1>
      {items.map(item => <div key={item.id}>{item.name}</div>)}
    </div>
  );
}
```

Add translations to all 4 locale files:
```json
// messages/en.json — add inside the existing object:
"yourmodule": { "title": "Your Module" }

// messages/sv.json:
"yourmodule": { "title": "Din modul" }

// messages/no.json:
"yourmodule": { "title": "Din modul" }

// messages/da.json:
"yourmodule": { "title": "Dit modul" }
```

---

### Step 5: Add a mobile screen

```typescript
// mobile/app/(app)/yourscreen.tsx
import { View, Text, FlatList } from "react-native";
import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";

export default function YourScreen() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    api.get("/api/yourmodule").then(setItems).catch(console.error);
  }, []);

  return (
    <View className="flex-1 p-4">
      <Text className="text-2xl font-bold mb-4">Your Screen</Text>
      <FlatList
        data={items}
        keyExtractor={item => item.id}
        renderItem={({ item }) => <Text>{item.name}</Text>}
      />
    </View>
  );
}
```

Add to the tab navigator in `mobile/app/(app)/_layout.tsx`.

---

### Full example: "Credit Notes" feature

A credit note is a negative invoice — used when you need to refund or cancel an invoice. Here's how you'd add it from scratch:

**1. Model** — add `CreditNote` to `models/invoicing.py`:
```python
class CreditNote(Base):
    __tablename__ = "credit_notes"
    id: Mapped[uuid.UUID] = ...
    org_id: Mapped[uuid.UUID] = ...
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    reason: Mapped[str] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[DateTime] = ...
```

**2. Migration** — `alembic revision --autogenerate -m "add credit_notes table"`

**3. Router** — add endpoints to `routers/invoicing.py`:
- `POST /api/invoicing/invoices/{id}/credit-note` — create credit note
- `GET /api/invoicing/credit-notes` — list credit notes

**4. PDF** — extend `services/pdf_generator.py` with `generate_credit_note_pdf()`

**5. Frontend** — add a "Create Credit Note" button on the invoice detail page

**6. Email** — extend `services/email.py` to send the credit note PDF to the customer

Each step follows the same pattern as described above.

---

## Appendix A: All Environment Variables

### Backend (Railway)

| Variable | Description | Example |
|---|---|---|
| `ENV` | `production` on Railway, `development` locally | `production` |
| `DEBUG` | Must be `False` on Railway | `False` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| `SUPABASE_URL` | Your Supabase project URL | `https://xxx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Service role key (full DB access) | `eyJ...` |
| `SUPABASE_JWT_SECRET` | JWT signing secret (from Supabase Dashboard) | `your-jwt-secret` |
| `RESEND_API_KEY` | Resend email API key | `re_...` |
| `STRIPE_SECRET_KEY` | Stripe secret key | `sk_live_...` |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret | `whsec_...` |
| `STRIPE_PRO_PRICE_ID` | Stripe price ID for PRO plan | `price_...` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `PORTAL_JWT_SECRET` | 64-char random hex for portal tokens | `a3f2...` |
| `AUTH_JWT_SECRET` | 64-char random hex for local auth tokens | `b8c1...` |
| `PORTAL_BASE_URL` | Frontend URL for portal links | `https://varuflow.vercel.app` |
| `FORTNOX_CLIENT_ID` | Fortnox OAuth client ID | `your-client-id` |
| `FORTNOX_CLIENT_SECRET` | Fortnox OAuth client secret | `your-client-secret` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `https://varuflow.vercel.app` |
| `TRUST_PROXY` | Set True on Railway (load balancer) | `True` |
| `SENTRY_DSN` | Sentry DSN for error tracking | `https://...@sentry.io/...` |
| `SMTP_FROM` | From email address | `noreply@varuflow.se` |

### Frontend (Vercel)

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend URL: `https://varuflow-production.up.railway.app` |
| `NEXT_PUBLIC_SUPABASE_URL` | Your Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key (safe for browser) |

Generate a 64-char secret:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Appendix B: All API Endpoints

### No auth required
```
GET  /api/health
POST /api/waitlist
POST /api/portal/auth/send-link
POST /api/portal/auth/verify
```

### Local auth
```
POST /api/local-auth/signup
POST /api/local-auth/verify-email
POST /api/local-auth/login
POST /api/local-auth/refresh
POST /api/local-auth/logout
GET  /api/local-auth/me
POST /api/local-auth/mfa/enable
POST /api/local-auth/mfa/confirm
POST /api/local-auth/mfa/disable
POST /api/local-auth/password/reset
POST /api/local-auth/password/confirm
```

### Auth (Supabase users)
```
POST /api/auth/onboarding
GET  /api/auth/me
```

### Inventory
```
GET/POST              /api/inventory/products
GET/PUT/DELETE        /api/inventory/products/{id}
GET/POST              /api/inventory/stock
POST                  /api/inventory/stock/adjust
PATCH                 /api/inventory/stock/{id}/threshold
GET/POST              /api/inventory/movements
GET/POST              /api/inventory/suppliers
GET/PUT/DELETE        /api/inventory/suppliers/{id}
GET/POST              /api/inventory/warehouses
GET/PUT/DELETE        /api/inventory/warehouses/{id}
GET/POST              /api/inventory/purchase-orders
GET                   /api/inventory/purchase-orders/{id}
PATCH                 /api/inventory/purchase-orders/{id}/status
POST                  /api/inventory/purchase-orders/{id}/receive
GET                   /api/inventory/purchase-orders/{id}/pdf
POST                  /api/inventory/import
GET                   /api/inventory/forecast
```

### Invoicing
```
GET/POST              /api/invoicing/customers
GET/PUT/DELETE        /api/invoicing/customers/{id}
GET/POST              /api/invoicing/invoices
GET/PUT               /api/invoicing/invoices/{id}
POST                  /api/invoicing/invoices/{id}/send
POST                  /api/invoicing/invoices/{id}/payment-link
GET                   /api/invoicing/invoices/{id}/pdf
POST                  /api/invoicing/invoices/{id}/credit-note (add this!)
POST                  /api/invoicing/payments
```

### Billing (Stripe SaaS)
```
POST /api/billing/checkout
POST /api/billing/portal
POST /api/billing/webhook
```

### Analytics (PRO)
```
GET /api/analytics/overview
GET /api/analytics/inventory
GET /api/analytics/customers
```

### AI Engine (PRO)
```
GET  /api/ai/cards
POST /api/ai/actions/send-reminder
POST /api/ai/actions/mark-seen
```

### Integrations
```
GET  /api/integrations/config
GET  /api/integrations/fortnox/connect
GET  /api/integrations/fortnox/callback
GET  /api/integrations/fortnox/status
DELETE /api/integrations/fortnox/disconnect
POST /api/integrations/fortnox/sync
POST /api/integrations/chat
```

### Portal (portal JWT)
```
GET  /api/portal/invoices
GET  /api/portal/invoices/{id}
POST /api/portal/invoices/{id}/pay
```

### POS
```
GET/POST              /api/pos/sessions
POST                  /api/pos/sessions/{id}/close
POST                  /api/pos/sales
GET                   /api/pos/products
```

### Team
```
GET    /api/team/members
POST   /api/team/invite
PATCH  /api/team/members/{id}
DELETE /api/team/members/{id}
```

### Recurring
```
GET/POST              /api/recurring
GET/PUT/DELETE        /api/recurring/{id}
POST                  /api/recurring/{id}/pause
POST                  /api/recurring/{id}/resume
```

---

## Appendix C: Common Errors and Fixes

| Error | Cause | Fix |
|---|---|---|
| CORS blocks all API calls | CORSMiddleware not first, or wrong origins | Check `main.py` middleware order; verify `CORS_ORIGINS` on Railway |
| All 401 errors | JWT secret mismatch | Set correct `SUPABASE_JWT_SECRET` on Railway, re-enable signature verification in `auth.py` |
| All 404 errors (backend) | `validate_production_config()` crashed startup | Check Railway logs; a secret validation failed; fix the env var causing the crash |
| `supabase.auth.signIn is not a function` | Supabase client is null | Check `isSupabaseConfigured` before calling auth methods |
| `localhost:9999 ERR_CONNECTION_REFUSED` | Wrong `SUPABASE_URL` pointing to local | Set correct hosted Supabase URL in Vercel env vars |
| `Module not found: Can't resolve 'react-is'` | Stale Docker volume | `docker volume rm varuflow_frontend_node_modules` |
| `experimental.turbo` warning in Next.js | Old config key | Remove it from `next.config.mjs` |
| GoTrue double-init AbortError | React Strict Mode | Keep `reactStrictMode: false` in `next.config.mjs` |
| TypeScript error on `ignoreDeprecations` | Invalid value | Use `"5.0"` not `"6.0"` |
| 422 on Supabase `emailRedirectTo` | Double-encoded URL | Use `encodeURIComponent()`, not manual `%3F` encoding |
| Alembic fails on Railway startup | Migration error | Check Railway deploy logs; run locally first with `alembic upgrade head` |

---

## Appendix D: Useful Commands

### Backend
```bash
# Start backend locally
cd backend && poetry run uvicorn app.main:app --reload

# Install dependencies
poetry install

# Add a dependency
poetry add <package-name>

# Create a migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1

# See migration history
alembic history

# Check current migration
alembic current

# Run tests
poetry run pytest

# Lint code
poetry run ruff check app/

# Type check
poetry run mypy app/
```

### Frontend
```bash
# Start frontend locally (with Turbopack)
cd frontend && npm run dev

# Install dependencies (always use this flag)
npm install --legacy-peer-deps

# Add a package
npm install <package> --legacy-peer-deps

# Type check
npx tsc --noEmit

# Build for production
npm run build

# Run linter
npm run lint
```

### Mobile
```bash
# Start Expo dev server
cd mobile && npx expo start

# Install dependencies
npm install --legacy-peer-deps

# Build for production
eas build --profile production --platform all

# Submit to stores
eas submit --platform all

# Update Expo Router typed routes (after adding new screens)
npx expo export --dump-sourcemap
```

### Git
```bash
# Push to production (triggers Railway + Vercel deploy)
git push origin main

# Check what changed
git diff HEAD~1

# Undo last commit (keep changes)
git reset --soft HEAD~1

# See Railway deploy logs
# → Go to railway.app → your project → Deployments → click the deploy
```

### Security secrets
```bash
# Generate a 64-character random secret for PORTAL_JWT_SECRET or AUTH_JWT_SECRET
python -c "import secrets; print(secrets.token_hex(32))"

# Verify no hardcoded secrets in backend code
grep -rn "sk_live\|sk_test\|whsec_\|re_[a-zA-Z]" backend/app/

# Verify no hardcoded Railway URL in frontend
grep -r "varuflow-production.up.railway.app" frontend/src

# Verify CORS is not wildcarded
grep -r 'allow_origins=\["\*"\]' backend/
```
