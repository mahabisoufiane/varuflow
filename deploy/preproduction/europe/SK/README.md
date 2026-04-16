# Slovakia — preproduction

| Field | Value |
|-------|-------|
| ISO   | SK |
| Region | europe |
| Currency | EUR |
| VAT | 23.0% |
| Locale | sk-SK |

## Expected env overrides for this deployment

```env
# Backend (Railway project: varuflow-preproduction-sk)
ENV=production   # pre-prod mirrors prod hardening
CORS_ORIGINS=https://sk.varuflow.app
FRONTEND_URL=https://sk.varuflow.app
PORTAL_BASE_URL=https://sk.varuflow.app
DATABASE_URL=<tier-specific Postgres for SK>
STRIPE_SECRET_KEY=<tier + country specific>
```

```env
# Frontend (Vercel project: varuflow-preproduction-sk)
NEXT_PUBLIC_API_URL=https://api-sk-preproduction.varuflow.app
NEXT_PUBLIC_DEFAULT_COUNTRY=SK
NEXT_PUBLIC_DEFAULT_LOCALE=sk-SK
NEXT_PUBLIC_DEFAULT_CURRENCY=EUR
```

## Infra provisioning
Replace the placeholders above before creating Railway / Vercel projects.
Never hardcode secrets in this file.
