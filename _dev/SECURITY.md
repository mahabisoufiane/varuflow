# Varuflow Security Audit
_Last updated: 2026-04-11_

---

## Vulnerabilities Found & Status

| # | Vulnerability | Severity | Status | Fix location |
|---|---------------|----------|--------|--------------|
| 1 | Login `<Link>` used bare `next/link` — locale prefix missing, broke navigation to `/[locale]/auth/login` | High | **FIXED** | `auth/login/page.tsx`, `auth/signup/page.tsx`, `auth/forgot-password/page.tsx` |
| 2 | `(app)/layout.tsx` redirect used `/auth/login` (no locale prefix) — caused redirect loop | High | **FIXED** | `(app)/layout.tsx` — now `/${locale}/auth/login` |
| 3 | Open redirect: `?next=` param accepted absolute URLs — could redirect users to attacker-controlled sites | High | **FIXED** | `auth/login/page.tsx` — `safeNext()` rejects `://` and `//` prefixes |
| 4 | Missing `NEXT_PUBLIC_SUPABASE_ANON_KEY` in `next.config.mjs` env bake | Medium | **FIXED** | `next.config.mjs` |
| 5 | Missing HTTP security headers (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`) | Medium | **FIXED** | `next.config.mjs` `headers()` function |
| 6 | No plan-level enforcement dependency in backend | Medium | **FIXED** | `backend/app/middleware/plan_check.py` created |
| 7 | Hardcoded English error strings in auth pages — raw Supabase errors shown to users | Low | **FIXED** | `auth/login/page.tsx` — `mapAuthError()` maps to i18n keys |
| 8 | `deprecated React.FormEvent` (bare, non-generic) in signup and login | Low | **FIXED** | Both auth pages use `React.FormEvent<HTMLFormElement>` |

---

## OWASP Top 10 Checklist

| Item | Status | Notes |
|------|--------|-------|
| A01 Broken Access Control | **MITIGATED** | JWT on every backend route via `get_current_user`; portal token blocked from internal routes; all queries filtered by `org_id` |
| A02 Cryptographic Failures | **MITIGATED** | HTTPS enforced by Vercel + Railway; Supabase JWT signed with HS256 + `SUPABASE_JWT_SECRET` |
| A03 Injection | **MITIGATED** | SQLAlchemy ORM throughout; Pydantic validation on all request bodies; no f-string SQL |
| A04 Insecure Design | **MITIGATED** | Multi-tenant isolation via `org_id` filter on every query; `plan_check.py` guards premium features |
| A05 Security Misconfiguration | **MITIGATED** | CORS reads from `CORS_ORIGINS` env var (never `*`); `DEBUG=False`/`ENV=production` on Railway; security headers on frontend |
| A06 Vulnerable Components | **ACCEPTED** | Dependencies audited at time of writing; no known critical CVEs in `pyproject.toml` or `package.json`; recommend monthly `pip audit` + `npm audit` |
| A07 Auth Failures | **MITIGATED** | `slowapi` rate limiter active globally (200/min default); login errors map to generic messages; session tokens in httpOnly cookies via `@supabase/ssr` |
| A08 Software Integrity | **MITIGATED** | `package-lock.json` committed; `poetry.lock` committed |
| A09 Logging Failures | **MITIGATED** | Structured JSON logging; `send_default_pii=False` in Sentry; no email/token logging in any route |
| A10 SSRF | **ACCEPTED** | No user-supplied URLs are fetched server-side currently; if added, must validate against allowlist |

---

## RLS Policies

RLS must be enabled and policies applied via Supabase SQL editor.
Run the following **once** in the Supabase SQL editor for your project:

```sql
-- Enable RLS on all tenant tables
ALTER TABLE organizations        ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE products             ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_items      ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices             ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers            ENABLE ROW LEVEL SECURITY;

-- Helper: resolve the caller's org_id from their user_id
-- (organization_members is the join table)
CREATE OR REPLACE FUNCTION auth_org_id() RETURNS uuid
  LANGUAGE sql STABLE SECURITY DEFINER
AS $$
  SELECT org_id FROM organization_members WHERE user_id = auth.uid() LIMIT 1;
$$;

-- Organizations: each user sees only their own org
CREATE POLICY "org_isolation" ON organizations
  FOR ALL USING (id = auth_org_id());

-- Organization members: see only members of your own org
CREATE POLICY "members_isolation" ON organization_members
  FOR ALL USING (org_id = auth_org_id());

-- Products
CREATE POLICY "products_isolation" ON products
  FOR ALL USING (organization_id = auth_org_id());

-- Inventory
CREATE POLICY "inventory_isolation" ON inventory_items
  FOR ALL USING (organization_id = auth_org_id());

-- Invoices
CREATE POLICY "invoices_isolation" ON invoices
  FOR ALL USING (organization_id = auth_org_id());

-- Customers
CREATE POLICY "customers_isolation" ON customers
  FOR ALL USING (organization_id = auth_org_id());
```

**Status:** SQL provided — must be run manually in Supabase dashboard.
The backend additionally enforces org isolation at the query level in every router.

---

## Rate Limits

| Endpoint | Limit | Implementation |
|----------|-------|----------------|
| All endpoints (default) | 200 req/min per IP | `slowapi` global limiter in `main.py` |
| POST `/api/auth/login` | Handled by Supabase Auth (built-in brute-force protection) | Supabase dashboard |

---

## CORS Configuration

```python
# backend/app/main.py
origins = os.getenv("CORS_ORIGINS", "https://varuflow.vercel.app").split(",")
# Railway env var: CORS_ORIGINS=https://varuflow.vercel.app
```

Never `allow_origins=["*"]`. The `CORS_ORIGINS` env var is the single source of truth.

---

## Known Remaining Risks & Mitigation Plan

| Risk | Mitigation |
|------|------------|
| Supabase RLS not yet applied | Must be run manually in Supabase SQL editor using the SQL above |
| No automated dependency CVE scanning | Add `pip audit` and `npm audit --audit-level=high` to CI pipeline |
| Fortnox tokens stored in plaintext in DB | Acceptable for MVP; encrypt at rest with `cryptography` library before GA |
| No per-user rate limit on auth (only per-IP) | Supabase Auth has built-in brute-force protection; add explicit limit if self-hosting |
| A10 SSRF: no external URL fetching currently | If Fortnox webhook URLs become user-configurable, validate against `https://` + allowlist |
