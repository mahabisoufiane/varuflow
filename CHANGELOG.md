# Changelog

All notable changes to Varuflow are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### In Progress
- Swedish Bankgiro/Plusgiro fields on Organization model
- OCR number generation per BGC Luhn specification
- Norwegian and Danish translation completions (no.json, da.json)
- Swish Merchant API integration (full QR + callbacks)
- Fortnox bidirectional sync (customer and product pull)
- Localised transactional emails (sv/no/da)
- Portal payment actions (Stripe payment link inside portal)

---

## [1.4.0] — 2026-04-29

### Added
- Production startup validator (`validate_production_config`) — crashes on placeholder secrets, empty `PII_ENCRYPTION_KEY`, wildcard CORS, missing Fortnox redirect URI
- `PII_ENCRYPTION_KEY` enforcement added to startup validation
- `FORTNOX_REDIRECT_URI` enforcement when Fortnox credentials are configured
- Sentry DSN warning on startup when `SENTRY_DSN` is unset
- `ENFORCE_SECRET_VALIDATION` and `ENFORCE_JWT_SIGNATURE` defaults hardened to `True` in production config
- Dev bypass now requires BOTH `ENV=development` AND `ALLOW_DEV_BYPASS=true` (defense-in-depth)
- Admin key rotation support via `ADMIN_API_KEY_PREVIOUS` (zero-downtime rotation)
- `CLAUDE.md` updated with correct Railway env var names

### Fixed
- **Critical:** `get_current_user()` had stray `request: Request,` inside return dict literal causing `NameError` on every authenticated production request
- CORS format in `docker-compose.yml` changed from JSON array to comma-separated string (was breaking all API calls in local dev)
- Hardcoded `localhost:8000` fallback removed from all frontend API clients (`api-client.ts`, `api.ts`, `portal-client.ts`, `supplier-portal-client.ts`)
- Next.js 16 `middleware.ts` vs `proxy.ts` conflict resolved — removed conflicting `middleware.ts`, `proxy.ts` is the correct Next.js 16 convention
- `docker-compose.yml` backend environment: added `ALLOW_DEV_BYPASS=true`, `ENFORCE_JWT_SIGNATURE=false`, `ENFORCE_SECRET_VALIDATION=false` for local dev without Supabase

### Changed
- `CORS_ORIGINS` in `docker-compose.yml`: `http://localhost:3000,http://localhost:3002`
- `PORTAL_JWT_SECRET`, `AUTH_JWT_SECRET` added to `_DANGEROUS_SECRETS` sentinel check

---

## [1.3.0] — 2026-04

### Added
- Peppol BIS Billing 3.0 UBL 2.1 XML export (`/api/einvoice/peppol/{id}`)
- SFTI validator integration for Peppol XML
- Norwegian EHF 3.0 export (`/api/invoicing/invoices/{id}/ehf`)
- SIE4 accounting export (CP437 encoded, BAS 2024 chart-of-accounts)
- Fortnox OAuth2 integration (connect, callback, token refresh, disconnect, invoice push sync)
- BankID Relying Party v6.0 client (mTLS, animated QR, `init`/`collect` endpoints)
- `bolagsverket.py` — company lookup with Luhn validation and 6-hour cache
- Multi-currency service: SEK/NOK/DKK + 80 ISO codes, Scandinavian formatting, openexchangerates.org fetcher
- VAT engine: SE moms, NO MVA, DK moms, intra-EU reverse charge, export rules
- 4-stage dunning sweep (Day +3/+7/+14/+30 past due) with email + WhatsApp/SMS
- Subscription pause/resume logic
- `PII_ENCRYPTION_KEY` — Fernet encryption for customer email, phone, address, TOTP secrets
- `FORTNOX_ENCRYPTION_KEY` — Fernet encryption for Fortnox OAuth tokens at rest
- Rate limiting middleware with per-org and per-IP limits
- Read-only maintenance mode (`READONLY_MODE`)
- Nightly summary email digest to org owners
- Push notification service
- Webhook dispatcher (outbound webhooks for external integrations)

### Added (Frontend)
- Dashboard with KPI cards, sparklines, revenue chart, stock alerts, AI action cards
- Customer detail page (`/customers/[id]`)
- Invoice detail page (`/invoices/[id]`)
- Settings page: account, team, billing (Stripe), integrations (Fortnox), notifications
- Analytics: commissions, forecasting sub-pages
- Inventory sub-pages: purchase orders, warehouses, transfers, stock counts, audit, labels
- Campaigns, segments, loyalty sub-pages
- Bookings, documents, expenses, gift cards, reviews pages
- B2B customer portal: login, invoice list, invoice detail, catalogue, orders
- Supplier portal: PO view, OTP verify

---

## [1.2.0] — 2026-01

### Added
- Recurring invoices with auto-send scheduler
- POS (point-of-sale): sessions, receipts, Z-reports, Swish payment method enum
- AI engine: rules-based action cards (no OpenAI calls), AI chat with GPT-4o
- Customer segments and campaigns engine
- Loyalty points engine
- Expense tracking and reporting
- GDPR data export endpoint
- Developer API keys
- Stripe Customer Portal for self-serve plan management
- Stripe webhook idempotency (`StripeProcessedEvent` model)
- Plan enforcement middleware (`require_plan`) across PRO-gated features

---

## [1.1.0] — 2025-11

### Added
- Supabase Auth integration (production)
- Local standalone auth system (`local_auth.py`): signup, email verification, login, MFA/TOTP, password reset
- Onboarding flow
- B2B customer portal with magic-link and OTP authentication
- Supplier portal
- Analytics router: revenue, cash flow, top customers, top products
- PDF invoice generation (ReportLab)
- Invoice email send via Resend
- Stripe payment links on invoices
- `payment_terms_days` default 30 days (Nordic B2B standard)
- IP allowlist for org-level access control
- Audit trail (`AuditEvent` model)

---

## [1.0.0] — 2025-09

### Added
- Initial release
- Core invoicing: customers, invoices, CRUD, status transitions
- Inventory: products, stock management, purchase orders
- Team management: invite, roles (owner/admin/member)
- Organization model with `org_number`, `vat_number`, `base_currency` (defaults SEK)
- Alembic migrations (initial schema)
- Docker Compose full-stack local dev environment
- next-intl i18n: Swedish (sv) and English (en)
- Health check endpoint (`/api/health`)
- CORS middleware with explicit origin list
