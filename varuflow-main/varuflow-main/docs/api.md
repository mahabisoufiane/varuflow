# API Reference

Base URL (production): `https://varuflow-production.up.railway.app`  
Base URL (local dev): `http://localhost:8000`  
Interactive docs: `<base>/docs` (Swagger UI) | `<base>/redoc`

---

## Authentication

All internal API endpoints require a Bearer JWT in the `Authorization` header:

```
Authorization: Bearer <supabase-jwt>
```

The JWT is issued by Supabase Auth and verified by the backend against `SUPABASE_JWT_SECRET`.

**Dev bypass:** In local dev (`ENV=development` + `ALLOW_DEV_BYPASS=true`), requests without an `Authorization` header are served as `DEV_USER` in `DEV_ORG`. Real auth is not required locally.

**Portal routes (`/api/portal/*`):** Use a separate short-lived JWT with `type: "portal"` claim, signed with `PORTAL_JWT_SECRET`. Portal tokens are rejected on internal routes.

**Admin routes:** Require `X-Admin-Key: <ADMIN_API_KEY>` header instead of a JWT.

---

## Modules

### Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/health` | None | Returns `{ status, db, version }` |

---

### Auth (Supabase-based)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/onboard` | JWT | Complete org onboarding after signup |
| GET | `/api/auth/me` | JWT | Current user + org info |
| PUT | `/api/auth/org` | JWT (owner) | Update organization details |

---

### Local Auth (standalone, non-Supabase)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/local-auth/signup` | None | Register with email + password |
| POST | `/api/local-auth/verify-email` | None | Verify email with token |
| POST | `/api/local-auth/login` | None | Login → returns access + refresh tokens |
| POST | `/api/local-auth/refresh` | None | Exchange refresh token |
| POST | `/api/local-auth/logout` | JWT | Invalidate session |
| POST | `/api/local-auth/forgot-password` | None | Send password reset email |
| POST | `/api/local-auth/reset-password` | None | Reset with token |
| GET | `/api/local-auth/mfa/setup` | JWT | Get TOTP QR code |
| POST | `/api/local-auth/mfa/verify` | JWT | Confirm TOTP setup |
| POST | `/api/local-auth/mfa/disable` | JWT | Disable MFA |
| POST | `/api/local-auth/bankid/init` | None | Start BankID auth |
| GET | `/api/local-auth/bankid/collect` | None | Poll BankID result |

---

### Invoicing

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/invoicing/customers` | JWT | List customers |
| POST | `/api/invoicing/customers` | JWT | Create customer |
| GET | `/api/invoicing/customers/:id` | JWT | Get customer |
| PUT | `/api/invoicing/customers/:id` | JWT | Update customer |
| DELETE | `/api/invoicing/customers/:id` | JWT | Soft-delete customer |
| GET | `/api/invoicing/invoices` | JWT | List invoices (filter by status, customer, date) |
| POST | `/api/invoicing/invoices` | JWT | Create invoice |
| GET | `/api/invoicing/invoices/:id` | JWT | Get invoice |
| PUT | `/api/invoicing/invoices/:id` | JWT | Update invoice |
| POST | `/api/invoicing/invoices/:id/send` | JWT | Send invoice by email |
| POST | `/api/invoicing/invoices/:id/mark-paid` | JWT | Record payment |
| GET | `/api/invoicing/invoices/:id/pdf` | JWT | Download PDF |
| GET | `/api/invoicing/invoices/:id/ehf` | JWT | Download Norwegian EHF 3.0 XML |
| POST | `/api/invoicing/invoices/:id/stripe-link` | JWT | Create Stripe payment link |
| GET | `/api/invoicing/aging-report` | JWT | Invoice aging by due date bucket |
| POST | `/api/invoicing/stripe-webhook` | Stripe sig | Handle invoice payment events |

---

### E-invoice / Peppol

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/einvoice/peppol/:id` | JWT (PRO) | Export Peppol BIS 3.0 UBL 2.1 XML |
| POST | `/api/einvoice/peppol/:id/validate` | JWT (PRO) | Validate via SFTI validator |

---

### Inventory

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/inventory/products` | JWT | List products |
| POST | `/api/inventory/products` | JWT | Create product |
| GET | `/api/inventory/products/:id` | JWT | Get product |
| PUT | `/api/inventory/products/:id` | JWT | Update product |
| DELETE | `/api/inventory/products/:id` | JWT | Soft-delete product |
| POST | `/api/inventory/products/import` | JWT | Bulk import from CSV |
| GET | `/api/inventory/warehouses` | JWT | List warehouses |
| POST | `/api/inventory/warehouses` | JWT | Create warehouse |
| GET | `/api/inventory/purchase-orders` | JWT | List purchase orders |
| POST | `/api/inventory/purchase-orders` | JWT | Create PO |
| GET | `/api/inventory/stock-counts` | JWT | List stock counts |
| POST | `/api/inventory/stock-counts` | JWT | Start stock count |
| GET | `/api/inventory/transfers` | JWT | List stock transfers |
| POST | `/api/inventory/transfers` | JWT | Create transfer |

---

### Analytics

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/analytics/revenue` | JWT | Revenue by period |
| GET | `/api/analytics/cash-flow` | JWT | Cash flow summary |
| GET | `/api/analytics/top-customers` | JWT | Top customers by revenue |
| GET | `/api/analytics/top-products` | JWT | Top products by volume |
| GET | `/api/analytics/forecasting` | JWT (PRO) | Sales forecast |
| GET | `/api/analytics/commissions` | JWT | Commission calculations |

