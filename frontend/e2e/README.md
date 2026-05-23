# Varuflow E2E Test Suite

Playwright-based end-to-end tests covering every critical user flow in the Varuflow application.

## Quick Start

```bash
cd frontend

# Run all E2E tests (headless, default locale)
npm run test:e2e

# Run only smoke tests (fastest — use before every deploy)
npm run test:smoke

# Run with visible browser
npm run test:e2e:headed

# Open the interactive Playwright UI
npm run test:e2e:ui

# View the last HTML report
npm run test:e2e:report
```

## Prerequisites

1. Node.js 20+
2. Playwright browsers installed:
   ```bash
   npx playwright install chromium firefox webkit
   ```
3. A running frontend (`npm run dev` or `PLAYWRIGHT_BASE_URL` pointing to staging)
4. Test accounts seeded in Supabase (see **Test Accounts** below)

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PLAYWRIGHT_BASE_URL` | `http://localhost:3000` | Frontend URL |
| `PLAYWRIGHT_API_URL` | `https://varuflow-production.up.railway.app` | Backend URL for health-check smoke test |

For local dev, create `frontend/.env.test`:
```
PLAYWRIGHT_BASE_URL=http://localhost:3000
PLAYWRIGHT_API_URL=http://localhost:8000
```

## Test Accounts

The suite expects these accounts to exist in your Supabase instance:

| Role   | Email                            | Password      |
|--------|----------------------------------|---------------|
| Owner  | test-owner@varuflow-e2e.com      | E2ETest2026!  |
| Admin  | test-admin@varuflow-e2e.com      | E2ETest2026!  |
| Member | test-member@varuflow-e2e.com     | E2ETest2026!  |

Create them once in Supabase Auth dashboard (or via the seed script):
```bash
node --loader ts-node/esm e2e/fixtures/seed.ts
```

## Running Specific Suites

```bash
# Auth flows only
npm run test:auth

# Invoicing flows only
npm run test:invoicing

# Marketing pages only
npm run test:marketing:e2e

# Single spec file
npx playwright test e2e/pos.spec.ts

# Single test by name (grep)
npx playwright test --grep "complete POS sale"

# Debug a specific test (opens browser with Playwright inspector)
npx playwright test --debug e2e/invoicing.spec.ts

# Update snapshots
npx playwright test --update-snapshots
```

## Browsers

The suite runs on:
- **Chromium** (Chrome) — primary
- **Firefox** — secondary
- **iPhone 14** (mobile) — responsive tests
- **iPad Pro** (tablet) — tablet layout tests

CI runs Chromium + Firefox. Mobile/tablet run locally with `--project=mobile`.

## Test Structure

```
e2e/
├── fixtures/
│   ├── auth.ts          # Login helpers & authedPage fixture
│   └── seed.ts          # Test data seeding / cleanup
├── smoke.spec.ts         # ~7 tests  — critical path, run every deploy
├── auth.spec.ts          # ~8 tests  — login, logout, forgot-password
├── dashboard.spec.ts     # ~7 tests  — KPIs, nav, responsive
├── invoicing.spec.ts     # ~9 tests  — create, send, filter, PDF
├── inventory.spec.ts     # ~7 tests  — products, stock adjust, forecasting
├── customers.spec.ts     # ~6 tests  — CRUD, search, export
├── pos.spec.ts           # ~6 tests  — session, cart, Z-report
├── bookings.spec.ts      # ~5 tests  — calendar, create booking
├── expenses.spec.ts      # ~5 tests  — log, approve, report
├── hr.spec.ts            # ~5 tests  — shifts, leave, payroll
├── settings.spec.ts      # ~8 tests  — org, team, billing, API keys
├── marketing.spec.ts     # ~10 tests — homepage, pricing, trial, SEO
├── upsells.spec.ts       # ~5 tests  — plan limits, upgrade modals
├── analytics.spec.ts     # ~7 tests  — charts, exports, AI forecasts
└── accessibility.spec.ts # ~6 tests  — labels, keyboard nav, alt text
```

## CI/CD

- **Every push/PR** → `smoke.spec.ts` runs automatically via `.github/workflows/e2e.yml`
- **Merges to main** → Full suite runs (Chromium + Firefox)
- **Daily at 06:00 UTC** → Full regression against staging

Failed test artifacts (screenshots, traces, videos) are uploaded to GitHub Actions artifacts for 14 days.

## Adding New Tests

1. Create `e2e/yourfeature.spec.ts`
2. Import the authenticated fixture:
   ```typescript
   import { test, expect } from './fixtures/auth';
   ```
3. Use `authedPage` for auth-required tests:
   ```typescript
   test('does something', async ({ authedPage: page }) => {
     await page.goto('/yourfeature');
     // ...
   });
   ```
4. Add `data-testid` attributes to any new interactive elements you're testing

## Troubleshooting

| Problem | Fix |
|---|---|
| `ERR_CONNECTION_REFUSED` | Start `npm run dev` or set `PLAYWRIGHT_BASE_URL` |
| `auth/login` redirect loop | Check Supabase `NEXT_PUBLIC_SUPABASE_*` env vars |
| Slow tests | Use `--project=chromium` to skip Firefox locally |
| Tests flaky in CI | Set `retries: 2` in `playwright.config.ts` (already default for CI) |
| `locator not found` | Add `data-testid` to the element or update the selector |
