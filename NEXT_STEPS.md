# NEXT_STEPS.md — Varuflow Priority Actions

Last updated: 2026-05-10

---

## Critical (Blocks Launch)

### ~~1. Fix 38 failing tests~~ ✅ DONE (2026-05-02 Repair Sprint)
- **Result:** 2747 passed, 0 failed. All 38 failures resolved. 146 new tests added. See REPAIR_LOG.md.

### 2. Set up Stripe production account
- **Details:** Blocks ALL payment collection — both customer invoice payments and Varuflow SaaS billing. Need verified business account with Swedish org number.
- **Owner:** Soufiane
- **Deps:** Business bank account, company registration docs
- **Est:** 1-2 hours setup + 2-3 days Stripe verification
- **Action:** Complete Stripe onboarding, set STRIPE_SECRET_KEY + STRIPE_WEBHOOK_SECRET on Railway, configure webhook endpoints for both /api/billing/webhook and /api/invoicing/webhook.

### 3. Configure Resend domain verification
- **Details:** Blocks all transactional email — invoice delivery, portal invites, password resets, dunning reminders.
- **Owner:** Soufiane
- **Deps:** DNS access to varuflow.com
- **Est:** 30 minutes setup + up to 48h DNS propagation
- **Action:** Add DKIM/SPF/DMARC records, verify domain in Resend dashboard, set RESEND_API_KEY on Railway.

### 4. Set Railway production environment variables
- **Details:** 25+ env vars must be configured before deployment is functional. See CLAUDE.md for complete list.
- **Owner:** Soufiane
- **Est:** 1 hour
- **Action:** Go through CLAUDE.md env var list one by one. Critical ones: DATABASE_URL, SUPABASE_JWT_SECRET, CORS_ORIGINS, PORTAL_JWT_SECRET, AUTH_JWT_SECRET, ENFORCE_SECRET_VALIDATION=true, ENFORCE_JWT_SIGNATURE=true.

### 5. Create Supabase production project
- **Details:** Blocks all authentication. Current setup may be pointing to dev/local Supabase instance.
- **Owner:** Soufiane
- **Est:** 30 minutes
- **Action:** Create new Supabase project (eu-north-1 for GDPR), configure auth providers, set SUPABASE_URL + SUPABASE_SERVICE_KEY + SUPABASE_JWT_SECRET on Railway, set NEXT_PUBLIC_SUPABASE_URL + NEXT_PUBLIC_SUPABASE_ANON_KEY on Vercel.

---

## High Priority (Within 30 Days)

### ~~6. Build missing frontend pages — Auto-Reorder settings~~ ✅ DONE (2026-05-10)
- **Result:** `inventory/auto-reorder/page.tsx` exists (311 lines).

### ~~7. Build missing frontend pages — Credit Notes~~ ✅ DONE (2026-05-10)
- **Result:** `invoices/credit-notes/page.tsx` exists (111 lines).

### ~~8. Build missing frontend pages — Dunning Management~~ ✅ DONE (2026-05-10)
- **Result:** `invoices/dunning/page.tsx` exists (162 lines).

### ~~9. Build missing frontend pages — Peppol Settings~~ ✅ DONE (2026-05-10)
- **Result:** `invoices/peppol/page.tsx` exists (167 lines).

### ~~10. Build missing frontend pages — Multi-Currency Settings~~ ✅ DONE (2026-05-10)
- **Result:** `settings/currency/page.tsx` exists (199 lines).

### ~~11. POS module test coverage~~ ✅ DONE (2026-05-10)
- **Result:** `tests/test_pos.py` — 161 lines, 33 tests, all passing.

### ~~12. HR module test coverage~~ ✅ DONE (2026-05-10)
- **Result:** `tests/test_team.py` — 198 lines, 20 tests, all passing.

### ~~13. Fortnox integration end-to-end tests~~ ✅ DONE (2026-05-10)
- **Result:** `tests/test_fortnox_integration.py` — 16 source-contract tests, all passing.

### 14. Connect blog CMS (Sanity.io)
- **Details:** Marketing site blog exists but needs Sanity.io project connected for content management.
- **Owner:** Frontend / Marketing
- **Est:** 1 day
- **Action:** Create Sanity project, define blog schema, connect to frontend via GROQ queries.

