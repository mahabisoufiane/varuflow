# Security Hardening — HTTP Response Headers

_Last updated: Item 22 (v42+)._

This document describes the HTTP security headers Varuflow emits on both the
Next.js frontend and the FastAPI backend, justifies each allow-list entry,
and gives operators a runbook for tightening the policy quickly when a
third-party provider is compromised.

## Where the policy lives

| Layer    | File                                           | Scope                    |
| -------- | ---------------------------------------------- | ------------------------ |
| Frontend | [frontend/src/lib/security-headers.mjs](../../frontend/src/lib/security-headers.mjs) | Every route (`/(.*)`)    |
| Frontend | [frontend/next.config.mjs](../../frontend/next.config.mjs) | Wires the lib into Next |
| Backend  | [backend/app/main.py](../../backend/app/main.py) (`_add_security_headers`) | Every JSON response      |
| Tests    | [frontend/src/tests/test_security_headers.mjs](../../frontend/src/tests/test_security_headers.mjs) | Golden-string + allow-list guardrails |
| CI       | [.github/workflows/security.yml](../../.github/workflows/security.yml) (`frontend-headers` job) | Runs the tests on every PR |

The frontend module exports pure functions (`buildCsp`, `buildSecurityHeaders`)
so the policy is testable in isolation. `next.config.mjs` is a thin caller —
a regression in the config is caught by the CI job below before it merges.

## Header-by-header rationale

