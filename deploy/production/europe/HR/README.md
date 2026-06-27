# Croatia — production

| Field | Value |
|-------|-------|
| ISO   | HR |
| Region | europe |
| Currency | EUR |
| VAT | 25.0% |
| Locale | hr-HR |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-hr)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://hr.varuflow.app
FRONTEND_URL=https://hr.varuflow.app
PORTAL_BASE_URL=https://hr.varuflow.app
DATABASE_URL=<tier-specific Postgres for HR>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-hr)
NEXT_PUBLIC_API_URL=https://api-hr-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=HR
NEXT_PUBLIC_DEFAULT_LOCALE=hr-HR
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
