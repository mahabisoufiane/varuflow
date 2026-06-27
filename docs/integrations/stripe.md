# Stripe Setup

Varuflow uses Stripe for two separate purposes. Keep them distinct — they use different endpoints and different webhook secrets.

---

## Two Separate Integrations

| Integration | Purpose | Backend router |
|-------------|---------|----------------|
| **SaaS billing** | Varuflow's own subscription plans (FREE vs PRO) | `routers/billing.py` |
| **Invoice payments** | Stripe payment links on customer invoices | `routers/invoicing.py` |

Both use the same `STRIPE_SECRET_KEY` but need separate webhook endpoints configured in the Stripe Dashboard.

---

## SaaS Billing (Subscriptions)

### Plan Structure

| Plan | Price | Features |
|------|-------|---------|
| FREE | 0 kr/mo | Core invoicing, inventory, customers |
| PRO | Set in Stripe | + Analytics, Peppol e-faktura, recurring invoices, AI chat, forecasting, developer API, webhooks |

Plan limits are enforced server-side in `backend/app/middleware/plan_check.py` — not just hidden in the UI.

### Setup

1. Create a product in Stripe: "Varuflow PRO"
2. Create a monthly price on it
3. Note the Price ID (`price_...`)
4. Set `STRIPE_PRO_PRICE_ID=price_...` on Railway

### Checkout Flow

```
1. Org owner clicks "Upgrade to PRO" in Settings → Billing
2. POST /api/billing/checkout
   └── Creates Stripe Checkout Session
   └── Returns { url }
3. Frontend redirects to Stripe-hosted checkout page
4. Customer enters card details, completes payment
5. Stripe calls POST /api/billing/webhook with customer.subscription.updated
6. Backend sets Organization.plan = "PRO"
7. Redirect returns user to /settings?billing=success
```

### Customer Portal

Org owners can manage their subscription (cancel, update card, view invoices) via:

```
POST /api/billing/portal → returns Stripe Customer Portal URL
```

### Webhook Events Handled

| Event | Action |
|-------|--------|
| `customer.subscription.updated` | Update `Organization.plan` based on subscription status |
| `customer.subscription.deleted` | Downgrade to FREE |
| `invoice.payment_succeeded` | Record payment, extend PRO access |
| `invoice.payment_failed` | Log, trigger grace period (access not cut immediately) |

---

## Invoice Payment Links

Customers can pay their invoices online via a Stripe-hosted payment page.

### How It Works

```
1. Invoice is SENT to customer
2. Org user clicks "Create Payment Link" on invoice detail page
3. POST /api/invoicing/invoices/:id/stripe-link
   └── Creates Stripe Payment Link with invoice amount
   └── Returns { url }
4. URL is emailed to customer or shared manually
5. Customer completes payment on Stripe-hosted page
6. Stripe calls POST /api/invoicing/stripe-webhook
7. Backend marks invoice as PAID
```

### Webhook Events Handled

| Event | Action |
|-------|--------|
| `checkout.session.completed` | Mark invoice as PAID if payment_status = paid |
| `payment_intent.succeeded` | Redundant confirmation |

---

## Configuration

### Environment Variables

```
STRIPE_SECRET_KEY=sk_live_...        # Never commit — set on Railway only
STRIPE_WEBHOOK_SECRET=whsec_...      # See below for how to get this
STRIPE_PRO_PRICE_ID=price_...        # PRO plan price ID
```

### Configuring Webhooks in Stripe Dashboard

You need **two separate webhook endpoints**:

1. **Billing webhook:**
   - URL: `https://varuflow-production.up.railway.app/api/billing/webhook`
   - Events: `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_succeeded`, `invoice.payment_failed`
   - Copy the Signing Secret → set as `STRIPE_WEBHOOK_SECRET` on Railway

2. **Invoice payment webhook:**
   - URL: `https://varuflow-production.up.railway.app/api/invoicing/stripe-webhook`
   - Events: `checkout.session.completed`, `payment_intent.succeeded`
   - Copy its Signing Secret → set as a second Railway variable (currently uses the same `STRIPE_WEBHOOK_SECRET` — if you need separate secrets, you'll need to add a new variable like `STRIPE_INVOICE_WEBHOOK_SECRET`)

> **Critical:** Both webhook endpoints verify the Stripe signature before processing any event. Never process webhook events without signature verification.

### Local Development (Stripe CLI)

To test webhooks locally:

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login
stripe login

# Forward webhooks to local backend
stripe listen --forward-to localhost:8000/api/billing/webhook
# Note the webhook signing secret printed — use it as STRIPE_WEBHOOK_SECRET in .env

# To test specific events
stripe trigger customer.subscription.updated
```

---

## Idempotency

The billing webhook uses the `StripeProcessedEvent` table to prevent duplicate processing. If Stripe delivers the same event twice (it does this for reliability), the second delivery is a no-op.

---

## Test Mode

Use `sk_test_...` keys and `whsec_test_...` webhook secrets for staging/development. Test card: `4242 4242 4242 4242` (any future expiry, any CVC).

Never use live keys in development.
