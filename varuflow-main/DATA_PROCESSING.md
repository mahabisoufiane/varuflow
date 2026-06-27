# DATA_PROCESSING.md — PII Inventory
**Generated:** 2026-06-14  
**Scope:** `backend/app/models/` — all SQLAlchemy models (~160 files)  
**Purpose:** GDPR Art. 30 Record of Processing Activities (RoPA) + encryption status

This document maps which database columns hold personal data, whether they are
encrypted at rest, and what retention rules apply. Update it whenever a new
model with PII is added or a column type changes.

---

## Key: column status

| Symbol | Meaning |
|--------|---------|
| 🔒 | Encrypted at rest via `EncryptedString` (Fernet AES-128-CBC, key `PII_ENCRYPTION_KEY`) |
| ⚠️ | Plaintext — stored unencrypted; consider adding `EncryptedString` |
| 🏷️ | Hashed / pseudonymous (no decrypt path) |
| 🗑️ | Anonymised on GDPR erasure (`DELETE /api/gdpr/organization`) |

---

## 1. Core business PII (directly collected from customers)

### `customers` table (`app/models/invoicing.py`)

| Column | Type | Status | Notes |
|--------|------|--------|-------|
| `company_name` | String(255) | ⚠️ 🗑️ | Legal entity name — may identify a natural person (sole trader) |
| `org_number` | String(20) | ⚠️ 🗑️ | Swedish org number — identifies the legal entity |
| `vat_number` | String(30) | ⚠️ 🗑️ | EU VAT identifier |
| `email` | EncryptedString(512) | 🔒 🗑️ | Primary contact email |
| `phone` | EncryptedString(256) | 🔒 🗑️ | Primary contact phone |
| `whatsapp_number` | EncryptedString(256) | 🔒 🗑️ | WhatsApp number |
| `address` | EncryptedString(1024) | 🔒 🗑️ | Billing/delivery address |
| `deleted_at` | TimestampTZ | — | Soft delete timestamp (added Phase 4 / M-2) |

Retention: retained 7 years after last invoice under BFL 7 kap. 2 §; PII
columns replaced with placeholders on GDPR erasure request.

### `customer_contacts` table (`app/models/customer_contact.py`)

| Column | Type | Status |
|--------|------|--------|
| `name` | String(128) | ⚠️ |
| `email` | EncryptedString(512) | 🔒 |
| `phone` | EncryptedString(256) | 🔒 |

### `suppliers` table (`app/models/inventory.py`)

| Column | Type | Status | Notes |
|--------|------|--------|-------|
| `email` | String(255) | ⚠️ | **Gap: not encrypted.** Consider `EncryptedString`. |
| `phone` | String(50) | ⚠️ | Same gap. |
| `address` | String(500) | ⚠️ | Same gap. |

### `supplier_contacts` table (`app/models/supplier_contact.py`)

| Column | Type | Status |
|--------|------|--------|
| `name` | String(128) | ⚠️ |
| `email` | EncryptedString(512) | 🔒 |
| `phone` | EncryptedString(256) | 🔒 |

---

## 2. Authentication

### `local_users` table (`app/models/auth.py`)

| Column | Type | Status | Notes |
|--------|------|--------|-------|
| `email` | String(320) | ⚠️ | Login credential; Supabase auth is primary — this is the local fallback |
| `totp_secret` | EncryptedString(512) | 🔒 | TOTP shared secret (MFA) |

### `auth_logs` / login logs (`app/models/auth.py`)

| Column | Type | Status | Notes |
|--------|------|--------|-------|
| `email` | String(320) | ⚠️ | Email in login attempt log |
| `ip_address` | String(45) | ⚠️ | Pseudonymous IP; GDPR-relevant under Art. 4(1) |

---

## 3. HR (special-category data — GDPR Art. 9)

### `hr_employees` table (`app/models/hr.py`)

| Column | Type | Status | Notes |
|--------|------|--------|-------|
| `national_id` | String(255) | ⚠️ | **Swedish personnummer** — encodes DOB + gender. GDPR Art. 9 special-category data in some interpretations; Swedish DPA (IMY) treats personnummer as highly sensitive. **High priority for `EncryptedString`.** |
| `address` | Text | ⚠️ | Home address |
| `email` | String(255) | ⚠️ | Work/personal email |
| `phone` | String(50) | ⚠️ | Work/personal phone |

### `payroll_runs` table (`app/models/payroll.py`)

| Column | Type | Status | Notes |
|--------|------|--------|-------|
| `personal_number` | EncryptedString(64) | 🔒 | Swedish personnummer — encrypted. Same Art. 9 sensitivity as above but handled correctly. |

