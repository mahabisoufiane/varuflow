# Jordan — production

| Field | Value |
|-------|-------|
| ISO   | JO |
| Region | middle-east |
| Currency | JOD |
| VAT | 16.0% |
| Locale | ar-JO |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-jo)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://jo.varuflow.app
FRONTEND_URL=https://jo.varuflow.app
PORTAL_BASE_URL=https://jo.varuflow.app
DATABASE_URL=<tier-specific Postgres for JO>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-jo)
NEXT_PUBLIC_API_URL=https://api-jo-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=JO
NEXT_PUBLIC_DEFAULT_LOCALE=ar-JO
NEXT_PUBLIC_DEFAULT_CURRENCY=JOD
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
