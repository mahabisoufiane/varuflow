# Stage 60–80: Monetization

Add the money layer once real users are using the product. Premature monetization before validated usage leads to churn. Delayed monetization leaves money on the table.

---

## Pricing Strategy

Start simple. One main plan. One upgrade tier. No free tier (use a trial instead).

### Recommended Initial Pricing

| Plan | Price | Includes | Target |
|------|-------|----------|--------|
| Starter | 299 SEK/mo (~25 EUR) | 1 Fortnox connection, up to 500 products, email alerts | Solo operators, very small businesses |
| Growth | 699 SEK/mo (~60 EUR) | 3 Fortnox connections, unlimited products, priority support | Small teams, 2–10 employees |

**Rule:** price based on the value created (hours saved per week × hourly rate), not on your costs. If reconciling inventory takes 5 hours/week at 300 SEK/hr, that is 1500 SEK/week of pain. 299 SEK/month is a no-brainer.

### Trial

- 14-day free trial, no credit card required at signup
- Send a "trial ending in 3 days" email on day 11
- Trial ends → hard paywall, data preserved for 30 days

---

## Stripe Integration Checklist

### Setup

- [ ] Create Stripe account (use Sweden entity, varuflow.se)
- [ ] Enable Stripe Tax for automatic VAT calculation
- [ ] Create products and price objects in Stripe dashboard
- [ ] Install Stripe Python SDK: `pip install stripe`
- [ ] Install Stripe JS: `npm install @stripe/stripe-js`

### Backend (FastAPI)

- [ ] `POST /api/billing/checkout` — create Stripe Checkout Session
- [ ] `POST /api/billing/portal` — create Customer Portal session
- [ ] `POST /api/webhooks/stripe` — handle Stripe events
- [ ] Webhook events to handle:
  - `checkout.session.completed` → activate subscription
  - `customer.subscription.updated` → update plan in DB
  - `customer.subscription.deleted` → downgrade to locked state
  - `invoice.payment_failed` → send failed payment email
  - `invoice.payment_succeeded` → send receipt

### Frontend (Next.js)

- [ ] `/pricing` page with plan cards and CTA buttons
- [ ] Checkout redirect on plan select
- [ ] `/settings/billing` page — shows current plan, next invoice, manage button
- [ ] Trial banner in dashboard header showing days remaining
- [ ] Paywall component for locked-out trial-expired users

### Database (Supabase)

```sql
-- Add to users/organizations table
ALTER TABLE organizations ADD COLUMN stripe_customer_id TEXT;
ALTER TABLE organizations ADD COLUMN stripe_subscription_id TEXT;
ALTER TABLE organizations ADD COLUMN plan TEXT DEFAULT 'trial';
ALTER TABLE organizations ADD COLUMN trial_ends_at TIMESTAMPTZ;
ALTER TABLE organizations ADD COLUMN subscription_status TEXT DEFAULT 'trialing';
```

---

## Invoice & Tax

- [ ] Enable Stripe Tax (automatic VAT/sales tax) — no manual setup needed
- Swedish customers: 25% moms (VAT) applied automatically via Stripe Tax
- Stripe generates PDF invoices automatically — link to them from `/settings/billing`

---

## Revenue Tracking

Track these from day one:

| Metric | How to measure |
|--------|---------------|
| MRR (Monthly Recurring Revenue) | Stripe Dashboard → Revenue |
| Trial-to-paid conversion | (paying customers / trial signups) × 100 |
| Churn rate | Cancelled this month / active last month |
| ARPU | MRR / active paying customers |
| Failed payment recovery rate | Recovered / total failed |