> **Action required:** `hr_employees.national_id` must be encrypted. Personnummer
> encryption uses the same `PII_ENCRYPTION_KEY` / `EncryptedString` pattern.

---

## 4. Financial PII

### `accounting_partners` table (`app/models/accounting_partners.py`)

| Column | Type | Status |
|--------|------|--------|
| `contact_email` | EncryptedString(1000) | 🔒 |
| `contact_phone` | EncryptedString(1000) | 🔒 |
| `bank_account` | EncryptedString(2000) | 🔒 |

### `bank_feed_accounts` table (`app/models/bank_feed.py`)

| Column | Type | Status | Notes |
|--------|------|--------|-------|
| `iban` | String(34) | ⚠️ | Bank account number — financial PII. Consider encrypting. |

### `payment_options` / `payment_signatures` (`app/models/payment_options.py`)

| Column | Type | Status |
|--------|------|--------|
| `signer_email` | String(254) | ⚠️ |
| `ip_address` | String(45) | ⚠️ |

---

## 5. E-commerce and storefront

### `online_orders` table (`app/models/ecommerce.py`)

| Column | Type | Status | Notes |
|--------|------|--------|-------|
| `customer_email` | String(255) | ⚠️ | Order-level email; not linked to a Customer row |
| `customer_name` | String(200) | ⚠️ | Guest checkout name |
| `shipping_address` | JSONB | ⚠️ | Delivery address (structured JSON) |

### `abandoned_carts` table (`app/models/ecommerce.py`)

| Column | Type | Status |
|--------|------|--------|
| `customer_email` | String(255) | ⚠️ |

### `product_waitlist` table (`app/models/product_waitlist.py`)

| Column | Type | Status |
|--------|------|--------|
| `email` | String(320) | ⚠️ |
| `name` | String(255) | ⚠️ |

### `local_payments` table (`app/models/local_payments.py`)

| Column | Type | Status |
|--------|------|--------|
| `customer_email` | String(320) | ⚠️ |

---

## 6. CRM, leads, and marketing

### `leads` table (`app/models/leads.py`)

| Column | Type | Status |
|--------|------|--------|
| `name` | String(300) | ⚠️ |
| `email` | String(255) | ⚠️ |
| `phone` | String(50) | ⚠️ |

### `growth_contacts` table (`app/models/growth.py`)

| Column | Type | Status |
|--------|------|--------|
| `company_name` | String(200) | ⚠️ |
| `contact_name` | String(200) | ⚠️ |
| `contact_email` | String(254) | ⚠️ |

### `campaign_recipients` table (`app/models/campaigns.py`)

| Column | Type | Status | Notes |
|--------|------|--------|-------|
| `email` | String(512) | ⚠️ | Marketing email recipient |

### `lead_form_submissions` table (`app/models/lead_forms.py`)

| Column | Type | Status |
|--------|------|--------|
| `submitter_email` | String(255) | ⚠️ |

### `sms_outbox` table (`app/models/sms_outbox.py`)

| Column | Type | Status |
|--------|------|--------|
| `phone_number` | String(30) | ⚠️ |

---

## 7. Bookings and services

### `group_booking_attendees` table (`app/models/group_booking.py`)

| Column | Type | Status |
|--------|------|--------|
| `name` | String(200) | ⚠️ |
| `email` | String(320) | ⚠️ |

### `family_members` table (`app/models/family_group.py`)

| Column | Type | Status | Notes |
|--------|------|--------|-------|
| `name` | String(200) | ⚠️ | Member name |
| `date_of_birth` | Date | ⚠️ | DOB — indirectly sensitive; needed for age-gated services |

### `live_chat_sessions` table (`app/models/live_chat.py`)

| Column | Type | Status |
|--------|------|--------|
| `visitor_name` | String(100) | ⚠️ |
| `visitor_email` | String(200) | ⚠️ |

---

## 8. Legal and governance

### `esign_signers` table (`app/models/esign.py`)

| Column | Type | Status |
|--------|------|--------|
| `name` | String(300) | ⚠️ |
| `email` | String(500) | ⚠️ |

### `esign_events` table (`app/models/esign.py`)

| Column | Type | Status |
|--------|------|--------|
| `actor_email` | String(500) | ⚠️ |
| `actor_name` | String(300) | ⚠️ |
| `ip_address` | String(64) | ⚠️ |

### `consent_records` table (`app/models/consent.py`)

