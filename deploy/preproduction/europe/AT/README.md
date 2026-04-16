# Austria — preproduction

| Field | Value |
|-------|-------|
| ISO   | AT |
| Region | europe |
| Currency | EUR |
| VAT | 20.0% |
| Locale | de-AT |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-at)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://at.varuflow.app
FRONTEND_URL=https://at.varuflow.app
PORTAL_BASE_URL=https://at.varuflow.app
DATABASE_URL=<tier-specific Postgres for AT>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-at)
NEXT_PUBLIC_API_URL=https://api-at-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=AT
NEXT_PUBLIC_DEFAULT_LOCALE=de-AT
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
