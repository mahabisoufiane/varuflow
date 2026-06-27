# Swish Integration

[Swish](https://www.swish.nu) is Sweden's dominant real-time mobile payment system, used by over 8 million Swedes. It is widely used in B2C and increasingly in B2B wholesale transactions.

---

## Current Status

**Partially implemented.** Swish exists as a payment method label in the POS module but the actual Swish Merchant API integration is not yet built.

| Component | Status |
|-----------|--------|
| POS payment method enum (`SWISH`) | Done |
| Swish QR code placeholder in PDF | Done (placeholder only) |
| Swish Merchant API integration | Not implemented |
| QR code generation (real) | Not implemented |
| Payment initiation | Not implemented |
| Payment status callback | Not implemented |

---

## Planned Implementation

### API: Swish Merchant Payments API (M-Commerce)

The correct API for Varuflow's use case is the [Swish Merchant Payments API](https://developer.swish.nu/documentation/getting-started), specifically:

- **E-commerce flow:** Customer initiates payment from their Swish app by scanning a QR or entering the merchant's Swish number
- **M-commerce flow:** Direct deep-link (`swish://paymentrequest?token=...`) for mobile users

### What Needs to Be Built

#### Backend

1. **`backend/app/services/swish_service.py`**
   - mTLS client (Swish requires mutual TLS, similar to BankID)
   - `create_payment_request(amount, currency, message, callback_url)` → returns `token` and `id`
   - `get_payment_status(payment_request_id)` → returns status: `CREATED | PAID | DECLINED | ERROR | CANCELLED`
   - `cancel_payment_request(payment_request_id)`

2. **`backend/app/routers/swish.py`**
   - `POST /api/swish/payment-request` — create payment request
   - `GET /api/swish/payment-request/:id` — poll status
   - `POST /api/swish/callback` — receive Swish callback (status update)

3. **New env vars:**
   ```
   SWISH_MERCHANT_NUMBER=123xxxxxxx      # Your Swish merchant number (10 digits)
   SWISH_CLIENT_CERT_PATH=               # PEM bundle (cert + key) from Swish
   SWISH_CA_CERT_PATH=                   # Swish root CA for server verification
   SWISH_CALLBACK_URL=https://varuflow-production.up.railway.app/api/swish/callback
   ```

#### Frontend

1. **QR code generation** in `PosReceiptModal.tsx` — replace `[Swish QR]` placeholder with real QR from token
2. **Payment status polling** in POS session page
3. **Mobile deep-link** via `swish://paymentrequest?token=<token>` for mobile checkout

---

## Merchant Onboarding

To accept Swish payments, you must be a registered Swish merchant:

1. Contact your Swedish bank (Handelsbanken, SEB, Swedbank, Nordea, etc.)
2. Request Swish for Merchants
3. Receive your **Swish merchant number** (10 digits starting with `123`)
4. Download your **merchant certificate** (`.p12` file) from the bank
5. Convert to PEM format:
   ```bash
   openssl pkcs12 -in merchant.p12 -out merchant.pem -nodes
   ```
6. Upload to Railway and set `SWISH_CLIENT_CERT_PATH`

---

## Test Environment

Swish provides a [merchant simulator](https://developer.swish.nu/documentation/environments#test) for development:

```
SWISH_API_URL=https://mss.crt.swish.nu/swish-cpcapi/api/v2
SWISH_MERCHANT_NUMBER=1231181189          # Simulator test number
```

Test certificates available from the Swish developer portal.

---

## Payment Flow (Once Implemented)

### POS (In-Store)

```
1. Cashier selects Swish as payment method
2. POST /api/swish/payment-request { amount, message: "Invoice #1234" }
3. Backend creates payment request via Swish API → returns token
4. Frontend displays QR code (customer scans with Swish app)
   OR launches swish:// deep-link on customer's mobile
5. Customer approves in their Swish app
6. Swish sends callback to /api/swish/callback with status=PAID
7. POS session records payment, marks receipt as complete
```

### Invoice Payment

```
1. Invoice is SENT to customer
2. Backend generates Swish payment request on invoice (like Stripe payment link)
3. QR or link embedded in PDF or emailed
4. Customer pays via Swish
5. Callback marks invoice as PAID
```

---

## References

- [Swish Developer Portal](https://developer.swish.nu)
- [Swish API Documentation](https://developer.swish.nu/documentation/getting-started)
- [Swish Test Environment](https://developer.swish.nu/documentation/environments#test)
- [Swish Merchant Onboarding](https://www.swish.nu/foretag)
