# Spain — production

| Field | Value |
|-------|-------|
| ISO   | ES |
| Region | europe |
| Currency | EUR |
| VAT | 21.0% |
| Locale | es-ES |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-production-es)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://es.varuflow.app
FRONTEND_URL=https://es.varuflow.app
PORTAL_BASE_URL=https://es.varuflow.app
DATABASE_URL=<tier-specific Postgres for ES>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-production-es)
NEXT_PUBLIC_API_URL=https://api-es-production.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=ES
NEXT_PUBLIC_DEFAULT_LOCALE=es-ES
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
