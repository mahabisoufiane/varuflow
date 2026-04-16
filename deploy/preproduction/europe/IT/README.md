# Italy — preproduction

| Field | Value |
|-------|-------|
| ISO   | IT |
| Region | europe |
| Currency | EUR |
| VAT | 22.0% |
| Locale | it-IT |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-it)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://it.varuflow.app
FRONTEND_URL=https://it.varuflow.app
PORTAL_BASE_URL=https://it.varuflow.app
DATABASE_URL=<tier-specific Postgres for IT>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-it)
NEXT_PUBLIC_API_URL=https://api-it-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=IT
NEXT_PUBLIC_DEFAULT_LOCALE=it-IT
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
