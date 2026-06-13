# PostHog Funnel Definitions

> Configure these funnels in PostHog UI under **Product Analytics → Funnels**.
> All event names are defined in `frontend/src/lib/analytics.ts` and `backend/app/services/analytics.py`.

---

## 1. Activation Funnel — Signup to Paid

**Goal:** Measure how many visitors that start a signup convert to paid subscribers.

### Steps

| Step | Event | PostHog Filter |
|------|-------|----------------|
| 1 | Visitor starts signup | `signup_started` |
| 2 | Signup completed (org created) | `signup_completed` |
| 3 | Trial started | `trial_started` |
| 4 | First invoice created | `first_invoice_created` |
| 5 | Subscription started | `subscription_started` |

### Configuration

- **Conversion window:** 30 days
- **Ordering:** ordered (must happen in sequence)
- **Breakdown:** by `plan` property on `subscription_started`

### Key question
What is the drop-off between `trial_started` and `first_invoice_created`?
This gap measures onboarding friction — reducing it is the highest-impact lever.

---

## 2. Upgrade Funnel — Warning to Conversion

**Goal:** Measure how many users who see a plan limit warning eventually upgrade.

### Steps

| Step | Event | PostHog Filter |
|------|-------|----------------|
| 1 | Limit warning banner shown | `limit_warning_shown` |
| 2 | Upgrade modal / upsell shown | `upsell_shown` |
| 3 | User clicks upgrade | `upsell_clicked` |
| 4 | Subscription upgraded | `subscription_upgraded` |

### Configuration

- **Conversion window:** 7 days
- **Breakdown:** by `resource` property on `limit_warning_shown` — shows which resource (products, invoices, users) drives the most upgrades
- **Compare:** `upsell_dismissed` count vs `upsell_converted` to see dismiss rate

### Key question
Which resource limit (products vs invoices vs users) has the highest conversion from warning → upgrade?

---

## 3. Onboarding Funnel — Signup to Completing All Steps

**Goal:** Measure completion of 6-step onboarding wizard.

### Steps

| Step | Event | PostHog Filter |
|------|-------|----------------|
| 1 | Signup completed | `signup_completed` |
| 2 | Onboarding: Org setup | `onboarding_step_completed` where `step = "org_setup"` |
| 3 | Onboarding: First product | `onboarding_step_completed` where `step = "first_product"` |
| 4 | Onboarding: First customer | `onboarding_step_completed` where `step = "first_customer"` |
| 5 | Onboarding: First invoice | `onboarding_step_completed` where `step = "first_invoice"` |
| 6 | Onboarding: Payment setup | `onboarding_step_completed` where `step = "payment_setup"` |
| 7 | Onboarding: Integrations | `onboarding_step_completed` where `step = "integrations"` |

### Configuration

- **Conversion window:** 14 days
- **Ordering:** unordered (steps can be done in any sequence)
- **Alert:** PostHog funnel alert when completion rate drops below 40%

---

## 4. Mobile Activation Funnel

**Goal:** Track mobile-specific activation separate from web.

### Steps

| Step | Event |
|------|-------|
| 1 | App opened | `app_opened` |
| 2 | Login completed | `signup_completed` (or identify succeeded) |
| 3 | First screen viewed | `screen_viewed` |
| 4 | First POS sale | `first_pos_sale` |

### Configuration

- **Filter:** add property `$lib = "posthog-react-native"` to all steps
- **Conversion window:** 3 days

---

## Instrumentation Reference

All events are fired via:

- **Backend:** `app.services.analytics` — called from routers after successful DB writes
- **Frontend (web):** `frontend/src/lib/analytics.ts` `Analytics.*` helpers
- **Mobile:** `mobile/lib/analytics.ts` `MobileAnalytics.*` helpers

### Calling conventions

```typescript
// Web — after successful signup
Analytics.signupCompleted({ plan: "FREE" });

// Web — after first invoice saved
Analytics.firstInvoiceCreated();

// Web — when limit banner renders
Analytics.limitWarningShown({ resource: "max_products", plan: "FREE", current: 410, limit: 500 });
```

```python
# Backend — after /api/auth/onboarding succeeds
await track_signup(user_id=str(user_id), org_name=org.name, plan=org.plan.value)

# Backend — after /api/trial/start succeeds
await track_trial_start(user_id=..., org_id=..., plan="PRO", source="direct")
```