### `Content-Security-Policy`
Primary defence against XSS. Every directive is enumerated explicitly; no
wildcards. See the [Allow-list inventory](#allow-list-inventory) for the per-host
justification. `frame-ancestors 'none'` complements `X-Frame-Options: DENY`
for browsers that ignore the legacy header.

Known compromise: `script-src` includes `'unsafe-inline' 'unsafe-eval'`.
This is required by the Next.js App Router hydration bootstrap and matches
Vercel's published template. Tightening to `strict-dynamic` + nonces is
tracked as a separate hardening item and requires middleware-generated
nonces injected into every `<script>` tag — not a drop-in change.

### `X-Frame-Options: DENY`
Legacy clickjacking defence. Redundant with `frame-ancestors 'none'` but
cheap and still respected by older browsers and bot-prevention proxies.

### `X-Content-Type-Options: nosniff`
Prevents browsers from MIME-sniffing `text/plain` into executable script.
Zero-cost hardening; no compatibility downside.

### `Referrer-Policy: strict-origin-when-cross-origin`
Strips path + query from the Referer on cross-origin navigation, keeps
the origin. Enough for analytics attribution but does not leak tenant IDs
or invoice numbers to third parties.

### `Permissions-Policy`
Explicitly disables `camera`, `microphone`, `geolocation` on the frontend.
Backend additionally disables `interest-cohort` (FLoC) since API responses
should never opt-in to browser ad-targeting experiments.

### `Strict-Transport-Security` (backend, production only)
`max-age=63072000; includeSubDomains; preload` — 2-year pin with preload
eligibility. Gated on `settings.ENV == "production"` so local dev and
preview deployments don't poison a developer's browser when they flip
between HTTP and HTTPS.

### `Cross-Origin-Opener-Policy: same-origin` (backend)
`Cross-Origin-Resource-Policy: same-site` (backend)
Isolates the API from cross-origin windows and embeds. The frontend
doesn't set these — it must remain embeddable as its own origin and the
Next.js runtime does not need cross-origin isolation for our workload.

## Allow-list inventory

Every external host explicitly enumerated in the frontend CSP, with the
product feature that requires it:

| Host                                   | Directive(s)                        | Why |
| -------------------------------------- | ----------------------------------- | --- |
| `https://js.stripe.com`                | `script-src`, `frame-src`           | Stripe Elements + Checkout SDK |
| `https://hooks.stripe.com`             | `frame-src`                         | Stripe 3DS challenge iframe |
| `https://api.stripe.com`               | `connect-src`                       | Stripe PaymentIntent confirmations from the browser |
| `https://client.crisp.chat`            | `script-src`, `style-src`, `font-src`, `frame-src`, `connect-src` | Crisp live-chat widget |
| `wss://client.relay.crisp.chat`        | `connect-src`                       | Crisp websocket for real-time chat |
| `https://fonts.googleapis.com`         | `style-src`                         | Google Fonts stylesheet |
| `https://fonts.gstatic.com`            | `font-src`                          | Google Fonts WOFF2 payloads |
| `NEXT_PUBLIC_API_URL`                  | `connect-src`                       | Varuflow FastAPI backend (env-supplied) |
| `NEXT_PUBLIC_SUPABASE_URL`             | `connect-src`                       | Supabase auth + realtime (env-supplied) |
| `new URL(NEXT_PUBLIC_SENTRY_DSN).origin` | `connect-src`                     | Sentry ingestion host — DSN origin only, never the full DSN |

The env-derived entries (API, Supabase, Sentry) are parsed safely at
build time. A malformed Sentry DSN degrades to "no Sentry host in CSP"
rather than throwing.

## Why `'unsafe-inline' 'unsafe-eval'` in `script-src`

Next.js App Router injects a small inline bootstrap script to wire up
client components; removing `'unsafe-inline'` breaks hydration. Moving
to nonce-based `strict-dynamic` requires:

1. A middleware that generates a per-request nonce.
2. Propagating the nonce through `<Script>` + every inline snippet.
3. A compile-time check that no library injects a raw `<script>` without
   the nonce.

This is tracked separately. Shipping it as part of the headers refactor
would break the "safe and minimal" constraint for Item 22 — the correct
place is a dedicated hardening item once Next.js ships first-class nonce
support for the App Router.

## Runbook — tightening quickly when a host is compromised

1. Identify the directive containing the compromised host (e.g. Crisp
   breach would hit `script-src`, `connect-src`, `frame-src`).
2. Remove the host from [frontend/src/lib/security-headers.mjs](../../frontend/src/lib/security-headers.mjs).
3. Run the test suite locally:
   ```sh
   cd frontend && node --test src/tests/test_security_headers.mjs
   ```
   The golden-string assertion will fail — update `EXPECTED_CSP` in the
   test file to match the new policy. The other allow-list assertions
   serve as a hand-hold to make sure you only removed what you intended.
4. Open a PR. The `frontend-headers` CI job will validate the new
   expected state.
5. If the backend also talks to the compromised host (Supabase, Sentry),
   update [backend/app/main.py](../../backend/app/main.py) in the same PR —
   backend CSP is `default-src 'none'` so it's usually unaffected, but
   Sentry SDK uses direct ingestion and is an exception.
6. Deploy. The policy change takes effect on next request; no browser
   cache purge needed because CSP is a response header, not a cached
   resource.

## Running the tests locally

```sh
cd frontend
node --test src/tests/test_security_headers.mjs
```

No extra dependencies required — `node:test` is stdlib since Node 18 and
the frontend already pins Node 18+ in CI.

---

# PII Encryption at Rest (Item 28)

Sensitive columns in Postgres are transparently encrypted with Fernet
(AES-128-CBC + HMAC-SHA256) before being written, and transparently
decrypted when read back through the ORM. The scheme is application-
level, not column-level-at-the-DB-layer — `pgcrypto` is not used. An
attacker with a read-only DB snapshot cannot recover the plaintext
without also compromising the API process.

## Encrypted columns

The `EncryptedString` SQLAlchemy `TypeDecorator` (see
[backend/app/services/encryption.py](../../backend/app/services/encryption.py))
is applied to:

| Column | Why encrypted |
|--------|---------------|
| `auth_users.totp_secret` | Raw TOTP seed — compromise gives permanent MFA bypass. |
| `customers.email` | PII; direct contact vector. |
| `customers.phone` | PII; direct contact vector. |
| `customers.whatsapp_number` | PII; direct contact vector. |
| `customers.address` | PII; physical-location data. |

Fortnox OAuth access and refresh tokens are already encrypted via the
older [backend/app/services/crypto.py](../../backend/app/services/crypto.py)
(ciphertext prefix `fenc:v1:`). That module is kept for backward
compatibility with tokens issued before Item 28; new columns use
`encryption.py` (prefix `penc:v1:`).

## Generating keys

```sh
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set the result in the environment as `PII_ENCRYPTION_KEY`. The key is a
32-byte urlsafe-Base64 string; any other shape will cause the module to
log an error and fall back to plaintext, which is why the key generator
is scripted rather than hand-edited.

## First-time rollout

The rollout is zero-downtime because `decrypt_pii` transparently returns
legacy plaintext values (no `penc:v1:` prefix) unchanged.

1. Deploy Item 28 code with `PII_ENCRYPTION_KEY` set.
2. Run migration `v46_pii_encryption_widen` to enlarge the VARCHAR
   columns so ciphertext fits.
3. New writes are encrypted; reads of legacy rows still work.
4. (Optional) Run the backfill script below to convert legacy rows.

## Backfill script

Re-reads every row of an encrypted column and re-writes the value,
triggering the `EncryptedString` bind path.

```python
# scripts/backfill_pii_encryption.py
import asyncio
from sqlalchemy import select
from sqlalchemy.orm import attributes
from app.database import AsyncSessionLocal
from app.models.auth import AuthUser
from app.models.invoicing import Customer


async def rewrite(obj, fields):
    for f in fields:
        v = getattr(obj, f)
        if v is not None:
            setattr(obj, f, v)                # force __setattr__ → bind
            attributes.flag_modified(obj, f)  # mark dirty


async def main() -> None:
    async with AsyncSessionLocal() as s:
        for u in (await s.execute(select(AuthUser))).scalars():
            await rewrite(u, ["totp_secret"])
        for c in (await s.execute(select(Customer))).scalars():
            await rewrite(c, ["email", "phone", "whatsapp_number", "address"])
        await s.commit()


if __name__ == "__main__":
    asyncio.run(main())
```

Run off-peak; wrap in a transaction-per-batch if your dataset is large.

## Key rotation

Zero-downtime rotation uses `MultiFernet` under the hood — set the old
key in `PII_ENCRYPTION_KEY_PREVIOUS` for the duration of the cutover so
rows written under the old key still decrypt.

```text
Step 1: Generate new key (see "Generating keys" above).

Step 2: Deploy with:
          PII_ENCRYPTION_KEY=<NEW KEY>
          PII_ENCRYPTION_KEY_PREVIOUS=<OLD KEY>
        New writes use NEW; old rows decrypt via OLD.

Step 3: Run the backfill script. Every row is re-written under NEW.

Step 4: Clear PII_ENCRYPTION_KEY_PREVIOUS and redeploy.
        Any row still encrypted with the old key will now raise
        RuntimeError("Stored PII could not be decrypted") on read —
        this is a loud failure, not silent data loss.
```

## Disabling the feature

Unsetting `PII_ENCRYPTION_KEY` is safe **only if no row has been
encrypted yet**. If encrypted rows exist and the key is removed, any
read of those rows raises `RuntimeError("PII_ENCRYPTION_KEY missing —
cannot decrypt stored PII")`. To permanently disable:

1. Keep `PII_ENCRYPTION_KEY` set.
2. Run a reverse backfill that writes `decrypt_pii(value)` back as
   plaintext.
3. Then unset the env var.

## Limitations

- **Fernet is non-deterministic.** The same plaintext encrypts to a
  different ciphertext on each write, so `WHERE email = :x` matches
  only the single row written in the current transaction. Exact-match
  lookups across rows require a separate blind-indexed hash column;
  none are in scope for Item 28 because no current code path does that.
- **Partial-text search does not work** on encrypted columns. The
  search API does not currently search `email`, `phone`, or `address`
  — if that changes, those indexes must fall back to an unencrypted
  projection of the minimum data needed.
- **No defence against RCE on the API server.** The key is in process
  memory by definition. Pair this with transparent disk encryption on
  the Postgres host and strict IAM on backup buckets for defence in
  depth.
- **Fortnox tokens use a different key.** `FORTNOX_ENCRYPTION_KEY` is
  independent from `PII_ENCRYPTION_KEY` and rotates on its own
  schedule. Do not try to unify them in place — the prefixes differ
  (`fenc:v1:` vs `penc:v1:`) so a mix-up surfaces as a loud
  `RuntimeError` rather than silent corruption, but the operational
  separation keeps blast radii small.

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| `RuntimeError: PII_ENCRYPTION_KEY missing` | Env var unset but DB has encrypted rows. | Restore the key from the secret manager and redeploy. |
| `RuntimeError: Stored PII could not be decrypted (key mismatch)` | Key rotated without backfill; previous key dropped. | Restore the old key as `PII_ENCRYPTION_KEY_PREVIOUS`, redeploy, run backfill, then drop again. |
| Startup log `PII_ENCRYPTION_KEY is invalid` | Key is not a valid urlsafe-Base64 32-byte Fernet key. | Regenerate with the `python -c` one-liner. Never hand-edit. |
| Tests pass locally but fail in CI with `RuntimeError: PII_ENCRYPTION_KEY missing` | CI env has the key; a seeded row was encrypted; a later test removes the key. | Call `app.services.encryption._reset_cache_for_tests()` from the fixture that changes the key. |
