# E2E Test Coverage Report

Generated: 2026-05-02

## Summary

| Category | Count |
|---|---|
| Spec files | 15 |
| Total tests | 103 |
| Browsers tested | 4 (Chrome, Firefox, Mobile, Tablet) |
| Pages covered | 40+ |
| Critical flows covered | 25 |

---

## Pages Tested

### Authenticated App Pages
| Page | Spec | Tests |
|---|---|---|
| `/dashboard` | dashboard.spec.ts | 7 |
| `/invoices` | invoicing.spec.ts | 3 |
| `/invoices/new` | invoicing.spec.ts, smoke.spec.ts | 3 |
| `/invoices/[id]` | invoicing.spec.ts | 2 |
| `/recurring` | invoicing.spec.ts | 1 |
| `/inventory` | inventory.spec.ts | 2 |
| `/inventory/products` | inventory.spec.ts | 3 |
| `/inventory/products/new` | inventory.spec.ts | 1 |
| `/inventory/products/[id]` | inventory.spec.ts | 1 |
| `/customers` | customers.spec.ts | 3 |
| `/customers/new` | customers.spec.ts | 1 |
| `/customers/[id]` | customers.spec.ts | 1 |
| `/pos` | pos.spec.ts, smoke.spec.ts | 7 |
| `/bookings` | bookings.spec.ts | 5 |
| `/expenses` | expenses.spec.ts | 4 |
| `/analytics` | analytics.spec.ts | 7 |
| `/accounting` | analytics.spec.ts | 1 |
| `/settings` | settings.spec.ts | 8 |
| `/settings/auto-reorder` | inventory.spec.ts | 1 |
| `/hr` or `/scheduling` | hr.spec.ts | 5 |

### Auth Pages
| Page | Spec | Tests |
|---|---|---|
| `/auth/login` | auth.spec.ts, smoke.spec.ts | 5 |
| `/auth/signup` | auth.spec.ts | 1 |
| `/auth/forgot-password` | auth.spec.ts | 1 |

### Marketing Pages
| Page | Spec | Tests |
|---|---|---|
| `/` (homepage) | marketing.spec.ts | 2 |
| `/pricing` | marketing.spec.ts | 1 |
| `/trial` or `/auth/signup` | marketing.spec.ts | 1 |
| `/vs/fortnox`, `/vs/odoo`, `/vs/visma` | marketing.spec.ts | 1 |
| `/verticals/salons`, `/retail`, `/b2b` | marketing.spec.ts | 1 |
| `/compliance` | marketing.spec.ts | 1 |
| `/demo` or `/contact` | marketing.spec.ts | 1 |
| `/blog` | marketing.spec.ts | 1 |
| `/regions/se`, `/no`, `/dk` | marketing.spec.ts | 1 |

---

## Critical User Flows Covered

1. **Auth login** — email/password → dashboard redirect
2. **Auth logout** — session cleared, redirect to login
3. **Auth error handling** — wrong password shows error
4. **Auth rate limiting** — repeated failures trigger lockout message
5. **Create invoice** — customer → line items → submit → draft state
6. **Invoice status display** — draft/sent/paid shown correctly
7. **Create product** — name, SKU, price → saved
8. **Stock adjustment** — dialog opens from product detail
9. **Create customer** — company name + email → saved
10. **Customer search** — filter by name
11. **POS session** — open, add product, view cart, close with Z-report
12. **POS search** — product search within POS
13. **Create booking** — modal opens, service selection available
14. **Log expense** — amount + description → saved
15. **Expense approval** — pending tab visible to admin
16. **Settings general** — editable fields render
17. **Invite team member** — dialog opens
18. **Billing settings** — plan info visible
19. **Analytics overview** — chart renders, date filter present
20. **Dashboard KPIs** — kpi-strip and metric cards render
21. **Dashboard navigation** — nav links go to correct routes
22. **Mobile layout** — content renders at 375px
23. **Upsell modals** — upgrade CTA shown for locked features
24. **Accessibility** — labels, keyboard nav, alt text, focus styles
25. **Smoke: all critical pages load** — no 404 or error pages

---

## Buttons & Interactive Elements Verified

Approximate counts:
- **Form submit buttons**: 12
- **Cancel / back buttons**: 6
- **Filter / search controls**: 8
- **Dropdown / select menus**: 7
- **Modal-opening buttons**: 8
- **Navigation links**: 15
- **Export / download buttons**: 6
- **Action buttons (Add, Edit, Delete)**: 10

**Total interactive elements tested**: ~72

---

## `data-testid` Coverage Added

New `data-testid` attributes added in this work:

### Login Page (`auth/login/page.tsx`)
- `data-testid="email-input"` — email field
- `data-testid="password-input"` — password field
- `data-testid="login-button"` — submit button
- `data-testid="google-login-button"` — Google OAuth button
- `data-testid="auth-error-banner"` — error display

### Invoice Create Page (`invoices/new/page.tsx`)
- `data-testid="customer-select"` — customer dropdown
- `data-testid="add-line-item"` — add line button
- `data-testid="save-draft"` — submit/create button
- `data-testid="cancel-invoice"` — cancel button

### Pre-existing (from prior development)
- `data-testid="kpi-strip"`, `"metric-card"` — dashboard
- `data-testid="pos-layout"`, `"pos-search"`, `"pos-cart-panel"`, etc. — full POS system
- `data-testid="recent-activity"` — dashboard widget
- `data-testid="ai-carousel"` — AI card carousel
- `data-testid="auto-reorder-*"` — settings page
- `data-testid="mobile-bottom-nav"` — mobile navigation

---

## Accessibility Checks

| Check | Spec | Status |
|---|---|---|
| All form inputs have label/aria-label | accessibility.spec.ts | ✓ |
| All buttons have accessible text | accessibility.spec.ts | ✓ (≤2 icon-only allowed) |
| Keyboard navigation moves focus | accessibility.spec.ts | ✓ |
| Error messages appear on empty submit | accessibility.spec.ts | ✓ |
| Focus indicator visible on inputs | accessibility.spec.ts | ✓ |
| Images have alt attributes | accessibility.spec.ts | ✓ |

---

## CI/CD Integration

| Trigger | Job | Browsers | Timeout |
|---|---|---|---|
| Every push / PR | Smoke Tests | Chromium | 15 min |
| PR only | Auth Spec | Chromium | 10 min |
| Merge to main | Full E2E | Chromium + Firefox | 45 min |
| Daily 06:00 UTC | Full E2E | Chromium + Firefox | 45 min |

---

## How to Run Everything

```bash
cd frontend

# Install browsers (one-time)
npx playwright install chromium firefox webkit

# Full suite
npm run test:e2e

# Smoke only (fastest, run before deploy)
npm run test:smoke

# With visible browser
npm run test:e2e:headed

# Open report
npm run test:e2e:report
```
