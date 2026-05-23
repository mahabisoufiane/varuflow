# Ireland — preproduction

| Field | Value |
|-------|-------|
| ISO   | IE |
| Region | europe |
| Currency | EUR |
| VAT | 23.0% |
| Locale | en-IE |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-ie)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://ie.varuflow.app
FRONTEND_URL=https://ie.varuflow.app
PORTAL_BASE_URL=https://ie.varuflow.app
DATABASE_URL=<tier-specific Postgres for IE>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-ie)
NEXT_PUBLIC_API_URL=https://api-ie-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=IE
NEXT_PUBLIC_DEFAULT_LOCALE=en-IE
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
