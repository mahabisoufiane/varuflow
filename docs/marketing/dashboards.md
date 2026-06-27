# PostHog Dashboard Definitions

> Create these dashboards in PostHog UI under **Dashboards → New Dashboard**.
> Each section lists the insight types and queries to add as dashboard tiles.

---

## 1. Acquisition Dashboard

**Purpose:** Track how many new users are signing up, their sources, and early conversion rates.

### Tiles

#### Signups over time
- **Type:** Trend
- **Events:** `signup_completed`
- **Breakdown:** none
- **Period:** last 30 days, daily

#### Signups by UTM source
- **Type:** Trend
- **Events:** `signup_completed`
- **Breakdown:** `utm_source` property
- **Period:** last 30 days

#### Trials started
- **Type:** Trend
- **Events:** `trial_started`
- **Period:** last 30 days

#### Signup → Trial conversion rate
- **Type:** Funnel (2-step)
- **Steps:** `signup_completed` → `trial_started`
- **Period:** last 30 days

#### Landing page views by page
- **Type:** Table
- **Events:** `landing_page_viewed`
- **Breakdown:** `page_name`
- **Period:** last 7 days

#### Competitor comparison views
- **Type:** Bar chart
- **Events:** `comparison_page_viewed`
- **Breakdown:** `competitor`
- **Period:** last 30 days

---

## 2. Activation Dashboard

**Purpose:** Measure how quickly new users reach their first meaningful action (time to value).

### Tiles

#### Time to first invoice (median)
- **Type:** User Path or custom HogQL query
- **Query:** Median time between `signup_completed` and `first_invoice_created` per user
- **Period:** last 30 days

#### Onboarding completion rate
- **Type:** Funnel
- **Steps:** Full 6-step funnel from `funnels.md` § Onboarding Funnel
- **Display:** Conversion % at each step
- **Period:** last 30 days

#### First invoice by day of week
- **Type:** Trend
- **Events:** `first_invoice_created`
- **Breakdown:** day of week
- **Period:** last 90 days

#### First POS sale over time
- **Type:** Trend
- **Events:** `first_pos_sale`
- **Period:** last 30 days

#### Onboarding step drop-off
- **Type:** Bar chart
- **Events:** `onboarding_step_completed`
- **Breakdown:** `step` property
- **Period:** last 30 days
- **Note:** Shows which step has lowest completion — high-priority fix target

---

## 3. Revenue Dashboard

**Purpose:** Track MRR movements, churn signals, and expansion.

### Tiles

#### New subscriptions over time
- **Type:** Trend
- **Events:** `subscription_started`
- **Breakdown:** `tier`
- **Period:** last 90 days

#### Upgrades vs downgrades vs cancellations
- **Type:** Trend (multiple series)
  - Series A: `subscription_upgraded`
  - Series B: `subscription_downgraded`
  - Series C: `subscription_canceled`
- **Period:** last 90 days

#### Trial to paid conversion
- **Type:** Funnel
- **Steps:** `trial_started` → `subscription_started`
- **Period:** last 30 days

#### Subscription tier breakdown
- **Type:** Pie chart
- **Events:** `subscription_started` (unique users)
- **Breakdown:** `tier`
- **Period:** all time

#### Upsell funnel
- **Type:** Funnel
- **Steps:** `upsell_shown` → `upsell_clicked` → `upsell_converted`
- **Period:** last 30 days

#### Upsell dismiss rate by resource
- **Type:** Bar chart
- **Events:** `upsell_dismissed`
- **Breakdown:** `placement`
- **Period:** last 30 days

---

## 4. Product Usage Dashboard

**Purpose:** Understand which features drive engagement and retention.

### Tiles

#### Top 30 features used
- **Type:** Table
- **Events:** `feature_used`
- **Breakdown:** `feature`
- **Period:** last 30 days
- **Sort:** by event count descending

#### Feature usage over time (top 10)
- **Type:** Trend
- **Events:** `feature_used`
- **Breakdown:** `feature` (top 10 values)
- **Period:** last 30 days

#### AI query volume
- **Type:** Trend
- **Events:** `ai_query_made`
- **Period:** last 30 days

#### Mobile vs web usage
- **Type:** Pie chart
- **Events:** any event
- **Breakdown:** `$lib` property (`posthog-js` = web, `posthog-react-native` = mobile)
- **Period:** last 30 days

#### Daily active users
- **Type:** Trend (unique users)
- **Events:** any (`$pageview` or `app_opened`)
- **Period:** last 30 days

#### Plan limit warnings hit
- **Type:** Trend
- **Events:** `limit_warning_shown`
- **Breakdown:** `resource`
- **Period:** last 30 days
- **Note:** Spikes here should trigger email to affected orgs

#### Plan limit blocks hit
- **Type:** Trend
- **Events:** `limit_blocked_shown`
- **Breakdown:** `plan`
- **Period:** last 30 days
- **Note:** Plan = "FREE" blocks are upgrade opportunities

---

## Setup Notes

### PostHog project settings

1. **Data residency:** Use EU Cloud (`eu.i.posthog.com`) for GDPR compliance.
2. **Autocapture:** Enabled. Input field values are scrubbed in `PostHogInit.tsx` — only element metadata is captured.
3. **Session recording:** Enable for logged-in users only. Add property filter `is_authenticated = true`.
4. **Feature flags:** Use PostHog feature flags for A/B tests on onboarding steps and pricing page copy.
5. **Cohorts:** Create cohorts for:
   - "Trial users" — users with `trial_started` in last 14 days
   - "Blocked by limit" — users with `limit_blocked_shown` in last 7 days
   - "Churned" — users with `subscription_canceled` in last 30 days

### Alerts to configure

| Alert | Condition | Channel |
|-------|-----------|---------|
| Signup spike | `signup_completed` > 2× weekly average | Slack #growth |
| Churn spike | `subscription_canceled` > 3 in 24h | Slack #revenue |
| Limit block spike | `limit_blocked_shown` > 20 in 24h | Slack #product |
| Onboarding drop | Funnel completion < 30% | Email to PMs |
