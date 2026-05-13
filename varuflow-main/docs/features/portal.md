# B2B Customer Portal

The Varuflow customer portal is a self-service web app for wholesale customers. It lets buyers view their invoices, track orders, browse the product catalogue, and place new orders — without needing access to the main Varuflow app.

---

## Overview

The portal is a separate Next.js app at `/portal/*`. It has its own auth system (no Supabase — uses magic links and OTP codes) and its own JWT type to prevent cross-contamination with the main app.

| Feature | Status |
|---------|--------|
| Magic link login | Done |
| OTP (SMS/email) login | Done |
| Invoice list | Done |
| Invoice detail | Done |
| Invoice PDF download | Done |
| Product catalogue | Done |
| Order placement | Done |
| Order history | Done |
| Invoice payment (Stripe/Swish) | Not implemented |
| Credit note visibility | Not implemented |
| Locale support (sv/no/da) | Not implemented (English only) |

---

## How Customers Access the Portal

### Sharing Portal Access

From the main Varuflow app, org users can send a portal access invite to a customer:

1. Open a customer record
2. Click **Send portal invite**
3. The customer receives an email with a magic link
4. They click the link → verified → logged into the portal

Or customers can return later at `https://varuflow.vercel.app/portal` and request a new OTP.

### Portal URL

Production: `https://varuflow.vercel.app/portal`  
Local dev: `http://localhost:3000/portal`

---

## Authentication

The portal uses its own lightweight auth — no Supabase account is required for customers.

### Magic Link Flow

```
1. Customer enters email at /portal/login
2. POST /api/portal/auth/magic-link { email }
   └── Backend looks up customer by email + org
   └── Generates a 24-hour signed token
   └── Sends email via Resend with link: /portal/auth/verify?token=...
3. Customer clicks link
4. GET /api/portal/auth/verify?token=...
   └── Validates token
   └── Creates portal session
   └── Returns portal JWT (type: "portal", signed with PORTAL_JWT_SECRET)
5. Frontend stores JWT, redirects to /portal/invoices
```

### OTP Flow

```
1. Customer enters email or phone at /portal/login
2. POST /api/portal/auth/otp/request { email }
   └── Generates 6-digit code, stores in portal_otp table (10-min TTL)
   └── Sends code via email or SMS
3. Customer enters code at /portal/auth/verify
4. POST /api/portal/auth/otp/verify { email, code }
   └── Validates code (checks expiry, max attempts)
   └── Returns portal JWT
```

### Portal JWT

Portal JWTs are distinct from regular user JWTs:

```json
{
  "type": "portal",
  "customer_id": "...",
  "org_id": "...",
  "exp": 1234567890
}
```

The `type: "portal"` claim is checked by the backend auth middleware. Portal tokens are **rejected on all internal routes** (e.g., `/api/invoicing/*`). Internal user JWTs are rejected on all portal routes. The two auth domains are completely isolated.

---

## Portal API Endpoints

All portal endpoints use the portal JWT:

```
Authorization: Bearer <portal-jwt>
```

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portal/invoices` | List invoices for the logged-in customer |
| GET | `/api/portal/invoices/:id` | Invoice detail (amounts, line items, status) |
| GET | `/api/portal/invoices/:id/pdf` | Download invoice PDF |
| GET | `/api/portal/catalogue` | Product catalogue (visible products only) |
| POST | `/api/portal/orders` | Place a new order |
| GET | `/api/portal/orders` | Order history |

---

## Portal Pages

```
/portal/                           → Redirects to /portal/invoices
/portal/login                      → Email input, request magic link or OTP
/portal/auth/verify?token=...      → Magic link verification
/portal/invoices                   → Invoice list with status badges
/portal/invoices/:id               → Invoice detail + PDF download
/portal/catalogue                  → Product catalogue
/portal/orders                     → Order history
```

---

## Security

### Org Isolation

Each portal session is scoped to a single customer within a single org. Customers can only see:
- Their own invoices (filtered by `customer_id`)
- Products visible to them (respects `is_public` flag on products or customer price groups)
- Their own orders

### Token Lifetime

| Token type | Lifetime |
|------------|---------|
| Magic link token | 24 hours |
| OTP code | 10 minutes |
| Portal JWT | Configurable via `PORTAL_JWT_SECRET` (typically 7 days) |

### PORTAL_JWT_SECRET

Separate from `AUTH_JWT_SECRET` and `SUPABASE_JWT_SECRET`. Set on Railway:

```
PORTAL_JWT_SECRET=<32-char-random-hex>
```

Generate: `python -c "import secrets; print(secrets.token_hex(16))"`

Keep it rotated (see [SECURITY.md → Admin key rotation](../../SECURITY.md) for the rotation pattern).

---

## Customisation

### Company Branding

The portal displays the seller's company name and logo (from their Organization profile). There is no white-label custom domain support yet.

### Visible Products

Control which products appear in the catalogue:
- Set `is_public = true` on products you want customers to see
- Customers see prices based on their customer price group (if configured)

---

## Missing Features (Roadmap)

### Invoice Payments from Portal

Customers currently cannot pay invoices from within the portal. This is the top requested portal feature.

**Planned implementation:**
1. Add "Pay now" button on invoice detail page
2. `POST /api/portal/invoices/:id/pay` → create Stripe Checkout session or Swish payment request
3. Redirect to payment page
4. On completion, mark invoice as PAID + notify org user

### Multiple Contacts per Customer

Currently one magic-link email per customer. Multi-contact support (e.g. finance contact, purchasing contact) is on the roadmap.

### Locale Support

The portal is English-only. Adding Swedish/Norwegian/Danish locale support requires:
1. Adding locale route prefix to portal pages (`/portal/sv/`, `/portal/en/`)
2. Adding portal keys to `sv.json`, `no.json`, `da.json`
3. Adding portal paths to locale middleware exclusions

### Credit Notes

Customers cannot see credit notes in the portal. These should appear alongside invoices.

---

## Supplier Portal

A separate supplier portal exists at `/supplier-portal/*` for purchase order management. Suppliers can view POs sent to them and update order status.

See: `/frontend/src/app/supplier-portal/` for the frontend pages.  
See: `backend/app/routers/supplier_portal.py` for the API.