| Column | Type | Status | Notes |
|--------|------|--------|-------|
| `ip_address` | String(64) | ⚠️ | Consent-capture IP — legally required for valid consent record |
| `requester_name` | String(300) | ⚠️ | DSAR requester name |
| `requester_email` | String(500) | ⚠️ | DSAR requester email |

### `customer_contracts` table (`app/models/customer_contract.py`)

| Column | Type | Status |
|--------|------|--------|
| `signer_email` | String(254) | ⚠️ |

---

## 9. Finance and investors

### `investors` table (`app/models/investor.py`)

| Column | Type | Status |
|--------|------|--------|
| `name` | String(200) | ⚠️ |
| `email` | String(320) | ⚠️ |

### `cap_table_shareholders` table (`app/models/cap_table.py`)

| Column | Type | Status |
|--------|------|--------|
| `name` | String(300) | ⚠️ |
| `email` | String(320) | ⚠️ |

---

## 10. Audit and system logs

### `audit_log_entries` table (`app/models/audit.py`)

| Column | Type | Status | Notes |
|--------|------|--------|-------|
| `ip_address` | String(64) | ⚠️ | GDPR Art. 4(1) — an IP is personal data. Required for audit trail; consider pseudonymisation after 90 days. |
| `actor_user_id` | UUID | — | Pseudonymous after org erasure |

---

## 11. Third-party processors

Data shared with external processors under DPA agreements:

| Processor | Data shared | DPA status |
|-----------|------------|-----------|
| Supabase | Auth tokens, user email (login) | Supabase DPA (GDPR-compliant) |
| Stripe | Customer name, email, card data | Stripe DPA (PCI-DSS + GDPR) |
| Resend | Recipient email, email content | Resend DPA required — verify |
| Sentry | Stack traces, request paths, may contain PII in URL params | PII scrubbing: configure `before_send` to strip PII |
| Fortnox | Invoice data, org VAT number | Fortnox GDPR DPA via Swedish standard |

---

## 12. Retention schedule

| Table / category | Legal basis | Retention period | Delete mechanism |
|-----------------|------------|-----------------|-----------------|
| Invoices, line items, payments | BFL 7 kap. 2 § (legal obligation) | 7 years after fiscal year end | Retained; customer PII anonymised on erasure request |
| Customer PII (name, email, phone, address) | Contract (Art. 6(1)(b)) | Duration of relationship + 1 year | `DELETE /api/gdpr/organization` anonymises |
| Auth logs (IP, email) | Legitimate interest (security) | 90 days | No automated purge yet — add to scheduler |
| Audit log | Legal obligation + legitimate interest | 7 years | No automated purge — out of scope for BFL retention |
| HR employees | Employment contract + labour law | Duration of employment + 5 years (SE) | Manual process via HR admin |
| Personal number (payroll) | Employment / tax obligation | 7 years (Skatteverket) | Manual process |
| Marketing emails / consents | Consent (Art. 6(1)(a)) | Until withdrawn | `gdpr_consent` endpoints |
| E-commerce orders (guest) | Contract | 3 years | No automated purge yet |
| IP addresses in audit log | Legitimate interest | Pseudonymise after 90 days | Not yet implemented |
| Chat sessions | Legitimate interest | 90 days | Not yet implemented |

---

## 13. Open gaps (prioritised)

| Priority | Gap | Column(s) | Recommendation |
|----------|-----|-----------|---------------|
| HIGH | `hr_employees.national_id` unencrypted | `national_id` | Add `EncryptedString(255)` — personnummer is special-category data |
| HIGH | `suppliers.email/phone/address` unencrypted | see above | Add `EncryptedString` — mirrors what was done for `Customer` in Phase 4 |
| MEDIUM | `bank_feed_accounts.iban` unencrypted | `iban` | Add `EncryptedString(64)` — bank account number is financial PII |
| MEDIUM | Auth log IP retention | `auth_logs.ip_address` | Add scheduler job to pseudonymise (hash) IPs after 90 days |
| MEDIUM | `ecommerce.customer_email/name/shipping_address` unencrypted | see above | Add `EncryptedString` or separate encrypted PII column |
| LOW | Sentry PII leak | Sentry integration | Configure `before_send` to strip query-string params that may contain email / token |
| LOW | Chat session / IP retention | `live_chat_sessions` | Add 90-day purge job |
| LOW | Resend DPA | — | Verify Resend DPA is signed and covers SE/EU data subjects |

---

*This document was generated by code review (M-9). Re-run the PII scan after
adding new models: `grep -rn "EncryptedString\|email\|phone\|address\|national_id\|iban" backend/app/models/ | grep "mapped_column"`*
