# Türkiye — production

| Field | Value |
|-------|-------|
| ISO   | TR |
| Region | middle-east |
| Currency | TRY |
| VAT | 20.0% |
| Locale | tr-TR |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-tr)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://tr.varuflow.app
FRONTEND_URL=https://tr.varuflow.app
PORTAL_BASE_URL=https://tr.varuflow.app
DATABASE_URL=<tier-specific Postgres for TR>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-tr)
NEXT_PUBLIC_API_URL=https://api-tr-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=TR
NEXT_PUBLIC_DEFAULT_LOCALE=tr-TR
NEXT_PUBLIC_DEFAULT_CURRENCY=TRY
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
