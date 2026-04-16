# Varuflow Project Audit — 2026-04-16

> Auto-generated against the rules in `CLAUDE.md` and `AGENTS.md`.
> Legend: ✅ PASS — ⚠️ PARTIAL — 🔴 FAIL / SECURITY ISSUE

---

## 🔴 Critical security findings — fix before any public launch

### 1. JWT signature verification is disabled in production
**File**: [backend/app/middleware/auth.py](backend/app/middleware/auth.py#L27-L53)

`_decode_token()` calls `jwt.decode(..., options={"verify_signature": False, ...})`
unconditionally. The TODO says this was temporarily disabled "until
`SUPABASE_JWT_SECRET` is confirmed correct in Railway," but the comment has
been in place long enough to be a standing hole. Any caller can forge a
token by generating any JWT locally — the backend accepts it as long as the
structure is valid.

**Fix (do not apply blindly — will 401 all users until Railway secret is
confirmed)**:
```python
if settings.SUPABASE_JWT_SECRET:
    return jwt.decode(
        token, settings.SUPABASE_JWT_SECRET,
        algorithms=["HS256"], options={"verify_aud": False},
    )
if settings.ENV == "development":
    return jwt.decode(token, "", algorithms=["HS256"],
                      options={"verify_signature": False, "verify_aud": False})
raise JWTError("SUPABASE_JWT_SECRET not configured")
```

### 2. `validate_production_config()` is a no-op
**File**: [backend/app/config.py](backend/app/config.py#L134-L170)

Every real check is commented out. On Railway with placeholder
`PORTAL_JWT_SECRET` / `AUTH_JWT_SECRET` / empty `SUPABASE_JWT_SECRET`,
the app boots happily. Re-enable the blocks once Railway secrets are verified.

---

## ✅ Passes

| Rule | Status | Notes |
|------|--------|-------|
| CORSMiddleware uses `settings.CORS_ORIGINS` env var (no wildcard) | ✅ | [main.py#L101](backend/app/main.py#L101) |
| CORS includes `OPTIONS` in methods | ✅ | [main.py#L105](backend/app/main.py#L105) |
| Security headers middleware present | ✅ | [main.py#L113-L119](backend/app/main.py#L113-L119) |
| Global exception handler preserves CORS | ✅ | [main.py#L141-L166](backend/app/main.py#L141-L166) |
| Portal JWT blocked on internal routes | ✅ | [auth.py#L89-L94](backend/app/middleware/auth.py#L89-L94) |
| `ai_engine.py` has zero OpenAI imports | ✅ | verified by grep |
| `reactStrictMode: false` in `next.config.mjs` | ✅ | [next.config.mjs](frontend/next.config.mjs) |
| Turbopack uses top-level `turbopack.resolveAlias` | ✅ | [next.config.mjs](frontend/next.config.mjs) |
| `customers/new/page.tsx` exists | ✅ | [page.tsx](frontend/src/app/[locale]/(app)/customers/new/page.tsx) |
| No hardcoded Railway URL in `frontend/src/` | ✅ | grep: 0 results |
| `api-client.ts` handles 401 with silent refresh + retry | ✅ | [api-client.ts](frontend/src/lib/api-client.ts) |

---

## ⚠️ Partial / needs attention

### A. Middleware order
`RateLimitMiddleware` is registered **before** `CORSMiddleware`
([main.py#L99](backend/app/main.py#L99)). Starlette's stack is LIFO, so
CORS *is* outermost in practice — this is the intended order, but
[CLAUDE.md](CLAUDE.md) Rule 1 states "CORSMiddleware MUST be first
registered." The code comment explains the intent. Either update
CLAUDE.md to reflect reality or refactor to move rate-limit behind CORS.

### B. Locale coverage
Before this audit only `en.json` and `sv.json` existed — AGENTS.md
requires also `no.json`, `da.json`. **Fixed by this change**:
29 additional locale files seeded from `en.json` in
[frontend/messages/](frontend/messages/). They now need human translation.

### C. Fortnox redirect URI is hardcoded to prod Railway domain
[config.py#L47](backend/app/config.py#L47):
```python
FORTNOX_REDIRECT_URI: str = "https://varuflow-production.up.railway.app/api/integrations/fortnox/callback"
```
Per-country deployments will need their own callback URL — move to
`.env.<tier>` templates (done in [deploy/](deploy/)).

### D. Dev bypass on invalid token
[auth.py#L79-L86](backend/app/middleware/auth.py#L79-L86) silently serves the
dev user on JWT decode errors when `ENV=development`. Safe as long as
`ENV=development` is never set on Railway — there is no defense-in-depth
check.

---

## 🆕 What this audit added

New structure under the repo root:

```
config/countries/<code>.json      69 countries × 1 file   (tax, VAT, currency)
config/countries/index.json        master list (machine-readable)
docs/legal/<code>/README.md        per-country compliance placeholder
deploy/<env>/                      development | preproduction | production
  ├── backend.env.example
  ├── frontend.env.example
  └── <region>/<code>/README.md    per-country per-tier override guide
backend/.env.<tier>.example        3 tiers × 1 file
frontend/.env.<tier>.example       3 tiers × 1 file
frontend/messages/<locale>.json    29 new locale seeds (copies of en.json)
scripts/scaffold_global.py         idempotent generator (safe to re-run)
```

All generated files are **scaffolding only** — they contain no secrets and
ship with placeholder values. Review before use in any real deployment.

---

## 📋 Recommended next steps (human-in-the-loop)

1. **Resolve the JWT-verification TODO** — verify `SUPABASE_JWT_SECRET` on
   Railway matches the Supabase project, then re-enable signature
   verification in `_decode_token` and re-enable the checks in
   `validate_production_config`.
2. **Translate the 29 seeded locale files** — they currently contain English
   strings. Route them through your translation pipeline.
3. **Verify VAT rates** in `config/countries/<code>.json` with local
   counsel before using them in billing logic. Rates change.
4. **Do not** create physical per-country copies of `backend/` / `frontend/`.
   The correct pattern is one codebase, many tier + country deployments —
   see `deploy/<env>/<region>/<code>/README.md` for the Railway/Vercel
   project naming convention.
5. Run `python3 scripts/scaffold_global.py` any time you add a new country.
