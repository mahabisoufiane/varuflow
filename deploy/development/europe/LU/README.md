# Luxembourg — development

| Field | Value |
|-------|-------|
| ISO   | LU |
| Region | europe |
| Currency | EUR |
| VAT | 17.0% |
| Locale | fr-LU |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-development-lu)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://lu.varuflow.app
FRONTEND_URL=https://lu.varuflow.app
PORTAL_BASE_URL=https://lu.varuflow.app
DATABASE_URL=<tier-specific Postgres for LU>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-development-lu)
NEXT_PUBLIC_API_URL=https://api-lu-development.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=LU
NEXT_PUBLIC_DEFAULT_LOCALE=fr-LU
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
