# Kuwait — preproduction

| Field | Value |
|-------|-------|
| ISO   | KW |
| Region | middle-east |
| Currency | KWD |
| VAT | 0.0% |
| Locale | ar-KW |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-kw)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://kw.varuflow.app
FRONTEND_URL=https://kw.varuflow.app
PORTAL_BASE_URL=https://kw.varuflow.app
DATABASE_URL=<tier-specific Postgres for KW>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-kw)
NEXT_PUBLIC_API_URL=https://api-kw-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=KW
NEXT_PUBLIC_DEFAULT_LOCALE=ar-KW
NEXT_PUBLIC_DEFAULT_CURRENCY=KWD
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
