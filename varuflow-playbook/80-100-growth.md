# Stage 80–100: Growth & Retention

After launch, focus less on new features and more on activation, retention, and failed-payment recovery. New features only get built when user behavior proves they increase usage or revenue.

---

## The Growth Loop

```
New user signs up
      ↓
Onboarding: connect Fortnox in < 5 min   ← optimize first
      ↓
First "aha moment": sees real stock data
      ↓
Weekly active use: checks dashboard 3×/week
      ↓
Refers a colleague or upgrades plan
      ↓
Becomes a long-term retained customer
```

Every growth effort should target one of these steps. If the loop breaks at onboarding, fix onboarding. If it breaks at the aha moment, fix the Fortnox sync speed.

---

## Activation Checklist

Activation = user reaches the "aha moment" within the first session.

- [ ] Measure time from signup to first stock view (target: under 10 minutes)
- [ ] Add progress indicator on onboarding (`Step 2 of 3: Connecting Fortnox...`)
- [ ] Pre-populate demo data if Fortnox connection takes > 30 seconds
- [ ] Send "Your inventory is ready" email the moment first sync completes
- [ ] In-app tooltip on first dashboard visit explaining each widget

---

## Retention Checklist

Retention = user comes back next week and the week after.

- [ ] Weekly digest email: "Your stock summary for the week"
  - Top 3 low-stock items
  - Units sold this week vs last week
  - One-click link back to dashboard
- [ ] Push low-stock alerts immediately via email (not just in-app)
- [ ] Monthly report email: usage summary with MOM comparison
- [ ] In-app changelog: show what's new when user logs in after an update

---

## Failed Payment Recovery

Stripe handles most of this automatically, but you must configure it:

- [ ] Enable Smart Retries in Stripe (retries failed charges at optimal times)
- [ ] Enable Dunning emails in Stripe Billing settings:
  - Day 1: "Your payment failed — update your card"
  - Day 7: "Last chance — your account will be paused in 3 days"
  - Day 10: Account locked, data preserved 30 days
- [ ] Add in-app banner when payment fails: red bar at top of dashboard
- [ ] Webhook `invoice.payment_failed` → set `subscription_status = 'past_due'` in DB

---

## Churn Analysis

When a user cancels, learn why.

- [ ] Add cancellation survey (1 question: "What was the main reason you cancelled?")
  - Options: Too expensive / Missing feature / Switching to competitor / No longer need it / Technical issues
- [ ] Log every cancellation with plan, months active, and survey answer
- [ ] Review churn reasons monthly and adjust roadmap accordingly

---

## Feature Building Rules (Post-Launch)

Only build the next feature when:

1. 3+ paying customers have requested it independently
2. It directly increases one of: activation rate, weekly active use, or trial-to-paid conversion
3. It does not increase support volume proportionally

> "Build less, polish more" — a product that does 3 things perfectly beats one that does 10 things adequately.

---

## Key Metrics Dashboard

Track these weekly. If any metric is red for 2 weeks in a row, drop everything and fix it.

| Metric | Target | Action if below target |
|--------|--------|----------------------|
| Trial activation rate | > 60% | Fix onboarding flow |
| Trial-to-paid conversion | > 25% | Improve aha moment speed |
| Monthly churn rate | < 5% | Improve retention emails |
| Weekly active users / total paid | > 70% | Fix engagement loop |
| Failed payment recovery | > 50% | Enable Stripe Smart Retries |
| Support tickets per user per month | < 0.5 | Fix UX or add documentation |
