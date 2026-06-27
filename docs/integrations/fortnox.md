# Fortnox Integration

Varuflow integrates with [Fortnox](https://www.fortnox.se) — the most widely used accounting system for Swedish SMEs. The integration uses OAuth2 and pushes invoices from Varuflow into Fortnox automatically.

---

## What It Does

- **Invoice sync (push):** When an invoice is marked as SENT in Varuflow, it can be pushed to Fortnox's invoice registry
- **OAuth2 authentication:** Org owners connect their Fortnox account once; tokens are refreshed automatically
- **Token security:** Fortnox OAuth tokens (access + refresh) are encrypted at rest using Fernet (`FORTNOX_ENCRYPTION_KEY`)

---

## Current Limitations

- **One-directional only:** Varuflow pushes invoices to Fortnox. Changes made in Fortnox are not pulled back.
- **Invoices only:** Customers and products are not synced. The sync sends invoice data only.
- **No sync history UI:** The settings page shows connected/disconnected status but no list of synced invoices or last-sync timestamp.

---

## Setup (Production)

### 1. Create a Fortnox App

1. Log in to [Fortnox Developer Portal](https://developer.fortnox.se)
2. Create a new app — select **Integration type: API**
3. Note down: `Client ID` and `Client Secret`
4. Add the redirect URI:
   ```
   https://varuflow-production.up.railway.app/api/integrations/fortnox/callback
   ```

### 2. Set Environment Variables on Railway

```
FORTNOX_CLIENT_ID=<your-client-id>
FORTNOX_CLIENT_SECRET=<your-client-secret>
FORTNOX_REDIRECT_URI=https://varuflow-production.up.railway.app/api/integrations/fortnox/callback
FORTNOX_ENCRYPTION_KEY=<Fernet-key>
```

Generate the encryption key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> The startup validator (`validate_production_config`) will crash the deploy if `FORTNOX_CLIENT_ID` or `FORTNOX_CLIENT_SECRET` is set but `FORTNOX_ENCRYPTION_KEY` or `FORTNOX_REDIRECT_URI` is missing.

### 3. Connect in the App

1. An org owner goes to **Settings → Integrations**
2. Clicks **Connect Fortnox**
3. The browser redirects to `GET /api/integrations/fortnox/connect` → redirects to Fortnox OAuth consent
4. After approval, Fortnox calls `/api/integrations/fortnox/callback`
5. Tokens are stored encrypted in the `Organization` table

---

## OAuth Flow (Technical)

```
1. GET /api/integrations/fortnox/connect
   └── Generates state param (CSRF), stores in session
   └── Redirects to: https://apps.fortnox.se/oauth-v1/auth
      ?client_id=...&redirect_uri=...&scope=invoice&state=...&response_type=code

2. User approves in Fortnox

3. GET /api/integrations/fortnox/callback?code=...&state=...
   └── Verifies state (CSRF)
   └── POSTs to https://apps.fortnox.se/oauth-v1/token to exchange code
   └── Encrypts access_token + refresh_token with FORTNOX_ENCRYPTION_KEY
   └── Stores in Organization.fortnox_access_token / fortnox_refresh_token / fortnox_token_expiry
   └── Redirects to /settings

4. APScheduler runs token refresh every 55 minutes
   └── Calls https://apps.fortnox.se/oauth-v1/token with grant_type=refresh_token
   └── Overwrites encrypted tokens in DB
```

---

## Invoice Sync (Technical)

Endpoint: `POST /api/integrations/fortnox/sync-invoices`  
Auth: Org owner JWT

The sync reads all SENT and PAID invoices that have not yet been synced, and creates them in Fortnox via:

```
POST https://api.fortnox.se/3/invoices
Authorization: Bearer <decrypted-access-token>
```

The Fortnox invoice format maps:

| Varuflow field | Fortnox field |
|----------------|--------------|
| `customer.org_number` | `CustomerNumber` |
| `customer.name` | `CustomerName` |
| `invoice.invoice_number` | `DocumentNumber` |
| `invoice.issued_date` | `InvoiceDate` |
| `invoice.due_date` | `DueDate` |
| `line_items[].description` | `Description` |
| `line_items[].quantity` | `DeliveredQuantity` |
| `line_items[].unit_price` | `Price` |
| `line_items[].vat_rate` | `VAT` |

---

## Token Encryption

Fortnox tokens are sensitive — they grant write access to the customer's accounting system. They are encrypted using Fernet symmetric encryption before being stored in the database.

Rotation: set `FORTNOX_ENCRYPTION_KEY` to the new key and `FORTNOX_ENCRYPTION_KEY_PREVIOUS` to the old key. Old tokens are re-encrypted on next read. Once all tokens have been re-encrypted, clear `FORTNOX_ENCRYPTION_KEY_PREVIOUS`.

---

## Disconnect

`POST /api/integrations/fortnox/disconnect` (owner only)

Clears `fortnox_access_token`, `fortnox_refresh_token`, and `fortnox_token_expiry` from the `Organization` row. Does not notify Fortnox (no revocation API call). The app tokens will expire naturally on Fortnox's side.

---

## Local Development

In local dev, leave `FORTNOX_CLIENT_ID` empty. The `/api/integrations/fortnox/connect` endpoint returns a 503 when credentials are not configured. All other app functionality works normally.

The startup validator is disabled in dev (`ENV=development`), so no crash occurs with empty Fortnox credentials locally.
