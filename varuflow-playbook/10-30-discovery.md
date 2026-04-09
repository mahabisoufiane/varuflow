# Stage 10–30: Discovery & Feature List

The goal of this stage is to talk to real potential users, confirm the pain is real, and turn it into a tiny feature list with one core workflow and no extras.

---

## Customer Interview Guide

Run 5–10 interviews before locking the feature list. Keep each under 30 minutes.

### Questions to ask

1. Walk me through how you manage inventory today, step by step.
2. What is the most painful part of that process?
3. How long does it take you per week? What would you do with that time back?
4. Have you tried any tool to solve this? What happened?
5. If you could wave a wand and fix one thing, what would it be?
6. What would make you switch tools immediately vs. "maybe someday"?
7. How much do you spend today on solving this (tools, time, people)?

### What to listen for

- Repeated words: "manual", "spreadsheet", "forgot", "mismatch", "Fortnox doesn't..."
- Dollar amounts — if they mention money, they feel real pain
- Workarounds — duct-tape solutions signal validated pain
- "We hired someone just to do this" — strongest signal

---

## Interview Findings Log

| # | Company | Role | Top Pain | Would Pay | Notes |
|---|---------|------|----------|-----------|-------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

---

## MVP Feature List

Only features that help the user reach the core outcome in the first session.

### Core Workflow (must-have)

- [x] Auth — magic link + password login (Supabase)
- [x] Onboarding — connect Fortnox account in < 5 minutes
- [x] Inventory dashboard — list of products with current stock levels
- [ ] Stock sync — pull product/invoice data from Fortnox automatically
- [ ] Low-stock alerts — email or in-app notification when item drops below threshold
- [ ] Manual stock adjustment — log a delivery or correction

### Supporting (needed before first paid customer)

- [x] Settings page — manage Fortnox connection, notification preferences
- [x] Analytics page — basic stock movement over time
- [ ] Support channel — email or in-app chat (Crisp / Intercom free tier)

### Backlog (do NOT build yet)

- Purchase order generation
- Supplier management
- Multi-warehouse support
- AI reorder suggestions
- Mobile app

---

## The One Core Metric

**Weekly Active Inventory Reviews** — the number of times a user opens the dashboard and checks or updates stock.

If this number grows, the product is creating value. If it is flat or zero, something in the workflow is broken.
