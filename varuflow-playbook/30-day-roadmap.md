# 30-Day Roadmap

A concrete, week-by-week plan for Varuflow based on the current state of the codebase (auth working, dashboard scaffolded, Fortnox integration in progress).

---

## Current State (Day 0)

- ✅ Auth: magic link + password login working
- ✅ Onboarding page exists
- ✅ Inventory, Analytics, Settings pages scaffolded
- ✅ Fortnox integration status page exists
- ✅ Docker Compose dev environment running
- ❌ Fortnox OAuth flow not complete
- ❌ Real stock data not yet pulling
- ❌ No pricing/billing
- ❌ No error monitoring

---

## Week 1 (Days 1–7): Make It Real

**Goal:** one real user can see their real Fortnox stock data.

| Day | Task | Stack |
|-----|------|-------|
| 1 | Complete Fortnox OAuth flow (client_id → token → refresh) | FastAPI |
| 2 | `GET /api/integrations/fortnox/products` — pull product catalog | FastAPI |
| 3 | `GET /api/integrations/fortnox/invoices` — pull sold quantities | FastAPI |
| 4 | Populate inventory table in Supabase from Fortnox data | FastAPI + Supabase |
| 5 | Render real products in Inventory page (replace mock data) | Next.js |
| 6 | Add loading skeleton + error state to Inventory page | Next.js |
| 7 | Test full flow end-to-end with a real Fortnox sandbox account | QA |

**Definition of done:** A test account can sign up, connect Fortnox, and see real product stock levels within 10 minutes.

---

## Week 2 (Days 8–14): Make It Useful

**Goal:** the core daily workflow is complete.

| Day | Task | Stack |
|-----|------|-------|
| 8 | Add low-stock threshold setting per product | Supabase + FastAPI |
| 9 | Low-stock alert email (send via Resend or SendGrid) | FastAPI |
| 10 | Manual stock adjustment form (+ / − with reason) | Next.js + FastAPI |
| 11 | Stock movement history log per product | Supabase + Next.js |
| 12 | Scheduled sync every 15 min (APScheduler in FastAPI) | FastAPI |
| 13 | Analytics page: stock movement chart (last 30 days) | Next.js + Chart.js |
| 14 | Add Sentry error monitoring (frontend + backend) | Sentry free tier |

**Definition of done:** User comes back daily to check alerts and adjustments without you prompting them.

---

## Week 3 (Days 15–21): Make It Sellable

**Goal:** first paying customer can sign up, pay, and use the product.

| Day | Task | Stack |
|-----|------|-------|
| 15 | Create Stripe account + products + prices | Stripe |
| 16 | `POST /api/billing/checkout` endpoint | FastAPI + Stripe |
| 17 | `/pricing` page with Starter + Growth plans | Next.js |
| 18 | Stripe webhook handler (activated, cancelled, failed payment) | FastAPI |
| 19 | Trial banner in dashboard + paywall for expired trials | Next.js |
| 20 | `/settings/billing` page — current plan + manage button | Next.js + Stripe Portal |
| 21 | Enable Stripe Tax + Smart Retries + dunning emails | Stripe Dashboard |

**Definition of done:** You can pay for your own product with a real card and receive an invoice.

---

## Week 4 (Days 22–30): Make It Grow

**Goal:** 3 external users actively using it; one paying.

| Day | Task | Stack |
|-----|------|-------|
| 22 | Add Crisp or Tawk.to support chat widget | Next.js |
| 23 | Write onboarding email sequence (Day 1, Day 3, Day 7) | Resend / MailerLite |
| 24 | Weekly digest email (stock summary) | FastAPI scheduled job |
| 25 | Password reset flow | Supabase + Next.js |
| 26 | Add `/health` endpoint + basic uptime monitor (UptimeRobot free) | FastAPI |
| 27 | Production Docker build tested (multi-stage Dockerfile) | Docker |
| 28 | Deploy to staging on ESXi | ESXi + Docker |
| 29 | Invite 3 pilot users, collect feedback | Sales |
| 30 | Review feedback, update backlog, plan Month 2 | Product |

**Definition of done:** 3 real users have logged in this week without you helping them.

---

## Month 2 Preview (based on feedback)

Add only what users ask for most:

- Multi-warehouse support
- Purchase order creation
- Supplier contact management
- Slack/Teams low-stock notifications
- Mobile-responsive design