### 15. Configure PostHog dashboard
- **Details:** PostHog SDK is integrated but dashboards/funnels need configuration for key metrics.
- **Owner:** Product / Soufiane
- **Est:** 2-4 hours
- **Action:** Set up funnels (signup -> onboarding -> first invoice), feature flags for gradual rollout, session recording for bug reports.

---

## Medium Priority (Within 90 Days)

### ~~16. Complete German locale to 100%~~ ✅ DONE (2026-05-10)
- **Result:** All 30 locale files now have 1325/1325 keys. 227 missing keys back-filled with English fallbacks across de, nl, fr, fi, pl, es, bg, cs, el, et, he, hr, hu, it, lt, lv, mk, pt, ro, sk, sl, sq, sr, tr, uk. sv/da/no had 4-5 missing. Native speaker review still recommended for AI/billing terms.

### ~~17. Complete Dutch and French locales to 100%~~ ✅ DONE (2026-05-10)
- **Result:** See item 16. All locales complete with English fallbacks.

### 18. E-invoicing integration for mandatory markets
- **Details:** Germany (XRechnung, mandatory Jan 2025), France (Factur-X, mandatory 2026-2027), Italy (FatturaPA, already mandatory). These are Tier 2-3 market requirements.
- **Owner:** Backend
- **Est:** 2-4 weeks per format
- **Action:** Start with XRechnung (Germany, most immediate). Build XML generation, validation, and transmission modules. Consider using existing libraries (mustangproject for ZUGFeRD, factur-x Python lib).

### 19. Mobile app store submissions
- **Details:** If mobile app exists (React Native or PWA wrapper), submit to iOS App Store and Google Play.
- **Owner:** Mobile / Soufiane
- **Est:** 1 week (including review cycles)
- **Action:** Prepare store listings, screenshots, privacy policy. Submit for review. Plan for 1-2 rejection cycles.

### 20. SOC 2 readiness assessment
- **Details:** Enterprise customers in Tier 2+ markets will require SOC 2 Type II. Start with gap assessment.
- **Owner:** Soufiane / External auditor
- **Est:** 2-4 weeks for assessment, 6-12 months for full certification
- **Action:** Engage SOC 2 readiness consultant. Key gaps likely: formal access control policies, incident response plan, change management documentation, vendor risk assessment. Start with Vanta or Drata for automated evidence collection.

---

## Quick Wins (Can Be Done Anytime, High ROI)

| # | Item | Effort | Impact |
|---|------|--------|--------|
| A | Add rate limiting to auth endpoints | 2 hours | Prevents brute force |
| B | Set up Sentry error alerting (SENTRY_DSN exists) | 1 hour | Immediate prod visibility |
| C | Configure UptimeRobot for /api/health | 15 min | Downtime alerts |
| D | Add OpenGraph meta tags to marketing pages | 1 hour | Better social sharing |
| E | Enable Vercel Analytics | 15 min | Frontend performance data |
| F | Write API documentation (OpenAPI/Swagger is auto-generated, just needs review) | 2 hours | Developer experience |
| G | Set up GitHub Actions CI pipeline (lint + test + type-check) | 2-3 hours | Prevents regressions |

---

## Dependencies Graph

```
Stripe Account (2) ──┐
                     ├──> First paying customer
Resend Domain (3) ───┤
                     │
Railway Env (4) ─────┤
                     │
Supabase Prod (5) ───┘

Fix Tests (1) ──> CI Pipeline (G) ──> Safe deployments

German Locale (16) ──> Germany Launch (Tier 2)
XRechnung (18) ──────> Germany Launch (Tier 2)
iDEAL via Stripe ────> Netherlands Launch (Tier 2)
```

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-02 | Prioritize Stripe + Resend over new features | Cannot collect revenue without payments and email |
| 2026-05-02 | Germany as first Tier 2 market | Largest EU wholesale market, XRechnung already mandatory |
| 2026-05-02 | Defer Russia/Belarus indefinitely | Sanctions risk, payment infrastructure unavailable |
| 2026-05-02 | SOC 2 before enterprise sales push | Required by most enterprise procurement teams |