---

### POS

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/pos/sessions` | JWT | Start POS session |
| GET | `/api/pos/sessions/:id` | JWT | Get session |
| POST | `/api/pos/sessions/:id/close` | JWT | Close session (Z-report) |
| POST | `/api/pos/receipts` | JWT | Create receipt |
| GET | `/api/pos/receipts/:id` | JWT | Get receipt / download PDF |
| GET | `/api/pos/z-reports` | JWT | List Z-reports |

---

### Recurring Invoices

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/recurring` | JWT (PRO) | List recurring schedules |
| POST | `/api/recurring` | JWT (PRO) | Create recurring schedule |
| PUT | `/api/recurring/:id` | JWT (PRO) | Update schedule |
| DELETE | `/api/recurring/:id` | JWT (PRO) | Cancel schedule |

---

### AI Engine

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/ai/cards` | JWT | Get AI action cards (rules-based, no OpenAI) |
| POST | `/api/ai/action` | JWT | Execute an AI action (send reminder, draft PO) |
| GET | `/api/ai/snooze/:card_id` | JWT | Snooze an action card |

---

### Integrations

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/integrations/fortnox/connect` | JWT (owner) | Start Fortnox OAuth flow |
| GET | `/api/integrations/fortnox/callback` | None | OAuth callback (redirect) |
| POST | `/api/integrations/fortnox/disconnect` | JWT (owner) | Remove Fortnox connection |
| POST | `/api/integrations/fortnox/sync-invoices` | JWT (owner) | Push invoices to Fortnox |
| GET | `/api/integrations/fortnox/status` | JWT | Check connection status |
| POST | `/api/integrations/chat` | JWT (PRO) | GPT-4o chat assistant |
| GET | `/api/integrations/bolagsverket/:orgnr` | JWT | Swedish company lookup |

---

### Billing (SaaS Subscriptions)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/billing/checkout` | JWT (owner) | Create Stripe Checkout session |
| POST | `/api/billing/portal` | JWT (owner) | Create Stripe Customer Portal session |
| GET | `/api/billing/status` | JWT | Current plan status |
| POST | `/api/billing/webhook` | Stripe sig | Handle subscription events |

---

### B2B Customer Portal

All portal endpoints use portal JWT (`type: "portal"`) in `Authorization` header.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/portal/auth/magic-link` | None | Request magic login link |
| GET | `/api/portal/auth/verify` | None | Verify magic link token |
| POST | `/api/portal/auth/otp/request` | None | Request OTP code |
| POST | `/api/portal/auth/otp/verify` | None | Verify OTP → returns portal JWT |
| GET | `/api/portal/invoices` | Portal JWT | List customer's invoices |
| GET | `/api/portal/invoices/:id` | Portal JWT | Invoice detail |
| GET | `/api/portal/invoices/:id/pdf` | Portal JWT | Download invoice PDF |
| GET | `/api/portal/catalogue` | Portal JWT | Product catalogue |
| POST | `/api/portal/orders` | Portal JWT | Place an order |
| GET | `/api/portal/orders` | Portal JWT | Order history |

---

### Team

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/team/members` | JWT | List team members |
| POST | `/api/team/invite` | JWT (owner/admin) | Invite by email |
| DELETE | `/api/team/members/:id` | JWT (owner) | Remove member |
| PUT | `/api/team/members/:id/role` | JWT (owner) | Change role |

---

### Accounting

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/accounting/sie4-export` | JWT (owner) | Export SIE4 file for fiscal year |

---

## Error Response Format

All errors return JSON:

```json
{
  "detail": "Human readable message",
  "code": "OPTIONAL_ERROR_CODE"
}
```

| Status | Meaning |
|--------|---------|
| `400` | Bad request |
| `401` | Unauthenticated — missing or invalid JWT |
| `403` | Unauthorized — authenticated but action not permitted |
| `404` | Resource not found |
| `422` | Validation error (Pydantic) |
| `429` | Rate limited |
| `500` | Internal server error |
| `503` | Service unavailable (maintenance mode or dependency down) |

---

## Rate Limiting

Limits are applied per-org and per-IP. Exceeding the limit returns `429 Too Many Requests` with a `Retry-After` header.

Rate limiting can be disabled for integration tests via `RATE_LIMIT_DISABLED=true` — **never set this in production**.

---

## Pagination

List endpoints support:

```
GET /api/invoicing/invoices?limit=50&offset=0
```

Default `limit` is 50. Maximum is 200. All list endpoints are paginated — unlimited result sets are not supported.
