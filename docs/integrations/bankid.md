# BankID Integration

[BankID](https://www.bankid.com) is Sweden's national e-identification system. Varuflow supports BankID authentication for Swedish users as an alternative to email/password login.

---

## What It Does

- **Authentication:** Users can log in using their BankID app (mobile) or BankID on card
- **QR code flow:** Animated QR code displayed in the app for the user to scan with their BankID app
- **Personnummer linking:** BankID confirms the user's personnummer (Swedish national ID)
- **mTLS:** The backend communicates with BankID's Relying Party API using mutual TLS (client certificate)

---

## Current Limitations

- **Auth only, no Sign:** Only the authentication flow is implemented. Document signing (BankID Sign) is not implemented.
- **App login only:** BankID is available in the main app login. It is not available in the B2B customer portal (portal uses magic link / OTP).
- **Production cert required:** BankID requires a relying-party client certificate from Finansiell ID-Teknik BID AB for production. Without it, the backend raises `BankIDNotConfigured` and returns 503.

---

## Setup (Production)

### 1. Obtain a Relying Party Certificate

1. Sign an agreement with [Finansiell ID-Teknik BID AB](https://www.bankid.com/en/foretag/kontakt)
2. Complete the Relying Party onboarding process
3. Receive a PEM bundle containing:
   - Relying-party client certificate
   - Private key
   (in that order, combined in a single `.pem` file)
4. Optionally receive the BankID CA bundle for server certificate pinning

### 2. Upload Certificate to Railway

Do **not** store the certificate file in git. Upload it as a Railway volume or secret file.

Option A — File path (recommended):
```bash
# Upload cert file to Railway volume
# Then set the environment variable:
BANKID_CLIENT_CERT_PATH=/path/to/rp-cert.pem
BANKID_CA_CERT_PATH=/path/to/bankid-ca.pem   # Optional — falls back to certifi
```

Option B — Base64 environment variable:
```bash
# Encode the cert
base64 -w 0 rp-cert.pem

# Store in Railway as BANKID_CLIENT_CERT_B64 and decode at startup
# (requires a small change to bankid.py to write to a temp file)
```

### 3. Set API URL for Production

```
BANKID_API_URL=https://appapi2.bankid.com/rp/v6.0
```

The default is the **test environment** (`https://appapi2.test.bankid.com/rp/v6.0`). You must override this for production.

---

## How the Auth Flow Works

```
1. User clicks "Logga in med BankID" on login page

2. POST /api/local-auth/bankid/init
   └── Backend calls BankID /auth endpoint (mTLS)
   └── Returns: { orderRef, autoStartToken, qrStartSecret, qrStartToken }

3. Frontend displays animated QR code
   └── QR data updates every second using HMAC-SHA256:
       qrData = "bankid." + qrStartToken + "." + time + "." + HMAC(qrStartSecret, time)

4. User opens BankID app → scans QR → approves

   (Alternative: user is on mobile → frontend launches bankid:/// URI scheme)

5. GET /api/local-auth/bankid/collect?orderRef=...
   └── Backend polls BankID /collect endpoint
   └── Returns status: pending | failed | complete
   └── On complete: returns { personnummer, name, jwt }

6. Frontend receives JWT → stores session → redirects to /dashboard
```

---

## Personnummer Handling

The `bankid.py` service normalises personnummer to canonical 12-digit format:

| Input | Normalised |
|-------|-----------|
| `850101-1234` | `198501011234` |
| `8501011234` | `198501011234` |
| `19850101+1234` | `198501011234` (born before 1900 if `+`) |
| `850101+1234` | `190501011234` |

The personnummer is **hashed** (SHA-256) before being stored — it is never stored in plaintext. Matching at login time uses the same hash.

---

## Test Environment

The default `BANKID_API_URL` points to BankID's test environment. You need BankID test app and test certificates to use it.

Test certificates are available from: https://www.bankid.com/en/utvecklare/test

Test personnummers (fictitious, for simulator):
- `190000000000` — Standard test user

---

## Error States

| BankID status | Meaning | User message |
|---------------|---------|--------------|
| `pending` | Waiting for user | "Scan the QR code with your BankID app" |
| `failed: cancelled` | User cancelled | "BankID login was cancelled" |
| `failed: expiredTransaction` | 30s timeout | "QR code expired — try again" |
| `failed: certificateErr` | Wrong BankID cert | "BankID error — contact support" |
| `failed: userCancel` | User rejected | "BankID login was rejected" |

---

## Security Notes

- All communication with BankID uses **mTLS** — both the backend presents a client certificate and verifies BankID's server certificate
- `orderRef` is a one-time token — it cannot be reused after collection
- BankID JWTs are short-lived (8 minutes timeout on their side)
- Personnummer is stored hashed only — Varuflow cannot recover a user's personnummer from the DB
