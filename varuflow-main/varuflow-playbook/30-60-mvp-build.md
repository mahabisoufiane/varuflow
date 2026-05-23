# Stage 30–60: MVP Build Checklist

The goal of this stage is to ship v1 with only the essentials and get it into users' hands fast.

---

## Build Checklist

### Authentication ✅

- [x] Supabase magic link login
- [x] Password login fallback
- [ ] Auth callback route (/auth/callback)
- [x] Protected routes via middleware
- [ ] Email confirmation flow tested end-to-end
- [ ] Password reset flow

### Onboarding

- [x] Onboarding page exists (/onboarding)
- [ ] Step 1: Enter company name
- [ ] Step 2: Connect Fortnox (OAuth or API key)
- [ ] Step 3: Initial stock import from Fortnox
- [ ] Completion state redirects to dashboard

### Core Inventory Workflow

- [x] Inventory page exists (/inventory)
- [ ] List all products with name, SKU, current stock, unit
- [ ] Filter/search by name or SKU
- [ ] Low-stock indicator (highlight rows below threshold)
- [ ] Click product → detail view with stock history
- [ ] Manual adjustment form (+ / − with reason note)

### Fortnox Integration

- [x] Integration status page exists
- [ ] OAuth connection flow (client_id, client_secret, redirect)
- [ ] Pull product catalog from Fortnox API
- [ ] Pull invoice lines to calculate sold quantities
- [ ] Webhook or scheduled sync (every 15 min)
- [ ] Handle Fortnox API rate limits gracefully

### Analytics

- [x] Analytics page exists
- [ ] Stock movement chart (last 30 days)
- [ ] Top 5 most sold products this month
- [ ] Low-stock count widget on dashboard

### Infrastructure

- [x] Docker Compose setup (frontend + backend)
- [x] Supabase (cloud)
- [x] .env.local documented and validated
- [x] Health check endpoint (GET /api/health)
- [ ] Error monitoring (Sentry free tier)
- [ ] Basic logging on FastAPI (structured JSON logs)

### Support Channel

- [ ] Add Crisp or Tawk.to chat widget to dashboard
- [ ] Create support@varuflow.com or similar
- [ ] Add feedback button to sidebar

---

## Definition of "Done" for MVP

The MVP is done when ONE real user can:

1. Sign up
2. Connect their Fortnox account
3. See their real stock levels
4. Receive a low-stock alert
5. Tell a friend what the product does

If any of those five steps fail, the MVP is not done.

---

## Tech Debt to Accept (for now)

- No mobile optimization — desktop only until feedback justifies it
- No real-time WebSocket sync — polling every 15 min is fine
- No i18n for error messages — English only for v1
- No automated tests — add after first 10 users confirm the workflow

## Tech Debt NOT to Accept

- Broken auth flow
- Unhandled API errors that crash the UI
- Missing loading states (skeleton loaders required)
- Env vars hardcoded in source code
